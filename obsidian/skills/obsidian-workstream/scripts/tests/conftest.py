"""A tiny invented vault for the vault scripts, and a settings file pointing at it."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

NOTES = {
    "Loose Note.md": "---\ntags: [ideas, pricing]\nstatus: draft\n---\nSee [[Target]] and [[Missing Note]].\n",
    "Sub/Target.md": "---\naliases:\n  - The Target\n---\nBack to [[Loose Note|loose]].\n",
    "Other/Target.md": "A second note with the same name.\n",
    "Projects MOC.md": "# Projects\n[[Sub/Target#Heading]]\n",
    "Private/Diary.md": "Never to be read. [[Target]]\n",
    ".obsidian/workspace.md": "app state\n",
    "Inbox/.keep.md": "",
}


@pytest.fixture
def vault(tmp_path, monkeypatch):
    root = tmp_path / "Vault"
    for rel, text in NOTES.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    conf = tmp_path / "settings.toml"
    conf.write_text(f'vault_dir = "{root}"\nvault_inbox = "Inbox"\nvault_private_dirs = ["Private"]\n', encoding="utf-8")
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(conf))
    return root
