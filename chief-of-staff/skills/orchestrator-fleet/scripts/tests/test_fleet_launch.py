"""fleet_launch.py on the Northwind Traders fleet, with a fake runner."""

import json

import pytest

import fleet_launch as fl
from conftest import now_iso


def launch(cli, *args):
    return cli(fl, *args)


def test_launch_queues_through_the_runner(fleet, cli):
    code, out, _ = launch(cli, "northwind-orders-orchestrator", "--params", "customer=lakeview-hardware")
    assert code == 0, out
    assert out.strip() == "queued northwind-orders-20300308 (queue 4)"
    assert fleet.launches()[-1] == ["launch", str(fleet.autos / "northwind-orders"), "--source", "agent",
                                    "--by", "", "--param", "customer=lakeview-hardware"]


def test_launch_json_shape_and_by(fleet, cli):
    code, out, _ = launch(cli, "northwind-orders-orchestrator", "--authority", "propose", "--cap", "2",
                          "--by", "northwind-cycle-orchestrator", "--format", "json", "--dry-run",
                          "--params", "customer=fabrikam")
    assert code == 0
    result = json.loads(out)
    assert result == {"action": "queued", "name": "northwind-orders-orchestrator",
                      "automation": "northwind-orders", "params": {"customer": "fabrikam", "dry_run": "true"},
                      "launches_today": 1, "cap": 2, "output": ["queued northwind-orders-20300308 (queue 4)"]}
    call = fleet.launches()[-1]
    assert call[4:6] == ["--by", "northwind-cycle-orchestrator"] and call[-2:] == ["--param", "dry_run=true"]


def test_params_after_one_flag_or_repeated(fleet, cli):
    fleet.data["orchestrators"][1]["inputs"] = {"customer": None, "week": None}
    fleet.save()
    assert launch(cli, "northwind-orders-orchestrator", "--params", "customer=a", "week=10")[0] == 0
    assert launch(cli, "northwind-orders-orchestrator", "--params", "customer=a", "--param", "week=10")[0] == 0
    assert fleet.launches()[-1][-4:] == fleet.launches()[-2][-4:] == ["--param", "customer=a", "--param", "week=10"]


def test_custom_template_and_param_args(fleet, cli):
    fleet.set_settings(**{**fleet.base_settings,
                          "launch_command": fleet.base_settings["launch_command"][:3] + ["{automation}"],
                          "param_args": ["-p", "{key}", "{value}"]})
    assert launch(cli, "northwind-orders-orchestrator", "--params", "customer=acme")[0] == 0
    assert fleet.launches()[-1] == ["launch", "northwind-orders", "-p", "customer", "acme"]


def test_the_launch_command_comes_from_settings_and_runs_without_a_shell(fleet, cli, tmp_path):
    fleet.data["orchestrators"][1]["inputs"] = {"note": None}
    fleet.save()
    marker = tmp_path / "chained"
    value = f"x; touch {marker} $(touch {marker}) `touch {marker}`"
    assert launch(cli, "northwind-orders-orchestrator", "--params", f"note={value}")[0] == 0
    assert fleet.launches()[-1][-2:] == ["--param", f"note={value}"]
    assert not marker.exists()
    fleet.set_settings(**{k: v for k, v in fleet.base_settings.items() if k != "launch_command"})
    code, out, _ = launch(cli, "northwind-orders-orchestrator", "--params", "note=x")
    assert code == 2 and "launch_command" in out


def test_dry_run_only_entry_is_forced_dry(fleet, cli):
    code, _, err = launch(cli, "northwind-close-orchestrator", "--params", "period=2030-02")
    assert code == 0 and "dry run forced: the entry at dry-run-only" in err
    assert "dry_run=true" in fleet.launches()[-1]


def test_dry_run_only_caller_forces_dry_too(fleet, cli):
    assert launch(cli, "northwind-close-orchestrator", "--authority", "dry-run-only")[0] == 0
    assert "dry_run=true" in fleet.launches()[-1]


@pytest.mark.parametrize("args, reason", [
    (["northwind-nobody-orchestrator"], "not in the registry"),
    (["northwind-returns-orchestrator"], "status spec"),
    (["northwind-pricing-orchestrator"], "needs authority trusted; the caller has propose"),
    (["northwind-orders-orchestrator", "--authority", "dry-run-only"], "needs authority propose"),
    (["northwind-orders-orchestrator", "--params", "run_dir=/tmp/x"], "a name the runner fills itself"),
    (["northwind-orders-orchestrator", "--params", "task=1"], "a name the runner fills itself"),
    (["northwind-orders-orchestrator", "--params", "region=west"], "not one of northwind-orders-orchestrator's inputs"),
    (["northwind-orders-orchestrator", "--params", "customer=Lakeview Hardware"], "does not match"),
    (["northwind-orders-orchestrator", "--params", "dry_run=perhaps"], "true or false"),
])
def test_launch_refuses(fleet, cli, args, reason):
    code, out, _ = launch(cli, *args)
    assert code == 1 and out.startswith("refused:") and reason in out, out
    assert fleet.launches() == []


def test_missing_automation_folder_is_refused(fleet, cli):
    (fleet.autos / "northwind-orders").rmdir()
    code, out, _ = launch(cli, "northwind-orders-orchestrator", "--format", "json")
    assert code == 1 and "does not exist" in json.loads(out)["reason"]


