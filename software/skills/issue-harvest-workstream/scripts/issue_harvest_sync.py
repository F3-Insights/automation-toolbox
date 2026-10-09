#!/usr/bin/env python3
# /// script
# dependencies = ["pyyaml"]
# ///
"""Gather one issue-harvest Run's work before the session: the source items and each
repository's issues, read only.

The session that decides the issues has no route to GitHub, so everything it needs is read here.

- The window: from the last live Run's start (runs.jsonl in the state folder), never further
  back than --window-days (setting `horizon_days`, 14); a first Run reads the last --window-days.
- The sources, each enabled in the settings: Portal notes (titles matching `exclude_titles`
  skipped, each read in full), Portal email (senders and subjects excluded by pattern, each body
  read), Portal tasks in a project the repo map ties to a repository, and the said-but-not-seen
  files. Any other listed source is reported as not reachable yet.
- The match: an item names a repository's `terms`, links to one of its `portal_projects`, comes
  from one of its `reporters`, or the Portal's search found it for a term. Each candidate carries
  `repo_hints`, a hint and never a decision.
- The queue: candidates the ledger holds in a final state are left out; the rest newest first,
  at most --max (60), in batches of --batch-size (8); the rest are deferred.
- GitHub: for each repository in scope (--repos, else every one with `harvest: true`) its labels,
  open issues and issues closed in the last `closed_days` (30), with the harvest markers in each.

Settings: [issue-harvest-workstream] (see _common.py) and `portal_mcp_config`.
Prints `QUEUE: 12 item(s) queued (...); 3 deferred; 2 repositories read` or `NOTHING: ...`,
led by `STALE: ...` when a source or repository could not be read; --format json prints the
whole result. --out writes it to a new file (never overwritten). Exit 0 when it ran, 2 for a bad
argument or unusable settings. A blank option (`--max=`) means not given.

Example:
    python3 issue_harvest_sync.py --out /runs/2030-01-07/harvest.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import _common as c

SCHEMA = "issue-harvest/harvest@1"
MAX_DEFAULT = 60
BATCH_DEFAULT = 8
ISSUE_FIELDS = "number,title,body,labels,state,url,createdAt,updatedAt,closedAt,author"


def issue_row(row):
    body = str(row.get("body") or "")
    author = row.get("author")
    return {"number": row.get("number"), "title": row.get("title"), "state": str(row.get("state") or "").lower(),
            "labels": c.label_names(row.get("labels")), "url": row.get("url"), "created_at": row.get("createdAt"),
            "updated_at": row.get("updatedAt"), "closed_at": row.get("closedAt"),
            "author": (author.get("login") if isinstance(author, dict) else author) or None,
            "harvest_markers": sorted(set(re.findall(re.escape(c.MARKER_PREFIX) + r"[0-9a-f]{12}", body))),
            "body": body[:c.BODY_SNAPSHOT] + (" ..." if len(body) > c.BODY_SNAPSHOT else "")}


def snapshot_repo(entry, closed_days):
    """One repository's labels, open issues and recently closed issues; an unreadable one says why."""
    repo = entry["repo"]
    out = dict(entry, github={"readable": True, "error": None}, existing_labels=[], open=[], recently_closed=[])
    try:
        labels = c.gh_json("gh label list", "label", "list", "-R", repo, "--limit", "200", "--json", "name") or []
        out["existing_labels"] = sorted(str(lb.get("name")) for lb in labels if isinstance(lb, dict))
        rows = c.gh_json("gh issue list", "issue", "list", "-R", repo, "--state", "open", "--limit",
                         str(c.LIST_LIMIT), "--json", ISSUE_FIELDS) or []
        if len(rows) >= c.LIST_LIMIT:
            out["github"]["error"] = f"{c.LIST_LIMIT} or more open issues; the dedupe snapshot may be incomplete"
        out["open"] = [issue_row(r) for r in rows if isinstance(r, dict)]
        since = (datetime.now(timezone.utc) - timedelta(days=closed_days)).date().isoformat()
        rows = c.gh_json("gh issue list", "issue", "list", "-R", repo, "--state", "closed", "--limit", "300",
                         "--search", f"closed:>={since}", "--json", ISSUE_FIELDS) or []
        out["recently_closed"] = [issue_row(r) for r in rows if isinstance(r, dict)]
    except Exception as exc:  # noqa: BLE001 - one unreadable repository never stops the others
        out["github"] = {"readable": False, "error": c.err_text(exc)}
    return out


def in_scope(repos, only):
    unknown = [o for o in only if not c.repo_entry(repos, o)]
    if unknown:
        raise ValueError(f"--repos names repositories the repo map does not list: {', '.join(unknown)}")
    if only:
        wanted = {o.lower() for o in only}
        return [r for r in repos if r["repo"].lower() in wanted]
    return [r for r in repos if r["harvest"]]


