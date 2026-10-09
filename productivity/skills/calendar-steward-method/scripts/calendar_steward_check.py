#!/usr/bin/env python3
"""calendar-steward-check: whether the calendar steward's pass is done, computed from the Run
folder, the steward's home and (with --portal) the owner's answers on the approval task.

The tests of done:
1. scan: the scan for the window was read and is fresh (RUN/scan.json, else the copy kept
   with the day's list).
2. proposals: the proposal file is well formed, every event it names is in the scan, every
   focus block and move lands in free time, no meeting with other attendees is moved, every
   decline carries its draft, at most twelve items.
3. coverage: every finding in the scan has a proposal or a stated dismissal.
4. published: the day's list is kept in the home and is on the owner's approval task (a list
   with no items needs no task). A dry run meets it with RUN/publish-dry-run.json.
5. applied: no item was changed without an ok, the last apply failed nothing, and (with
   --portal) every item the owner answered ok or no has an outcome.
The approve pass is judged on 5 alone.

--precheck prints one line for a scheduler: `WORK: <reason>` when today's list is not yet
published (weekdays) or an answer of ok or no waits to be applied; otherwise
`NOTHING: <reason>`.

Inputs: DATE (blank: today in the owner's timezone), --run, --home, --portal, --tz,
--format text|json, --precheck. Exit 0 whenever it ran, 2 on a bad argument.

Example:
    python3 calendar_steward_check.py 2026-10-05 --run RUN --portal
"""

import argparse
import json
import sys
from datetime import timedelta

import _common as c

TESTS = ("scan", "proposals", "coverage", "published", "applied")


def first_json(*paths):
    for p in paths:
        if p is not None:
            value = c.read_json(p)
            if value is not None:
                return value
    return None


def pending_answers(home, today, portal):
    """Lists where an answer of ok or no is not yet applied, judged from the answers against
    the item ledger, never from clocks."""
    out = []
    rows = {r["id"]: r for r in c.Ledger(home).rows()}
    for folder in c.day_folders(home):
        listed = c.folder_day(folder)
        published, frozen = c.read_json(folder / "publish.json"), c.read_json(folder / "items.json")
        if (not isinstance(published, dict) or not isinstance(frozen, dict) or not published.get("items")
                or listed < today - timedelta(days=c.LIST_DAYS) or listed > today):
            continue
        sources = c.answer_sources(folder, portal, published.get("task") if portal is not None else None)
        resolved = c.resolve_answers(frozen.get("items") or [], sources)
        waiting = [r["n"] for r in resolved["items"] if r["state"] in ("approved", "declined")
                   and (rows.get(f"{folder.name}:{r['n']}") or {}).get("state") not in c.FINAL]
        if waiting:
            out.append(f"{folder.name}: item(s) {', '.join(str(n) for n in waiting)}")
    return out


def applied_gaps(home, run):
    gaps = []
    for row in c.Ledger(home).rows():
        if row.get("state") in ("applied", "unchanged"):
            verb, extra = c.read_answer(row.get("answer") or "")
            if verb != "ok" or extra:
                gaps.append(f"{row['id']}: {row.get('state')} without an ok (answer {row.get('answer')!r})")
        if row.get("state") == "failed":
            gaps.append(f"{row['id']}: the write failed ({row.get('outcome')}); the next apply retries it")
    if run is not None:
        for name in ("apply.json", "apply-dry-run.json"):
            result = c.read_json(run / name)
            if isinstance(result, dict) and result.get("status") == "failed":
                gaps.append(f"{name}: a write failed")
    return gaps


