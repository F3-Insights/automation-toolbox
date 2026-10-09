"""Ledger helpers the month-end-flux scripts share.

A pull is a JSON file, either {"meta": {...}, "rows": [...]} or a bare list of rows. Rows come
in one of two shapes and every script reads them through field():

- the standard shape: GL lines (je_id, journal, date, account, account_name, location,
  debit, credit, memo, created_at, vendor), journal-entry headers (je_id, je_number,
  journal, date, description, state, reversed_from) and document lines such as AP bills
  (doc_id, posting_date, counterparty, memo);
- the Sage Intacct shape as a pull lands it, with dotted names (glAccount.id,
  journalEntry.key, baseAmount with txnType, ...).
"""

import calendar
import csv
import io
import json
import re
from pathlib import Path
from statistics import median

LINE, HEADER, DOC = "line", "header", "doc"

# Standard field -> the Sage Intacct name(s) a raw pull carries instead; the first present wins.
INTACCT = {
    LINE: {"je_id": "journalEntry.key", "journal": "journalEntry.glJournal.id", "date": "entryDate",
           "account": "glAccount.id", "account_name": "glAccount.name",
           "location": "dimensions.location.id", "memo": "description", "state": "journalEntry.state",
           "created_at": "audit.createdDateTime", "vendor": "dimensions.vendor.id"},
    HEADER: {"je_id": ("key", "id"), "je_number": "id", "journal": "glJournal.id", "date": "postingDate",
             "reversed_from": "reversedFromDate"},
    DOC: {"doc_id": ("bill.id", "invoice.id"), "posting_date": ("bill.postingDate", "invoice.invoiceDate"),
          "counterparty": ("vendor.name", "invoice.customer.name")},
}


def field(row, name, kind=LINE):
    """A standard field as text, from either shape; '' when absent."""
    if name in row:
        value = row[name]
    else:
        aliases = INTACCT[kind].get(name, ())
        aliases = (aliases,) if isinstance(aliases, str) else aliases
        value = next((row[a] for a in aliases if a in row), "")
    return "" if value is None else str(value)


def money(value):
    """An amount as a number; blank or absent is zero."""
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).replace(",", "").replace("$", ""))


def _standard(row):
    return "debit" in row or "credit" in row


def signed(row):
    """A GL line's amount, debit positive."""
    if _standard(row):
        return money(row.get("debit")) - money(row.get("credit"))
    amount = money(row.get("baseAmount") or row.get("txnAmount"))
    return amount if str(row.get("txnType", "")).lower().startswith("d") else -amount


def debit(row):
    """A GL line's debit amount; zero for a credit line."""
    if _standard(row):
        return money(row.get("debit"))
    return max(signed(row), 0.0)


def side(row):
    """'debit' or 'credit'; a raw Intacct row reports its own flag as written."""
    if _standard(row):
        return "credit" if money(row.get("credit")) and not money(row.get("debit")) else "debit"
    return str(row.get("txnType"))


def amount_key(row):
    """The unsigned amount as text, stable between runs (a raw Intacct row keeps its string)."""
    return f"{abs(signed(row)):.2f}" if _standard(row) else str(row.get("baseAmount"))


def load_pull(path):
    """The rows of a pull, in either file shape."""
    path = Path(path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"pull not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8").removeprefix("\ufeff"))
    if isinstance(data, dict):
        return list(data.get("rows") or [])
    if isinstance(data, list):
        return data
    raise ValueError(f"{path}: expected a list of rows or a {{meta, rows}} object")


def load_table(path):
    """Rows from a CSV file, a JSON list, or JSON {rows: [...]}."""
    path = Path(path).expanduser()
    if path.suffix.lower() == ".csv":
        # newline="" keeps a line break or form feed inside a quoted cell part of that cell.
        text = path.read_text(encoding="utf-8").removeprefix("\ufeff")
        return list(csv.DictReader(io.StringIO(text, newline="")))
    data = json.loads(path.read_text(encoding="utf-8").removeprefix("\ufeff"))
    if isinstance(data, dict):
        data = data.get("rows") or data.get("transactions") or []
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a list of rows")
    return [dict(r) for r in data]


def month_of(value):
    """'2026-03-31' -> '2026-03'; '' when it is not a date."""
    text = str(value or "")
    return text[:7] if re.match(r"^\d{4}-\d{2}", text) else ""


def shift_period(period, months):
    year, month = (int(p) for p in period.split("-")[:2])
    index = year * 12 + month - 1 + months
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def trailing_periods(period, count):
    """The `count` periods before `period`, oldest first."""
    return [shift_period(period, -n) for n in range(count, 0, -1)]


def reporting_period_month(label):
    """'Month Ended March 2026' -> '2026-03'; anything else -> ''."""
    parts = str(label or "").split()
    if len(parts) < 4 or parts[0] != "Month" or parts[1] != "Ended":
        return ""
    names = [calendar.month_name[i].lower() for i in range(1, 13)]
    try:
        return f"{int(parts[3]):04d}-{names.index(parts[2].lower()) + 1:02d}"
    except (ValueError, IndexError):
        return ""


def median_of(values):
    return round(median(values), 2) if values else 0.0


def mad_z(value, history):
    """(z, median) by median absolute deviation, scaled 1.4826. A zero deviation counts as 1,
    so a flat history gives the raw dollar change, which the amount floor then filters."""
    if not history:
        return 0.0, 0.0
    med = median(history)
    mad = median([abs(x - med) for x in history]) or 1.0
    return (value - med) / (1.4826 * mad), med


MONTHS = ("JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER"
          "|JAN|FEB|MAR|APR|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC")


def normalize_description(text):
    """Fold an entry description to a key that is the same every month: upper case, no
    reversal prefix, month names as <M> and numbers as <N>, punctuation squeezed."""
    body = re.sub(r"^REVERSED?\s*-\s*", "", str(text or ""), flags=re.I).upper()
    body = re.sub(rf"\b({MONTHS})\b", "<M>", body)
    body = re.sub(r"\d+([.,]\d+)*", "<N>", body)
    body = re.sub(r"[^A-Z0-9<>]+", " ", body)
    return re.sub(r"\s+", " ", body).strip()
