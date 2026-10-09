# /// script
# dependencies = ["pyyaml"]
# ///
"""Say whether a toolbox audit is due, and whether one Run's audit is done.

Due (--precheck, for a scheduler): `WORK: ...` when AUDIT_FOLDER/runs.jsonl (written by
toolbox_audit_record.py) has no audit within --every-days (default 6, a weekly cadence less a day
of slack), else `NOTHING: last audit <date>`. A folder that does not exist yet means no audit has
run: WORK.

Done (--run RUN): the three tests of done over the Run folder, computed from scan.json,
findings.json and the fix worktree:

1. covered: every scan item at level error or warning is in a finding's `keys` (or is its `id`),
   kept or dismissed;
2. one-fix: every finding has a rank, a title, evidence, one fix and a state; a dismissed one has
   a reason;
3. fix-rule: the fix worktree's diff passes the fix rule (see _common.py), and every finding
   marked `fixed` names its files and has the checker's PASS.

With neither option it reports the last audit. Exit 0 whenever it ran, whatever it found; 2 on a
bad argument.

Example:
    python3 toolbox_audit_check.py ~/audits/toolbox --run RUN
"""

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import _common as c

TESTS = ("covered", "one-fix", "fix-rule")
EVERY_DAYS = 6


def last_audit(folder):
    path = folder / "runs.jsonl"
    if not path.is_file():
        return None
    last = None
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("date") and (last is None or str(row["date"]) >= str(last["date"])):
            last = row
    return last


def due(folder, as_of, every_days):
    last = last_audit(folder) if folder.is_dir() else None
    if last is None:
        return "WORK: no toolbox audit on record yet"
    when = date.fromisoformat(str(last["date"])[:10])
    if (as_of - when).days >= every_days:
        return f"WORK: the last toolbox audit was {when.isoformat()}, {(as_of - when).days} day(s) ago"
    return (f"NOTHING: last toolbox audit {when.isoformat()} ({last.get('findings', '?')} findings); "
            f"next due {(when + timedelta(days=every_days)).isoformat()}")


def check_run(run):
    scan = c.read_json(run / "scan.json")
    data = c.read_json(run / "findings.json")
    findings = c.findings_of(run)
    tests = {}

    gaps = []
    if scan is None:
        gaps.append("no scan.json in the Run folder")
    if data is None:
        gaps.append("no findings.json in the Run folder")
    covered = {str(k) for f in findings for k in [f.get("id")] + list(f.get("keys") or []) if k}
    wanted = [i for i in (scan or {}).get("items") or [] if i.get("level") in ("error", "warning")]
    missing = [i["key"] for i in wanted if i.get("key") not in covered]
    gaps += [f"not in any finding: {k}" for k in missing[:20]]
    if len(missing) > 20:
        gaps.append(f"and {len(missing) - 20} more")
    tests["covered"] = {"met": not gaps, "items": len(wanted), "gaps": gaps}

    gaps, ids = [], set()
    for f in findings:
        fid = str(f.get("id") or "")
        label = fid or str(f.get("title") or "a finding with no id")
        if not fid:
            gaps.append(f"{label}: no id")
        elif fid in ids:
            gaps.append(f"{fid}: two findings share the id")
        ids.add(fid)
        state = f.get("state")
        if state not in c.STATES:
            gaps.append(f"{label}: state '{state}' is none of {', '.join(c.STATES)}")
        if state == "dismissed":
            if not str(f.get("reason") or "").strip():
                gaps.append(f"{label}: dismissed with no reason")
            continue
        for key in ("title", "fix"):
            if not str(f.get(key) or "").strip():
                gaps.append(f"{label}: no {key}")
        if not f.get("evidence"):
            gaps.append(f"{label}: no evidence")
        if not isinstance(f.get("rank"), int) or f["rank"] < 1:
            gaps.append(f"{label}: no rank")
    if data is None:
        gaps.append("no findings.json in the Run folder")
    tests["one-fix"] = {"met": not gaps, "findings": len(findings), "gaps": gaps}

    gaps, files = [], []
    info = c.read_json(run / "fix-branch.json")
    worktree = Path(info["worktree"]) if info and info.get("worktree") else None
    have_tree = worktree is not None and worktree.is_dir()
    if have_tree:
        files, problems = c.verify_fix(run, worktree, c.load_denylist())
        gaps += problems
    for f in findings:
        if f.get("state") == "fixed":
            if not f.get("files"):
                gaps.append(f"{f.get('id')}: marked fixed but names no files")
            elif have_tree and not set(f["files"]) <= set(files):
                gaps.append(f"{f.get('id')}: marked fixed but its files are unchanged in the worktree")
            if f.get("review") != "PASS":
                gaps.append(f"{f.get('id')}: marked fixed without the checker's PASS")
    tests["fix-rule"] = {"met": not gaps, "files": files, "gaps": gaps}
    met = sum(1 for t in tests.values() if t["met"])
    return {"run": str(run), "tests": tests, "met": met, "of": len(TESTS), "done": met == len(TESTS)}


def render(result):
    out = [f"toolbox-audit-check --run {result['run']}",
           f"{'DONE' if result['done'] else 'NOT DONE'} ({result['met']} of {result['of']} tests met)"]
    for number, (name, test) in enumerate(result["tests"].items(), start=1):
        out.append(f"{number} {name}: {'MET' if test['met'] else 'NOT MET'}")
        out += [f"  - {gap}" for gap in test["gaps"]]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Whether a toolbox audit is due (--precheck), or a Run's audit is done (--run).")
    ap.add_argument("folder", help="the audit folder: earlier reports, the findings ledger and runs.jsonl")
    ap.add_argument("--run", help="a Run folder: judge that Run's audit")
    ap.add_argument("--as-of", help="judge as of this date (yyyy-mm-dd); default today")
    ap.add_argument("--every-days", type=int, default=EVERY_DAYS, help="an audit is due after this many days")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--precheck", action="store_true", help="one line, WORK: or NOTHING:, for a scheduler")
    args = ap.parse_args(argv)
    try:
        folder = Path(args.folder).expanduser()
        when = date.fromisoformat(args.as_of) if args.as_of else date.today()
        result = check_run(c.run_folder(args.run)) if args.run else None
    except (c.AuditError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.precheck or result is None:
        line = due(folder, when, args.every_days)
        if args.format == "json" and not args.precheck:
            print(json.dumps({"folder": str(folder), "due": line, "last": last_audit(folder)}, indent=1))
        else:
            print(line)
        return 0
    print(json.dumps(result, indent=1) if args.format == "json" else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
