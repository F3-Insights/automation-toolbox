# /// script
# dependencies = ["pyyaml"]
# ///
"""Whether task capture is done, computed from the capture sources and the capture ledger.

Offline and read only: it reads the sources (see _common.py), the capture ledger and
runs.jsonl, never the Portal, so a scheduler can run it often for nothing. Three tests:

- processed: no source item that was in the sources when the last Run started is still
  undecided. An item is late when the ledger holds it as `seen` with a first_seen at or before
  the last live Run's start. An item the ledger has never seen arrived after that Run: new, not late.
- no-duplicates: every `created` row names its task and the item's marker, and no task was
  created for two items.
- sources: every source that is not `future` could be read (an absent optional file counts).

Inputs: --sources FILE (default: the [task-stack-capture] settings), --state DIR,
--horizon-days N (14; older items no Run has seen are not work), --as-of YYYY-MM-DD.
Prints a text report, the JSON (--format json), or with --precheck one line for a heartbeat:
`WORK: <n> source item(s) to capture` or `NOTHING: ...`, with indented detail lines.
Exit 0 whenever it ran; 2 on a bad argument or an unusable sources file.

Example:
    python3 task_capture_check.py --precheck
"""

import argparse
import json
import sys
from datetime import datetime, timedelta

import _common as c

TESTS = ("processed", "no-duplicates", "sources")
HORIZON_DEFAULT = 14
SHOW = 10


def _when(value):
    try:
        stamp = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return stamp if stamp.tzinfo else stamp.astimezone()


def check(items, reports, rows, last, today, horizon_days=HORIZON_DEFAULT):
    cutoff = today - timedelta(days=horizon_days)
    started = _when((last or {}).get("started_at"))
    tests = {}

    late, new, waiting = [], [], []
    for it in items:
        row = rows.get(it["key"])
        if row and row.get("state") in c.FINAL:
            continue
        day = c.parse_day(it["date"])
        if row is None:
            # Never seen by a Run: new work if open and inside the horizon.
            if it["open"] and (day is None or day >= cutoff):
                new.append(it["key"])
            continue
        waiting.append(it["key"])
        seen = _when(row.get("first_seen"))
        if started is not None and seen is not None and seen <= started:
            late.append(f"{it['key']}: {row.get('state')} since {row.get('first_seen')} ({row.get('note') or 'no note'})")
    tests["processed"] = {"met": not late, "gaps": late,
                          "detail": f"{len(new)} new since the last Run, {len(waiting)} waiting in the ledger"}

    dupes, by_task = [], {}
    for key, row in rows.items():
        if row.get("state") != "created":
            continue
        if not row.get("task") or not row.get("marker"):
            dupes.append(f"{key}: created without its task or marker")
            continue
        if row["marker"] != c.source_marker(key):
            dupes.append(f"{key}: marker {row['marker']} is not the item's ({c.source_marker(key)})")
        if row["task"] in by_task:
            dupes.append(f"{row['task']} created for both {by_task[row['task']]} and {key}")
        by_task.setdefault(row["task"], key)
    tests["no-duplicates"] = {"met": not dupes, "gaps": dupes,
                              "detail": f"{len(by_task)} task(s) created from source items"}

    unreadable = [f"{r['name']}: {r['error']}" for r in reports if r.get("readable") is False]
    future = [r["name"] for r in reports if r["kind"] == "future"]
    tests["sources"] = {"met": not unreadable, "gaps": unreadable,
                        "detail": f"{sum(1 for r in reports if r.get('readable'))} read"
                                  + (f"; not reachable yet: {', '.join(future)}" if future else "")}

    stuck = sorted(k for k, r in rows.items() if r.get("state") == "stuck")
    met = sum(1 for t in tests.values() if t["met"])
    return {"tool": "task-capture-check", "as_of": today.isoformat(), "horizon_days": horizon_days,
            "last_run": last, "tests": tests, "met": met, "of": len(TESTS), "done": met == len(TESTS),
            "new": new, "waiting": waiting, "stuck": stuck, "sources": reports, "ledger_rows": len(rows)}


def precheck_line(result):
    todo = len(result["new"]) + len(result["waiting"])
    if todo:
        head = (f"WORK: {todo} source item(s) to capture ({len(result['new'])} new, "
                f"{len(result['waiting'])} waiting from earlier Runs)")
    else:
        head = f"NOTHING: no source item to capture ({result['ledger_rows']} recorded)"
    lines = [head] + [f"  unreadable source {g}" for g in result["tests"]["sources"]["gaps"]]
    if result["stuck"]:
        lines.append(f"  {len(result['stuck'])} item(s) stuck after {c.MAX_ATTEMPTS} attempts")
    return "\n".join(lines)


def render(result):
    last = result["last_run"] or {}
    out = [f"task-capture-check as of {result['as_of']}; last Run started {last.get('started_at') or 'never'}",
           f"{'DONE' if result['done'] else 'NOT DONE'} ({result['met']} of {result['of']} tests met)"]
    for number, (name, test) in enumerate(result["tests"].items(), start=1):
        out.append(f"{number} {name}: {'MET' if test['met'] else 'NOT MET'} ({test['detail']})")
        out += [f"  - {gap}" for gap in test["gaps"][:SHOW]]
        if len(test["gaps"]) > SHOW:
            out.append(f"  - and {len(test['gaps']) - SHOW} more")
    for r in result["sources"]:
        state = {True: f"{r['items']} item(s), {r['open']} open", False: f"UNREADABLE {r['error']}",
                 None: r.get("note") or "not read"}[r.get("readable")]
        out.append(f"  source {r['name']} ({r['kind']}): {state}")
    if result["stuck"]:
        out.append(f"  stuck: {', '.join(result['stuck'][:SHOW])}")
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(prog="task_capture_check.py", description=__doc__.split("\n\n")[0])
    p.add_argument("--sources", default="", help="The capture sources file (default: the settings)")
    p.add_argument("--state", default="", help="The task-stack state folder")
    p.add_argument("--horizon-days", default=str(HORIZON_DEFAULT),
                   help="New items dated before today minus this many days are not work (default 14)")
    p.add_argument("--as-of", default="", help="Judge as of this date (YYYY-MM-DD); blank: today")
    p.add_argument("--format", choices=("text", "json"), default="text")
    p.add_argument("--precheck", action="store_true", help="One line, WORK: or NOTHING:, for a scheduler")
    a = p.parse_args(argv)
    try:
        horizon = c.whole_number(a.horizon_days, "horizon-days", HORIZON_DEFAULT, 0, 3650)
        today = c.as_of_date(a.as_of)
        sources, _origin = c.load_sources(a.sources)
        items, reports = c.gather(sources)
        root = c.state_root(a.state)
        result = check(items, reports, c.read_ledger(root), c.last_run(root), today, horizon)
    except c.Bad as exc:
        c.fail(exc)
    if a.precheck:
        print(precheck_line(result))
    elif a.format == "json":
        print(json.dumps(result, indent=1, ensure_ascii=False, default=str))
    else:
        print(render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
