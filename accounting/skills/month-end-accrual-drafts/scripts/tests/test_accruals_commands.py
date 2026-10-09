"""Tests for how accruals.py finds the commands it runs: plain scripts by owning skill, never PATH."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
SKILLS = SCRIPTS.parent.parent  # accounting/skills, laid out as ~/.claude/skills is


def load():
    sys.modules.pop("_common", None)
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location("acc_accruals", SCRIPTS / "accruals.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPTS))


accruals = load()


def test_own_commands_run_the_sibling_script(monkeypatch):
    monkeypatch.setenv("PATH", "")
    for name in ("card-export", "cc-accrual", "service-period-accrual"):
        argv = accruals.command(name)
        assert Path(argv[-1]) == SCRIPTS / (name.replace("-", "_") + ".py")
        assert Path(argv[-1]).is_file()


def test_journal_entry_commands_come_from_their_owning_skill(monkeypatch):
    monkeypatch.setenv("PATH", "")
    monkeypatch.setenv("ACCRUALS_SKILLS_DIR", str(SKILLS))
    assert accruals.command("je-import")[-1] == str(SKILLS / "month-end-journal-entry/scripts/je_import.py")
    assert accruals.command("je-import-check")[-1].endswith("month-end-journal-entry/scripts/je_import_check.py")


def test_default_skills_folder_is_the_by_name_path(monkeypatch, tmp_path):
    monkeypatch.delenv("ACCRUALS_SKILLS_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(accruals.Bad) as err:
        accruals.command("je-import")
    assert str(tmp_path / ".claude/skills/month-end-journal-entry/scripts/je_import.py") in str(err.value)


def test_run_executes_a_command_with_nothing_on_path(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", "")
    monkeypatch.setenv("ACCRUALS_SKILLS_DIR", str(SKILLS))
    empty = tmp_path / "empty.csv"
    empty.write_text("JOURNAL,DATE\n")
    code, out, _ = accruals.run("je-import-check", [str(empty)], ok=(0, 1))
    assert code == 1 and out["passed"] is False