def check(day, home, run=None, portal=None):
    folder = home / day.isoformat()
    scan = first_json(run / "scan.json" if run else None, folder / "scan.json")
    doc = first_json(run / "proposals.json" if run else None, folder / "proposals.json")
    pass_ = str(scan.get("pass") or "auto") if isinstance(scan, dict) else "auto"
    tests = {}

    def put(name, gaps, note=""):
        tests[name] = {"met": not gaps, "gaps": gaps, "note": note}

    if pass_ == "approve":
        for name in ("scan", "proposals", "coverage", "published"):
            put(name, [], "not this pass (approve)")
    else:
        if not isinstance(scan, dict):
            put("scan", ["no scan.json in the Run folder or with the day's list"])
        elif scan.get("stale"):
            put("scan", [f"the scan is STALE: {scan.get('reason')}"])
        elif scan.get("date") != day.isoformat():
            put("scan", [f"the scan is for {scan.get('date')}, not {day.isoformat()}"])
        else:
            put("scan", [], f"{len(scan.get('findings') or [])} finding(s)"
                + (f"; read gaps: {'; '.join(scan['unreadable'])}" if scan.get("unreadable") else ""))
        good_scan = scan if isinstance(scan, dict) and not scan.get("stale") else None
        if doc is None:
            put("proposals", ["no proposals.json"])
            put("coverage", ["no proposals.json"])
        else:
            put("proposals", c.proposals_problems(doc, good_scan, day=day.isoformat()),
                f"{len(doc.get('proposals') or [])} proposal(s)" if isinstance(doc, dict) else "")
            put("coverage", c.coverage_gaps(doc, good_scan) if isinstance(doc, dict) else ["not readable"])
        published = c.read_json(folder / "publish.json")
        dry = c.read_json(run / "publish-dry-run.json") if run else None
        if isinstance(published, dict) and (published.get("task") or not published.get("items")):
            put("published", [], f"task {published.get('task') or 'none (no items)'}, {published.get('items')} item(s)")
        elif isinstance(dry, dict) and dry.get("status") in ("would_publish", "unchanged"):
            put("published", [], "dry run: would publish")
        else:
            put("published", ["the day's list is not published"])
    gaps = applied_gaps(home, run)
    if portal is not None:
        gaps += [f"answers not yet applied: {p}" for p in pending_answers(home, day, portal)]
    put("applied", gaps)
    met = sum(1 for t in tests.values() if t["met"])
    return {"date": day.isoformat(), "pass": pass_, "home": str(home), "run": str(run) if run else None,
            "tests": {k: tests[k] for k in TESTS}, "met": met, "of": len(TESTS), "done": met == len(TESTS)}


def precheck(home, today, portal):
    published = c.read_json(home / today.isoformat() / "publish.json")
    if today.weekday() < 5 and not isinstance(published, dict):
        return f"WORK: the calendar list for {today.isoformat()} is not published"
    pending = pending_answers(home, today, portal)
    if pending:
        return f"WORK: answers to apply ({'; '.join(pending[:3])})"
    return (f"NOTHING: the list for {today.isoformat()} is published and no answer waits" if isinstance(published, dict)
            else f"NOTHING: {today.strftime('%A')}, no list due and no answer waits")


def render(result):
    out = [f"calendar-steward-check {result['date']} ({result['pass']} pass)",
           f"{'DONE' if result['done'] else 'NOT DONE'} ({result['met']} of {result['of']} tests met)"]
    for number, (name, test) in enumerate(result["tests"].items(), start=1):
        out.append(f"{number} {name}: {'MET' if test['met'] else 'NOT MET'}" + (f" ({test['note']})" if test["note"] else ""))
        out += [f"  - {gap}" for gap in test["gaps"][:25]]
        if len(test["gaps"]) > 25:
            out.append(f"  - and {len(test['gaps']) - 25} more")
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="Whether the calendar steward's pass is done, test by test.")
    parser.add_argument("day", nargs="?", default="", help="the list's day, yyyy-mm-dd (blank: today)")
    parser.add_argument("--run", default="", help="the Run folder (scan.json, proposals.json, the finish's results)")
    parser.add_argument("--home", default="", help="the steward's home folder")
    parser.add_argument("--portal", action="store_true", help="also read the owner's answers on the approval tasks")
    parser.add_argument("--tz", default="", help="IANA timezone for today")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--precheck", action="store_true", help="one line, WORK: or NOTHING:, for a scheduler")
    args = parser.parse_args()
    try:
        day = c.resolve_day(args.day, c.zone(c.blank(args.tz) or None))
        home = c.home_dir(args.home)
        run = c.guard_run_path(args.run) if c.blank(args.run) else None
    except c.Bad as exc:
        print(c.safe(f"ERROR {exc}"), file=sys.stderr)
        sys.exit(2)
    portal = None
    if args.portal:
        try:
            portal = c.client()
        except Exception as exc:  # the check runs without the Portal and says so
            print(c.safe(f"note: the Portal could not be reached ({type(exc).__name__}); local answers only"), file=sys.stderr)
    try:
        if args.precheck:
            print(precheck(home, day, portal))
            return
        result = check(day, home, run, portal)
    except c.Bad as exc:
        print(c.safe(f"ERROR {exc}"), file=sys.stderr)
        sys.exit(2)
    print(c.safe(json.dumps(result, indent=1) if args.format == "json" else render(result)))


if __name__ == "__main__":
    main()
