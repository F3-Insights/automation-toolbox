"""trial_balance.py on an invented company, Northwind Traders."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.pop("_common", None)  # another skill's _common may be loaded in the same run
import trial_balance as tb

SCRIPT = Path(tb.__file__)
ACCOUNTS = {
    "1100": ("Operating cash", "balanceSheet", "debit"),
    "2100": ("Trade payables", "balanceSheet", "credit"),
    "3100": ("Partner capital", "balanceSheet", "credit"),
    "4100": ("Product revenue", "incomeStatement", "credit"),
    "6100": ("Warehouse lease", "incomeStatement", "debit"),
}


def line(je, account, side, amount, day, state="posted", loc="10", dept="D1"):
    return {"journalEntry.key": je, "glAccount.id": account, "entryDate": day, "txnType": side,
            "baseAmount": amount, "journalEntry.state": state, "dimensions.location.id": loc,
            "dimensions.department.id": dept}


def entry(je, debit, credit, amount, day, **kw):
    return [line(je, debit, "debit", amount, day, **kw), line(je, credit, "credit", amount, day, **kw)]


HISTORY = entry("H1", "1100", "3100", "9000.00", "2025-06-30") + entry("H2", "1100", "4100", "400.00", "2025-11-30")
BRIDGE = entry("B1", "6100", "1100", "250.00", "2026-02-10") + entry("B2", "6100", "1100", "250.00", "2026-04-10")
CURRENT = (entry("C1", "1100", "4100", "1800.00", "2026-04-20") + entry("C2", "6100", "2100", "250.00", "2026-04-30")
           + entry("C3", "6100", "2100", "99.00", "2026-04-30", state="draft"))


def write(path, rows, meta=None):
    path.write_text(json.dumps({"meta": meta or {"pulled-at": "2026-05-02T08:00:00+00:00"}, "rows": rows}))
    return path


@pytest.fixture
def pulls(tmp_path):
    accounts = [{"id": k, "name": v[0], "accountType": v[1], "normalBalance": v[2]} for k, v in ACCOUNTS.items()]
    return {name: str(write(tmp_path / f"{name}.json", rows)) for name, rows in
            (("history", HISTORY), ("bridge", BRIDGE), ("current", CURRENT), ("accounts", accounts))}


def test_the_pulls_stitch_without_overlap_and_drafts_stay_out():
    lines, windows = tb.select_windows(HISTORY, BRIDGE, CURRENT, "2026-04-30")
    assert windows["bridge_used"] == 4  # both bridge entries sit before the current window
    assert all(x["journalEntry.state"] == "posted" for x in lines)
    lines, windows = tb.select_windows(HISTORY, BRIDGE, CURRENT, "2026-04-30", current_from="2026-03-01")
    assert windows["bridge_used"] == 2 and windows["current_window"] == "2026-03-01..2026-04-30"


def test_a_window_start_inside_the_history_stops():
    with pytest.raises(ValueError):
        tb.select_windows(HISTORY, BRIDGE, CURRENT, "2026-04-30", current_from="2025-07-01")


def test_balance_sheet_cumulative_income_statement_ytd_and_re_prior(pulls):
    result, _ = tb.trial_balance("2026-04-30", **pulls)
    ending = {r["Account"]: r["Ending balance"] for r in result["rows"]}
    assert ending["1100"] == 9000 + 400 - 500 + 1800
    assert ending["4100"] == -1800  # last year's 400 moved to RE-PRIOR
    assert ending["RE-PRIOR"] == -400
    assert result["balanced"] and result["ytd_net_income"] == 1800 - 750


def test_by_dimensions_carries_the_upload_layout_in_normal_sign(pulls):
    result, _ = tb.trial_balance("2026-04-30", by_dimensions=True, **pulls)
    upload = {r[0]: r[8:] for r in result["dimensions"]["upload_rows"]}
    assert result["dimensions"]["upload_columns"][-1] == "Month Ended April 2026"
    assert upload["4100"] == [0.0, 0.0, 0.0, 1800.0]


def test_cli_json_and_workbook(pulls, tmp_path):
    out = tmp_path / "TB April.xlsx"
    args = [sys.executable, str(SCRIPT), "--as-of", "2026-04-30", "--format", "json", "--out", str(out),
            "--by-dimensions"] + [x for k, v in pulls.items() for x in (f"--{k}", v)]
    done = subprocess.run(args, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["balanced"] is True
    assert out.stat().st_size > 0 and (tmp_path / "TB April - monthly upload layout.csv").is_file()


def test_a_one_sided_line_exits_one(pulls, tmp_path):
    write(Path(pulls["current"]), CURRENT + [line("X", "6100", "debit", "5.00", "2026-04-30")])
    args = [sys.executable, str(SCRIPT), "--as-of", "2026-04-30"] + [x for k, v in pulls.items() for x in (f"--{k}", v)]
    done = subprocess.run(args, capture_output=True, text=True)
    assert done.returncode == 1 and "FAIL" in done.stdout
