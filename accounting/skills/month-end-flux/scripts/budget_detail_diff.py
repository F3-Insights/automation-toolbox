#!/usr/bin/env python3
"""Compare the budget detail Sage Intacct holds with the budget upload sheet, and find the
freshest forecast.

    python3 budget_detail_diff.py --detail budget-detail.json --list-budgets
    python3 budget_detail_diff.py --detail budget-detail.json --upload "forecast upload.csv" [--budget-id ID]

--detail is a pull of Intacct's budget detail (rows with budget.id, glAccount.id,
dimensions.department.id, dimensions.location.id, reportingPeriod.id such as
"Month Ended March 2026", and amount).

Freshest forecast: budget ids are usually dated (FORECAST-2026-03, FORECAST-2026-02, BUDGET).
Among the ids starting with --prefix, the one with the highest embedded YYYY-MM wins, and an
undated id never beats a dated one. Without --budget-id the diff uses that pick and says so.

The diff: --upload is the Sage budget-upload layout, key columns ACCT_NO, DEPT_ID, LOCATION_ID
plus one column per "Month Ended <Month> <Year>". Each cell is matched to the detail at the same
account, department, location and month. Findings: amount_differs (error), missing_in_intacct
(error, the upload did not land), extra_in_intacct (warning, often a stale row from an earlier
upload) and period_unparseable (warning, a month column that cannot be read).

Prints a summary and the findings, or JSON. Exit 1 on any error finding, 2 on unusable input.
"""

import argparse
import json
import re
import sys
from collections import defaultdict

from _common import load_pull, load_table, money, reporting_period_month

DATED = re.compile(r"(\d{4})[-_]?(\d{2})")


def budget_periods(rows):
    """{budget id: {rows, periods, first, last}}."""
    out = {}
    for row in rows:
        bid = str(row.get("budget.id") or "")
        if not bid:
            continue
        entry = out.setdefault(bid, {"rows": 0, "periods": set()})
        entry["rows"] += 1
        month = reporting_period_month(row.get("reportingPeriod.id"))
        if month:
            entry["periods"].add(month)
    for entry in out.values():
        months = sorted(entry.pop("periods"))
        entry.update(periods=months, first=months[0] if months else "", last=months[-1] if months else "")
    return out


def freshest_forecast(budget_ids, prefix="FORECAST"):
    """The dated id with the highest YYYY-MM among those starting with prefix."""
    matching = [str(b) for b in budget_ids if not prefix or str(b).upper().startswith(prefix.upper())]
    dated = [(f"{m.group(1)}-{m.group(2)}", b) for b in matching for m in [DATED.search(b)] if m]
    if dated:
        return max(dated)[1]
    return sorted(matching)[-1] if matching else ""


def index_detail(rows, budget_id):
    """{(account, department, location, month): amount} for one budget id."""
    index = defaultdict(float)
    for row in rows:
        month = reporting_period_month(row.get("reportingPeriod.id"))
        if str(row.get("budget.id") or "") != budget_id or not month:
            continue
        key = (str(row.get("glAccount.id") or ""), str(row.get("dimensions.department.id") or ""),
               str(row.get("dimensions.location.id") or ""), month)
        index[key] += money(row.get("amount"))
    return {k: round(v, 2) for k, v in index.items()}


def index_upload(rows):
    """{(account, department, location, month): amount} from the upload sheet, plus findings."""
    if not rows:
        raise ValueError("the upload sheet is empty")
    findings, columns = [], {}
    for column in rows[0]:
        if str(column).startswith("Month Ended"):
            month = reporting_period_month(column)
            if month:
                columns[column] = month
            else:
                findings.append({"check": "period_unparseable", "severity": "warning", "key": column,
                                 "detail": f"column {column!r} is not a parseable period"})
    if not columns:
        raise ValueError("no 'Month Ended <Month> <Year>' columns found in the upload sheet")
    index = defaultdict(float)
    for row in rows:
        for column, month in columns.items():
            key = (str(row.get("ACCT_NO") or "").strip(), str(row.get("DEPT_ID") or "").strip(),
                   str(row.get("LOCATION_ID") or "").strip(), month)
            index[key] += money(row.get(column))
    return {k: round(v, 2) for k, v in index.items()}, findings


