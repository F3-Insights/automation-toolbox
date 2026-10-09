"""Tests for month_end_check.py on the invented Northwind folder."""

import json
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.modules.pop("_common", None)  # another skill's _common may be loaded in the same run
from month_end_fixture import CHECKLIST, PERIOD, entry, settle

import month_end_check as mec
from month_end_record import record

SCRIPT = Path(mec.__file__)
TODAY = date(2026, 4, 3)


def rec(root, test, item, state, **kw):
    return record(root, PERIOD, test, item, state, "month-end-reviewer", **kw)


def month(root):
    return root / "2026" / PERIOD


def cli(root, *args):
    return subprocess.run([sys.executable, str(SCRIPT), str(root), "--today", TODAY.isoformat(), *args],
                          capture_output=True, text=True)


def complete(root):
    m = month(root)
    rec(root, "entries", "card", "booked", evidence="JE 301", review="PASS")
    rec(root, "entries", "vendor", "booked", evidence="JE 302", review="PASS")
    rec(root, "entries", "bonus", "not-needed", review="PASS")
    (m / "journal-entries" / "bonus accrual March 2026.csv").unlink()
    rec(root, "reconciliations", "10200", "reconciled", evidence="reconciliations/10200 cash.xlsx", amount="80000", review="PASS")
    rec(root, "reconciliations", "13000-13999", "reconciled", evidence="reconciliations/prepaids.xlsx", amount="3000", review="PASS")
    rec(root, "reconciliations", "22000", "reconciled", evidence="reconciliations/22000 accruals.xlsx", amount="-5,900", review="PASS")
    procedures = root / "MONTH-END-PROCEDURES.md"
    procedures.write_text(procedures.read_text().replace("| 22000, 22500 |", "| 31000 | Retained earnings | cash | |\n| 22000, 22500 |"))
    rec(root, "reconciliations", "31000", "reconciled", evidence="reconciliations/10200 cash.xlsx", amount="-77100", review="PASS")
    (m / "reporting" / f"MONTH-END-FINDINGS-{PERIOD}.md").write_text("# Findings\n\n- 62000 up on the trade show.\n")
    rec(root, "flux", "pl", "explained", review="PASS")
    status = m / "STATUS.md"
    status.write_text(status.read_text().replace("| 2026-03-30 | open | | |", "| 2026-03-30 | answered | No | 2026-04-01 |"))


def test_period_from_root_status_and_text_output(folder):
    data = json.loads(cli(folder, "--format", "json").stdout)
    assert data["period"] == PERIOD and data["done"] is False
    assert data["pull"] == {"date": "2026-04-02", "preliminary": True, "note": ""}
    text = cli(folder).stdout
    assert "Pull: 2026-04-02 PRELIMINARY" in text and "Close: NOT DONE" in text
    assert all(n in text for n in ("1 entries", "2 reconciliations", "3 flux", "4 questions"))


@pytest.mark.parametrize("args", [["missing"], ["{root}", "--period", "March"], ["{root}", "--period", "2025-01"]])
def test_bad_arguments_exit_2(folder, args):
    run = subprocess.run([sys.executable, str(SCRIPT), *[a.replace("{root}", str(folder)) for a in args]],
                         capture_output=True, text=True)
    assert run.returncode == 2


def test_drafts_matched_to_pull(folder):
    t = mec.check(folder, today=TODAY)["tests"]["entries"]
    by_file = {Path(d["file"]).name: d for d in t["drafts"]}
    assert len(by_file) == 3  # the backup CSV has no DEBIT/CREDIT columns
    card = by_file["card accrual March 2026.csv"]
    assert (card["status"], card["je"], card["debits"]) == ("posted-matching", "301", 1800.0)
    vendor = by_file["vendor accrual March 2026.csv"]
    assert (vendor["status"], vendor["posted_debits"]) == ("posted-different", 4100.0)
    assert by_file["bonus accrual March 2026.csv"]["status"] == "not-posted"
    assert "no entries rows in the evidence file" in t["gaps"]
    assert [c["description"] for c in t["recurring_candidates"]] == ["Rent accrual Feb 2026"]


def test_entered_but_not_posted(folder):
    path = month(folder) / "work" / "source" / f"headers-{PERIOD}.json"
    data = json.loads(path.read_text())
    data["rows"].append(entry("305", "2026-03-31", "Bonus accrual Mar 2026", 900.0, state="draft")[0])
    path.write_text(json.dumps(data))
    bonus = [d for d in mec.check(folder, today=TODAY)["tests"]["entries"]["drafts"] if "bonus" in d["file"]][0]
    assert bonus["status"] == "not-posted" and "JE 305 is in the ledger as draft" in bonus["note"]


