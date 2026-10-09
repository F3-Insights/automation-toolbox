"""firm_billing_check: the five tests and the scheduler's precheck."""

import json

from billing_fixtures import PERIOD, billing_folder, done_folder, pdir_of, record, run


def check(folder, *extra):
    res = run("firm_billing_check.py", folder, "--period", PERIOD, "--as-of", "2026-10-05", *extra)
    assert res.returncode == 0, res.stderr
    return res.stdout


def test_nothing_pulled_is_work(tmp_path):
    assert check(billing_folder(tmp_path), "--precheck").strip() == f"WORK: {PERIOD} is not pulled"


def test_done_folder_meets_every_test(tmp_path):
    folder = done_folder(tmp_path)
    result = json.loads(check(folder, "--format", "json"))
    assert result["done"], result["tests"]
    assert check(folder, "--precheck").startswith(f"NOTHING: {PERIOD} billing is done")
    assert check(folder).startswith("DONE: firm billing")


def test_an_edited_draft_fails_drafts_and_review(tmp_path):
    folder = done_folder(tmp_path)
    path = pdir_of(folder) / "invoices" / "acme-ops 2026-09 invoice DRAFT.json"
    d = json.loads(path.read_text())
    d["notes"] = "changed"
    path.write_text(json.dumps(d))
    tests = json.loads(check(folder, "--format", "json"))["tests"]
    assert not tests["drafts"]["met"] and not tests["review"]["met"]


def test_open_row_and_missing_reason(tmp_path):
    folder = done_folder(tmp_path)
    record(folder, "fabrikam-qtr", "open")
    out = check(folder, "--precheck")
    assert out.startswith("WORK:") and "contracts" in out


def test_weekend_and_bad_arguments(tmp_path):
    folder = billing_folder(tmp_path)
    res = run("firm_billing_check.py", folder, "--period", PERIOD, "--as-of", "2026-10-03", "--precheck")
    assert res.stdout.startswith("NOTHING: a weekend")
    assert run("firm_billing_check.py").returncode == 2
    assert run("firm_billing_check.py", folder, "--period", "13-2026").returncode == 2