def diff(detail, upload, tolerance=0.005):
    findings = []
    for key in sorted(set(detail) | set(upload)):
        account, dept, location, month = key
        where = f"{account}/{dept or '-'}/{location or '-'} {month}"
        theirs, ours = detail.get(key), upload.get(key)
        if theirs is None and ours:
            findings.append({"check": "missing_in_intacct", "severity": "error", "key": where,
                             "detail": f"the sheet has ${ours:,.2f}; Intacct has no such row",
                             "upload": ours, "intacct": None})
        elif ours is None and theirs:
            findings.append({"check": "extra_in_intacct", "severity": "warning", "key": where,
                             "detail": f"Intacct has ${theirs:,.2f}; the sheet has no such row",
                             "upload": None, "intacct": theirs})
        elif theirs is not None and ours is not None and abs(round(ours - theirs, 2)) > tolerance:
            delta = round(ours - theirs, 2)
            findings.append({"check": "amount_differs", "severity": "error", "key": where,
                             "detail": f"sheet ${ours:,.2f} vs Intacct ${theirs:,.2f} (difference ${delta:,.2f})",
                             "upload": ours, "intacct": theirs})
    return findings


def compare(detail_rows, upload_rows=None, budget_id="", prefix="FORECAST", tolerance=0.005):
    budgets = budget_periods(detail_rows)
    freshest = freshest_forecast(list(budgets), prefix)
    result = {"budgets": dict(sorted(budgets.items())), "freshest_forecast": freshest,
              "budget_id": budget_id or freshest, "findings": [], "errors": 0, "passed": True}
    if upload_rows is None:
        result["summary"] = f"{len(budgets)} budget id(s); freshest forecast: {freshest or '(none)'}"
        return result
    chosen = result["budget_id"]
    if not chosen:
        raise ValueError("no budget id to diff against: pass --budget-id")
    if chosen not in budgets:
        raise ValueError(f"budget id {chosen!r} is not in the detail pull (has: {', '.join(sorted(budgets)) or 'none'})")
    upload, findings = index_upload(upload_rows)
    findings += diff(index_detail(detail_rows, chosen), upload, tolerance)
    errors = sum(1 for f in findings if f["severity"] == "error")
    result.update(findings=findings, errors=errors, passed=errors == 0, cells=len(upload),
                  summary=f"{chosen}: {len(upload):,} upload cell(s), {len(findings)} finding(s), {errors} error(s)")
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description="Diff Intacct's budget detail against the upload sheet. Exit 1 on any error.")
    p.add_argument("--detail", required=True, help="Intacct budget-detail pull (JSON)")
    p.add_argument("--upload", default="", help="budget upload sheet (CSV in the Sage layout)")
    p.add_argument("--budget-id", default="", help="budget id to diff against (default: the freshest forecast)")
    p.add_argument("--prefix", default="FORECAST", help="budget-id prefix the freshest-forecast finder considers")
    p.add_argument("--tolerance", type=float, default=0.005, help="dollars of difference tolerated per cell")
    p.add_argument("--list-budgets", action="store_true", help="list every budget id with its rows and period range")
    p.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)
    upload = "" if a.list_budgets else a.upload
    try:
        result = compare(load_pull(a.detail), load_table(upload) if upload else None,
                         a.budget_id, a.prefix, a.tolerance)
    except (OSError, ValueError) as exc:
        print(f"budget-detail-diff: {exc}", file=sys.stderr)
        return 2
    if a.format == "json":
        print(json.dumps(result, indent=1))
    else:
        print(result["summary"])
        if not upload:
            for bid, meta in result["budgets"].items():
                mark = " <- freshest" if bid == result["freshest_forecast"] else ""
                print(f"  {bid:24} {meta['rows']:>6,} rows  {meta['first']}..{meta['last']}{mark}")
        for f in result["findings"]:
            print(f"  {f['severity'].upper():7} {f['check']:20} {f['key']:32} {f['detail']}")
        if upload:
            print("PASS" if result["passed"] else f"FAIL: {result['errors']} error(s)")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
