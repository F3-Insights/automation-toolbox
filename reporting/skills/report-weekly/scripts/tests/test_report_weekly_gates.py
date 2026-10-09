"""report_weekly_gates.py: Gates 1 and 2 as one numbered list with defaults, and the answers applied."""

import json

from conftest import PERIOD, run


EDITOR = """## Keep
- Systems and support | the support queue | is affected | operations feels it | file://2/my-week.md

## Leave out
- Other topics | the controller's note | internal | file://1/controller-week-46.md

## Misfiled

<!-- QUESTIONS_START -->
Q1 | Is the October close final? | It sets the close figure | file://1/controller-week-46.md
<!-- QUESTIONS_END -->
"""

DRAFT = """# Weekly Highlights - Finance and Technology - 2027-11-12

## Month-end close

- **October close:** the October close signed off on 2027-11-06 (file://1/controller-week-46.md).

## Cash and collections

- **Receivables:** no change this week (owner://gate2).

## Systems and support

- **Support queue:** the queue rose to 41 tickets (file://2/my-week.md).

## Other topics

- **Nothing further:** no other call-outs (owner://gate1).

## Decisions needed

None this week.
"""


def check(store, *args):
    return json.loads(run("report_weekly_check", store, "--period", PERIOD, "--as-of", "2027-11-11", "--format",
                          "json", *args).stdout)


def test_the_gates_are_numbered_with_defaults_and_applied(store, week):
    folder = store / "work" / PERIOD
    (folder / "editor.txt").write_text(EDITOR)
    run("report_questions", "verdicts", "--from", folder / "editor.txt", "--out", folder / "verdicts.json")
    run("report_questions", "collect", "--from", folder / "editor.txt", "--out", folder / "questions.json")
    built = run("report_weekly_gates", "build", folder, "--due", "2027-11-11", "--format", "json")
    assert built.returncode == 0, built.stderr
    gates = json.loads((folder / "gates.json").read_text())["items"]
    kinds = [g["kind"] for g in gates]
    assert kinds[0] == "categories" and {"leave-out", "question", "wins", "metric", "table"} <= set(kinds)
    assert run("report_weekly_gates", "build", folder).returncode == 3, "a built list is not replaced without --rebuild"
    pull = next(g["n"] for g in gates if g["kind"] == "leave-out")
    question = next(g["n"] for g in gates if g["kind"] == "question")
    (folder / "gate-answers.json").write_text(json.dumps({
        "reply": f"{pull} yes, {question} yes it is final", "answered_on": "2027-11-11",
        "answers": {str(pull): "yes", str(question): "yes, it is final"}}))
    applied = run("report_weekly_gates", "apply", folder, "--answers", folder / "gate-answers.json", "--format", "json")
    assert applied.returncode == 0, applied.stderr
    gate1 = json.loads((folder / "gate1.json").read_text())
    assert gate1["items"]["pull_back"] == [{"ref": "file://1/controller-week-46.md"}]
    assert json.loads((folder / "questions.json").read_text())["questions"][0]["answer"] == "yes, it is final"
    owner_input = (folder / "owner-input.md").read_text()
    assert "Default taken" in owner_input and "Answer: yes" in owner_input
    (folder / "CONFIRMATIONS.md").write_text("## CR-1a2b\n- Question: Weekly report gates for the week ending "
                                             "2027-11-12\n- State: answered\n- Due: 2027-11-11\n")
    (folder / "draft.md").write_text(DRAFT)
    result = check(store, "--phase", "assemble", "--report-folder", store / "out")
    assert result["tests"]["gates"]["met"] and result["tests"]["sections"]["met"], result["tests"]
    assert result["tests"]["numbers"]["met"], result["tests"]["numbers"]
    assert result["next"] == {"step": "render", "waits_on": "agent",
                              "why": f"no Word and PDF pair in {store / 'out' / PERIOD}"}
