"""report_render.py: tables in, evidence out, Word and PDF written."""

import json
import shutil

import pytest

from conftest import run


APPROVED = """# Weekly Highlights - Finance and Technology - 2027-11-12

## Cash and collections

- **Cash:** cash on hand is $1.84M (facts://cash_on_hand).
- **Receivables:** one account is 62 days overdue
  (portal://task/t2, owner://questions/1).

{{table:october}}

{{table:missing}}
"""

@pytest.fixture


def facts(tmp_path):
    path = tmp_path / "facts.json"
    run("report_facts", "init", "--facts", path, "--period", "2027-11-12")
    run("report_facts", "add-table", "--facts", path, "--key", "october", "--title", "October results",
        "--as-of", "2027-10-31", stdin="Line,October\nRevenue,\"4,812,000\"\n")
    return path


def test_markdown_render_substitutes_tables_and_lifts_the_evidence_out(tmp_path, facts):
    report = tmp_path / "approved.md"
    report.write_text(APPROVED)
    done = run("report_render", "--report", report, "--facts", facts, "--out-dir", tmp_path / "out", "--name",
               "weekly-2027-11-12", "--format", "md", "--json")
    assert done.returncode == 0, done.stderr
    result = json.loads(done.stdout)
    assert result["tables"] == ["october"] and result["tables_missing"] == ["missing"]
    text = (tmp_path / "out" / "weekly-2027-11-12.md").read_text()
    assert "://" not in text and "( )" not in text and "()" not in text
    assert "| Revenue | 4,812,000 |" in text and "{{table:missing}}" in text
    assert "62 days overdue." in text, "a citation's trailing full stop rejoins its sentence"
    evidence = json.loads((tmp_path / "out" / "evidence-map.json").read_text())
    assert evidence["refs"] == 3


@pytest.mark.skipif(not (shutil.which("pandoc") and shutil.which("soffice")), reason="pandoc and LibreOffice")


def test_the_word_and_pdf_files_are_written_and_counted(tmp_path, facts):
    report = tmp_path / "approved.md"
    report.write_text(APPROVED.replace("{{table:missing}}", ""))
    done = run("report_render", "--report", report, "--facts", facts, "--out-dir", tmp_path / "out", "--name",
               "weekly-2027-11-12", "--json")
    assert done.returncode == 0, done.stderr
    form = json.loads(done.stdout)["form_check"]
    assert form["pages"] == 1 and form["passed"] is True
    assert (tmp_path / "out" / "weekly-2027-11-12.docx").is_file()
