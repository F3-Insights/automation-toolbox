"""The toolbox audit's scripts against a made-up toolbox: Acme Components' widget-review department,
in a temporary folder and a temporary git repository. Nothing here comes from a real toolbox."""

import json
import subprocess
import sys
import textwrap
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import _common as c  # noqa: E402
import toolbox_audit_check as chk  # noqa: E402
import toolbox_audit_fix as fx  # noqa: E402
import toolbox_audit_record as rec  # noqa: E402
import toolbox_audit_scan as sc  # noqa: E402

GOOD = "Runs the Acme widget review each week and records a verdict per lot. Use when a lot needs a verdict."
CHECK_STUB = '''
"""A stand-in for the toolbox check."""
import sys
DEPARTMENTS = ["widgets"]
print("widgets/skills/widget-method/SKILL.md:7: private name: Dana")
print("widgets/skills/widget-method/SKILL.md:9: private name: Dana")
print("widgets/agents/widget-inspector.md: quote the description, it contains ': '")
print("0 problem(s)", file=sys.stderr)
sys.exit(1)
'''


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")
    return path


def agent(root, name, description, extra="", body="Do the work.\n"):
    return write(root / "widgets" / "agents" / f"{name}.md",
                 f"---\nname: {name}\ndescription: {description}\nmodel: opus\n{extra}---\n\n{body}")


@pytest.fixture
def toolbox(tmp_path, monkeypatch):
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "none.toml"))
    monkeypatch.setenv("F3I_TOOLBOX_DENYLIST", "")
    monkeypatch.setattr(c, "DEFAULT_DENYLIST", tmp_path / "no-denylist.txt")
    root = tmp_path / "toolbox"
    write(root / "scripts" / "toolbox_check.py", CHECK_STUB)
    agent(root, "widget-review-orchestrator", GOOD, extra="skills: [widget-method, missing-method]\n",
          body="| Agent | Owns |\n|---|---|\n| `widget-inspector` | lots |\n\nRun `python3 ~/.claude/skills/widget-method/scripts/gone.py`.\n")
    agent(root, "widget-inspector", "Inspects lots: one verdict each, from the register pull.", extra="skills: [widget-method]\n")
    agent(root, "widget-reviewer", "x" * 720)
    write(root / "widgets" / "skills" / "widget-method" / "SKILL.md",
          "---\nname: widget-method\ndescription: How a widget lot is judged and recorded.\n---\n\nRun `python3 ~/.claude/skills/widget-method/scripts/lot_count.py`.\n")
    write(root / "widgets" / "skills" / "widget-method" / "scripts" / "lot_count.py",
          '"""Count lots."""\nimport argparse\nargparse.ArgumentParser().parse_args()\nimport os\nos.environ.get("WIDGET_TOKEN")\n')
    write(root / "widgets" / "skills" / "widget-method" / "scripts" / "lot-label.py", "import yaml\n")
    write(root / "widgets" / "skills" / "widget-method" / "scripts" / "tests" / "test_lot.py",
          "# runs lot-label.py\n# fixture: python3 ~/.claude/skills/nowhere/scripts/x.py\n")
    write(root / "widgets" / "skills" / "widget-forgotten" / "SKILL.md",
          "---\nname: widget-forgotten\ndescription: A method nothing calls any more.\n---\n\nBody.\n")
    write(root / "widgets" / "tools" / "stray.py", '"""Stray."""\n')
    write(root / "widgets" / "README.md", "# Widgets\n\n| Agent | What |\n|---|---|\n| `widget-review-orchestrator` | x |\n| `widget-retired` | y |\n")
    write(root / "docs" / "settings.md", "# Owner settings\n")
    return root


def keys(result, section="", kind=""):
    return {i["key"] for i in result["items"] if (not section or i["section"] == section) and (not kind or i["kind"] == kind)}


def test_scan_reuses_the_toolbox_check_and_never_copies_a_private_name(toolbox):
    result = sc.scan(toolbox, run_help=False)
    guards = [i for i in result["items"] if i["section"] == "guards"]
    assert [i["key"] for i in guards] == ["guards:private-name:widgets/skills/widget-method/SKILL.md"]
    assert "2 hit(s)" in guards[0]["text"]
    assert "Dana" not in json.dumps(result)
    assert any(i["section"] == "check" and "widget-inspector" in i["where"] for i in result["items"])  # structure, not a guard


