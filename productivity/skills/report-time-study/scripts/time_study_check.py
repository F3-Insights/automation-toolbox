"""Say whether the time study of a period, or of one window, is done, test by test.

Inputs: HOME, the time-study tool's private home folder (default the setting `home` under
[report-time-study]); `--period yyyy-mm` (default the last full month before `--as-of`) or
`--window D1_to_D2`; `--as-of yyyy-mm-dd` (default today). A blank option (`--period=`)
means not given.

Done is six tests, computed from the files the tool and the workers leave in the home:
1. collected: every day of the span sits in a window whose local signals are collected;
2. segmented: every recording in each window has its segment file;
3. attributed: every day of each window has slots.csv, day.md and topics.csv;
4. checked: each window has the independent checker's check.json;
5. reported: each window has out/report-<window>.md, newer than its slots and topics, and
   out/said-not-seen-<window>.json;
6. answered: no answers-<date>.md in a window is newer than its report.
A window whose report is marked provisional (questions open) with no new answers counts as
done and waiting on the owner.

Prints the tests as text, or JSON with `--format json`; `--out FILE` also writes the JSON.
`--precheck` prints one line for a scheduler, `WORK: <reason>` or `NOTHING: <reason>`, then
indented detail. Exit 0 whenever it ran, whatever it found; 2 on a bad argument or a missing home.

Example:
    python3 time_study_check.py ~/timestudy/private --period 2030-09 --format json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from _common import TESTS, Bad, fail, home_or_setting, plan, window_state


def check(home, period=None, window=None, as_of=None):
    root = Path(home).expanduser()
    today = date.fromisoformat(as_of) if as_of else date.today()
    scope = plan(root, today, period=period, window=window)
    states = {name: window_state(root, name) for name in scope["existing"]}
    tests = {}
    for t in TESTS:
        gaps = [f"{name}: {g}" for name, s in states.items() for g in s["tests"][t]["gaps"]]
        # A window not yet created fails every test: "not collected" for the first, "not started" after.
        if t == "collected":
            gaps = [f"{name}: a new window, not collected yet" for name in scope["new"]] + gaps
        else:
            gaps += [f"{name}: not started" for name in scope["new"]]
        tests[t] = {"met": not gaps, "gaps": gaps}
    met = sum(1 for t in tests.values() if t["met"])
    return {"home": str(root), "period": scope["period"], "window": window, "span": scope["span"],
            "as_of": today.isoformat(), "windows": states, "new_windows": scope["new"],
            "skipped_days": scope["skipped"], "notes": scope["notes"],
            "waiting_on_owner": sorted(n for n, s in states.items() if s["waiting_on_owner"]),
            "tests": tests, "met": met, "of": len(TESTS), "done": met == len(TESTS)}


def precheck_lines(result):
    span = f"{result['span'][0]} to {result['span'][1]}"
    waiting = result["waiting_on_owner"]
    if result["done"]:
        tail = f"; {len(waiting)} window(s) wait on the owner's answers ({', '.join(waiting)})" if waiting else ""
        lines = [f"NOTHING: every day from {span} is studied and reported{tail}"]
    else:
        open_tests = [n for n, t in result["tests"].items() if not t["met"]]
        todo = sorted({g.split(":", 1)[0] for t in result["tests"].values() for g in t["gaps"]})
        lines = [f"WORK: {len(todo)} window(s) from {span} not done ({', '.join(open_tests)})"]
        lines += [f"  window: {name}" for name in todo]
    return lines + [f"  note: {n}" for n in result["notes"]]


def render(result):
    head = f"time-study-check {result['home']} {result['period'] or result['window']}"
    out = [head, f"span {result['span'][0]} to {result['span'][1]}",
           f"{'DONE' if result['done'] else 'NOT DONE'} ({result['met']} of {result['of']} tests met)"]
    for number, (name, test) in enumerate(result["tests"].items(), start=1):
        out.append(f"{number} {name}: {'MET' if test['met'] else 'NOT MET'}")
        out += [f"  - {gap}" for gap in test["gaps"]]
    if result["waiting_on_owner"]:
        out.append("waiting on the owner's answers: " + ", ".join(result["waiting_on_owner"]))
    return "\n".join(out + [f"note: {n}" for n in result["notes"]])


def main(argv=None):
    ap = argparse.ArgumentParser(prog="time-study-check", description=__doc__.split("\n\n")[0])
    ap.add_argument("home", nargs="?", default="", help="the tool's home folder")
    ap.add_argument("--period", default="", help="yyyy-mm; blank: the last full month")
    ap.add_argument("--window", default="", help="one window, D1_to_D2")
    ap.add_argument("--as-of", dest="as_of", default="", help="judge as of this date, yyyy-mm-dd")
    ap.add_argument("--format", dest="fmt", choices=["text", "json"], default="text")
    ap.add_argument("--out", default="", help="also write the JSON result to this file")
    ap.add_argument("--precheck", action="store_true", help="one line, WORK: or NOTHING:, for a scheduler")
    a = ap.parse_args(argv)
    try:
        as_of = a.as_of.strip() or None
        if as_of:
            date.fromisoformat(as_of)
        result = check(home_or_setting(a.home), period=a.period.strip() or None,
                       window=a.window.strip() or None, as_of=as_of)
    except (Bad, ValueError) as exc:
        return fail(exc)
    if a.out.strip():
        Path(a.out.strip()).expanduser().write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    if a.precheck:
        print("\n".join(precheck_lines(result)))
    elif a.fmt == "json":
        print(json.dumps(result, indent=1))
    else:
        print(render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
