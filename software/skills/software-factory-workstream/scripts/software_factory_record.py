"""Upsert one row of a repository's software-factory ledger.

The ledger is <state_dir>/<owner>__<name>/SOFTWARE-FACTORY-LEDGER.csv, one row per issue
attempt keyed <issue>:<attempt> (SOFTWARE-FACTORY.md, "The ledger"). Issue 0 is onboarding.

The attempt is --attempt K (at most the latest + 1), --new-attempt for latest + 1 (a re-build
after a failure or a reopen), else the issue's latest attempt, or 1 for a new issue. Fields left
out keep their recorded value; '' clears one. A new --head-sha without a new --review clears the
review, so a PASS never outlives the code it passed. No row is ever deleted, every other row
keeps its exact text, and the file is written atomically. --title keeps the issue's title in
SOFTWARE-FACTORY-TITLES.json beside the ledger, for software_factory_check.py's repeat check.

Inputs: OWNER/NAME and the options below. State folder: $SOFTWARE_FACTORY_STATE_DIR, else
<state_dir setting>/software-factory, else ~/.local/state/software-factory.
Prints what it did (or JSON with --format json). Exit 0 recorded, 2 on a bad argument.

Example:
  python3 software_factory_record.py acme/widgets --issue 42 --state building \
      --branch software-factory/issue-42-fix-dates --by software-factory-orchestrator
"""

import argparse
import json
import sys
from pathlib import Path

from _common import STATES, FactoryError, record


def main(argv=None):
    ap = argparse.ArgumentParser(description="Upsert one row of OWNER/NAME's software-factory ledger.")
    ap.add_argument("repo", help="OWNER/NAME")
    ap.add_argument("--issue", required=True, help="the issue number; 0 for onboarding")
    ap.add_argument("--state", required=True, help=f"one of {', '.join(STATES)}")
    ap.add_argument("--attempt", help="the attempt (default: the issue's latest, or 1)")
    ap.add_argument("--new-attempt", action="store_true", help="start attempt latest+1")
    ap.add_argument("--branch")
    ap.add_argument("--pr")
    ap.add_argument("--head-sha", help="the branch's head commit; a new one clears the review")
    ap.add_argument("--verify", help="verified, failed, no-tests or repro-not-shown ('' clears)")
    ap.add_argument("--review", help="PASS or FAIL ('' clears)")
    ap.add_argument("--risk", help="low, normal or one-way-door ('' clears)")
    ap.add_argument("--note", help="one line of note")
    ap.add_argument("--title", help="the issue's title, kept for the repeat check")
    ap.add_argument("--by", required=True, help="who recorded the row")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args(argv)
    try:
        result = record(args.repo, args.issue, args.state, args.by, attempt=args.attempt,
                        new_attempt=args.new_attempt, title=args.title, branch=args.branch, pr=args.pr,
                        head_sha=args.head_sha, verify=args.verify, review=args.review, risk=args.risk,
                        note=args.note)
    except (FactoryError, OSError) as exc:
        print(f"software_factory_record: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(result, indent=1))
    else:
        print(f"{result['action']} {result['id']} ({result['row']['state']}) in {Path(result['path']).name}")
        for warning in result["warnings"]:
            print(f"  warning: {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
