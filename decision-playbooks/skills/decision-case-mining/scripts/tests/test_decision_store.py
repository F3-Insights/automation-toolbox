"""decision_store.py: cases and bullets need citations; the audit and the export read them back.
All data is invented (Acme Components buying from Northwind Traders)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import decision_store as ds  # noqa: E402


@pytest.fixture(autouse=True)
def empty_settings(tmp_path, monkeypatch):
    path = tmp_path / "settings.toml"
    path.write_text("")
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(path))
    return path


def run(capsys, db, *argv):
    code = ds.main(["--db", str(db), *argv])
    return code, capsys.readouterr()


CASE = {
    "category": "spend-approvals",
    "situation_summary": "Northwind Traders asked Acme Components to pay a quarterly invoice early.",
    "action_taken": "Approved early payment.",
    "reasoning": "The early-payment discount beats the cash yield.",
    "sources": [{"type": "email", "external_ref": "email-001", "title": "Re: early payment",
                 "url": "portal://email/email-001", "locator": "reply-1"}],
}


def test_case_with_inline_source_then_stats_and_clean_audit(tmp_path, capsys):
    db = tmp_path / "store.db"
    assert run(capsys, db, "init")[0] == 0
    code, out = run(capsys, db, "add-case", "--json", json.dumps([CASE, dict(CASE, category="delegation")]))
    assert code == 0 and json.loads(out.out) == {"case_ids": [1, 2]}
    code, out = run(capsys, db, "stats")
    counts = json.loads(out.out)
    assert counts["sources"] == 1 and counts["cases"] == 2
    assert counts["cases_by_category"] == {"spend-approvals": 1, "delegation": 1}
    code, out = run(capsys, db, "audit")
    assert code == 0 and json.loads(out.out)["violations"] == 0


def test_case_without_source_is_refused_and_nothing_written(tmp_path, capsys):
    db = tmp_path / "store.db"
    run(capsys, db, "init")
    bad = dict(CASE, sources=[])
    code, out = run(capsys, db, "add-case", "--json", json.dumps([CASE, bad]))
    assert code == 1 and "has no source" in out.err
    assert json.loads(run(capsys, db, "stats")[1].out)["cases"] == 0


def test_bullets_need_a_citation_and_export_groups_by_kind(tmp_path, capsys):
    db = tmp_path / "store.db"
    run(capsys, db, "init")
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps(CASE))
    run(capsys, db, "add-case", "--file", str(cases))
    code, out = run(capsys, db, "add-playbook", "--json", json.dumps(
        {"category": "spend-approvals", "title": "Payment approvals", "risk_tier": "financial",
         "human_final_pass": True}))
    pid = json.loads(out.out)["playbook_id"]
    code, out = run(capsys, db, "add-bullet", "--json", json.dumps({"playbook_id": pid, "text": "x", "sources": []}))
    assert code == 1 and "has no source" in out.err
    code, out = run(capsys, db, "add-bullet", "--json", json.dumps([
        {"playbook_id": pid, "kind": "principle", "text": "Pay early when the discount beats the cash yield.",
         "sources": [{"case_id": 1}]},
        {"playbook_id": pid, "kind": "escalation", "text": "Ask before paying a new vendor early.",
         "sources": [{"source_id": 1, "locator": "reply-1"}]},
    ]))
    assert code == 0
    code, out = run(capsys, db, "export-playbook", "--category", "spend-approvals")
    text = out.out
    assert code == 0
    assert text.index("## Principles") < text.index("## Escalation triggers")
    assert "Sources: case:1" in text and "portal://email/email-001?reply-1" in text
    assert "A person makes the final move" in text


def test_audit_finds_a_missing_archived_copy(tmp_path, capsys):
    db = tmp_path / "store.db"
    run(capsys, db, "init")
    (tmp_path / "kept.vtt").write_text("WEBVTT")
    run(capsys, db, "add-source", "--json", json.dumps([
        {"type": "recording", "external_ref": "r1", "raw_path": "kept.vtt", "content_hash": "abc"},
        {"type": "recording", "external_ref": "r2", "raw_path": "gone.vtt", "content_hash": "def"},
    ]))
    code, out = run(capsys, db, "audit")
    result = json.loads(out.out)
    assert code == 1 and result["sources_copy_missing"] == [2]


def test_missing_database_setting_exits_2(capsys):
    with pytest.raises(SystemExit) as done:
        ds.main(["stats"])
    assert done.value.code == 2
    assert "[decision-case-mining]" in capsys.readouterr().err


def test_database_from_settings(tmp_path, capsys, empty_settings):
    empty_settings.write_text(f'[decision-case-mining]\ndatabase = "{tmp_path / "s.db"}"\n')
    assert ds.main(["init"]) == 0
    assert (tmp_path / "s.db").exists()


def test_cases_and_sources_listings(tmp_path, capsys):
    db = tmp_path / "store.db"
    run(capsys, db, "init")
    run(capsys, db, "add-case", "--json", json.dumps(CASE))
    run(capsys, db, "add-source", "--json", json.dumps(
        {"type": "recording", "external_ref": "r1", "url": "https://example.test/r1",
         "meta": {"classification": "playbook-narration", "category": "spend-approvals"}}))
    cases = json.loads(run(capsys, db, "cases", "--category", "spend-approvals")[1].out)
    assert len(cases) == 1 and cases[0]["sources"][0]["external_ref"] == "email-001"
    found = json.loads(run(capsys, db, "sources", "--type", "recording", "--category", "spend-approvals")[1].out)
    assert [s["external_ref"] for s in found] == ["r1"]
    assert json.loads(run(capsys, db, "sources", "--category", "delegation")[1].out) == []


def test_re_registering_a_source_keeps_its_classification(tmp_path, capsys):
    db = tmp_path / "store.db"
    run(capsys, db, "init")
    run(capsys, db, "add-source", "--json", json.dumps(
        {"type": "recording", "external_ref": "r1", "content_hash": "h1",
         "meta": {"classification": "playbook-narration", "category": "spend-approvals"}}))
    run(capsys, db, "add-source", "--json", json.dumps(
        {"type": "recording", "external_ref": "r1", "meta": {"platform": "loom", "duration": None}}))
    found = json.loads(run(capsys, db, "sources", "--category", "spend-approvals")[1].out)
    assert [s["external_ref"] for s in found] == ["r1"]
    meta = found[0]["meta"] if isinstance(found[0]["meta"], dict) else json.loads(found[0]["meta"])
    assert meta["platform"] == "loom" and meta["classification"] == "playbook-narration"
    assert found[0]["content_hash"] == "h1"


def test_missing_input_file_is_a_clean_error(tmp_path, capsys):
    db = tmp_path / "store.db"
    run(capsys, db, "init")
    code, out = run(capsys, db, "add-case", "--file", str(tmp_path / "nope.json"))
    assert code == 1 and "decision_store:" in out.err
