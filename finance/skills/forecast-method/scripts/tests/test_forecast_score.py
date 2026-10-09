import json

import forecast_bridge
import forecast_score
from conftest import open_vintage, write_hypotheses


def test_scores_and_the_calibration_log_is_appended_once(folder, capsys):
    vdir = open_vintage(folder)
    assert forecast_score.main([str(folder), "--vintage", "rev5"]) == 1          # nothing to score yet
    write_hypotheses(vdir)
    forecast_bridge.main([str(folder), "--vintage", "rev5"])
    capsys.readouterr()
    assert forecast_score.main([str(folder), "--vintage", "rev5", "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    revenue = next(s for s in data["scores"] if s["line"] == "revenue")
    assert revenue["expected"] == 30000.0 and revenue["actual"] == 40000.0 and revenue["within_tolerance"]
    fy = next(s for s in data["scores"] if s["line"] == "fy_ebitda")
    assert fy["expected"] == 18000.0 and fy["actual"] == 28000.0
    forecast_score.main([str(folder), "--vintage", "rev5"])
    assert len((folder / "calibration.jsonl").read_text().splitlines()) == len(data["scores"])
