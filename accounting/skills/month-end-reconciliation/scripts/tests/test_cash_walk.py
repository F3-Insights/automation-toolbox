"""Tests for cash_walk.py: classification reads the offset account, never the memo."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "cash_walk.py"
sys.path.insert(0, str(SCRIPT.parent))
sys.modules.pop("_common", None)  # another skill's _common may be loaded in the same run
from cash_walk import classify_offset, walk  # noqa: E402

PERIOD = "2026-03"
RULES = {"financing": ["3", "25"], "investing": ["15"], "operating": []}


def std(account, amount, je, side="debit", date="2026-03-12", name="", memo="ACH WITHDRAWAL"):
    """A GL line in the standard shape."""
    return {"je_id": je, "date": date, "account": account, "account_name": name, "memo": memo,
            "debit": amount if side == "debit" else 0, "credit": amount if side == "credit" else 0}


def intacct(account, amount, je, side="debit", date="2026-03-12", name="", memo="ACH WITHDRAWAL"):
    """The same line as a raw Sage Intacct pull lands it."""
    return {"glAccount.id": account, "glAccount.name": name, "baseAmount": f"{amount:.2f}", "txnType": side,
            "entryDate": date, "journalEntry.key": je, "description": memo}


def entry(make, je, amount, offset, name="", date="2026-03-12"):
    return [make("10100", amount, je, "credit", date, "Operating Cash"), make(offset, amount, je, "debit", date, name)]


def by_je(result):
    return {m["je_id"]: m for m in result["movements"]}


def test_classify_offset():
    assert classify_offset("30100", RULES) == "financing"
    assert classify_offset("15000", RULES) == "investing"
    assert classify_offset("60300", RULES) == "operating"
    assert classify_offset("30100", {"financing": []}) == "operating"


@pytest.mark.parametrize("make", [std, intacct])
def test_offset_decides_whatever_the_memo_says(make):
    rows = (entry(make, "1", 150000.0, "30100", "Owner Distributions") + entry(make, "2", 20000.0, "60300")
            + entry(make, "3", 75000.0, "15200") + entry(make, "4", 5000.0, "10900"))
    moves = by_je(walk(rows, PERIOD, ("10",), rules=RULES))
    assert moves["1"]["classification"] == "financing" and moves["1"]["cause"] == "ACH WITHDRAWAL"
    assert moves["2"]["classification"] == "operating"
    assert moves["3"]["classification"] == "investing"
    assert "4" not in moves  # both sides inside the walk: no net movement
    assert by_je(walk(rows, PERIOD, ("10",), {"10100"}, RULES))["4"]["classification"] == "transfer"


def test_largest_offset_and_missing_other_side():
    rows = [std("10100", 100000.0, "5", "credit"), std("60300", 1000.0, "5"), std("30100", 99000.0, "5"),
            std("10100", 500.0, "6", "credit")]
    moves = by_je(walk(rows, PERIOD, ("10",), rules=RULES))
    assert moves["5"]["offset_account"] == "30100" and moves["5"]["classification"] == "financing"
    assert moves["6"]["classification"] == "transfer"


def test_scope_period_and_totals():
    rows = (entry(std, "1", 150000.0, "30100") + entry(std, "2", 20000.0, "60300")
            + entry(std, "7", 999.0, "60300", date="2026-02-27") + [std("60300", 9, "8"), std("23000", 9, "8", "credit")])
    result = walk(rows, PERIOD, ("10",), rules=RULES, floor=50000.0, opening=1000000.0)
    assert result["by_classification"] == {"financing": -150000.0, "operating": -20000.0}
    assert result["net_change"] == -170000.0 and result["closing"] == 830000.0
    assert [m["je_id"] for m in result["movements"]] == ["1", "2"]
    assert [m["je_id"] for m in result["material"]] == ["1"]
    with pytest.raises(ValueError, match="name the cash accounts"):
        walk(rows, PERIOD)


def test_cli(tmp_path):
    lines = tmp_path / "lines.json"
    lines.write_text(json.dumps({"meta": {}, "rows": entry(std, "1", 150000.0, "30100", "Owner Distributions")}))
    base = [sys.executable, str(SCRIPT), "--period", PERIOD, "--lines", str(lines)]
    text = subprocess.run(base + ["--cash-prefix", "10", "--financing", "3", "--floor", "1000"],
                          capture_output=True, text=True)
    assert text.returncode == 0 and "1 cash movement(s)" in text.stdout and "30100" in text.stdout
    out = subprocess.run(base + ["--cash-prefix", "10", "--financing", "3", "--opening", "1000000", "--format", "json"],
                         capture_output=True, text=True)
    payload = json.loads(out.stdout)
    assert payload["closing"] == 850000.0 and payload["movements"][0]["offset_account_name"] == "Owner Distributions"
    bad = subprocess.run(base, capture_output=True, text=True)
    assert bad.returncode == 2 and "name the cash accounts" in bad.stderr
