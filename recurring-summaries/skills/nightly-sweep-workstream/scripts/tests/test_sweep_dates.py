"""sweep_dates.py: local-day windows, which dates a run takes, catch-up, retries, in-progress marks."""

import json
from datetime import date, datetime, timedelta, timezone

import pytest

import _common as c
import sweep_dates as sd
from conftest import TZ, FakePortal

UTC = timezone.utc
DAY = "2030-03-06"
AT_0040 = datetime(2030, 3, 7, 6, 40, tzinfo=UTC)  # 00:40 in Chicago (CST) on 03-07


def plan(ledger, now, **kw):
    return sd.plan(ledger, now, TZ, **kw)


def dates_of(out):
    return [d["date"] for d in out["dates"]]


def test_the_window_is_the_local_day_not_the_utc_day():
    [d] = plan({"2030-03-05": {}}, AT_0040)["dates"]
    assert d["date"] == DAY and d["weekday"] == "Wednesday"
    assert d["email_window"]["since"] == "2030-03-06T06:00:00Z"
    assert d["email_window"]["until"] == "2030-03-07T06:00:00Z"
    assert d["next_day"] == "2030-03-07" and d["next_day_weekday"] == "Thursday"
    assert d["calendar_window"]["since"] == "2030-03-07T06:00:00Z"


@pytest.mark.parametrize("day,since,until,hours", [
    ("2030-03-10", "2030-03-10T06:00:00Z", "2030-03-11T05:00:00Z", 23),  # clocks go forward
    ("2030-11-03", "2030-11-03T05:00:00Z", "2030-11-04T06:00:00Z", 25),  # clocks go back
])
def test_the_window_holds_across_the_clock_changes(day, since, until, hours):
    w = c.local_day(date.fromisoformat(day), c.zone(TZ))
    assert (w["since"], w["until"]) == (since, until)
    assert c.parse_time(w["until"]) - c.parse_time(w["since"]) == timedelta(hours=hours)


def test_window_boundaries_since_inclusive_until_exclusive():
    w = c.local_day(date(2030, 3, 6), c.zone(TZ))
    assert c.in_window("2030-03-06T06:00:00Z", w)
    assert c.in_window("2030-03-07T05:59:59Z", w)
    assert not c.in_window("2030-03-07T06:00:00Z", w)


def test_a_run_after_midnight_sweeps_yesterday_and_never_a_day_still_open():
    assert dates_of(plan({"2030-03-05": {}}, AT_0040)) == [DAY]
    late_evening = datetime(2030, 3, 7, 5, 30, tzinfo=UTC)  # 23:30 on 03-06 local: 03-06 is still open
    assert dates_of(plan({"2030-03-05": {}}, late_evening)) == []


def test_calendar_prep_preps_the_day_that_has_just_started():
    [d] = plan({"2030-03-05": {}}, AT_0040)["dates"]
    assert d["calendar_prep"] is True and d["relationship_check"] is True


def test_missed_nights_are_caught_up_oldest_first_three_a_run():
    out = plan({"2030-03-01": {}}, AT_0040)
    assert dates_of(out) == ["2030-03-02", "2030-03-03", "2030-03-04"]
    assert out["waiting_for_next_run"] == ["2030-03-05", DAY]
    assert [d["relationship_check"] for d in out["dates"]] == [False, False, True]
    assert [d["calendar_prep"] for d in out["dates"]] == [False, False, False]


def test_a_gap_older_than_the_lookback_is_reported_not_swept():
    out = plan({"2030-02-20": {}}, AT_0040)
    assert "2030-02-21" in out["beyond_lookback"]
    assert dates_of(out)[0] == "2030-02-28"


def test_a_named_date_is_swept_whatever_the_ledger_says():
    out = plan({DAY: {"completed_at": "x"}}, AT_0040, explicit=DAY)
    assert dates_of(out) == [DAY] and any("already swept" in n for n in out["notes"])
    with pytest.raises(c.Stop):
        plan({}, AT_0040, explicit="2030-03-08")


def test_today_may_be_named_but_is_said_to_be_open():
    out = plan({}, AT_0040, explicit="2030-03-07")
    assert dates_of(out) == ["2030-03-07"] and any("not over" in n for n in out["notes"])


def test_an_incomplete_date_is_offered_again_at_most_twice():
    ledger = {"2030-03-05": {"complete": False, "attempts": 1}}
    assert "2030-03-05" in dates_of(plan(ledger, AT_0040))
    ledger = {"2030-03-05": {"complete": False, "attempts": 3}}
    out = plan(ledger, AT_0040)
    assert "2030-03-05" not in dates_of(out) and out["incomplete_gave_up"] == ["2030-03-05"]


