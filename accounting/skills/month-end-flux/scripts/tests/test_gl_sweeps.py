"""Tests for gl_sweeps.py: one planted defect per sweep, a clean month, and the exit codes."""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "gl_sweeps.py"
sys.path.insert(0, str(SCRIPT.parent))
sys.modules.pop("_common", None)  # another skill's _common may be loaded in the same run
import gl_sweeps as gs  # noqa: E402

PERIOD = "2026-03"
BASELINE = ["2025-09", "2025-10", "2025-11", "2025-12", "2026-01", "2026-02"]
CFG = dict(gs.DEFAULTS)


def line(account="60300", amount=1000.0, date="2026-03-15", side="debit", je="1", journal="GJ", loc="100", **kw):
    row = {"je_id": je, "journal": journal, "date": date, "account": account, "account_name": "Software",
           "location": loc, "debit": amount if side == "debit" else 0.0,
           "credit": amount if side == "credit" else 0.0}
    row.update(kw)
    return row


def intacct_line(account, amount, date, je, side="debit", journal="GJ"):
    return {"glAccount.id": account, "glAccount.name": "Software", "baseAmount": f"{amount:.2f}", "txnType": side,
            "entryDate": date, "journalEntry.key": je, "journalEntry.glJournal.id": journal,
            "dimensions.location.id": "100"}


def header(key="1", date="2026-03-31", state="posted", desc="entry", **kw):
    return {"je_id": key, "date": date, "state": state, "description": desc, "journal": "GJ", **kw}


def history(account="60300", amount=10000.0, months=BASELINE[1:]):
    return [line(account, amount, f"{m}-15", je=f"B{m}{account}") for m in months]


def checks(findings):
    return [f["check"] for f in findings]


def test_run_rate_flags_shortfall_and_honours_excluded_accrual():
    rows = history() + [line(amount=2000.0, je="9")]
    found = gs.sweep_run_rate(rows, [], PERIOD, CFG)
    assert found and found[0]["amount"] == 8000.0 and found[0]["key"] == "run_rate:60300:2026-03"
    rows.append(line(amount=8000.0, je="77"))  # this month's accrual fills the hole
    assert gs.sweep_run_rate(rows, [], PERIOD, CFG) == []
    hidden = gs.sweep_run_rate(rows, [header("77", je_number="ACR-3")], PERIOD, {**CFG, "run_rate_exclude_jes": ["ACR-3"]})
    assert hidden and hidden[0]["amount"] == 8000.0


def test_run_rate_reads_raw_intacct_rows_too():
    rows = [intacct_line("60300", 10000.0, f"{m}-15", f"B{m}") for m in BASELINE[1:]]
    rows.append(intacct_line("60300", 1000.0, "2026-03-15", "9"))
    assert checks(gs.sweep_run_rate(rows, [], PERIOD, CFG)) == ["run_rate"]


def test_negative_expense_and_entity_balance():
    rows = [line(amount=900.0, side="credit"), line("20000", 900.0)]
    assert checks(gs.sweep_negative_expense(rows, {}, PERIOD, CFG)) == ["negative_expense"]
    unbalanced = [line(amount=100.0, loc="100"), line("20000", 100.0, side="credit", loc="200")]
    found = gs.sweep_entity_balance(unbalanced, PERIOD)
    assert {f["key"] for f in found} == {"entity_balance:100:2026-03", "entity_balance:200:2026-03"}
    assert gs.sweep_entity_balance(rows, PERIOD) == []


def test_stuck_drafts_and_pending_reversal():
    assert checks(gs.sweep_stuck_drafts([header(state="draft"), header("2")])) == ["stuck_drafts"]
    found = gs.sweep_reversal_integrity([header("5", state="reversalpending")], PERIOD, CFG)
    assert found[0]["severity"] == "high"


def test_late_postings():
    rows = [line(amount=12000.0, date="2026-01-31", je="40", created_at="2026-04-03T10:00:00Z"),
            line(amount=5000.0, date="2026-03-02", je="41", created_at="2026-04-02T10:00:00Z")]
    found = gs.sweep_late_postings(rows, PERIOD, CFG)
    assert [f["key"] for f in found] == ["late_postings:JE40"] and found[0]["severity"] == "medium"


