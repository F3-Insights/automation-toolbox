"""An invented vault with loose notes, a thin map note and an old checklist."""

import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

NOTES = {
    "Lakeview supplier call.md": "Notes. [[Suppliers/Acme Components]] [[Suppliers/Northwind Traders]]\n",
    "Random thought.md": "No links here.\n",
    "Suppliers/Acme Components.md": "Supplier. [[Lakeview supplier call]]\n",
    "Suppliers/Northwind Traders.md": "---\ntags: [suppliers]\n---\nSupplier.\n",
    "Maps/Suppliers MOC.md": "---\ntags: [suppliers]\n---\n[Placeholder] list suppliers here\n",
    "Maps/Full MOC.md": "x" * 300 + "\n",
    "Old/Chores.md": "- [ ] fix the gate\n- [x] done\n- [ ] paint\n",
    "Private/Journal.md": "- [ ] private item [[Random thought]]\n",
}


@pytest.fixture
def vault(tmp_path, monkeypatch):
    root = tmp_path / "Vault"
    for rel, text in NOTES.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    old = time.time() - 400 * 86400
    for rel in ("Old/Chores.md", "Private/Journal.md"):
        os.utime(root / rel, (old, old))
    conf = tmp_path / "settings.toml"
    conf.write_text(f'vault_dir = "{root}"\nvault_private_dirs = ["Private"]\n', encoding="utf-8")
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(conf))
    return root