def test_a_date_another_run_is_sweeping_is_not_taken_twice(tmp_path):
    busy = {DAY: {"started_at": (AT_0040 - timedelta(hours=1)).isoformat(), "run": "other"}}
    out = plan({"2030-03-05": {}}, AT_0040, in_progress=busy)
    assert dates_of(out) == [] and out["in_progress_elsewhere"] == [DAY]
    refused = plan({}, AT_0040, explicit=DAY, in_progress=busy)
    assert refused["status"] == "refused" and refused["code"] == "IN_PROGRESS"
    stale = {DAY: {"started_at": (AT_0040 - timedelta(hours=4)).isoformat(), "run": "other"}}
    assert dates_of(plan({"2030-03-05": {}}, AT_0040, in_progress=stale)) == [DAY]
    root = tmp_path / "state"
    sd.take(root, AT_0040, TZ, 3, 7, DAY, "run-a", False)
    again = sd.take(root, AT_0040, TZ, 3, 7, DAY, "run-b", False)
    assert again["code"] == "IN_PROGRESS"


def test_an_empty_ledger_with_no_daily_note_sweeps_the_newest_two():
    assert dates_of(plan({}, AT_0040)) == ["2030-03-05", DAY]


def test_an_empty_ledger_reaches_back_to_the_day_before_the_newest_daily_note():
    assert dates_of(plan({}, AT_0040, last_note="2030-03-05")) == ["2030-03-04", "2030-03-05", DAY]
    out = plan({}, AT_0040, last_note="2030-03-02")
    assert dates_of(out) == ["2030-03-04", "2030-03-05", DAY] and out["beyond_lookback"] == ["2030-03-01",
                                                                                            "2030-03-02",
                                                                                            "2030-03-03"]


def test_cli_writes_dates_json_marks_the_dates_and_finds_the_newest_daily_note(tmp_path, capsys):
    portal = FakePortal()
    portal.add_note("Daily Note - 2030-03-05")
    run = tmp_path / "run"
    with pytest.raises(SystemExit) as code:
        sd.main(["--run", str(run), "--now", AT_0040.isoformat()], client=portal)
    assert code.value.code == 0
    out = json.loads(capsys.readouterr().out)
    saved = json.loads((run / "dates.json").read_text())
    assert dates_of(saved) == ["2030-03-04", "2030-03-05", DAY] and saved["dry_run"] is False
    assert saved["vip_stale_days"] == 30 and out["status"] == "ok"
    ledger = json.loads((tmp_path / "state" / "ledger.json").read_text())
    assert set(ledger["in_progress"]) == {"2030-03-04", "2030-03-05", DAY}


def test_a_dry_run_sets_no_mark(tmp_path, capsys):
    with pytest.raises(SystemExit):
        sd.main(["--run", str(tmp_path / "run"), "--dry-run", "--date", DAY, "--now", AT_0040.isoformat()],
                client=FakePortal())
    assert json.loads((tmp_path / "run" / "dates.json").read_text())["dry_run"] is True
    assert not (tmp_path / "state" / "ledger.json").exists()


def test_vip_staleness_is_a_setting_with_a_safe_default(settings_file):
    from conftest import set_settings
    assert c.vip_stale_days() == (30, None)
    set_settings(settings_file, "vip_stale_days = 45")
    assert c.vip_stale_days() == (45, None)


def test_an_unusable_vip_staleness_falls_back_with_a_note(settings_file):
    from conftest import set_settings
    set_settings(settings_file, "vip_stale_days = 0")
    days, note = c.vip_stale_days()
    assert days == 30 and "default" in note


def test_without_a_timezone_it_stops(settings_file, tmp_path, capsys):
    settings_file.write_text('[nightly-sweep-workstream]\nstate = "x"\n')
    with pytest.raises(SystemExit) as code:
        sd.main(["--run", str(tmp_path / "r")], client=FakePortal())
    assert code.value.code == 2 and "timezone" in capsys.readouterr().out


def test_state_inside_the_skill_folder_is_refused():
    with pytest.raises(c.Stop):
        c.guard_run_path(str(c.SKILL_DIR / "scripts" / "state"))


def test_run_folder_anywhere_in_the_toolbox_checkout_is_refused(tmp_path, monkeypatch):
    repo = tmp_path / "toolbox"
    skill = repo / "dept" / "skills" / "nightly-sweep-workstream"
    skill.mkdir(parents=True)
    (repo / ".git").mkdir()
    monkeypatch.setattr(c, "SKILL_DIR", skill)
    with pytest.raises(c.Stop):
        c.guard_run_path(str(repo / "runs" / "2030-03-07"))
    assert c.guard_run_path(str(tmp_path / "elsewhere")) == (tmp_path / "elsewhere").resolve()
