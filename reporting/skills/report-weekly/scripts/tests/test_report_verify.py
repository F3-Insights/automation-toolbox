"""report_verify.py: a draft checked against its pack; errors stop it, findings inform Gate 3."""

import json

import pytest

from conftest import ledger, run


GOOD = """# Weekly Highlights - Finance and Technology - 2027-11-12

## Month-end close

- **October close:** the October close signed off on 2027-11-06, two days later than planned (portal://task/t1).

## Cash and collections

- **Receivables:** one account is 62 days overdue and the credit hold is disputed (portal://task/t2).

## Systems and support

- **Support queue:** the queue rose to 41 tickets after the patch window (portal://email/e1).

## Other topics

- **Nothing further:** no other call-outs this week (owner://gate2).

## Decisions needed

None this week.
"""

@pytest.fixture


def pack(tmp_path, store):
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(ledger()))
    run("report_organize", "--ledger", path, "--outline-file", store / "profile.md", "--out", tmp_path / "pack.json")
    return tmp_path / "pack.json"


def verify(tmp_path, pack, text):
    report = tmp_path / "draft.md"
    report.write_text(text)
    done = run("report_verify", "--report", report, "--pack", pack, "--json")
    found = json.loads(done.stdout)
    return done.returncode, [e["kind"] for e in found["errors"]], [f["kind"] for f in found["findings"]]


def test_a_sound_draft_has_no_error_and_ties_every_figure(tmp_path, pack):
    code, errors, findings = verify(tmp_path, pack, GOOD)
    assert code == 0 and errors == []
    assert not {"NOT_IN_CITED_RECORD", "UNCITED_FIGURE", "MISSING_CATEGORY", "NO_DECISIONS_BLOCK"} & set(findings)


def test_the_errors_stop_the_report(tmp_path, pack):
    text = GOOD.replace("(owner://gate2)", "(portal://task/t99)") + \
        "- **Settlement:** the Lakeview\n  settlement was paid.\n- **Board pack:** marked done.\n"
    code, errors, _ = verify(tmp_path, pack, text)
    assert code == 3
    assert {"UNKNOWN_REFERENCE", "NEVER_APPEARS", "UNCITED_COMPLETION_CLAIM"} <= set(errors)


def test_the_audience_bar_raises_findings_and_never_errors(tmp_path, pack):
    text = GOOD.replace("None this week.", "") .replace("## Decisions needed", "") + (
        "- **Queue:** still waiting on Sam Jordan for the support fix (portal://email/e1).\n"
        "- **Refund:** we recovered $78.93 (portal://task/t2).\n"
        "- **Meetings:** the team met for 2.5 hours this week.\n"
        "- **Scanner:** the scanner contract renewal is still outstanding.\n"
        "- **Flags:** the close project is flagged as WAITING_HEAVY.\n")
    code, errors, findings = verify(tmp_path, pack, text)
    assert code == 0 and errors == []
    assert {"PERSON_BLAMED", "IMMATERIAL_FIGURE", "ACTIVITY_HOURS", "AUTHOR_TASK_UPDATE", "TRACKER_VOCABULARY",
            "NO_DECISIONS_BLOCK"} <= set(findings)


def test_a_carry_over_left_unanswered_is_a_finding(tmp_path, store):
    week = ledger(prior=[{"ref": "portal://note/n0", "title": "Weekly Highlights", "date": "2027-11-05",
                          "bullets": [{"label": "Depot lease", "text": "The depot lease renewal is unresolved."}]}])
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(week))
    run("report_organize", "--ledger", path, "--outline-file", store / "profile.md", "--out", tmp_path / "pack.json")
    _, _, findings = verify(tmp_path, tmp_path / "pack.json", GOOD)
    assert "CARRY_OVER_NOT_ADDRESSED" in findings
    _, _, findings = verify(tmp_path, tmp_path / "pack.json", GOOD.replace("Receivables:", "Depot lease:"))
    assert "CARRY_OVER_NOT_ADDRESSED" not in findings


def test_an_owner_reference_other_than_the_three_answers_is_unknown(tmp_path, pack):
    # owner:// exempts a line from the figure and completion checks, so only gate1, gate2 and
    # questions/<id> may carry that exemption.
    text = GOOD + "- **Board pack:** completed, with $4,500 recovered (owner://anything).\n"
    code, errors, findings = verify(tmp_path, pack, text)
    assert code == 3
    assert {"UNKNOWN_REFERENCE", "UNCITED_COMPLETION_CLAIM"} <= set(errors) and "UNCITED_FIGURE" in findings
    code, errors, _ = verify(tmp_path, pack, GOOD + "- **Board pack:** completed (owner://questions/q3).\n")
    assert code == 0 and errors == []


def test_a_long_never_published_item_stops_the_draft_as_it_stops_the_record(tmp_path, store):
    """Verify and record check the same complete list; no item is dropped for its length."""
    long_item = "Northwind Traders pension scheme deficit figures"
    profile = store / "profile.md"
    profile.write_text(profile.read_text().replace("1. the Lakeview settlement",
                                                   f"1. the Lakeview settlement\n2. {long_item}"))
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(ledger()))
    run("report_organize", "--ledger", path, "--outline-file", profile, "--out", tmp_path / "pack.json")
    text = GOOD.replace("no other call-outs this week", f"the {long_item}\n  are with the actuary")
    code, errors, _ = verify(tmp_path, tmp_path / "pack.json", text)
    assert code == 3 and "NEVER_APPEARS" in errors
    # The same text is what report-record refuses, so the two agree.
    (tmp_path / "approved.md").write_text(text)
    refused = run("report_record", "save", "--store", store, "--period", "2027-11-12", "--report",
                  tmp_path / "approved.md", "--profile", profile, "--skip-ledger", "--json")
    assert refused.returncode == 3
