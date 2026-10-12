"""pr_merge.py: the merge guard, against a fake gh for a made-up repository of Acme Components.
Nothing reaches a network."""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import pr_merge  # noqa: E402

REPO = "acme-components/parts-catalog"
GREEN = [{"name": "tests", "status": "COMPLETED", "conclusion": "SUCCESS"},
         {"context": "lint", "state": "SUCCESS"}]


def pr(**over):
    base = {"number": 12, "state": "OPEN", "isDraft": False, "baseRefName": "development",
            "headRefName": "issue/12-part-search", "headRefOid": "abc123",
            "labels": [{"name": "ai-agent"}, {"name": "bug"}], "statusCheckRollup": GREEN,
            "mergeable": "MERGEABLE"}
    base.update(over)
    return base


@pytest.fixture
def fake(monkeypatch):
    """A gh that answers pr view and repo view from `state`, and records every call."""
    state = {"pr": pr(), "default": "main", "calls": [], "merge_fails": False}

    def gh(*args):
        state["calls"].append(list(args))
        if args[:2] == ("pr", "view"):
            return json.dumps(state["pr"])
        if args[:2] == ("repo", "view"):
            return json.dumps({"defaultBranchRef": {"name": state["default"]}})
        if args[:2] == ("pr", "merge"):
            if state["merge_fails"]:
                raise pr_merge.GhError("Head branch was modified")
            return ""
        raise AssertionError(f"unexpected gh call {args}")

    monkeypatch.setattr(pr_merge, "gh", gh)
    return state


def merges(state):
    return [c for c in state["calls"] if c[:2] == ["pr", "merge"]]


def test_merges_a_green_agent_pr_into_development_by_squash_pinned_to_its_head(fake, capsys):
    assert pr_merge.main(["12", "-R", REPO]) == 0
    assert merges(fake) == [["pr", "merge", "12", "-R", REPO, "--squash", "--match-head-commit", "abc123"]]
    assert capsys.readouterr().out.startswith("merged PR #12 (issue/12-part-search -> development)")


@pytest.mark.parametrize("over, default, why", [
    ({"labels": [{"name": "bug"}]}, "main", "no 'ai-agent' label"),
    ({"isDraft": True}, "main", "is a draft"),
    ({"state": "MERGED"}, "main", "is merged, not open"),
    ({"baseRefName": "main"}, "main", "the default branch"),
    ({"baseRefName": "trunk"}, "trunk", "the default branch"),
    ({"baseRefName": "production"}, "main", "a production branch"),
    ({"baseRefName": "master"}, "main", "a production branch"),
    ({"baseRefName": "staging"}, "main", "not the integration branch development"),
    ({"mergeable": "CONFLICTING"}, "main", "merge conflict"),
    ({"statusCheckRollup": [{"name": "tests", "status": "COMPLETED", "conclusion": "FAILURE"}]}, "main",
     "failed checks: tests"),
    ({"statusCheckRollup": [{"context": "deploy-preview", "state": "ERROR"}]}, "main", "failed checks: deploy-preview"),
    ({"statusCheckRollup": [{"name": "tests", "status": "IN_PROGRESS", "conclusion": ""}]}, "main",
     "still pending: tests"),
    ({"statusCheckRollup": [{"context": "lint", "state": "PENDING"}]}, "main", "still pending: lint"),
    ({"statusCheckRollup": []}, "main", "has no checks"),
])
def test_refuses_with_one_line_and_merges_nothing(fake, capsys, over, default, why):
    fake["pr"] = pr(**over)
    fake["default"] = default
    assert pr_merge.main(["12", "-R", REPO]) == 1
    out = capsys.readouterr().out
    assert out.startswith("refused: ") and why in out and out.count("\n") == 1
    assert merges(fake) == []


def test_an_integration_flag_naming_production_still_refuses(fake, capsys):
    fake["pr"] = pr(baseRefName="main")
    assert pr_merge.main(["12", "-R", REPO, "--integration", "main"]) == 1
    assert merges(fake) == []
    fake["pr"] = pr(baseRefName="prod")
    assert pr_merge.main(["12", "-R", REPO, "--integration", "prod"]) == 1
    assert merges(fake) == []


def test_another_integration_branch_and_strategy(fake, capsys):
    fake["pr"] = pr(baseRefName="dev")
    assert pr_merge.main(["12", "-R", REPO]) == 1
    assert pr_merge.main(["12", "-R", REPO, "--integration", "dev", "--strategy", "merge"]) == 0
    assert merges(fake)[0][5] == "--merge"


def test_no_checks_merges_only_when_allowed(fake):
    fake["pr"] = pr(statusCheckRollup=[])
    assert pr_merge.main(["12", "-R", REPO, "--allow-no-checks"]) == 0
    assert len(merges(fake)) == 1


def test_skipped_and_neutral_checks_pass(fake):
    fake["pr"] = pr(statusCheckRollup=[{"name": "docs", "status": "COMPLETED", "conclusion": "SKIPPED"},
                                       {"name": "audit", "status": "COMPLETED", "conclusion": "NEUTRAL"}])
    assert pr_merge.main(["12", "-R", REPO]) == 0


def test_dry_run_reports_and_merges_nothing(fake, capsys):
    assert pr_merge.main(["12", "-R", REPO, "--dry-run"]) == 0
    assert capsys.readouterr().out.startswith("would merge PR #12")
    assert merges(fake) == []
    fake["pr"] = pr(baseRefName="main")
    assert pr_merge.main(["12", "-R", REPO, "--dry-run"]) == 1
    assert "refused:" in capsys.readouterr().out


def test_a_failed_merge_exits_2(fake, capsys):
    fake["merge_fails"] = True
    assert pr_merge.main(["12", "-R", REPO]) == 2
    assert "Head branch was modified" in capsys.readouterr().err


def test_the_command_end_to_end_with_a_fake_gh_on_path(tmp_path):
    """The real gh() through a stand-in gh executable: view answers, merge is logged."""
    log = tmp_path / "gh.log"
    fake_gh = tmp_path / "gh"
    fake_gh.write_text(
        "#!/bin/sh\n"
        f"echo \"$*\" >> '{log}'\n"
        "case \"$1 $2\" in\n"
        f"  'pr view') echo '{json.dumps(pr(baseRefName='main'))}' ;;\n"
        "  'repo view') echo '{\"defaultBranchRef\": {\"name\": \"main\"}}' ;;\n"
        "  *) exit 1 ;;\n"
        "esac\n")
    fake_gh.chmod(fake_gh.stat().st_mode | stat.S_IXUSR)
    env = {**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}"}
    done = subprocess.run([sys.executable, str(SCRIPTS / "pr_merge.py"), "12", "-R", REPO],
                          capture_output=True, text=True, env=env)
    assert done.returncode == 1
    assert done.stdout.strip() == "refused: PR #12 targets main, the default branch; promotion belongs to a person"
    assert "pr merge" not in log.read_text()
