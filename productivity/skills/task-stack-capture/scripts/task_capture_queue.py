# /// script
# dependencies = ["pyyaml"]
# ///
"""The work of one task-capture Run, gathered in code before the session.

Reads every capture source (see _common.py), the capture ledger and, unless --offline, the
owner's task stack in the Portal (read only), and sorts the items:

- processed: the ledger already holds them in a final state. Left out.
- closed: closed at the source (ticked, or the time study saw them kept) and not yet final in
  the ledger. Listed for task_capture_record.py to record; never queued.
- expired: open, never seen by a Run, and dated more than --horizon-days (14) ago. Listed,
  never queued; launch with a larger horizon to capture further back.
- queued: the rest, newest first (no date counts as today), at most --max (40), cut into
  batches of --batch-size (10); deferred: the open items past the cap.

Each queued item carries its marker (the one task-stack-apply gives a create with
`source: <key>`) and, from the Portal: `already` (a task already carrying the marker),
`candidates` (up to five of the owner's tasks, open or closed in the last 60 days, whose
titles are close, with a score: a hint, never a decision) and `domain_hint` (the domain whose
name matches the item's domain, with its catch-all project). The JSON also lists the owner's
contact id and every active domain with its catch-all project. When the Portal cannot be read
the first line says STALE and the queue is still written, without hints.

First line: `QUEUE: 12 item(s) queued (...); 3 expired; 1 closed; 0 deferred` or `NOTHING: ...`.
--out writes a new file and never overwrites one. Read only toward the sources and the Portal.
Exit 0 when it ran, 2 for a bad argument or an unusable sources file. A blank option from a
launch form (--max=) means not given.

Example:
    python3 task_capture_queue.py --out RUN/capture-queue.json --max=40
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

import _common as c

TOOL = "task-capture-queue"
VERSION = 1
MAX_DEFAULT, HORIZON_DEFAULT, BATCH_DEFAULT = 40, 14, 10
HINT_THRESHOLD = 0.5
HINTS = 5
CLOSED_WINDOW_DAYS = 60
OPEN_TASK_STATUSES = ("TODO", "IN_PROGRESS", "WAITING")
# Clock times and recording hashes say nothing about the commitment, and their digits would
# make two items read as different periods.
NOISE = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b|\([0-9a-f]{6,}\)|\b[0-9a-f]{8,}\b")
_TAG = re.compile(r"^\s*(?:\[[^\]]*\]\s*|\([^)]*\)\s*|(?:re|fw|fwd|todo|action|task)\s*:\s*)+", re.I)
_PUNCT = re.compile(r"[^a-z0-9 ]+")
STOP_WORDS = frozenset("a an and the to for with of on in at by from re fw fwd about please".split())
MONTHS = frozenset("january february march april may june july august september october november december "
                   "jan feb mar apr jun jul aug sep sept oct nov dec q1 q2 q3 q4".split())


# --------------------------------------------------------------------------- matching

def normalise_title(title):
    """Lower case, mail prefixes and tags removed, punctuation and filler words dropped."""
    text = _PUNCT.sub(" ", _TAG.sub("", str(title or "").lower()))
    return " ".join(w for w in text.split() if w not in STOP_WORDS)


def similarity(a, b):
    """How alike two normalised titles read; titles naming different numbers or periods
    ("OI-022" and "OI-023", "August" and "September") are different items."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ma = {w for w in a.split() if any(ch.isdigit() for ch in w) or w in MONTHS}
    mb = {w for w in b.split() if any(ch.isdigit() for ch in w) or w in MONTHS}
    if ma and mb and ma != mb:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def words(text):
    return normalise_title(NOISE.sub(" ", str(text or "")))


def match_score(item_words, title):
    """The title similarity, or the share of the shorter side's content words the two share
    (two at least), whichever is higher."""
    other = normalise_title(title)
    if not item_words or not other:
        return 0.0
    a = {w for w in item_words.split() if len(w) > 2}
    b = {w for w in other.split() if len(w) > 2}
    shared = a & b
    overlap = len(shared) / min(len(a), len(b)) if a and b and len(shared) >= 2 else 0.0
    return round(max(similarity(item_words, other), 0.9 * overlap), 2)


def catch_alls(projects):
    """Each domain's open catch-all project (is_general)."""
    out = {}
    for p in projects:
        if p.get("is_general") and not p.get("is_archived") and str(p.get("domain_id") or ""):
            out.setdefault(str(p["domain_id"]).lower(), str(p.get("id")).lower())
    return out


