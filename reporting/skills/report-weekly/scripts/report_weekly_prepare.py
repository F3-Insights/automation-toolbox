#!/usr/bin/env python3
"""report-weekly-prepare: collect and organise the week in code before an unattended session.

    report_weekly_prepare.py STORE [--scope NAME] [--period YYYY-MM-DD] [--phase collect|assemble|auto]
                             [--from-dir DIR] [--direct-report-dir DIR] [--run-dir DIR]
                             [--dry-run-if true|false] [--format text|json]

Runs the report-weekly skill's code steps in order, with this folder's own scripts:
  1. the role profile STORE/profile.md: validate, and whether its quarterly review is due;
  2. the work order, opened on disk only (the owner's visible task is the gate request);
  3. the week, in the profile's tier: portal reads --scope, manual folds --from-dir in, and
     harvester is left to the session, which dispatches the harvester worker;
  4. the facts set, started once per week from the profile's standing metrics;
  5. the report ledger's candidates, when the store has a ledger;
  6. the pack and the digest.
Everything lands in STORE/work/<period>/ (a dry run writes under RUN_DIR/work/<period>/ and opens
no work order). A week whose gate questions are out (gates.json exists) is never recollected:
the owner's answers are numbered against that collection. The assemble phase collects nothing.

The first line printed is FRESH: ... when the week is collected and organised, STALE: ... and
why when it is not (an invalid profile, a review due, a failed collection). The result is also
written to prepare.json in the week folder. Exit 0 whenever it ran; 2 on a bad argument.

Example:
  python3 report_weekly_prepare.py ~/reports/finance --scope "Northwind" --period 2027-11-12
"""

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from _common import (FILES, OK, WORK_DIR, Fail, first_line, json_or_none, now_utc,
                     resolve_period, run_main, run_script, store_dir, week_dir, week_start, write_json,
                     write_text)

AGENT = "weekly-report-orchestrator"


def prepare(store, period, scope, phase, from_dir, direct_dir, run_dir, dry_run):
    home = week_dir(store, period)
    if dry_run and not run_dir:
        raise Fail("a dry run needs --run-dir: nothing is written in the store")
    folder = Path(run_dir).expanduser() / WORK_DIR / period if dry_run else home
    folder.mkdir(parents=True, exist_ok=True)
    file = lambda role: folder / FILES[role]  # noqa: E731
    profile = store / "profile.md"
    steps = []
    result = {"schema": "report-weekly-prepare/1", "period": period, "store": str(store), "folder": str(folder),
              "phase": phase, "dry_run": dry_run, "started_at": now_utc(), "steps": steps}

    def step(name, args, timeout=1800):
        code, out, err = run_script(name, args, timeout)
        said = first_line(out)
        steps.append({"step": name, "exit": code, "detail": first_line(err) or ("" if said.startswith("{") else said)
                      or ("ok" if code == OK else f"exit {code}")})
        return code, out, err

    def finish(status, line, **extra):
        result.update(extra, status=status, line=f"{status}: {line}", finished_at=now_utc())
        write_json(file("prepare"), result)
        return result

    if not profile.is_file():
        return finish("STALE", f"no role profile at {profile}; the owner runs the report-weekly setup interview first", blocked="profile")
    code, out, _ = step("report_profile", ["validate", "--profile", profile, "--json"])
    if code:
        errors = (json_or_none_text(out) or {}).get("errors") or [{"detail": f"exit {code}"}]
        return finish("STALE", f"the role profile does not validate ({len(errors)} error(s)): {errors[0].get('detail')}",
                      blocked="profile", profile_errors=errors)
    code, out, _ = step("report_profile", ["due", "--profile", profile, "--json"])
    if (json_or_none_text(out) or {}).get("due") is True:
        return finish("STALE", "the role profile's quarterly review is due; the owner runs the report-weekly setup interview",
                      blocked="profile-review")
    _, out, _ = step("report_profile", ["show", "--profile", profile, "--json"])
    tier = str((json_or_none_text(out) or {}).get("tier") or "portal").casefold()
    result["tier"] = tier

    if (home / FILES["gates"]).is_file() or ((home / FILES["pack"]).is_file() and phase == "assemble"):
        items = len((json_or_none(home / FILES["ledger"]) or {}).get("items") or [])
        return finish("FRESH", f"kept the collection for the week ending {period} ({items} evidence items); the gate "
                               f"questions are numbered against it", collected=False, kept=True, folder=str(home))
    if phase == "assemble":
        return finish("STALE", f"the week ending {period} has not been collected; the assembly has nothing to draft from",
                      collected=False)
    if not dry_run:
        step("report_workorder", ["open", "--period", period, "--author", slug(store.name), "--agent", AGENT,
                                  "--store", store, "--no-portal"])
    if tier == "harvester":
        return finish("STALE", "the profile's tier is harvester: the session dispatches report-harvester to write the "
                               "evidence ledger, then runs this again", collected=False)
    window = ["--since", week_start(period), "--until", (date.fromisoformat(period) + timedelta(days=1)).isoformat(),
              "--outline-file", profile, "--out", file("ledger")]
    if tier == "manual":
        if not from_dir:
            return finish("STALE", "the profile's tier is manual and no --from-dir was given", collected=False)
        window = ["--tier", "manual", "--from-dir", from_dir, "--domain", scope or "the author's scope"] + window
    elif not scope:
        return finish("STALE", "the portal tier needs --scope, the Portal scope's name", collected=False)
    else:
        window = ["--domain", scope, "--lookahead-days", "7"] + window
    window += ["--direct-report-dir", direct_dir] if direct_dir else []
    code, out, err = step("report_collect", window)
    if code or not file("ledger").is_file():
        return finish("STALE", f"report-collect failed (exit {code}): {first_line(err) or first_line(out)}", collected=False)
    if not file("facts").is_file():
        step("report_facts", ["init", "--facts", file("facts"), "--period", period, "--profile", profile])
    candidates = None
    if (store / "report-ledger.jsonl").is_file():
        code, out, _ = step("report_ledger", ["candidates", "--evidence", file("ledger"), "--as-of", period,
                                              "--store", store])
        if code == OK and json_or_none_text(out) is not None:
            write_text(file("candidates"), out)
            candidates = file("candidates")
    else:
        steps.append({"step": "report_ledger", "exit": 0, "detail": "no report ledger yet; continuity is skipped"})
    args = ["--ledger", file("ledger"), "--outline-file", profile, "--out", file("pack"), "--digest", file("digest")]
    args += ["--facts", file("facts")] if file("facts").is_file() else []
    args += ["--ledger-candidates", candidates] if candidates else []
    code, out, err = step("report_organize", args)
    if code or not file("pack").is_file():
        return finish("STALE", f"report-organize produced no pack (exit {code}): {first_line(err) or first_line(out)}",
                      collected=True)
    if not dry_run:
        step("report_workorder", ["stage", "--period", period, "--stage", "organize", "--store", store, "--no-portal",
                                  "--file", file("pack"), "--note", "collected and organised in code before the session"])
    items = len((json_or_none(file("ledger")) or {}).get("items") or [])
    errors = ((json_or_none(file("pack")) or {}).get("outline") or {}).get("errors") or []
    if errors:
        return finish("STALE", f"collected {items} evidence items, but the profile has {len(errors)} error(s): {errors[0]}",
                      collected=True, items=items, outline_errors=len(errors))
    count = len((json_or_none(candidates) or {}).get("candidates") or []) if candidates else 0
    return finish("FRESH", f"collected {items} evidence items for the week ending {period} ({tier} tier), {count} ledger "
                           f"candidates; pack and digest in {folder}", collected=True, items=items,
                  ledger_candidates=count, outline_errors=0)


