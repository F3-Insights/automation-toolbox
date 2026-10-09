import json

import forecast_bridge
from _common import build_bridge, overlaps, owner_of
from conftest import MODULES, open_vintage, set_vintage
import yaml


def test_the_bridge_walks_and_foots(folder):
    vdir = open_vintage(folder)
    assert forecast_bridge.main([str(folder), "--vintage", "rev5"]) == 0
    bridge = json.loads((vdir / "bridge.json").read_text())
    year = bridge["years"]["2027"]
    walk = {l["key"]: l["amount"] for l in year["walk"]}
    assert walk["revenue"] == 40000.0              # 8k x five months
    assert walk["outside"] == -12000.0             # 4k x Q4, unfavourable
    assert walk["staff"] == 0.0 and walk["unclaimed"] == 0.0
    assert year["fy_change"] == 28000.0
    assert {q["quarter"]: q["change"] for q in year["quarters"]} == {"Q1'27": 0, "Q2'27": 0, "Q3'27": 16000, "Q4'27": 12000}
    assert all(c["ok"] for c in bridge["foots"])
    assert "| Wholesale and online revenue | Sales director | 40.0 |" in (vdir / "bridge.md").read_text()


def test_closed_months_split_out_and_unowned_accounts_go_to_unclaimed(folder):
    vdir = open_vintage(folder)
    set_vintage(vdir, last_actual_month="2027-09", prior_last_actual_month="2027-06")
    (folder / "modules.yaml").write_text(yaml.safe_dump(
        {"modules": [m for m in MODULES["modules"] if m["key"] != "outside"]}))
    walk = {l["key"]: l for l in build_bridge(folder, "rev5")["years"]["2027"]["walk"]}
    assert walk["restated"]["amount"] == 0.0
    assert walk["actuals"]["amount"] == 16000.0 and walk["actuals"]["months"] == ["2027-07", "2027-08", "2027-09"]
    assert walk["revenue"]["amount"] == 24000.0
    assert walk["unclaimed"]["amount"] == -12000.0
    assert [a["account"] for a in walk["unclaimed"]["accounts"]] == ["66000"]


def test_overlapping_prefixes_are_reported():
    modules = [{"key": "a", "accounts": ["5"]}, {"key": "b", "accounts": ["5", "52"]}]
    assert owner_of("52000", modules)["key"] == "b"
    assert owner_of("51000", modules)["key"] == "a"
    assert overlaps(modules) == ["5 (a and b)"]
