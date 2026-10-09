"""report_questions.py: the workers' questions and the audience editor's three lists."""

import json

from conftest import run


EDITOR = """The audience editor's verdict.

## Keep
- Month-end close | the October close signed off two days late | has to know | the chief executive asked | portal://task/t1
- Month-end close | the credit hold is disputed | decides because of it | the head of sales owns it | portal://task/t8

## Leave out
- Other topics | the winter lunch booking | it affects nobody outside the department | portal://email/e9

## Misfiled
- portal://task/t8 | filed under Month-end close | reads as Cash and collections | a disputed credit hold
- portal://email/e9 | filed under Other topics | reads as not this scope | a staff social

<!-- QUESTIONS_START -->
Q1 | Is the credit hold already known to the leadership team? | It changes whether the bullet explains | portal://task/t2
Q2 | Should the scanner renewal be named? | It has no price yet | portal://task/t7
<!-- QUESTIONS_END -->
"""

CONTINUITY = "<!-- QUESTIONS_START -->\nQ1 | Is the credit hold already known to the leadership team? | dup | portal://task/t8\n<!-- QUESTIONS_END -->\n"


def test_questions_are_collected_numbered_folded_and_answered(tmp_path):
    (tmp_path / "editor.txt").write_text(EDITOR)
    (tmp_path / "continuity.txt").write_text(CONTINUITY)
    out = tmp_path / "questions.json"
    done = run("report_questions", "collect", "--from", tmp_path / "editor.txt", "--from", tmp_path / "continuity.txt",
               "--out", out)
    found = json.loads(done.stdout)
    assert found["count"] == 2 and found["raw"] == 3
    assert found["questions"][0]["affects"] == ["portal://task/t2", "portal://task/t8"]
    assert json.loads(run("report_questions", "answer", "--questions", out, "--id", "1", "--answer",
                          "Yes, it was raised on Monday.").stdout)["ref"] == "owner://questions/1"
    listed = json.loads(run("report_questions", "list", "--questions", out).stdout)
    assert listed["answered_refs"] == ["owner://questions/1"] and listed["open"] == 1
    assert run("report_questions", "answer", "--questions", out, "--id", "9", "--answer", "x").returncode == 2


def test_the_editors_lists_become_gate_one_proposals(tmp_path):
    (tmp_path / "editor.txt").write_text(EDITOR)
    found = json.loads(run("report_questions", "verdicts", "--from", tmp_path / "editor.txt").stdout)
    assert found["counts"] == {"keep": 2, "leave_out": 1, "misfiled": 2}
    assert found["moves"] == [{"ref": "portal://task/t8", "category": "Cash and collections"}]
    assert found["strike_candidates"] == ["portal://email/e9"]
    assert found["gate1_proposals"][0]["ask"] == "move portal://task/t8 to Cash and collections?"
    assert found["keep"][1]["category"] == "Month-end close", "the editor never re-files"
