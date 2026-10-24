import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def no_owner_settings(tmp_path, monkeypatch):
    """Never read the real owner's settings file during a test."""
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "no-settings.toml"))
