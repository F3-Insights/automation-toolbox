"""fleet_status.py on the Northwind Traders fleet, with a fake runner and a fake check."""

import json
import stat

import _common as c
import fleet_status as fst
from conftest import now_iso


def status(cli, *args):
    code, out, err = cli(fst, *args)
    assert code == 0, err
    return out


def test_status_rows_from_the_runner(fleet, cli):
    fleet.runs({"runs": [
        {"id": "o-3", "automation": "northwind-orders", "status": "running", "started_at": now_iso(0)},
        {"id": "o-2", "automation": "northwind-orders", "status": "awaiting_owner", "started_at": now_iso(2)},
        {"id": "o-1", "workflow": "northwind-orders", "status": "completed", "accepted": True,
         "started_at": now_iso(30)},
        {"run_id": "r-1", "automation": "northwind-receiving", "status": "failed", "accepted": False,
         "started_at": now_iso(1), "for_owner": ["confirm the dock schedule with Priya"],
         "source": json.dumps({"kind": "schedule"})},
    ], "queue": [{"automation": "northwind-pricing", "queued_at": now_iso(0)}]})
    data = json.loads(status(cli, "--format", "json"))
    assert set(data) == {"registry", "runs_error", "orchestrators"} and data["runs_error"] is None
    rows = {r["name"]: r for r in data["orchestrators"]}
    orders = rows["northwind-orders-orchestrator"]
    assert orders["last_run"]["id"] == "o-3" and orders["last_run"]["outcome"] == "running"
    assert orders["live"] is True and orders["queued"] is False and orders["waiting_on_owner"] == 1
    receiving = rows["northwind-receiving-orchestrator"]
    assert receiving["last_run"]["outcome"] == "failed, not accepted" and receiving["live"] is False
    assert receiving["last_run"]["source"] == "schedule" and receiving["waiting_on_owner"] == 1
    assert receiving["check"] == "WORK: 3 purchase orders to review"
    assert (fleet.tmp / "check.log").read_text().strip() == "--precheck"
    pricing = rows["northwind-pricing-orchestrator"]
    assert pricing["queued"] is True and pricing["last_run"] is None
    assert rows["northwind-returns-orchestrator"]["check"] == "skipped: not built"
    assert set(orders) == {"name", "domain", "status", "authority", "automation", "last_run", "live", "queued",
                           "waiting_on_owner", "check"}


def test_status_text(fleet, cli):
    fleet.runs([{"id": "o-1", "automation": "northwind-orders", "status": "completed", "accepted": True,
                 "started_at": now_iso(1)}])
    out = status(cli, "--no-checks")
    assert "o-1" in out and "completed, accepted" in out


def test_status_survives_an_unreadable_runner(fleet, cli):
    fleet.runs_file.unlink()
    out = status(cli, "--no-checks")
    assert "runs unavailable: runs_command failed: runner: no trace to read" in out
    assert "northwind-orders-orchestrator" in out
    fleet.runs_file.write_text("not json")
    data = json.loads(status(cli, "--no-checks", "--format", "json"))
    assert "did not print JSON" in data["runs_error"] and len(data["orchestrators"]) == 5


def test_status_without_runs_command_reports_it(fleet, cli):
    settings = dict(fleet.base_settings)
    settings.pop("runs_command")
    fleet.set_settings(**settings)
    data = json.loads(status(cli, "--no-checks", "--format", "json"))
    assert data["runs_error"] == "setting [orchestrator-fleet] runs_command is needed"


def test_status_filters(fleet, cli):
    data = json.loads(status(cli, "--status", "live", "--no-checks", "--format", "json"))
    assert {r["name"] for r in data["orchestrators"]} == {"northwind-orders-orchestrator",
                                                          "northwind-pricing-orchestrator"}
    data = json.loads(status(cli, "--domain", "lakeview", "--no-checks", "--format", "json"))
    assert data["orchestrators"] == []


def test_status_without_registry_exits_2(fleet, cli):
    fleet.set_settings()
    code, _, err = cli(fst, "--no-checks")
    assert code == 2 and "registry is needed" in err


def test_check_headline_rules(fleet, tmp_path, monkeypatch):
    assert fst.check_headline(None, "live") is None
    assert fst.check_headline("northwind-check", "spec") == "skipped: not built"
    assert fst.check_headline("northwind-check {customer}", "live") == "skipped: needs launch params"
    assert fst.check_headline("no-such-northwind-command", "live").startswith("skipped:")
    slow = tmp_path / "bin" / "northwind-slow"
    slow.write_text("#!/bin/sh\nsleep 5\n")
    slow.chmod(slow.stat().st_mode | stat.S_IEXEC)
    assert fst.check_headline("northwind-slow", "live", timeout=1) == "timed out after 1s"
    failing = tmp_path / "bin" / "northwind-fail"
    failing.write_text("#!/bin/sh\necho 'no ledger folder' >&2\nexit 2\n")
    failing.chmod(failing.stat().st_mode | stat.S_IEXEC)
    assert fst.check_headline("northwind-fail --precheck", "live") == "exit 2: no ledger folder"


def test_check_headline_expands_home(fleet, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert fst.check_headline("~/bin/northwind-check", "live") == "WORK: 3 purchase orders to review"


def test_parse_runs_reads_leniently():
    runs = c.parse_runs(json.dumps([
        {"id": "a", "automation": "x", "status": "completed", "created_at": "2030-03-01T09:00:00Z",
         "source_kind": "agent", "params": {"dry_run": True}},
        {"id": "b", "workflow": "x", "status": "running", "at": "2030-03-02T09:00:00",
         "source": {"kind": "agent", "agent": "fabrikam-cycle-orchestrator"}, "live": False},
        {"id": "c", "status": "completed"},   # no automation: ignored
    ]))
    assert [r.id for r in runs] == ["b", "a"]
    assert runs[0].source_agent == "fabrikam-cycle-orchestrator" and runs[0].is_live is False
    assert runs[1].source_kind == "agent" and runs[1].dry_run is True
