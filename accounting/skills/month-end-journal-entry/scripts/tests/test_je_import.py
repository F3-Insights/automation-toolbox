"""Tests for je_import.py and je_import_check.py: the Intacct 28-column layout and its checks.

Each check gets an invented entry with one planted defect.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent


def load(name):
    """Import a script of this skill by file, with its own _common beside it."""
    sys.modules.pop("_common", None)
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location(f"je_{name}", SCRIPTS / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPTS))


je = load("je_import")
chk = load("je_import_check")
common = sys.modules["_common"]

ENTRY = {
    "journal": "GJ", "description": "To accrue August rent, Acme Components",
    "posting_date": "2026-08-31", "reversal_date": "2026-09-01",
    "lines": [
        {"account": "6100", "location": "100", "department": "ADMIN", "memo": "Accrued rent", "debit": 2500.0},
        {"account": "2100", "location": "100", "department": "ADMIN", "memo": "Offset", "credit": 2500.0},
    ],
}


def checks(findings):
    return {f["check"] for f in findings}


def run(script, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True)


def test_dates_are_m_d_yyyy_without_leading_zeros():
    assert common.intacct_date("2026-08-01") == "8/1/2026"
    assert common.intacct_date("2026-12-25") == "12/25/2026"
    assert common.intacct_date("") == ""


def test_header_fields_on_the_first_line_only_and_line_numbers_restart():
    rows = je.build_rows([ENTRY, ENTRY], "2026-09-01")
    assert rows[0]["JOURNAL"] == "GJ" and rows[0]["STATE"] == "Posted"
    assert rows[1]["JOURNAL"] == "" and rows[1]["DATE"] == "" and rows[1]["STATE"] == ""
    assert [r["LINE_NO"] for r in rows] == [1, 2, 1, 2]
    assert common.check_rows(rows, "2100", "Posted") == []


def test_a_negative_debit_moves_to_the_credit_column():
    rows = je.build_rows([{**ENTRY, "lines": [{"account": "6100", "debit": -25.0}]}], "2026-09-01")
    assert rows[0]["DEBIT"] == "" and rows[0]["CREDIT"] == "25.00"


def test_each_planted_defect_is_caught():
    rows = je.build_rows([ENTRY], "2026-09-01")
    rows[1]["JOURNAL"] = "GJ"
    assert "header_on_first_line" in checks(common.check_rows(rows))
    rows = je.build_rows([ENTRY], "2026-09-01")
    rows[0]["DATE"] = "2026-08-31"
    assert "date_format" in checks(common.check_rows(rows))
    rows = je.build_rows([ENTRY], "2026-09-01")
    rows[1]["LINE_NO"] = 3
    assert "line_no_restart" in checks(common.check_rows(rows))
    rows = je.build_rows([ENTRY], "2026-09-01")
    rows[0]["DEBIT"] = "-2500.00"
    assert "never_negative" in checks(common.check_rows(rows))
    rows = je.build_rows([{**ENTRY, "reversal_date": "2026-09-15"}], "2026-09-01")
    assert "reverse_date_next_month" in checks(common.check_rows(rows))


def test_each_entity_needs_its_own_offset():
    two = {**ENTRY, "lines": [
        {"account": "6100", "location": "100", "debit": 500.0},
        {"account": "6100", "location": "200", "debit": 300.0},
        {"account": "2100", "location": "100", "credit": 800.0},
    ]}
    findings = common.check_rows(je.build_rows([two], "2026-09-01"), "2100")
    assert any(f["check"] == "liability_offset_per_entity" and "entity 200" in f["where"] for f in findings)
    two["lines"] = two["lines"][:2] + [{"account": "2100", "location": "100", "credit": 500.0},
                                       {"account": "2100", "location": "200", "credit": 300.0}]
    assert common.check_rows(je.build_rows([two], "2026-09-01"), "2100") == []


def test_the_cli_writes_a_posted_file_that_the_check_passes(tmp_path):
    src = tmp_path / "proposals.json"
    src.write_text(json.dumps({"period": "2026-08", "proposals": [ENTRY]}))
    out = tmp_path / "out.csv"
    done = run("je_import.py", str(src), "--out", str(out), "--liability-account", "2100", "--format", "json")
    assert done.returncode == 0, done.stderr
    result = json.loads(done.stdout)
    assert result["je_count"] == 1 and result["line_count"] == 2 and "rows" not in result
    with out.open(newline="") as handle:
        assert next(csv.reader(handle)) == common.COLUMNS
    lint = run("je_import_check.py", str(out), "--liability-account", "2100", "--state", "Posted",
               "--format", "json")
    assert lint.returncode == 0
    assert json.loads(lint.stdout)["total_debits"] == 2500.0


def test_a_missing_period_is_a_usage_error(tmp_path):
    src = tmp_path / "proposals.json"
    src.write_text(json.dumps([{"lines": []}]))
    done = run("je_import.py", str(src))
    assert done.returncode == 2 and "period" in done.stderr


def test_a_file_without_proposals_is_refused_not_passed_empty(tmp_path):
    # A mis-keyed file must not become an empty import file that reports PASS.
    source = tmp_path / "wrong.json"
    source.write_text(json.dumps({"period": "2026-08", "entries": [ENTRY]}))
    done = run("je_import.py", str(source), "--out", str(tmp_path / "out.csv"))
    assert done.returncode == 2
    assert "proposals" in done.stderr
    assert not (tmp_path / "out.csv").exists()