def json_or_none_text(text):
    try:
        found = json.loads(text)
    except (TypeError, ValueError):
        return None
    return found if isinstance(found, dict) else None


def slug(name):
    text = "".join(c if c.isalnum() else "-" for c in name.casefold()).strip("-")
    while "--" in text:
        text = text.replace("--", "-")
    return text or "author"


def main():
    parser = argparse.ArgumentParser(description="Collect and organise the week before the session.")
    parser.add_argument("store", nargs="?", default="", help="the author's store; $REPORT_STORE_DIR without it")
    parser.add_argument("--scope", default="", help="the Portal scope's name (portal tier)")
    parser.add_argument("--period", default="", help="the period end; this week's Friday without it")
    parser.add_argument("--phase", default="", help="collect, assemble or auto (the default)")
    parser.add_argument("--from-dir", default="", help="the folder the manual tier folds in")
    parser.add_argument("--direct-report-dir", default="")
    parser.add_argument("--run-dir", default="", help="the Run folder; a dry run writes here")
    parser.add_argument("--dry-run-if", default="", help="true: a dry run, which writes nothing in the store")
    parser.add_argument("--today", default="", help="treat this YYYY-MM-DD as today")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    phase = args.phase.strip().casefold() or "auto"
    if phase not in ("collect", "assemble", "auto"):
        raise Fail(f"--phase {phase!r} is not collect, assemble or auto")
    today = date.fromisoformat(args.today) if args.today.strip() else None
    result = prepare(store_dir(args.store, must_exist=True), resolve_period(args.period, today), args.scope.strip(),
                     phase, args.from_dir.strip(), args.direct_report_dir.strip(), args.run_dir.strip(),
                     args.dry_run_if.strip().casefold() in ("1", "true", "yes", "on"))
    if args.format == "json":
        print(json.dumps(result, indent=1, default=str))
    else:
        print(result["line"])
        for row in result["steps"]:
            print(f"  {row['step']}: exit {row['exit']}, {row['detail']}")
    return OK


if __name__ == "__main__":
    run_main(main)
