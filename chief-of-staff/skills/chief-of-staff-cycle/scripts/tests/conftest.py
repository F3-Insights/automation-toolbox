"""Shared test data: invented settings, a doer registry, an in-memory Insights Portal for
Northwind Traders. Nothing here touches the network."""

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import _common as c  # noqa: E402

OWNER = "00000900-1111-4111-8111-111111111111"
TASK = "00000100-1111-4111-8111-111111111111"

REGISTRY = """
[[doer]]
name = "produce-work"
route = "produce"
purpose = "One private, review-ready draft"

[[doer]]
name = "meeting-prep"
route = "skill"
skill = "meeting-prep"
worker = "chief-of-staff-meeting-prep-doer"
args = "FOCUS"

[[doer]]
name = "person-brief"
route = "agent"
agent = "person-researcher"
args = "FOCUS"
default_args = "next meeting"

[[doer]]
name = "bad-one"
route = "agent"
agent = "task-reconcile-orchestrator"

[retired]
relationship-check = "replaced by crm-relationship-tending-orchestrator; launch it"
"""


@pytest.fixture(autouse=True)
def owner(tmp_path, monkeypatch):
    """Settings for an invented owner, with every document in a temporary folder."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "registry.toml").write_text(REGISTRY)
    (docs / "roster.md").write_text("# Doers\n\n## Active doers\n\n| Doer | Trust | Health |\n|---|---|---|\n"
                                    "| meeting-prep | PROPOSE | not yet run |\n| produce-work | TRUSTED | fine |\n\n## Retired\n")
    (docs / "ledger.md").write_text("# Ledger\n- 2030-03-01 | Chief of Staff | cycle launched (note)\n")
    (docs / "inbox").mkdir()
    (docs / "principles.md").write_text("Prefer finished drafts over plans.\n")
    settings = tmp_path / "settings.toml"
    settings.write_text(f"""
state_dir = "{tmp_path / 'state'}"
voice_guide = "{docs / 'principles.md'}"
[chief-of-staff-cycle]
doer_registry = "{docs / 'registry.toml'}"
doer_roster = "{docs / 'roster.md'}"
event_ledger = "{docs / 'ledger.md'}"
principles_inbox = "{docs / 'inbox'}"
principles = "{docs / 'principles.md'}"
charter = "{docs / 'missing-charter.md'}"
portal_web_url = "https://portal.example.test"
""")
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(settings))
    monkeypatch.delenv("F3I_TOOLBOX_DRY_RUN", raising=False)
    monkeypatch.delenv("NOTIFY_OWNER_MODE", raising=False)
    return docs


@pytest.fixture
def root(tmp_path):
    return c.state_root(None)


class FakePortal:
    """Notes and tasks in memory, with whoami for the owner in a named zone."""

    def __init__(self, tz="America/Chicago"):
        self.notes, self.tasks, self.calls, self.tz = [], [], [], tz
        self.fail_tasks = False
        self.records = {}

    def call(self, tool, args=None):
        args = args or {}
        self.calls.append((tool, args))
        if tool == "whoami":
            return {"principal": {"contact_id": OWNER, "timezone": self.tz}}
        if tool == "get":
            if args.get("entity_type") == "note":
                key = args.get("id_or_query")
                for n in self.notes:
                    if n["id"] == key or n["title"] == key:
                        return {"note": dict(n)}
                return {"text": f"No note found for {key}"}
            rec = self.records.get(args.get("id_or_query"))
            return rec if rec else {"text": f"nothing for {args.get('id_or_query')}"}
        if tool == "search":
            return {"notes": [{"id": n["id"], "title": n["title"]} for n in self.notes if args["query"] in n["title"]]}
        if tool == "create_note":
            note = {"id": f"note-{len(self.notes) + 1}", "title": args["title"], "content": args["content"],
                    "updated_at": "2030-03-04T12:00:00Z"}
            self.notes.append(note)
            return {"id": note["id"]}
        if tool == "update_note":
            note = next(n for n in self.notes if n["id"] == args["id"])
            note["content"] = args["fields"]["content"]
            return {"success": True}
        if tool == "list_entities":
            if self.fail_tasks:
                raise c.Bad("portal list_entities: HTTP 500")
            search = (args.get("filters") or {}).get("search", "")
            rows = [t for t in self.tasks if search.lower() in t["title"].lower()]
            if not (args.get("filters") or {}).get("include_completed"):
                rows = [t for t in rows if t.get("status") not in ("DONE", "CANCELLED")]
            return {"items": rows, "has_more": False}
        if tool == "create_task":
            if "domain_id_or_name" in args and args["domain_id_or_name"] == "Unknown":
                raise c.Bad("portal create_task: unknown domain")
            task = {"id": f"task-{len(self.tasks) + 1}", "status": "TODO", **args,
                    "created_at": c.now_utc().isoformat()}
            self.tasks.append(task)
            return {"id": task["id"]}
        raise AssertionError(tool)
