import json

import costing_fixtures  # noqa: F401  (puts the scripts folder on the path)
import routing_rollup as rr

CM = rr.DEFAULT_MAP


def op(mat, wc, minutes, base=""):
    return {"material": mat, "operation": "10", "work_center": wc, "minutes": str(minutes), "base_qty": str(base)}


ROUTING = [op("FG-1", "ASM1", 20, 2), op("SUB-1", "PRS1", 3), op("SUB-2", "PRS1", 1)]
BOM = [{"parent": "FG-1", "component": "SUB-1", "qty_per": "2"}, {"parent": "SUB-1", "component": "SUB-2", "qty_per": "3"}]
WC = {"ASM1": "Plant A", "PRS1": "Plant A"}


def test_own_and_linked_minutes():
    r = rr.rollup(ROUTING, BOM, WC, CM, {}, {})
    p = r["parts"][0]
    assert p["material"] == "FG-1" and p["own_min"] == 10 and p["linked_min"] == 2 * (3 + 3 * 1)
    assert r["passed"]


def test_unmapped_mixed_and_cycle():
    bom = BOM + [{"parent": "SUB-2", "component": "FG-1", "qty_per": "1"}]
    r = rr.rollup(ROUTING, bom, {"ASM1": "Plant A", "PRS1": "Plant B"}, CM, {}, {}, only={"FG-1"})
    checks = {f["check"] for f in r["findings"]}
    assert {"bom_cycle", "mixed_factory"} <= checks and not r["passed"]
    r = rr.rollup(ROUTING, BOM, {"ASM1": "Plant A"}, CM, {}, {})
    assert r["findings"][0]["check"] == "unmapped_work_center"


def test_rate_validation_tolerances():
    own = [op("FG-9", "ASM1", 10)]
    ok = rr.rollup(own, [], WC, CM, {"FG-9": 10.8}, {"Plant A": 1.0})
    assert ok["parts"][0]["verdict"] == "accept" and ok["parts"][0]["basis"] == "own"
    bad = rr.rollup(own, [], WC, CM, {"FG-9": 11.5}, {"Plant A": 1.0})
    assert bad["parts"][0]["verdict"] == "reject" and not bad["passed"]
    linked = rr.rollup(ROUTING, BOM, WC, CM, {"FG-1": 23.8}, {"Plant A": 1.0})  # 22 min, +8%
    assert linked["parts"][0]["verdict"] == "reject"
    assert rr.rollup(ROUTING, BOM, WC, CM, {"FG-1": 23.8}, {"Plant A": 1.0}, linked_tol=0.10)["passed"]


def test_cli(tmp_path, capsys):
    def write(name, text):
        (tmp_path / name).write_text(text, encoding="utf-8")
        return str(tmp_path / name)

    rt = write("rt.csv", "material,operation,work_center,minutes,base_qty\nFG-1,10,ASM1,20,2\nSUB-1,10,PRS1,3,\n")
    bom = write("bom.csv", "parent,component,qty_per\nFG-1,SUB-1,2\n")
    wc = write("wc.csv", "work_center,factory\nASM1,Plant A\nPRS1,Plant A\n")
    assert rr.main([rt, "--bom", bom, "--wc-map", wc, "--out", str(tmp_path / "o.csv"), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["parts"][0]["total_min"] == 16
    assert "FG-1" in (tmp_path / "o.csv").read_text()
    bad = write("bad.csv", "parent,child\nFG-1,SUB-1\n")
    try:
        rr.main([rt, "--bom", bad])
    except SystemExit as e:
        assert e.code == 1
    assert "DATA REQUEST" in capsys.readouterr().err