def test_scan_finds_lints_drift_and_script_rule_gaps(toolbox):
    result = sc.scan(toolbox, run_help=False)
    assert "lint:description:widgets/agents/widget-reviewer.md" in keys(result, "lint")
    drift = keys(result, "drift")
    assert "drift:skills:widget-review-orchestrator:missing-method" in drift
    assert any("widget-method/gone.py" in k for k in drift)
    assert "drift:readme-missing:widgets:widget-inspector" in drift
    assert "drift:readme-stale:widgets:widget-retired" in drift
    assert "drift:env:widgets/skills/widget-method/scripts/lot_count.py:WIDGET_TOKEN" in drift
    scripts = keys(result, "scripts")
    assert "scripts:placement:widgets/tools/stray.py" in scripts
    assert "scripts:name:widgets/skills/widget-method/scripts/lot-label.py" in scripts
    assert "scripts:dependencies:widgets/skills/widget-method/scripts/lot-label.py" in scripts
    assert "scripts:tests:widgets/skills/widget-method/scripts/lot_count.py" in scripts
    assert "scripts:tests:widgets/skills/widget-method/scripts/lot-label.py" not in scripts
    assert not any("nowhere" in k for k in drift)
    assert "unused:skill:widget-forgotten" in keys(result, "unused")
    assert result["teams"]["widget-review-orchestrator"]["workers"][0]["agent"] == "widget-inspector"
    assert all(v["ok"] for v in result["sections"].values())


def test_scan_runs_help_under_plain_python(toolbox):
    write(toolbox / "widgets" / "skills" / "widget-method" / "scripts" / "broken.py", '"""Broken."""\nraise SystemExit(3)\n')
    result = sc.scan(toolbox, run_help=True)
    assert "scripts:help:widgets/skills/widget-method/scripts/broken.py" in keys(result, "scripts", "help")
    assert "scripts:help:widgets/skills/widget-method/scripts/lot_count.py" not in keys(result, "scripts", "help")


STAGE = "- **Goal.** g\n- **Who.** w\n- **Move on when** m\n"
ORCHESTRATOR_BODY = ("You own the widget review.\n\n## Goal\n\ng\n\n## Inputs\n\ni\n\n## Context\n\nc\n\n## Approach\n\n"
                     + "".join(f"### {s}\n\n{STAGE}\n" for s in sc.STAGES)
                     + "## Team\n\n| Sub-agent | Given |\n|---|---|\n| `widget-inspector` | lots |\n\n"
                     "## Boundaries\n\nb\n\n## Done when\n\nd\n\n## Output\n\no\n")
SUB_AGENT_BODY = ("You own each lot's verdict.\n\n## Goal\n\ng\n\n## Inputs\n\ni\n\n## Context\n\nc\n\n"
                   "## Approach\n\n- Judge each lot on the rules.\n\n## Boundaries\n\nb\n\n## Done when\n\nd\n\n"
                   "## Output\n\n```\n## Step 1\n## Step 2\n```\n\n## Notes\n\nAn extra section after the standard is fine.\n")


def problems(name, body):
    return dict(sc.template_problems(name, f"---\nname: {name}\ndescription: d\n---\n\n{body}"))


def test_an_agent_on_the_template_has_no_template_problem():
    assert problems("widget-review-orchestrator", ORCHESTRATOR_BODY) == {}
    assert problems("widget-inspector", SUB_AGENT_BODY) == {}   # a fenced "## Step 1" is not structure


def test_a_missing_or_out_of_order_section_is_reported():
    got = problems("widget-inspector", SUB_AGENT_BODY.replace("## Context\n\nc\n\n", ""))
    assert got == {"template-sections": "missing ## Context"}
    swapped = SUB_AGENT_BODY.replace("## Goal\n\ng\n\n## Inputs\n\ni\n", "## Inputs\n\ni\n\n## Goal\n\ng\n")
    assert "out of order (Inputs, Goal, Context" in problems("widget-inspector", swapped)["template-sections"]
    late_team = ORCHESTRATOR_BODY.replace("## Team\n", "## Later\n").replace("## Output\n\no\n", "## Output\n\no\n\n## Team\n\nt\n")
    assert "out of order" in problems("widget-review-orchestrator", late_team)["template-sections"]


def test_an_orchestrator_needs_its_team_and_the_five_stages():
    got = problems("widget-review-orchestrator", ORCHESTRATOR_BODY.replace("## Team\n", "## Your team\n"))
    assert got == {"template-team": "an orchestrator with no ## Team section"}
    got = problems("widget-review-orchestrator", ORCHESTRATOR_BODY.replace("### C. Build", "### C. Do the work"))
    assert got["template-stages"].endswith("missing ### C. Build")
    swapped = ORCHESTRATOR_BODY.replace("### A. Gather", "### X").replace("### B. Plan & clarify", "### A. Gather").replace("### X", "### B. Plan & clarify")
    assert "out of order" in problems("widget-review-orchestrator", swapped)["template-stages"]
    thin = ORCHESTRATOR_BODY.replace("### D. Test & review\n\n" + STAGE, "### D. Test & review\n\n- **Goal.** g\n")
    assert problems("widget-review-orchestrator", thin)["template-stages"].endswith("D. Test & review (no Who, Move on when)")
    no_approach = problems("widget-review-orchestrator", "## Goal\n\n## Steps\n\n1. Do it.\n")
    assert set(no_approach) == {"template-sections", "template-team", "template-stages"}