def portal_context(corpus, owner, today):
    """The owner's tasks worth comparing with (open, or closed in the window) and the domains."""
    projects = corpus.get("project") or []
    pmap = {str(p.get("id")).lower(): p for p in projects}
    dnames = {str(d.get("id")).lower(): str(d.get("name") or "") for d in corpus.get("domain") or []}
    general = catch_alls(projects)
    since = today - timedelta(days=CLOSED_WINDOW_DAYS)
    tasks = []
    for t in corpus.get("task") or []:
        holder = str(t.get("owner_contact_id") or "").lower()
        if owner and holder and holder != owner.lower():
            continue
        status = str(t.get("status") or "").upper()
        if status not in OPEN_TASK_STATUSES:
            updated = c.parse_day(t.get("updated_at") or t.get("completed_at"))
            if updated is None or updated < since:
                continue
        project = pmap.get(str(t.get("project_id") or "").lower()) or {}
        did = str(project.get("domain_id") or t.get("domain_id") or "").lower()
        tasks.append({"ref": f"portal://task/{str(t.get('id')).lower()}", "title": str(t.get("title") or ""),
                      "status": status, "project": project.get("name"), "domain": dnames.get(did),
                      "due": t.get("due_date"), "source_reference": str(t.get("source_reference") or ""),
                      "description": str(t.get("description") or "")})
    domains = [d for d in corpus.get("domain") or [] if d.get("is_active", True) is not False]
    return {"tasks": tasks,
            "domains": [{"id": str(d.get("id")).lower(), "name": d.get("name"),
                         "catch_all_project": general.get(str(d.get("id")).lower())} for d in domains]}


def hints(item, ctx):
    marker = item["marker"]
    already = next((t["ref"] for t in ctx["tasks"]
                    if t["source_reference"] == marker or marker in t["description"]), None)
    mine = words(item["text"])
    scored = sorted(((match_score(mine, t["title"]), t) for t in ctx["tasks"]), key=lambda x: (-x[0], x[1]["ref"]))
    scored = [(s, t) for s, t in scored if s >= HINT_THRESHOLD]
    domain_hint = None
    want = str(item.get("domain") or "").strip().lower()
    if want:
        for d in ctx["domains"]:
            name = str(d.get("name") or "").lower()
            if name and (name == want or want in name or name in want):
                domain_hint = d
                break
    return {"already": already, "domain_hint": domain_hint,
            "candidates": [{"ref": t["ref"], "title": t["title"], "status": t["status"], "project": t["project"],
                            "domain": t["domain"], "due": t["due"], "score": s} for s, t in scored[:HINTS]]}


def read_portal(config, server):
    """(corpus, owner contact id) read through the Portal: domains (inactive too, since they
    still own tasks), projects, and tasks of every status."""
    client = c.Portal(config or None, server or None)
    who = client.call("whoami")
    principal = (who.get("principal") or {}) if isinstance(who, dict) else {}
    owner = str(principal.get("contact_id") or "").strip() or None
    corpus = {"domain": client.list_all("domain", {"include_inactive": True}),
              "project": client.list_all("project"), "task": client.list_all("task")}
    seen = {str(t.get("id")) for t in corpus["task"]}
    for status in ("DONE", "CANCELLED"):
        for row in client.list_all("task", {"status": status}):
            if str(row.get("id")) not in seen:
                seen.add(str(row.get("id")))
                corpus["task"].append(row)
    return corpus, owner


# --------------------------------------------------------------------------- the queue

def _brief(item):
    return {"key": item["key"], "source": item["source"], "ref": item["ref"], "date": item["date"],
            "marker": item["marker"]}


def build(items, reports, recorded, *, today, max_items=MAX_DEFAULT, horizon_days=HORIZON_DEFAULT,
          batch_size=BATCH_DEFAULT, ctx=None, owner=None, portal="offline"):
    cutoff = today - timedelta(days=horizon_days)
    processed, closed, expired, candidates = [], [], [], []
    for it in items:
        row = recorded.get(it["key"])
        day = c.parse_day(it["date"])
        if row and row.get("state") in c.FINAL:
            processed.append(it["key"])
        elif not it["open"]:
            closed.append(it)
        elif row is None and day is not None and day < cutoff:
            expired.append(it)
        else:
            candidates.append(dict(it, attempts=int((row or {}).get("attempts") or 0),
                                   first_seen=(row or {}).get("first_seen") or None))
    candidates.sort(key=lambda i: (str(i["date"] or today.isoformat()), str(i.get("time") or ""), i["key"]),
                    reverse=True)
    queued, deferred = candidates[:max_items], candidates[max_items:]
    for n, it in enumerate(queued):
        it["batch"] = f"b{n // batch_size + 1}"
        if ctx is not None:
            it.update(hints(it, ctx))
    per_source = {}
    for it in queued:
        per_source[it["source"]] = per_source.get(it["source"], 0) + 1
    return {
        "tool": TOOL, "version": VERSION,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "as_of": today.isoformat(), "horizon_days": horizon_days, "max": max_items, "batch_size": batch_size,
        "portal": portal, "owner_contact_id": owner, "sources": list(reports),
        "counts": {"found": len(items), "processed": len(processed), "closed": len(closed),
                   "expired": len(expired), "queued": len(queued), "deferred": len(deferred),
                   "per_source": per_source},
        "batches": sorted({i["batch"] for i in queued}, key=lambda b: int(b[1:])),
        "items": queued,
        "deferred": [_brief(i) for i in deferred],
        "expired": [_brief(i) for i in expired],
        "closed": [_brief(i) for i in closed],
        "domains": (ctx or {}).get("domains") or [],
    }


