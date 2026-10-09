"""An in-memory Portal for the calendar steward's scripts, and a stand-in for task-stack-apply.
Invented data: the owner works at Acme Components; the day is Monday 2030-03-04 in New York,
07:00 local."""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

import _common as c

DAY = date(2030, 3, 4)
NOW = datetime(2030, 3, 4, 12, 0, tzinfo=timezone.utc)   # 07:00 in New York
ME = "owner@acme.test"


def uid(n):
    return f"{n:08d}-0000-4000-8000-000000000000"


OWNER, PROJECT = uid(900), uid(700)


def ev(n, title, start, end, kind="meeting", people=(), organizer=None, description="", owner_response="accepted"):
    attendees = [{"email": ME, "name": "Owner", "response_status": owner_response}] if kind == "meeting" else []
    attendees += [{"email": p, "name": p.split("@")[0], "response_status": "accepted"} for p in people]
    return {"id": uid(n), "_ref": f"portal://calendar_event/{uid(n)}", "title": title, "event_kind": kind,
            "start_time": start, "end_time": end, "is_all_day": False, "attendees": attendees,
            "calendar_name": "Calendar", "_organizer": organizer or ME, "_description": description}


def corpus():
    return [
        ev(1, "Acme ops weekly", "2030-03-04T14:00:00Z", "2030-03-04T15:00:00Z",
           people=("priya@acme.test", "sam@acme.test"), organizer="priya@acme.test"),
        ev(2, "Carrier review", "2030-03-04T14:30:00Z", "2030-03-04T15:30:00Z", people=("jordan@fabrikam.test",),
           organizer="jordan@fabrikam.test", owner_response="needsAction",
           description="Agenda: rates for the second quarter, the claims backlog and the new lane."),
        ev(3, "Deep Work", "2030-03-04T16:00:00Z", "2030-03-04T18:00:00Z", kind="availability_block"),
        ev(4, "Vendor sync", "2030-03-04T17:00:00Z", "2030-03-04T17:30:00Z", people=("marcus@acme.test",),
           description="Walk through the vendor scorecard and the next steps for the audit."),
        ev(5, "Admin hold", "2030-03-05T19:00:00Z", "2030-03-05T20:00:00Z", kind="availability_block"),
    ]


class FakePortal:
    def __init__(self):
        self.events = corpus()
        self.tasks, self.comments, self.calls, self.tick = {}, {}, [], 0

    def stamp(self):
        self.tick += 1
        return (NOW - timedelta(minutes=30) + timedelta(seconds=self.tick)).isoformat()

    def writes(self):
        return [x for x in self.calls if x[0].startswith(("create_", "update_"))]

    @staticmethod
    def page(rows, args):
        off, lim = int(args.get("offset") or 0), int(args.get("limit") or 50)
        more = off + lim < len(rows)
        return {"items": rows[off:off + lim], "total": len(rows), "has_more": more, "next_offset": off + lim if more else None}

    def call(self, tool, args=None):
        args = dict(args or {})
        self.calls.append((tool, args))
        f = args.get("filters") or {}
        if tool == "whoami":
            return {"principal": {"contact_id": OWNER, "timezone": "America/New_York", "primary_email": ME},
                    "inboxes": [{"address": ME}]}
        if tool == "list_entities":
            if args["entity_type"] == "calendar_event":
                lo, hi = f.get("since", ""), f.get("until", "")
                rows = [{k: v for k, v in e.items() if not k.startswith("_") or k == "_ref"} for e in self.events
                        if (not lo or e["end_time"] > lo) and (not hi or e["start_time"] < hi)]
                return self.page(rows, args)
            if args["entity_type"] == "task":
                rows = [t for t in self.tasks.values() if f.get("search", "") in str(t.get("description") or "")]
                return self.page(rows, args)
            return self.page([], args)
        if tool == "get":
            ident = str(args["id_or_query"]).lower()
            if args["entity_type"] == "calendar_event":
                e = next((x for x in self.events if x["id"] == ident), None)
                if e is None:
                    return {"error": "not found"}
                return {"event": {"id": e["id"], "title": e["title"], "description": e["_description"],
                                  "organizer_email": e["_organizer"], "attendees": e["attendees"]},
                        "attendee_emails": [a["email"] for a in e["attendees"]]}
            if args["entity_type"] == "task":
                t = self.tasks.get(ident)
                return {"task": dict(t), "comments": list(self.comments[ident])} if t else {"error": "not found"}
            return {"error": "not found"}
        if tool == "create_task":
            new = uid(30000 + len(self.tasks))
            self.tasks[new] = dict(args, id=new, status="TODO", created_at=self.stamp())
            self.comments[new] = []
            return {"id": new}
        if tool == "create_task_comment":
            self.comments[args["task_id"]].append({"id": uid(40000 + len(self.calls)), "body": args["body"],
                                                   "created_at": self.stamp()})
            return {"id": "ok"}
        if tool == "update_task":
            self.tasks[args["id"]]["status"] = args["status"]
            return {"id": args["id"]}
        raise AssertionError(f"unexpected call {tool}")

    def owner_says(self, task_ref, text):
        tid = task_ref.rsplit("/", 1)[-1]
        self.comments[tid].append({"id": uid(60000 + len(self.comments[tid])), "body": text, "created_at": self.stamp()})


