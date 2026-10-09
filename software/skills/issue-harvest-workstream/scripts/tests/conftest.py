"""Shared fixtures for the issue-harvest script tests, against an invented company (Northwind
Traders) and placeholder repositories. A fake Portal client and a fake `gh` stand in for the real
systems; nothing reaches a network.
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
# The scripts, and this folder so the tests can import its helpers in any pytest import mode.
for folder in (SCRIPTS, Path(__file__).resolve().parent):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import _common as c  # noqa: E402

NOW = datetime(2030, 3, 16, 12, 0, tzinfo=timezone.utc)
APP = "example-org/widget-app"
OPS = "example-org/ops-tool"
LOCKED = "example-org/billing"
BODY = ("## What happens\nThe export button errors on large orders.\n\n## Expected behaviour\nThe export finishes.\n\n"
        "## Acceptance\n- An order of 500 lines exports.\n")


def ago(days):
    return (NOW - timedelta(days=days)).isoformat()


REPO_MAP = """repos:
  - repo: example-org/widget-app
    product: Widget app
    harvest: true
    labels: {bug: [bug], feature: [enhancement], always: [agent-filed]}
    title: {convention: "WA-YYYYMMDD-CODE: summary", pattern: '^WA-\\d{8}-[A-Z0-9]{3,12}: .+'}
    terms: [Widget app, widget portal]
    portal_projects: [proj-widget]
    reporters: [tester@example.com]
  - repo: example-org/ops-tool
    product: Ops tool
    harvest: true
    public: true
    labels: {bug: [bug]}
    terms: [ops tool]
  - repo: example-org/billing
    product: Billing
    harvest: false
    terms: [billing system]
"""


@pytest.fixture
def home(tmp_path, monkeypatch):
    names = tmp_path / "names.txt"
    names.write_text("# private names\nJordan Northwind\n", encoding="utf-8")
    (tmp_path / "repos.yaml").write_text(REPO_MAP, encoding="utf-8")
    said = tmp_path / "said"
    said.mkdir()
    settings = tmp_path / "settings.toml"
    settings.write_text(f"""
