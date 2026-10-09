import json
import os
import time
from datetime import date

import pytest
from conftest import make_window

import _common as common
import time_study_check as chk


def test_the_default_period_is_the_last_full_month_cut_into_even_windows(home):
    p = common.plan(home, date(2030, 10, 2))
    assert p["period"] == "2030-09" and p["span"] == ["2030-09-01", "2030-09-30"]
    assert p["new"] == ["2030-09-01_to_2030-09-10", "2030-09-11_to_2030-09-20", "2030-09-21_to_2030-09-30"]


def test_days_already_in_a_window_are_not_planned_again(home):
    make_window(home, "2030-09-01_to_2030-09-07")
    make_window(home, "2030-09-15_to_2030-09-20")
    p = common.plan(home, date(2030, 10, 2))
    assert p["existing"] == ["2030-09-01_to_2030-09-07", "2030-09-15_to_2030-09-20"]
    assert p["new"] == ["2030-09-08_to_2030-09-14", "2030-09-21_to_2030-09-30"]


def test_a_missed_month_is_caught_up_but_only_the_newest_45_days(home):
    make_window(home, "2030-07-25_to_2030-07-31")
    p = common.plan(home, date(2030, 10, 2))
    assert p["span"][0] == "2030-08-01" and p["new"][0].startswith("2030-08-17")
    assert p["skipped"][0] == "2030-08-01" and len(p["skipped"]) == 16


def test_a_running_period_stops_at_yesterday_and_windows_may_not_overlap(home):
    assert common.plan(home, date(2030, 9, 10), period="2030-09")["new"] == ["2030-09-01_to_2030-09-09"]
    make_window(home, "2030-09-01_to_2030-09-07")
    with pytest.raises(common.Bad):
        common.plan(home, date(2030, 10, 2), window="2030-09-05_to_2030-09-10")


def test_a_finished_period_is_done_and_the_precheck_says_nothing(home, capsys):
    make_window(home, "2030-09-01_to_2030-09-14")
    make_window(home, "2030-09-15_to_2030-09-30")
    assert chk.main([str(home), "--as-of", "2030-10-02", "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["done"] is True
    chk.main([str(home), "--as-of", "2030-10-02", "--precheck"])
    assert capsys.readouterr().out.startswith("NOTHING: every day from 2030-09-01 to 2030-09-30")


def test_each_test_of_done_names_its_gap(home):
    w = make_window(home, "2030-09-01_to_2030-09-14", recordings=("rec-a", "rec-b"), segmented=False,
                    checked=False, said=False)
    make_window(home, "2030-09-15_to_2030-09-30", collected=False, days=False, report=False)
    answers = w / "answers-2030-10-03.md"
    answers.write_text("1) yes")
    os.utime(answers, (time.time() + 60, time.time() + 60))
    t = chk.check(str(home), as_of="2030-10-02")["tests"]
    assert not any(v["met"] for v in t.values())
    assert any("2 of 2 recording(s)" in g for g in t["segmented"]["gaps"])
    assert any("without slots.csv" in g for g in t["attributed"]["gaps"])
    assert any("answers wait" in g for g in t["answered"]["gaps"])


def test_a_provisional_report_waits_on_the_owner_and_new_days_are_work(home, capsys):
    make_window(home, "2030-09-01_to_2030-09-20", provisional=True)
    chk.main([str(home), "--as-of", "2030-10-02", "--precheck"])
    out = capsys.readouterr().out
    assert out.startswith("WORK: 1 window(s)") and "  window: 2030-09-21_to_2030-09-30" in out
    assert chk.check(str(home), as_of="2030-10-02")["waiting_on_owner"] == ["2030-09-01_to_2030-09-20"]


def test_blank_options_mean_not_given_and_out_writes_json(home, tmp_path):
    out = tmp_path / "after.json"
    assert chk.main([str(home), "--period=", "--window=", "--as-of", "2030-10-02", "--out", str(out)]) == 0
    assert json.loads(out.read_text())["period"] == "2030-09"


def test_bad_arguments_exit_2(home, tmp_path):
    assert chk.main([]) == 2
    assert chk.main([str(tmp_path / "nowhere")]) == 2
    assert chk.main([str(home), "--period", "2030-13"]) == 2


def test_home_comes_from_the_setting_when_not_given(home, tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "settings.toml"
    cfg.write_text(f'[report-time-study]\nhome = "{home}"\n')
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(cfg))
    assert chk.main(["--as-of", "2030-10-02", "--precheck"]) == 0
    assert capsys.readouterr().out.startswith("WORK: 3 window(s)")
