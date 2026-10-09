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
    assert result["template"] == {"widgets": {"agents": 4, "flagged": 3}}


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
    ops = json.loads((run / "changes.json").read_text())["ops"]
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