@pytest.mark.parametrize("structure,flagged", [
    ("## Step 1: read\n\n## Step 2: judge\n", True),
    ("### 1. Read\n\n### 2. Judge\n", True),
    ("## Steps\n\n1. Read.\n2. Judge.\n", True),
    ("### 1. Read\n", False),
    ("- 1. Read\n- 2. Judge\n", False),
])
def test_a_sub_agent_written_as_a_step_script_is_reported(structure, flagged):
    body = SUB_AGENT_BODY.replace("- Judge each lot on the rules.\n", structure)
    assert ("template-steps" in problems("widget-inspector", body)) is flagged


def test_scan_reports_template_drift_per_agent_and_per_department(toolbox):
    write(toolbox / "widgets" / "agents" / "widget-checker.md", f"---\nname: widget-checker\ndescription: {GOOD}\n---\n\n{SUB_AGENT_BODY}")
    result = sc.scan(toolbox, run_help=False)
    template = [i for i in result["items"] if i["kind"].startswith("template-")]
    assert {i["level"] for i in template} == {"warning"} and {i["section"] for i in template} == {"lint"}
    assert "lint:template-team:widgets/agents/widget-review-orchestrator.md" in keys(result, "lint")
    assert "lint:template-sections:widgets/agents/widget-inspector.md" in keys(result, "lint")
    assert not any("widget-checker" in i["where"] for i in template)
    assert result["template"] == {"widgets": {"pattern": "agent-file", "agents": 4, "flagged": 3}}


def test_scan_without_a_repo_setting_says_which_setting(toolbox, capsys):
    assert sc.main([]) == 2
    assert "[toolbox-audit-workstream]" in capsys.readouterr().err


def test_the_fix_rule_allows_a_shorter_description_and_nothing_else():
    old = "---\nname: widget-reviewer\ndescription: " + "x" * 720 + "\nmodel: opus\n---\n\nBody.\n"
    good = "---\nname: widget-reviewer\ndescription: Reviews a widget lot. Use when a lot is done.\nmodel: opus\n---\n\nBody.\n"
    assert c.check_file("widgets/agents/widget-reviewer.md", old, good, []) == []
    bad = good.replace("model: opus", "model: fable").replace("Body.", "Other body.")
    problems = c.check_file("widgets/agents/widget-reviewer.md", old, bad, [])
    assert any("body changed" in p for p in problems) and any("'model' changed" in p for p in problems)
    assert c.check_file("widgets/README.md", old, good, [])[0].endswith("SKILL.md)")


def test_the_fix_rule_refuses_a_private_name_from_the_denylist(tmp_path, monkeypatch):
    deny = write(tmp_path / "deny.txt", "# private\n=Priya\n")
    monkeypatch.setenv("F3I_TOOLBOX_DENYLIST", str(deny))
    monkeypatch.setattr(c, "DEFAULT_DENYLIST", tmp_path / "absent.txt")
    old = "---\nname: widget-reviewer\ndescription: Reviews lots.\n---\nBody.\n"
    new = "---\nname: widget-reviewer\ndescription: Reviews lots for Priya.\n---\nBody.\n"
    assert any("private name" in p for p in c.check_file("widgets/agents/widget-reviewer.md", old, new, c.load_denylist()))


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


@pytest.fixture
def repo(toolbox, tmp_path):
    git(toolbox, "init", "-q", "-b", "main")
    git(toolbox, "-c", "user.email=dana@example.com", "-c", "user.name=Dana", "add", "-A")
    git(toolbox, "-c", "user.email=dana@example.com", "-c", "user.name=Dana", "commit", "-q", "-m", "start")
    run = tmp_path / "runs" / "r1"
    run.mkdir(parents=True)
    write(toolbox / "scripts" / "toolbox_check.py", "import sys\nsys.exit(0)\n")
    git(toolbox, "-c", "user.email=dana@example.com", "-c", "user.name=Dana", "commit", "-qam", "quiet check")
    return toolbox, run


def shorten(worktree):
    path = worktree / "widgets" / "agents" / "widget-reviewer.md"
    path.write_text(path.read_text().replace("x" * 720, "Reviews a widget lot. Use when a lot is done."))


def findings(run, state="fixed", review="PASS"):
    c.write_json(run / "findings.json", {"findings": [
        {"id": "lint:description:widgets/agents/widget-reviewer.md", "rank": 1, "section": "lint", "level": "error",
         "title": "widget-reviewer's description is too long", "evidence": ["scan.json"], "fix": "Shorten it",
         "state": state, "files": ["widgets/agents/widget-reviewer.md"], "review": review}]})


def test_open_refuses_a_run_folder_inside_the_live_checkout(repo):
    root, _ = repo
    inside = root / "runs-here"
    inside.mkdir()
    with pytest.raises(c.AuditError, match="inside the repository"):
        fx.open_worktree(inside, root)


