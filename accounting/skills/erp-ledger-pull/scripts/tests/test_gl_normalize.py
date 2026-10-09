"""gl_normalize.py: an invented spreadsheet export (Lakeview Hardware) and an Intacct snapshot."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.pop("_common", None)  # another skill's _common may be loaded in the same run
import gl_normalize as gn

SCRIPT = gn.__file__

MAP = """system: lakeview-sheet
date_format: "%m/%d/%Y"
gl-lines:
  fields:
    je_id: Entry
    date: Date
    account: Acct
    account_name: Acct Name
    memo: Line Memo
    description: Entry Memo
    reversed_from: Reverses
  amount: {debit: Dr, credit: Cr}
  constants: {state: posted}
ap-bills:
  fields: {doc_id: Bill, date: Date, counterparty: Vendor, account: Acct, amount: Amount}
"""

LINES = """﻿Entry,Date,Acct,Acct Name,Line Memo,Entry Memo,Dr,Cr,Reverses
J1,03/31/2026,6200,Freight,,Accrue freight MAR 2026,120.00,,
J1,03/31/2026,2200,Accrued liabilities,,Accrue freight MAR 2026,,120.00,
J2,04/01/2026,2200,Accrued liabilities,,Reversed - Accrue freight APR 2026,120.00,,03/31/2026
J2,04/01/2026,6200,Freight,,Reversed - Accrue freight APR 2026,-120.00,,03/31/2026
"""


@pytest.fixture
def sheet(tmp_path):
    (tmp_path / "map.yaml").write_text(MAP)
    (tmp_path / "gl.csv").write_text(LINES, encoding="utf-8")
    (tmp_path / "bills.csv").write_text("Bill,Date,Vendor,Acct,Amount\nB7,04/02/2026,Fabrikam Logistics,6200,95.5\n")
    return tmp_path


def test_amount_forms():
    assert gn.amounts({"Dr": "-5"}, {"debit": "Dr", "credit": "Cr"}, "x") == (0.0, 5.0)
    assert gn.amounts({"Amt": "-7"}, {"signed": "Amt"}, "x") == (0.0, 7.0)
    assert gn.amounts({"V": "3", "T": "Credit"}, {"value": "V", "type": "T"}, "x") == (0.0, 3.0)
    with pytest.raises(gn.Refused, match="row 2"):
        gn.amounts({"Amt": "ten"}, {"signed": "Amt"}, "row 2")


def test_bad_maps_are_refused():
    with pytest.raises(gn.Refused, match="lacks: colour"):
        gn.validate_map({"gl-lines": {"fields": {"colour": "C"}, "amount": {"signed": "A"}}})
    with pytest.raises(gn.Refused, match="exactly one"):
        gn.validate_map({"gl-lines": {"amount": {"signed": "A", "debit": "D"}}})
    with pytest.raises(gn.Refused, match="under amount"):
        gn.validate_map({"gl-lines": {"fields": {"debit": "D"}, "amount": {"signed": "A"}}})
    gn.validate_map(gn.INTACCT_MAP)


def test_dates_need_a_format_when_not_iso():
    assert gn.to_date("2026-04-01T10:00:00", "", "x") == "2026-04-01"
    with pytest.raises(gn.Refused):
        gn.to_date("04/01/2026", "", "x")


def test_a_spreadsheet_becomes_the_standard_shape(sheet):
    results = gn.normalize("csv", "2026-04", {"gl-lines": str(sheet / "gl.csv"), "ap-bills": str(sheet / "bills.csv")},
                           gn.load_map("csv", str(sheet / "map.yaml")))
    lines = results["gl-lines"]["rows"]
    assert list(lines[0]) == list(gn.FIELDS["line"])
    assert lines[3]["debit"] == 0.0 and lines[3]["credit"] == 120.0  # a negative debit is a credit
    headers = {h["je_id"]: h for h in results["je-headers"]["rows"]}
    assert headers["J1"]["reversed_by"] == "J2"  # same text once the month is folded out
    meta = results["gl-lines"]["meta"]
    assert meta["server_total"] is None and meta["system"] == "lakeview-sheet"
    assert results["ap-bills"]["rows"][0]["amount"] == 95.5


def test_an_intacct_snapshot_needs_no_map(tmp_path):
    rows = [{"journalEntry.key": "77", "id": "1", "entryDate": "2026-04-30", "glAccount.id": "6200",
             "txnType": "credit", "baseAmount": "10.00", "journalEntry.state": "posted"}]
    (tmp_path / "lines.json").write_text(json.dumps({"meta": {"pulled-at": "2026-05-01T00:00:00Z",
                                                              "server-total-count": 1}, "rows": rows}))
    out = gn.normalize("intacct", "2026-04", {"gl-lines": str(tmp_path / "lines.json")}, gn.load_map("intacct"))
    line = out["gl-lines"]["rows"][0]
    assert (line["je_id"], line["credit"], line["state"]) == ("77", 10.0, "posted")
    assert out["gl-lines"]["meta"]["server_total"] == 1


def test_the_cli_writes_one_file_per_input_and_refuses_csv_without_a_map(sheet):
    base = [sys.executable, SCRIPT, "--period", "2026-04", "--out", str(sheet / "std"), "--lines", str(sheet / "gl.csv")]
    done = subprocess.run(base + ["--system", "csv"], capture_output=True, text=True)
    assert done.returncode == 2 and "needs --map" in done.stderr
    done = subprocess.run(base + ["--system", "csv", "--map", str(sheet / "map.yaml")], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert sorted(p.name for p in (sheet / "std").iterdir()) == ["gl-lines.json", "je-headers.json"]
