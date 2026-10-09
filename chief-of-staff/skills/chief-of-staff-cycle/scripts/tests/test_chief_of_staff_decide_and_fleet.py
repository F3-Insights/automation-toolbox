"""The decide check against the owner's doer registry, and the fleet snapshot and launch with
the other skills' scripts replaced by fakes."""

import json

import pytest

import _common as c
import chief_of_staff_cycle as cy
import chief_of_staff_decide_check as dc
import chief_of_staff_fleet as fl
from conftest import TASK

ENTRIES = [
    {"name": "acme-tasks-orchestrator", "domain": "acme", "status": "live", "authority": "propose",
     "automation": "acme-tasks", "triggers": {"cadence": "nightly"}, "inputs": {"window": "\\d{1,2}d"},
     "purpose": "Close done tasks."},
    {"name": "acme-plan-orchestrator", "domain": "acme", "status": "scheduled", "authority": "propose",
     "automation": "acme-plan", "triggers": {"schedule": "30 6 * * 1-5"}, "inputs": {}},
    {"name": "acme-review-orchestrator", "domain": "acme", "status": "built", "authority": "dry-run-only",
     "automation": "acme-review", "triggers": {}, "inputs": {}},
    {"name": "acme-replies-orchestrator", "domain": "acme", "status": "live", "authority": "trusted",
     "automation": "acme-replies", "triggers": {}, "inputs": {}},
    {"name": "acme-draft-orchestrator", "domain": "acme", "status": "spec", "authority": "propose",
     "automation": None, "triggers": {}, "inputs": {}},
    {"name": "chief-of-staff-cycle-orchestrator", "domain": "cos", "status": "live", "authority": "propose",
     "automation": "cos", "triggers": {}, "inputs": {}},
]


class Fakes:
    """Stands in for fleet_status.py, fleet_registry.py, fleet_launch.py and task_stack_check.py."""

    def __init__(self, today):
        self.calls, self.status_code, self.launch = [], 0, (0, {"action": "queued", "output": ["queued acme-tasks"]})
        self.rows = [{"name": "acme-tasks-orchestrator", "live": False, "queued": False,
                      "last_run": {"outcome": "failed", "when": f"{today} 01:00"}},
                     {"name": "acme-plan-orchestrator", "queued": True}]

    def __call__(self, argv, timeout=180):
        self.calls.append(argv)
        script = argv[1].rsplit("/", 1)[-1]
        if script == "fleet_status.py":
            return self.status_code, json.dumps({"orchestrators": self.rows, "runs_error": None}), "boom"
        if script == "fleet_registry.py":
            return 0, json.dumps(ENTRIES), ""
        if script == "task_stack_check.py":
            return 0, "WORK: 4 tasks look done\n", ""
        if script == "fleet_launch.py":
            code, answer = self.launch
            return code, json.dumps(answer), ""
        if script == "notify_owner.py":
            return 0, json.dumps({"sent": True, "channel": "teams"}), ""
        raise AssertionError(argv)


@pytest.fixture
def cycle(root, monkeypatch, owner):
    folder = cy.start(root, c.local_now().date().isoformat())["folder"]
    return c.Path(folder)


@pytest.fixture
def fakes(monkeypatch):
    f = Fakes(c.local_now().date().isoformat())
    monkeypatch.setattr(c, "run_script", f)
    return f


def switch_on(owner, tmp_path, extra=""):
    settings = tmp_path / "settings.toml"
    settings.write_text(settings.read_text().replace("[chief-of-staff-cycle]",
                                                     f"[chief-of-staff-cycle]\nfleet_launches = \"on\"\n{extra}"))


# --------------------------------------------------------------------------- the decide check

def decide(raw, fleet=None, max_dispatches=2):
    return dc.check(raw, c.load_doers(), max_dispatches, fleet)


