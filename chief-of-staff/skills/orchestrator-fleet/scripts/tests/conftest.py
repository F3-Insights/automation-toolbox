"""A made-up fleet for Northwind Traders: a registry, agent files, an automations folder, a
settings file, a fake runner and a fake check command. Nothing here launches a real Run."""

import json
import os
import stat
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FAKE_RUNNER = """
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a") as log:
    log.write(json.dumps(args) + "\\n")
if args[0] == "runs":
    try:
        print(open(os.environ["FAKE_RUNS"]).read())
    except FileNotFoundError:
        print("runner: no trace to read", file=sys.stderr)
        sys.exit(1)
    sys.exit(0)
if args[0] == "launch":
    if os.environ.get("FAKE_REFUSE"):
        print("refused northwind-orders: daily limit")
        print("  the Automation's own limit is reached", file=sys.stderr)
        sys.exit(1)
    print("queued northwind-orders-20300308 (queue 4)")
    sys.exit(0)
sys.exit(3)
"""

FAKE_CHECK = """#!/bin/sh
echo "$@" > "$FAKE_CHECK_LOG"
echo "WORK: 3 purchase orders to review"
"""


def entry(name, **over):
    base = {"name": name, "plan": None, "domain": "northwind", "tier": "B", "status": "spec",
            "automation": None, "purpose": "Made-up work for Northwind Traders.",
            "triggers": {"manual": True}, "inputs": {}, "record": "the Northwind folder",
            "authority": "propose", "check": None, "outputs": ["a draft"], "replaces": [], "wave": 1,
            "value": "M"}
    base.update(over)
    return base


def now_iso(hours_ago=0):
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


class Fleet:
    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def launches(self):
        return [call for call in self.calls() if call[0] == "launch"]

    def save(self):
        self.registry.write_text(yaml.safe_dump(self.data, sort_keys=False))

    def set_settings(self, **fleet):
        lines = ["[orchestrator-fleet]"] + [f"{k} = {json.dumps(v)}" for k, v in fleet.items()]
        self.settings.write_text("\n".join(lines) + "\n")

    def runs(self, rows):
        self.runs_file.write_text(json.dumps(rows))


@pytest.fixture
def fleet(tmp_path, monkeypatch):
    f = Fleet()
    f.tmp = tmp_path
    f.agents = tmp_path / "agents"
    (f.agents / "northwind").mkdir(parents=True)
    f.autos = tmp_path / "automations"
    entries = [
        entry("northwind-close-orchestrator", status="dry-run-passed", automation="northwind-close",
              authority="dry-run-only", tier="A", inputs={"period": r"\d{4}-\d{2}"}),
        entry("northwind-orders-orchestrator", status="live", automation="northwind-orders",
              inputs={"customer": "[a-z-]+"}),
        entry("northwind-pricing-orchestrator", status="live", automation="northwind-pricing", authority="trusted"),
        entry("northwind-receiving-orchestrator", status="scheduled", automation="northwind-receiving",
              authority="trusted", check="northwind-check",
              triggers={"schedule": "15,45 8-17 * * 1-5", "tz": "America/Chicago",
                        "precheck": "northwind-check --precheck"}),
        entry("northwind-returns-orchestrator", check="northwind-check {customer}"),
    ]
    for e in entries:
        if e["status"] != "spec":
            (f.agents / "northwind" / f"{e['name']}.md").write_text(f"---\nname: {e['name']}\n---\n")
        if e["automation"]:
            (f.autos / e["automation"]).mkdir(parents=True)
    f.data = {"version": 1, "launch_cap_per_day": 3, "orchestrators": entries}
    f.registry = tmp_path / "fleet" / "REGISTRY.yaml"
    f.registry.parent.mkdir()
    f.save()

    runner = tmp_path / "runner.py"
    runner.write_text(FAKE_RUNNER)
    f.runs_file, f.log = tmp_path / "runs.json", tmp_path / "runner.log"
    f.runs_file.write_text("[]")
    f.settings = tmp_path / "settings.toml"
    f.base_settings = {
        "registry": str(f.registry), "agents_dir": str(f.agents), "automations_dir": str(f.autos),
        "runs_command": [sys.executable, str(runner), "runs"],
        "launch_command": [sys.executable, str(runner), "launch", "{automation_path}", "--source", "agent",
                           "--by", "{by}"],
        "reserved_params": ["task", "run_dir"],
    }
    f.set_settings(**f.base_settings)

    bindir = tmp_path / "bin"
    bindir.mkdir()
    check = bindir / "northwind-check"
    check.write_text(FAKE_CHECK)
    check.chmod(check.stat().st_mode | stat.S_IEXEC)

    monkeypatch.delenv("FAKE_REFUSE", raising=False)
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(f.settings))
    monkeypatch.setenv("FAKE_LOG", str(f.log))
    monkeypatch.setenv("FAKE_RUNS", str(f.runs_file))
    monkeypatch.setenv("FAKE_CHECK_LOG", str(tmp_path / "check.log"))
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    return f


@pytest.fixture
def cli(capsys):
    """Run a script's main() in-process: (exit code, stdout, stderr)."""
    def invoke(module, *argv):
        try:
            code = module.main(list(argv))
        except SystemExit as exc:
            code = exc.code
        out = capsys.readouterr()
        return code, out.out, out.err
    return invoke
