#!/usr/bin/env python3
"""Draft the post-cutoff vendor accrual: next month's AP bills that belong to the closing
period, plus estimates for arrears vendors who have not billed yet.

A bill posted after month-end belongs to the month when:
- its memo names the month ("AUGUST 2026", "Aug 2026", "2026-08", "8/2026" and the other ways
  a person writes it); a bill that names the period on any line counts in full; or
- its vendor bills in arrears (--arrears-vendor, matched inside the vendor name), so next
  month's bill is this month's service, unless the bill names some other month.

An arrears vendor with no bill for the period at all is accrued at the median of its last
three bills, allocated across accounts and departments the way its latest bill was, and the
memo says ESTIMATE so nobody mistakes it for an invoice.

Only expense accounts count (--expense-prefix, default 5 to 9). --exclude-vendor drops a vendor
accrued elsewhere, --exclude-bill a bill id already accrued. The proposal is one reversing entry
dated month-end: one debit per vendor x account x department x location, and one liability
credit per location, so each entity balances on its own.

Inputs: --next-bills, the AP bill lines posted after the period, and --bills, the bill lines
within and before it for the estimates (a ledger pull, {"meta", "rows"} or a bare list, in
the standard or the Sage Intacct shape). --out writes the result JSON, which je_import.py reads.
Prints a summary, or with --format json: proposals, bills, total, estimates, counts, passed,
summary. Exit 0 when no estimate was needed, 1 when any line is an estimate (check it before
the file is uploaded), 2 on bad input.

Example:
    python3 service_period_accrual.py --period 2026-08 --next-bills ap-bills-2026-09.json \\
        --bills ap-bills-trailing.json --liability-account 2100 --location 100 \\
        --arrears-vendor "FABRIKAM LOGISTICS"
"""

from __future__ import annotations

import argparse
import calendar
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

from _common import field, first_of_next_month, load_snapshot, money, period_end, period_tokens, shift_period

DEFAULT_EXPENSE_PREFIXES = ("5", "6", "7", "8", "9")


def doc(row: dict, name: str) -> str:
    return field(row, name, "doc")


def other_month_pattern(period: str, span: int = 12):
    """A regex for a memo naming a month other than the period, with its year.

    Only year-qualified forms count ("AUG 2026", "Aug-26", "2026-08", "8/2026"), each standing
    alone, so "11/2026" never reads as January and "MARKETING" never reads as March.
    """
    forms = []
    for offset in range(-span, span + 1):
        if offset == 0:
            continue
        other = shift_period(period, offset)
        year, month = (int(x) for x in other.split("-"))
        name, abbr, yy = calendar.month_name[month].upper(), calendar.month_abbr[month].upper(), f"{year % 100:02d}"
        forms += [f"{name} {year}", f"{abbr} {year}", f"{name} {yy}", f"{abbr} {yy}", f"{abbr}-{yy}",
                  f"{abbr}'{yy}", other, f"{month:02d}/{year}", f"{month}/{year}"]
    return re.compile(r"(?<![0-9A-Z])(?:" + "|".join(re.escape(f) for f in forms) + r")(?![0-9A-Z])")


def bill_line(row: dict, default_department: str, location: str, **extra) -> dict:
    return {"bill_id": doc(row, "doc_id"), "posting_date": doc(row, "posting_date"),
            "vendor": doc(row, "counterparty").strip(), "account": doc(row, "account"),
            "account_name": doc(row, "account_name"),
            "department": (doc(row, "department") or default_department).upper(),
            "location": doc(row, "location") or location,
            "amount": round(money(doc(row, "amount")), 2), "memo": doc(row, "memo"), **extra}


def bills_for_period(rows, period, arrears, excluded_vendors, excluded_bills, default_department,
                     location, expense_prefixes) -> list:
    """Next-month bill lines whose memo names the period, or whose vendor bills in arrears."""
    tokens, other = period_tokens(period), other_month_pattern(period)
    memos = defaultdict(list)
    for row in rows:
        memos[doc(row, "doc_id")].append(doc(row, "memo").upper())
    names_period = {b for b, ms in memos.items() if any(t in m for m in ms for t in tokens)}
    names_other = {b for b, ms in memos.items() if any(other.search(m) for m in ms)}
    found = []
    for row in rows:
        vendor, bill_id = doc(row, "counterparty").strip().upper(), doc(row, "doc_id")
        if not doc(row, "account").startswith(expense_prefixes):
            continue
        if any(x and x in vendor for x in excluded_vendors) or bill_id in excluded_bills:
            continue
        if any(t in doc(row, "memo").upper() for t in tokens):
            reason = "memo names the month"
        elif any(a and a in vendor for a in arrears):
            if bill_id in names_other and bill_id not in names_period:
                continue  # the bill names another month, so it is that month's service
            reason = "arrears vendor (bills month M in M+1)"
        else:
            continue
        found.append(bill_line(row, default_department, location, reason=reason))
    return found


