"""meeting_prep_pick.py on an invented owner at Northwind Traders (northwind.test, his own firm)
who also holds an address at a client, Contoso (contoso.test). The day is Thursday 2030-03-07
in Los Angeles, whose window is 08:00Z on the 7th to 08:00Z on the 8th."""

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _common as c  # noqa: E402
import meeting_prep_pick as mp  # noqa: E402

OWNER = "00000900-1111-4111-8111-111111111111"
DAY = "2030-03-07"
MORNING = datetime(2030, 3, 7, 15, 0, tzinfo=timezone.utc)      # 07:00 in Los Angeles
EVENING = datetime(2030, 3, 8, 1, 0, tzinfo=timezone.utc)       # 17:00 on the 7th in Los Angeles


def uid(n):
    return f"{n:08d}-2222-4222-8222-222222222222"


def event(n, title, start, end, attendees=(), **kw):
    row = {"id": uid(n), "_ref": f"portal://calendar_event/{uid(n)}", "title": title, "event_kind": "meeting",
           "start_time": f"{DAY}T{start}:00Z", "end_time": f"{DAY}T{end}:00Z",
           "attendees": [{"email": a} for a in attendees], "is_all_day": False}
    row.update(kw)
    return row


ME = "owner@northwind.test"


class FakePortal:
    def __init__(self, events=(), notes=(), details=None, page=200, fail_list=0, empty_first=False):
        self.events, self.notes, self.details = list(events), list(notes), details or {}
        self.page, self.fail_list, self.empty_first, self.calls = page, fail_list, empty_first, []

    def call(self, tool, args=None):
        args = args or {}
        self.calls.append((tool, args))
        if tool == "whoami":
            return {"principal": {"contact_id": OWNER, "timezone": "America/Los_Angeles"},
                    "inboxes": [{"address": ME}, {"address": "owner@contoso.test"}]}
        if tool == "list_entities":
            assert args["entity_type"] == "calendar_event"
            if self.fail_list:
                self.fail_list -= 1
                raise c.PortalError("portal list_entities: response too large")
            if self.empty_first:
                self.empty_first = False
                return {"items": [], "has_more": False, "total": 0}
            f = args["filters"]
            rows = [e for e in self.events if f["since"] <= e["start_time"] < f["until"]]
            offset, limit = int(args.get("offset") or 0), min(args["limit"], self.page)
            window = rows[offset:offset + limit]
            more = offset + len(window) < len(rows)
            return {"items": window, "has_more": more, "total": len(rows)}
        if tool == "get":
            return self.details.get(args["id_or_query"], {"event": {}})
        if tool == "search":
            return {"notes": [n for n in self.notes if args["query"].lower() in n["title"].lower()]}
        raise AssertionError(f"the pick called {tool}, which it never should")


def run(portal, *extra, now=MORNING, capsys=None):
    with pytest.raises(SystemExit) as done:
        mp.main(["--day", DAY, *extra], portal=portal, now=now)
    return done.value.code, capsys.readouterr()


def picks(portal, *extra, capsys):
    code, out = run(portal, *extra, capsys=capsys)
    assert code == 0, out
    return json.loads(out.out)


def test_classifies_skips_and_ranks(capsys):
    events = [
        event(1, "Board prep", "17:00", "18:00", [ME, "dana@fabrikam.test"],
              organizer_email=ME, recurring_event_id=None),                                       # rank 1
        event(2, "Pricing call", "16:00", "17:00", ["lee@fabrikam.test"], recurring_event_id="s1",
              organizer_email="lee@fabrikam.test"),                                                # rank 2
        event(3, "Coffee", "18:00", "18:30"),                                                    # rank 3: one-off,
                                                                                                   # nobody invited
        event(4, "Gym", "14:00", "15:00"),                                                         # personal
        event(5, "Team standup", "15:30", "15:45", ["ana@northwind.test"]),                       # internal recurring
        event(6, "Canceled: Vendor demo", "19:00", "20:00", ["vic@fabrikam.test"]),               # cancelled
        event(7, "Holiday", "08:00", "08:00", is_all_day=True),                                    # all day
        event(8, "Planning", "20:00", "21:00", ["ana@northwind.test"]),                           # internal
        event(9, "Dentist", "21:00", "22:00", ["front@smiles.test"]),                             # private, even with others
    ]
    result = picks(FakePortal(events), capsys=capsys)
    assert [(p["title"], p["rank"]) for p in result["picks"]] == [
        ("Board prep", 1), ("Pricing call", 2), ("Coffee", 3)]
    reasons = {s["title"]: s["reason"] for s in result["skipped"]}
    assert reasons == {"Gym": "personal", "Team standup": "internal recurring", "Canceled: Vendor demo": "cancelled",
                       "Holiday": "all day", "Planning": "internal", "Dentist": "personal"}
    first = result["picks"][0]
    assert first["owner_role"] == "organizer" and first["note_title"] == "Meeting Prep: Board prep - 2030-03-07"
    assert first["start_local"] == "09:00" and first["external_domains"] == ["fabrikam.test"]
    assert ME not in first["attendees"]
    assert result["window"] == {"since": "2030-03-07T08:00:00Z", "until": "2030-03-08T08:00:00Z"}


