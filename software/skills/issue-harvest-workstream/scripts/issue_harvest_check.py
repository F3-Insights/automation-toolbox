#!/usr/bin/env python3
# /// script
# dependencies = ["pyyaml"]
# ///
"""Say whether the issue harvest is done, computed from its ledger, the Portal and GitHub.

Three tests:
1. decided: every source item a Run has seen has a final state in the ledger (no `seen` row
   left), and no new candidate item has arrived since the last live Run started. The Portal is
   read cheaply (lists only, no note fetched in full).
2. found: every `filed` or `commented` row carries its marker on GitHub, in the issue body or one
   of its comments. --offline trusts the ledger's `verified` column instead.
3. sources: the last live Run read every enabled source and every target repository.

--precheck prints one line for a scheduler, `WORK: <reason>` or `NOTHING: <reason>`, and skips
the GitHub reads unless --verify-github is given. --offline reads neither the Portal nor GitHub.

Settings: [issue-harvest-workstream] (repos_file, state, sources) and `portal_mcp_config`.
Exit 0 whenever it ran; 2 on unusable settings or a bad argument.

Example:
    python3 issue_harvest_check.py --precheck
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

import _common as c

TESTS = ("decided", "found", "sources")


def test_decided(rows, new):
    left = [r for r in rows if r.get("state") == "seen"]
    gaps = [f"{r['id']}: not decided yet ({r.get('note') or 'seen'})" for r in left]
    if new is None:
        note = "new source items not counted (offline)"
    elif new.get("error"):
        note = f"new source items not counted: {new['error']}"
        gaps.append(note)
    else:
        note = f"{new['count']} new candidate source item(s) since {new['since']}"
        if new["count"]:
            gaps.append(note)
    return {"met": not gaps, "rows": len(rows), "left": len(left),
            "stuck": [r["id"] for r in rows if r.get("state") == "stuck"], "new": new, "gaps": gaps, "note": note}


def test_found(rows, lookup):
    written = [r for r in rows if r.get("state") in c.WRITTEN]
    gaps = []
    for r in written:
        where = f"{r.get('repo')}#{r.get('issue')}"
        ok = str(r.get("verified") or "").lower() == "yes" if lookup is None else lookup(r)
        if ok is None:
            gaps.append(f"{r['id']}: {where} could not be read on GitHub")
        elif not ok:
            gaps.append(f"{r['id']}: {where} does not carry the marker " + ("(ledger)" if lookup is None else "on GitHub"))
    return {"met": not gaps, "rows": len(written), "checked_on_github": lookup is not None, "gaps": gaps}


def test_sources(last):
    if last is None:
        return {"met": False, "last_run": None, "gaps": ["no live Run recorded yet"]}
    gaps = [f"source {s.get('name')}: {s.get('error') or 'unreadable'}" for s in last.get("sources") or []
            if isinstance(s, dict) and s.get("readable") is False]
    gaps += [f"repository {r.get('repo')}: {(r.get('github') or {}).get('error') or 'unreadable'}"
             for r in last.get("repos") or [] if isinstance(r, dict) and (r.get("github") or {}).get("readable") is False]
    return {"met": not gaps, "last_run": last.get("run"), "started_at": last.get("started_at"), "gaps": gaps}


def count_new(cfg, repos, root, client, book, now):
    """Candidate items since the last live Run that the ledger does not hold (cheap reads)."""
    win = c.window(root, int(cfg.get("horizon_days") or c.HORIZON_DEFAULT), now)
    items, reports = c.gather(client, cfg, [r for r in repos if r["harvest"]], win["since"], win["until"], full=False)
    fresh = [i for i in items if i["key"] not in book]
    out = {"since": win["since"].isoformat(timespec="seconds"), "count": len(fresh), "keys": [i["key"] for i in fresh][:50]}
    unread = [s["name"] for s in reports if s.get("readable") is False]
    if unread:
        out["error"] = "could not read " + ", ".join(unread)
    return out


def github_lookup():
    """A marker finder over GitHub: each repository listed once, each commented issue viewed once."""
    cache, views = {}, {}

    def look(row):
        try:
            tags = [f"{c.MARKER_PREFIX}{h}" for h in (row.get("marker") or c.key_hash(row["id"])).split(",") if h]
            numbers = [int(n) for n in (row.get("issue") or "0").split()]
            repos = [cache.setdefault(n, c.Repo(n)) for n in (row.get("repo") or "").split() or [""]]
            if row.get("state") == "filed":
                bodies = [str(i.get("body") or "") for r in repos for i in r.issues() if int(i.get("number") or 0) in numbers]
            else:
                bodies = []
                for r in repos:
                    for n in numbers:
                        key = f"{r.name}#{n}"
                        if key not in views:
                            views[key] = r.view(n)
                        bodies += [str(cm.get("body") or "") for cm in views[key].get("comments") or [] if isinstance(cm, dict)]
            return all(any(t in b for b in bodies) for t in tags)
        except (c.GitHubError, ValueError, TypeError):
            return None

    return look


def check(cfg, repos, root, *, client=None, portal=True, github=True, now=None, lookup=None):
    now = now or datetime.now(timezone.utc)
    rows = c.ledger_rows(root)
    book = {r["id"]: r for r in rows}
    new = None
    if portal:
        if client is None:
            new = {"since": None, "count": 0, "error": "the Portal could not be reached"}
        else:
            try:
                new = count_new(cfg, repos, root, client, book, now)
            except Exception as exc:  # noqa: BLE001 - reported as a gap, never a crash
                new = {"since": None, "count": 0, "error": c.err_text(exc)}
    if github and lookup is None:
        lookup = github_lookup()
    last = c.last_run(root)
    tests = {"decided": test_decided(rows, new), "found": test_found(rows, lookup if github else None),
             "sources": test_sources(last)}
    met = sum(1 for t in tests.values() if t["met"])
    states = {}
    for r in rows:
        states[r.get("state") or ""] = states.get(r.get("state") or "", 0) + 1
    return {"tool": "issue-harvest-check", "state": str(root), "as_of": now.isoformat(timespec="seconds"),
            "last_run": last.get("run") if last else None, "ledger": states, "tests": tests,
            "met": met, "of": len(TESTS), "done": met == len(TESTS)}


def precheck_line(result):
    t = result["tests"]
    if result["last_run"] is None:
        return "WORK: no live issue-harvest Run recorded yet"
    reasons = []
    if t["decided"]["left"]:
        reasons.append(f"{t['decided']['left']} source item(s) not decided yet")
    new = t["decided"].get("new") or {}
    if new.get("count"):
        reasons.append(f"{new['count']} new candidate source item(s) since {new.get('since')}")
    if new.get("error"):
        reasons.append(f"new items not counted ({new['error']})")
    if not t["sources"]["met"]:
        reasons.append("the last Run could not read: " + "; ".join(t["sources"]["gaps"])[:200])
    if not t["found"]["met"]:
        reasons.append(f"{len(t['found']['gaps'])} filed item(s) not found back")
    if reasons:
        return "WORK: " + "; ".join(reasons)
    return f"NOTHING: every source item decided, nothing new since {new.get('since') or 'the last Run'}"


def render(result):
    out = [f"issue-harvest-check {result['state']}",
           f"{'DONE' if result['done'] else 'NOT DONE'} ({result['met']} of {result['of']} tests met)",
           "ledger: " + (", ".join(f"{k} {v}" for k, v in sorted(result["ledger"].items())) or "empty")]
    for number, (name, test) in enumerate(result["tests"].items(), start=1):
        out.append(f"{number} {name}: {'MET' if test['met'] else 'NOT MET'}")
        out += [f"  - {gap}" for gap in test["gaps"][:30]]
        if len(test["gaps"]) > 30:
            out.append(f"  - and {len(test['gaps']) - 30} more")
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(description="Whether the issue harvest is done, test by test.")
    p.add_argument("--repos-file", default="", help="the repo map (default: setting repos_file)")
    p.add_argument("--state", default="", help="the state folder (default: setting state)")
    p.add_argument("--offline", action="store_true", help="the ledger alone: read neither the Portal nor GitHub")
    p.add_argument("--verify-github", action="store_true", help="with --precheck: also look for each marker on GitHub")
    p.add_argument("--format", dest="fmt", choices=("text", "json"), default="text")
    p.add_argument("--precheck", action="store_true", help="one line, WORK: or NOTHING:, for a scheduler")
    a = p.parse_args(argv)
    try:
        cfg = c.harvest_settings()
        repos = c.load_repos(cfg, a.repos_file)
        root = c.state_root(cfg, a.state)
        if a.precheck and c.last_run(root) is None:
            print("WORK: no live issue-harvest Run recorded yet")
            return 0
        client = None if a.offline else c.open_client()[0]
        github = not a.offline and (a.verify_github or not a.precheck)
        result = check(cfg, repos, root, client=client, portal=not a.offline, github=github)
    except (c.ConfigError, ValueError) as exc:
        print(f"issue-harvest-check: {exc}", file=sys.stderr)
        return 2
    if a.precheck:
        print(precheck_line(result))
    elif a.fmt == "json":
        print(json.dumps(result, indent=1, default=str))
    else:
        print(render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
