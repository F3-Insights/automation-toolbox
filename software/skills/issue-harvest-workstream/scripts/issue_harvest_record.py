#!/usr/bin/env python3
"""Record each queued source item's outcome in the harvest ledger, after issue_file.py.

Reads RUN/harvest.json (what was queued and deferred), RUN/decisions.json (the session's decision
per item) and RUN/filed.json (what issue_file.py did), and upserts one ledger row per item:

    new: filed, or an issue already carried its marker      -> filed (repo, issue, url, verified)
    new: an open issue already had exactly its title         -> duplicate (that issue)
    comment: commented, or the comment was already there      -> commented
    new or comment: refused, failed, or issue-file not run    -> seen, one more attempt; stuck at three
    duplicate / not-software / ask                            -> duplicate / not-software / asked
    queued with no decision                                   -> seen, one more attempt; stuck at three
    deferred past the cap                                     -> seen (no attempt counted)

An item a `new` decision carries in `also` gets the same outcome as the item it rides with. An
item filed in parts has one row listing every part; it is final only when every part is. A row
keeps its first_seen. Then the Run is appended to runs.jsonl (its start is the next Run's window
start) and RUN/record.json is written. A dry run (--dry-run-if true, or decisions.json says
`"dry_run": true`) writes only RUN/record-dry-run.json.

State folder: --state, else setting `state` under [issue-harvest-workstream], else
<state_dir>/issue-harvest. Prints `RECORDED: 3 filed, 1 commented, 4 duplicate, 20 not-software,
2 asked, 0 stuck; 1 left for the next Run` (`WOULD RECORD: ...`). Exit 0 when it ran (no
harvest.json prints STALE and records nothing), 2 when RUN is not a folder or no state folder is set.

Example:
    python3 issue_harvest_record.py --run /runs/2030-01-07
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _common as c

SUMMARY = ("filed", "commented", "duplicate", "not-software", "asked", "stuck")


def outcome(d, filed, filed_ran):
    """The ledger fields one decision earns; `retry` marks an attempt that did not land."""
    if d is None:
        return {"state": "seen", "note": "no decision this Run", "retry": True}
    kind = str(d.get("decision") or "")
    if kind in ("new", "comment"):
        r = filed.get(c.part_key(str(d.get("source") or ""), d.get("part")))
        if r is None:
            why = "issue-file has no result for it" if filed_ran else "issue-file did not run"
            return {"state": "seen", "note": why, "retry": True}
        status, why = r.get("status"), str(r.get("why") or "")
        base = {"repo": r.get("repo") or "", "issue": str(r.get("issue") or ""), "url": r.get("url") or ""}
        if status in ("filed", "commented"):
            return dict(base, state=status, verified="yes" if r.get("verified") else "no", note=str(d.get("reason") or ""))
        if status == "already":
            if kind == "comment" or "marker" in why or "comment" in why:
                return dict(base, state="filed" if kind == "new" else "commented", verified="yes",
                            note=f"found on GitHub: {why}")
            return dict(base, state="duplicate", note=f"found on GitHub: {why}")
        return dict(base, state="seen", note=f"{status}: {why}", retry=True)
    if kind == "duplicate":
        of = f"#{d.get('issue')}" if d.get("issue") else f"source {d.get('of_source')}"
        return {"state": "duplicate", "repo": str(d.get("repo") or ""), "issue": str(d.get("issue") or ""),
                "note": f"duplicate of {of}: {d.get('reason') or ''}".strip()}
    if kind == "not-software":
        return {"state": "not-software", "note": str(d.get("reason") or "")}
    if kind == "ask":
        return {"state": "asked", "note": str(d.get("question") or d.get("reason") or "")}
    return {"state": "seen", "note": f"unknown decision {kind!r}", "retry": True}


def combine(outs):
    """One row for an item filed in several parts: final only when every part is."""
    retry = any(o.get("retry") for o in outs)
    first = next((o for o in outs if o["state"] in c.WRITTEN), outs[0])
    got = {"state": "seen" if retry else first["state"],
           "repo": " ".join(dict.fromkeys(o["repo"] for o in outs if o.get("repo"))),
           "issue": " ".join(o["issue"] for o in outs if o.get("issue")),
           "url": " ".join(o["url"] for o in outs if o.get("url")),
           "verified": "yes" if all(o.get("verified") == "yes" for o in outs if o["state"] in c.WRITTEN) else "no",
           "note": (f"{len(outs)} parts: " + "; ".join(str(o.get("note") or o["state"]) for o in outs))[:500]}
    if retry:
        got["retry"] = True
    return got


def plan(harvest, decisions, filed_doc, book, now, run_name):
    """The ledger rows this Run earns."""
    items = {str(i.get("key")): i for i in harvest.get("items") or [] if isinstance(i, dict)}
    by_source, parts = {}, {}
    for d in (decisions or {}).get("decisions") or []:
        if isinstance(d, dict) and str(d.get("source") or "") in items:
            by_source.setdefault(str(d["source"]), d)
            if d.get("decision") in ("new", "comment"):
                parts.setdefault(str(d["source"]), []).append(d)
    filed = {str(r.get("key") or r.get("source")): r for r in (filed_doc or {}).get("results") or []
             if isinstance(r, dict)}
    riders = {}
    for d in by_source.values():
        if d.get("decision") == "new":
            for k in d.get("also") or []:
                if k in items and k != d.get("source"):
                    riders[str(k)] = d
    ran = filed_doc is not None
    rows = []
    for key, item in items.items():
        old = book.get(key, {})
        if key in riders and key not in by_source:
            got = outcome(riders[key], filed, ran)
            got["note"] = f"carried by {riders[key].get('source')}; " + str(got.get("note") or "")
        elif len(parts.get(key, [])) > 1:
            got = combine([outcome(d, filed, ran) for d in parts[key]])
            got["marker"] = ",".join(c.key_hash(c.part_key(key, d.get("part"))) for d in parts[key])
        else:
            got = outcome(by_source.get(key), filed, ran)
        attempts = int(old.get("attempts") or 0)
        if got.pop("retry", False):
            attempts += 1
            if attempts >= c.MAX_ATTEMPTS:
                got["state"] = "stuck"
        rows.append(dict({"id": key, "source": item.get("source") or "", "ref": item.get("ref") or "",
                          "marker": got.pop("marker", None) or c.key_hash(key), "item_date": str(item.get("date") or ""),
                          "first_seen": old.get("first_seen") or harvest.get("started_at") or now,
                          "last_run": run_name, "attempts": str(attempts), "updated_at": now,
                          "by": "issue-harvest-record"}, **got))
    for key in harvest.get("deferred") or []:
        old = book.get(key, {})
        if old.get("state") in c.FINAL:
            continue
        rows.append({"id": key, "source": key.split(":", 1)[0], "state": "seen",
                     "first_seen": old.get("first_seen") or harvest.get("started_at") or now, "last_run": run_name,
                     "attempts": old.get("attempts") or "0", "note": "deferred past the cap", "updated_at": now,
                     "by": "issue-harvest-record", "marker": c.key_hash(key)})
    return rows


def summary(rows):
    counts = {s: 0 for s in SUMMARY}
    counts["left"] = 0
    for r in rows:
        if r["state"] in counts:
            counts[r["state"]] += 1
        if r["state"] == "seen":
            counts["left"] += 1
    return counts


def main(argv=None):
    p = argparse.ArgumentParser(description="Record each queued source item's outcome in the harvest ledger.")
    p.add_argument("--run", dest="run_dir", required=True, help="the Run folder")
    p.add_argument("--dry-run-if", default="", help="only report when this is true (a launch form's dry_run)")
    p.add_argument("--state", default="", help="the state folder (default: setting state)")
    a = p.parse_args(argv)
    folder = Path(a.run_dir).expanduser()
    try:
        if not folder.is_dir():
            raise ValueError(f"{folder} is not a Run folder")
        root = c.state_root(c.harvest_settings(), a.state)
    except (c.ConfigError, ValueError) as exc:
        print(f"issue-harvest-record: {exc}", file=sys.stderr)
        return 2
    harvest = c.load_json(folder / "harvest.json")
    if harvest is None:
        print("STALE: no harvest.json in the Run folder; nothing recorded")
        return 0
    decisions = c.load_json(folder / "decisions.json")
    filed_doc = c.load_json(folder / "filed.json")
    dry = c.truthy(a.dry_run_if) or bool((decisions or {}).get("dry_run"))
    now = c.now_iso()
    try:
        with c.locked(root):
            rows = plan(harvest, decisions, filed_doc, c.ledger_book(root), now, folder.name)
            counts = summary(rows)
            if not dry:
                c.ledger_upsert(root, rows)
                with (root / "runs.jsonl").open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"run": folder.name, "started_at": harvest.get("started_at"), "recorded_at": now,
                                         "dry_run": False, "decided": bool(decisions), "counts": counts,
                                         "sources": harvest.get("sources"),
                                         "repos": [{"repo": r.get("repo"), "github": r.get("github")}
                                                   for r in harvest.get("repos") or []]}) + "\n")
    except (c.ConfigError, ValueError) as exc:
        print(f"issue-harvest-record: {exc}", file=sys.stderr)
        return 2
    word = "WOULD RECORD" if dry else "RECORDED"
    head = f"{word}: " + ", ".join(f"{counts[s]} {s}" for s in SUMMARY) + f"; {counts['left']} left for the next Run"
    out = {"tool": "issue-harvest-record", "run": str(folder), "dry_run": dry, "headline": head, "counts": counts,
           "rows": rows, "ledger": str(c.ledger_path(root))}
    try:
        c.write_new(folder / ("record-dry-run.json" if dry else "record.json"), out)
    except FileExistsError as exc:
        print(f"issue-harvest-record: {exc}", file=sys.stderr)
    print(head)
    return 0


if __name__ == "__main__":
    sys.exit(main())