def test_the_cap_drops_lower_ranks_and_lists_them(capsys):
    events = [event(n, f"Client call {n}", f"{10 + n}:00", f"{10 + n}:30", [f"p{n}@fabrikam.test"],
                    recurring_event_id="s") for n in range(1, 5)]
    events.append(event(9, "Workshop with Fabrikam", "22:00", "23:00", ["kim@fabrikam.test"], recurring_event_id="s"))
    result = picks(FakePortal(events), "--cap", "2", capsys=capsys)
    assert [p["title"] for p in result["picks"]] == ["Workshop with Fabrikam", "Client call 1"]
    assert [d["title"] for d in result["dropped"]] == ["Client call 2", "Client call 3", "Client call 4"]
    assert result["dropped"][0]["reason"] == "cap" and result["dropped"][0]["rank"] == 2
    assert result["dropped"][0]["attendees"] == ["p2@fabrikam.test"]


def test_an_already_prepped_meeting_takes_its_place_and_is_left_alone(capsys):
    events = [event(1, "Client call", "17:00", "18:00", ["dana@fabrikam.test"]),
              event(2, "Intro call", "19:00", "19:30", ["lee@fabrikam.test"])]
    notes = [{"id": uid(50), "title": "Meeting Prep: Client call - 2030-03-07"},
             {"id": uid(51), "title": "Meeting Prep: Intro call - 2030-03-06"}]           # another day: not this one
    result = picks(FakePortal(events, notes), "--cap", "1", capsys=capsys)
    assert result["prepped"][0]["note"] == f"portal://note/{uid(50)}"
    assert result["picks"] == [] and result["dropped"][0]["title"] == "Intro call"
    code, out = run(FakePortal(events, notes), "--cap", "1", "--precheck", capsys=capsys)
    assert code == 0 and out.out.startswith("NOTHING: no external meeting left to prep on 2030-03-07")


def test_a_clients_staff_meeting_counts_only_when_long_enough(capsys):
    events = [event(1, "Finance staff meeting", "17:00", "18:00", ["cfo@contoso.test", "ap@contoso.test"]),
              event(2, "Contoso check-in", "19:00", "19:20", ["ap@contoso.test"]),
              event(3, "Firm sync", "20:00", "21:00", ["ana@northwind.test"])]
    result = picks(FakePortal(events), "--home-domains", "northwind.test", "--staff-minutes", "30", capsys=capsys)
    assert [(p["title"], p["rank"]) for p in result["picks"]] == [("Finance staff meeting", 4)]
    assert {s["title"]: s["reason"] for s in result["skipped"]} == {"Contoso check-in": "internal",
                                                                   "Firm sync": "internal"}
    result = picks(FakePortal(events), capsys=capsys)                    # no staff rule: all internal
    assert result["picks"] == []


def test_the_organizer_is_read_from_the_event_when_the_listing_lacks_it(capsys):
    events = [event(1, "Supplier call", "17:00", "18:00", ["dana@fabrikam.test"])]
    details = {uid(1): {"event": {"organizer_email": ME, "recurring_event_id": None}}}
    result = picks(FakePortal(events, details=details), capsys=capsys)
    assert result["picks"][0]["owner_role"] == "organizer" and result["picks"][0]["rank"] == 1


def test_clones_collapse_to_the_copy_with_most_attendees(capsys):
    events = [event(1, "Client call", "17:00", "18:00", []),
              event(2, "Client call (clone)", "17:00", "18:00", ["dana@fabrikam.test"])]
    result = picks(FakePortal(events), capsys=capsys)
    assert result["counts"]["events"] == 1 and result["picks"][0]["event"].endswith(uid(2))


def test_a_page_too_large_is_asked_for_again_smaller(capsys):
    events = [event(1, "Client call", "17:00", "18:00", ["dana@fabrikam.test"])]
    portal = FakePortal(events, fail_list=1)
    result = picks(portal, capsys=capsys)
    sizes = [a["limit"] for t, a in portal.calls if t == "list_entities"]
    assert sizes[:2] == [50, 25] and len(result["picks"]) == 1


def test_an_empty_weekday_is_listed_twice_before_it_is_trusted(capsys):
    portal = FakePortal([event(1, "Client call", "17:00", "18:00", ["dana@fabrikam.test"])], empty_first=True)
    result = picks(portal, capsys=capsys)
    assert len(result["picks"]) == 1


def test_a_portal_that_cannot_be_read_is_never_a_quiet_day(capsys):
    code, out = run(FakePortal(fail_list=99), "--precheck", capsys=capsys)
    assert code == 2 and out.out == "" and "could not list the calendar" in out.err


def test_precheck_says_work_and_out_writes_picks(tmp_path, capsys):
    target = tmp_path / "run" / "picks.json"
    events = [event(1, "Client call", "17:00", "18:00", ["dana@fabrikam.test"])]
    code, out = run(FakePortal(events), "--precheck", "--out", str(target), capsys=capsys)
    assert code == 0 and out.out.startswith("WORK: 1 meeting(s) to prep on 2030-03-07")
    assert json.loads(target.read_text())["picks"][0]["title"] == "Client call"


@pytest.mark.parametrize("text, now, want", [("", MORNING, "2030-03-07"), ("", EVENING, "2030-03-08"),
                                             ("next-working-day", datetime(2030, 3, 9, 1, 0, tzinfo=timezone.utc),
                                              "2030-03-11"),
                                             ("tomorrow", MORNING, "2030-03-08"), ("2030-03-20", MORNING, "2030-03-20")])
def test_the_day_is_resolved_in_the_owners_zone(text, now, want):
    local = now.astimezone(c.ZoneInfo("America/Los_Angeles"))
    assert mp.resolve_day(text, local.date(), local.hour) == date.fromisoformat(want)


def test_a_bad_day_is_refused(capsys):
    with pytest.raises(SystemExit) as done:
        mp.main(["--day", "someday"], portal=FakePortal(), now=MORNING)
    assert done.value.code == 2 and "--day" in capsys.readouterr().out