def test_reclass_date():
    headers = [header("60", date="2026-03-20", desc="Reclass Northwind inv 48213")]
    bills = [{"doc_id": "B-48213", "posting_date": "2026-02-10", "counterparty": "Northwind Traders", "memo": ""}]
    cfg = {**CFG, "reclass_vendors": ["NORTHWIND"]}
    assert checks(gs.sweep_reclass_date(headers, bills, PERIOD, cfg)) == ["reclass_date"]
    bills[0]["posting_date"] = "2026-03-10"
    assert gs.sweep_reclass_date(headers, bills, PERIOD, cfg) == []


def test_reversal_integrity():
    parent = header("70", date="2026-02-28", desc="To accrue rent FEB 2026")
    good = header("71", date="2026-03-01", desc="Reversed - To accrue rent MAR 2026", reversed_from="2026-02-28")
    late = header("72", date="2026-03-04", desc="To accrue rent FEB 2026", reversed_from="2026-02-28")
    orphan = header("73", date="2026-03-01", desc="Other", reversed_from="2026-02-28")
    found = gs.sweep_reversal_integrity([parent, good, late, orphan], PERIOD, CFG)
    assert [f["key"] for f in found] == ["reversal_integrity:JE72", "reversal_integrity:JE73"]


def test_duplicates():
    rows = [line(amount=4200.0, je="80", date="2026-03-03", vendor="V100"),
            line(amount=4200.0, je="81", date="2026-03-06", vendor="V100"),
            line(amount=4200.0, je="82", date="2026-03-28", vendor="V200")]
    found = gs.sweep_duplicates(rows, {}, CFG)
    assert [f["evidence"] for f in found] == [["JE80", "JE81"]]


def test_swings_and_journal_shape():
    accounts = {"40000": {"id": "40000", "accountType": "incomeStatement", "normalBalance": "credit"}}
    rows = [line("40000", 50000.0 + i * 100, f"{m}-15", "credit", je=f"R{m}") for i, m in enumerate(BASELINE)]
    rows.append(line("40000", 150000.0, "2026-03-15", "credit", je="R3"))
    found = gs.sweep_swings(rows, accounts, {}, PERIOD, CFG)
    assert checks(found) == ["swings"] and found[0]["amount"] > 0
    shape = [line(je=f"P{m}", date=f"{m}-10", journal="PAYROLL") for m in BASELINE]
    shape.append(line(je="N1", journal="NEWJ"))
    found = gs.sweep_journal_shape(shape, PERIOD, CFG)
    assert [(f["key"], f["severity"]) for f in found] == [
        ("journal_shape:new:NEWJ:2026-03", "low"), ("journal_shape:PAYROLL:2026-03", "high")]


def test_clean_month_passes():
    rows = [r for m in BASELINE + [PERIOD] for r in (line(amount=10000.0, date=f"{m}-15", je=f"J{m}"),
                                                    line("20000", 10000.0, f"{m}-15", "credit", je=f"J{m}"))]
    result = gs.run_sweeps(rows, [header(f"J{PERIOD}")], {}, [], PERIOD)
    assert result["passed"] and result["findings"] == []


def test_cli_exit_codes(tmp_path):
    def dump(name, rows):
        path = tmp_path / name
        path.write_text(json.dumps({"meta": {}, "rows": rows}))
        return str(path)
    lines = dump("lines.json", [line(amount=100.0), line("20000", 90.0, side="credit")])
    headers = dump("headers.json", [header()])
    run = subprocess.run([sys.executable, str(SCRIPT), "--period", PERIOD, "--lines", lines, "--headers", headers,
                          "--format", "json"], capture_output=True, text=True)
    assert run.returncode == 1 and json.loads(run.stdout)["high"] == 1
    missing = subprocess.run([sys.executable, str(SCRIPT), "--period", PERIOD, "--lines", "nope.json",
                              "--headers", headers], capture_output=True, text=True)
    assert missing.returncode == 2
