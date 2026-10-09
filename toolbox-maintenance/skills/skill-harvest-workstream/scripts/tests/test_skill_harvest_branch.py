"""skill_harvest_branch.py against a made-up toolbox in a temporary git repository. The drafts
describe invented work for Acme Components; nothing here comes from a real session."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import skill_harvest_branch as shb  # noqa: E402

NAME_CHECK = HERE.parents[2] / "skills-extract" / "scripts" / "name_check.py"
GIT = ["-c", "user.email=dana@example.com", "-c", "user.name=Dana"]


def git(cwd, *args):
    return subprocess.run(["git", *GIT, *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


@pytest.fixture
def setup(tmp_path, monkeypatch):
    deny = tmp_path / "denylist.txt"
    deny.write_text("Northwind\n")
    monkeypatch.setenv("F3I_TOOLBOX_DENYLIST", str(deny))
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "none.toml"))
    repo = tmp_path / "toolbox"
    (repo / "finance" / "skills").mkdir(parents=True)
    (repo / "finance" / "README.md").write_text("# Finance\n")
    (repo / "scripts").mkdir()
    (repo / "scripts" / "toolbox_check.py").write_text("import sys\nsys.exit(0)\n")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "start")
    run = tmp_path / "runs" / "2026-10"
    skill = run / "drafts" / "finance" / "skills" / "finance-lot-count"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: finance-lot-count\ndescription: Count lots. Use when a lot count is due.\n---\n\nBody.\n")
    (run / "harvest-note.md").write_text("- finance-lot-count: counts lots each month.\n")
    return repo, run


def test_drafts_are_committed_on_a_review_branch_and_main_is_untouched(setup):
    repo, run = setup
    result = shb.stage(run, repo, checker=str(NAME_CHECK), today="2026-10-05")
    assert result["state"] == "committed", result
    assert result["branch"] == "skill-harvest/2026-10-05"
    assert git(repo, "log", "-1", "--format=%s", "main").strip() == "start"
    shown = git(repo, "show", "--format=%B", result["branch"])
    assert "finance/skills/finance-lot-count/SKILL.md" in git(repo, "show", "--name-only", "--format=", result["branch"])
    assert "counts lots each month" in shown and "Skill-Harvest-Run: 2026-10" in shown
    assert not (run / "toolbox").exists()


def test_a_denylisted_name_in_a_draft_refuses_the_branch(setup):
    repo, run = setup
    (run / "drafts" / "finance" / "skills" / "finance-lot-count" / "SKILL.md").write_text(
        "---\nname: finance-lot-count\ndescription: Count lots for Northwind.\n---\n")
    result = shb.stage(run, repo, checker=str(NAME_CHECK))
    assert result["state"] == "refused" and "name check" in result["line"]
    assert "skill-harvest/" not in git(repo, "branch")


def test_a_draft_outside_a_department_skill_folder_is_refused(setup):
    repo, run = setup
    (run / "drafts" / "notes.md").write_text("loose\n")
    (run / "drafts" / "legal" / "skills" / "x" ).mkdir(parents=True)
    (run / "drafts" / "legal" / "skills" / "x" / "SKILL.md").write_text("x\n")
    result = shb.stage(run, repo, checker=str(NAME_CHECK))
    assert result["state"] == "refused"
    assert any("notes.md" in p for p in result["problems"]) and any("no department legal" in p for p in result["problems"])


def test_a_run_folder_inside_the_toolbox_is_refused(setup):
    repo, run = setup
    inside = repo / "run"
    (inside / "drafts").mkdir(parents=True)
    (inside / "drafts" / "a.md").write_text("a\n")
    with pytest.raises(shb.Refused, match="inside the toolbox"):
        shb.stage(inside, repo, checker=str(NAME_CHECK))


def test_dry_run_checks_only_and_main_needs_the_repo_setting(setup, capsys):
    repo, run = setup
    assert shb.stage(run, repo, checker=str(NAME_CHECK), dry_run=True)["state"] == "would-stage"
    assert "skill-harvest/" not in git(repo, "branch")
    assert shb.main(["--run", str(run)]) == 2
    assert "[skill-harvest-workstream]" in capsys.readouterr().err
    assert shb.main(["--run", str(run), "--repo", str(repo), "--name-check", str(NAME_CHECK), "--dry-run"]) == 0
    assert json.loads((run / "branch.json").read_text())["state"] == "would-stage"


def live_state(repo):
    """The live checkout's branch, head commit and working-tree status."""
    return (git(repo, "symbolic-ref", "--short", "HEAD").strip(), git(repo, "rev-parse", "HEAD").strip(),
            git(repo, "status", "--porcelain"))


