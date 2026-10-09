#!/usr/bin/env python3
"""Every active Insights Portal project with the mechanical half of its priority score.

Reads four Portal listings (domains, goals, projects, tasks), groups the tasks onto their
projects, and computes the three factors of the owner's scoring formula that are arithmetic:
deadline pressure (20%), staleness (20%) and the counts behind risk (15%). Heat, domain
weight and neglect need things outside the Portal and come back as null for a model to fill.
`mechanical_score` therefore runs 0 to 55 and is a floor on the final score. Each project
also carries flags: NO_OWNER, NO_GOAL, NO_TASKS, NO_NEXT_TASK, OVERDUE, DUE_SOON, UNDATED,
STALE_30D, WAITING_HEAVY.

Inputs: the owner setting `portal_mcp_config` (and optionally `portal_server`). Read only.
Prints a ranked markdown table, or with --json the list of project objects. Warnings go to
stderr. Exit 0 ok, 2 on any error.

Example:
  python3 project_scoreboard.py --json --domain "Acme Components" --limit 20
"""

import argparse
import json
import sys
from datetime import datetime, timezone

from _common import (MECHANICAL_MAX, PortalError, SettingMissing, connect, is_active_project,
                     page_through, parse_time, safe, score_project)

ENTITY_TYPES = ("domain", "goal", "project", "task")


def read_corpus(client):
    corpus, unreadable = {}, {}
    for kind in ENTITY_TYPES:
        corpus[kind], skipped = page_through(client, kind)
        if skipped:
            unreadable[kind] = skipped
    return corpus, unreadable


def key_report(rows):
    """Which keys the Portal put on these items, with counts. Keys only, never values."""
    keys = {}
    for row in rows:
        for key in row:
            keys[str(key)] = keys.get(str(key), 0) + 1
    return {"items": len(rows), "keys": dict(sorted(keys.items()))}


