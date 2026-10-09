"""A fake Insights Portal and invented settings for the nightly-sweep script tests.

Nothing here touches the network. The fake answers the MCP tools the scripts call and refuses
an argument the tool does not take. The data is invented: the owner Dana at Acme Components,
their assistant Sam, a contact Priya at Northwind Traders, in America/Chicago in March 2030.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _common as c  # noqa: E402

OWNER = "10000000-0000-4000-8000-000000000001"
PRIYA = "10000000-0000-4000-8000-000000000002"
NORTHWIND = "20000000-0000-4000-8000-000000000001"
TZ = "America/Chicago"

CREATE_TASK_ARGS = {"title", "description", "domain_id_or_name", "due_date", "priority", "owner_contact_id",
                    "source_reference", "source_email_id", "project_id", "task_contact_id"}
CREATE_NOTE_ARGS = {"title", "content", "associations", "note_type", "tag_names", "is_pinned"}
UPDATE_NOTE_FIELDS = {"title", "content", "is_pinned", "visibility"}

SETTINGS = f"""
portal_mcp_config = "unused.json"

[nightly-sweep-workstream]
timezone = "{TZ}"
assistant_email = "sam@example.com"
portal_brief_email = "brief@example.org"
owner_names = ["Dana", "Dana Reyes"]
firm_names = ["Acme", "Acme Components"]
"""


@pytest.fixture(autouse=True)
def settings_file(tmp_path, monkeypatch):
    path = tmp_path / "settings.toml"
    path.write_text(SETTINGS + f'\nstate = "{tmp_path / "state"}"\n')
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(path))
    monkeypatch.delenv("F3I_TOOLBOX_DRY_RUN", raising=False)
    return path


def set_settings(path, extra):
    """Add lines to the [nightly-sweep-workstream] table (it is the last table in the file)."""
    path.write_text(path.read_text() + "\n" + extra + "\n")


class FakePortal:
    def __init__(self):
        self.emails, self.tasks, self.notes, self.events, self.contacts = [], {}, {}, {}, {}
        self.domains, self.projects, self.bodies, self.calls = [], [], {}, []
        self.ids, self.tick, self.page = 0, 0, 200
        self.fail = {}  # tool -> "error" | "lost" | "note_type"
        self.whoami_ok = True

    def new_id(self):
        self.ids += 1
        return f"90000000-0000-4000-8000-{self.ids:012d}"

    def stamp(self):
        self.tick += 1
        return f"2030-03-07T09:{self.tick // 60:02d}:{self.tick % 60:02d}Z"

    def writes(self):
        return [x for x in self.calls if x[0] in ("create_task", "update_task", "create_note", "update_note")]

    def add_email(self, received_at, sender="priya@example.com", archived=False, direction="received",
                  subject="Hello", recipients=None):
        row = {"id": self.new_id(), "subject": subject, "from_address": sender, "received_at": received_at,
               "is_archived": archived, "direction": direction, "recipient_contact_ids": recipients or []}
        self.emails.append(row)
        return row

    def add_task(self, **fields):
        t = {"id": self.new_id(), "status": "TODO", "description": "", "title": "A task",
             "created_at": f"2030-03-01T00:00:{len(self.tasks):02d}Z", "source_reference": None,
             "owner_contact_id": OWNER, "updated_at": self.stamp()}
        t.update(fields)
        self.tasks[t["id"]] = t
        return t

    def add_note(self, title, content="", created_at="2030-03-06T15:00:00Z", **fields):
        n = {"id": self.new_id(), "title": title, "content": content, "created_at": created_at,
             "updated_at": created_at, "tags": [], "associations": [], "visibility": "PUBLIC"}
        n.update(fields)
        self.notes[n["id"]] = n
        return n

    def add_event(self, start_time):
        e = {"id": self.new_id(), "title": "Supplier review", "start_time": start_time}
        self.events[e["id"]] = e
        return e

    def call(self, tool, args=None):
        args = dict(args or {})
        self.calls.append((tool, args))
        mode = self.fail.get(tool)
        if mode == "error":
            raise RuntimeError(f"{tool} failed")
        return getattr(self, f"_{tool}")(args, mode)

    def _whoami(self, args, mode):
        return {"principal": {"contact_id": OWNER, "timezone": TZ}} if self.whoami_ok else {}

    def _list_entities(self, args, mode):
        kind, f = args["entity_type"], dict(args.get("filters") or {})
        offset, limit = int(args.get("offset") or 0), min(int(args.get("limit") or 25), self.page)
        if kind == "email":
            assert set(f) <= {"since", "until", "direction", "search"}, f  # never is_archived
            since, until = c.parse_time(f.get("since")), c.parse_time(f.get("until"))
            # Inclusive at both ends: the script must cut at until itself.
            rows = [e for e in self.emails if e["direction"] == f.get("direction", e["direction"])
                    and (not since or c.parse_time(e["received_at"]) >= since)
                    and (not until or c.parse_time(e["received_at"]) <= until)]
        elif kind == "task":
            assert set(f) <= {"search", "status"}, f
            statuses = f.get("status") or ["TODO", "IN_PROGRESS", "WAITING"]
            needle = str(f.get("search") or "")
            rows = [t for t in self.tasks.values() if t["status"] in statuses
                    and (needle in t["title"] or needle in (t["description"] or ""))]
        elif kind == "domain":
            rows = [d for d in self.domains if f.get("include_inactive") or d.get("is_active", True)]
        elif kind == "project":
            rows = list(self.projects)
        else:
            rows = []
        page = rows[offset:offset + limit]
        more = offset + limit < len(rows)
        return {"items": [dict(r) for r in page], "total": len(rows), "has_more": more,
                "next_offset": offset + limit if more else None}

    def _search(self, args, mode):
        q = args["query"].strip('"')
        return {"notes": [{"id": n["id"], "title": n["title"], "created_at": n["created_at"],
                           "updated_at": n["updated_at"]}
                          for n in self.notes.values() if q in n["title"] or q in n["content"]]}

    def _get(self, args, mode):
        uid, kind = args["id_or_query"], args["entity_type"]
        if kind == "task" and uid in self.tasks:
            return {"task": dict(self.tasks[uid])}
        if kind == "note" and uid in self.notes:
            return dict(self.notes[uid])
        if kind == "calendar_event" and uid in self.events:
            return {"event": dict(self.events[uid])}
        if kind == "contact" and uid in self.contacts:
            return dict(self.contacts[uid])
        return {"error": "not found"}

    def _email_bodies(self, args, mode):
        assert set(args) == {"ids"}, args
        return {"items": [{"id": i, "found": i in self.bodies, "body": self.bodies.get(i)} for i in args["ids"]]}

    def _create_task(self, args, mode):
        assert set(args) <= CREATE_TASK_ARGS, set(args) - CREATE_TASK_ARGS
        assert args.get("priority") is None or args["priority"] in (1, 2, 3, 4)
        t = self.add_task(title=args["title"], description=args.get("description", ""),
                          source_reference=args.get("source_reference"), owner_contact_id=args.get("owner_contact_id"),
                          priority=args.get("priority"), due_date=args.get("due_date"))
        if mode == "lost":
            raise RuntimeError("the answer was lost")
        return {"id": t["id"]}

    def _update_task(self, args, mode):
        assert set(args) == {"id", "status"}, args
        assert args["status"] != "CANCELLED"
        self.tasks[args["id"]]["status"] = args["status"]
        return {"id": args["id"]}

    def _create_note(self, args, mode):
        assert set(args) <= CREATE_NOTE_ARGS, set(args) - CREATE_NOTE_ARGS
        if mode == "note_type" and "note_type" in args:
            raise RuntimeError("note_type 'meeting-notes' rejected")
        assert args.get("associations"), "a note needs an association"
        stamp = self.stamp()
        n = self.add_note(args["title"], args["content"], created_at=stamp)
        n.update({k: args[k] for k in ("tag_names", "associations", "note_type", "is_pinned") if k in args})
        if mode == "lost":
            raise RuntimeError("the answer was lost")
        return {"id": n["id"]}

    def _update_note(self, args, mode):
        assert set(args) == {"id", "fields"} and set(args["fields"]) <= UPDATE_NOTE_FIELDS, args
        self.notes[args["id"]].update(args["fields"])
        self.notes[args["id"]]["updated_at"] = self.stamp()
        return {"id": args["id"]}


@pytest.fixture
def portal():
    return FakePortal()