def test_the_live_checkout_keeps_its_branch_files_and_head(setup):
    repo, run = setup
    git(repo, "checkout", "-q", "-b", "owner-work")
    (repo / "finance" / "README.md").write_text("# Finance, being edited\n")
    before = live_state(repo)
    result = shb.stage(run, repo, checker=str(NAME_CHECK), today="2026-10-05")
    assert result["state"] == "committed", result
    assert live_state(repo) == before
    assert "finance-lot-count" not in str(list((repo / "finance" / "skills").iterdir()))
    assert git(repo, "branch", "--contains", result["branch"]).split() == [result["branch"]]  # merged nowhere


def test_a_run_folder_inside_a_linked_worktree_is_refused(setup, tmp_path):
    repo, run = setup
    other = tmp_path / "other-tree"
    git(repo, "worktree", "add", "-q", "-b", "side", str(other))
    inside = other / "run"
    (inside / "drafts").mkdir(parents=True)
    (inside / "drafts" / "a.md").write_text("a\n")
    with pytest.raises(shb.Refused, match="inside the toolbox"):
        shb.stage(inside, repo, checker=str(NAME_CHECK))


def test_a_symbolic_link_draft_is_refused(setup, tmp_path):
    repo, run = setup
    outside = tmp_path / "outside.md"
    outside.write_text("anything\n")
    (run / "drafts" / "finance" / "skills" / "finance-lot-count" / "rules.md").symlink_to(outside)
    result = shb.stage(run, repo, checker=str(NAME_CHECK))
    assert result["state"] == "refused" and "symbolic link" in result["line"]
    assert "skill-harvest/" not in git(repo, "branch")


def test_no_toolbox_check_means_no_commit(setup):
    repo, run = setup
    git(repo, "rm", "-q", "scripts/toolbox_check.py")
    git(repo, "commit", "-q", "-m", "drop check")
    result = shb.stage(run, repo, checker=str(NAME_CHECK), today="2026-10-05")
    assert result["state"] == "refused" and "no check script" in result["line"]
    assert git(repo, "log", "-1", "--format=%s", result["branch"]).strip() == "drop check"  # nothing committed on it


def test_a_failing_toolbox_check_commits_nothing_and_withholds_the_name(setup):
    repo, run = setup
    (repo / "scripts" / "toolbox_check.py").write_text(
        "import sys\nprint('finance/skills/finance-lot-count/SKILL.md:3: private name: Northwind')\nsys.exit(1)\n")
    git(repo, "commit", "-qam", "strict check")
    result = shb.stage(run, repo, checker=str(NAME_CHECK), today="2026-10-05")
    assert result["state"] == "refused" and "toolbox check failed" in result["line"]
    assert git(repo, "log", "-1", "--format=%s", result["branch"]).strip() == "strict check"
    stored = (json.dumps(result))
    assert "Northwind" not in stored and "(withheld)" in stored


def test_a_private_name_in_the_run_folder_name_refuses_the_commit_message(setup, tmp_path):
    repo, run = setup
    named = tmp_path / "runs" / "northwind-2026-10"
    run.rename(named)
    result = shb.stage(named, repo, checker=str(NAME_CHECK))
    assert result["state"] == "refused" and "commit message" in result["line"]
    assert "skill-harvest/" not in git(repo, "branch")