def test_commit_commits_a_passing_fix_on_its_branch_and_never_on_main(repo, monkeypatch):
    root, run = repo
    monkeypatch.setattr(c, "DEFAULT_DENYLIST", run / "absent.txt")
    info = fx.open_worktree(run, root, today="2026-10-05")
    assert info["branch"] == "toolbox-audit/fixes-2026-10-05" and fx.open_worktree(run, root)["reused"]
    worktree = Path(info["worktree"])
    shorten(worktree)
    findings(run)
    result = fx.commit(run, dry_run=False)
    assert result["committed"], result
    assert git(root, "log", "-1", "--format=%s", "main").strip() == "quiet check"
    assert "widget-reviewer.md" in git(root, "show", "--name-only", "--format=", info["branch"])
    assert not worktree.exists()


def test_commit_refuses_a_change_outside_the_rule_and_leaves_the_worktree(repo, monkeypatch):
    root, run = repo
    monkeypatch.setattr(c, "DEFAULT_DENYLIST", run / "absent.txt")
    worktree = Path(fx.open_worktree(run, root)["worktree"])
    (worktree / "widgets" / "README.md").write_text("changed\n")
    findings(run)
    result = fx.commit(run, dry_run=False)
    assert result["state"] == "refused" and worktree.exists()


def test_the_fix_rule_never_edits_a_copied_skill(repo, monkeypatch):
    root, run = repo
    monkeypatch.setattr(c, "DEFAULT_DENYLIST", run / "absent.txt")
    write(root / "widgets" / "skills" / "acme-conduct" / "SKILL.md", "---\nname: acme-conduct\ndescription: " + "y" * 720 + "\n---\n\nBody.\n")
    write(root / "widgets" / "skills" / "acme-conduct" / ".shared-copy", "Copied from shared/skills/acme-conduct.\n")
    git(root, "add", "-A")
    git(root, "-c", "user.email=dana@example.com", "-c", "user.name=Dana", "commit", "-qm", "a copy")
    worktree = Path(fx.open_worktree(run, root)["worktree"])
    skill = worktree / "widgets" / "skills" / "acme-conduct" / "SKILL.md"
    skill.write_text(skill.read_text().replace("y" * 720, "How every Acme agent behaves."))
    _, problems = c.verify_fix(run, worktree, [])
    assert any("a copied skill" in p and "shared/skills/" in p for p in problems)


def test_commit_with_nothing_changed_removes_the_worktree_and_branch(repo):
    root, run = repo
    info = fx.open_worktree(run, root)
    assert fx.commit(run, dry_run=False)["state"] == "nothing"
    assert info["branch"] not in git(root, "branch")


def test_check_run_computes_the_three_tests(repo, monkeypatch):
    root, run = repo
    monkeypatch.setattr(c, "DEFAULT_DENYLIST", run / "absent.txt")
    c.write_json(run / "scan.json", {"items": [{"key": "lint:description:widgets/agents/widget-reviewer.md", "level": "error"},
                                               {"key": "scripts:tests:x", "level": "warning"}]})
    fx.open_worktree(run, root)
    shorten(run / "toolbox")
    findings(run, review="")
    result = chk.check_run(run)
    assert not result["tests"]["covered"]["met"]
    assert result["tests"]["one-fix"]["met"]
    assert any("checker's PASS" in g for g in result["tests"]["fix-rule"]["gaps"])


def test_record_keeps_the_ledger_week_over_week_and_files_tasks_once(tmp_path):
    run, folder = tmp_path / "r1", tmp_path / "audit"
    run.mkdir()
    c.write_json(run / "scan.json", {"counts": {"agents": 3}, "sections": {"lint": {"ok": True}}})
    c.write_json(run / "findings.json", {"findings": [
        {"id": "lint:a", "rank": 1, "section": "lint", "level": "error", "title": "A is wrong", "evidence": ["x"],
         "fix": "Fix A", "state": "task", "task_title": "Fix the A lint"},
        {"id": "lint:b", "rank": 2, "section": "lint", "level": "warning", "title": "B", "evidence": ["y"], "fix": "Fix B",
         "state": "proposed"}]})
    assert rec.record(run, folder, dry_run=False, task_domain="00000000-0000-0000-0000-000000000000")["recorded"]
    changes = json.loads((run / "changes.json").read_text())
    assert changes["orchestrator"] == "toolbox-maintenance-auditor"  # the task-stack writer maps it to the old name's markers
    ops = changes["ops"]
    assert ops[0]["source"] == "toolbox-audit:lint:a" and ops[0]["title"] == "Fix the A lint"
    run2 = tmp_path / "r2"
    run2.mkdir()
    c.write_json(run2 / "scan.json", {"sections": {"lint": {"ok": True}}})
    c.write_json(run2 / "findings.json", {"findings": [
        {"id": "lint:a", "rank": 1, "section": "lint", "level": "error", "title": "A", "evidence": ["x"], "fix": "Fix A",
         "state": "proposed"}]})
    rec.record(run2, folder, dry_run=False)
    rows = rec.read_ledger(folder)
    assert rows["lint:a"]["runs_seen"] == "2" and rows["lint:b"]["state"] == "resolved"
    assert "open since" in (run2 / "REPORT.md").read_text()
    assert chk.due(folder, date.today(), 6).startswith("NOTHING")
    assert chk.due(folder, date.today() + timedelta(days=7), 6).startswith("WORK")


