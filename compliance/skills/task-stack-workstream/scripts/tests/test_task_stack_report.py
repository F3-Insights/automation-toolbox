"""task_stack_report.py: REPORT.md from what the Run's deterministic steps wrote."""

import json

import pytest

import _common as c
import task_stack_report as rp


def report(capsys, run):
    with pytest.raises(SystemExit) as done:
        rp.main(["--run", str(run)])
    return done.value.code, capsys.readouterr().out


def test_score_before_and_after_writes_and_questions(tmp_path, capsys):
    zero = {k: {"flagged": 0, "clean_share": None} for k in c.COMPONENTS}
    before = {"tool": "task-stack-check", "as_of": "2030-03-03", "domains": [],
              "overall": {"score": 50.0, "components": dict(zero, overdue={"flagged": 4, "clean_share": 0.6})},
              "findings": {"overdue": [{"ref": "a"}, {"ref": "b"}]}}
    after = {"tool": "task-stack-check", "as_of": "2030-03-04", "domains": [],
             "overall": {"score": 52.5, "components": dict(zero, overdue={"flagged": 3, "clean_share": 0.7})},
             "findings": {k: ([{"ref": "a"}] if k == "overdue" else []) for k in c.COMPONENTS}}
    applied = {"counts": {"complete": {"applied": 1}, "cancel": {"refused": 1}}, "undo_log": "/x/undo.jsonl",
               "results": [{"op": "complete", "task": "portal://task/1", "outcome": "applied", "reason": "sent"},
                           {"op": "cancel", "task": "portal://task/2", "outcome": "refused", "code": "GOAL_LINKED",
                            "reason": "links to a goal"}]}
    changes = {"questions": [{"ask": "Merge the two freight tasks?", "why": "titles differ"}]}
    for name, data in (("before.json", before), ("after.json", after), ("apply.json", applied),
                       ("changes.json", changes)):
        (tmp_path / name).write_text(json.dumps(data))
    code, out = report(capsys, tmp_path)
    assert code == 0 and out.startswith("REPORT: score 50.0 -> 52.5 (+2.5); 1 applied, 1 refused")
    text = (tmp_path / "REPORT.md").read_text()
    assert "| overdue | 4 | 3 | better | 0 | 1 |" in text
    assert "GOAL_LINKED links to a goal" in text and "1. Merge the two freight tasks? Why: titles differ" in text


def test_missing_files_are_named(tmp_path, capsys):
    code, out = report(capsys, tmp_path)
    assert code == 0 and "missing before.json, after.json, apply.json, changes.json" in out


def test_a_capture_runs_source_items(tmp_path, capsys):
    (tmp_path / "capture-record.json").write_text(json.dumps({
        "dry_run": False, "counts": {"created": 2, "seen": 1},
        "rows": [{"id": "quick-capture:aa11", "state": "seen", "note": "refused NOT_NEXT_ACTION"},
                 {"id": "quick-capture:bb22", "state": "seen", "note": "deferred past the cap"}]}))
    report(capsys, tmp_path)
    text = (tmp_path / "REPORT.md").read_text()
    assert "2 created" in text and "quick-capture:aa11: seen" in text and "bb22" not in text


def test_not_a_folder_exits_2(tmp_path, capsys):
    code, _ = report(capsys, tmp_path / "nope")
    assert code == 2
