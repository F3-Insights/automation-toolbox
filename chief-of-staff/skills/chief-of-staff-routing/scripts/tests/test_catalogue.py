"""The catalogue against an invented two-department toolbox and the real checkout."""

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import catalogue as cat  # noqa: E402


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def toolbox(tmp_path):
    root = tmp_path / "toolbox"
    write(root / "acme" / ".claude-plugin" / "plugin.json", json.dumps({"name": "acme", "description": "Acme books. Closes."}))
    write(root / "acme" / "agents" / "acme-close.md",
          '---\nname: acme-close\ndescription: "Runs the month-end close for one period."\n'
          'tools: ["Read", "Skill", "Agent"]\n---\n\nYou close.\n\n## Inputs\n\n- **Period**: yyyy-mm.\n\n## Done\n\nClosed.\n')
    write(root / "acme" / "agents" / "acme-worker.md", "---\nname: acme-worker\ndescription: One slice.\n---\n")
    write(root / "acme" / "agents" / "acme-reviewer.md", "---\nname: acme-reviewer\ndescription: Checks.\n---\n")
    write(root / "acme" / "skills" / "acme-close-method" / "SKILL.md",
          "---\nname: acme-close-method\ndescription: Reference loaded by acme-close, not for a user request.\n---\n")
    write(root / "acme" / "skills" / "journal-entry" / "SKILL.md",
          "---\nname: journal-entry\ndescription: Prepare one month-end journal entry.\n---\n")
    write(root / "acme" / "skills" / "shared-one" / "SKILL.md", "---\nname: shared-one\ndescription: Copied.\n---\n")
    write(root / "acme" / "skills" / "shared-one" / ".shared-copy", "source: shared/skills/shared-one\n")
    write(root / "acme" / "bin" / "acme-pull", "#!/bin/sh\n")
    write(root / "notes" / "agents" / "loose.md", "---\nname: loose\n---\n")  # not a plugin: left out
    write(root / "chief" / ".claude-plugin" / "plugin.json", json.dumps({"name": "chief", "description": "Front door."}))
    write(root / "chief" / "skills" / "routing" / "scripts" / "catalogue.py", "")
    return root


def test_departments_list_main_agents_owner_skills_and_commands(tmp_path):
    root = toolbox(tmp_path)
    autos = tmp_path / "automations"
    write(autos / "acme-close-march" / "sentinel.yaml", "title: Acme close\nagent: acme-close\n")
    write(autos / "other" / "sentinel.yaml", "title: Other\nagent: nobody\n")
    found = {d["department"]: d for d in cat.departments(root, cat.automations(autos))}
    assert set(found) == {"acme", "chief"}
    acme = found["acme"]
    main = [a for a in acme["agents"] if a["role"] == "main"]
    assert [a["name"] for a in main] == ["acme-close"]
    assert main[0]["inputs"] == "- **Period**: yyyy-mm."
    assert main[0]["start"].endswith("--agent acme:acme-close")
    assert main[0]["automations"] == [{"automation": "acme-close-march", "title": "Acme close"}]
    assert {a["name"]: a["role"] for a in acme["agents"]}["acme-reviewer"] == "reviewer"
    assert [s["name"] for s in acme["skills"]] == ["journal-entry"]
    assert acme["commands"] == ["acme-pull"]


def test_a_query_ranks_by_name_and_description(tmp_path):
    root = toolbox(tmp_path)
    ranked = cat.rank(cat.departments(root, {}), "close the month", 5)
    assert [r["name"] for r in ranked] == ["acme-close", "journal-entry"]
    assert cat.rank(cat.departments(root, {}), "the of", 5) == []


def test_the_real_checkout_lists_this_front_door(capsys):
    assert cat.main(["--department", "chief-of-staff", "--format", "json", "--automations-dir", "/nonexistent"]) == 0
    out = json.loads(capsys.readouterr().out)
    (dept,) = out["departments"]
    names = {a["name"] for a in dept["agents"] if a["role"] == "main"}
    assert {"chief-of-staff", "chief-of-staff-cycle-runner"} <= names
    assert "chief-of-staff-catalogue" in dept["commands"]
