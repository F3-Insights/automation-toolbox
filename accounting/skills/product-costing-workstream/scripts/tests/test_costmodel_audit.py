import json

import pytest

from costing_fixtures import LAYOUT, block, build, tb_row, write_layout

import costmodel_audit as ca

INFO = ["Retail", "Lakeview Hardware", "AC-100", "Bracket, steel"]


def fg_row(product, month, basis="month", **fields):
    return {"product_fg": product, "month_no": month, "basis": basis, "_raw_cm_pct": None, **fields}


def test_duplicates_month_basis_only():
    rows = [fg_row("A", 1), fg_row("A", 1), fg_row("B", 1, basis="ytd"), fg_row("B", 1, basis="ytd")]
    assert [f["product"] for f in ca.check_duplicates(rows)] == ["A"]


def test_margin_checks():
    assert ca.check_margins([fg_row("A", 1, sales_amount=100.0, total_cost=60.0, cm=40.0, cm_pct=0.4)]) == []
    assert ca.check_margins([fg_row("A", 1, sales_amount=100.0, total_cost=60.0, cm=50.0)])
    assert ca.check_margins([fg_row("A", 1, sales_amount=100.0, total_cost=60.0, cm=40.0, cm_pct=0.5)])
    pending = fg_row("A", 1, sales_amount=100.0, total_cost=0.0, cost_pending=True)
    assert ca.check_margins([{**pending, "_raw_cm_pct": 1.0}])
    assert ca.check_margins([pending]) == []


def test_ytd_equals_sum():
    rows = [fg_row("A", 1, sales_amount=100.0, total_cost=50.0), fg_row("A", 2, sales_amount=100.0, total_cost=50.0)]
    assert ca.check_ytd(rows + [fg_row("A", 2, "ytd", sales_amount=200.0, total_cost=100.0)]) == []
    assert ca.check_ytd(rows + [fg_row("A", 2, "ytd", sales_amount=250.0, total_cost=100.0)])


def test_std_var_ties_tb_with_map():
    fg = [fg_row("A", 3, std_dm=70.0, var_dm=5.0)]
    tb = [{"category": "Materials", "subcategory": None, "month_no": 3, "amount": 75.0}]
    assert ca.check_std_var_tb(fg, tb, 3, {}, ["dm"])
    assert ca.check_std_var_tb(fg, tb, 3, {"dm": ["Materials"]}, ["dm"]) == []
    assert ca.cost_components(LAYOUT) == ["dm", "dl", "voh", "foh"]


def model(tmp_path, alloc=None, extra_tabs=None, tb_amount=1000.0):
    return build(tmp_path / "model.xlsx", green=[(INFO, [block(1000.0, 600.0)])],
                 tb=[tb_row("Sales", [tb_amount])], alloc=alloc, extra_tabs=extra_tabs)


def run(tmp_path, capsys, *extra):
    code = ca.main([str(tmp_path / "model.xlsx"), "--year", "2026", "--month", "1", "--layout", str(write_layout(tmp_path)), "--format", "json", *extra])
    return code, json.loads(capsys.readouterr().out)


def test_clean_workbook_passes(tmp_path, capsys):
    model(tmp_path)
    code, r = run(tmp_path, capsys)
    assert code == 0 and r["passed"] and len(r["sha256"]) == 64
    assert [f["check"] for f in r["findings"]] == ["wrong_month_refs"]  # no allocation tab: info only


def test_wrong_month_reference_fails(tmp_path, capsys):
    # month 1 sits in column D of the ledger tab; column E is month 2
    model(tmp_path, alloc={"A1": "='Ledger'!$E$5*2", "A2": "=Ledger!D5"})
    code, r = run(tmp_path, capsys)
    bad = [f for f in r["findings"] if f["check"] == "wrong_month_refs"]
    assert code == 1 and len(bad) == 1 and "Ledger month 2" in bad[0]["detail"]


def test_cached_error_and_pools(tmp_path, capsys):
    model(tmp_path, extra_tabs={"Plant A": [tb_row("Sales", [600.0])], "Plant B": [tb_row("Sales", [300.0]), ["#REF!"]]})
    code, r = run(tmp_path, capsys, "--pool-tabs", "Plant A,Plant B", "--consolidated-tab", "Ledger")
    checks = {f["check"] for f in r["findings"]}
    assert code == 1 and {"cached_errors", "factory_pools_sum"} <= checks