def build(cfg, repos, root, client, *, days, max_items, batch, only, github, now=None):
    now = now or datetime.now(timezone.utc)
    win = c.window(root, days, now)
    scope = in_scope(repos, only)
    items, reports = c.gather(client, cfg, scope, win["since"], win["until"])
    book = c.ledger_book(root)
    fresh = [i for i in items if book.get(i["key"], {}).get("state") not in c.FINAL]
    for i in fresh:
        row = book.get(i["key"])
        i["previous"] = {"state": row.get("state"), "attempts": row.get("attempts"), "note": row.get("note")} if row else None
    fresh.sort(key=lambda i: str(c.parse_time(i.get("time") or i.get("date")) or ""), reverse=True)
    queued, deferred = fresh[:max_items], fresh[max_items:]
    batches = {f"b{n + 1}": [i["key"] for i in queued[k:k + batch]] for n, k in enumerate(range(0, len(queued), batch))}
    closed_days = int(cfg.get("closed_days") or c.CLOSED_DAYS_DEFAULT)
    snaps = [snapshot_repo(r, closed_days) if github else
             dict(r, github={"readable": None, "error": "not read"}, existing_labels=[], open=[], recently_closed=[])
             for r in scope]
    by_source = {}
    for i in queued:
        by_source[i["source"]] = by_source.get(i["source"], 0) + 1
    return {
        "schema": SCHEMA, "tool": "issue-harvest-sync", "generated_at": c.now_iso(),
        "started_at": now.isoformat(timespec="seconds"),
        "window": {"since": win["since"].isoformat(timespec="seconds"), "until": win["until"].isoformat(timespec="seconds"),
                   "first_run": win["first_run"], "last_run": win["last_run"], "horizon_days": days},
        "repos": snaps, "other_repos": [r["repo"] for r in repos if r not in scope],
        "sources": reports, "items": queued, "batches": batches, "deferred": [i["key"] for i in deferred],
        "counts": {"queued": len(queued), "deferred": len(deferred), "candidates": len(items),
                   "already_decided": len(items) - len(fresh), "by_source": by_source},
    }


def headline(result):
    stale = [s["name"] for s in result["sources"] if s.get("readable") is False]
    stale += [r["repo"] for r in result["repos"] if r["github"].get("readable") is False]
    lead = f"STALE: could not read {', '.join(stale)}. " if stale else ""
    n = result["counts"]["queued"]
    if not n:
        return f"{lead}NOTHING: no new source item about the software since {result['window']['since']}"
    by = ", ".join(f"{k} {v}" for k, v in sorted(result["counts"]["by_source"].items()))
    read = sum(1 for r in result["repos"] if r["github"].get("readable"))
    return f"{lead}QUEUE: {n} item(s) queued ({by}); {result['counts']['deferred']} deferred; {read} repositories read"


def main(argv=None):
    p = argparse.ArgumentParser(description="Gather one issue-harvest Run's source items and issues, read only.")
    p.add_argument("--out", default="", help="write the queue here (a new file)")
    p.add_argument("--window-days", default="", help="the furthest back to read, in days (default: setting, 14)")
    p.add_argument("--max", dest="max_items", default="", help=f"the most items to queue (default {MAX_DEFAULT})")
    p.add_argument("--batch-size", default="", help=f"items per batch (default {BATCH_DEFAULT})")
    p.add_argument("--repos", default="", help="only these repositories, owner/name, comma separated")
    p.add_argument("--repos-file", default="", help="the repo map (default: setting repos_file)")
    p.add_argument("--state", default="", help="the state folder (default: setting state)")
    p.add_argument("--no-github", action="store_true", help="do not read GitHub")
    p.add_argument("--format", dest="fmt", choices=("text", "json"), default="text")
    a = p.parse_args(argv)
    try:
        cfg = c.harvest_settings()
        repos = c.load_repos(cfg, a.repos_file)
        days = c.whole_number(a.window_days, "window-days", int(cfg.get("horizon_days") or c.HORIZON_DEFAULT), 1, 365)
        cap = c.whole_number(a.max_items, "max", MAX_DEFAULT, 1, 1000)
        batch = c.whole_number(a.batch_size, "batch-size", BATCH_DEFAULT, 1, 50)
        only = [r.strip() for r in a.repos.split(",") if r.strip()]
        in_scope(repos, only)
        root = c.state_root(cfg, a.state)
        client, err = c.open_client()
        result = build(cfg, repos, root, client, days=days, max_items=cap, batch=batch, only=only,
                       github=not a.no_github)
        if err:
            result["portal_error"] = err
        if a.out:
            c.write_new(Path(a.out), result)
    except (c.ConfigError, ValueError, FileExistsError) as exc:
        print(f"issue-harvest-sync: {exc}", file=sys.stderr)
        return 2
    if a.fmt == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    print(headline(result))
    for s in result["sources"]:
        word = {False: "unreadable", None: "not read"}.get(s.get("readable"), "read")
        print(f"  {s['name']}: {word}, {s.get('listed', 0)} listed, {s.get('candidates', 0)} candidates"
              + (f" ({s['error']})" if s.get("error") else "") + (f" ({s['note']})" if s.get("note") else ""))
    for r in result["repos"]:
        print(f"  {r['repo']}: {len(r['open'])} open, {len(r['recently_closed'])} recently closed"
              + (f" ({r['github']['error']})" if r["github"].get("error") else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
