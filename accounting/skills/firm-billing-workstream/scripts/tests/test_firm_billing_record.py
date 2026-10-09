"""firm_billing_record: the evidence file and what each state needs."""

import json

from billing_fixtures import LAKEVIEW_INVOICE, PERIOD, billing_folder, draft_acme, pdir_of, pull, record

HEADER = ("id,client,state,draft,amount,rate_basis,months,evidence,question,note,content_sha256,"
          "review,review_file,review_sha256,updated_at,by")


def evidence(folder):
    return (pdir_of(folder) / f"BILLING-EVIDENCE-{PERIOD}.csv").read_text()


def test_drafted_reads_the_draft_and_a_new_draft_clears_the_review(tmp_path):
    folder = billing_folder(tmp_path)
    pull(folder)
    path = draft_acme(folder)
    review = tmp_path / "review.md"
    review.write_text("PASS")
    res = record(folder, "acme-ops", "drafted", "--draft", path, "--review", "PASS", "--review-file", review)
    assert res.stdout.strip() == "RECORDED: acme-ops drafted (created)"
    text = evidence(folder)
    assert text.splitlines()[0] == HEADER and ",7000.00,retainer,hours,2026-09," in text.replace('"', "")
    second = draft_acme(folder)
    res = record(folder, "acme-ops", "drafted", "--draft", second)
    assert "the earlier review was cleared" in res.stdout and ",PASS," not in evidence(folder)
    assert record(folder, "acme-ops", "drafted", "--draft", second, "--amount", "1").returncode == 1


def test_states_and_what_each_needs(tmp_path):
    folder = billing_folder(tmp_path)
    pull(folder)
    assert record(folder, "fabrikam-qtr", "not-billable").returncode == 1
    assert record(folder, "fabrikam-qtr", "not-billable", "--note", "next quarter").returncode == 0
    assert record(folder, "northwind-build", "question", "--note", "n").returncode == 1
    assert record(folder, "lakeview-adv", "already-billed", "--evidence", "nothing.pdf").returncode == 1
    assert record(folder, "lakeview-adv", "already-billed", "--evidence", LAKEVIEW_INVOICE).returncode == 0
    assert record(folder, "client:other-co", "drafted").returncode == 2
    assert record(folder, "client:other-co", "question", "--question", "Q", "--note", "n").returncode == 0
    nw = {"contract": "northwind-build", "period": PERIOD, "months": ["2026-09"], "lines": []}
    (tmp_path / "x.json").write_text(json.dumps(nw))
    assert "unconfirmed" in record(folder, "northwind-build", "drafted", "--draft", tmp_path / "x.json").stdout


def test_review_rules_and_bad_arguments(tmp_path):
    folder = billing_folder(tmp_path)
    pull(folder)
    assert record(folder, "acme-ops", "open", "--review", "PASS", "--review-file", "none.md").returncode == 1
    assert record(folder, "acme-ops", "open", "--review-file", "none.md").returncode == 1
    assert record(folder, "unknown-co", "open").returncode == 2
    assert record(folder, "acme-ops", "finished").returncode == 2
    assert record(folder, "acme-ops", "open", "--rate-basis", "bonus").returncode == 2
    assert record(folder, "acme-ops", "open", "--months", "Sept").returncode == 2
    assert record(folder, "acme-ops", "open", "--period-dir=", "--note=", "--by=").returncode == 0


def test_an_update_keeps_the_evidence_file_permissions(tmp_path):
    # The file is replaced atomically; the replacement must not tighten or loosen who can read it.
    folder = billing_folder(tmp_path)
    pull(folder)
    assert record(folder, "fabrikam-qtr", "not-billable", "--note", "billed next quarter").returncode == 0
    path = pdir_of(folder) / f"BILLING-EVIDENCE-{PERIOD}.csv"
    path.chmod(0o640)
    assert record(folder, "fabrikam-qtr", "not-billable", "--note", "billed in December").returncode == 0
    assert path.stat().st_mode & 0o777 == 0o640
