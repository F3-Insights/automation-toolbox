"""firm_billing_pull on an invented billing folder."""

import json

import yaml

from billing_fixtures import AS_OF, PERIOD, billing_folder, contract_of, pdir_of, pull, run, write_yaml


def entry(p, cid):
    return next(e for e in p["contracts"] if e["id"] == cid)


def test_first_line_files_and_next_number(tmp_path):
    folder = billing_folder(tmp_path)
    res = run("firm_billing_pull.py", folder, "--period", PERIOD, "--as-of", AS_OF)
    assert res.returncode == 0 and res.stdout.startswith("FRESH: 4 contracts, 4 billable, 3 with unbilled months")
    p = pull(folder)
    assert (pdir_of(folder) / "STATUS.md").exists() and (pdir_of(folder) / "work/source/pulled.md").exists()
    assert len(p["invoices_found"]) == 4 and p["next_number"] == "0018"   # found two levels deep


def test_retainer_capped_hours_and_catch_up_month(tmp_path):
    p = pull(billing_folder(tmp_path))
    acme = entry(p, "acme-ops")
    assert acme["last_billed_month"] == "2026-07" and acme["unbilled_months"] == ["2026-08", "2026-09"]
    assert acme["hours"] == {"2026-08": 15.5, "2026-09": 12.0}
    hours = [line for line in acme["expected"]["2026-09"] if line["rate_id"] == "hours"][0]
    assert hours["quantity"] == 10.0 and hours["amount"] == 2000.0 and "capped at 10" in hours["basis"]


def test_short_time_records_warn_and_milestone_needs_evidence(tmp_path):
    p = pull(billing_folder(tmp_path, september_days=20))
    assert "the time records cover 20 of 30 days of 2026-09" in entry(p, "acme-ops")["warnings"]
    nw = entry(p, "northwind-build")
    assert nw["billable"] and all(line["needs_evidence"] for line in nw["expected"]["2026-09"])
    assert "unconfirmed terms: confirmed is false in BILLING.yaml" in nw["warnings"]


def test_quarterly_advance_and_uncontracted(tmp_path):
    p = pull(billing_folder(tmp_path))
    fab = entry(p, "fabrikam-qtr")
    assert fab["billable"] and "a PO is required and BILLING.yaml has none" in fab["warnings"]
    assert entry(p, "lakeview-adv")["unbilled_months"] == []          # billed in advance for September
    assert [u["id"] for u in p["uncontracted"]] == ["client:other-co"]


def test_stale_yaml_writes_nothing_and_dry_run_stays_in_the_run_dir(tmp_path):
    folder = billing_folder(tmp_path)
    (folder / "BILLING.yaml").write_text("version: 2\n")
    res = run("firm_billing_pull.py", folder, "--period", PERIOD)
    assert res.returncode == 0 and res.stdout.startswith("STALE:") and not pdir_of(folder).exists()
    write_yaml(folder)
    res = run("firm_billing_pull.py", folder, "--period", PERIOD, "--dry-run-if=true", "--run-dir", tmp_path / "run")
    assert res.returncode == 0 and (tmp_path / "run/billing/2026/2026-09/work/source/billing-pull.json").exists()
    assert not pdir_of(folder).exists()


def test_invoice_ledger_and_bad_arguments(tmp_path):
    ledger = tmp_path / "sent.csv"
    ledger.write_text("number,client,date\n0020,Acme,2026-09-01\n")
    folder = billing_folder(tmp_path, lambda d: d["settings"].update(invoice_ledger=str(ledger)))
    assert entry(pull(folder), "acme-ops")["unbilled_months"] == ["2026-09"]
    assert run("firm_billing_pull.py").returncode == 2
    assert run("firm_billing_pull.py", folder, "--period", "Sept").returncode == 2
    assert run("firm_billing_pull.py", folder, "--period=", "--as-of=", "--run-dir=").returncode == 0


def test_unreadable_time_rows_are_warned_not_dropped_silently(tmp_path):
    folder = billing_folder(tmp_path)
    hours_csv = tmp_path / "time" / "hours.csv"
    hours_csv.write_text(hours_csv.read_text() + "2026-09-15,acme,2.5h\n2026-09-16,acme,\n2026-9-17,acme,1\n")
    res = run("firm_billing_pull.py", folder, "--period", PERIOD, "--as-of", AS_OF, "--format", "json")
    assert res.returncode == 0, res.stderr
    warnings = json.loads(res.stdout)["pull"]["time"]["warnings"]
    assert len(warnings) == 3
    assert "line 64" in warnings[0] and "'2.5h' are not a number" in warnings[0]
    assert "'' are not a number" in warnings[1] and "'2026-9-17' is not yyyy-mm-dd" in warnings[2]
    assert res.stderr.count("WARNING ") == 3 and "2.5h" in res.stderr
    p = pull(folder)
    assert entry(p, "acme-ops")["hours"]["2026-09"] == 12.0      # the good rows are still counted
    assert "Warning: hours.csv line 64" in (pdir_of(folder) / "work/source/pulled.md").read_text()
