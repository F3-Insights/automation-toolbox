import json
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

import _common as c
import email_context_pack as ecp
from reply_fixtures import portal, run  # noqa: F401


def test_the_pack_carries_every_part_with_its_ref(portal, capsys):
    code, pack = run(ecp, capsys, "portal://email/m3", "--contact", "c-dana")
    assert code == 0
    assert pack["email"]["_ref"] == "portal://email/m3" and pack["email"]["body"].startswith("Can we meet")
    assert all(m["_ref"].startswith("portal://email/") and m["body"] for m in pack["thread"])
    assert pack["contact"]["_ref"] == "portal://contact/c-dana"
    assert pack["contact"]["addresses"] == ["dana@acme.test"]
    assert pack["tasks"][0]["_ref"] == "portal://task/t1"
    assert pack["projects"][0]["name"] == "Acme rollout"
    assert [v["id"] for v in pack["voice_samples"]] == ["m1"]
    cal = pack["calendar"]
    assert cal["asked_to_meet"] is True and cal["slots"] and len(cal["days"]) == 10
    assert cal["timezone"] == "America/New_York"


def test_no_meeting_ask_means_null_calendar_with_a_reason(portal, capsys):
    portal.emails["m3"]["body"] = "Thanks, the invoice is paid.\n\nOn Tue the owner wrote:\n> can we meet"
    code, pack = run(ecp, capsys, "m3")
    assert code == 0 and pack["calendar"] is None
    assert any(u["field"] == "calendar" and "does not appear to ask to meet" in u["reason"] for u in pack["unknown"])
    assert pack["contact"]["id"] == "c-dana"   # the sender, with no --contact


def test_a_failed_read_is_null_with_a_reason_never_an_empty_list(portal, capsys, monkeypatch):
    real = portal.list_entities

    def flaky(a):
        if a["entity_type"] == "task":
            raise RuntimeError("down")
        return real(a)
    monkeypatch.setattr(portal, "list_entities", flaky)
    code, pack = run(ecp, capsys, "m3", "--slots", "no")
    assert code == 0 and pack["tasks"] is None and pack["projects"] is None
    assert {u["field"] for u in pack["unknown"]} >= {"tasks", "projects", "calendar"}


def test_out_writes_the_file_and_refuses_a_path_inside_the_toolbox(portal, capsys, tmp_path):
    target = tmp_path / "run" / "pack.json"
    code, out = run(ecp, capsys, "m3", "--out", target)
    assert code == 0 and out["path"] == str(target)
    assert json.loads(target.read_text())["email_ref"] == "portal://email/m3"
    inside = c.toolbox_root() / "pack.json"
    code, out = run(ecp, capsys, "m3", "--out", inside)
    assert code == 2 and "inside the toolbox" in out["reason"] and not inside.exists()


def test_free_slots_skip_busy_time_and_keep_working_hours():
    tz = ZoneInfo("America/New_York")
    day = date(2030, 3, 4)   # a Monday
    busy = c.Event({"start_time": "2030-03-04T15:00:00Z", "end_time": "2030-03-04T16:30:00Z", "title": "x"})
    slots = ecp.free_slots([busy], [day], tz, datetime(2030, 3, 1, tzinfo=timezone.utc))["slots"]
    assert [(s["start_local"][11:16], s["end_local"][11:16]) for s in slots] == [("09:00", "10:00"), ("11:30", "17:00")]
    assert ecp.working_days(day, 6)[-1].isoformat() == "2030-03-11"


def test_run_files_are_refused_inside_the_toolbox(tmp_path):
    with pytest.raises(c.Failure):
        c.guard_run_path(str(c.toolbox_root() / "x.json"))
    assert c.guard_run_path(str(tmp_path / "x.json")) == (tmp_path / "x.json").resolve()