def test_the_registry_is_the_execution_boundary():
    out = decide(json.dumps({"dispatches": [
        {"doer": "produce-work", "args": f"task:{TASK}"},
        {"doer": "relationship-check", "args": ""},
        {"doer": "made-up", "args": ""},
        {"doer": "meeting-prep", "args": "Fabrikam (review)"}]}))
    assert [a["doer"] for a in out["accepted"]] == ["produce-work"]
    reasons = {s["name"]: s["reason"] for s in out["skipped"]}
    assert reasons["relationship-check"].startswith("replaced")
    assert reasons["made-up"] == "not in the doer registry"
    assert "rejected by registry pattern" in reasons["meeting-prep"]


def test_no_registry_means_no_doer(tmp_path, owner):
    out = dc.check(json.dumps({"dispatches": [{"doer": "produce-work", "args": f"task:{TASK}"}]}),
                   c.load_doers(str(tmp_path / "none.toml")))
    assert not out["accepted"] and "could not be read" in out["skipped"][0]["reason"]


def test_the_cap_can_be_lowered_never_raised_and_defaults_fill_in():
    many = {"dispatches": [{"doer": "person-brief", "args": ""}, {"doer": "meeting-prep", "args": "Fabrikam"},
                           {"doer": "produce-work", "args": f"task:{TASK}"}]}
    out = decide(json.dumps(many), max_dispatches=9)
    assert len(out["accepted"]) == 2 and out["accepted"][0]["args"] == "next meeting"
    assert out["accepted"][0]["worker"] == "person-researcher" and out["accepted"][0]["route"] == "agent"
    assert len(decide(json.dumps(many), max_dispatches=1)["accepted"]) == 1


def test_produce_work_takes_only_an_entity_and_a_uuid():
    out = decide(json.dumps({"dispatches": [{"doer": "produce-work", "args": "task: the Northwind invoice"}]}))
    assert not out["accepted"]


def test_a_runner_envelope_a_fenced_reply_and_nothing_all_parse():
    inner = {"priorities": [{"item": "x"}], "dispatches": []}
    assert decide(json.dumps({"result": json.dumps(inner)}))["status"] == "ok"
    assert decide("Here it is:\n```json\n" + json.dumps(inner) + "\n```")["status"] == "ok"
    assert decide("no json at all")["status"] == "parse_failed"
    assert decide("  ")["status"] == "empty"


def test_the_improvement_surface_is_the_registry_skills_only():
    out = decide(json.dumps({"improvements": [
        {"target": "chief-of-staff-cycle/SKILL.md", "change": "x"},
        {"target": "sales/skills/bd-workstream/SKILL.md", "change": "x"},
        {"target": "productivity/skills/meeting-prep/SKILL.md", "change": "Add a line", "rationale": "it missed"}]}))
    assert out["improvement"] == {"target": "meeting-prep", "change": "Add a line", "rationale": "it missed"}
    assert len([s for s in out["skipped"] if "surface" in s["reason"]]) == 2


# --------------------------------------------------------------------------- the snapshot

def test_with_the_switch_off_the_fleet_is_read_and_nothing_can_launch(cycle, fakes):
    out = fl.snapshot(cycle)
    assert out["launches"] == "off" and out["launchable"] == []
    assert "acme-tasks-orchestrator" in out["would_be_launchable"]
    assert out["task_stack"]["precheck"].startswith("WORK")
    skipped = decide(json.dumps({"launches": [{"orchestrator": "acme-tasks-orchestrator", "trigger": "stall"}]}), out)
    assert not skipped["launches"] and "off" in skipped["skipped"][0]["reason"]


