"""report_weekly_check.py: done computed from the week's files, and the scheduler's one line."""

import json

from conftest import PERIOD, run


def check(store, *args):
    return json.loads(run("report_weekly_check", store, "--period", PERIOD, "--as-of", "2027-11-11", "--format",
                          "json", *args).stdout)


def test_check_names_the_next_step_after_collection(store, week):
    result = check(store, "--phase", "collect")
    assert result["next"]["step"] == "judge" and not result["phase_done"]
    assert result["tests"]["evidence"]["gaps"] == ["no editor.txt from report-audience-editor",
                                                   "no verdicts.json (report_questions.py verdicts)"]
    line = run("report_weekly_check", store, "--period", PERIOD, "--phase", "collect", "--precheck").stdout
    assert line.startswith("WORK: judge")


def test_a_blocked_profile_is_nothing_for_an_agent_to_do(store):
    (store / "profile.md").write_text("# Weekly report profile\n\n## Seats\n")
    run("report_weekly_prepare", store, "--period", PERIOD)
    line = run("report_weekly_check", store, "--period", PERIOD, "--precheck").stdout
    assert line.startswith("NOTHING: the role profile")
