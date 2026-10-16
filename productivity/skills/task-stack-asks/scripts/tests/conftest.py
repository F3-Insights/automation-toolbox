"""Shared test data: an in-memory Insights Portal for an invented owner, Dana at Northwind
Traders, with the clock pinned to Monday 2030-03-04 12:00 UTC. Nothing touches the network."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _common as c  # noqa: E402

NOW = datetime(2030, 3, 4, 12, 0, tzinfo=timezone.utc)


def uid(n):
    return f"{n:08d}-2222-4222-8222-222222222222"


OWNER, CEO, BOARD, STAFF, OUTSIDER = uid(900), uid(901), uid(902), uid(903), uid(904)
D_NW, P_NW_GENERAL, CO_NW = uid(800), uid(700), uid(600)

DOMAIN_FILE = """# Northwind

Facts about the domain.

```yaml
vip:
  - {company: "Northwind Traders", roles: [board_member, founder], titles: ["chief executive"]}
mail:
  inboxes: [dana@northwind.test]
  correspondent_domains: [northwind.test]
ignore:
  senders: ["*@notify.northwind.test"]
```
"""


def ago(hours):
    return (NOW - timedelta(hours=hours)).isoformat().replace("+00:00", "Z")


def email(n, direction, hours, sender, to, contact=None, recipients=(), subject="Re: rates"):
    return {"id": uid(n), "direction": direction, "received_at": ago(hours), "from_address": sender,
            "to_addresses": list(to), "recipient_contact_ids": list(recipients), "contact_id": contact,
            "subject": subject, "received_local": ago(hours)}


def default_emails():
    return [
        email(1, "received", 5, "ceo@northwind.test", ["dana@northwind.test"], CEO, [OWNER], "Board pack"),
        email(2, "received", 2, "kim@northwind.test", ["dana@northwind.test"], STAFF, [OWNER], "Lease"),
        email(3, "sent", 3, "dana@northwind.test", ["kim@northwind.test"], OWNER, [STAFF], "Send me the lease"),
        email(4, "received", 1, "alerts@notify.northwind.test", ["dana@northwind.test"], None, [OWNER]),
        email(5, "received", 4, "pat@fabrikam.test", ["dana@personal.test"], OUTSIDER, [OWNER], "Golf"),
        email(6, "sent", 6, "dana@personal.test", ["board@northwind.test"], OWNER, [BOARD], "Q1 numbers"),
        email(7, "received", 24 * 40, "ceo@northwind.test", ["dana@northwind.test"], CEO, [OWNER], "Old"),
    ]


class FakePortal(c.Portal):
    """The Portal's answers for the calls task-asks makes; list_all pages through `call`."""

    def __init__(self, emails=None, meetings=None, tasks=None):
        self.emails = default_emails() if emails is None else emails
        self.meetings = meetings if meetings is not None else [
            {"id": "rec1", "calendar_event_id": uid(500), "note_id": uid(501), "started_at": ago(8)},
            {"id": "rec2", "calendar_event_id": uid(502), "note_id": uid(503), "started_at": ago(9)},
            {"id": "rec3", "calendar_event_id": None, "started_at": ago(9)},
        ]
        self.events = {
            uid(500): {"event": {"id": uid(500), "title": "Board prep", "organizer_email": "dana@northwind.test",
                                 "start_local": ago(8)},
                       "attendee_emails": ["board@northwind.test", "Kim@northwind.test", "guest@northwind.test"]},
            uid(502): {"event": {"id": uid(502), "title": "Family dinner", "organizer_email": "dana@personal.test",
                                 "start_local": ago(9)}, "attendee_emails": ["sam@home.test"]},
        }
        self.tasks = tasks or []
        self.contacts = {CEO: ("VIP", "ceo@northwind.test"), BOARD: ("VIP", "board@northwind.test"),
                         STAFF: ("Kim Lee", "kim@northwind.test")}
        self.calls = []

    def call(self, tool, args=None):
        args = dict(args or {})
        self.calls.append((tool, args))
        if tool == "whoami":
            return {"principal": {"contact_id": OWNER, "primary_email": "dana@northwind.test",
                                  "timezone": "America/Los_Angeles"},
                    "inboxes": [{"address": "dana@northwind.test"}, {"address": "dana@personal.test"}]}
        if tool == "list_relationships":
            return {"relationships": [
                {"contact_id": CEO, "relationship_type": "employee", "title": "Chief Executive Officer", "is_current": True},
                {"contact_id": BOARD, "relationship_type": "board_member", "title": None, "is_current": True},
                {"contact_id": STAFF, "relationship_type": "employee", "title": "Controller", "is_current": True},
                {"contact_id": uid(905), "relationship_type": "board_member", "is_current": False},
                {"contact_id": OWNER, "relationship_type": "founder", "is_current": True}]}
        if tool == "get":
            if args["entity_type"] == "contact":  # by id, or by address as the contact's natural key
                key = args["id_or_query"]
                cid = key if key in self.contacts else next((i for i, (_, a) in self.contacts.items() if a == key), None)
                if cid is None:
                    raise c.PortalError("portal get: not found")
                name, addr = self.contacts[cid]
                return {"contact": {"id": cid, "full_name": name, "primary_email": addr}, "emails": [{"address": addr}]}
            return self.events[args["id_or_query"]]
        if tool == "list_fellow_meetings":
            return {"meetings": self.meetings, "next_offset": None}
        if tool == "list_entities":
            kind, f = args["entity_type"], args.get("filters") or {}
            if kind == "domain":
                rows = [{"id": D_NW, "name": "Northwind"}, {"id": uid(801), "name": "Home"}]
            elif kind == "project":
                rows = [{"id": P_NW_GENERAL, "domain_id": D_NW, "is_general": True}]
            elif kind == "company":
                rows = [{"id": CO_NW, "name": "Northwind Traders"}]
            elif kind == "email":
                rows = [e for e in self.emails if e["direction"] == f["direction"] and e["received_at"] >= f["since"]]
            elif kind == "task":
                rows = [t for t in self.tasks if f["search"] in t["description"]]
            else:
                raise AssertionError(kind)
            return {"items": rows, "has_more": False, "next_offset": None}
        raise AssertionError(f"task-asks called {tool}, which it never should")


@pytest.fixture(autouse=True)
def settings(tmp_path, monkeypatch):
    path = tmp_path / "settings.toml"
    path.write_text(f'state_dir = "{tmp_path / "state"}"\n', encoding="utf-8")
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(path))
    return path


@pytest.fixture
def domain_file(tmp_path):
    p = tmp_path / "northwind.md"
    p.write_text(DOMAIN_FILE, encoding="utf-8")
    return p
