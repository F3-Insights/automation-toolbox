#!/usr/bin/env python3
"""Lint a Sage Intacct GL journal-entry import CSV already on disk, as a person will upload it.

Checks that the file has rows and the template's 28 columns in order, then runs every entry
check: header fields on the first line only, M/D/YYYY dates, LINE_NO restarting at 1 per entry,
no negative amounts, debits equal credits, REVERSEDATE the 1st of the month after DATE, STATE as
required, and (with --liability-account) exactly one offset line per location that has debits.

Options: --liability-account ACCOUNT; --state STATE, the STATE every entry must carry (default
Posted, for a file a person uploads; pass "" to skip the check); --format text|json.
Prints a summary with each finding, or JSON with je_count, line_count, total_debits,
total_credits, states, findings, errors and passed.
Exit 0 when the file passes, 1 when any check fails, 2 when the file cannot be read.

Example:
    python3 je_import_check.py "August accrual.csv" --liability-account 2100
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _common import COLUMNS, amount, check_rows, entries, print_findings, read_rows


def check_file(path: Path, liability_account: str = "", state: str = "Posted") -> dict:
    header, rows = read_rows(path)
    findings = []

    def flag(check, detail):
        findings.append({"check": check, "severity": "error", "where": path.name, "detail": detail})

    if not rows:
        flag("rows", "the file has no rows")
    if header != COLUMNS:
        flag("columns", "the columns are not the Intacct GL template's 28, in order")
    bad = [r for r in rows if not str(r.get("LINE_NO") or "").strip().isdigit()]
    if bad:
        flag("line_no_restart", f"LINE_NO is not a number on {len(bad)} line(s)")
    else:
        findings += check_rows(rows, liability_account, state)
    debits = round(sum(amount(r.get("DEBIT")) for r in rows), 2)
    credits = round(sum(amount(r.get("CREDIT")) for r in rows), 2)
    groups = entries(rows) if not bad else []
    return {
        "path": str(path), "je_count": len(groups), "line_count": len(rows),
        "total_debits": debits, "total_credits": credits,
        "states": sorted({str(g[0].get("STATE") or "") for g in groups}),
        "findings": findings, "errors": len(findings), "passed": not findings,
        "summary": (f"{path.name}: {len(groups)} JE(s), {len(rows)} line(s), debits ${debits:,.2f}, "
                    f"credits ${credits:,.2f}; {len(findings)} error(s)"),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=__doc__.split("\n\n", 1)[1])
    parser.add_argument("csv_path")
    parser.add_argument("--liability-account", default="",
                        help="accrued-liability account; turns on the one offset per entity check")
    parser.add_argument("--state", default="Posted", help="STATE every entry must carry; '' skips the check")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    try:
        result = check_file(Path(args.csv_path).expanduser(), args.liability_account, args.state)
    except (OSError, ValueError) as exc:
        print(f"je_import_check: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(result, indent=1))
    else:
        print(result["summary"])
        print_findings(result["findings"])
        print("PASS" if result["passed"] else "FAIL")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
