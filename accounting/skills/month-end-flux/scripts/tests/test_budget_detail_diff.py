"""Tests for budget_detail_diff.py with an invented budget and upload sheet."""

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "budget_detail_diff.py"
sys.path.insert(0, str(SCRIPT.parent))
sys.modules.pop("_common", None)  # another skill's _common may be loaded in the same run
from budget_detail_diff import compare, freshest_forecast  # noqa: E402


def detail(bid, account, amount, month="March", dept="D10", loc="100"):
    return {"budget.id": bid, "glAccount.id": account, "dimensions.department.id": dept,
            "dimensions.location.id": loc, "reportingPeriod.id": f"Month Ended {month} 2026", "amount": str(amount)}


DETAIL = [detail("FORECAST-2026-02", "60300", 900), detail("FORECAST-2026-03", "60300", 1000),
          detail("FORECAST-2026-03", "60300", 1100, "April"), detail("FORECAST-2026-03", "61000", 50),
          detail("BUDGET", "60300", 800)]
UPLOAD = [{"BUDGET_ID": "FORECAST-2026-03", "ACCT_NO": "60300", "DEPT_ID": "D10", "LOCATION_ID": "100",
           "CLASSID": "", "Month Ended March 2026": "1,000.00", "Month Ended April 2026": "1,250",
           "Month Ended Smarch 2026": "1"},
          {"BUDGET_ID": "FORECAST-2026-03", "ACCT_NO": "62000", "DEPT_ID": "D10", "LOCATION_ID": "100",
           "CLASSID": "", "Month Ended March 2026": "75", "Month Ended April 2026": "0",
           "Month Ended Smarch 2026": ""}]


def test_freshest_forecast():
    assert freshest_forecast(["BUDGET", "FORECAST-2026-02", "FORECAST_202603", "FORECAST"]) == "FORECAST_202603"
    assert freshest_forecast(["FORECAST", "FORECAST-B"]) == "FORECAST-B"
    assert freshest_forecast(["BUDGET"]) == ""


def test_list_only():
    result = compare(DETAIL)
    assert result["freshest_forecast"] == "FORECAST-2026-03" and result["passed"]
    assert result["budgets"]["FORECAST-2026-03"] == {"rows": 3, "periods": ["2026-03", "2026-04"],
                                                     "first": "2026-03", "last": "2026-04"}


def test_diff_findings():
    result = compare(DETAIL, UPLOAD)
    found = {(f["check"], f["key"]) for f in result["findings"]}
    assert found == {("period_unparseable", "Month Ended Smarch 2026"),
                     ("amount_differs", "60300/D10/100 2026-04"),
                     ("extra_in_intacct", "61000/D10/100 2026-03"),
                     ("missing_in_intacct", "62000/D10/100 2026-03")}
    assert result["errors"] == 2 and not result["passed"]
    with pytest.raises(ValueError, match="not in the detail"):
        compare(DETAIL, UPLOAD, budget_id="NOPE")


def test_cli(tmp_path):
    (tmp_path / "detail.json").write_text(json.dumps({"meta": {}, "rows": DETAIL}))
    with (tmp_path / "upload.csv").open("w", newline="", encoding="utf-8") as fh:
        fh.write("\ufeff")  # a byte-order mark, as Excel writes
        writer = csv.DictWriter(fh, fieldnames=list(UPLOAD[0]))
        writer.writeheader()
        writer.writerows(UPLOAD)
    base = [sys.executable, str(SCRIPT), "--detail", str(tmp_path / "detail.json")]
    listed = subprocess.run(base + ["--list-budgets"], capture_output=True, text=True)
    assert listed.returncode == 0 and "<- freshest" in listed.stdout
    diffed = subprocess.run(base + ["--upload", str(tmp_path / "upload.csv")], capture_output=True, text=True)
    assert diffed.returncode == 1 and "FAIL: 2 error(s)" in diffed.stdout


def test_a_form_feed_inside_a_quoted_cell_does_not_split_the_upload_row(tmp_path):
    from _common import load_table

    path = tmp_path / "upload.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(UPLOAD[0]))
        writer.writeheader()
        writer.writerow(dict(UPLOAD[0], CLASSID="note\x0cpage two"))
    rows = load_table(path)
    assert len(rows) == 1 and rows[0]["Month Ended March 2026"] == "1,000.00"
