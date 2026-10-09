#!/usr/bin/env python3
# /// script
# dependencies = ["openpyxl"]
# ///
"""A trial balance as of a date, computed from posted GL lines.

Intacct's API offers a read-only user no trial-balance object, so the balance is built the
way the ledger builds it: every posted line since inception, debits positive, summed per
account. The lines come from three pulls that must not overlap, checked at run time:

  --history   the historical journal export, from inception to its last date
  --bridge    a wider pull, used only for dates after the history and before --current
  --current   this close's pull; its window replaces the bridge (--current-from names where
              that window starts; default its earliest line)

--accounts is the chart of accounts: rows with id, name, accountType (balanceSheet or
incomeStatement) and normalBalance (debit or credit). Lines may be in the standard ledger
shape or Intacct's dotted shape.

Balance-sheet accounts carry their cumulative balance, income-statement accounts their
fiscal-year-to-date activity, and prior years' net income lands on one computed RE-PRIOR line
so the statement foots. Two checks: all lines net to zero, and debits equal credits.

--by-dimensions adds account x department x location x class sheets, a monthly sheet and a CSV
in the budget-upload layout (normal-balance sign: a credit account is positive when in
credit).

Prints a summary line, or the result as JSON with --format json. --out writes the workbook
(it needs openpyxl), also alongside --format json. Exit 0 when it balances, 1 when it does not,
2 on a bad input.

Example:
    python3 trial_balance.py --as-of 2026-07-31 --history hist.json --bridge bridge.json \\
        --current lines-2026-07.json --accounts accounts.json --out "TB July 2026.xlsx"
"""

from __future__ import annotations

import argparse
import calendar
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from _common import ln, load_snapshot, signed


def select_windows(history, bridge, current, as_of, current_from=""):
    """Stitch the three pulls into one posted-only list with no date in two pulls."""
    if not current:
        raise ValueError("the current pull is empty; nothing to build a balance from")
    if not history:
        raise ValueError("the history pull is empty; the balance would start mid-life")
    cur_dates = [ln(x, "date") for x in current]
    cur_lo, cur_hi = min(cur_dates), max(cur_dates)
    hist_hi = max(ln(x, "date") for x in history)
    if current_from:
        if cur_lo < current_from:
            raise ValueError(f"the current pull has lines dated {cur_lo}, before its window start {current_from}")
        if hist_hi >= current_from:
            raise ValueError(f"the history runs to {hist_hi}, inside the current window from {current_from}")
        cur_lo = current_from
    bridge_used = [x for x in bridge if hist_hi < ln(x, "date") < cur_lo]
    lines = [x for x in list(history) + bridge_used + [c for c in current if ln(c, "date") <= cur_hi]
             if ln(x, "date") <= as_of and (ln(x, "state") or "posted").lower() == "posted"]
    windows = {"history_through": hist_hi, "bridge_window": f"{hist_hi} < date < {cur_lo}",
               "bridge_used": len(bridge_used), "current_window": f"{cur_lo}..{cur_hi}",
               "history_lines": len(history), "bridge_lines": len(bridge), "current_lines": len(current)}
    return lines, windows


def tb_row(account, name, kind, normal, opening, ytd):
    end = round(opening + ytd, 2)
    return {"Account": account, "Name": name, "Type": kind, "Normal": normal,
            "Opening (FY)": round(opening, 2), "YTD activity": round(ytd, 2), "Ending balance": end,
            "Debit": end if end > 0 else 0.0, "Credit": -end if end < 0 else 0.0}


def build(lines, accounts, as_of, fy_start):
    """The consolidated balance, the by-entity (location) breakdown and the two checks."""
    opening, ytd = defaultdict(float), defaultdict(float)
    by_entity = defaultdict(lambda: defaultdict(float))
    for x in lines:
        account, amount = ln(x, "account"), signed(x)
        (opening if ln(x, "date") < fy_start else ytd)[account] += amount
        by_entity[account][ln(x, "location") or "?"] += amount
    prior_pl, rows = 0.0, []
    for account in sorted(set(opening) | set(ytd)):
        meta = accounts.get(account, {})
        kind = meta.get("accountType", "?")
        open_bal = opening[account]
        if kind == "incomeStatement":  # last year's profit belongs in retained earnings
            prior_pl += open_bal
            open_bal = 0.0
        if abs(open_bal + ytd[account]) < 0.005 and abs(ytd[account]) < 0.005:
            continue
        rows.append(tb_row(account, meta.get("name", ""), kind, meta.get("normalBalance", ""), open_bal, ytd[account]))
    re_prior = round(prior_pl, 2)
    rows.append(tb_row("RE-PRIOR", "Net income of prior years (computed, not an account)", "computed", "credit",
                       re_prior, 0.0))
    debits, credits = round(sum(r["Debit"] for r in rows), 2), round(sum(r["Credit"] for r in rows), 2)
    net = round(sum(signed(x) for x in lines), 2)
    return {
        "as_of": as_of, "fiscal_year_start": fy_start, "rows": rows,
        "by_entity": {a: dict(m) for a, m in by_entity.items()},
        "entities": sorted({e for m in by_entity.values() for e in m}),
        "debits": debits, "credits": credits,
        "ytd_net_income": round(-sum(v for a, v in ytd.items()
                                     if accounts.get(a, {}).get("accountType") == "incomeStatement"), 2),
        "all_lines_net": net, "re_prior": re_prior, "lines": len(lines),
        "balanced": abs(debits - credits) < 0.005 and abs(net) < 0.005,
    }


