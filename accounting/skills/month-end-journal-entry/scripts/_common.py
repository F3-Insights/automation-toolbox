"""The Sage Intacct GL journal-entry import layout and its checks, shared by je_import.py
(which builds the file) and je_import_check.py (which lints a file already on disk).

The layout is Intacct's own GL import template: its 28 columns in order, the header fields
(JOURNAL, DATE, REVERSEDATE, DESCRIPTION, STATE) on the first line of each entry only, and
dates as M/D/YYYY with no leading zeros. Intacct rejects a file that repeats the header on
every line or uses its own column names, which is why every file is linted before upload.
"""

from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

COLUMNS = [
    "DONOTIMPORT", "JOURNAL", "DATE", "REVERSEDATE", "DESCRIPTION", "REFERENCE_NO", "LINE_NO",
    "ACCT_NO", "LOCATION_ID", "DEPT_ID", "DOCUMENT", "MEMO", "DEBIT", "CREDIT", "SOURCEENTITY",
    "CURRENCY", "EXCH_RATE_DATE", "EXCH_RATE_TYPE_ID", "EXCHANGE_RATE", "STATE", "ALLOCATION_ID",
    "BILLABLE", "RPESENTRY", "GLENTRY_CUSTOMERID", "GLENTRY_VENDORID", "GLENTRY_ITEMID",
    "GLENTRY_CLASSID", "GLENTRY_EMPLOYEEID",
]
HEADER_FIELDS = ("JOURNAL", "DATE", "REVERSEDATE", "DESCRIPTION", "STATE")
MDY = re.compile(r"^([1-9]|1[0-2])/([1-9]|[12]\d|3[01])/\d{4}$")


def first_of_next_month(period: str) -> str:
    """'2026-08' -> '2026-09-01'."""
    year, month = (int(p) for p in period.split("-")[:2])
    year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return f"{year:04d}-{month:02d}-01"


def intacct_date(value) -> str:
    """'2026-08-31' -> '8/31/2026'. Text that is not an ISO date is returned unchanged."""
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = date.fromisoformat(text[:10])
    except ValueError:
        return text
    return f"{parsed.month}/{parsed.day}/{parsed.year}"


def amount(value) -> float:
    text = str(value or "").strip().replace(",", "")
    return float(text) if text else 0.0


def entries(rows: list) -> list:
    """Split the flat row list into entries: a new entry starts at LINE_NO 1."""
    out = []
    for row in rows:
        if int(row.get("LINE_NO") or 0) == 1 or not out:
            out.append([])
        out[-1].append(row)
    return out


def check_rows(rows: list, liability_account: str = "", state: str = "") -> list:
    """Every check over the rows, as findings {check, severity, where, detail}.

    The checks: header fields on the first line only, M/D/YYYY dates, LINE_NO restarting at 1,
    no negative amounts, the entry balanced, REVERSEDATE the 1st of the next month, STATE as
    asked (when a state is given), and one liability offset line per location that has debits
    (when a liability account is given), so each entity balances on its own.
    """
    findings = []

    def flag(check, where, detail):
        findings.append({"check": check, "severity": "error", "where": where, "detail": detail})

    for entry in entries(rows):
        head = entry[0]
        label = f"{head.get('JOURNAL', '?')} {head.get('DATE', '?')}"
        for position, row in enumerate(entry, start=1):
            carried = [f for f in HEADER_FIELDS if position != 1 and str(row.get(f) or "").strip()]
            if carried:
                flag("header_on_first_line", f"{label} line {position}",
                     f"header field(s) {', '.join(carried)} repeated on a continuation line")
            for field in ("DEBIT", "CREDIT"):
                raw = str(row.get(field) or "").strip()
                if raw and amount(raw) < 0:
                    flag("never_negative", f"{label} line {position}",
                         f"{field} is {raw}; a negative belongs in the other column")

        for field in ("DATE", "REVERSEDATE"):
            value = str(head.get(field) or "").strip()
            if value and not MDY.match(value):
                flag("date_format", label, f"{field} {value!r} is not M/D/YYYY without leading zeros")

        if state and str(head.get("STATE") or "").strip() != state:
            flag("state", label, f"STATE is {str(head.get('STATE') or '').strip()!r}; this file must say {state!r}")

        debits = round(sum(amount(r.get("DEBIT")) for r in entry), 2)
        credits = round(sum(amount(r.get("CREDIT")) for r in entry), 2)
        if abs(debits - credits) > 0.005:
            flag("balanced", label, f"debits {debits:,.2f} do not equal credits {credits:,.2f}")

        numbers = [int(r.get("LINE_NO") or 0) for r in entry]
        if numbers != list(range(1, len(entry) + 1)):
            flag("line_no_restart", label,
                 f"LINE_NO runs {numbers}; it must restart at 1 and increment by one per entry")

        posting = str(head.get("DATE") or "").strip()
        reverse = str(head.get("REVERSEDATE") or "").strip()
        if posting and reverse and MDY.match(posting) and MDY.match(reverse):
            month, _, year = posting.split("/")
            expected = intacct_date(first_of_next_month(f"{int(year):04d}-{int(month):02d}"))
            if reverse != expected:
                flag("reverse_date_next_month", label,
                     f"REVERSEDATE {reverse} is not {expected}, the 1st of the month after {posting}")

        if liability_account:
            debits_by_loc, offsets_by_loc = defaultdict(float), defaultdict(int)
            for row in entry:
                loc = str(row.get("LOCATION_ID") or "")
                if str(row.get("ACCT_NO") or "") == liability_account:
                    offsets_by_loc[loc] += 1
                elif str(row.get("DEBIT") or "").strip():
                    debits_by_loc[loc] += amount(row["DEBIT"])
            for loc in sorted(set(debits_by_loc) | set(offsets_by_loc)):
                count = offsets_by_loc.get(loc, 0)
                where = f"{label} entity {loc or '(blank)'}"
                if debits_by_loc.get(loc) and count != 1:
                    flag("liability_offset_per_entity", where,
                         f"{count} offset line(s) on {liability_account}; each entity needs exactly one")
                elif not debits_by_loc.get(loc) and count > 1:
                    flag("liability_offset_per_entity", where,
                         f"{count} offset line(s) on {liability_account} with no debits in that entity")
    return findings


def read_csv_text(path: Path) -> str:
    """The file's text with any byte-order mark dropped (Excel writes one)."""
    text = path.read_bytes().decode("utf-8")
    return text[1:] if text.startswith("\ufeff") else text


def read_rows(path: Path) -> tuple:
    """(header, rows) of an import CSV on disk, every value kept as written."""
    text = read_csv_text(path)
    header = next(csv.reader(io.StringIO(text, newline="")), [])
    rows = [dict(r) for r in csv.DictReader(io.StringIO(text, newline=""))]
    return header, rows


def print_findings(findings: list) -> None:
    for f in findings:
        print(f"  {f['severity'].upper():7} {f['check']:28} {f['where']:28} {f['detail']}")
