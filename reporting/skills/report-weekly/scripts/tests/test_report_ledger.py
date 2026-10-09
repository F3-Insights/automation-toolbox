"""report_ledger.py: every published bullet kept, retrieved age-blind. Invented data only."""

import json

from conftest import ledger, run


PUBLISHED = """# Weekly Highlights - Finance and Technology - 2027-11-12

## Finance

- **Credit hold:** the Fabrikam Logistics credit hold is disputed; we expect a decision by 2027-11-19.
- **Month-end close:** the monthly close signed off on day four, as it does each month.

## Technology

- **Support queue:** the queue is back under 30 tickets.
"""

def add(tmp_path, store, text=PUBLISHED, date="2027-11-12"):
    report = tmp_path / "published.md"
    report.write_text(text)
    done = run("report_ledger", "add", "--report", report, "--date", date, "--seat", "Finance", "--store", store)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def entries(store):
    return [json.loads(line) for line in (store / "report-ledger.jsonl").read_text().splitlines()]


def test_add_splits_by_seat_classifies_and_redacts_the_never_recorded(tmp_path, store):
    result = add(tmp_path, store)
    assert result["bullets"] == 3 and result["redacted"] is True
    rows = {e["topic"]: e for e in entries(store)}
    assert rows["Credit hold"]["kind"] == "dated_expectation" and rows["Credit hold"]["due_date"] == "2027-11-19"
    assert rows["Month-end close"]["kind"] == "recurring" and rows["Month-end close"]["cycle"] == "monthly"
    assert rows["Support queue"]["seat"] == "Technology"
    assert "Fabrikam Logistics" not in (store / "report-ledger.jsonl").read_text()
    assert add(tmp_path, store)["added"] == 0, "the same report twice updates rather than doubles"


def test_candidates_are_age_blind_and_say_why(tmp_path, store):
    add(tmp_path, store, date="2027-08-20")
    week = tmp_path / "week.json"
    week.write_text(json.dumps(ledger()))
    done = run("report_ledger", "candidates", "--evidence", week, "--as-of", "2027-11-19", "--store", store, "--json")
    rows = {r["topic"]: r for r in json.loads(done.stdout)["candidates"]}
    assert "falls in or before this week" in rows["Credit hold"]["reason"]
    assert "the same week one quarter back" not in rows["Month-end close"]["reason"]
    assert "monthly cycle comes round" in rows["Month-end close"]["reason"]
    assert rows["Credit hold"]["_ref"].startswith("ledger://")


def test_a_recurring_entry_is_answered_not_closed_unless_retired(tmp_path, store):
    add(tmp_path, store)
    recurring = next(e["id"] for e in entries(store) if e["kind"] == "recurring")
    refused = run("report_ledger", "close", "--id", recurring, "--store", store)
    assert refused.returncode == 3 and "recurs" in refused.stderr
    assert run("report_ledger", "answer", "--id", recurring, "--on", "2027-11-12", "--store", store).returncode == 0
    assert next(e for e in entries(store) if e["id"] == recurring)["closed"] is False
    assert run("report_ledger", "close", "--id", recurring, "--retire", "--store", store).returncode == 0
    closed = next(e for e in entries(store) if e["id"] == recurring)
    assert closed["closed"] is True and closed["retired"] is True


def test_there_is_no_default_store(tmp_path, monkeypatch):
    monkeypatch.delenv("REPORT_STORE_DIR", raising=False)
    done = run("report_ledger", "list", env={"REPORT_STORE_DIR": ""})
    assert done.returncode == 2 and "no report store" in done.stderr


def test_a_missing_profile_is_said_rather_than_redacting_nothing_silently(tmp_path, store):
    report = tmp_path / "published.md"
    report.write_text(PUBLISHED)
    done = run("report_ledger", "add", "--report", report, "--date", "2027-11-12", "--store", store,
               "--profile", tmp_path / "no-such-profile.md")
    assert done.returncode == 0
    assert "no never-recorded rule was applied" in json.loads(done.stdout)["warnings"][0]
    assert "no never-recorded rule was applied" in done.stderr
    assert add(tmp_path, store)["warnings"] == []
