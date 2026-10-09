"""Tests for je_import_check.py: linting an import file already on disk."""

from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent


def load(name):
    """Import a script of this skill by file, with its own _common beside it."""
    sys.modules.pop("_common", None)
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location(f"je_{name}", SCRIPTS / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPTS))


je = load("je_import")
chk = load("je_import_check")
common = sys.modules["_common"]

ENTRY = {
    "journal": "GJ", "description": "To accrue August rent, Acme Components",
    "posting_date": "2026-08-31", "reversal_date": "2026-09-01",
    "lines": [
        {"account": "6100", "location": "100", "department": "ADMIN", "memo": "Accrued rent", "debit": 2500.0},
        {"account": "2100", "location": "100", "department": "ADMIN", "memo": "Offset", "credit": 2500.0},
    ],
}


def checks(findings):
    return {f["check"] for f in findings}


def run(script, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True)


def test_a_draft_file_fails_the_posted_requirement_unless_skipped(tmp_path):
    src = tmp_path / "proposals.json"
    src.write_text(json.dumps([ENTRY]))
    out = tmp_path / "draft.csv"
    assert run("je_import.py", str(src), "--out", str(out), "--state", "Draft").returncode == 0
    result = chk.check_file(out)
    assert "state" in checks(result["findings"]) and not result["passed"]
    assert chk.check_file(out, state="")["passed"]
    assert run("je_import_check.py", str(out)).returncode == 1


def test_an_unbalanced_entry_and_reordered_columns_are_caught(tmp_path):
    path = tmp_path / "bad.csv"
    je.write_csv(path, je.build_rows([{**ENTRY, "lines": ENTRY["lines"][:1]}], "2026-09-01"))
    assert "balanced" in checks(chk.check_file(path)["findings"])
    text = path.read_text().replace("DONOTIMPORT,JOURNAL", "JOURNAL,DONOTIMPORT", 1)
    path.write_text(text)
    assert "columns" in checks(chk.check_file(path)["findings"])