def estimates_for_unbilled(all_rows, period, arrears, found, excluded_bills, default_department,
                           location, expense_prefixes) -> list:
    """One estimated line set per arrears vendor with no bill for the period yet: the median of
    its last three bills, allocated like the latest bill."""
    tokens, out = period_tokens(period), []
    covered = {b["vendor"].upper() for b in found}
    for key in arrears:
        if not key or any(key in v for v in covered):
            continue
        mine = [r for r in all_rows
                if key in doc(r, "counterparty").upper() and doc(r, "account").startswith(expense_prefixes)]
        if not mine or any(doc(r, "doc_id") in excluded_bills for r in mine):
            continue
        if any(doc(r, "posting_date")[:7] == period and any(t in doc(r, "memo").upper() for t in tokens)
               for r in mine):
            continue  # already billed for the period
        by_bill = defaultdict(list)
        for row in mine:
            by_bill[doc(row, "doc_id")].append(row)
        recent = sorted(by_bill.items(), key=lambda kv: max(doc(r, "posting_date") for r in kv[1]))[-3:]
        totals = [sum(money(doc(r, "amount")) for r in lines) for _, lines in recent]
        estimate = round(median(totals), 2)
        if estimate <= 0:
            continue
        latest_id, latest_lines = recent[-1]
        latest_total = sum(money(doc(r, "amount")) for r in latest_lines) or estimate
        vendor = doc(latest_lines[0], "counterparty") or key
        for row in latest_lines:
            line = bill_line(row, default_department, location)
            line.update(
                bill_id=f"est:{latest_id}", posting_date="", vendor=vendor,
                amount=round(estimate * (money(doc(row, "amount")) / latest_total), 2),
                memo=(f"estimate: median of last {len(totals)} bills ({', '.join(f'{t:,.0f}' for t in totals)}), "
                      f"allocated like bill {latest_id} ({doc(row, 'memo')[:30]})"),
                reason="estimate (arrears vendor, unbilled at close)")
            out.append(line)
    return out


