"""Tests for cc_accrual.py: the MCC map by department, cardholder lookup, the unmapped queues,
the department column, merchant overrides and the balancing offset."""

from __future__ import annotations

import csv
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


cc = load("cc_accrual")

PERIOD = "2026-08"
MCC = {
    "map": {
        "5812": {"category": "MEALS", "account_by_department": {
            "FIELD": {"account": "5150", "account_name": "Field Meals"},
            "BACKOFFICE": "6150",
            "default": {"account": "6190", "account_name": "Other Meals"}}},
        "5734": {"category": "SOFTWARE", "account": "6300", "account_name": "Software"},
    },
    "department_families": {"FINANCE": "BACKOFFICE", "HR": "BACKOFFICE"},
}
PEOPLE = {"JORDAN LEE": {"department": "FIELD"}, "MARCUS HALE": {"department": "FINANCE"},
          "PRIYA NAIR": {"department": "SALES"}}
CARD = [
    {"date": "2026-08-02", "post_date": "2026-08-04", "cardholder": "JORDAN Q LEE", "merchant": "Acme Catering",
     "mcc": "5812", "amount": "1,500.00"},
    {"date": "2026-08-05", "post_date": "2026-08-07", "cardholder": "MARCUS HALE", "merchant": "Corner Deli",
     "mcc": "5812", "amount": "120.00"},
    {"date": "2026-08-07", "post_date": "2026-08-09", "cardholder": "PRIYA NAIR", "merchant": "Bistro",
     "mcc": "5812", "amount": "80.00"},
    {"date": "2026-08-12", "post_date": "2026-08-14", "cardholder": "JORDAN LEE", "merchant": "Code Host",
     "mcc": "5734", "amount": "40.00"},
]
KW = dict(liability_account="2100", unmapped_account="6990", location="100", always_vendor_named=["SOFTWARE"])


def build(rows=None, **kw):
    return cc.build(list(CARD if rows is None else rows), PERIOD, cc.as_map(MCC), cc.as_map(PEOPLE),
                    MCC["department_families"], **{**KW, **kw})


def lines(result, naming=None):
    return [ln for ln in result["proposals"][0]["lines"] if naming is None or ln["naming"] == naming]


def test_the_account_follows_department_then_family_then_default():
    by_merchant = {r["merchant"]: r["account"] for r in build()["rows"]}
    assert by_merchant == {"ACME CATERING": "5150", "CORNER DELI": "6150", "BISTRO": "6190", "CODE HOST": "6300"}


def test_cardholder_names_match_without_middle_initials_or_apostrophes():
    assert cc.normalize_person("Dana J. O'Neil") == "DANA ONEIL"
    assert cc.lookup_person({"DANA ONEIL": {"department": "HR"}}, "DANA M O NEIL") is None
    assert cc.lookup_person({"DANA O'NEIL": {"department": "HR"}}, "DANA ONEIL") == {"department": "HR"}
    assert cc.lookup_person(PEOPLE, "JORDAN ALEX LEE")["department"] == "FIELD"
    assert cc.lookup_person(PEOPLE, "NOBODY HERE") is None


def test_a_clean_month_balances_and_names_large_and_always_named_merchants():
    result = build()
    assert result["passed"] and result["ready"] and not result["unmapped_merchants"]
    named = {ln["vendor"] for ln in lines(result, "vendor")}
    assert named == {"ACME CATERING", "CODE HOST"}
    offset = lines(result, "offset")[0]
    assert offset["credit"] == result["total"] == 1740.0 and offset["account"] == "2100"
    entry = result["proposals"][0]
    assert entry["posting_date"] == "2026-08-31" and entry["reversal_date"] == "2026-09-01"


def test_unmapped_merchants_and_cardholders_are_queued_not_guessed():
    rows = CARD + [{"date": "2026-08-15", "cardholder": "SAM UNKNOWN", "merchant": "Mystery Shop",
                    "mcc": "9999", "amount": "25.00"}]
    result = build(rows)
    assert result["unmapped_merchants"] == ["MYSTERY SHOP"] and result["unmapped_cardholders"] == ["SAM UNKNOWN"]
    mystery = [r for r in result["rows"] if r["merchant"] == "MYSTERY SHOP"][0]
    assert mystery["account"] == "6990" and mystery["department"] == "GENERAL" and not result["passed"]


def test_rows_outside_the_period_or_past_the_cutoff_are_left_out():
    rows = CARD + [{"date": "2026-07-31", "cardholder": "JORDAN LEE", "merchant": "Old", "mcc": "5734",
                    "amount": "10"}]
    result = build(rows, post_date_cutoff="2026-08-10")
    assert result["excluded_by_post_date"] == 1 and len(result["rows"]) == 3


def test_the_department_column_drives_the_department_and_gaps_are_reported():
    rows = [dict(r, dept_export=label) for r, label in zip(CARD, ["field", "SALES", "", "mystery"])]
    result = build(rows, dept_labels={"Field": "FIELD", "Sales": "SALES"})
    recon = result["department_reconciliation"]
    assert recon["source"] == "column" and not recon["ready"] and not result["passed"]
    assert [r["department"] for r in result["rows"]] == ["FIELD", "SALES", "SALES", "FIELD"]
    assert recon["disagreements"][0]["cardholder"] == "MARCUS HALE"
    assert [u["label"] for u in recon["unknown_labels"]] == ["MYSTERY"]
    assert recon["blanks"][0]["cardholder"] == "PRIYA NAIR"


def test_a_merchant_override_wins_over_the_mcc():
    overrides = [{"pattern": "CODE*", "category": "HOSTING", "account": "6310"}]
    result = build(merchant_overrides=overrides)
    host = [r for r in result["rows"] if r["merchant"] == "CODE HOST"][0]
    assert host["account"] == "6310" and host["category"] == "HOSTING"
    assert result["merchant_overrides_used"] == {"CODE*": {"rows": 1, "amount": 40.0}}
    with pytest.raises(ValueError, match="no account"):
        build(merchant_overrides=[{"pattern": "X"}])


def test_the_cli_reads_the_files_writes_the_proposal_and_exits_by_readiness(tmp_path):
    card_csv = tmp_path / "card.csv"
    with card_csv.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CARD[0]))
        writer.writeheader()
        writer.writerows(CARD)
    (tmp_path / "mcc.json").write_text(json.dumps(MCC))
    (tmp_path / "people.json").write_text(json.dumps(PEOPLE))
    out = tmp_path / "proposal.json"
    args = [sys.executable, str(SCRIPTS / "cc_accrual.py"), str(card_csv), "--period", PERIOD,
            "--mcc-map", str(tmp_path / "mcc.json"), "--people-map", str(tmp_path / "people.json"),
            "--liability-account", "2100", "--unmapped-account", "6990", "--location", "100",
            "--always-vendor-named", "SOFTWARE", "--out", str(out), "--format", "json"]
    done = subprocess.run(args, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    result = json.loads(done.stdout)
    assert result["total"] == 1740.0 and json.loads(out.read_text())["proposals"] == result["proposals"]
    (tmp_path / "people.json").write_text(json.dumps({}))
    assert subprocess.run(args, capture_output=True, text=True).returncode == 1
