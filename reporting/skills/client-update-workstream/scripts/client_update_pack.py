# /// script
# dependencies = ["pyyaml"]
# ///
"""Gather one engagement's week into a numbered source pack before the session.

Writes the week's work/ folder: sources.json (the pack), sources.md (every source by role),
sources-a.md and sources-b.md (the two fact-check halves) and sources/ (Portal items and the
repo log as text). A pack already there moves to work/superseded-<stamp>/ first; the evidence
file, the claims and the reviews are never touched. The window is the time since the last
update, or a catch-up after a long gap (THE WINDOW in _common.py).

Sources, numbered S001, S002 ... in this order:
  context   the engagement context: the Context's background source (a file, a folder holding
            the rules' Engagement context file, or portal://note/<id> or portal://project/<id>,
            read here, read only), else the file beside the rules. Missing is a warning.
  previous  the newest earlier update and the review note beside it (path only).
  folder    files in the client folders (Context sources named engagement or engagement-*),
            under the rules' Source folders ("." is a folder's own files only), modified in the
            window or with a date in the window in their name. Never open matches, desktop.ini,
            names starting "~$" or ".", the updates folder and files over 25 MB are left out;
            no file is opened. The newest 200 are kept.
  portal    report-weekly's report_collect.py sweep of the rules' Portal domain for the window
            (7 days ahead): one source per meeting, note, task, project and mail thread, mail
            only when a counterparty matches Client email domains. An unreadable Portal makes
            the pack STALE; the rest is still written.
  repo      the Context's repo git log for the window.

context and previous go to half a (every checker reads them); the rest, largest first,
alternate b, a, so each fact-checker reads about half. With two or more sources neither half
is empty. On a dry run (--dry-run-if true) the week folder is <run-dir>/client-update/<week>/.

First line: "FRESH: <n> sources for <engagement> <week> (<since> to <date>), pack at <work>"
("FRESH: catch-up, ..." for a catch-up) or "STALE: <reason>; <n> sources, pack at <work>",
then indented detail. --format json prints sources.json. Exit 0 when it ran, 2 on a bad
argument or a missing Context, source or rules file.

Settings: [client-update-workstream] contexts_dir (or the top-level contexts_dir);
portal_mcp_config and portal_server for a Portal-backed engagement context.

    python3 client_update_pack.py acme-weekly-update --week 2026-W40
"""

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import _common as cu

REPORT_COLLECT = Path("~/.claude/skills/report-weekly/scripts/report_collect.py").expanduser()
MAX_BYTES, MAX_FILES, LOOKAHEAD_DAYS = 25 * 1024 * 1024, 200, 7
PORTAL_KINDS = ("meeting", "note", "task", "project", "mail")
ROLES = ("context", "previous", "folder", "portal", "repo")
SHARED_ROLES = ("context", "previous")
PACK_FILES = (cu.SOURCES_JSON, cu.SOURCES_MD, cu.SOURCES_A_MD, cu.SOURCES_B_MD, cu.SOURCES_DIR)
SECRETS = re.compile(r"(?i)(bearer\s+\S+|authorization[\"'\s:=]+\S+|[?&](?:key|token|api_key|access_token)=[^\s&\"']+)")


def safe(text) -> str:
    """Every error passes through here, so a bearer token is never printed."""
    return SECRETS.sub("[redacted]", str(text))


def file_source(role, path, when, title, size=None) -> dict:
    if size is None:
        try:
            size = Path(path).stat().st_size
        except OSError:
            size = 0
    return {"role": role, "kind": "file", "title": title, "occurred_at": when.isoformat() if when else None,
            "ref": None, "path": str(path), "size": int(size)}


# --------------------------------------------------------------------------- context and previous update

