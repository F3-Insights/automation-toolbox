import json

import pytest

import costing_fixtures  # noqa: F401  (puts the scripts folder on the path)
import prodqty_check as pq

CM = pq.DEFAULT_MAP
PRODUCTS = ["AC-100", "AC-200", "AC-300", "AC-400", "AC-500", "AC-600"]


def qrows(month_qty):
    return [{"product": p, "month": m, "prod_qty": str(q)} for m, by in month_qty.items() for p, q in by.items()]


def test_clean_data_passes():
    r = pq.check_quantities(qrows({"2026-01": {p: i + 1 for i, p in enumerate(PRODUCTS)}, "2026-02": {p: i + 10 for i, p in enumerate(PRODUCTS)}}), CM)
    assert r["passed"] and r["products"] == 6


def test_carry_forward_and_floor():
    same = {p: 7 for p in PRODUCTS}
    r = pq.check_quantities(qrows({"2026-01": same, "2026-02": same}), CM)
    assert [f["check"] for f in r["findings"]] == ["carry_forward"]
    few = {p: 7 for p in PRODUCTS[:4]}
    assert pq.check_quantities(qrows({"2026-01": few, "2026-02": few}), CM)["passed"]


def test_duplicate_key():
    rows = qrows({"2026-01": {"AC-100": 5}}) * 2
    r = pq.check_quantities(rows, CM)
    assert r["findings"][0]["check"] == "duplicate_key" and not r["passed"]


def test_movements_and_standards():
    rows = qrows({"2026-01": {"AC-100": 5, "AC-200": -2}})
    moves = [{"product": "AC-100", "month": "2026-01", "qty": "8"}, {"product": "AC-100", "month": "2026-01", "qty": "-3"},
             {"product": "AC-200", "month": "2026-01", "qty": "-2"}]
    r = pq.check_quantities(rows, CM, movements=moves, standards=[{"product": "AC-100"}])
    checks = [(f["check"], f.get("product")) for f in r["findings"]]
    assert ("negative_net", "AC-200") in checks and ("no_labor_standard", "AC-200") in checks
    assert not any(c == "movement_recon" for c, _ in checks)
    r = pq.check_quantities(rows, CM, movements=[{"product": "AC-100", "month": "2026-01", "qty": "9"}])
    assert r["findings"][0]["check"] == "movement_recon"


def test_cli(tmp_path, capsys):
    f = tmp_path / "q.csv"
    f.write_text("﻿Part,Period,Made\nAC-100,2026-01,5\nAC-100,2026-01,5\n", encoding="utf-8")
    assert pq.main([str(f), "--map", "product=Part,month=Period,prod_qty=Made", "--format", "json"]) == 1
    assert json.loads(capsys.readouterr().out)["errors"] == 1
    with pytest.raises(SystemExit) as e:
        pq.main([str(f)])
    assert e.value.code == 1 and "DATA REQUEST" in capsys.readouterr().err
    with pytest.raises(SystemExit) as e:
        pq.main([str(f), "--map", "colour=Part"])
    assert e.value.code == 2
