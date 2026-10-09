"""An invented Month-End folder for Northwind Traders closing March 2026, built in tmp_path."""

import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PERIOD = "2026-03"

PROCEDURES = """# Month-end procedures

## Balance-sheet accounts

| Account | Name | Workstream | Company workbook |
|---|---|---|---|
| 10200 | Cash - checking | cash | cash.xlsx |
| `13000-13999` | Prepaids | accruals | prepaids.xlsx |
| 22000, 22500 | Accrued expenses | accruals | accruals.xlsx |

## Other
"""

STATUS = """# 2026-03 status

## Waiting on

| Id | Phase | Question | Asked of | How | Asked at | State | Answer | Answered at |
|---|---|---|---|---|---|---|---|---|
| Q1 | Accruals | Is the bonus accrual still needed? | Controller | email | 2026-03-30 | open | | |
| Q2 | Cash | Which statement is final? | Controller | email | 2026-03-29 | closed | The second | 2026-03-30 |
"""

CHECKLIST = """# Procedures 2026-03

| Step | Task | Owner | Due | Status |
|---|---|---|---|---|
| 1 | Pull the ledger | Agent | ME+1 = 2026-04-01 | done |
| 2 | Draft the card accrual | Agent (accruals) | ME+2 = 2026-04-02 | open |
| 3 | Approve payroll | Controller | ME+1 = 2026-04-01 | open |
| 4 | Draft the flux | Agent | ME+6 = 2026-04-08 | open |
"""


def dump(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"meta": {}, "rows": rows}))


def entry(key, day, description, amount, state="posted", reversed_from=None):
    """A raw Intacct header and its two lines."""
    head = {"key": key, "id": key, "postingDate": day, "state": state, "description": description,
            "reversedFromDate": reversed_from}
    lines = [{"journalEntry.key": key, "glAccount.id": "62000", "txnType": "debit", "baseAmount": f"{amount:.2f}"},
             {"journalEntry.key": key, "glAccount.id": "22000", "txnType": "credit", "baseAmount": f"{amount:.2f}"}]
    return head, lines


def ledger(source, period, entries):
    dump(source / f"headers-{period}.json", [h for h, _ in entries])
    dump(source / f"lines-{period}.json", [ln for _, ls in entries for ln in ls])


def import_file(path, description, amounts):
    """A draft import CSV: debit lines then one credit line, STATE Posted."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"DATE": "2026-03-31", "LINE_NO": "1", "DESCRIPTION": description, "STATE": "Posted",
             "ACCT_NO": "62000", "DEBIT": f"{amounts[0]:.2f}", "CREDIT": ""}]
    rows += [{"LINE_NO": str(i + 2), "ACCT_NO": "62000", "DEBIT": f"{a:.2f}", "CREDIT": ""} for i, a in enumerate(amounts[1:])]
    rows.append({"LINE_NO": str(len(amounts) + 1), "ACCT_NO": "22000", "DEBIT": "", "CREDIT": f"{sum(amounts):.2f}"})
    with path.open("w", newline="", encoding="utf-8") as fh:
        fh.write("\ufeff")  # a byte-order mark, as Excel writes
        writer = csv.DictWriter(fh, fieldnames=["DATE", "LINE_NO", "DESCRIPTION", "STATE", "ACCT_NO", "DEBIT", "CREDIT"])
        writer.writeheader()
        writer.writerows(rows)


def settle(month):
    """Date every file in the month before the last LOG entry."""
    stamp = datetime(2026, 4, 2, 16, 0).timestamp()
    for path in month.rglob("*"):
        if path.is_file():
            os.utime(path, (stamp, stamp))


def build_folder(tmp_path):
    root = tmp_path / "Northwind Month-End"
    root.mkdir()
    (root / "MONTH-END-PROCEDURES.md").write_text(PROCEDURES)
    (root / "STATUS.md").write_text("# Northwind Traders\n\n- **Current period:** `2026-03`\n")
    month = root / "2026" / PERIOD
    for sub in ("journal-entries", "reconciliations", "reporting", "work/source"):
        (month / sub).mkdir(parents=True)
    (month / "STATUS.md").write_text(STATUS)
    (month / "LOG.md").write_text("# Log\n\n## 2026-04-01 08:30 by keeper\n- set up\n\n## 2026-04-02 17:00 by orchestrator\n")
    (month / f"MONTH-END-PROCEDURES-{PERIOD}.md").write_text(CHECKLIST)
    (month / "reporting" / f"MONTH-END-FINDINGS-{PERIOD}.md").write_text("# Findings\n")
    source = month / "work" / "source"
    (source / "pulled.md").write_text("Pulled 2026-04-02, read-only. PRELIMINARY: March still open.\n")
    ledger(source, PERIOD, [
        entry("301", "2026-03-31", "Card accrual Mar 2026", 1800.0),
        entry("302", "2026-03-31", "Vendor accrual March 2026", 4100.0),
        entry("303", "2026-03-01", "Reversed - Rent accrual Feb 2026", 2500.0, reversed_from="2026-02-28"),
        entry("304", "2026-03-31", "Amortization 03/2026", 600.0),
    ])
    dump(source / f"trial-balance-{PERIOD}.json", [
        {"Account": "10200", "Name": "Cash - checking", "Type": "balanceSheet", "Ending balance": 80000.0},
        {"Account": "13100", "Name": "Prepaid rent", "Type": "balanceSheet", "Ending balance": 2400.0},
        {"Account": "13200", "Name": "Prepaid software", "Type": "balanceSheet", "Ending balance": 600.0},
        {"Account": "22000", "Name": "Accrued expenses", "Type": "balanceSheet", "Ending balance": -5900.0},
        {"Account": "22500", "Name": "Accrued bonus", "Type": "balanceSheet", "Ending balance": 0.0},
        {"Account": "31000", "Name": "Retained earnings", "Type": "balanceSheet", "Ending balance": -77100.0},
        {"Account": "41000", "Name": "Sales", "Type": "incomeStatement", "Ending balance": -12000.0},
    ])
    je = month / "journal-entries"
    import_file(je / "card accrual March 2026.csv", "Card accrual Mar 2026", [1200.0, 600.0])
    import_file(je / "vendor accrual March 2026.csv", "Vendor accrual March 2026", [4000.0])
    import_file(je / "bonus accrual March 2026.csv", "Bonus accrual Mar 2026", [900.0])
    (je / "card backup.csv").write_text("Cardholder,Amount\nDana,1200\n")
    ledger(root / "2026" / "2026-02" / "work" / "source", "2026-02", [
        entry("201", "2026-02-28", "Card accrual Feb 2026", 1700.0),
        entry("202", "2026-02-28", "Rent accrual Feb 2026", 2500.0),
        entry("203", "2026-02-28", "Bonus accrual February 2026", 850.0),
        entry("204", "2026-02-28", "Reversed - Legal accrual Jan 2026", 300.0, reversed_from="2026-01-31"),
        entry("205", "2026-02-14", "Mid-month reclass", 40.0),
        entry("206", "2026-02-28", "Amortization 02/2026", 600.0),
    ])
    for name in ("10200 cash.xlsx", "prepaids.xlsx", "22000 accruals.xlsx"):
        (month / "reconciliations" / name).write_text("support\n")
    settle(month)
    return root
