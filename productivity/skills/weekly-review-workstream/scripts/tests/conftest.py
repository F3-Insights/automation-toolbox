"""Shared test data: an in-memory Insights Portal holding an invented company, Lakeview
Hardware, with today pinned to Friday 2030-03-08. Nothing here touches the network."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _common as c  # noqa: E402


def uid(n):
    return f"{n:08d}-2222-4222-8222-222222222222"


OWNER, OTHER = uid(900), uid(901)
D_OPS = uid(800)
P_STORE, P_EMPTY, P_WAIT = uid(700), uid(701), uid(702)
TODAY = "2030-03-08"


def task(n, title, status="TODO", project=P_STORE, **kw):
    row = {"id": uid(n), "title": title, "status": status, "project_id": project, "domain_id": D_OPS,
           "owner_contact_id": OWNER, "priority": "P3", "created_at": "2030-03-01T10:00:00Z",
           "updated_at": "2030-03-05T10:00:00Z"}
    row.update(kw)
    return row


CORPUS = {
    "domain": [{"id": D_OPS, "name": "Lakeview Operations"}],
    "project": [{"id": P_STORE, "name": "Spring store reset", "domain_id": D_OPS, "status": "IN_PROGRESS",
                 "goal_id": uid(600)},
                {"id": P_EMPTY, "name": "Supplier review", "domain_id": D_OPS, "status": "IN_PROGRESS"},
                {"id": P_WAIT, "name": "Shelf order", "domain_id": D_OPS, "status": "IN_PROGRESS"}],
    "task": [task(1, "Order the endcap displays", due_date="2030-03-12"),
             task(2, "Call the shelving vendor", status="WAITING", project=P_WAIT, due_date="2030-03-06",
                  waiting_on_name="Sam"),
             task(3, "Draft the window sign", due_date="2030-01-02", project=P_EMPTY,
                  updated_at="2029-12-01T10:00:00Z"),
             task(4, "Review the lease", owner_contact_id=OTHER, due_date="2030-02-01"),
             task(5, "Archive old flyers", status="DONE", project=P_EMPTY)],
}


class FakePortal:
    """The reads the gather and check make, answered in memory."""

    def __init__(self, corpus=CORPUS, comments=None):
        self.corpus, self.comments, self.calls = corpus, comments or {}, []

    def call(self, tool, args=None):
        args = args or {}
        self.calls.append((tool, args))
        if tool == "whoami":
            return {"principal": {"contact_id": OWNER}}
        if tool == "get":
            return {"task": {"id": args["id_or_query"]}, "comments": self.comments.get(args["id_or_query"], [])}
        if tool == "list_entities":
            rows = list(self.corpus.get(args["entity_type"], []))
            if args["entity_type"] == "task":
                want = (args.get("filters") or {}).get("status")
                rows = [r for r in rows if (r["status"] == want if want else c.is_open_task(r))]
            return {"items": rows, "total": len(rows), "has_more": False}
        raise AssertionError(f"unexpected call {tool}")


@pytest.fixture
def home(tmp_path, monkeypatch):
    settings = tmp_path / "settings.toml"
    settings.write_text(f'state_dir = "{tmp_path / "state"}"\n', encoding="utf-8")
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(settings))
    return tmp_path / "state" / "weekly-review"


STACK = {"tool": "task-stack-check", "as_of": TODAY,
         "overall": {"score": 81.5, "items_flagged": 3,
                     "components": {"filing": {"flagged": 0, "pool": 4}, "overdue": {"flagged": 2, "pool": 4}}},
         "findings": {}}
