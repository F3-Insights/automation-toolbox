from conftest import make_window

import time_study_collect as col


def test_collect_runs_the_tool_for_each_uncollected_window(home, capsys):
    make_window(home, "2030-09-01_to_2030-09-14")
    make_window(home, "2030-09-15_to_2030-09-20", collected=False)
    assert col.main([str(home), "--as-of", "2030-10-02", "--period=", "--dry-run-if=false"]) == 0
    assert capsys.readouterr().out.startswith("COLLECTED: 2 window(s)")
    assert (home / "calls.log").read_text().splitlines() == [
        "collect --since 2030-09-21 --until 2030-09-30 --window 2030-09-21_to_2030-09-30",
        "collect --since 2030-09-15 --until 2030-09-20 --window 2030-09-15_to_2030-09-20"]
    col.main([str(home), "--as-of", "2030-10-02"])
    assert capsys.readouterr().out.startswith("NOTHING: ")


def test_a_dry_run_plans_and_writes_nothing(home, capsys):
    col.main([str(home), "--as-of", "2030-10-02", "--dry-run-if=true"])
    assert capsys.readouterr().out.startswith("PLAN: dry run; would collect 3 window(s)")
    assert not (home / "calls.log").exists()


def test_a_failed_collect_is_partial_and_still_exit_0(home, capsys):
    assert col.main([str(home), "--as-of", "2031-02-02", "--period", "2031-01"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("PARTIAL: collected 2 of 3 window(s)") and "calendar source timed out" in out