def test_record_in_a_dry_run_writes_only_the_runs_report(tmp_path):
    run, folder = tmp_path / "r1", tmp_path / "audit"
    run.mkdir()
    c.write_json(run / "findings.json", {"findings": []})
    assert rec.record(run, folder, dry_run=True)["line"].startswith("WOULD RECORD")
    assert (run / "REPORT.md").exists() and not folder.exists()


def live_state(root):
    """The live checkout's branch, head commit and working-tree status."""
    return (git(root, "symbolic-ref", "--short", "HEAD").strip(), git(root, "rev-parse", "HEAD").strip(),
            git(root, "status", "--porcelain"))


def test_a_committed_fix_leaves_the_live_checkout_alone_and_merges_nowhere(repo, monkeypatch):
    root, run = repo
    monkeypatch.setattr(c, "DEFAULT_DENYLIST", run / "absent.txt")
    (root / "widgets" / "README.md").write_text("an edit the owner is making\n")
    before = live_state(root)
    info = fx.open_worktree(run, root, today="2026-10-05")
    shorten(Path(info["worktree"]))
    findings(run)
    assert fx.commit(run, dry_run=False)["committed"]
    assert live_state(root) == before
    assert git(root, "branch", "--contains", info["branch"]).split() == [info["branch"]]


def test_open_refuses_a_run_folder_inside_a_linked_worktree(repo, tmp_path):
    root, _ = repo
    other = tmp_path / "side-tree"
    git(root, "worktree", "add", "-q", "-b", "side", str(other))
    inside = other / "run"
    inside.mkdir()
    with pytest.raises(c.AuditError, match="inside the repository"):
        fx.open_worktree(inside, root)


def test_a_tampered_fix_branch_file_never_reaches_the_live_checkout(repo, monkeypatch):
    root, run = repo
    monkeypatch.setattr(c, "DEFAULT_DENYLIST", run / "absent.txt")
    info = fx.open_worktree(run, root)
    shorten(root)  # the same edit, but in the live checkout
    findings(run)
    for bad in ({**info, "worktree": str(root), "branch": "main"}, {**info, "branch": "main"},
                {**info, "worktree": str(root)}):
        c.write_json(run / "fix-branch.json", bad)
        with pytest.raises(c.AuditError, match="nothing done"):
            fx.commit(run, dry_run=False)
        with pytest.raises(c.AuditError, match="nothing done"):
            fx.worktree_info(run)
    assert "main" in git(root, "branch") and git(root, "log", "-1", "--format=%s", "main").strip() == "quiet check"
    assert "widgets/agents/widget-reviewer.md" in git(root, "status", "--porcelain")  # left as it was, uncommitted
    assert Path(info["worktree"]).exists()


def test_commit_needs_the_toolbox_check_and_the_checkers_pass(repo, monkeypatch):
    root, run = repo
    monkeypatch.setattr(c, "DEFAULT_DENYLIST", run / "absent.txt")
    info = fx.open_worktree(run, root)
    worktree = Path(info["worktree"])
    shorten(worktree)
    findings(run, review="")
    result = fx.commit(run, dry_run=False)
    assert result["state"] == "refused" and "checker's PASS" in result["problems"][0]
    findings(run)
    ok, why = fx.toolbox_check(worktree.parent, ["widgets/agents/widget-reviewer.md"])  # a folder with no check script
    assert not ok and "nothing is committed" in why
    monkeypatch.setattr(fx, "toolbox_check", lambda wt, files: (False, "widgets/agents/widget-reviewer.md:3: private name: Dana"))
    monkeypatch.setenv("F3I_TOOLBOX_DENYLIST", str(write(run.parent / "deny.txt", "=Dana\n")))
    result = fx.commit(run, dry_run=False)
    assert result["state"] == "refused" and "private name: (withheld)" in result["problems"][0]
    assert "Dana" not in json.dumps(result)
    assert git(root, "log", "-1", "--format=%s", info["branch"]).strip() == "quiet check"


def test_commit_refuses_a_private_name_in_its_message_and_never_prints_it(repo, monkeypatch, tmp_path):
    root, run = repo
    deny = write(tmp_path / "deny.txt", "Fabrikam\n")
    monkeypatch.setenv("F3I_TOOLBOX_DENYLIST", str(deny))
    info = fx.open_worktree(run, root)
    shorten(Path(info["worktree"]))
    findings(run)
    data = c.read_json(run / "findings.json")
    data["findings"][0]["title"] = "widget-reviewer's description is too long for Fabrikam"
    c.write_json(run / "findings.json", data)
    result = fx.commit(run, dry_run=False)
    assert result["state"] == "refused" and "commit message" in result["problems"][0]
    assert "Fabrikam" not in json.dumps(result)


