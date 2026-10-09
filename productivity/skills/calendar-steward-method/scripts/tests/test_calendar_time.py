"""calendar-time: meeting hours over a period, with the arithmetic checkable by reading the
dates. The owner's timezone is America/New_York, so a day-bucketing bug would show."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import _common as c  # noqa: E402
import calendar_time as ct  # noqa: E402

NOW = datetime(2030, 3, 9, 12, 0, tzinfo=timezone.utc)
OWNER = "owner@acme.test"
SINCE, UNTIL = "2030-03-02", "2030-03-09"


class FakePortal:
    """Refuses a page above `max_page` (a large response fails outright on the live server) and
    any page holding a `poison` row."""

    def __init__(self, events=(), max_page=50, poison=(), tz="America/New_York", whoami_error=None):
        self.events, self.max_page, self.poison, self.tz = list(events), max_page, set(poison), tz
        self.whoami_error, self.calls = whoami_error, []

    def call(self, tool, args=None):
        args = dict(args or {})
        if tool == "whoami":
            if self.whoami_error:
                raise self.whoami_error
            return {"principal": {"timezone": self.tz, "primary_email": OWNER}, "inboxes": [{"address": OWNER}]}
        self.calls.append(args)
        offset, size = int(args.get("offset") or 0), int(args.get("limit") or self.max_page)
        if size > self.max_page:
            raise RuntimeError("response payload too large")
        window = self.events[offset:offset + size]
        if any(i in self.poison for i in range(offset, offset + len(window))):
            raise RuntimeError("validation error: string_too_long")
        return {"items": window, "total": len(self.events), "has_more": offset + len(window) < len(self.events)}


def event(eid="e1", title="Weekly sync", start="2030-03-05T14:00:00Z", end="2030-03-05T15:00:00Z", kind="meeting",
          attendees=(), **fields):
    base = {"id": eid, "_ref": f"portal://calendar_event/{eid}", "title": title, "start_time": start, "end_time": end,
            "is_all_day": False, "event_kind": kind,
            "attendees": [{"email": a, "name": "x", "response_status": "accepted"} for a in attendees]}
    base.update(fields)
    return base


def run(events=(), portal=None, **kw):
    portal = portal or FakePortal(events)
    return ct.run(portal, since=kw.pop("since", SINCE), until=kw.pop("until", UNTIL), now=NOW, **kw), portal


def titles(result):
    return [r["title"] for r in result["in_scope"]["items"]]


def test_availability_all_day_cancelled_and_unknown_kinds_are_counted_not_hours():
    result, _ = run([event("b1", kind="availability_block"), event("a1", is_all_day=True),
                     event("c1", title="Canceled: Board prep"), event("c2", title="Cancelled: Board prep"),
                     event("x1", kind="focus_time"), event("m1", title="Why it was cancelled")])
    n = result["counts"]
    assert (n["availability_blocks"], n["all_day"], n["cancelled"], n["distinct"]) == (1, 1, 2, 1)
    assert titles(result) == ["Why it was cancelled"] and result["totals"]["hours_sum"] == 1.0
    assert any("focus_time" in w for w in result["warnings"])


def test_a_clone_collapses_onto_the_copy_with_the_most_attendees():
    result, _ = run([event("e1", title="Pipeline review (Clone)"),
                     event("e2", title="RE: Pipeline review", attendees=("dana@northwind.test",)),
                     event("e3", title="Pipeline review", start="2030-03-06T14:00:00Z", end="2030-03-06T15:00:00Z")])
    assert result["counts"]["duplicates_collapsed"] == 1 and result["counts"]["distinct"] == 2
    assert result["in_scope"]["items"][0]["attendee_count"] == 1


def test_scope_by_attendee_domain_or_title_never_the_owners_own_address():
    events = [event("e1", title="Client call", attendees=(OWNER, "dana@northwind.test")),
              event("e2", title="Internal", start="2030-03-05T16:00:00Z", end="2030-03-05T17:00:00Z",
                    attendees=(OWNER, "sam@acme.test")),
              event("e3", title="Northwind baseline", start="2030-03-05T18:00:00Z", end="2030-03-05T18:30:00Z")]
    result, _ = run(events, scope_domains=["@northwind.test", "acme.test"], scope_titles=["(?i)baseline"])
    assert titles(result) == ["Client call", "Internal", "Northwind baseline"]
    by_title = {r["title"]: r for r in result["in_scope"]["items"]}
    assert by_title["Client call"]["matched_by"] == ["attendee_domain"]
    assert by_title["Internal"]["matched_domains"] == ["acme.test"]   # sam, not the owner
    assert by_title["Northwind baseline"]["matched_by"] == ["title"]
    only_owner, _ = run([event("e1", attendees=(OWNER,))], scope_domains=["acme.test"])
    assert only_owner["in_scope"]["meetings"] == 0 and only_owner["out_of_scope"]["meetings"] == 1
    assert "items" not in only_owner["out_of_scope"]


def test_an_exclude_pattern_drops_the_meeting_even_when_in_scope():
    result, _ = run([event("e1", title="Hold: travel", attendees=("dana@northwind.test",))],
                    scope_domains=["northwind.test"], exclude_titles=["(?i)^hold"])
    assert result["counts"]["excluded_by_title"] == 1 and result["in_scope"]["meetings"] == 0


def test_a_bad_regex_is_an_error_not_a_traceback():
    with pytest.raises(c.Bad):
        run([event()], scope_titles=["("])


def test_categories_first_match_wins_and_uncategorised_is_counted(tmp_path):
    path = tmp_path / "cats.toml"
    path.write_text('[categories]\nclient = ["(?i)client"]\ninternal = ["(?i)sync", "(?i)client"]\nidle = ["(?i)nothing"]\n')
    result, _ = run([event("e1", title="Client sync"), event("e2", title="Team sync", start="2030-03-05T16:00:00Z",
                                                            end="2030-03-05T16:30:00Z"),
                     event("e3", title="Lunch", start="2030-03-05T17:00:00Z", end="2030-03-05T18:00:00Z")],
                    categories_path=str(path))
    assert result["in_scope"]["by_category"] == {"client": 1.0, "internal": 0.5, "idle": 0.0, "uncategorised": 1.0}
    with pytest.raises(c.Bad):
        run([event()], categories_path=str(tmp_path / "missing.toml"))


def test_sum_and_union_differ_by_exactly_the_double_booking():
    result, _ = run([event("e1", title="A", start="2030-03-05T14:00:00Z", end="2030-03-05T16:00:00Z"),
                     event("e2", title="B", start="2030-03-05T15:00:00Z", end="2030-03-05T17:00:00Z"),
                     event("e3", title="C", start="2030-03-05T15:15:00Z", end="2030-03-05T15:45:00Z")])
    assert result["totals"] == {"hours_sum": 4.5, "hours_union": 3.0, "double_booked_hours": 1.5}


def test_a_meeting_after_midnight_utc_belongs_to_the_previous_day_in_new_york():
    result, _ = run([event("e1", start="2030-03-06T01:00:00Z", end="2030-03-06T02:00:00Z")])
    assert result["in_scope"]["by_day"] == {"2030-03-05": 1.0}


def test_the_period_defaults_to_the_last_seven_full_days_and_is_half_open():
    portal = FakePortal([])
    result = ct.run(portal, now=NOW)
    assert result["period"]["since_local"].startswith("2030-03-02T00:00") and result["period"]["until_local"].startswith("2030-03-09T00:00")
    assert portal.calls[0]["filters"] == {"since": "2030-03-02T05:00:00Z", "until": "2030-03-09T05:00:00Z"}
    with pytest.raises(c.Bad):
        run([], since="2030-03-09", until="2030-03-02")
    with pytest.raises(c.Bad):
        run([], since="last tuesday")


def test_a_whoami_failure_warns_and_still_reports_the_period():
    result, _ = run([event()], portal=FakePortal([event()], whoami_error=RuntimeError("down")))
    assert result["period"]["timezone"] == "UTC" and any("whoami failed" in w for w in result["warnings"])


def test_the_walk_halves_a_page_too_large_and_steps_over_a_poison_row():
    events = [event(f"e{i}", title=f"Meeting {i}", start=f"2030-03-05T{8 + i:02d}:00:00Z",
                    end=f"2030-03-05T{8 + i:02d}:30:00Z") for i in range(6)]
    portal = FakePortal(events, max_page=4)
    result, _ = run(portal=portal)
    assert [x["limit"] for x in portal.calls][:2] == [50, 25] and result["counts"]["rows_read"] == 6
    result, _ = run(portal=FakePortal(events, poison=[3]))
    assert result["counts"]["rows_read"] == 5 and result["counts"]["unreadable_rows"] == 1
    assert any("would not serialise 1" in w for w in result["warnings"])


def test_a_dead_transport_is_an_error_and_never_an_empty_calendar():
    with pytest.raises(c.Failure, match="could not read any calendar rows"):
        run(portal=FakePortal([event()], max_page=0))


def test_the_command_prints_a_table_or_json_and_never_an_attendee_address(monkeypatch, capsys):
    portal = FakePortal([event(attendees=("dana@northwind.test",))])
    monkeypatch.setattr(c, "client", lambda *a: portal)
    monkeypatch.setattr(sys, "argv", ["calendar_time.py", "--since", SINCE, "--until", UNTIL,
                                      "--scope-domain", "northwind.test"])
    ct.main()
    out = capsys.readouterr()
    assert out.out.startswith("# Meeting time, 2030-03-02 to 2030-03-09") and "dana@" not in out.out
    monkeypatch.setattr(sys, "argv", ["calendar_time.py", "--since", SINCE, "--until", UNTIL, "--json"])
    ct.main()
    payload = json.loads(capsys.readouterr().out)
    assert {"period", "counts", "totals", "in_scope", "notes", "warnings"} <= set(payload) and "explain" not in payload
    monkeypatch.setattr(sys, "argv", ["calendar_time.py", "--scope-title", "("])
    with pytest.raises(SystemExit) as exc:
        ct.main()
    assert exc.value.code == 2