def portal_get(kind, ident, config=None):
    """One Portal note or project, read only, over the MCP JSON-RPC endpoint the settings name."""
    conf = cu.settings()
    config = config or conf.get("portal_mcp_config")
    server = conf.get("portal_server") or "insights-portal"
    if not config:
        raise RuntimeError("setting portal_mcp_config is needed to read a Portal engagement context")
    entry = json.loads(Path(config).expanduser().read_text(encoding="utf-8"))["mcpServers"][server]
    token = os.environ.get("INSIGHTS_PORTAL_ASSISTANT_TOKEN", "").strip()
    auth = f"Bearer {token}" if token else (entry.get("headers") or {}).get("Authorization", "")
    expand = lambda v: re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", lambda m: os.environ.get(m.group(1), ""), v or "")
    url, auth = expand(entry.get("url")), expand(auth)
    parts = urlsplit(url)
    if not (parts.scheme == "https" or (parts.scheme == "http" and parts.hostname in ("localhost", "127.0.0.1"))):
        raise RuntimeError("the Portal URL must be HTTPS (HTTP only on localhost)")
    if not auth.startswith("Bearer ") or not auth[7:].strip():
        raise RuntimeError("no Portal bearer token: set INSIGHTS_PORTAL_ASSISTANT_TOKEN or put one in the config")
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
        "name": "get", "arguments": {"entity_type": kind, "id_or_query": ident}}}).encode()
    request = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": auth, "Content-Type": "application/json", "Accept": "application/json, text/event-stream"})

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args):
            return None    # the bearer only ever goes to the configured URL

    with urllib.request.build_opener(NoRedirect).open(request, timeout=60) as response:
        raw = response.read().decode("utf-8", errors="replace")
    lines = [raw] if raw.lstrip().startswith("{") else [l[5:] for l in raw.splitlines() if l.startswith("data:")]
    answer = json.loads(lines[-1])
    if "error" in answer:
        raise RuntimeError(f"portal get: {answer['error']}")
    result = answer.get("result", answer)
    if isinstance(result, dict) and "content" in result:
        text = "\n".join(c.get("text", "") for c in result["content"] if c.get("type") == "text")
        try:
            return json.loads(text)
        except ValueError:
            return text
    return result


def record_text(record, kind) -> str:
    """A note's content or a project's description."""
    if isinstance(record, str):
        return record.strip()
    if isinstance(record, dict) and isinstance(record.get(kind), dict):
        record = record[kind]
    keys = ("content", "body", "text") if kind == "note" else ("description", "content", "text")
    for key in keys:
        value = record.get(key) if isinstance(record, dict) else None
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def context_source(eng, config, no_portal):
    """The engagement context as (source, text or None), or (None, warning)."""
    ref = eng.context_portal
    if eng.background and eng.background.startswith("portal://") and ref is None:
        return None, (f"the background source {eng.background!r} is not portal://note/<id> or "
                      "portal://project/<id>: the update has no back-context")
    if ref:
        if no_portal:
            return None, f"the engagement context {eng.background} was not read: --no-portal"
        kind, ident = ref
        try:
            text = record_text(portal_get(kind, ident, config), kind)
        except Exception as exc:  # an unreadable Portal is a missing context, not a dead run
            return None, f"the engagement context {eng.background} could not be read ({safe(type(exc).__name__)})"
        if not text:
            return None, f"the engagement context {eng.background} is empty or not found"
        body = f"# engagement context (Portal {kind} {ident})\n\n{text}\n"
        return ({"role": "context", "kind": f"portal-{kind}", "title": f"engagement context: {eng.background}",
                 "occurred_at": None, "ref": eng.background, "path": None, "size": len(body.encode())}, body), None
    path = eng.context_path
    if not path.is_file():
        where = f"{eng.background} (the Context's background source)" if eng.background else f"{path.name} beside the rules"
        return None, f"no engagement context ({where}): the update has no back-context and no revision can be proposed"
    return (file_source("context", path, None, f"engagement context: {path.name}"), None), None


def previous_sources(week, previous) -> list:
    """The previous update, and the review note in its folder of the same date (else the newest
    dated no later)."""
    if previous is None:
        return []
    day = week.engagement.rules.update_day
    when = cu.date_in_text(previous.name, day)
    out = [file_source("previous", previous, when, f"previous update: {previous.name}")]
    notes = []
    for path in previous.parent.glob(cu.as_glob(week.engagement.rules.review_note)):
        found = cu.date_in_text(path.name, day) if path.is_file() and path != previous else None
        if found and (when is None or found <= when):
            notes.append((found, path))
    same = [p for d, p in notes if d == when]
    note = same[0] if same else (max(notes)[1] if notes else None)
    if note is not None:
        out.append(file_source("previous", note, cu.date_in_text(note.name, day), f"previous review note: {note.name}"))
    return out


# --------------------------------------------------------------------------- client folders and repo

def within(path, folder) -> bool:
    return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)