def test_the_scan_withholds_a_private_name_in_a_file_path(toolbox, tmp_path, monkeypatch):
    deny = write(tmp_path / "deny.txt", "Fabrikam\n")
    monkeypatch.setenv("F3I_TOOLBOX_DENYLIST", str(deny))
    agent(toolbox, "widget-fabrikam-helper", "Helps.")
    result = sc.scan(toolbox, run_help=False)
    stored = json.dumps({k: v for k, v in result.items() if k != "root"})
    assert "fabrikam" not in stored.lower() and "(withheld)" in stored


# --- the plugin pattern: a department with .claude-plugin/plugin.json -------------------------

GADGET_STEPS = """## Steps

1. [script] Pull the lots: `gadgets-lot-pull --week W`.
   → nothing to inspect: done
2. [hand-off: gadgets-worker] Inspect each lot (section Inspect one lot).
3. [hand-off: gadgets-reviewer] Check every verdict (section Check the verdicts).
   → FAIL: step 2 (max 1)
4. [judgment] Write the week's note.
   → written: done
"""
MAIN_BODY = """You run one week's gadget inspection for Acme Components.

Before anything else, load your skills with the Skill tool.

## Goal

Every lot has one checked verdict.

## Inputs

- The week.

## How to work

Follow `gadget-inspection-method`, section Steps: `gadgets-worker` per lot, `gadgets-reviewer` on every verdict.

## Done

The week's note is written.

## Never

- Write to the register.
"""
REVIEWER_BODY = "You judge work you did not make.\n\n## Goal\n\ng\n\n## Inputs\n\ni\n\n## Never\n\n- Edit.\n\n## Done\n\nd\n"
WRAPPER = '#!/bin/sh\n# Generated by scripts/build_bins.py; do not edit.\nexec python3 "$root/skills/{skill}/scripts/{script}" "$@"\n'


def plugin_agent(root, name, description, tools, extra="", body=MAIN_BODY, dept="gadgets"):
    return write(root / dept / "agents" / f"{name}.md",
                 f"---\nname: {name}\ndescription: {description}\nmodel: opus\n{extra}tools: {json.dumps(tools)}\n---\n\n{body}")


def make_plugin(toolbox):
    """The gadgets department of Acme Components converted to the plugin pattern, beside the
    unconverted widgets department, with a shared skill copied into it."""
    check = toolbox / "scripts" / "toolbox_check.py"
    check.write_text(check.read_text().replace('DEPARTMENTS = ["widgets"]', 'DEPARTMENTS = ["widgets", "gadgets"]'))
    write(toolbox / "gadgets" / ".claude-plugin" / "plugin.json", '{"name": "gadgets", "description": "d", "version": "0.1.0"}\n')
    plugin_agent(toolbox, "gadget-inspection", "Runs the weekly gadget inspection.",
                 ["Read", "Write", "Skill", "Agent", "Bash(gadgets-lot-pull:*)"],
                 extra="skills: [acme-conduct, gadget-inspection-method]\n")
    plugin_agent(toolbox, "gadgets-reviewer", "Judges gadget work it did not make.", ["Read", "Glob", "Skill"],
                 extra='disallowedTools: ["Write", "Edit"]\n', body=REVIEWER_BODY)
    plugin_agent(toolbox, "gadgets-worker", "Does one slice of a gadget job.", ["Read", "Write", "Skill"],
                 extra="skills: [acme-conduct]\n", body="You do one slice.\n")
    write(toolbox / "gadgets" / "skills" / "gadget-inspection-method" / "SKILL.md",
          "---\nname: gadget-inspection-method\ndescription: How a gadget lot is inspected.\n---\n\n"
          f"{GADGET_STEPS}\n## Inspect one lot\n\nRun `gadgets-lot-pull` first.\n")
    write(toolbox / "gadgets" / "skills" / "gadget-inspection-method" / "scripts" / "lot_pull.py", '"""Pull lots."""\n')
    write(toolbox / "gadgets" / "skills" / "gadget-inspection-method" / "scripts" / "tests" / "test_pull.py", "# lot_pull\n")
    write(toolbox / "gadgets" / "bin" / "gadgets-lot-pull", WRAPPER.format(skill="gadget-inspection-method", script="lot_pull.py"))
    conduct = "---\nname: acme-conduct\ndescription: How every Acme agent behaves.\n---\n\nAsk rather than guess.\n"
    write(toolbox / "shared" / "skills" / "acme-conduct" / "SKILL.md", conduct)
    write(toolbox / "gadgets" / "skills" / "acme-conduct" / "SKILL.md", conduct)
    write(toolbox / "gadgets" / "skills" / "acme-conduct" / ".shared-copy",
          "Generated by scripts/build_shared.py from shared/skills/acme-conduct; do not edit.\n")
    write(toolbox / "gadgets" / "README.md", "# Gadgets\n\n| Piece | What |\n|---|---|\n| `gadget-inspection` | x |\n"
          "| `gadgets-reviewer` | x |\n| `gadgets-worker` | x |\n| `gadget-inspection-method` | x |\n| `gadgets-lot-pull` | x |\n")
    return toolbox


@pytest.fixture
def plugin(toolbox):
    return make_plugin(toolbox)


