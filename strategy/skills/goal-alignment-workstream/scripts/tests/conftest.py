"""Shared test data: an in-memory Insights Portal holding an invented company, Fabrikam
Logistics, reviewed for February 2030 on 2030-03-02. Nothing here touches the network."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _common as c  # noqa: E402


def uid(n):
    return f"{n:08d}-3333-4333-8333-333333333333"


OWNER = uid(900)
D_FLEET, D_SALES, D_IDLE = uid(800), uid(801), uid(802)
G_FLEET, G_SALES, G_SUB = uid(600), uid(601), uid(602)
P_ROUTES, P_OLD, P_SUB = uid(700), uid(701), uid(702)
TODAY = "2030-03-02"


def task(n, title, project, status="TODO", **kw):
    row = {"id": uid(n), "title": title, "status": status, "project_id": project, "owner_contact_id": OWNER,
           "created_at": "2030-02-03T10:00:00Z", "updated_at": "2030-02-03T10:00:00Z"}
    row.update(kw)
    return row


CORPUS = {
    "domain": [{"id": D_FLEET, "name": "Fleet"}, {"id": D_SALES, "name": "Sales"}, {"id": D_IDLE, "name": "Research"}],
    "goal": [{"id": G_FLEET, "title": "Cut empty miles", "domain_id": D_FLEET, "status": "IN_PROGRESS",
              "priority": "P1"},
             {"id": G_SALES, "title": "Win two carriers", "domain_id": D_SALES, "status": "IN_PROGRESS",
              "priority": "P2"},
             {"id": G_SUB, "title": "Route pilot", "domain_id": D_FLEET, "status": "NOT_STARTED",
              "parent_goal_id": G_FLEET}],
    "project": [{"id": P_ROUTES, "name": "Route optimiser", "domain_id": D_FLEET, "status": "IN_PROGRESS",
                 "goal_id": G_SUB, "updated_at": "2030-02-20T10:00:00Z"},
                {"id": P_OLD, "name": "Old depot study", "domain_id": D_SALES, "status": "IN_PROGRESS",
                 "updated_at": "2029-09-01T10:00:00Z", "created_at": "2029-08-01T10:00:00Z"}],
    "task": [task(1, "Load the February routes", P_ROUTES, status="DONE", completed_at="2030-02-14T10:00:00Z"),
             task(2, "Test the optimiser", P_ROUTES),
             task(3, "Read the depot quotes", P_OLD, updated_at="2029-09-01T10:00:00Z",
                  created_at="2029-08-01T10:00:00Z")],
}


class FakePortal:
    def __init__(self, corpus=CORPUS, comments=None):
        self.corpus, self.comments = corpus, comments or {}

    def call(self, tool, args=None):
        args = args or {}
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
    return tmp_path / "state" / "goal-alignment"


RULES = """# Goal alignment rules

## Settings

- Quarterly months: 1, 4, 7, 10
- Pulse rotation 1: Business, Health
- Pulse rotation 2: Family
- Pulse rotation start: 2030-01
- Telos domains agents read: Business, Family
- Starved hours: 4 (below this a goal's domain is starved)
- Stop days: 90

## Other
- Ignored: yes
"""


@pytest.fixture
def time_home(tmp_path):
    root = tmp_path / "time"
    (root / "data").mkdir(parents=True)
    (root / "data" / "daily_domain_hours.csv").write_text(
        "date,weekday,work_hours,total_hours,Fleet,Sales,Research,Sleep\n"
        "2030-02-03,Mon,8,24,6,1,1,8\n2030-02-04,Tue,8,24,2,0,6,8\n2030-03-01,Fri,8,24,8,0,0,8\n")
    (root / "data" / "time_slots.csv").write_text(
        "date,window,domain,hours,topic,topic_label,tier\n2030-02-03,w1,Fleet,6,routes,Routing,seen\n"
        "2030-02-03,w1,Sleep,8,sleep,Sleep,seen\n")
    return root
