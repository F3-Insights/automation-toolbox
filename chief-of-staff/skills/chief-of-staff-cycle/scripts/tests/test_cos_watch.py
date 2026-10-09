"""The Monitor check: baseline, additions only, each material rule, the day's roll, the
cursor, failures and the output shape, against an invented Portal for Northwind Traders."""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

import _common as c
import cos_watch as w
from conftest import SCRIPTS

NOW = datetime(2030, 3, 5, 17, 0, tzinfo=timezone.utc)  # 11:00 in Chicago
DAY = "2030-03-05"


def iso(dt):
    return dt.isoformat()


class Portal:
    """Two briefings: today's tasks and VIP mail, the week's meetings."""

    def __init__(self, day=DAY):
        self.day = day
        self.overdue, self.due, self.vip, self.meetings = [], [], [], []
        self.down = False
        self.today_extra, self.week_override = {}, None
        self.calls = []

    def call(self, tool, args=None):
        self.calls.append((tool, args))
        assert tool == "briefing", tool
        if self.down:
            raise c.Bad("portal briefing: HTTP 502")
        if args["scope"] == "today":
            out = {"window": {"label": self.day, "start_local": f"{self.day}T00:00:00-06:00"},
                   "tasks": {"overdue": list(self.overdue), "due_in_window": list(self.due)},
                   "emails": {"vip_recent": list(self.vip)}}
            for key, value in self.today_extra.items():
                if key in ("overdue_error", "due_in_window_error"):
                    out["tasks"][key] = value
                else:
                    out[key] = value
            return out
        assert args == {"scope": "week", "sections": ["meetings"]}
        return self.week_override if self.week_override is not None else {"meetings": list(self.meetings)}


def task(i, title=None):
    return {"id": f"task-{i}", "title": title or f"Send the Fabrikam schedule {i}"}


def mail(i, hours_ago=1, sender="Dana Whitfield"):
    return {"id": f"mail-{i}", "subject": f"Contoso renewal {i}", "from_name": sender,
            "from_address": "dana@example.com", "received_at": iso(NOW - timedelta(hours=hours_ago))}