def name_dates(name) -> list:
    out = []
    for m in cu.DATE_RE.finditer(name):
        try:
            out.append(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except ValueError:
            pass
    return out


def scan_folders(folders, since, until, source_folders=(), never_open=(), skip_under=()):
    """The client folders' files in the window, and warnings. Stats files, never opens them,
    because client folders sit on slow synced drives."""
    warnings, found, too_big, seen = [], [], [], set()
    skip = [os.path.abspath(str(p)) for p in skip_under]
    start = datetime.combine(since, datetime.min.time()).timestamp()
    end = datetime.combine(until + timedelta(days=1), datetime.min.time()).timestamp()
    for folder in folders:
        base = os.path.abspath(str(folder))
        if not os.path.isdir(base):
            warnings.append(f"the engagement folder {folder} does not exist; skipped")
            continue
        roots = [(base, False) if sub.strip().rstrip("/") in (".", "") else
                 (os.path.normpath(os.path.join(base, sub)), True) for sub in source_folders] or [(base, True)]
        for root, recursive in roots:
            if not os.path.isdir(root) or any(within(root, s) for s in skip):
                continue
            rel_root = os.path.relpath(root, base).replace(os.sep, "/")
            if rel_root != "." and cu.matches_never_open(never_open, os.path.basename(root), rel_root):
                continue
            stack = [root]
            while stack:
                current = stack.pop()
                try:
                    with os.scandir(current) as listing:
                        entries = list(listing)
                except OSError as exc:
                    warnings.append(f"could not list {os.path.relpath(current, base)}: {type(exc).__name__}")
                    continue
                for entry in entries:
                    name, full = entry.name, os.path.join(current, entry.name)
                    relative = os.path.relpath(full, base).replace(os.sep, "/")
                    if (name.startswith((".", "~$")) or name.lower() == "desktop.ini"
                            or cu.matches_never_open(never_open, name, relative)):
                        continue
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if recursive and not any(within(full, s) for s in skip):
                                stack.append(full)
                            continue
                        info = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if full in seen or not stat.S_ISREG(info.st_mode):
                        continue
                    dated = [d for d in name_dates(name) if since <= d <= until]
                    if not (start <= info.st_mtime < end or dated):
                        continue
                    seen.add(full)
                    if info.st_size > MAX_BYTES:
                        too_big.append(relative)
                        continue
                    when = dated[0] if dated else datetime.fromtimestamp(info.st_mtime).date()
                    found.append((info.st_mtime, file_source("folder", full, when, relative, info.st_size)))
    if too_big:
        warnings.append(f"{len(too_big)} file(s) over 25 MB left out: " + ", ".join(sorted(too_big)[:10])
                        + (" ..." if len(too_big) > 10 else ""))
    found.sort(key=lambda t: t[0], reverse=True)
    if len(found) > MAX_FILES:
        warnings.append(f"{len(found)} engagement-folder files in the window; the newest {MAX_FILES} kept")
        found = found[:MAX_FILES]
    kept = [s for _, s in found]
    kept.sort(key=lambda s: (s.get("occurred_at") or "", s["title"]))
    return kept, warnings


def repo_log(repo, since, until):
    """(the git log text or None, a note when there is none)."""
    if not repo.is_dir():
        return None, f"the repo {repo} does not exist"
    try:
        done = subprocess.run(["git", "-C", str(repo), "log", f"--since={since} 00:00:00", f"--until={until} 23:59:59",
                               "--date=short", "--pretty=format:%h %ad %an %s"],
                              capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"git log could not run in {repo}: {type(exc).__name__}"
    if done.returncode != 0:
        return None, f"git log failed in {repo}: {done.stderr.strip()[:200]}"
    return (done.stdout.strip(), None) if done.stdout.strip() else (None, f"no commits in {repo.name} from {since} to {until}")


# --------------------------------------------------------------------------- the Portal sweep

def read_portal(domain, since, until) -> dict:
    """report_collect.py's read-only sweep of the domain, as its evidence ledger."""
    cmd = [sys.executable, str(REPORT_COLLECT), "--domain", domain, "--since", since.isoformat(),
           "--until", (until + timedelta(days=1)).isoformat(), "--lookahead-days", str(LOOKAHEAD_DAYS)]
    done = subprocess.run(cmd, capture_output=True, text=True, timeout=900, stdin=subprocess.DEVNULL)
    if done.returncode != 0:
        first = (done.stderr or done.stdout or "no output").strip().splitlines()
        raise RuntimeError(f"report_collect.py exited {done.returncode}: {first[-1] if first else ''}")
    return json.loads(done.stdout)


def mail_matches(item, domains) -> bool:
    if not domains:
        return True
    for party in item.get("counterparties") or []:
        text = str(party or "").strip().lower()
        if any(text == d or text.endswith("@" + d) or text.endswith("." + d) for d in domains):
            return True
    return False


def portal_items(ledger, domains):
    """The ledger's items of the kinds kept, each ref once, mail only from the client's
    domains; and the counts kept (and <kind>_read) by kind."""
    counts, kept, seen = {}, [], set()
    for item in ledger.get("items") or []:
        kind = str(item.get("kind") or "")
        if kind not in PORTAL_KINDS:
            continue
        counts[f"{kind}_read"] = counts.get(f"{kind}_read", 0) + 1
        ref = str(item.get("ref") or "")
        if (kind == "mail" and not mail_matches(item, domains)) or (ref and ref in seen):
            continue
        seen.add(ref)
        counts[kind] = counts.get(kind, 0) + 1
        kept.append(item)
    return kept, counts


def portal_text(item) -> str:
    body = str(item.get("text") or "").strip() or str((item.get("extra") or {}).get("excerpt") or "").strip()
    lines = [f"# {item.get('title') or '(untitled)'}", "", f"- Kind: {item.get('kind')}",
             f"- When: {item.get('occurred_at') or 'not known'}",
             f"- Who: {', '.join(str(c) for c in item.get('counterparties') or []) or 'not recorded'}",
             f"- Detail: {item.get('detail') or ''}".rstrip(),
             f"- Projects: {', '.join(str(p) for p in item.get('projects') or [])}".rstrip(),
             f"- Ref: {item.get('ref') or ''}".rstrip(), ""]
    return "\n".join(lines + ([body, ""] if body else []))


# --------------------------------------------------------------------------- halves and files

def assign_halves(sources) -> None:
    for s in sources:
        if s["role"] in SHARED_ROLES:
            s["half"] = "a"
    rest = sorted((s for s in sources if s["role"] not in SHARED_ROLES), key=lambda s: (-s["size"], s["id"]))
    for n, s in enumerate(rest):
        s["half"] = "b" if n % 2 == 0 else "a"
    if len(sources) >= 2:
        for empty, full in (("a", "b"), ("b", "a")):
            if not any(s["half"] == empty for s in sources):
                mine = [s for s in sources if s["half"] == full]
                min(mine[1:], key=lambda s: s["size"])["half"] = empty


def sources_md(pack) -> str:
    lines = [f"# Sources for {pack['engagement']} {pack['week']}", "",
             f"Window {pack['since']} to {pack['until']}; update dated {pack['date']}; variant {pack['variant']}.", "",
             pack["window"]["note"], ""]
    for role in ROLES:
        mine = [s for s in pack["sources"] if s["role"] == role]
        if mine:
            lines += [f"## {role} ({len(mine)})", ""]
            for s in mine:
                bits = [f"{s['id']} [{s['half']}]", s["title"], s.get("occurred_at") or "no date",
                        s.get("ref") or "", s.get("path") or ""]
                lines.append("- " + " · ".join(b for b in bits if b))
            lines.append("")
    if pack["carry"]:
        lines += [f"## carry ({len(pack['carry'])})", ""]
        lines += [f"- {c['id']} · {c['item']} · {c.get('owner') or 'no owner'} · due {c.get('due') or 'none'}"
                  for c in pack["carry"]] + [""]
    if pack["warnings"]:
        lines += ["## warnings", ""] + [f"- {w}" for w in pack["warnings"]] + [""]
    return "\n".join(lines)


def half_md(pack, half) -> str:
    mine = [s for s in pack["sources"] if s["half"] == half]
    head = [f"# Fact-check half {half}: {len(mine)} sources, {sum(s['size'] for s in mine)} bytes", ""]
    return "\n".join(head + [f"{s['id']} · {s['role']} · {s['title']} · {s.get('path') or s.get('ref') or ''}"
                             for s in mine]) + "\n"


def supersede(work):
    """Move an existing pack into work/superseded-<stamp>/; return where, or None."""
    present = [work / name for name in PACK_FILES if (work / name).exists()]
    if not present:
        return None
    target = cu.free_path(work / f"superseded-{cu.stamp()}")
    target.mkdir(parents=True)
    for path in present:
        shutil.move(str(path), str(target / path.name))
    return target


def write_new(path, text) -> None:
    if path.exists():
        raise cu.Bad(f"refusing to overwrite {path}")
    path.write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------- the pack

def build(engagement, week=None, run_dir=None, dry_run_if=None, as_of=None, week_dir=None, contexts=None,
          config=None, no_portal=False) -> dict:
    dry = cu.truthy(dry_run_if)
    if dry and not cu.blank(run_dir):
        raise cu.Bad("--dry-run-if is true but no --run-dir was given")
    wk = cu.resolve(engagement, week, as_of, None if dry else week_dir, contexts)
    if dry:
        wk.week_dir = Path(cu.blank(run_dir)).expanduser() / "client-update" / wk.label
    eng, rules = wk.engagement, wk.engagement.rules
    span = cu.update_window(wk)
    since, until = span["since"], span["until"]
    work = wk.work
    work.mkdir(parents=True, exist_ok=True)
    moved = supersede(work)

    warnings, sources, texts = [], [], []
    found, problem = context_source(eng, config, no_portal)
    if problem:
        warnings.append(problem)
    elif found[1] is None:
        sources.append(found[0])
    else:
        texts.append(found)
    sources += previous_sources(wk, span["previous"])
    if eng.engagements:
        kept, notes = scan_folders(eng.engagements, since, until, rules.source_folders, rules.never_open,
                                   [eng.updates, wk.week_dir])
        sources += kept
        warnings += notes
    else:
        warnings.append("the Context has no engagement folder, so no folder files are in the pack")

    portal = {"domain": rules.portal_domain, "read": False, "error": None, "counts": {}}
    stale = None
    if no_portal:
        portal["error"] = "not read: --no-portal"
    elif not rules.portal_domain:
        portal["error"] = "not read: the rules name no Portal domain"
        warnings.append("the rules name no Portal domain, so the Portal was not read")
    else:
        try:
            items, counts = portal_items(read_portal(rules.portal_domain, since, until),
                                         rules.client_email_domains)
            portal.update(read=True, counts=counts)
            for item in items:
                text = portal_text(item)
                texts.append(({"role": "portal", "kind": str(item.get("kind")),
                               "title": str(item.get("title") or "(untitled)"), "occurred_at": item.get("occurred_at"),
                               "ref": item.get("ref") or None, "path": None, "size": len(text.encode())}, text))
        except Exception as exc:  # an unreadable Portal is a stale pack, not a dead one
            portal["error"] = safe(f"{type(exc).__name__}: {exc}")[:300]
            stale = f"the Portal could not be read ({portal['error']})"
            warnings.append(stale)
    if eng.repo is not None:
        log, note = repo_log(eng.repo, since, until)
        if log:
            text = f"# git log of {eng.repo.name}, {since} to {until}\n\n{log}\n"
            texts.append(({"role": "repo", "kind": "git-log", "title": f"git log of {eng.repo.name}",
                           "occurred_at": until.isoformat(), "ref": None, "path": None,
                           "size": len(text.encode())}, text))
        elif note:
            warnings.append(note)

    # A Portal context comes first, then the file sources, then the other written sources.
    context_first = [t for t in texts if t[0]["role"] == "context"]
    others = [t for t in texts if t[0]["role"] != "context"]
    every = [s for s, _ in context_first] + sources + [s for s, _ in others]
    for number, source in enumerate(every, start=1):
        source["id"] = f"S{number:03d}"
    if texts:
        (work / cu.SOURCES_DIR).mkdir(parents=True, exist_ok=True)
        for source, text in context_first + others:
            path = work / cu.SOURCES_DIR / f"{source['id']}.md"
            write_new(path, text)
            source["path"] = str(path)
    assign_halves(every)

    carry = [{k: r.get(k, "") for k in ("id", "item", "owner", "due", "opened_week", "last_week", "note")}
             for r in cu.read_rows(wk.ledger_file).values() if r.get("state") == "open"]
    window = {"kind": span["kind"], "since": since.isoformat(), "until": until.isoformat(),
              "previous_date": span["previous_date"].isoformat() if span["previous_date"] else None,
              "gap_days": span["gap_days"], "note": span["note"]}
    from_portal = eng.context_portal is not None
    pack = {
        "schema": cu.SOURCES_SCHEMA, "engagement": eng.name, "context_file": str(eng.context_file),
        "rules_file": str(eng.rules_file), "variant": rules.variant, "length_default": rules.length_default,
        "week": wk.label, "date": wk.date.isoformat(), "since": since.isoformat(), "until": until.isoformat(),
        "window": window,
        "context": {"path": eng.background if from_portal else str(eng.context_path),
                    "from": "portal" if from_portal else "file",
                    "exists": bool(context_first) or (not from_portal and eng.context_path.is_file()),
                    "proposed": str(wk.context_proposed)},
        "recipients": rules.recipients,
        "folders": {"updates": str(eng.updates), "week": str(wk.week_dir), "work": str(work),
                    "engagements": [str(p) for p in eng.engagements], "rules": str(eng.rules_file.parent),
                    "repo": str(eng.repo) if eng.repo else None},
        "files": wk.files(),
        "sources": [{k: s.get(k) for k in ("id", "role", "kind", "title", "occurred_at", "ref", "path", "size",
                                          "half")} for s in every],
        "carry": carry, "portal": portal, "warnings": warnings, "generated_at": cu.now_utc(), "dry_run": dry,
        "stale": stale, "superseded": str(moved) if moved else None,
    }
    write_new(work / cu.SOURCES_JSON, json.dumps(pack, indent=1, ensure_ascii=False) + "\n")
    write_new(work / cu.SOURCES_MD, sources_md(pack))
    write_new(work / cu.SOURCES_A_MD, half_md(pack, "a"))
    write_new(work / cu.SOURCES_B_MD, half_md(pack, "b"))
    return pack


def render(pack) -> str:
    n, work = len(pack["sources"]), pack["folders"]["work"]
    if pack.get("stale"):
        out = [f"STALE: {pack['stale']}; {n} sources, pack at {work}"]
    else:
        kind = "catch-up, " if pack["window"]["kind"] == "catch-up" else ""
        out = [f"FRESH: {kind}{n} sources for {pack['engagement']} {pack['week']} "
               f"({pack['since']} to {pack['date']}), pack at {work}"]
    out.append(f"  window: {pack['window']['note']}")
    out.append("  by role: " + ", ".join(f"{r} {sum(1 for s in pack['sources'] if s['role'] == r)}" for r in ROLES))
    for half in ("a", "b"):
        mine = [s for s in pack["sources"] if s["half"] == half]
        out.append(f"  half {half}: {len(mine)} sources, {sum(s['size'] for s in mine)} bytes")
    portal = pack["portal"]
    out.append("  portal: " + (f"read {json.dumps(portal['counts'])}" if portal["read"]
                               else f"not read ({portal['error']})"))
    out.append(f"  carry: {len(pack['carry'])} open item(s)")
    if pack.get("superseded"):
        out.append(f"  the earlier pack moved to {pack['superseded']}")
    return "\n".join(out + [f"  warning: {w}" for w in pack["warnings"]])


def main():
    p = argparse.ArgumentParser(description="Gather one engagement's week into work/sources.json for the session.")
    p.add_argument("engagement", nargs="?", default="", help="a Context name or the path to a Context YAML file")
    p.add_argument("--week", default="", help="yyyy-Www or a yyyy-mm-dd date in the week; blank: this week")
    p.add_argument("--run-dir", default="", help="the Run folder; a dry run writes its week folder under it")
    p.add_argument("--dry-run-if", default="", help="true, 1, yes or on: write under --run-dir only")
    p.add_argument("--as-of", default="", help="the current week as of this date (yyyy-mm-dd); blank: today")
    p.add_argument("--week-dir", default="", help="use this folder as the week folder")
    p.add_argument("--contexts-dir", default="", help="where Context YAML files are found by name")
    p.add_argument("--config", default="", help="the MCP config holding the Portal (default: the setting)")
    p.add_argument("--no-portal", action="store_true", help="do not read the Portal")
    p.add_argument("--format", dest="fmt", choices=["text", "json"], default="text")
    args = p.parse_args()
    pack = build(args.engagement, args.week, args.run_dir, args.dry_run_if, args.as_of, args.week_dir,
                 args.contexts_dir, cu.blank(args.config), args.no_portal)
    print(json.dumps(pack, indent=1, ensure_ascii=False) if args.fmt == "json" else render(pack))


if __name__ == "__main__":
    cu.run_main(main)