def test_no_prior_pull_skips_recurring(folder):
    for path in (folder / "2026" / "2026-02" / "work" / "source").iterdir():
        path.unlink()
    t = mec.check(folder, today=TODAY)["tests"]["entries"]
    assert t["recurring_candidates"] == [] and "no 2026-02 pull" in t["recurring_note"]


def test_describe():
    assert mec.describe("To accrue RENT Sept. 2026") == mec.describe("to accrue rent - August 2025")
    assert mec.describe("Reversed - Amortization 03/2026") == "amortization"


def test_reconciliations(folder):
    t = mec.check(folder, today=TODAY)["tests"]["reconciliations"]
    assert t["counts"] == {"accounts": 5, "reconciled": 0, "unassigned": 1}
    assert any(g.startswith("unassigned: 31000 Retained earnings") for g in t["gaps"])
    rec(folder, "reconciliations", "13000-13999", "reconciled", evidence="reconciliations/prepaids.xlsx", amount="3000", review="PASS")
    rec(folder, "reconciliations", "13200", "reconciled", evidence="reconciliations/prepaids.xlsx", amount="600", review="PASS")
    rec(folder, "reconciliations", "22000", "reconciled", evidence="reconciliations/gone.xlsx", amount="-5900", review="FAIL")
    items = {it["item"]: it for it in mec.check(folder, today=TODAY)["tests"]["reconciliations"]["items"]}
    assert items["13200"]["ok"] and items["13000-13999"]["accounts"] == ["13100"]
    assert "stale: reconciled at 3,000.00, ledger now 2,400.00" in items["13000-13999"]["problems"]
    assert {"file missing: reconciliations/gone.xlsx", "review FAIL, not PASS"} <= set(items["22000"]["problems"])
    assert items["10200"]["problems"] == ["no evidence row"]
    assert mec.in_spec("13500", mec.account_spec("13000 - 13999"))
    assert not mec.in_spec("22100", mec.account_spec("22000, 22500"))


def test_flux_and_questions(folder):
    t = mec.check(folder, today=TODAY)["tests"]
    assert any("nothing beyond its heading" in g for g in t["flux"]["gaps"])
    assert t["questions"]["open"] == [{"id": "Q1", "question": "Is the bonus accrual still needed?",
                                       "asked_of": "Controller", "state": "open", "age_days": 4}]
    rec(folder, "flux", "pl", "explained")
    assert "flux:pl explained/no review" in mec.check(folder, today=TODAY)["tests"]["flux"]["gaps"][-1]


def test_complete_close_is_done(folder):
    complete(folder)
    data = json.loads(cli(folder, "--format", "json").stdout)
    assert data["done"] is True, {n: t["gaps"] for n, t in data["tests"].items()}
    assert cli(folder, "--precheck").stdout.startswith("NOTHING: close done")


def test_precheck_triggers(folder):
    first = cli(folder, "--precheck").stdout.splitlines()
    assert first[0].startswith("WORK: ") and "1 agent-owned checklist row(s) open and due" in first[0]
    assert "  due: 2 Draft the card accrual (due 2026-04-02)" in first
    m = month(folder)
    (m / f"MONTH-END-PROCEDURES-{PERIOD}.md").write_text(CHECKLIST.replace("2026-04-02 | open", "2026-04-02 | done"))
    settle(m)
    assert cli(folder, "--precheck").stdout.startswith("NOTHING: 2026-03 close open")
    later = datetime(2026, 4, 3, 8, 0).timestamp()
    os.utime(m / "reconciliations" / "prepaids.xlsx", (later, later))
    out = cli(folder, "--precheck").stdout
    assert out.startswith("WORK: 1 file(s) changed") and "changed: reconciliations/prepaids.xlsx" in out


def test_a_non_numeric_income_statement_balance_is_ignored(folder):
    # Only balance-sheet rows are parsed; text on an income-statement row must not stop the check.
    path = month(folder) / "work" / "source" / f"trial-balance-{PERIOD}.json"
    data = json.loads(path.read_text())
    data["rows"].append({"Account": "49000", "Name": "Memo total", "Type": "incomeStatement", "Ending balance": "n/a"})
    path.write_text(json.dumps(data))
    t = mec.check(folder, today=TODAY)["tests"]["reconciliations"]
    assert t["counts"]["accounts"] == 5
