"""Tests for recurring_je_scan.py: presence by schedule key and by folded description, and
the classes that say whether an absence is a miss or an explained exception."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

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


rjs = load("recurring_je_scan")

PERIOD = "2026-08"
SPECS = [
    {"id": "A", "name": "Insurance accrual", "journal": "GJ", "typical_amount": 900,
     "match": {"description_contains": ["TO ACCRUE INSURANCE"]}},
    {"id": "B", "name": "Depreciation", "journal": "GJ", "mechanism": "scheduled",
     "match": {"scheduled_operation_key": "SCH-7"}},
    {"id": "C", "name": "Commission accrual", "conditional": True, "condition": "only in a quarter-end month",
     "match": {"description_contains": ["TO ACCRUE COMMISSION"]}},
    {"id": "D", "name": "Royalty true-up", "retired": True, "mechanism": "odd",
     "match": {"description_contains": ["ROYALTY TRUE UP"]}},
    {"id": "E", "name": "Software amortization", "journal": "GJ",
     "match": {"description_contains": ["TO AMORTIZE SOFTWARE"]}},
]


def header(key, desc, date="2026-08-31", journal="GJ", state="Posted", **extra):
    return {"je_id": key, "journal": journal, "date": date, "description": desc, "state": state, **extra}


HEADERS = [
    header("1", "To accrue Insurance AUGUST 2026"),
    header("2", "Monthly depreciation", schedule_id="SCH-7"),
    header("3", "Reversed - To amortize software JULY 2026", date="2026-08-01", reversed_from="2026-07-31"),
    header("4", "To record bank fees JUNE 2026", date="2026-06-30"),
    header("5", "To record bank fees JULY 2026", date="2026-07-31"),
    header("6", "To record bank fees AUGUST 2026"),
]
# Lines in the Sage Intacct dotted shape, to prove both shapes are read.
LINES = [{"journalEntry.key": k, "baseAmount": f"{a:.2f}", "txnType": t, "glAccount.id": "6100"}
         for k, a, t in [("1", 900, "debit"), ("1", 900, "credit"), ("2", 250, "debit"), ("2", 250, "credit"),
                         ("4", 30, "debit"), ("5", 35, "debit"), ("6", 40, "debit")]]


def scan(headers=None, specs=None):
    return rjs.scan(list(HEADERS if headers is None else headers), LINES, list(SPECS if specs is None else specs),
                    PERIOD, manual_journals=["GJ"])


def by_id(result):
    return {e["id"]: e for e in result["entries"]}


def test_each_entry_is_found_or_classified():
    entries = by_id(scan())
    assert (entries["A"]["status"], entries["A"]["detection"], entries["A"]["amount"]) == ("present", "description", 900.0)
    assert entries["A"]["expected_amount"] == 900.0
    assert (entries["B"]["status"], entries["B"]["detection"]) == ("present", "scheduled_op")
    assert entries["C"]["status"] == "exception" and "quarter-end" in entries["C"]["note"]
    assert entries["D"]["status"] == "exception" and entries["D"]["mechanism"] == "manual"
    assert entries["E"]["status"] == "missing"  # the reversal of July never counts as August


def test_an_unposted_entry_is_present_and_flagged():
    headers = [header("1", "To accrue insurance AUG 2026", state="Draft")] + HEADERS[1:]
    entry = by_id(scan(headers))["A"]
    assert entry["status"] == "present" and "NOT POSTED (draft)" in entry["note"]


def test_an_unlisted_recurrence_is_reported_so_the_list_can_grow():
    result = scan()
    assert [g["pattern"] for g in result["unmatched_recurring"]] == ["TO RECORD BANK FEES <M> <N>"]
    assert result["unmatched_recurring"][0]["typical_amount"] == 35.0
    assert result["missing"] == ["E"] and not result["passed"]


def test_the_cli_reads_yaml_and_exits_by_whether_anything_is_missing(tmp_path):
    pytest.importorskip("yaml")
    (tmp_path / "h.json").write_text(json.dumps({"meta": {}, "rows": HEADERS}))
    (tmp_path / "l.json").write_text(json.dumps(LINES))
    import yaml
    (tmp_path / "list.yaml").write_text(yaml.safe_dump({"entries": SPECS}))
    (tmp_path / "list.json").write_text(json.dumps(SPECS[:4]))
    base = [sys.executable, str(SCRIPTS / "recurring_je_scan.py"), "--period", PERIOD, "--headers",
            str(tmp_path / "h.json"), "--lines", str(tmp_path / "l.json"), "--manual-journal", "GJ"]
    done = subprocess.run(base + ["--standard-jes", str(tmp_path / "list.yaml"), "--format", "json"],
                          capture_output=True, text=True)
    assert done.returncode == 1 and json.loads(done.stdout)["missing"] == ["E"]
    assert subprocess.run(base + ["--standard-jes", str(tmp_path / "list.json")],
                          capture_output=True, text=True).returncode == 0
    gone = subprocess.run(base + ["--standard-jes", str(tmp_path / "none.yaml")], capture_output=True, text=True)
    assert gone.returncode == 2 and "does not exist" in gone.stderr
