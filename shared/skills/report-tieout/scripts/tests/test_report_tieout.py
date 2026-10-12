"""Tests for report_tieout.py, with an invented three-report package."""

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "report_tieout.py"
sys.path.insert(0, str(SCRIPT.parent))
from report_tieout import parse_value, read_ledger, tieout  # noqa: E402

ROWS = [
    {"file": "memo.html", "period": "2026-03", "metric": "Consolidated EBITDA", "value": "$2.4M", "location": "p1"},
    {"file": "deck.pptx", "period": "2026-03", "metric": "Consolidated EBITDA", "value": "2,400,000", "location": "slide 3"},
    {"file": "lender.pdf", "period": "2026-03", "metric": "Consolidated EBITDA", "value": "2400000", "location": "p7"},
]


def write(tmp_path, rows):
    path = tmp_path / "ledger.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        fh.write("\ufeff")  # a byte-order mark, as Excel writes
        writer = csv.DictWriter(fh, fieldnames=["file", "period", "metric", "value", "location"])
        writer.writeheader()
        writer.writerows(rows)
    return path


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)


@pytest.mark.parametrize("raw,expected", [
    ("1200", 1200.0), ("$1,200.50", 1200.5), ("$1.2M", 1_200_000.0), ("(450)", -450.0),
    ("$(74)k", -74_000.0), ("($74k)", -74_000.0), ("−74.5", -74.5), ("-450", -450.0),
    ("n/a", None), ("", None),
])
def test_parse_value(raw, expected):
    assert parse_value(raw) == expected


def test_all_tie(tmp_path):
    result = tieout(read_ledger(write(tmp_path, ROWS)), "Consolidated EBITDA", 1.0)
    assert result["passed"] and result["findings"] == []


def test_spread_beyond_tolerance(tmp_path):
    rows = ROWS[:2] + [{**ROWS[2], "value": "2,405,000"}]
    result = tieout(read_ledger(write(tmp_path, rows)), None, 1.0)
    disagree = [f for f in result["findings"] if f["check"] == "disagree"]
    assert len(disagree) == 1 and disagree[0]["spread"] == 5000.0
    assert "(p7)" in disagree[0]["detail"]
    assert tieout(read_ledger(write(tmp_path, rows)), None, 5000.0)["passed"]


def test_missing_period_and_unparsed(tmp_path):
    rows = ROWS + [
        {"file": "memo.html", "period": "2026-04", "metric": "Consolidated EBITDA", "value": "$2.5M", "location": ""},
        {"file": "deck.pptx", "period": "2026-04", "metric": "Consolidated EBITDA", "value": "tbd", "location": ""},
    ]
    result = tieout(read_ledger(write(tmp_path, rows)), None, 1.0)
    checks = [(f["check"], f["period"]) for f in result["findings"]]
    assert ("missing", "2026-04") in checks and ("unparsed", "2026-04") in checks
    assert checks[-1][0] == "unparsed"


def test_bad_ledger(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("file,period\nmemo.html,2026-03\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_ledger(bad)
    assert run(bad).returncode == 2


def test_cli(tmp_path):
    good = run(write(tmp_path, ROWS), "--metric", "Consolidated EBITDA")
    assert good.returncode == 0 and "ALL TIE" in good.stdout
    rows = ROWS[:2] + [{**ROWS[2], "value": "2,405,000"}]
    bad = run(write(tmp_path, rows), "--format", "json")
    assert bad.returncode == 1 and json.loads(bad.stdout)["passed"] is False


def test_a_line_break_or_form_feed_inside_a_location_stays_in_its_row(tmp_path):
    # Text copied from a PDF often carries a form feed or line break; it must not split the row.
    rows = [dict(ROWS[0], location="p1\x0cfooter"), dict(ROWS[1], location="slide 3\nnotes"), ROWS[2]]
    ledger = read_ledger(write(tmp_path, rows))
    assert len(ledger) == 3 and ledger[0]["location"] == "p1\x0cfooter"
    done = run(write(tmp_path, rows), "--format", "json")
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["passed"] is True