def meeting(i, hours_ahead=3, all_day=False):
    start = NOW + timedelta(hours=hours_ahead)
    return {"id": f"evt-{i}", "title": f"Northwind review {i}", "start_time": iso(start),
            "start_local": (start - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%S-06:00"), "is_all_day": all_day}


def run(portal, since):
    return w.watch(portal, since, now=NOW)


@pytest.fixture
def portal():
    p = Portal()
    p.overdue, p.due, p.vip = [task(1)], [task(2)], [mail(1)]
    p.meetings = [meeting(1), meeting(2, hours_ahead=50)]
    return p


def baseline(portal):
    return run(portal, "")["cursor"]


# --------------------------------------------------------------------------- baseline and additions

def test_the_first_run_reports_nothing_and_returns_the_baseline(portal):
    out = run(portal, "")
    assert out["items"] == [] and out["cursor"].startswith("c1.")
    assert run(portal, out["cursor"]) == {"items": [], "cursor": out["cursor"]}


def test_only_additions_count(portal):
    cursor = baseline(portal)
    portal.overdue, portal.vip = [], []  # gone: not a change
    out = run(portal, cursor)
    assert out["items"] == [] and out["cursor"] != cursor


def test_each_material_rule_is_one_item_with_a_stable_key(portal):
    cursor = baseline(portal)
    portal.overdue.append(task(3, "Approve the Tailspin invoice"))
    portal.due.append(task(4, "Call Adventure Works"))
    portal.vip.append(mail(2))
    portal.meetings.append(meeting(3, hours_ahead=20))
    items = run(portal, cursor)["items"]
    assert [i["key"] for i in items] == ["overdue:task-3", "due-today:task-4", "vip-mail:mail-2", "meeting:evt-3"]
    assert items[0]["summary"] == "Newly overdue: Approve the Tailspin invoice"
    assert items[1]["summary"] == "Due today: Call Adventure Works"
    assert items[2]["summary"] == "VIP mail from Dana Whitfield: Contoso renewal 2"
    assert items[3]["summary"] == "New meeting at 07:00: Northwind review 3"
    assert run(portal, cursor)["items"] == items  # the same change, the same keys


def test_the_returned_cursor_makes_the_same_change_old(portal):
    cursor = baseline(portal)
    portal.vip.append(mail(2))
    after = run(portal, cursor)
    assert len(after["items"]) == 1
    assert run(portal, after["cursor"])["items"] == []


# --------------------------------------------------------------------------- what is not material

def test_old_vip_mail_is_not_new(portal):
    cursor = baseline(portal)
    portal.vip.append(mail(3, hours_ago=30))
    assert run(portal, cursor)["items"] == []
    assert w.watch(portal, cursor, now=NOW, email_hours=48)["items"][0]["key"] == "vip-mail:mail-3"


def test_meetings_far_off_past_or_all_day_are_not_material(portal):
    cursor = baseline(portal)
    portal.meetings += [meeting(4, hours_ahead=30), meeting(5, hours_ahead=-2), meeting(6, hours_ahead=4, all_day=True)]
    out = run(portal, cursor)
    assert out["items"] == []
    portal.meetings.append(meeting(7, hours_ahead=26))
    assert [i["key"] for i in w.watch(portal, out["cursor"], now=NOW, meeting_hours=48)["items"]] == ["meeting:evt-7"]


def test_a_known_meeting_coming_within_a_day_is_not_new(portal):
    cursor = baseline(portal)  # evt-2 is 50 hours out and already known
    later = NOW + timedelta(hours=30)
    assert w.watch(portal, cursor, now=later)["items"] == []


def test_the_days_roll_is_not_a_change_but_mail_and_meetings_still_are(portal):
    cursor = baseline(portal)
    nxt = Portal(day="2030-03-06")
    nxt.overdue = [task(1), task(2)]          # yesterday's due task is now overdue
    nxt.due = [task(8)]                       # due today because the date moved
    nxt.vip = [mail(1), mail(9)]
    nxt.meetings = [meeting(1), meeting(2, hours_ahead=50), meeting(9, hours_ahead=5)]
    out = run(nxt, cursor)
    assert [i["key"] for i in out["items"]] == ["vip-mail:mail-9", "meeting:evt-9"]
    nxt.overdue.append(task(10))
    assert [i["key"] for i in run(nxt, out["cursor"])["items"]] == ["overdue:task-10"]


# --------------------------------------------------------------------------- the cursor

def test_the_cursor_round_trips_and_stays_small():
    current = {"o": [f"t{i}" for i in range(25)], "t": [f"d{i}" for i in range(50)],
           "v": [f"v{i}" for i in range(20)], "m": [f"m{i}" for i in range(50)]}
    cursor = w.encode_cursor(DAY, current)
    day, seen = w.decode_cursor(cursor)
    assert day == DAY and seen["m"] == {w._h(f"m{i}") for i in range(50)}
    assert len(cursor) < 2500


@pytest.mark.parametrize("bad", ["2030-03-05T00:00:00Z", "c1.!!!", "c1." + "e30",  # {} has no date
                                 w.CURSOR_PREFIX + w.base64.urlsafe_b64encode(
                                     b'{"d":"2030-03-05","o":["x"],"t":[],"v":[],"m":[]}').decode()])
def test_a_bad_cursor_is_refused(portal, bad):
    with pytest.raises(c.Bad, match="bad cursor"):
        run(portal, bad)
    assert portal.calls == []  # refused before the Portal is read


# --------------------------------------------------------------------------- failures

def test_the_portal_down_fails(portal):
    portal.down = True
    with pytest.raises(c.Bad, match="HTTP 502"):
        run(portal, "")


@pytest.mark.parametrize("extra, week, why", [
    ({"overdue_error": "timeout"}, None, "overdue failed"),
    ({"due_in_window_error": "refused"}, None, "due_in_window failed"),
    ({"emails": {"error": "boom"}}, None, "VIP mail section failed"),
    ({"window": {}}, None, "no local date"),
    ({}, {"meetings": {"error": "calendar sync"}}, "meetings came back unreadable"),
])
def test_a_failed_section_fails_rather_than_looking_empty(portal, extra, week, why):
    portal.today_extra, portal.week_override = extra, week
    with pytest.raises(c.Bad, match=why):
        run(portal, "")


# --------------------------------------------------------------------------- the command line

def cli(*args):
    env = {k: v for k, v in os.environ.items() if k != "INSIGHTS_PORTAL_ASSISTANT_TOKEN"}
    return subprocess.run([sys.executable, str(SCRIPTS / "cos_watch.py"), *args],
                          capture_output=True, text=True, env=env)


def test_the_command_line_prints_one_json_object(monkeypatch, portal, capsys):
    monkeypatch.setattr(c, "Portal", lambda: portal)
    with pytest.raises(SystemExit) as done:
        w.main(["--since="])
    out = capsys.readouterr()
    assert done.value.code == 0 and out.err == ""
    body = json.loads(out.out)
    assert set(body) == {"items", "cursor"} and body["items"] == [] and out.out.count("\n") == 1
    portal.vip.append(mail(5))
    with pytest.raises(SystemExit):
        w.main([f"--since={body['cursor']}"])
    body2 = json.loads(capsys.readouterr().out)
    assert body2["items"] == [{"key": "vip-mail:mail-5", "summary": "VIP mail from Dana Whitfield: Contoso renewal 5"}]


def test_the_command_line_fails_with_one_line_on_stderr(monkeypatch, portal, capsys):
    portal.down = True
    monkeypatch.setattr(c, "Portal", lambda: portal)
    with pytest.raises(SystemExit) as done:
        w.main(["--since="])
    out = capsys.readouterr()
    assert done.value.code == 2 and out.out == ""
    assert out.err.startswith("cos_watch: portal briefing: HTTP 502") and out.err.count("\n") == 1


def test_a_bad_cursor_on_the_command_line_exits_non_zero():
    done = cli("--since=not-a-cursor")
    assert done.returncode == 2 and done.stdout == "" and "bad cursor" in done.stderr


def test_no_portal_setting_exits_non_zero():
    done = cli("--since=")  # the invented settings name no portal_mcp_config
    assert done.returncode == 2 and done.stdout == "" and "portal_mcp_config" in done.stderr
