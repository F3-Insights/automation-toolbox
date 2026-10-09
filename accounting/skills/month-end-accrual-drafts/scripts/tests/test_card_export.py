"""Tests for card_export.py: the period's rows from a card download, payments dropped, signs kept."""

from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from openpyxl import Workbook

SCRIPTS = Path(__file__).resolve().parent.parent


def load(name):
    sys.modules.pop("_common", None)
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location(f"acc_{name}", SCRIPTS / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPTS))


card = load("card_export")

HEAD = ("Tran Date", "Post Date", "Merchant Name", "Amount", "Cardholder Name",
        "Diverted From Cardholder Name", "MCC Code", "MCC Description", "Tran Type", "Dept", "Reference Number")
GRID = [
    HEAD,
    ("8/3/2026", "8/5/2026", "Lakeview Hardware", 412.5, "Sam Ortiz", None, 5251, "Hardware", "Purchase", "ops", "R1"),
    ("8/9/2026", "8/10/2026", "Fabrikam Logistics", -60.0, "Central Account", "Priya Nair", 4215, "Courier",
     "Credit", "Admin", "R2"),
    ("8/20/2026", "8/21/2026", "Payment Thank You", -5000.0, "Sam Ortiz", None, None, None, "Payment", "", "R3"),
    ("7/30/2026", "8/1/2026", "Northwind Traders", 99.0, "Sam Ortiz", None, 5999, "Misc", "Purchase", "", "R4"),
]


def test_keeps_the_period_drops_payments_and_keeps_signs():
    result = card.convert(GRID, "2026-08")
    assert result["row_count"] == 2 and result["total"] == 352.5
    assert result["dropped"] == {"payment to the card (not an expense)": 1, "transaction date outside 2026-08": 1}
    refund = result["rows"][1]
    assert refund["amount"] == "-60.00" and refund["cardholder"] == "PRIYA NAIR" and refund["dept_export"] == "ADMIN"
    assert result["rows"][0]["date"] == "2026-08-03" and result["rows"][0]["mcc"] == "5251"


def test_a_missing_column_stops_naming_it_and_a_different_export_is_described():
    with pytest.raises(ValueError, match="Merchant Name"):
        card.convert([tuple("Payee" if h == "Merchant Name" else h for h in HEAD)] + GRID[1:], "2026-08")
    renamed = [tuple("Payee" if h == "Merchant Name" else h.upper() for h in HEAD)] + GRID[1:]
    result = card.convert(renamed, "2026-08", card.parse_columns(["merchant=payee"]))
    assert result["rows"][0]["merchant"] == "Lakeview Hardware"


def test_the_cli_writes_the_csv_and_fails_on_an_empty_period(tmp_path):
    book = Workbook()
    sheet = book.active
    sheet.title = card.DEFAULT_SHEET
    for row in GRID:
        sheet.append(row)
    xlsx = tmp_path / "download.xlsx"
    book.save(xlsx)
    out = tmp_path / "card.csv"
    done = subprocess.run([sys.executable, str(SCRIPTS / "card_export.py"), str(xlsx), "--period", "2026-08",
                           "--out", str(out), "--format", "json"], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert {k: json.loads(done.stdout)[k] for k in ("row_count", "total")} == {"row_count": 2, "total": 352.5}
    with out.open(newline="") as handle:
        assert [r["merchant"] for r in csv.DictReader(handle)] == ["Lakeview Hardware", "Fabrikam Logistics"]
    empty = subprocess.run([sys.executable, str(SCRIPTS / "card_export.py"), str(xlsx), "--period", "2026-03"],
                           capture_output=True, text=True)
    assert empty.returncode == 1
