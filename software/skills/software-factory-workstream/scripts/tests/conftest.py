"""Test set-up: the scripts folder and this folder on the import path, isolated settings, clones
and state, and the fake standing in for gh and git."""

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
for folder in (HERE.parent, HERE):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import _common  # noqa: E402
from sf_support import Fake  # noqa: E402


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Settings, clones and state under tmp_path; nothing read from the real home."""
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "settings.toml"))
    monkeypatch.setenv("SOFTWARE_FACTORY_REPOS_DIR", str(tmp_path / "repos"))
    monkeypatch.setenv("SOFTWARE_FACTORY_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.delenv("GH", raising=False)
    for key, value in {"GIT_AUTHOR_NAME": "Dana", "GIT_AUTHOR_EMAIL": "dana@example.com",
                       "GIT_COMMITTER_NAME": "Dana", "GIT_COMMITTER_EMAIL": "dana@example.com",
                       "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig")}.items():
        monkeypatch.setenv(key, value)
    (tmp_path / "gitconfig").write_text("")
    return tmp_path


@pytest.fixture
def fake(env, monkeypatch):
    f = Fake()
    monkeypatch.setattr(_common, "run", f)
    return f
