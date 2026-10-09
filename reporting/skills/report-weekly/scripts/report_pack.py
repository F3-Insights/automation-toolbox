#!/usr/bin/env python3
"""report-pack: collect and organise one scope's week in one command.

Runs report_collect.py (the Portal tier) and then report_organize.py with the same flags, so a
caller who wants one command has one. The evidence ledger between them is kept with
--ledger-out, which is what report_organize.py can be re-run from without another sweep.

Inputs: the collection flags (--domain, --since, --until, --lookahead-days, --outline-file,
--direct-report-dir, --prior-reports, --scope-term) and the organising flags (--facts,
--ledger-candidates, --gate1, --max-evidence). Writes the pack (--out) and the digest
(--digest), and prints what each step printed. Exit 0 ok, 2 error.

Example:
  python3 report_pack.py --domain "Northwind" --outline-file profile.md --out pack.json --digest digest.md
"""

import argparse
import sys
import tempfile
from pathlib import Path

from _common import OK, Fail, run_main, run_script

COLLECT = ("domain", "since", "until", "lookahead_days", "outline_file", "direct_report_dir", "prior_reports",
           "scope_term")
ORGANIZE = ("outline_file", "facts", "ledger_candidates", "gate1", "max_evidence", "out", "digest")


def flags(args, names):
    out = []
    for name in names:
        value = getattr(args, name)
        if value not in (None, ""):
            out += [f"--{name.replace('_', '-')}", value]
    return out


def main():
    parser = argparse.ArgumentParser(description="Collect, then organise, one scope's week.")
    for name in sorted(set(COLLECT) | set(ORGANIZE)):
        parser.add_argument(f"--{name.replace('_', '-')}", default=None)
    parser.add_argument("--ledger-out", default="", help="keep the evidence ledger here")
    args = parser.parse_args()
    if not args.domain:
        raise Fail("--domain is required: the Portal scope's name or uuid")
    with tempfile.TemporaryDirectory() as scratch:
        ledger = Path(args.ledger_out).expanduser() if args.ledger_out else Path(scratch) / "ledger.json"
        for name, command in (("report_collect", flags(args, COLLECT) + ["--out", ledger]),
                              ("report_organize", ["--ledger", ledger] + flags(args, ORGANIZE))):
            code, out, err = run_script(name, command)
            sys.stdout.write(out)
            sys.stderr.write(err)
            if code:
                raise Fail(f"{name}.py stopped with exit {code}")
    return OK


if __name__ == "__main__":
    run_main(main)
