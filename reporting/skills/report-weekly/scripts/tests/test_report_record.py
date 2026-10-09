"""report_record.py: the week kept with its manifest, and the proposals read back from it."""

import json

from conftest import run


DRAFT = """# Weekly Highlights - Finance - 2027-11-12

## Cash and collections

- **Credit hold:** the Fabrikam Logistics credit hold is disputed; we expect a decision by 2027-11-19.
- **Cash:** cash on hand is steady and we are pleased to report it.
"""

APPROVED = DRAFT.replace("steady and we are pleased to report it", "steady") + \
    "- **Depot move:** the depot move starts on 2027-11-22.\n"


def save(tmp_path, store, period, report, draft=None, *extra):
    (tmp_path / "approved.md").write_text(report)
    args = ["save", "--store", store, "--period", period, "--report", tmp_path / "approved.md",
            "--profile", store / "profile.md", "--seat", "Finance", "--json", *extra]
    if draft is not None:
        (tmp_path / "draft.md").write_text(draft)
        args += ["--draft", tmp_path / "draft.md"]
    return run("report_record", *args)


def test_save_keeps_the_week_redacts_and_hands_it_to_the_ledger(tmp_path, store):
    pack = tmp_path / "pack.json"
    pack.write_text(json.dumps({"categories": [], "items": [{"text": "Fabrikam Logistics owes the remittance"}]}))
    done = save(tmp_path, store, "2027-11-12", APPROVED, DRAFT, "--pack", pack)
    assert done.returncode == 0, done.stderr
    manifest = json.loads(done.stdout)
    assert manifest["ledger_pending"] is False and manifest["ledger"]["bullets"] == 3
    assert {r["file"] for r in manifest["redactions"]} == {"report.md", "draft.md", "pack.json"}
    assert all(r["rule"] == "never-recorded rule 1" for r in manifest["redactions"])
    stored = "".join(p.read_text() for p in (store / "records" / "2027-11-12").iterdir() if p.is_file())
    assert "Fabrikam Logistics" not in stored + (store / "report-ledger.jsonl").read_text()
    size = manifest["edit_size"]
    assert (size["bullets_added"], size["bullets_changed"], size["bullets_unchanged"]) == (1, 1, 1)
    row = json.loads((store / "edit-size.jsonl").read_text().splitlines()[-1])
    assert row["measured"] is True and row["word_change_ratio"] > 0


def test_a_week_with_no_draft_records_nulls_not_zeros(tmp_path, store):
    assert save(tmp_path, store, "2027-11-12", APPROVED, None, "--skip-ledger").returncode == 0
    row = json.loads((store / "edit-size.jsonl").read_text())
    assert row["measured"] is False and row["bullets_added"] is None and "no --draft" in row["reason"]


def test_a_never_published_term_refuses_the_record_and_writes_nothing(tmp_path, store):
    done = save(tmp_path, store, "2027-11-19", APPROVED + "- **Settlement:** the Lakeview settlement closed.\n")
    assert done.returncode == 3 and "never-published" in done.stderr
    assert not (store / "records").exists()


def test_learn_proposes_a_phrase_the_author_always_takes_out(tmp_path, store):
    for period in ("2027-11-12", "2027-11-19", "2027-11-26"):
        assert save(tmp_path, store, period, APPROVED, DRAFT, "--skip-ledger").returncode == 0
    found = json.loads(run("report_record", "learn", "--store", store, "--json").stdout)
    kinds = {p["kind"] for p in found["proposals"]}
    assert {"phrase_always_rewritten", "recurring_manual_addition"} <= kinds
    assert any("pleased to report" in p["detail"] for p in found["proposals"])


def test_rendered_files_are_kept_by_reference_while_a_never_recorded_list_is_in_force(tmp_path, store):
    pdf = tmp_path / "weekly-2027-11-12.pdf"
    pdf.write_bytes(b"%PDF-1.4 Fabrikam Logistics owes the remittance")
    done = save(tmp_path, store, "2027-11-12", APPROVED, DRAFT, "--skip-ledger", "--rendered", pdf)
    assert done.returncode == 0, done.stderr
    manifest = json.loads(done.stdout)
    assert not (store / "records" / "2027-11-12" / "rendered").exists()
    assert manifest["rendered"][0]["stored"] == "by reference" and len(manifest["rendered"][0]["sha256"]) == 64
    assert manifest["rendered_storage"].startswith("by reference")


def test_rendered_files_are_copied_when_the_never_recorded_list_is_empty(tmp_path, store):
    profile = store / "profile.md"
    profile.write_text(profile.read_text().replace("## Never recorded\n\n1. Fabrikam Logistics\n", "## Never recorded\n\n"))
    pdf = tmp_path / "weekly-2027-11-12.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    done = save(tmp_path, store, "2027-11-12", APPROVED, DRAFT, "--skip-ledger", "--rendered", pdf)
    assert done.returncode == 0, done.stderr
    assert (store / "records" / "2027-11-12" / "rendered" / pdf.name).read_bytes() == b"%PDF-1.4"
    assert json.loads(done.stdout)["rendered_storage"].startswith("copied")


def test_never_recorded_is_redacted_inside_a_word_in_the_record_and_the_ledger(tmp_path, store):
    profile = store / "profile.md"
    profile.write_text(profile.read_text().replace("1. Fabrikam Logistics", "1. Bluejay"))
    report = APPROVED + "- **Systems:** Projectbluejay went live on 2027-11-10.\n"
    done = save(tmp_path, store, "2027-11-12", report, DRAFT)
    assert done.returncode == 0, done.stderr
    stored = (store / "records" / "2027-11-12" / "report.md").read_text()
    assert "bluejay" not in stored.casefold() and "[redacted: never recorded]" in stored
    assert "bluejay" not in (store / "report-ledger.jsonl").read_text().casefold()


def test_learn_merges_the_overlapping_phrases_of_one_struck_sentence(tmp_path, store):
    for period in ("2027-11-12", "2027-11-19", "2027-11-26"):
        assert save(tmp_path, store, period, APPROVED, DRAFT, "--skip-ledger").returncode == 0
    found = json.loads(run("report_record", "learn", "--store", store, "--json").stdout)
    phrases = [p["detail"] for p in found["proposals"] if p["kind"] == "phrase_always_rewritten"]
    assert len(phrases) == 1 and "'is steady and we are pleased to report'" in phrases[0]
