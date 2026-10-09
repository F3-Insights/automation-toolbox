"""Collect the local signals for every window of a time-study Run not yet collected.

The refresh before a time-study session. It works out the Run's windows (the period, default
the last full month, widened back to the day after the latest window; or the one window
named) and runs the time-study tool's `collect` for every window not yet collected: each new
window, and each existing one without its coverage.json. Collected windows are left alone, and
the tool's `--force` is never passed.

Inputs: HOME (the tool's private home; default the setting `home` under [report-time-study]),
`--period yyyy-mm`, `--window D1_to_D2`, `--as-of yyyy-mm-dd`, `--dry-run-if true` (plan only,
collect nothing), `--repo DIR` (the tool's checkout; see time_study_tool.py), `--format text|json`.

The first line is for the session that follows: `COLLECTED: ...`, `NOTHING: ...`, `PLAN: ...`
on a dry run, or `PARTIAL: ...` when a window's collect failed, with its reason indented below.
Exit 0 whenever it ran; 2 on a bad argument, a missing home or no checkout.

Example:
    python3 time_study_collect.py ~/timestudy/private --period 2030-09
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from _common import Bad, fail, home_or_setting, parse_window, plan, run_tool

TRUE = {"1", "true", "yes", "on"}


def collect(home, period=None, window=None, as_of=None, dry_run=False, repo=None):
    root = Path(home).expanduser()
    today = date.fromisoformat(as_of) if as_of else date.today()
    scope = plan(root, today, period=period, window=window)
    todo = list(scope["new"]) + [n for n in scope["existing"]
                                 if not (root / "data" / "raw" / n / "coverage.json").is_file()]
    results = []
    for name in todo:
        a, b = parse_window(name)
        if dry_run:
            results.append({"window": name, "state": "planned"})
            continue
        code, out, err = run_tool(str(root), "collect", ["--since", a.isoformat(), "--until", b.isoformat(),
                                                         "--window", name], repo=repo)
        lines = [ln for ln in (out + err).splitlines() if ln.strip()]
        results.append({"window": name, "state": "collected" if code == 0 else "failed",
                        "exit": code, "output": lines[-6:]})
    return {"home": str(root), "period": scope["period"], "span": scope["span"], "dry_run": dry_run,
            "windows": results, "already": [n for n in scope["existing"] if n not in todo],
            "notes": scope["notes"]}


def first_line(result):
    span = f"{result['span'][0]} to {result['span'][1]}"
    names = [r["window"] for r in result["windows"]]
    failed = [r["window"] for r in result["windows"] if r["state"] == "failed"]
    if not names:
        return f"NOTHING: every window from {span} is already collected"
    if result["dry_run"]:
        return f"PLAN: dry run; would collect {len(names)} window(s) from {span}: {', '.join(names)}"
    if failed:
        return (f"PARTIAL: collected {len(names) - len(failed)} of {len(names)} window(s) from {span}; "
                f"failed: {', '.join(failed)}")
    return f"COLLECTED: {len(names)} window(s) from {span}: {', '.join(names)}"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="time-study-collect", description=__doc__.split("\n\n")[0])
    ap.add_argument("home", nargs="?", default="", help="the tool's home folder")
    ap.add_argument("--period", default="", help="yyyy-mm; blank: the last full month")
    ap.add_argument("--window", default="", help="one window, D1_to_D2")
    ap.add_argument("--as-of", dest="as_of", default="", help="plan as of this date, yyyy-mm-dd")
    ap.add_argument("--dry-run-if", dest="dry_run_if", default="", help="true: plan only, collect nothing")
    ap.add_argument("--repo", default="", help="the time-study checkout")
    ap.add_argument("--format", dest="fmt", choices=["text", "json"], default="text")
    a = ap.parse_args(argv)
    try:
        if a.as_of.strip():
            date.fromisoformat(a.as_of.strip())
        result = collect(home_or_setting(a.home), period=a.period.strip() or None,
                         window=a.window.strip() or None, as_of=a.as_of.strip() or None,
                         dry_run=a.dry_run_if.strip().lower() in TRUE, repo=a.repo.strip() or None)
    except (Bad, ValueError) as exc:
        return fail(exc)
    if a.fmt == "json":
        print(json.dumps({"first_line": first_line(result), **result}, indent=1))
        return 0
    print(first_line(result))
    for r in result["windows"]:
        if r["state"] == "failed":
            print(f"  {r['window']} exit {r['exit']}: " + " / ".join(r["output"]))
    for n in result["notes"]:
        print(f"  note: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