def gadget_items(result):
    return [i for i in result["items"] if i["where"].startswith("gadgets") and i["section"] not in ("check", "guards")]


def test_a_department_on_the_plugin_pattern_is_clean_and_the_old_one_is_judged_as_before(toolbox):
    before = {i["key"] for i in sc.scan(toolbox, run_help=False)["items"]}
    plugin_toolbox = make_plugin(toolbox)
    result = sc.scan(plugin_toolbox, run_help=False)
    assert gadget_items(result) == []
    assert not any(i["kind"].startswith("template-") and "gadgets" in i["where"] for i in result["items"])
    widgets = {k for k in (i["key"] for i in result["items"]) if "gadget" not in k and "shared" not in k}
    assert widgets == before  # the unconverted department is judged by the agent file standard, unchanged
    assert result["template"]["gadgets"] == {"pattern": "plugin", "agents": 3, "flagged": 0}
    assert result["template"]["widgets"]["pattern"] == "agent-file"
    assert result["counts"]["plugins"] == 1 and result["counts"]["main_agents"] == 1
    assert "shared" not in {d for d in result["template"]} and not any(i["where"] == "shared" for i in result["items"])
    team = result["teams"]["gadget-inspection"]
    assert team["pattern"] == "plugin" and team["steps_skill"] == "gadget-inspection-method"
    assert [w["agent"] for w in team["workers"]] == ["gadgets-worker", "gadgets-reviewer"]


def test_a_main_agent_is_found_by_what_it_does_not_by_its_name(plugin):
    text = (plugin / "gadgets" / "agents" / "gadget-inspection.md").read_text()
    assert sc.role_of("gadget-inspection", "gadgets", text) == "main"
    assert sc.role_of("gadgets-reviewer", "gadgets", text) == "reviewer"
    no_agent_tool = text.replace('"Agent", ', "")
    assert sc.role_of("gadget-inspection", "gadgets", no_agent_tool) == "main"  # it dispatches the worker
    assert sc.role_of("gadget-labeller", "gadgets", "---\nname: gadget-labeller\ntools: [Read]\n---\n\nLabel lots.\n") == "other"
    plugin_agent(plugin, "gadget-labeller", "Labels lots.", ["Read"], body="You label lots.\n")
    result = sc.scan(plugin, run_help=False)
    assert "lint:pattern-role:gadgets/agents/gadget-labeller.md" in keys(result, "lint")
    assert "gadget-labeller" not in sc.Toolbox(plugin).main_agents()


def test_a_main_agent_off_the_pattern_is_reported(plugin):
    long_body = MAIN_BODY.replace("## Goal\n", "## Goal\n" + "More procedure.\n" * 30).replace("## Never", "## Rules")
    plugin_agent(plugin, "gadget-inspection", "Runs the weekly gadget inspection.", ["Read", "Agent", "Bash"],
                 extra="skills: [acme-conduct]\n", body=long_body)
    got = sc.pattern_problems(sc.Toolbox(plugin), "gadget-inspection",
                              plugin / "gadgets" / "agents" / "gadget-inspection.md", "main")
    main = [t for k, t in got if k == "pattern-main"]
    assert "missing ## Never" in main
    assert any("lines; a main agent is about 40" in t for t in main)
    assert any("tools lack Skill" in t for t in main) and any("bare Bash" in t for t in main)
    assert [t for k, t in got if k == "pattern-steps"][0].startswith("none of its skills in gadgets (acme-conduct)")


def test_the_reviewer_is_read_only_and_the_worker_cannot_dispatch(plugin):
    plugin_agent(plugin, "gadgets-reviewer", "Judges.", ["Read", "Edit", "Bash"], body=REVIEWER_BODY)
    plugin_agent(plugin, "gadgets-worker", "One slice.", ["Read", "Agent"], body="You do one slice.\n")
    result = sc.scan(plugin, run_help=False)
    lint = {i["key"]: i["text"] for i in result["items"] if i["section"] == "lint"}
    assert "not read-only: its tools grant Edit, Bash" in lint["lint:pattern-reviewer:gadgets/agents/gadgets-reviewer.md"]
    assert "cannot dispatch" in lint["lint:pattern-worker:gadgets/agents/gadgets-worker.md"]
    (plugin / "gadgets" / "agents" / "gadgets-reviewer.md").unlink()
    result = sc.scan(plugin, run_help=False)
    assert "lint:pattern-department:gadgets:reviewer" in keys(result, "lint")


def test_steps_are_read_as_sentinel_reads_them():
    found, steps, problems = sc.parse_steps(GADGET_STEPS)
    assert found and problems == []
    assert [(s["n"], s["kind"], s["target"]) for s in steps][:3] == [(1, "script", None), (2, "hand-off", "gadgets-worker"),
                                                                   (3, "hand-off", "gadgets-reviewer")]
    bad = ("## Steps\n\n1. Pull the lots.\n2. [hand-off] Inspect.\n4. [script] Write the note.\n"
           "   → FAIL: step 9\n-> loose: stop\n")
    whys = [why for _, why in sc.parse_steps(bad)[2]]
    assert "step 1: no [kind] after the number" in whys
    assert "step 2: a hand-off names no agent ([hand-off: agent-name])" in whys
    assert "step 4 comes where step 3 was expected" in whys
    assert "step 4: a script step names no command in backticks" in whys
    assert "step 4: goes to step 9, which does not exist" in whys
    assert any("indent a branch line" in w for w in whys) and any("with →, not ->" in w for w in whys)
    assert sc.parse_steps("# Skill\n\nNo steps here.\n") == (False, [], [])


