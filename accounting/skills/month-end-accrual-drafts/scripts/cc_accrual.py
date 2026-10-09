#!/usr/bin/env python3
# /// script
# dependencies = ["pyyaml"]
# ///
"""Turn a month of credit-card transactions into a coded, reversing accrual journal entry,
with queues of what could not be coded instead of a guess.

Each transaction is coded by two maps the owner keeps: the MCC map (merchant category code to
category and account) and the people map (cardholder to department). Rows are grouped into
department x category buckets; any merchant at or above --vendor-name-floor, and every merchant
in an --always-vendor-named category, gets its own vendor-named line. One credit on the
liability account balances the entry, dated month-end and reversing on the 1st of next month.

The account depends on the department as well as the category: an MCC entry gives a flat
"account", or an "account_by_department" block keyed by department, by department family
(the MCC file's "department_families"), and "default"; the most specific wins. The MCC file
may also hold "merchant_overrides", a list of {pattern, account, category?, account_name?,
account_by_department?} checked before the MCC map; a pattern with * or ? is a glob over the
merchant name, otherwise it matches when the name contains it, ignoring case.

Departments: when the card file has a department column (dept_export) or --dept-labels is
given, the column drives each row's department through the label map (label to department
id). The people map is then only a fallback for a blank or unknown label, which is reported.
Without a column the people map is the source. department_reconciliation says, per
cardholder, where the column and the people map disagree, every unknown label and blank.

Inputs: the card CSV (or JSON rows) from card_export.py, --period, --mcc-map, --people-map
(JSON, or YAML with pyyaml), --liability-account, --unmapped-account, and the optional
settings below. --out writes the full result JSON, which je_import.py reads.
Prints a summary, or with --format json the full result: proposals, unmapped_merchants,
unmapped_cardholders, department_reconciliation, merchant_overrides_used, rows (every row
traced to its department and account), total, ready, passed, summary.
Exit 0 when the draft is clean, 1 when a queue or department gap remains (the entry is still
written), 2 on bad input.

Example:
    python3 cc_accrual.py card-2026-08.csv --period 2026-08 --mcc-map mcc.json \\
        --people-map people.json --liability-account 2100 --unmapped-account 6990 \\
        --location 100 --out cc-accrual-2026-08.json
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

from _common import first_of_next_month, load_map, load_rows, money, month_of, period_end


def as_map(data) -> dict:
    """A bare mapping or {"map": {...}}; a scalar value is taken as the category."""
    if isinstance(data, dict) and isinstance(data.get("map"), dict):
        data = data["map"]
    if not isinstance(data, dict):
        raise ValueError("a map file must be a mapping of key -> coding")
    return {str(k): (v if isinstance(v, dict) else {"category": str(v)}) for k, v in data.items()}


def normalize_person(name: str) -> str:
    """'DANA M PRIYA' -> 'DANA PRIYA': upper case, apostrophes deleted, punctuation and
    single letters (middle initials) dropped, so the bank's string matches the map's key."""
    text = str(name or "").upper().replace("'", "").replace("’", "")
    text = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text)
    return " ".join(t for t in text.split() if len(t) > 1)


def lookup_person(people: dict, cardholder: str):
    """The exact key, then the normalized name, then first and last name only; else None."""
    if cardholder in people:
        return people[cardholder]
    wanted = normalize_person(cardholder)
    if not wanted:
        return None
    by_norm = {normalize_person(k): v for k, v in people.items()}
    if wanted in by_norm:
        return by_norm[wanted]
    parts = wanted.split()
    if len(parts) >= 2:
        for key, value in by_norm.items():
            kp = key.split()
            if len(kp) >= 2 and (kp[0], kp[-1]) == (parts[0], parts[-1]):
                return value
    return None


def label_key(label) -> str:
    """Case and extra spaces never matter in a department label."""
    return " ".join(str(label or "").split()).upper()


def as_labels(data) -> dict:
    """A label map {label: department id} (or {"map": ...}; a value may be {"department": id})."""
    if isinstance(data, dict) and isinstance(data.get("map"), dict):
        data = data["map"]
    if not isinstance(data, dict):
        raise ValueError("--dept-labels must be a mapping of label -> department id")
    out = {}
    for label, value in data.items():
        dept = value.get("department") if isinstance(value, dict) else value
        if label_key(label) and str(dept or "").strip():
            out[label_key(label)] = str(dept).strip().upper()
    return out


def check_overrides(data) -> list:
    out = []
    for entry in list(data or []):
        if not isinstance(entry, dict) or not str(entry.get("pattern") or "").strip():
            raise ValueError(f"a merchant override needs a pattern: {entry!r}")
        if not (entry.get("account") or entry.get("account_by_department")):
            raise ValueError(f"merchant override {entry['pattern']!r} has no account")
        out.append({**entry, "pattern": str(entry["pattern"]).strip()})
    return out


def match_override(overrides: list, merchant: str):
    name = merchant.upper()
    for entry in overrides:
        pattern = entry["pattern"].upper()
        if re.search(r"[*?\[]", pattern) and fnmatch.fnmatchcase(name, pattern):
            return entry
        if not re.search(r"[*?\[]", pattern) and pattern in name:
            return entry
    return None


def account_for(coding: dict, department: str, families: dict, fallback: str) -> tuple:
    """(account, account_name): the department's cell, its family's, "default", then the flat account."""
    matrix = coding.get("account_by_department")
    if isinstance(matrix, dict):
        for key in (department, families.get(department, ""), "default"):
            if key and key in matrix:
                cell = matrix[key]
                if isinstance(cell, dict):
                    return str(cell.get("account") or ""), str(cell.get("account_name") or coding.get("account_name", ""))
                return str(cell), str(coding.get("account_name", ""))
    return str(coding.get("account") or fallback), str(coding.get("account_name", ""))


def build(transactions: list, period: str, mcc_map: dict, people_map: dict, families: dict | None = None,
          liability_account: str = "", liability_name: str = "Accrued Expenses", unmapped_account: str = "",
          location: str = "", default_department: str = "GENERAL", journal: str = "GJ",
          vendor_name_floor: float = 1000.0, always_vendor_named: list | None = None,
          post_date_cutoff: str = "", dept_labels: dict | None = None,
          merchant_overrides: list | None = None) -> dict:
    if not liability_account:
        raise ValueError("--liability-account is required: the accrual needs somewhere to credit")
    families = {str(k).upper(): str(v).upper() for k, v in (families or {}).items()}
    always = [str(c).upper() for c in (always_vendor_named or [])]
    default_department = str(default_department).upper()
    labels = {label_key(k): str(v).upper() for k, v in (dept_labels or {}).items()}
    overrides = check_overrides(merchant_overrides)
    rows_in = [r for r in transactions if not period or month_of(r.get("date") or r.get("tran_date")) == period]
    # The card file has a department column when a label map is given or any row has a label.
    column = dept_labels is not None or any(label_key(r.get("dept_export")) for r in rows_in)

    buckets, unmapped, cardholders, traced, past_cutoff = {}, [], [], [], 0
    for row in rows_in:
        posted = str(row.get("post_date") or row.get("posted_date") or "").strip()[:10]
        if posted and post_date_cutoff and posted > post_date_cutoff[:10]:
            past_cutoff += 1  # a row with no post date is never trimmed
            continue
        amount = money(row.get("amount"))
        if not amount:
            continue
        merchant = str(row.get("merchant") or row.get("vendor") or "UNKNOWN").upper().strip()
        mcc = str(row.get("mcc") or "").strip()
        override, coding = match_override(overrides, merchant), mcc_map.get(mcc)
        if override is not None:
            coding = {**override, "category": override.get("category") or (coding or {}).get("category") or "OTHER"}
            coded_by = f"merchant override {override['pattern']}"
        elif coding is None:
            coding = {"category": "OTHER", "account": unmapped_account, "account_name": "Other Expense"}
            coded_by = "unmapped"
            if merchant not in unmapped:
                unmapped.append(merchant)
        else:
            coded_by = f"mcc {mcc}"

        cardholder = str(row.get("cardholder") or "").strip()
        people_dept = str((lookup_person(people_map, cardholder) or {}).get("department") or "").upper()
        label = label_key(row.get("dept_export"))
        column_dept = labels.get(label, "") if label else ""
        if coding.get("department"):
            department, source = str(coding["department"]).upper(), "mcc map"
        elif column and column_dept:
            department, source = column_dept, "column"
        else:
            why = ("unknown label" if label else "blank label") if column else ""
            if people_dept:
                department, source = people_dept, f"{why}, people map" if why else "people map"
            else:
                department, source = default_department, f"{why}, default" if why else "default"
                if (cardholder or "(blank)") not in cardholders:
                    cardholders.append(cardholder or "(blank)")

        category = str(coding.get("category", "OTHER")).upper()
        account, account_name = account_for(coding, department, families, unmapped_account)
        bucket = buckets.setdefault((department, category, account, account_name), {})
        bucket[merchant] = round(bucket.get(merchant, 0.0) + amount, 2)
        traced.append({
            "date": str(row.get("date") or row.get("tran_date") or "")[:10], "merchant": merchant,
            "cardholder": cardholder, "amount": round(amount, 2), "mcc": mcc, "dept_export": label,
            "column_department": column_dept, "people_department": people_dept,
            "department": department, "department_source": source,
            "category": category, "account": account, "account_name": account_name, "coded_by": coded_by,
        })

    lines = []
    for (department, category, account, account_name), merchants in sorted(buckets.items()):
        base = {"account": account, "account_name": account_name, "department": department,
                "location": location, "credit": 0.0, "category": category}
        named = {m: t for m, t in merchants.items() if abs(t) >= vendor_name_floor or category in always}
        for merchant, total in sorted(named.items()):
            lines.append({**base, "debit": round(total, 2), "memo": f"ACCRUED {category} - {merchant}",
                          "vendor": merchant, "naming": "vendor", "max_merchant": round(abs(total), 2)})
        rest = {m: t for m, t in merchants.items() if m not in named}
        if rest:
            lines.append({**base, "debit": round(sum(rest.values()), 2), "memo": f"ACCRUED {category}",
                          "vendor": "", "naming": "bucket", "max_merchant": round(max(abs(t) for t in rest.values()), 2)})
    total = round(sum(line["debit"] for line in lines), 2)
    lines.append({"account": liability_account, "account_name": liability_name, "department": default_department,
                  "location": location, "debit": 0.0, "credit": total,
                  "memo": f"ACCRUED CREDIT CARD EXPENSES {period}", "vendor": "", "category": "",
                  "naming": "offset", "max_merchant": 0.0})

    recon = department_reconciliation(traced, column)
    overrides_used = {}
    for r in traced:
        if r["coded_by"].startswith("merchant override "):
            used = overrides_used.setdefault(r["coded_by"][len("merchant override "):], {"rows": 0, "amount": 0.0})
            used["rows"] += 1
            used["amount"] = round(used["amount"] + r["amount"], 2)
    notes = ["unmapped: " + ", ".join(unmapped) if unmapped else "every merchant mapped"]
    if cardholders:
        notes.append(f"cardholders absent from the people map (report only, accrued at "
                     f"{default_department}): {', '.join(cardholders)}")
    if column:
        notes.append(recon["summary"])
    if past_cutoff:
        notes.append(f"{past_cutoff} row(s) excluded by the post-date cutoff {post_date_cutoff}")
    clean = recon["ready"] and not unmapped and not cardholders
    return {
        "period": period, "vendor_name_floor": vendor_name_floor, "always_vendor_named": always,
        "proposals": [{"je_id": f"CC-{period}", "journal": journal,
                       "description": f"CREDIT CARD EXPENSE ACCRUAL {period}",
                       "posting_date": period_end(period), "reversal_date": first_of_next_month(period),
                       "source": "cc-accrual", "lines": lines}],
        "unmapped_merchants": unmapped, "unmapped_cardholders": cardholders,
        "post_date_cutoff": post_date_cutoff, "excluded_by_post_date": past_cutoff,
        "total": total, "notes": "; ".join(notes),
        "department_reconciliation": recon, "merchant_overrides_used": overrides_used,
        "ready": clean, "rows": traced, "passed": clean,
        "summary": (f"{period} credit-card accrual: ${total:,.0f} across {len(lines) - 1} line(s), "
                    f"{sum(1 for line in lines if line['naming'] == 'vendor')} vendor-named"),
    }


def department_reconciliation(traced: list, column: bool) -> dict:
    """Where each row's department came from, and every place the column and the people map part.

    by_source: rows and amount per source. disagreements: per cardholder, rows where the column
    and the people map differ, and which was used. unknown_labels: labels the label map lacks.
    blanks: rows with no label. ready: false when any row's department came from a fallback.
    """
    by_source, disagree, unknown, blanks = {}, {}, {}, {}

    def add(bucket, amount):
        bucket["rows"] = bucket.get("rows", 0) + 1
        bucket["amount"] = round(bucket.get("amount", 0.0) + amount, 2)

    for r in traced:
        add(by_source.setdefault(r["department_source"], {}), r["amount"])
        if not column:
            continue
        who = r["cardholder"] or "(blank)"
        if r["column_department"] and r["column_department"] != r["people_department"]:
            add(disagree.setdefault((who, r["column_department"], r["people_department"]), {
                "cardholder": who, "column": r["column_department"],
                "people_map": r["people_department"] or "(not in people map)",
                "used": r["department"], "used_source": r["department_source"]}), r["amount"])
        if r["department_source"].startswith("unknown label"):
            entry = unknown.setdefault(r["dept_export"], {"label": r["dept_export"], "cardholders": [], "used": []})
            add(entry, r["amount"])
            for key, value in (("cardholders", who), ("used", r["department"])):
                if value not in entry[key]:
                    entry[key].append(value)
        if r["department_source"].startswith("blank label"):
            add(blanks.setdefault((who, r["department"]), {
                "cardholder": who, "used": r["department"], "used_source": r["department_source"]}), r["amount"])
    fallback = [r for r in traced if column and r["department_source"] not in ("column", "mcc map")]
    out = {
        "source": "column" if column else "people map",
        "by_source": by_source,
        "disagreements": sorted(disagree.values(), key=lambda d: (-abs(d["amount"]), d["cardholder"])),
        "unknown_labels": sorted(unknown.values(), key=lambda d: d["label"]),
        "blanks": sorted(blanks.values(), key=lambda d: d["cardholder"]),
        "fallback_rows": len(fallback),
        "fallback_amount": round(sum(r["amount"] for r in fallback), 2),
        "ready": not fallback,
    }
    if not column:
        out["summary"] = "departments from the people map (the export has no department column)"
    else:
        out["summary"] = (
            f"departments from the export's column; {sum(d['rows'] for d in out['disagreements'])} row(s) where "
            f"the column and the people map disagree; {len(out['unknown_labels'])} unknown label(s); "
            f"{sum(b['rows'] for b in out['blanks'])} blank label row(s); "
            f"{len(fallback)} row(s), ${out['fallback_amount']:,.2f}, on a fallback"
            + ("" if not fallback else " - the draft is not ready"))
    return out


def run(transactions: str, period: str, mcc_map: str, people_map: str, dept_labels: str = "", **settings) -> dict:
    """Read the files and build: the MCC file also carries department_families and merchant_overrides."""
    mcc_file = dict(load_map(mcc_map, "--mcc-map") or {})
    labels = as_labels(load_map(dept_labels, "--dept-labels")) if dept_labels else None
    codes = as_map({k: v for k, v in mcc_file.items() if k != "merchant_overrides"})
    return build(load_rows(transactions), period, codes, as_map(load_map(people_map, "--people-map") or {}),
                 mcc_file.get("department_families"), dept_labels=labels,
                 merchant_overrides=mcc_file.get("merchant_overrides"), **settings)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=__doc__.split("\n\n", 1)[1])
    parser.add_argument("transactions")
    parser.add_argument("--period", required=True, help="accounting period YYYY-MM")
    parser.add_argument("--mcc-map", required=True, help="MCC -> {category, account, account_by_department}")
    parser.add_argument("--people-map", required=True, help="cardholder -> {department}")
    parser.add_argument("--liability-account", required=True, help="accrued-liability account the offset credits")
    parser.add_argument("--liability-name", default="Accrued Expenses")
    parser.add_argument("--unmapped-account", required=True, help="account unmapped merchants are coded to")
    parser.add_argument("--location", default="", help="LOCATION_ID for every line")
    parser.add_argument("--default-department", default="GENERAL")
    parser.add_argument("--journal", default="GJ")
    parser.add_argument("--vendor-name-floor", type=float, default=1000.0,
                        help="a merchant at or above this gets its own named line (default 1000)")
    parser.add_argument("--always-vendor-named", action="append", default=[],
                        help="category always broken out by vendor; repeatable")
    parser.add_argument("--post-date-cutoff", default="", help="drop rows posted after this date (YYYY-MM-DD)")
    parser.add_argument("--dept-labels", default="", help="the export's department label -> department id")
    parser.add_argument("--out", default="", help="write the result JSON here (je_import.py reads it)")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    try:
        result = run(args.transactions, args.period, args.mcc_map, args.people_map, args.dept_labels,
                     liability_account=args.liability_account, liability_name=args.liability_name,
                     unmapped_account=args.unmapped_account, location=args.location,
                     default_department=args.default_department, journal=args.journal,
                     vendor_name_floor=args.vendor_name_floor, always_vendor_named=args.always_vendor_named,
                     post_date_cutoff=args.post_date_cutoff)
        if args.out:
            out = Path(args.out).expanduser()
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, indent=1))
            result["out"] = str(out)
    except (OSError, ValueError, TypeError) as exc:
        print(f"cc_accrual: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(result, indent=1))
    else:
        print(result["summary"])
        for d in result["department_reconciliation"]["disagreements"]:
            print(f"  dept: {d['cardholder']} column {d['column']} vs people map {d['people_map']}: "
                  f"{d['rows']} row(s) {d['amount']:,.2f}, used {d['used']}")
        for u in result["department_reconciliation"]["unknown_labels"]:
            print(f"  dept: unknown label {u['label']!r}: {u['rows']} row(s) {u['amount']:,.2f}")
        print(f"  {result['notes']}")
        for line in result["proposals"][0]["lines"]:
            print(f"  {line['account']:8} {line['department']:10} {line['naming']:7} "
                  f"{line['debit'] or -line['credit']:>14,.2f}  {line['memo'][:56]}")
        if args.out:
            print(f"  wrote {args.out}")
        print("PASS" if result["passed"] else "FAIL: unmapped merchants or cardholders, or department gaps")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