[issue-harvest-workstream]
repos_file = "{tmp_path / 'repos.yaml'}"
state = "{tmp_path / 'state'}"
public_denylist_files = ["{names}"]
horizon_days = 14
[issue-harvest-workstream.sources.portal_notes]
enabled = true
exclude_titles = ["^Daily Note"]
[issue-harvest-workstream.sources.portal_email]
enabled = true
exclude_senders = ["noreply"]
exclude_subjects = ['^\\[Build']
[issue-harvest-workstream.sources.portal_tasks]
enabled = true
[issue-harvest-workstream.sources.said_not_seen]
enabled = true
path = "{said}"
[issue-harvest-workstream.sources.loom]
enabled = false
note = "no feed"
""", encoding="utf-8")
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(settings))
    cfg = c.harvest_settings()
    return {"tmp": tmp_path, "settings_file": settings, "settings": cfg, "repos": c.load_repos(cfg),
            "state": tmp_path / "state", "said": said, "names": names}


class FakePortal:
    def __init__(self):
        self.notes = [
            {"id": "n1", "title": "Widget review", "updated_at": ago(1), "content_preview": "short"},
            {"id": "n2", "title": "Daily Note 2030-03-15", "updated_at": ago(1), "content_preview": "Widget app"},
            {"id": "n3", "title": "Lunch plans", "updated_at": ago(2), "content_preview": "tacos"},
            {"id": "n4", "title": "Old widget note", "updated_at": ago(40), "content_preview": "Widget app"},
        ]
        self.full = {"n1": "The Widget app export button errors on large orders.", "n3": "Nothing about software."}
        self.emails = [
            {"id": "e1", "subject": "Bug", "summary": "the screen is blank", "from_address": "tester@example.com",
             "received_at": ago(0.5), "contact_id": "c1"},
            {"id": "e2", "subject": "Newsletter", "summary": "Widget app mentioned",
             "from_address": "noreply@example.com", "received_at": ago(0.5)},
            {"id": "e3", "subject": "[Build succeeded] widget", "summary": "Widget app",
             "from_address": "ci@example.com", "received_at": ago(0.5)},
            {"id": "e4", "subject": "Lunch", "summary": "see you", "from_address": "sam@example.com",
             "received_at": ago(0.5)},
        ]
        self.tasks = {"proj-widget": [{"id": "t1", "title": "Add CSV export", "created_at": ago(3)},
                                      {"id": "t2", "title": "Old", "created_at": ago(30)}]}
        self.bodies = {}
        self.calls = []

    def list_entities(self, kind, filters=None):
        self.calls.append(f"list:{kind}")
        if kind == "note":
            return list(self.notes)
        if kind == "email":
            return list(self.emails) if (filters or {}).get("direction") == "received" else []
        if kind == "task":
            return list(self.tasks.get((filters or {}).get("project_id"), []))
        return []

    def call(self, tool, args):
        self.calls.append(tool)
        if tool == "get":
            return {"note": {"content": self.full.get(args["id_or_query"], ""), "associations": {}}}
        if tool == "search":
            return {"notes": [{"id": "n3"}] if "ops tool" in args["query"] else [], "emails": []}
        if tool == "email_bodies":
            return {"items": [{"id": i, "found": i in self.bodies, "body": self.bodies.get(i, "")} for i in args["ids"]]}
        return {}


class FakeGitHub:
    """gh's issue and label commands for a few repositories, in memory."""

    def __init__(self):
        self.issues = {APP: [], OPS: [], LOCKED: []}
        self.labels = {APP: ["bug", "enhancement"], OPS: ["bug"], LOCKED: ["bug"]}
        self.writes = []
        self.broken = set()

    def add(self, repo, number, title, body="", state="OPEN", closed_at=""):
        self.issues[repo].append({"number": number, "title": title, "body": body, "state": state,
                                  "url": f"https://github.com/{repo}/issues/{number}", "labels": [],
                                  "createdAt": ago(5), "updatedAt": ago(1), "closedAt": closed_at or None,
                                  "author": {"login": "triage-lead"}, "comments": []})

    def __call__(self, *args, input=None, timeout=300):
        a = [str(x) for x in args]
        repo = a[a.index("-R") + 1] if "-R" in a else ""
        if repo in self.broken:
            return 1, "", "HTTP 404: Not Found"
        if a[:2] == ["label", "list"]:
            return 0, json.dumps([{"name": n} for n in self.labels[repo]]), ""
        if a[:2] == ["issue", "list"]:
            state = a[a.index("--state") + 1]
            return 0, json.dumps([i for i in self.issues[repo] if state == "all" or i["state"].lower() == state]), ""
        if a[:2] == ["issue", "view"]:
            hit = next((i for i in self.issues[repo] if i["number"] == int(a[2])), None)
            return (0, json.dumps(hit), "") if hit else (1, "", "no issue")
        if a[:2] == ["issue", "create"]:
            self.writes.append(a)
            n = 100 + len(self.issues[repo])
            self.add(repo, n, a[a.index("--title") + 1], input or "")
            self.issues[repo][-1]["labels"] = [{"name": a[k + 1]} for k, x in enumerate(a) if x == "--label"]
            return 0, f"https://github.com/{repo}/issues/{n}\n", ""
        if a[:2] == ["issue", "comment"]:
            self.writes.append(a)
            hit = next(i for i in self.issues[repo] if i["number"] == int(a[2]))
            hit["comments"].append({"body": input, "url": f"{hit['url']}#issuecomment-{len(hit['comments']) + 1}"})
            return 0, hit["url"], ""
        return 2, "", "fake gh: unexpected " + " ".join(a)


@pytest.fixture
def github(monkeypatch):
    fake = FakeGitHub()
    monkeypatch.setattr(c, "gh", fake)
    return fake


def harvest(home, portal=None, **kw):
    import issue_harvest_sync as sync
    opts = dict(days=14, max_items=60, batch=8, only=[], github=True, now=NOW)
    opts.update(kw)
    return sync.build(home["settings"], home["repos"], home["state"], portal or FakePortal(), **opts)


def run_folder(home, h, decisions, dry=False):
    runs = home["tmp"] / "runs"
    run = runs / f"run-{len(list(runs.glob('*'))) if runs.exists() else 0}"
    run.mkdir(parents=True)
    (run / "harvest.json").write_text(json.dumps(h), encoding="utf-8")
    (run / "decisions.json").write_text(json.dumps({"dry_run": dry, "decisions": decisions}), encoding="utf-8")
    return run


def new(source, title="WA-20300316-EXPORT: export fails on large orders", **kw):
    d = {"source": source, "decision": "new", "repo": APP, "kind": "bug", "title": title, "body": BODY, "check": "PASS"}
    d.update(kw)
    return d