def first_line(result):
    n = result["counts"]
    unreadable = [s["name"] for s in result["sources"] if s.get("readable") is False]
    tail = f"; unreadable: {', '.join(unreadable)}" if unreadable else ""
    portal = "" if result["portal"] in ("read", "offline") else f"; {result['portal']}"
    if not n["queued"]:
        return (f"NOTHING: no new source item to capture ({n['found']} found, {n['processed']} processed before); "
                f"{n['expired']} expired; {n['closed']} closed{tail}{portal}")
    where = ", ".join(f"{k} {v}" for k, v in n["per_source"].items())
    return (f"QUEUE: {n['queued']} item(s) queued ({where}); {n['expired']} expired; {n['closed']} closed; "
            f"{n['deferred']} deferred{tail}{portal}")


def as_text(result):
    lines = [first_line(result)]
    for it in result["items"]:
        extra = f" already {it['already']}" if it.get("already") else ""
        cands = f" ({len(it['candidates'])} candidate duplicate(s))" if it.get("candidates") else ""
        lines.append(f"  {it['batch']} {it['key']} {it['date'] or '-'}: {it['text'][:90]}{extra}{cands}")
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(prog="task_capture_queue.py", description=__doc__.split("\n\n")[0])
    p.add_argument("--sources", default="", help="The capture sources file (default: the settings)")
    p.add_argument("--state", default="", help="The task-stack state folder")
    p.add_argument("--max", default=str(MAX_DEFAULT), help="At most this many items (default 40)")
    p.add_argument("--horizon-days", default=str(HORIZON_DEFAULT), help="Older new items are expired (default 14)")
    p.add_argument("--batch-size", default=str(BATCH_DEFAULT), help="Items per worker batch (default 10)")
    p.add_argument("--source", default="", help="Only this source, by name")
    p.add_argument("--as-of", default="", help="Judge against this date (YYYY-MM-DD) instead of today")
    p.add_argument("--offline", action="store_true", help="Read no Portal: no duplicate hints")
    p.add_argument("--format", choices=("text", "json"), default="text")
    p.add_argument("--out", default="", help="Also write the JSON to this new file (never overwritten)")
    p.add_argument("--config", default="", help="MCP config holding the Portal (default: setting portal_mcp_config)")
    p.add_argument("--server", default="", help="The Portal's server name (default: setting portal_server)")
    a = p.parse_args(argv)
    try:
        cap = c.whole_number(a.max, "max", MAX_DEFAULT, 1, 1000)
        horizon = c.whole_number(a.horizon_days, "horizon-days", HORIZON_DEFAULT, 0, 3650)
        size = c.whole_number(a.batch_size, "batch-size", BATCH_DEFAULT, 1, 200)
        today = c.as_of_date(a.as_of)
        out_path = Path(a.out).expanduser() if a.out.strip() else None
        if out_path is not None and out_path.exists():
            raise c.Bad(f"--out {a.out!r} exists; this command never overwrites a file")
        sources, _origin = c.load_sources(a.sources)
        only = a.source.strip()
        if only and only not in {s["name"] for s in sources}:
            raise c.Bad(f"--source {only!r} is not one of {', '.join(s['name'] for s in sources)}")
        items, reports = c.gather(sources, only)
        recorded = c.read_ledger(c.state_root(a.state))
    except c.Bad as exc:
        c.fail(exc)

    ctx, owner, portal = None, None, "offline"
    if not a.offline:
        try:
            corpus, owner = read_portal(a.config, a.server)
            ctx = portal_context(corpus, owner, today)
            portal = "read"
        except Exception as exc:  # the queue stands without hints
            portal = f"STALE: the Portal could not be read ({type(exc).__name__}); no duplicate hints"
    result = build(items, reports, recorded, today=today, max_items=cap, horizon_days=horizon,
                   batch_size=size, ctx=ctx, owner=owner, portal=portal)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("x", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1, ensure_ascii=False, default=str)
            fh.write("\n")
    if a.format == "json":
        print(json.dumps(result, indent=1, ensure_ascii=False, default=str))
    else:
        print(c.safe(as_text(result) if out_path is None else first_line(result)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
