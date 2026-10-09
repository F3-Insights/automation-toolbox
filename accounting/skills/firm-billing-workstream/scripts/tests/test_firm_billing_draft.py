"""firm_billing_draft: drafting from a lines file, refusals and --verify."""

import json

import pytest

from billing_fixtures import PERIOD, acme_lines, billing_folder, draft_acme, pdir_of, pull, run, write_yaml


def test_draft_writes_three_files_then_v2(tmp_path):
    folder = billing_folder(tmp_path)
    pull(folder)
    first = draft_acme(folder)
    d = json.loads(first.read_text())
    assert d["total"] == 7000.0 and d["proposed_number"] == "0018" and d["due_date"] == "2026-10-31"
    assert first.with_suffix(".md").read_text().startswith("# DRAFT invoice, proposed number 0018")
    assert "DRAFT" in first.with_suffix(".html").read_text()
    second = draft_acme(folder)
    assert second.name == "acme-ops 2026-09 invoice DRAFT v2.json" and first.read_text() == json.dumps(d, indent=1) + "\n"


def test_verify_ok_then_refused_after_an_edit(tmp_path):
    folder = billing_folder(tmp_path)
    pull(folder)
    path = draft_acme(folder)
    res = run("firm_billing_draft.py", folder, "--verify", path)
    assert res.returncode == 0 and res.stdout.startswith("OK: ")
    d = json.loads(path.read_text())
    d["total"] = 9000
    path.write_text(json.dumps(d))
    res = run("firm_billing_draft.py", folder, "--verify", path)
    assert res.returncode == 1 and "edited after drafting" in res.stdout


@pytest.mark.parametrize("change, reason", [
    ({"months": ["2026-07"]}, "not one of the pull's unbilled months"),
    ({"lines": [{"rate_id": "retainer", "month": "2026-09", "quantity": 1, "unit_price": 5000, "amount": 4000}]},
     "is not quantity"),
    ({"lines": [{"rate_id": "hours", "month": "2026-09", "quantity": 12, "unit_price": 200, "amount": 2400}]},
     "is not the pull's hours"),
    ({"lines": [{"rate_id": "bonus", "month": "2026-09", "quantity": 1, "unit_price": 1, "amount": 1}]},
     "is not a rate of acme-ops"),
])
def test_refusals_write_nothing(tmp_path, change, reason):
    folder = billing_folder(tmp_path)
    pull(folder)
    res = run("firm_billing_draft.py", folder, "--period", PERIOD, "--contract", "acme-ops",
              "--lines", acme_lines(folder, **change))
    assert res.returncode == 1 and reason in res.stdout
    assert not (pdir_of(folder) / "invoices").exists()


def test_hours_override_and_evidence_files(tmp_path):
    folder = billing_folder(tmp_path)
    pull(folder)
    lines = [{"rate_id": "hours", "month": "2026-09", "quantity": 8, "unit_price": 200, "amount": 1600,
              "override_reason": "the owner capped September at 8 hours"}]
    assert draft_acme(folder, lines=lines).is_file()
    nw = {"contract": "northwind-build", "period": PERIOD, "months": ["2026-09"],
          "lines": [{"rate_id": "m1", "month": "2026-09", "quantity": 1, "unit_price": 7500, "amount": 7500,
                     "evidence": ["readout.pdf"]}]}
    path = tmp_path / "nw.json"
    path.write_text(json.dumps(nw))
    args = ["firm_billing_draft.py", folder, "--period", PERIOD, "--contract", "northwind-build", "--lines", path]
    assert "is not a file that exists" in run(*args).stdout
    (folder / "readout.pdf").write_text("pdf")
    assert run(*args).returncode == 0


def test_stale_pull_po_and_bad_arguments(tmp_path):
    folder = billing_folder(tmp_path)
    pull(folder)
    fab = {"contract": "fabrikam-qtr", "period": PERIOD, "months": ["2026-07", "2026-08", "2026-09"],
           "lines": [{"rate_id": "retainer", "month": "2026-09", "quantity": 1, "unit_price": 3000, "amount": 3000}]}
    path = tmp_path / "fab.json"
    path.write_text(json.dumps(fab))
    res = run("firm_billing_draft.py", folder, "--period", PERIOD, "--contract", "fabrikam-qtr", "--lines", path)
    assert "requires a PO" in res.stdout
    write_yaml(folder, lambda d: d["settings"].update(currency="EUR"))
    res = run("firm_billing_draft.py", folder, "--period", PERIOD, "--contract", "acme-ops", "--lines", acme_lines(folder))
    assert res.returncode == 1 and "the pull is stale" in res.stdout
    assert run("firm_billing_draft.py", folder, "--period", PERIOD, "--contract", "acme-ops").returncode == 2