def test_which_orchestrators_the_cycle_may_launch_and_how(cycle, fakes, owner, tmp_path):
    switch_on(owner, tmp_path)
    out = fl.snapshot(cycle)
    modes = {r["name"]: r["mode"] for r in out["launchable"]}
    assert modes == {"acme-tasks-orchestrator": "live", "acme-review-orchestrator": "dry-run"}
    reasons = {r["name"]: r["reason"] for r in out["not_launchable"]}
    assert "queued" in reasons["acme-plan-orchestrator"] and "trusted" in reasons["acme-replies-orchestrator"]
    assert "never launched" in reasons["chief-of-staff-cycle-orchestrator"]
    assert "acme-draft-orchestrator" not in reasons


def test_a_fleet_status_that_cannot_run_is_reported_not_fatal(cycle, fakes):
    fakes.status_code = 2
    assert "exit 2" in fl.snapshot(cycle)["errors"][0]


def test_launches_are_checked_against_the_snapshot(cycle, fakes, owner, tmp_path):
    switch_on(owner, tmp_path)
    fleet = fl.snapshot(cycle)
    out = decide(json.dumps({"launches": [
        {"orchestrator": "acme-tasks-orchestrator", "trigger": "stall", "params": {"window": "3d"}},
        {"orchestrator": "acme-tasks-orchestrator", "trigger": "stall"},
        {"orchestrator": "acme-review-orchestrator", "trigger": "whim"},
        {"orchestrator": "acme-replies-orchestrator", "trigger": "event"}]}), fleet)
    assert [(a["orchestrator"], a["mode"]) for a in out["launches"]] == [("acme-tasks-orchestrator", "live")]
    reasons = [s["reason"] for s in out["skipped"]]
    assert any("already launched" in r for r in reasons) and any("off-schedule" in r for r in reasons)
    bad = decide(json.dumps({"launches": [{"orchestrator": "acme-tasks-orchestrator", "trigger": "stall",
                                           "params": {"dry_run": "false"}}]}), fleet)
    assert "not the decider's" in bad["skipped"][0]["reason"]


# --------------------------------------------------------------------------- the launch

def accept(cycle, fakes, owner, tmp_path, params=None, extra=""):
    switch_on(owner, tmp_path, extra)
    fleet = fl.snapshot(cycle)
    out = decide(json.dumps({"launches": [{"orchestrator": "acme-tasks-orchestrator", "trigger": "stall",
                                           "reason": "it failed overnight", "params": params or {}}]}), fleet)
    c.atomic_json(cycle / "decision.json", out)


def test_a_launch_runs_fleet_launch_at_propose_and_is_recorded(cycle, fakes, owner, tmp_path):
    accept(cycle, fakes, owner, tmp_path, {"window": "3d"})
    out, code = fl.launch(cycle, "acme-tasks-orchestrator")
    assert code == 0 and out["status"] == "launched"
    argv = fakes.calls[-1]
    assert argv[2:] == ["acme-tasks-orchestrator", "--authority", "propose", "--cap", "12", "--by",
                        "chief-of-staff-cycle-orchestrator", "--format", "json", "--params", "window=3d"]
    row = c.read_json(cycle / "execution.json")[-1]
    assert row["doer"] == "launch:acme-tasks-orchestrator" and row["status"] == "launched"
    assert fl.launch(cycle, "acme-tasks-orchestrator")[0]["status"] == "refused"


def test_a_launch_the_check_did_not_accept_is_refused_and_runs_nothing(cycle, fakes, owner, tmp_path):
    accept(cycle, fakes, owner, tmp_path)
    before = len(fakes.calls)
    assert fl.launch(cycle, "acme-review-orchestrator")[0]["status"] == "refused"
    assert len(fakes.calls) == before


def test_fleet_launch_refusing_is_recorded_and_the_backstop_tells_the_owner(cycle, fakes, owner, tmp_path):
    accept(cycle, fakes, owner, tmp_path)
    fakes.launch = (1, {"action": "refused", "reason": "daily cap reached: 12 launches today, cap 12"})
    out, code = fl.launch(cycle, "acme-tasks-orchestrator")
    assert code == 3 and out["reason"] == "daily backstop reached" and out["owner_told"] == "sent"