def dimension_rows(lines, accounts, as_of, fy_start):
    """Balances at the account x department x location x class grain, and the monthly block in
    the budget-upload layout (normal-balance sign)."""
    opening, ytd = defaultdict(float), defaultdict(float)
    monthly = defaultdict(lambda: defaultdict(float))
    for x in lines:
        key = (ln(x, "account"), ln(x, "department"), ln(x, "location"), ln(x, "class"))
        if ln(x, "date") < fy_start:
            opening[key] += signed(x)
        else:
            ytd[key] += signed(x)
            monthly[key][ln(x, "date")[:7]] += signed(x)
    prior_by_loc, balances = defaultdict(float), []
    for key in sorted(set(opening) | set(ytd)):
        account, dept, loc, cls = key
        meta = accounts.get(account, {})
        kind, open_bal = meta.get("accountType", "?"), opening[key]
        if kind == "incomeStatement":
            prior_by_loc[loc] += open_bal
            open_bal = 0.0
        if abs(open_bal + ytd[key]) < 0.005 and abs(ytd[key]) < 0.005:
            continue
        row = tb_row(account, meta.get("name", ""), kind, "", open_bal, ytd[key])
        balances.append({"ACCT_NO": account, "Account name": row["Name"], "Type": kind, "DEPT_ID": dept,
                         "LOCATION_ID": loc, "CLASSID": cls,
                         **{k: row[k] for k in ("Opening (FY)", "YTD activity", "Ending balance", "Debit", "Credit")}})
    for loc, value in sorted(prior_by_loc.items()):
        if abs(round(value, 2)) < 0.005:
            continue
        row = tb_row("RE-PRIOR", "", "computed", "", value, 0.0)
        balances.append({"ACCT_NO": "RE-PRIOR", "Account name": "Net income of prior years (computed, not an account)",
                         "Type": "computed", "DEPT_ID": "", "LOCATION_ID": loc, "CLASSID": "",
                         **{k: row[k] for k in ("Opening (FY)", "YTD activity", "Ending balance", "Debit", "Credit")}})
    year = as_of[:4]
    months = [f"{year}-{m:02d}" for m in range(1, int(as_of[5:7]) + 1)]
    columns = (["ACCT_NO", "DEPT_ID", "LOCATION_ID", "CUSTOMERID", "VENDORID", "ITEMID", "CLASSID", "EMPLOYEEID"]
               + [f"Month Ended {calendar.month_name[int(m[5:])]} {year}" for m in months])
    upload = []
    for key in sorted(monthly):
        account, dept, loc, cls = key
        sign = -1.0 if accounts.get(account, {}).get("normalBalance") == "credit" else 1.0
        values = [round(sign * monthly[key].get(m, 0.0), 2) or 0.0 for m in months]
        if any(abs(v) >= 0.005 for v in values):
            upload.append([account, dept, loc, "", "", "", cls, ""] + values)
    return {"balances": balances, "upload_columns": columns, "upload_rows": upload, "months": months}


