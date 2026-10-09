"""Ledger helpers the month-end-reconciliation scripts share.

A ledger pull is a JSON file, either {"meta": {...}, "rows": [...]} or a bare list of rows.
A GL line arrives in one of two shapes, and every script reads it through field():

- the standard shape: je_id, date, account, account_name, debit, credit, memo, ...
- the Sage Intacct shape as a pull lands it: journalEntry.key, entryDate, glAccount.id,
  baseAmount with txnType ("debit" or "credit"), ...
"""

import json
from pathlib import Path

# Standard GL-line field -> the Sage Intacct name a raw pull carries instead.
INTACCT_LINE = {
    "je_id": "journalEntry.key", "line_no": "id", "journal": "journalEntry.glJournal.id",
    "date": "entryDate", "posting_date": "entryDate", "account": "glAccount.id",
    "account_name": "glAccount.name", "department": "dimensions.department.id",
    "location": "dimensions.location.id", "memo": "description", "state": "journalEntry.state",
}


def load_rows(path):
    """The rows of a ledger pull, in either file shape."""
    path = Path(path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"ledger pull not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8").removeprefix("\ufeff"))
    if isinstance(data, dict):
        return list(data.get("rows") or [])
    if isinstance(data, list):
        return data
    raise ValueError(f"{path}: expected a list of rows or a {{meta, rows}} object")


def field(row, name):
    """A GL line's standard field as text, from either shape; '' when absent."""
    value = row.get(name, row.get(INTACCT_LINE.get(name, ""), ""))
    return "" if value is None else str(value)


def money(value):
    """An amount as a number; blank or absent is zero."""
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).replace(",", "").replace("$", ""))


def signed(row):
    """A GL line's amount, debit positive and credit negative."""
    if "debit" in row or "credit" in row:
        return money(row.get("debit")) - money(row.get("credit"))
    amount = money(row.get("baseAmount") or row.get("txnAmount"))
    return amount if str(row.get("txnType", "")).lower().startswith("d") else -amount
