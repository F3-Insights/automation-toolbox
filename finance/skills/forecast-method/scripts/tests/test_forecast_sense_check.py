import json

import forecast_bridge
import forecast_sense_check
from conftest import open_vintage, set_vintage, write_hypotheses


def test_a_restated_month_is_material_and_ids_are_stable(folder):
    vdir = open_vintage(folder)
    set_vintage(vdir, last_actual_month="2027-06", prior_last_actual_month="2027-06")
    new = json.loads((vdir / "work/source/new.json").read_text())
    for row in new["rows"]:
        if row["account"] == "62000":
            row["amounts"]["2027-02"] = 7000.0          # a closed month moved
    (vdir / "work/source/new.json").write_text(json.dumps(new))
    flags = forecast_sense_check.build(folder, "rev5")["flags"]
    restated = [f for f in flags if f["kind"] == "restated"]
    assert restated and restated[0]["account"] == "62000" and restated[0]["severity"] == "material"
    assert not any(f["kind"] == "sign" and f["account"] == "48000" for f in flags)    # exempt by prefix
    assert [f["id"] for f in flags] == [f["id"] for f in forecast_sense_check.build(folder, "rev5")["flags"]]


def test_a_big_miss_is_a_material_flag(folder, capsys):
    vdir = open_vintage(folder)
    write_hypotheses(vdir, revenue=-90000.0)
    forecast_bridge.main([str(folder), "--vintage", "rev5"])
    assert forecast_sense_check.main([str(folder), "--vintage", "rev5"]) == 0
    flags = json.loads((vdir / "flags.json").read_text())["flags"]
    miss = [f for f in flags if f["kind"] == "hypothesis_miss" and f["line"] == "revenue"]
    assert miss and miss[0]["severity"] == "material"
    assert "hypothesis_miss" in capsys.readouterr().out