def test_the_backstop_counts_earlier_cycles_launches(cycle, fakes, owner, tmp_path):
    accept(cycle, fakes, owner, tmp_path, extra="launch_backstop = 1")
    other = cycle.parent / "050000"
    other.mkdir()
    c.atomic_json(other / "execution.json", [{"doer": "launch:x", "status": "launched"}])
    out, _ = fl.launch(cycle, "acme-tasks-orchestrator")
    assert out["reason"] == "daily backstop reached"
    assert not any(a[1].endswith("fleet_launch.py") for a in fakes.calls)


def test_a_dry_run_cycle_launches_nothing(root, fakes, owner, tmp_path):
    folder = c.Path(cy.start(root, c.local_now().date().isoformat(), dry_run=True)["folder"])
    accept(folder, fakes, owner, tmp_path)
    out, code = fl.launch(folder, "acme-tasks-orchestrator")
    assert out["status"] == "would_launch" and code == 0
    assert not any(a[1].endswith("fleet_launch.py") for a in fakes.calls)


def test_launch_rechecks_params_against_the_registry(cycle, fakes, owner, tmp_path):
    accept(cycle, fakes, owner, tmp_path, {"window": "3d"})
    decision = c.read_json(cycle / "decision.json")
    decision["launches"][0]["params"] = {"window": "999 days"}
    c.atomic_json(cycle / "decision.json", decision)
    out, code = fl.launch(cycle, "acme-tasks-orchestrator")
    assert code == 3 and "does not match" in out["reason"]


def test_launch_refuses_when_the_switch_is_turned_off_after_the_check(cycle, fakes, owner, tmp_path):
    accept(cycle, fakes, owner, tmp_path)
    settings = tmp_path / "settings.toml"
    settings.write_text(settings.read_text().replace('fleet_launches = "on"\n', ""))
    out, code = fl.launch(cycle, "acme-tasks-orchestrator")
    assert code == 3 and out["reason"] == "fleet launches are off"
    assert not any(a[1].endswith("fleet_launch.py") for a in fakes.calls)


def test_the_switch_reads_off_unless_it_says_on(owner, tmp_path):
    settings = tmp_path / "settings.toml"
    base = settings.read_text()
    for value, expected in (('"yes"', "off"), ("true", "off"), ('"enabled"', "off"), ('"ON "', "on")):
        settings.write_text(base.replace("[chief-of-staff-cycle]", f"[chief-of-staff-cycle]\nfleet_launches = {value}"))
        assert fl.launch_switch() == expected
    settings.write_text(base)
    assert fl.launch_switch() == "off"


# --------------------------------------------------------------------------- what the cycle may reach

def test_the_cycle_scripts_reach_only_known_tools_and_commands():
    """The cycle's scripts call no Portal tool beyond reads and the receipt's note and task
    writes, run nothing through a shell, and run only the named scripts of other skills; the
    one message path is comms-reply-to-email's owner-only script."""
    import re
    allowed = {"whoami", "get", "search", "list_entities", "briefing", "create_note", "update_note", "create_task"}
    for path in sorted(c.SKILL_DIR.glob("scripts/*.py")):
        text = path.read_text()
        used = set(re.findall(r'\.call\("([a-z_]+)"', text))
        assert used <= allowed, (path.name, used - allowed)
        assert "shell=True" not in text and "os.system" not in text and "Popen" not in text, path.name
    named = {p.name for p in (c.NOTIFY_SCRIPT, fl.FLEET_STATUS, fl.FLEET_REGISTRY,
                              fl.FLEET_LAUNCH, fl.TASK_STACK_CHECK)}
    assert named == {"notify_owner.py", "fleet_status.py", "fleet_registry.py",
                     "fleet_launch.py", "task_stack_check.py"}
    assert c.NOTIFY_SCRIPT.parent.parent.name == "comms-reply-to-email"