def fake_task_stack(portal):
    """A stand-in for task-stack-apply: each create op becomes a task, logged for undo."""
    def apply(changes_path, log_path, dry):
        changes = json.loads(Path(changes_path).read_text())
        results = []
        for op in changes["ops"]:
            if dry:
                results.append({"id": op["id"], "op": "create", "outcome": "would_apply"})
                continue
            tid = portal.call("create_task", {"title": op["title"], "description": op["description"],
                                              "due_date": op["due_date"], "project_id": op.get("project")})["id"]
            c.append_jsonl(log_path, {"op_id": op["id"], "task_id": tid, "action": "create"})
            results.append({"id": op["id"], "op": "create", "outcome": "applied", "task": f"portal://task/{tid}"})
        return {"status": "would_apply" if dry else "applied", "results": results}

    def undo(log_path, op_id, dry):
        for line in Path(log_path).read_text().splitlines():
            row = json.loads(line)
            if (op_id is None or row["op_id"] == op_id) and not dry:
                portal.call("update_task", {"id": row["task_id"], "status": "CANCELLED"})
        return {"status": "would_undo" if dry else "undone"}

    return apply, undo


@pytest.fixture
def portal(monkeypatch, tmp_path):
    fake = FakePortal()
    monkeypatch.setattr(c, "client", lambda *a, **k: fake)
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "settings.toml"))
    return fake


def dp_state(tmp_path):
    state = tmp_path / "dp"
    (state / "2030-03-04").mkdir(parents=True, exist_ok=True)
    (state / "2030-03-04" / "morning.json").write_text(json.dumps({"proposals": [
        {"id": "f1", "kind": "focus-block", "title": "Focus: freight quote", "start": "14:00", "end": "15:30",
         "for": f"portal://task/{uid(1)}", "why": "the quote is due tomorrow"}]}))
    return state


def ref(n):
    return f"portal://calendar_event/{uid(n)}"


def proposals(scan, dry=False):
    props = [
        {"id": "p1", "kind": "focus-block", "date": "2030-03-04", "start": "14:00", "end": "15:30",
         "title": "Focus: freight quote", "for": f"portal://task/{uid(1)}", "why": "due tomorrow",
         "source": "daily-plan", "from": "2030-03-04:f1"},
        {"id": "p2", "kind": "decline", "event": ref(1), "date": "2030-03-04", "start": "09:00", "end": "10:00",
         "title": "Acme ops weekly", "draft": "I will skip this week; Priya has the numbers.",
         "why": "it collides with the carrier review"},
        {"id": "p3", "kind": "prep", "event": ref(2), "date": "2030-03-04", "start": "09:30", "title": "Carrier review",
         "prepare": "the rate sheet", "why": "external, no prep note"},
        {"id": "p4", "kind": "move", "event": ref(5), "date": "2030-03-05", "start": "14:00", "end": "15:00",
         "title": "Admin hold", "to": {"date": "2030-03-05", "start": "16:00", "end": "17:00"},
         "why": "frees the afternoon for the audit"},
    ]
    ids = {}
    for f in scan["findings"]:
        ids.setdefault(f["kind"], []).append(f["id"])
    findings = [{"ids": ids.get("conflict", []), "proposal": "p2"}, {"ids": ids.get("no-prep", []), "proposal": "p3"},
                {"ids": ids.get("daily-plan", []), "proposal": "p1"},
                {"ids": [i for k, v in ids.items() if k not in ("conflict", "no-prep", "daily-plan") for i in v],
                 "dismissed": "acceptable this week"}]
    return {"tool": "calendar-steward", "version": 1, "date": "2030-03-04", "dry_run": dry, "summary": "A busy Monday.",
            "proposals": props, "findings": findings, "questions": []}
