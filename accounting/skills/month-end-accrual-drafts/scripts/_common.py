"""Helpers the accrual scripts share: periods, amounts, reading ledger pulls, and reading a
field off a row in either ledger shape.

A pull row comes in one of two shapes. The standard shape names its fields plainly
(account, je_id, debit, credit, doc_id, counterparty). A Sage Intacct pull, as it lands,
carries the ERP's dotted names instead (glAccount.id, journalEntry.key, baseAmount with
txnType). `field` asks for the plain name and falls back to the dotted one.
"""

from __future__ import annotations

import calendar
import csv
import io
import json
import re
from pathlib import Path

# Plain name -> the Intacct name(s) the dotted shape uses, per kind of row.
INTACCT = {
    "line": {
        "je_id": "journalEntry.key", "journal": "journalEntry.glJournal.id", "date": "entryDate",
        "account": "glAccount.id", "account_name": "glAccount.name",
    },
    "header": {
        "je_id": ("key", "id"), "journal": "glJournal.id", "date": "postingDate",
        "reversed_from": "reversedFromDate", "schedule_id": "scheduledOperationKey",
    },
    "doc": {
        "doc_id": ("bill.id", "invoice.id"),
        "posting_date": ("bill.postingDate", "invoice.invoiceDate"),
        "counterparty": ("vendor.name", "invoice.customer.name"),
        "account": "glAccount.id", "account_name": "glAccount.name",
        "department": "dimensions.department.id", "location": "dimensions.location.id",
        "amount": "baseAmount",
    },
}


def field(row: dict, name: str, kind: str = "line") -> str:
    """The text of field `name` on a row of either shape; '' when absent."""
    if name in row:
        value = row[name]
    else:
        aliases = INTACCT[kind].get(name, ())
        value = next((row[a] for a in ((aliases,) if isinstance(aliases, str) else aliases) if a in row), None)
    return "" if value is None else str(value)


def money(value) -> float:
    """An amount from a number or text such as '$1,250.00'; blank is zero."""
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).replace(",", "").replace("$", ""))


def signed(row: dict) -> float:
    """A GL line's amount, debit positive, from either shape."""
    if "debit" in row or "credit" in row:
        return money(row.get("debit")) - money(row.get("credit"))
    amount = money(row.get("baseAmount") or row.get("txnAmount"))
    return amount if str(row.get("txnType", "")).lower().startswith("d") else -amount


# --- periods -------------------------------------------------------------------------------


def month_of(value) -> str:
    """'2026-07-31' -> '2026-07'; '' when the text is not a date."""
    text = str(value or "")
    return text[:7] if re.match(r"^\d{4}-\d{2}", text) else ""


def shift_period(period: str, months: int) -> str:
    year, month = (int(p) for p in period.split("-")[:2])
    index = year * 12 + month - 1 + months
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def period_end(period: str) -> str:
    year, month = (int(p) for p in period.split("-")[:2])
    return f"{period}-{calendar.monthrange(year, month)[1]:02d}"


def first_of_next_month(period: str) -> str:
    return f"{shift_period(period, 1)}-01"


def period_tokens(period: str) -> list:
    """Upper-case fragments a person writes in a memo to name the period."""
    year, month = (int(x) for x in period.split("-"))
    name, abbr = calendar.month_name[month].upper(), calendar.month_abbr[month].upper()
    yy = f"{year % 100:02d}"
    return [f"{name} {year}", f"{abbr} {year}", f"{name} {yy}", f"{abbr} {yy}", f"{abbr}-{yy}", f"{abbr}{yy}",
            period, f"{month:02d}/{year}", f"{month}/{year}", f"{month:02d}-{year}", name, f"{abbr}."]


# --- reading files -------------------------------------------------------------------------


def read_text(path: Path) -> str:
    """A file's text with any byte-order mark dropped (Excel writes one)."""
    text = path.read_text(encoding="utf-8")
    return text[1:] if text.startswith("\ufeff") else text


def load_snapshot(path) -> list:
    """The rows of a pull: {"meta": ..., "rows": [...]} or a bare list."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")
    data = json.loads(read_text(path))
    if isinstance(data, dict):
        return list(data.get("rows") or [])
    if isinstance(data, list):
        return data
    raise ValueError(f"{path}: expected a list of rows or a {{meta, rows}} object")


def load_rows(path) -> list:
    """Rows from a CSV (a byte-order mark is dropped), a bare JSON list, or {rows|transactions: [...]}."""
    path = Path(path)
    text = read_text(path)
    if path.suffix.lower() == ".csv":
        return [dict(r) for r in csv.DictReader(io.StringIO(text, newline=""))]
    data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("rows") or data.get("transactions") or []
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a list of rows")
    return [dict(r) for r in data]


def load_map(path, what: str):
    """A settings file in JSON, or YAML when the name ends .yaml or .yml (needs pyyaml)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"{what}: the file does not exist: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        import yaml  # only a YAML file needs it
        return yaml.safe_load(text)
    return json.loads(text)