def build(corpus, now, domain="", limit=0):
    """The scoreboard from the four listings. No I/O and no clock, so it can be tested."""
    domains = {str(d.get("id")): str(d.get("name") or d.get("title") or "") for d in corpus.get("domain", [])}
    goals = {str(g.get("id")): str(g.get("title") or g.get("name") or "") for g in corpus.get("goal", [])}
    by_project = {}
    for t in corpus.get("task", []):
        pid = str(t.get("project_id") or "").strip()
        if pid:  # a task with no project belongs to none, never guessed by name
            by_project.setdefault(pid, []).append(t)
    rows = [score_project(p, by_project.get(str(p.get("id") or ""), []), domains, goals, now)
            for p in corpus.get("project", []) if is_active_project(p)]
    rows.sort(key=lambda r: (-r["mechanical_score"], r["name"].lower(), r["project_id"]))
    if domain.strip():
        rows = [r for r in rows if domain.strip().lower() in r["domain"].lower()]
    matched = len(rows)
    if limit > 0:
        rows = rows[:limit]
    flag_counts = {}
    for r in rows:
        for f in r["flags"]:
            flag_counts[f] = flag_counts.get(f, 0) + 1
    scores = sorted(r["mechanical_score"] for r in rows)
    return {"as_of": now.date().isoformat(), "projects": rows, "matched": matched, "shown": len(rows),
            "projects_read": len(corpus.get("project", [])), "tasks_read": len(corpus.get("task", [])),
            "tasks_grouped": sum(len(v) for v in by_project.values()),
            "flag_counts": dict(sorted(flag_counts.items())),
            "score_range": {"min": scores[0] if scores else None,
                            "median": scores[len(scores) // 2] if scores else None,
                            "max": scores[-1] if scores else None, "max_possible": MECHANICAL_MAX}}


def warnings_for(result, unreadable, domain):
    out = [f"the Portal would not serialise {n} {kind} row(s); they were stepped over and are missing"
           for kind, n in sorted(unreadable.items())]
    bad = sum(r["mechanical"]["deadline_pressure"]["unparseable_due_dates"] for r in result["projects"])
    if bad:
        out.append(f"{bad} task due dates would not parse and were ignored for deadline pressure; run --explain")
    undated = sum("UNDATED" in r["flags"] for r in result["projects"])
    if undated:
        out.append(f"{undated} projects carried no parseable timestamp and were scored as maximally stale")
    if not result["projects"]:
        out.append("no active projects matched" + (f" domain {domain!r}" if domain else ""))
    return out


def cell(text, width):
    text = " ".join(str(text or "").split()).replace("|", "/")
    return text if len(text) <= width else text[:width - 1] + "…"


def as_markdown(result):
    lines = [f"# Project scoreboard, {result['as_of']}", "",
             f"{result['shown']} of {result['matched']} active projects shown, {result['tasks_grouped']} tasks "
             f"grouped from {result['tasks_read']} read. Mechanical score runs 0 to {MECHANICAL_MAX} of the "
             f"composite's 100; the other 45 (heat, domain weight, neglect) are the model's.", "",
             "| # | Score | Project | Domain | Open | Ovd | Wait | Stale | Next due | Flags |",
             "|--:|------:|---------|--------|-----:|----:|-----:|------:|----------|-------|"]
    for rank, r in enumerate(result["projects"], 1):
        m = r["mechanical"]
        stale = m["staleness"]["days_since_activity"]
        lines.append(f"| {rank} | {r['mechanical_score']} | {cell(r['name'], 34)} | {cell(r['domain'], 18)} | "
                     f"{m['load']['open_tasks']} | {m['load']['overdue_tasks']} | {m['load']['waiting_tasks']} | "
                     f"{'?' if stale is None else stale} | {m['next_dated_task'] or '-'} | {' '.join(r['flags'])} |")
    counts = result["flag_counts"]
    lines += ["", "Flags: " + (", ".join(f"{k} {v}" for k, v in counts.items()) if counts else "none")]
    return "\n".join(lines)


def main(argv=None, client=None):
    ap = argparse.ArgumentParser(description="Every active Portal project with its mechanical score. Read only.")
    ap.add_argument("--limit", type=int, default=0, help="keep only the top N by mechanical score")
    ap.add_argument("--domain", default="", help="only projects whose domain name contains this text")
    ap.add_argument("--as-of", default="", help="score against this date (YYYY-MM-DD) instead of today")
    ap.add_argument("--config", default="", help="MCP config file (default: the portal_mcp_config setting)")
    ap.add_argument("--server", default="", help="server name in the MCP config (default: portal_server or insights-portal)")
    ap.add_argument("--json", action="store_true", help="print the project list as JSON")
    ap.add_argument("--explain", action="store_true", help="also print the item keys the Portal returned, to stderr")
    args = ap.parse_args(argv)
    try:
        if args.limit < 0:
            raise ValueError("--limit cannot be negative")
        now = datetime.now(timezone.utc)
        if args.as_of.strip():
            now = parse_time(args.as_of.strip())
            if now is None:
                raise ValueError(f"--as-of wants YYYY-MM-DD, got {args.as_of!r}")
        client = client or connect(args.config or None, args.server or None)
        corpus, unreadable = read_corpus(client)
    except (ValueError, SettingMissing, PortalError) as exc:
        print(safe(f"ERROR {exc}"), file=sys.stderr)
        return 2
    except Exception as exc:  # a transport or shape failure means no scoreboard
        print(safe(f"ERROR project-scoreboard could not complete: {type(exc).__name__}: {exc}"), file=sys.stderr)
        return 2
    result = build(corpus, now, domain=args.domain, limit=args.limit)
    for w in warnings_for(result, unreadable, args.domain):
        print(safe(f"warning: {w}"), file=sys.stderr)
    print(safe(json.dumps(result["projects"], indent=1, default=str) if args.json else as_markdown(result)))
    if args.explain:
        print(f"portal calls: {getattr(client, 'calls', None)}", file=sys.stderr)
        for kind in ENTITY_TYPES:
            seen = key_report(corpus.get(kind, []))
            print(f"keys seen on {kind} items ({seen['items']} read):", file=sys.stderr)
            for key, n in seen["keys"].items():
                print(f"  {key} ({n})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
