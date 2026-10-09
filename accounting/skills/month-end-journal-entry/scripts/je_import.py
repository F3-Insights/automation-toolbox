#!/usr/bin/env python3
"""Build the Sage Intacct GL journal-entry import CSV from proposed entries, and lint it.

Input is a JSON file of proposed entries (a bare list of entries is accepted too):

    {"period": "2026-08",
     "proposals": [{"journal": "GJ", "description": "To accrue August rent",
                    "posting_date": "2026-08-31", "reversal_date": "2026-09-01",
                    "lines": [{"account": "6100", "location": "100", "department": "ADMIN",
                               "memo": "Accrued rent", "debit": 2500.0, "credit": 0.0},
                              {"account": "2100", "location": "100", "department": "ADMIN",
                               "memo": "Accrued rent", "debit": 0.0, "credit": 2500.0}]}]}

Each line becomes one CSV row in Intacct's 28-column template, header fields on the first line
of each entry only and dates as M/D/YYYY. A negative net amount is moved to the other column.
An entry with no reversal_date reverses on the 1st of the month after the period. The rows are
then checked as je_import_check.py checks a file on disk.

STATE defaults to Posted: a person uploads the CSV, and that upload is the human review. Draft
is accepted for an entry created through the ERP's API, which a person then posts there.
Agents never upload or post.

Options: --out FILE writes the CSV; --period YYYY-MM (default: the file's period, else the
first entry's posting month); --state; --liability-account ACCOUNT turns on the one offset per
entity check; --format text|json. Prints a summary (or JSON without the rows).
Exit 0 when every check passes, 1 when any fails, 2 on bad input.

Example:
    python3 je_import.py proposals.json --out "August accrual.csv" --liability-account 2100
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from _common import COLUMNS, check_rows, entries, first_of_next_month, intacct_date, print_findings


def build_rows(proposals: list, default_reverse: str, state: str = "Posted") -> list:
    """One CSV row per line, the header fields on the first line of each entry."""
    rows = []
    for proposal in proposals:
        reverse = proposal.get("reversal_date") or default_reverse
        for index, line in enumerate(proposal.get("lines") or [], start=1):
            first = index == 1
            net = round(float(line.get("debit") or 0.0) - float(line.get("credit") or 0.0), 2)
            debit, credit = (net, 0.0) if net >= 0 else (0.0, -net)
            rows.append({
                "JOURNAL": proposal.get("journal", "GJ") if first else "",
                "DATE": intacct_date(proposal.get("posting_date", "")) if first else "",
                "REVERSEDATE": intacct_date(reverse) if first else "",
                "DESCRIPTION": proposal.get("description", "") if first else "",
                "LINE_NO": index,
                "ACCT_NO": str(line.get("account") or ""),
                "LOCATION_ID": str(line.get("location") or ""),
                "DEPT_ID": str(line.get("department") or ""),
                "MEMO": str(line.get("memo") or ""),
                "DEBIT": f"{debit:.2f}" if debit else "",
                "CREDIT": f"{credit:.2f}" if credit else "",
                "STATE": state if first else "",
            })
    return rows


def write_csv(path: Path, rows: list) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore", restval="")
        writer.writeheader()
        writer.writerows(rows)
    return path


def build(proposals: list, period: str = "", state: str = "Posted", liability_account: str = "",
          out: str = "") -> dict:
    if not period:
        period = str((proposals[0] if proposals else {}).get("posting_date") or "")[:7]
    if len(period) != 7 or period[4] != "-":
        raise ValueError("period is required (pass --period or put posting_date on an entry)")
    reverse = first_of_next_month(period)
    rows = build_rows(proposals, reverse, state)
    findings = check_rows(rows, liability_account, state)
    debits = round(sum(float(r["DEBIT"]) for r in rows if r["DEBIT"]), 2)
    credits = round(sum(float(r["CREDIT"]) for r in rows if r["CREDIT"]), 2)
    count = len(entries(rows))
    result = {
        "period": period, "state": state, "reverse_date": reverse,
        "je_count": count, "line_count": len(rows),
        "total_debits": debits, "total_credits": credits, "columns": COLUMNS, "rows": rows,
        "findings": findings, "errors": len(findings), "passed": not findings,
        "summary": (f"{period}: {count} JE(s), {len(rows)} line(s), ${debits:,.2f} debits; "
                    f"STATE={state}, REVERSEDATE={reverse}, Intacct GL template layout"),
    }
    if out:
        result["csv_path"] = str(write_csv(Path(out).expanduser(), rows))
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=__doc__.split("\n\n", 1)[1])
    parser.add_argument("proposals_json")
    parser.add_argument("--out", default="", help="write the import CSV here")
    parser.add_argument("--period", default="", help="accounting period YYYY-MM")
    parser.add_argument("--state", default="Posted", help="STATE column value (default Posted)")
    parser.add_argument("--liability-account", default="",
                        help="accrued-liability account; turns on the one offset per entity check")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    try:
        payload = json.loads(Path(args.proposals_json).read_text())
        if isinstance(payload, dict):
            if "proposals" not in payload:
                raise ValueError("the file has no \"proposals\" list; nothing would be imported")
            proposals, period = payload["proposals"], args.period or payload.get("period", "")
        else:
            proposals, period = payload, args.period
        result = build(list(proposals), period, args.state, args.liability_account, args.out)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"je_import: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=1))
    else:
        print(result["summary"])
        if result.get("csv_path"):
            print(f"  wrote {result['csv_path']}")
        print_findings(result["findings"])
        print("PASS" if result["passed"] else "FAIL")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
