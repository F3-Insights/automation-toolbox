"""Tests for service_period_accrual.py: bills naming the period, arrears vendors, the
median-of-three estimate for a vendor silent at close, and one credit per location."""

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


spa = load("service_period_accrual")

PERIOD = "2026-08"


def bill(bill_id, vendor, account, amount, memo="", date="2026-09-04", dept="OPS", loc="100", intacct=False):
    """A bill line in the standard shape, or in the Sage Intacct dotted shape."""
    if intacct:
        return {"bill.id": bill_id, "bill.postingDate": date, "vendor.name": vendor, "glAccount.id": account,
                "glAccount.name": f"Acct {account}", "dimensions.department.id": dept,
                "dimensions.location.id": loc, "baseAmount": f"{amount:.2f}", "memo": memo}
    return {"doc_id": bill_id, "date": date, "posting_date": date, "counterparty": vendor, "account": account,
            "account_name": f"Acct {account}", "department": dept, "location": loc, "amount": amount, "memo": memo}


NEXT = [
    bill("N1", "LAKEVIEW HARDWARE", "6400", 1800.0, "Repairs Aug 2026"),
    bill("N2", "FABRIKAM LOGISTICS", "6500", 4200.0, "Freight services", loc="200", intacct=True),
    bill("N3", "NORTHWIND TRADERS", "6600", 700.0, "September supplies"),
    bill("N4", "LAKEVIEW HARDWARE", "1500", 950.0, "Repairs Aug 2026"),
    bill("N5", "FABRIKAM LOGISTICS", "6500", 300.0, "Freight SEP 2026"),
]
PRIOR = [
    bill("S1", "ACME COMPONENTS SERVICES", "6700", 1000.0, "May", "2026-05-12", "ADMIN"),
    bill("S2", "ACME COMPONENTS SERVICES", "6700", 2400.0, "June", "2026-06-12", "ADMIN"),
    bill("S3", "ACME COMPONENTS SERVICES", "6700", 600.0, "July", "2026-07-12", "ADMIN"),
    bill("S3", "ACME COMPONENTS SERVICES", "6200", 1400.0, "July", "2026-07-12", "ADMIN"),
]
KW = dict(liability_account="2100", location="100", arrears_vendors=["FABRIKAM", "ACME COMPONENTS SERVICES"])


def build(next_rows=None, **kw):
    next_rows = NEXT if next_rows is None else next_rows
    return spa.build(list(next_rows), PRIOR + list(next_rows), PERIOD, **{**KW, **kw})


def test_memo_naming_the_month_and_arrears_vendors_are_pulled_back():
    result = build()
    found = {(b["bill_id"], b["reason"]) for b in result["bills"] if not b["bill_id"].startswith("est:")}
    assert found == {("N1", "memo names the month"), ("N2", "arrears vendor (bills month M in M+1)")}


def test_another_months_number_must_stand_alone():
    pattern = spa.other_month_pattern(PERIOD)
    assert pattern.search("FREIGHT SEP 2026") and pattern.search("PO 9/2026")
    assert not pattern.search("PO 19/2026") and not pattern.search("MARKETING")


def test_a_silent_arrears_vendor_is_estimated_at_the_median_allocated_like_the_latest_bill():
    result = build()
    est = [b for b in result["bills"] if b["bill_id"] == "est:S3"]
    assert sorted((b["account"], b["amount"]) for b in est) == [("6200", 1400.0), ("6700", 600.0)]
    assert result["estimates"] == ["ACME COMPONENTS SERVICES"] and not result["passed"]
    assert all("ESTIMATE" in ln["memo"] for ln in result["proposals"][0]["lines"] if ln["vendor"].startswith("ACME"))


def test_one_credit_per_location_and_the_entry_reverses_on_the_first():
    entry = build()["proposals"][0]
    offsets = {ln["location"]: ln["credit"] for ln in entry["lines"] if ln["naming"] == "offset"}
    assert offsets == {"100": 3800.0, "200": 4200.0}
    assert entry["posting_date"] == "2026-08-31" and entry["reversal_date"] == "2026-09-01"
    assert entry["description"] == "To accrue August 2026 expenses received after the AP cutoff"


def test_exclusions_and_nothing_to_accrue():
    result = build(exclude_vendors=["FABRIKAM"], exclude_bills=["S3"], arrears_vendors=["ACME COMPONENTS SERVICES"])
    assert {b["bill_id"] for b in result["bills"]} == {"N1"} and result["passed"]
    assert build([bill("N9", "NORTHWIND TRADERS", "6600", 10.0, "Sept")], arrears_vendors=[])["proposals"] == []
    with pytest.raises(ValueError):
        build(liability_account="")


def test_the_cli_writes_the_proposal_and_exits_one_on_an_estimate(tmp_path):
    (tmp_path / "next.json").write_text(json.dumps({"meta": {}, "rows": NEXT}))
    (tmp_path / "prior.json").write_text(json.dumps(PRIOR))
    out = tmp_path / "proposal.json"
    base = [sys.executable, str(SCRIPTS / "service_period_accrual.py"), "--period", PERIOD,
            "--next-bills", str(tmp_path / "next.json"), "--bills", str(tmp_path / "prior.json"),
            "--liability-account", "2100", "--location", "100", "--arrears-vendor", "FABRIKAM",
            "--format", "json"]
    done = subprocess.run(base + ["--arrears-vendor", "ACME COMPONENTS SERVICES", "--out", str(out)],
                          capture_output=True, text=True)
    assert done.returncode == 1, done.stderr
    assert json.loads(done.stdout)["counts"]["estimate (arrears vendor, unbilled at close)"] == 2
    assert json.loads(out.read_text())["total"] == 8000.0
    assert subprocess.run(base, capture_output=True, text=True).returncode == 0
