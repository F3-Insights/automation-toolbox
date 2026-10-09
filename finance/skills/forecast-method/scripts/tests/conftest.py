"""A made-up Forecast folder for Northwind Traders, built fresh in tmp_path for each test.

Two issued revisions sit in delivery/: rev4 (the prior) and rev5 (the new one). Each is a
report-shaped income statement with a consolidated block (Entity ALL), a second-entity block that
must not be counted, the sheet's own Total Revenue and EBITDA rows, a "should be zero" check row,
and a Changes sheet. rev5 raises wholesale revenue 8,000 a month from August and consulting
4,000 a month from October, so the FY change is +40,000 - 12,000 = +28,000.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MONTHS = [datetime(2027, m, 1) for m in range(1, 13)]
YEAR = "2027"

# account: (name, monthly amount in the prior). Costs positive.
PRIOR = {
    "41000": ("Wholesale revenue", 80000.0),
    "42000": ("Online revenue", 15000.0),
    "48000": ("Returns allowance", -1500.0),
    "51000": ("Cost of goods", 32000.0),
    "52000": ("Inbound freight", 4000.0),
    "58000": ("Warehouse bonus", 800.0),
    "61000": ("Wages", 25000.0),
    "61500": ("Staff bonus", 1500.0),
    "62000": ("Lease", 6000.0),
    "66000": ("Consulting", 2500.0),
    "81000": ("Amortisation", 1200.0),
}
PRIOR_EBITDA = 12 * ((80000 + 15000 - 1500) - (32000 + 4000) - (25000 + 6000 + 2500))   # 288,000 pre-bonus


def amounts(revision):
    """{account: (name, [12 monthly amounts])} for rev4 or rev5."""
    out = {}
    for account, (name, base) in PRIOR.items():
        values = []
        for month in range(1, 13):
            value = base
            if revision == 5 and account == "41000" and month >= 8:
                value += 8000.0
            if revision == 5 and account == "66000" and month >= 10:
                value += 4000.0
            values.append(value)
        out[account] = (name, values)
    return out


def write_book(path, data, changes=None, break_tie=False):
    from openpyxl import Workbook
    book = Workbook()
    ws = book.active
    ws.title = "Income Statement"
    ws.append(["Northwind Traders income statement"])
    ws.append([])
    ws.append(["GL", "Description", "Entity"] + MONTHS)
    revenue, cost = [0.0] * 12, [0.0] * 12
    for account, (name, values) in data.items():
        ws.append([int(account), name, "ALL"] + values)
        for i, v in enumerate(values):
            if account[0] == "4":
                revenue[i] += v
            elif account[0] in "56":
                cost[i] += v
    ws.append([None, "Total Revenue", "ALL"] + revenue)
    ws.append([None, "EBITDA", "ALL"] + [r - c + (2.0 if break_tie else 0.0) for r, c in zip(revenue, cost)])
    ws.append([None, "Check (should be zero)", None] + [0.0] * 12)
    ws.append([])
    ws.append([None, "Entity E2", None])
    for account, (name, values) in data.items():
        ws.append([int(account), name, "E2"] + [v / 4 for v in values])
    log = book.create_sheet("Changes")
    log.append(["Date", "Change", "Asked by"])
    for row in changes or []:
        log.append(row)
    book.save(path)
    return path


SETTINGS = {
    "basis": "pre_bonus",
    "years": [2027],
    "accounts": {"section_prefixes": {"4": "revenue", "5": "cogs", "6": "sga", "8": "below_ebitda"},
                 "bonus_accounts": ["58000", "61500"]},
    "layouts": {"default": {"sheet": "Income Statement", "header_row": 3,
                            "columns": {"account": "GL", "account_name": "Description", "location": "Entity"},
                            "row_filter": {"Entity": "ALL"}, "blank_token": "",
                            "tie_rows": {"revenue": "Total Revenue", "ebitda": "EBITDA"},
                            "zero_rows": ["Check (should be zero)"]}},
    "revisions": {"folder": "delivery", "pattern": "Northwind forecast rev*.xlsx", "number": r"rev(\d+)",
                  "vintage_from": r"rev\d+"},
    "change_log_sheets": ["Changes"],
    "sign_exempt_accounts": ["48"],
    "thresholds": {"materiality_abs": 15000},
}

MODULES = {"modules": [
    {"key": "revenue", "label": "Wholesale and online revenue", "accounts": ["41", "42"], "owner": "Sales director"},
    {"key": "returns", "label": "Returns", "accounts": ["48"]},
    {"key": "cogs", "label": "Cost of goods", "accounts": ["5"]},
    {"key": "staff", "label": "Staff", "accounts": ["61"]},
    {"key": "outside", "label": "Outside services", "accounts": ["66"], "materiality_abs": 8000},
]}


@pytest.fixture
def folder(tmp_path):
    root = tmp_path / "Forecast"
    (root / "delivery").mkdir(parents=True)
    (root / "FORECAST-SETTINGS.yaml").write_text(yaml.safe_dump(SETTINGS, sort_keys=False))
    (root / "modules.yaml").write_text(yaml.safe_dump(MODULES, sort_keys=False))
    write_book(root / "delivery" / "Northwind forecast rev4.xlsx", amounts(4))
    write_book(root / "delivery" / "Northwind forecast rev5.xlsx", amounts(5),
               changes=[["2027-07-14", "Wholesale up 8k a month from August for the new retail chain", "Sales director"],
                        ["2027-07-15", "Consulting up 4k a month in Q4 for the system migration", "Controller"]])
    return root


def open_vintage(root):
    """Run forecast-prepare and return the new vintage's folder."""
    import forecast_prepare
    result = forecast_prepare.prepare(root)
    assert result["line"].startswith("FRESH: vintage rev5, rev4 to rev5"), result["line"]
    return root / "vintages" / "rev5"


def write_hypotheses(vdir, revenue=30000.0):
    lines = {f"{YEAR}:{m['key']}": {"expected": 0.0, "confidence": 0.6, "rationale": "No request touches it."}
             for m in MODULES["modules"]}
    lines[f"{YEAR}:revenue"] = {"expected": revenue, "confidence": 0.7, "rationale": "The retail chain."}
    lines[f"{YEAR}:outside"] = {"expected": -12000.0, "confidence": 0.5, "rationale": "The migration."}
    (vdir / "hypotheses.json").write_text(json.dumps({"fy": {YEAR: {"ebitda_expected": PRIOR_EBITDA + 18000.0}},
                                                      "lines": lines}))


def set_vintage(vdir, **fields):
    meta = yaml.safe_load((vdir / "VINTAGE.yaml").read_text())
    meta.update(fields)
    (vdir / "VINTAGE.yaml").write_text(yaml.safe_dump(meta))
