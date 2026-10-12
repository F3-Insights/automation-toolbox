"""Shared test data: an in-memory Insights Portal holding an invented company, Northwind
Traders, with the clock pinned to 2030-03-04 12:00 UTC. Nothing here touches the network."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

NOW = datetime(2030, 3, 4, 12, 0, tzinfo=timezone.utc)


def uid(n):
    return f"{n:08d}-1111-4111-8111-111111111111"


OWNER, OTHER = uid(900), uid(901)
D_SALES, D_OPS = uid(800), uid(801)
P_ROUTES, P_BUCKET, P_AUDIT = uid(700), uid(701), uid(702)
G_GROW, G_SUB = uid(600), uid(601)
EMAIL, NOTE, EVENT_PAST, EVENT_FUTURE = uid(500), uid(501), uid(502), uid(503)


def iso(dt):
    return dt.isoformat().replace("+00:00", "Z")


def ago(days):
    return iso(NOW - timedelta(days=days))


def task(n, title, status="TODO", project_id=P_ROUTES, domain_id=D_SALES, created=90, updated=90, **kw):
    row = {"id": uid(n), "title": title, "status": status, "project_id": project_id, "domain_id": domain_id,
           "goal_id": None, "due_date": None, "deadline": None, "start_date": None, "priority": "P3",
           "owner_contact_id": OWNER, "owner_name": "Dana", "waiting_on_contact_id": None,
           "waiting_reason": None, "description": "", "created_at": ago(created), "updated_at": ago(updated),
           "is_archived": False}
    row.update(kw)
    return row


def projects():
    return [
        {"id": P_ROUTES, "name": "Delivery routes", "domain_id": D_SALES, "goal_id": None, "status": "IN_PROGRESS",
         "created_at": ago(400), "updated_at": ago(200)},
        {"id": P_BUCKET, "name": "General Tasks", "domain_id": D_SALES, "goal_id": None, "status": "IN_PROGRESS",
         "is_general": True, "created_at": ago(400), "updated_at": ago(200)},
        {"id": P_AUDIT, "name": "Year-end audit", "domain_id": D_OPS, "goal_id": G_GROW, "status": "IN_PROGRESS",
         "created_at": ago(400), "updated_at": ago(200)},
    ]


def goals():
    return [{"id": G_GROW, "title": "Grow wholesale", "domain_id": D_OPS, "status": "IN_PROGRESS", "priority": "P2",
             "created_at": ago(300), "updated_at": ago(100)}]


DOMAINS = [{"id": D_SALES, "name": "Northwind Sales"}, {"id": D_OPS, "name": "Northwind Operations"}]


class FakePortal:
    """Answers the calls the task-stack scripts make, the way the Portal does: `get` nests a
    task under `task` with comments and hierarchy beside it; update_task honours
    expected_updated_at; a comment moves the task's updated_at. There is no delete tool."""

    def __init__(self, tasks, evidence=None):
        self.tasks = {t["id"]: dict(t) for t in tasks}
        self.comments = {t["id"]: [] for t in tasks}
        self.projects = {p["id"]: p for p in projects()}
        self.goals = {g["id"]: g for g in goals()}
        self.evidence = evidence if evidence is not None else {
            ("email", EMAIL): {"id": EMAIL, "subject": "Re: the rates"},
            ("note", NOTE): {"id": NOTE, "title": "Ops review"},
            ("calendar_event", EVENT_PAST): {"id": EVENT_PAST, "start_time": ago(2)},
            ("calendar_event", EVENT_FUTURE): {"id": EVENT_FUTURE, "start_time": iso(NOW + timedelta(days=2))},
        }
        self.calls, self.tick = [], 0

    def stamp(self):
        self.tick += 1
        return iso(NOW + timedelta(seconds=self.tick))

    def writes(self):
        return [x for x in self.calls if x[0].startswith(("update_", "create_"))]

    def call(self, tool, args=None):
        args = dict(args or {})
        self.calls.append((tool, args))
        if tool == "whoami":
            return {"principal": {"contact_id": OWNER}}
        if tool == "get":
            kind, ident = args["entity_type"], args["id_or_query"]
            if kind == "task":
                t = self.tasks.get(ident)
                if t is None:
                    return {"error": "not found"}
                hier = {"domain": {"id": t.get("domain_id")}}
                proj = self.projects.get(t.get("project_id"))
                if proj:
                    hier["project"] = dict(proj)
                    hier["domain"] = {"id": proj["domain_id"]}
                return {"task": dict(t), "comments": [dict(x) for x in self.comments[ident]], "hierarchy": hier}
            if kind == "project" and ident in self.projects:
                out = {"project": dict(self.projects[ident])}
                if args.get("detail") == "full":
                    out["tasks"] = [dict(t) for t in self.tasks.values() if t.get("project_id") == ident]
                return out
            if kind == "goal" and ident in self.goals:
                return {"goal": dict(self.goals[ident])}
            found = self.evidence.get((kind, ident))
            if found is None:
                return {"error": "not found"}
            if kind == "calendar_event":
                return {"event": dict(found), "_ref": f"portal://calendar_event/{ident}"}
            if kind == "email":
                return {"thread": [dict(found)], "_ref": f"portal://email/{ident}"}
            return dict(found)
        if tool == "update_task":
            t = self.tasks[args["id"]]
            if args.get("expected_updated_at") and args["expected_updated_at"] != t["updated_at"]:
                raise RuntimeError("portal update_task: the task changed since expected_updated_at")
            if args.get("status"):
                t["status"] = args["status"]
            t.update(args.get("fields") or {})
            t["updated_at"] = self.stamp()
            return {"id": t["id"]}
        if tool in ("update_project", "update_goal"):
            rec = (self.projects if tool == "update_project" else self.goals)[args["id"]]
            rec.update(args.get("fields") or {})
            rec["updated_at"] = self.stamp()
            return {"id": rec["id"]}
        if tool == "create_task_comment":
            cid = uid(10000 + len(self.calls))
            self.comments[args["task_id"]].append({"id": cid, "body": args["body"]})
            self.tasks[args["task_id"]]["updated_at"] = self.stamp()
            return {"id": cid}
        if tool == "create_task":
            new = uid(20000 + len(self.tasks))
            row = task(0, args["title"], project_id=args.get("project_id"), domain_id=args.get("domain_id_or_name"),
                       id=new, description=args.get("description", ""), source_reference=args.get("source_reference"),
                       owner_contact_id=args.get("owner_contact_id"), due_date=args.get("due_date"))
            row["created_at"] = row["updated_at"] = self.stamp()
            self.tasks[new], self.comments[new] = row, []
            return {"id": new}
        if tool == "list_entities":
            kind, filters = args["entity_type"], args.get("filters") or {}
            if kind == "task":
                rows = list(self.tasks.values())
                if filters.get("search"):
                    rows = [t for t in rows if filters["search"] in str(t.get("description") or "")]
                elif isinstance(filters.get("status"), str):
                    rows = [t for t in rows if t["status"] == filters["status"]]
                elif not filters.get("status"):
                    rows = [t for t in rows if t["status"] in ("TODO", "IN_PROGRESS", "WAITING")]
            else:
                rows = {"project": list(self.projects.values()), "goal": list(self.goals.values()),
                        "domain": DOMAINS}.get(kind, [])
            offset, limit = int(args.get("offset") or 0), int(args.get("limit") or 200)
            window = rows[offset:offset + limit]
            more = offset + len(window) < len(rows)
            return {"items": [dict(r) for r in window], "total": len(rows), "has_more": more,
                    "next_offset": offset + len(window) if more else None}
        raise AssertionError(f"a task-stack script called {tool}, which it never should")


@pytest.fixture(autouse=True)
def no_owner_settings(tmp_path, monkeypatch):
    """Each test starts with an empty settings file of its own."""
    path = tmp_path / "settings.toml"
    path.write_text("")
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(path))
    return path
