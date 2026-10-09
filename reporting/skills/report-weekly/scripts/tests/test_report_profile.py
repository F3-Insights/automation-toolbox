"""report_profile.py and the profile reader in _profile.py. Invented data only."""

import json

import _profile as pf
from conftest import PROFILE, run


def test_a_complete_profile_validates_with_no_error(store):
    done = run("report_profile", "validate", "--profile", store / "profile.md", "--json")
    assert done.returncode == 0, done.stdout
    assert json.loads(done.stdout)["errors"] == []


def test_the_blank_form_does_not_validate(tmp_path):
    form = tmp_path / "profile.md"
    assert run("report_profile", "init", "--out", form).returncode == 0
    assert run("report_profile", "init", "--out", form).returncode == 2, "an existing file needs --force"
    done = run("report_profile", "validate", "--profile", form, "--json")
    assert done.returncode == 3
    kinds = {e["kind"] for e in json.loads(done.stdout)["errors"]}
    assert {"TIER", "REVIEW_DATE", "METRIC_NO_SOURCE"} <= kinds


def test_a_missing_section_and_a_misplaced_catch_all_are_errors(tmp_path):
    text = PROFILE.replace("## Review date", "## Reviewed when").replace("- Kind: other", "- Kind: project")
    path = tmp_path / "profile.md"
    path.write_text(text)
    found = json.loads(run("report_profile", "validate", "--profile", path, "--json").stdout)
    kinds = {e["kind"] for e in found["errors"]}
    assert {"MISSING_SECTION", "OTHER_NOT_LAST"} <= kinds
    assert any("Reviewed when" in r for r in found["reading"])


def test_the_profile_projects_to_the_outline_it_is_read_as(store):
    shown = run("report_profile", "show", "--profile", store / "profile.md", "--outline").stdout
    outline = pf.parse_outline(shown)
    direct = pf.parse_outline(PROFILE)
    assert direct["read_as"] == "profile"
    assert [c["name"] for c in outline["categories"]] == [c["name"] for c in direct["categories"]] == [
        "Month-end close", "Cash and collections", "Systems and support", "Other topics"]
    assert direct["materiality"]["amount"] == 10000
    assert direct["length"]["hard_cap_words"] == 1100
    assert pf.validate_outline(direct) == ([], [])


def test_the_review_falls_due(store):
    done = run("report_profile", "due", "--profile", store / "profile.md", "--today", "2028-03-01", "--json")
    assert json.loads(done.stdout)["due"] is True
    done = run("report_profile", "due", "--profile", store / "profile.md", "--today", "2027-12-01", "--json")
    assert json.loads(done.stdout)["due"] is False


def test_an_acronym_keyword_matches_only_the_acronym():
    categories = pf.compile_outline(pf.parse_outline(PROFILE))
    base = {"kind": "task", "text": "", "subject": "", "domains": [], "names": [], "projects": [], "goals": []}
    filed = lambda title: pf.assign(categories, dict(base, title=title))["category"]  # noqa: E731
    assert filed("Reconcile AR to the ledger") == "Cash and collections"
    assert filed("These are the shareable files") is None
    assert filed("Overdue invoices from the depot") == "Cash and collections"