def test_steps_hand_off_only_to_the_departments_worker_or_reviewer(plugin):
    skill = plugin / "gadgets" / "skills" / "gadget-inspection-method" / "SKILL.md"
    skill.write_text(skill.read_text().replace("[hand-off: gadgets-worker]", "[hand-off: widget-inspector]")
                     .replace("2. [hand-off", "2.  [hand-off").replace("   → nothing to inspect: done\n", "   → nothing: later\n"))
    result = sc.scan(plugin, run_help=False)
    lint = {i["key"]: i["text"] for i in result["items"] if i["section"] == "lint"}
    where = "gadgets/skills/gadget-inspection-method/SKILL.md"
    assert "hands off to widget-inspector" in lint[f"lint:pattern-handoff:{where}"]
    assert "a branch reads 'condition: step N|stop|ask|done (max N)'" in lint[f"lint:pattern-steps:{where}"]


def test_a_plugin_reaches_no_other_departments_agent_or_skill(plugin):
    plugin_agent(plugin, "gadget-inspection", "Runs the weekly gadget inspection.",
                 ["Read", "Skill", "Agent(gadgets-worker, gadgets:gadgets-reviewer, widget-inspector)"],
                 extra="skills: [gadget-inspection-method, widget-method]\n")
    result = sc.scan(plugin, run_help=False)
    cross = keys(result, "drift", "cross-department")
    assert cross == {"drift:cross-department:gadget-inspection:skill:widget-method",
                     "drift:cross-department:gadget-inspection:agent:widget-inspector"}
    assert {i["level"] for i in result["items"] if i["kind"] == "cross-department"} == {"error"}


def test_a_copy_must_match_its_source(plugin):
    copy = plugin / "gadgets" / "skills" / "acme-conduct"
    (copy / "SKILL.md").write_text((copy / "SKILL.md").read_text() + "An edit made in the copy.\n")
    write(copy / "notes.md", "Only in the copy.\n")
    result = sc.scan(plugin, run_help=False)
    drift = {i["key"]: i for i in result["items"] if i["kind"] == "copy"}
    item_ = drift["drift:copy:gadgets/skills/acme-conduct"]
    assert item_["level"] == "error" and "SKILL.md" in item_["text"] and "notes.md" in item_["text"]
    (copy / ".shared-copy").write_text("source: acme-gone\n")
    result = sc.scan(plugin, run_help=False)
    assert "does not exist" in {i["key"]: i for i in result["items"]}["drift:copy:gadgets/skills/acme-conduct"]["text"]


def test_a_copy_is_judged_once_at_its_source(plugin):
    result = sc.scan(plugin, run_help=False)
    assert sc.Toolbox(plugin).skills["acme-conduct"] == plugin / "shared" / "skills" / "acme-conduct"
    assert not any(i["where"].startswith("gadgets/skills/acme-conduct") for i in result["items"])


def test_a_plugin_runs_commands_by_name_and_a_command_counts_as_use(plugin):
    result = sc.scan(plugin, run_help=False)
    assert "unused:script:gadgets/skills/gadget-inspection-method/scripts/lot_pull.py" not in keys(result, "unused")
    assert not any("gadgets-lot-pull" in k for k in keys(result, "drift"))  # the README may list commands
    skill = plugin / "gadgets" / "skills" / "gadget-inspection-method" / "SKILL.md"
    skill.write_text(skill.read_text() + "\nOr `python3 ${CLAUDE_PLUGIN_ROOT}/skills/gadget-inspection-method/scripts/lot_pull.py`.\n")
    result = sc.scan(plugin, run_help=False)
    assert "lint:pattern-script-path:gadgets/skills/gadget-inspection-method/SKILL.md" in keys(result, "lint")


def test_the_toolbox_checks_plugin_lines_are_plugin_findings(plugin):
    write(plugin / "scripts" / "toolbox_check.py", 'print("gadgets/bin/gadgets-lot-pull: out of date (write); run python3 '
          'scripts/build_bins.py gadgets")\nprint("gadgets/agents/gadget-inspection.md:6: Bash(gadgets-gone) names no '
          'command in gadgets/bin/")\n')
    result = sc.scan(plugin, run_help=False)
    plugin_items = [i for i in result["items"] if i["section"] == "check" and i["kind"] == "plugin"]
    assert {i["where"] for i in plugin_items} == {"gadgets/bin/gadgets-lot-pull", "gadgets/agents/gadget-inspection.md"}
    assert not [i for i in result["items"] if i["section"] == "guards"]
