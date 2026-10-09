"""fleet_registry.py list and validate, on the Northwind Traders fleet."""

import json

import pytest

import _common as c
import fleet_registry as fr


def test_list_text_json_and_filters(fleet, cli):
    code, out, _ = cli(fr, "list")
    assert code == 0 and "northwind-close-orchestrator" in out and "5 of 5 orchestrators" in out
    code, out, _ = cli(fr, "list", "--status", "live", "--format", "json")
    assert [e["name"] for e in json.loads(out)] == ["northwind-orders-orchestrator", "northwind-pricing-orchestrator"]
    _, out, _ = cli(fr, "list", "--domain", "fabrikam")
    assert "no orchestrators match" in out


def test_validate_clean_fleet(fleet, cli):
    code, out, _ = cli(fr, "validate", "--format", "json")
    report = json.loads(out)
    assert code == 0, report
    assert report["ok"] and report["errors"] == [] and report["warnings"] == [] and report["entries"] == 5
    assert report["by_status"] == {"dry-run-passed": 1, "live": 2, "scheduled": 1, "spec": 1}


def test_no_registry_setting_exits_2(fleet, cli):
    fleet.set_settings()
    code, _, err = cli(fr, "list")
    assert code == 2 and "setting [orchestrator-fleet] registry is needed (or pass --registry)" in err
    code, _, _ = cli(fr, "list", "--registry", str(fleet.registry))
    assert code == 0


def test_missing_registry_file_exits_2(fleet, cli):
    code, _, err = cli(fr, "validate", "--registry", str(fleet.tmp / "nope.yaml"))
    assert code == 2 and "no registry" in err


def test_without_automations_dir_folders_are_not_checked(fleet, cli):
    settings = dict(fleet.base_settings)
    settings.pop("automations_dir")
    fleet.set_settings(**settings)
    fleet.data["orchestrators"][4]["automation"] = "northwind-nowhere"
    fleet.save()
    code, out, _ = cli(fr, "validate", "--format", "json")
    report = json.loads(out)
    assert code == 0 and any("not checked" in w for w in report["warnings"])


def test_registry_automations_dir_is_relative_to_the_registry(fleet):
    settings = dict(fleet.base_settings)
    settings.pop("automations_dir")
    fleet.set_settings(**settings)
    fleet.data["automations_dir"] = "../automations"
    fleet.save()
    registry = c.load_registry()
    assert registry.automations_dir().resolve() == fleet.autos.resolve()


def errors_for(fleet):
    registry = c.load_registry()
    return fr.validate(registry, c.agents_dir(), registry.automations_dir())[0]


@pytest.mark.parametrize("change, expected", [
    (lambda d: d["orchestrators"].append(dict(d["orchestrators"][4])), "registered twice"),
    (lambda d: d["orchestrators"][4].update(name="northwind-returns"), "-orchestrator"),
    (lambda d: d["orchestrators"][4].update(status="built"), "no agent file"),
    (lambda d: d["orchestrators"][4].update(automation="northwind-missing"), "does not exist"),
    (lambda d: d["orchestrators"][4].update(automation="northwind-close"), "already northwind-close-orchestrator's"),
    (lambda d: d["orchestrators"][4].update(inputs={"run_dir": None}), "a name the runner fills itself"),
    (lambda d: d["orchestrators"][4].update(inputs={"dry_run": None}), "a name the runner fills itself"),
    (lambda d: d["orchestrators"][4].update(inputs={"x": "(unclosed"}), "does not compile"),
    (lambda d: d["orchestrators"][4].update(triggers={"schedule": "60 * * * *"}), "outside 0-59"),
    (lambda d: d["orchestrators"][4].update(triggers={"schedule": "* * *"}), "five fields"),
    (lambda d: d["orchestrators"][4].update(triggers={"tz": "Moon/Crater"}), "not an IANA zone"),
    (lambda d: d["orchestrators"][4].update(triggers={"precheck": "northwind-check 'open"}), "does not parse"),
    (lambda d: d["orchestrators"][4].update(triggers={"hourly": True}), "unknown key 'hourly'"),
    (lambda d: d["orchestrators"][4].update(colour="blue"), "unknown field colour"),
    (lambda d: d["orchestrators"][4].pop("record"), "missing record"),
    (lambda d: d["orchestrators"][4].update(tier="Z"), "tier 'Z'"),
    (lambda d: d["orchestrators"][4].update(authority="owner"), "authority 'owner'"),
    (lambda d: d["orchestrators"][4].update(status="scheduled"), "names no Automation"),
    (lambda d: d["orchestrators"][4].update(wave=-1), "wave must be"),
    (lambda d: d["orchestrators"][4].update(value="X"), "value 'X'"),
])
def test_validate_catches(fleet, cli, change, expected):
    change(fleet.data)
    fleet.save()
    errors = errors_for(fleet)
    assert any(expected in e for e in errors), errors
    code, out, _ = cli(fr, "validate")
    assert code == 1 and out.startswith("FAIL")


def test_agent_file_is_found_in_any_subfolder_and_flag_overrides(fleet, cli):
    elsewhere = fleet.tmp / "other-agents"
    elsewhere.mkdir()
    code, out, _ = cli(fr, "validate", "--agents-dir", str(elsewhere), "--format", "json")
    assert code == 1 and any("no agent file" in e for e in json.loads(out)["errors"])


def test_cron_accepts_the_usual_lines():
    for line in ("30 6 * * 1-5", "15,45 8-17 * * *", "*/10 * * * *", "0 9 1 mar fri", "0 0 * * 0-7"):
        assert fr.cron_problem(line) is None, line
    assert "backwards" in fr.cron_problem("0 18-9 * * *")
    assert "bad step" in fr.cron_problem("*/0 * * * *")
    assert "is not a value" in fr.cron_problem("0 9 * smarch *")


def test_cron_reads_the_nth_weekday():
    assert fr.cron_problem("0 8 * * 2#1") is None
    assert fr.cron_problem("0 8 * * fri#3") is None
    assert "nth weekday" in fr.cron_problem("0 8 * * 2#7")
    assert "nth weekday" in fr.cron_problem("0 8 * * 8#1")