def build(next_rows: list, all_rows: list, period: str, liability_account: str, location: str = "",
          default_department: str = "GENERAL", arrears_vendors=(), exclude_vendors=(), exclude_bills=(),
          journal: str = "GJ", expense_prefixes: tuple = DEFAULT_EXPENSE_PREFIXES, pass_label: str = "",
          liability_name: str = "Accrued Expenses", description: str = "") -> dict:
    if not liability_account:
        raise ValueError("--liability-account is required: the accrual needs somewhere to credit")
    arrears = [str(v).upper() for v in arrears_vendors]
    excluded_vendors = {str(v).upper() for v in exclude_vendors}
    excluded_bills = {str(b) for b in exclude_bills}
    default_department = str(default_department).upper()
    bills = bills_for_period(next_rows, period, arrears, excluded_vendors, excluded_bills,
                             default_department, location, expense_prefixes)
    bills += estimates_for_unbilled(all_rows, period, arrears, bills, excluded_bills,
                                    default_department, location, expense_prefixes)

    estimated = {b["vendor"] for b in bills if b["reason"].startswith("estimate")}
    grouped, names = defaultdict(float), {}
    for bill in bills:
        grouped[(bill["vendor"], bill["account"], bill["department"], bill["location"])] += bill["amount"]
        names[bill["account"]] = bill["account_name"]
    lines = []
    for (vendor, account, department, loc), amount in sorted(grouped.items(), key=lambda kv: -kv[1]):
        if round(amount, 2) <= 0:
            continue
        memo = f"ACCRUED {vendor} - {names.get(account, '')} {period}" + (
            " (ESTIMATE, unbilled)" if vendor in estimated else "")
        lines.append({"account": account, "account_name": names.get(account, ""), "department": department,
                      "location": loc, "debit": round(amount, 2), "credit": 0.0, "memo": memo.strip(),
                      "vendor": vendor, "category": "", "naming": "vendor", "max_merchant": round(amount, 2)})
    total = round(sum(line["debit"] for line in lines), 2)
    debit_lines = len(lines)

    proposals = []
    if lines:
        by_location = defaultdict(float)
        for line in lines:
            by_location[line["location"]] += line["debit"]
        for loc, amount in sorted(by_location.items()):
            lines.append({"account": liability_account, "account_name": liability_name,
                          "department": default_department, "location": loc, "debit": 0.0,
                          "credit": round(amount, 2), "memo": f"ACCRUED POST-CUTOFF VENDOR EXPENSES {period}",
                          "vendor": "", "category": "", "naming": "offset", "max_merchant": 0.0})
        year, month = (int(x) for x in period.split("-"))
        suffix = f" - pass {pass_label}" if pass_label else ""
        template = description or "To accrue {month} {year} expenses received after the AP cutoff"
        proposals.append({
            "je_id": f"POST-CUTOFF VENDOR ACCRUAL {period}{suffix.upper()}", "journal": journal,
            "description": template.format(month=calendar.month_name[month], year=year) + suffix,
            "posting_date": period_end(period), "reversal_date": first_of_next_month(period),
            "source": "service-period-accrual", "lines": lines,
        })

    counts = defaultdict(int)
    for bill in bills:
        counts[bill["reason"]] += 1
    return {
        "period": period, "proposals": proposals, "bills": bills, "total": total,
        "estimates": sorted(estimated), "counts": dict(counts), "passed": not estimated,
        "summary": (f"{period}: {len(bills)} next-month AP bill line(s) belong to the period "
                    f"({', '.join(f'{n} {r}' for r, n in counts.items()) or 'none'}); "
                    f"draft accrual ${total:,.2f} across {debit_lines} debit line(s)"),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=__doc__.split("\n\n", 1)[1])
    parser.add_argument("--period", required=True, help="accounting period YYYY-MM")
    parser.add_argument("--next-bills", required=True, help="AP bill lines posted after the period")
    parser.add_argument("--bills", default="", help="AP bill lines within the period, for the estimates")
    parser.add_argument("--liability-account", required=True, help="accrued-liability account the offsets credit")
    parser.add_argument("--liability-name", default="Accrued Expenses")
    parser.add_argument("--location", default="", help="LOCATION_ID when a bill line has none")
    parser.add_argument("--default-department", default="GENERAL")
    parser.add_argument("--arrears-vendor", action="append", default=[], help="vendor who bills month M in M+1; repeatable")
    parser.add_argument("--exclude-vendor", action="append", default=[], help="vendor accrued elsewhere; repeatable")
    parser.add_argument("--exclude-bill", action="append", default=[], help="bill id already accrued; repeatable")
    parser.add_argument("--expense-prefix", action="append", default=[], help="expense account prefix; repeatable")
    parser.add_argument("--journal", default="GJ")
    parser.add_argument("--pass-label", default="", help="suffix for a second pass in the same period")
    parser.add_argument("--description", default="", help="entry description; {month} and {year} are filled in")
    parser.add_argument("--out", default="", help="write the result JSON here (je_import.py reads it)")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    try:
        next_rows = load_snapshot(args.next_bills)
        all_rows = (load_snapshot(args.bills) if args.bills else []) + next_rows
        result = build(next_rows, all_rows, args.period, args.liability_account, args.location,
                       args.default_department, args.arrears_vendor, args.exclude_vendor, args.exclude_bill,
                       args.journal, tuple(args.expense_prefix) or DEFAULT_EXPENSE_PREFIXES, args.pass_label,
                       args.liability_name, args.description)
        if args.out:
            out = Path(args.out).expanduser()
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, indent=1))
    except (OSError, ValueError, KeyError) as exc:
        print(f"service_period_accrual: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(result, indent=1))
    else:
        print(result["summary"])
        for proposal in result["proposals"]:
            for line in proposal["lines"]:
                print(f"  {line['account']:8} {line['department']:10} {line['location']:4} "
                      f"{line['debit'] or -line['credit']:>14,.2f}  {line['memo'][:60]}")
        if args.out:
            print(f"  wrote {args.out}")
        print("PASS" if result["passed"] else f"FAIL: estimated {', '.join(result['estimates'])}; confirm before upload")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
