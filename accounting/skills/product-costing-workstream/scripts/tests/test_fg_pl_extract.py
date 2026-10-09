import json

import pytest

from costing_fixtures import block, build, tb_row, write_layout

import fg_pl_extract

INFO = ["Retail", "Northwind Traders", "AC-100", "Bracket, steel"]


def run(tmp_path, capsys, *extra):
    code = fg_pl_extract.main([str(tmp_path / "model.xlsx"), "--year", "2026", "--layout", str(write_layout(tmp_path)), *extra])
    return code, capsys.readouterr()


def test_reconcile_tolerance():
    fg = [{"basis": "month", "sales_amount": 10000.0}]
    assert fg_pl_extract.reconcile(fg, [{"category": "Sales", "amount": 10004.0}], "Sales")["status"] == "green"
    assert fg_pl_extract.reconcile(fg, [{"category": "Sales", "amount": 10100.0}], "Sales")["status"] == "red"


def test_extract_ties_and_flags_cost_pending(tmp_path, capsys):
    build(tmp_path / "model.xlsx",
          green=[(INFO, [block(1000.0, 600.0), block(500.0, 300.0)]),
                 (["Retail", "Northwind Traders", "AC-200", "Hinge"], [block(200.0, 0.0, cm_pct=1.0)]),
                 ([None, None, None, "Subtotal"], [block(1700.0, 900.0)])],
          tb=[tb_row("Sales", [1200.0, 500.0])])
    code, out = run(tmp_path, capsys)
    r = json.loads(out.out)
    assert code == 0
    assert r["products"] == 2 and r["cost_pending"] == 1
    assert len(r["fct_fg_pl"]) == 3 and len(r["fct_tb"]) == 12
    pending = [x for x in r["fct_fg_pl"] if x["product_fg"] == "AC-200"][0]
    assert pending["cost_pending"] and pending["cm_pct"] is None
    assert r["reconciliation"]["status"] == "green"


def test_out_dir_and_red_tie_exits_one(tmp_path, capsys):
    build(tmp_path / "model.xlsx", green=[(INFO, [block(1000.0, 600.0)])], tb=[tb_row("Sales", [900.0])])
    code, out = run(tmp_path, capsys, "--out", str(tmp_path / "work"))
    assert code == 1 and "RED" in out.out
    assert (tmp_path / "work" / "fct_fg_pl.csv").exists()
    assert json.loads((tmp_path / "work" / "reconciliation.json").read_text())["difference"] == 100.0


def test_missing_tab_fails(tmp_path, capsys):
    build(tmp_path / "model.xlsx", green=[(INFO, [block(1000.0, 600.0)])], tb=[])
    with pytest.raises(SystemExit) as e:
        run(tmp_path, capsys, "--month-tab", "No such tab")
    assert e.value.code == 1 and "Tabs not found" in capsys.readouterr().err


def test_no_layout_exits_two(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "none.toml"))
    (tmp_path / "model.xlsx").write_bytes(b"x")
    with pytest.raises(SystemExit) as e:
        fg_pl_extract.main([str(tmp_path / "model.xlsx"), "--year", "2026"])
    assert e.value.code == 2 and "cost_model_layout" in capsys.readouterr().err