def test_bad_param_shape_is_exit_2(fleet, cli):
    assert launch(cli, "northwind-orders-orchestrator", "--params", "customer")[0] == 2


def test_missing_launch_command_is_exit_2(fleet, cli):
    settings = dict(fleet.base_settings)
    settings.pop("launch_command")
    fleet.set_settings(**settings)
    code, out, _ = launch(cli, "northwind-orders-orchestrator")
    assert code == 2 and "setting [orchestrator-fleet] launch_command is needed" in out


def test_automation_path_needs_automations_dir(fleet, cli):
    settings = dict(fleet.base_settings)
    settings.pop("automations_dir")
    fleet.set_settings(**settings)
    code, out, _ = launch(cli, "northwind-orders-orchestrator")
    assert code == 2 and "automations_dir is needed" in out


def test_cap_counts_todays_agent_launches(fleet, cli):
    fleet.runs([
        {"id": "1", "automation": "northwind-orders", "status": "completed", "started_at": now_iso(0),
         "source": {"kind": "agent"}},
        {"id": "2", "automation": "northwind-orders", "status": "completed", "started_at": now_iso(0),
         "source": json.dumps({"kind": "agent"})},
        {"id": "3", "automation": "northwind-receiving", "status": "completed", "started_at": now_iso(0),
         "source": {"kind": "schedule"}},
        {"id": "0", "automation": "northwind-orders", "status": "completed", "started_at": now_iso(72),
         "source_kind": "agent"},
    ])
    assert launch(cli, "northwind-orders-orchestrator", "--cap", "3")[0] == 0
    code, out, _ = launch(cli, "northwind-orders-orchestrator", "--cap", "2", "--format", "json")
    assert code == 1 and json.loads(out)["reason"] == "daily cap reached: 2 agent launches today, cap 2"
    assert launch(cli, "northwind-orders-orchestrator")[0] == 0   # the registry's cap (3) applies


def test_cap_by_one_agent_counts_only_its_launches(fleet, cli):
    fleet.runs([
        {"id": "1", "automation": "northwind-orders", "status": "completed", "started_at": now_iso(0),
         "source": {"kind": "agent", "agent": "northwind-cycle-orchestrator"}},
        {"id": "2", "automation": "northwind-orders", "status": "completed", "started_at": now_iso(0),
         "source": {"kind": "agent", "agent": "northwind-tick-orchestrator"}},
        {"id": "3", "automation": "northwind-orders", "status": "completed", "started_at": now_iso(0),
         "source": {"kind": "agent", "agent": "northwind-tick-orchestrator"}},
    ])
    assert launch(cli, "northwind-orders-orchestrator", "--cap", "2", "--by", "northwind-cycle-orchestrator")[0] == 0
    code, out, _ = launch(cli, "northwind-orders-orchestrator", "--cap", "1", "--by", "northwind-cycle-orchestrator")
    assert code == 1 and "daily cap reached: 1 launches by northwind-cycle-orchestrator today, cap 1" in out
    assert launch(cli, "northwind-orders-orchestrator", "--cap", "3")[0] == 1


def test_cap_counts_sourceless_runs_of_registered_automations(fleet, cli):
    fleet.runs([
        {"id": "1", "automation": "northwind-orders", "status": "completed", "started_at": now_iso(0)},
        {"id": "2", "automation": "northwind-receiving", "status": "completed", "started_at": now_iso(0)},
        {"id": "3", "automation": "unregistered-thing", "status": "completed", "started_at": now_iso(0)},
    ])
    code, out, _ = launch(cli, "northwind-orders-orchestrator", "--cap", "2", "--by", "northwind-cycle-orchestrator")
    assert code == 1 and "daily cap reached: 2" in out


def test_unreadable_runs_refuse_a_capped_launch(fleet, cli):
    fleet.runs_file.unlink()
    code, out, _ = launch(cli, "northwind-orders-orchestrator")
    assert code == 1 and "cannot count today's launches" in out
    settings = dict(fleet.base_settings)
    settings.pop("runs_command")
    fleet.set_settings(**settings)
    code, out, _ = launch(cli, "northwind-orders-orchestrator")
    assert code == 1 and "runs_command is needed" in out


def test_runner_refusal_passes_through(fleet, cli, monkeypatch):
    monkeypatch.setenv("FAKE_REFUSE", "1")
    code, out, _ = launch(cli, "northwind-orders-orchestrator", "--format", "json")
    result = json.loads(out)
    assert code == 1 and result["reason"] == "refused by the runner"
    assert result["output"] == ["refused northwind-orders: daily limit", "  the Automation's own limit is reached"]


def test_no_cap_means_no_count(fleet, cli):
    del fleet.data["launch_cap_per_day"]
    fleet.save()
    fleet.runs_file.unlink()
    assert launch(cli, "northwind-orders-orchestrator", "--by", "northwind-cycle-orchestrator")[0] == 0
    assert launch(cli, "northwind-orders-orchestrator", "--authority", "trusted")[0] == 0


def test_a_propose_caller_with_no_cap_and_no_by_fails_closed(fleet, cli):
    del fleet.data["launch_cap_per_day"]
    fleet.save()
    code, out, _ = launch(cli, "northwind-orders-orchestrator")
    assert code == 1 and "no launch cap" in out
    assert fleet.launches() == []
