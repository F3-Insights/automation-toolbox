"""Shared test data for the pack and delivery tests: an invented engagement with Northwind
Traders, its Context, rules, updates folder and client folders. Nothing touches the network."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

NAME = "northwind-update"
WEEK = "2026-W40"          # update day Friday 2026-10-02


def put(path, text="northwind", day=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if day:
        when = datetime.fromisoformat(f"{day}T12:00:00").timestamp()
        os.utime(path, (when, when))
    return path


def engagement(tmp, variant="memo", extra=None, sources=None, previous="2026-09-25"):
    """Northwind's Context, rules, updates folder and two client folders, and owner settings
    naming the Contexts folder. Returns the paths."""
    fields = {"Variant": variant, "Update day": "Friday", "Week folder": "Drafts/{date}",
              "Draft file": "Northwind Update {date} DRAFT." + ("md" if variant == "memo" else "html"),
              "Review note": "{date} review-notes.md", "Previous updates": "Northwind Update *.md",
              "Client email domains": "northwind.test"}
    if variant == "memo":
        fields["Cover email"] = "Northwind Email {date} DRAFT.md"
    fields.update(extra or {})
    rules = tmp / "rules"
    put(rules / "UPDATE-RULES.md", "\n".join(["# Rules", "", "## Update inputs", ""]
                                             + [f"- {k}: {v}" for k, v in fields.items() if v is not None]) + "\n")
    updates = tmp / "client" / "Weekly Update"
    updates.mkdir(parents=True)
    if previous:
        put(updates / f"Northwind Update {previous}.md", "last update", previous)
    general, proposal = tmp / "client" / "General", tmp / "client" / "Proposal"
    general.mkdir()
    proposal.mkdir()
    listed = [{"name": "rules", "kind": "folder", "path": str(rules)},
              {"name": "updates", "kind": "folder", "path": str(updates)},
              {"name": "engagement-general", "kind": "folder", "path": str(general)},
              {"name": "engagement-proposal", "kind": "folder", "path": str(proposal)}] + list(sources or [])
    contexts = tmp / "contexts"
    contexts.mkdir()
    (contexts / f"{NAME}.yaml").write_text(json.dumps({"name": NAME, "sources": listed}), encoding="utf-8")
    settings = tmp / "settings.toml"
    settings.write_text(f'[client-update-workstream]\ncontexts_dir = "{contexts}"\n', encoding="utf-8")
    os.environ["F3I_TOOLBOX_SETTINGS"] = str(settings)
    return {"rules": rules, "updates": updates, "general": general, "proposal": proposal,
            "contexts": contexts, "week_dir": tmp / "week"}


@pytest.fixture(autouse=True)
def keep_env(monkeypatch, tmp_path):
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "unset.toml"))
