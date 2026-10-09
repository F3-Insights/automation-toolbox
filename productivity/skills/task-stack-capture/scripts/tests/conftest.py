"""Shared fixtures: the scripts folder on sys.path, settings in a temporary file, and a small
invented set of capture sources."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def no_owner_settings(tmp_path, monkeypatch):
    """Point settings at a file of the test's own (only state_dir set), so a real owner file is never read."""
    path = tmp_path / "settings.toml"
    path.write_text(f'state_dir = "{tmp_path / "state-dir"}"\n', encoding="utf-8")
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(path))
    return path


@pytest.fixture
def sources(tmp_path):
    """Three sources: a said-not-seen folder, a markdown inbox and a future source."""
    said = tmp_path / "said"
    said.mkdir()
    (said / "said-not-seen-2026-09.json").write_text(json.dumps({
        "schema": "time-study/said-not-seen@1", "window": "2026-09",
        "items": [
            {"id": "a1b2c3d4", "ref": 1, "date": "2026-09-28", "commitment": "Send Dana the freight summary",
             "quote": "I'll send it today", "domain": "Northwind", "status": "open"},
            {"id": "e5f6a7b8", "ref": 2, "date": "2026-09-29", "commitment": "Call Sam about the lease",
             "status": "seen"},
            {"id": "c9d0e1f2", "ref": 3, "date": "2026-08-01", "commitment": "Review the Acme pallet forecast",
             "status": "open"},
        ]}), encoding="utf-8")
    inbox = tmp_path / "inbox.md"
    inbox.write_text("# Inbox 2026-09-30\n- [ ] Book the Lakeview workshop room\n- [x] Pay the parking fine\n"
                     "- 2026-09-27: Draft the Fabrikam renewal note\n", encoding="utf-8")
    file = tmp_path / "sources.json"
    file.write_text(json.dumps({"sources": [
        {"name": "said-not-seen", "kind": "said-not-seen", "path": str(said)},
        {"name": "quick-capture", "kind": "markdown-inbox", "path": str(inbox)},
        {"name": "chat", "kind": "future", "note": "no read path yet"},
    ]}), encoding="utf-8")
    return file