def write_workbook(result, accounts, out, label, dimensions=None):
    """The trial balance workbook, plus the upload CSV beside it when dimensions are given."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    bold = Font(bold=True)
    book = Workbook()
    ws = book.active
    ws.title = "Trial Balance"
    ws.append([f"Trial Balance as of {result['as_of']} - {label}"])
    ws["A1"].font = Font(bold=True, size=12)
    ws.append([f"Computed from posted GL lines; pulled {result.get('pulled_at', '')[:19]} UTC; "
               f"debits {result['debits']:,.2f} = credits {result['credits']:,.2f}; "
               f"YTD net income {result['ytd_net_income']:,.2f}"])
    ws.append([])
    header = list(result["rows"][0])
    ws.append(header)
    for cell in ws[4]:
        cell.font = bold
    for row in result["rows"]:
        ws.append([row[h] for h in header])
    ws.append([])
    ws.append(["", "TOTAL", "", "", "", "", "", result["debits"], result["credits"]])
    for col, width in zip("ABCDEFGHI", (11, 46, 16, 8, 16, 16, 16, 16, 16)):
        ws.column_dimensions[col].width = width
    for row in ws.iter_rows(min_row=5, min_col=5, max_col=9):
        for cell in row:
            cell.number_format = "#,##0.00;(#,##0.00);-"

    ws2 = book.create_sheet("By entity")
    entities = result["entities"]
    ws2.append(["Account", "Name"] + [f"Entity {e}" for e in entities] + ["Total"])
    for cell in ws2[1]:
        cell.font = bold
    for account in sorted(result["by_entity"]):
        values = [round(result["by_entity"][account].get(e, 0.0), 2) for e in entities]
        if any(abs(v) >= 0.005 for v in values):
            ws2.append([account, accounts.get(account, {}).get("name", "")] + values + [round(sum(values), 2)])
    ws2.append(["", "Entity check (should be 0.00)"]
               + [round(sum(m.get(e, 0.0) for m in result["by_entity"].values()), 2) for e in entities]
               + [result["all_lines_net"]])
    ws2.column_dimensions["B"].width = 46

    written = [out]
    if dimensions:
        ws3 = book.create_sheet("TB by dimension")
        ws3.append([f"Trial balance by account x department x location x class, as of {result['as_of']} - {label}"])
        ws3["A1"].font = bold
        head = list(dimensions["balances"][0]) if dimensions["balances"] else []
        ws3.append(head)
        for cell in ws3[2]:
            cell.font = bold
        for row in dimensions["balances"]:
            ws3.append([row[h] for h in head])
        ws4 = book.create_sheet(f"Monthly {result['as_of'][:4]} (upload layout)")
        ws4.append(dimensions["upload_columns"])
        for cell in ws4[1]:
            cell.font = bold
        for row in dimensions["upload_rows"]:
            ws4.append(row)
        csv_path = Path(out).with_suffix("").as_posix() + " - monthly upload layout.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(dimensions["upload_columns"])
            writer.writerows(dimensions["upload_rows"])
        written.append(csv_path)

    ws5 = book.create_sheet("Run metadata")
    for key, value in [
        ("As of", result["as_of"]), ("Label", label), ("Fiscal year start", result["fiscal_year_start"]),
        ("Generated", datetime.now(timezone.utc).isoformat(timespec="seconds")),
        ("Lines in the balance", f"{result['lines']:,} posted lines dated <= {result['as_of']}"),
        ("Check: all lines net to zero", f"{result['all_lines_net']:,.2f}"),
        ("Check: debits = credits", f"{result['debits']:,.2f} vs {result['credits']:,.2f}"),
        ("Computed line", f"RE-PRIOR = net income of years before {result['fiscal_year_start'][:4]}: "
                          f"{result['re_prior']:,.2f}"),
        ("Not included", "Draft or submitted entries (posted only)"),
    ]:
        ws5.append([key, value])
    ws5.column_dimensions["A"].width = 30
    ws5.column_dimensions["B"].width = 140
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    book.save(out)
    return written


def trial_balance(as_of, history, bridge, current, accounts, fiscal_year_start="", by_dimensions=False,
                  current_from=""):
    """Load the pulls and build the balance. Returns (result, account map)."""
    fy_start = fiscal_year_start or f"{as_of[:4]}-01-01"
    account_map = {str(a["id"]): a for a in load_snapshot(accounts)[0]}
    current_rows, cur_meta = load_snapshot(current)
    lines, windows = select_windows(load_snapshot(history)[0], load_snapshot(bridge)[0], current_rows,
                                    as_of, current_from)
    result = build(lines, account_map, as_of, fy_start)
    result["windows"] = windows
    result["pulled_at"] = str(cur_meta.get("pulled-at") or cur_meta.get("pulled_at") or "")
    if by_dimensions:
        result["dimensions"] = dimension_rows(lines, account_map, as_of, fy_start)
    return result, account_map


def main(argv=None):
    p = argparse.ArgumentParser(description="Trial balance as of a date, from posted GL lines.")
    p.add_argument("--as-of", required=True, help="balance date, yyyy-mm-dd")
    p.add_argument("--label", default="", help="label for the workbook header")
    for name in ("history", "bridge", "current", "accounts"):
        p.add_argument(f"--{name}", required=True)
    p.add_argument("--out", default="", help="write the .xlsx here")
    p.add_argument("--fiscal-year-start", default="", help="yyyy-mm-dd; default 1 January of the as-of year")
    p.add_argument("--current-from", default="", help="yyyy-mm-dd the current pull's query started")
    p.add_argument("--by-dimensions", action="store_true", help="add the dimension sheets and the upload CSV")
    p.add_argument("--format", default="text", choices=["text", "json", "xlsx"])
    args = p.parse_args(argv)
    try:
        if args.format == "xlsx" and not args.out:
            raise ValueError("--out is required when writing a workbook")
        result, account_map = trial_balance(args.as_of, args.history, args.bridge, args.current, args.accounts,
                                            args.fiscal_year_start, args.by_dimensions, args.current_from)
        if args.out:
            result["written"] = write_workbook(result, account_map, args.out, args.label or args.as_of,
                                               result.get("dimensions"))
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps({k: v for k, v in result.items() if k != "dimensions"}, indent=1, default=str))
    else:
        print(f"{args.as_of}: {len(result['rows'])} lines; debits {result['debits']:,.2f} "
              f"credits {result['credits']:,.2f}; all-lines net {result['all_lines_net']:,.2f}; "
              f"YTD NI {result['ytd_net_income']:,.2f}; {result['lines']:,} posted lines")
        for path in result.get("written", []):
            print(f"  wrote {path}")
        print("PASS" if result["balanced"] else "FAIL: the balance does not foot")
    return 0 if result["balanced"] else 1


if __name__ == "__main__":
    sys.exit(main())
