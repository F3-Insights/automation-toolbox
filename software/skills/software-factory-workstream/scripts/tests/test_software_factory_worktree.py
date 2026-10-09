"""software_factory_worktree.py: the issue's worktree from the local clone, offline."""

import json

from sf_support import REPO, commit, make_origin, sh
from software_factory_worktree import main

RULES = "# Factory rules\n\n- Integration branch: development\n"


def test_created_then_reused(env, capsys):
    make_origin(env, {"README.md": "Acme widgets\n", ".software-factory/SOFTWARE-FACTORY-RULES.md": RULES})
    assert main([REPO, "--issue", "42", "--slug", "Fix date parse!", "--format", "json"]) == 0
    made = json.loads(capsys.readouterr().out)
    assert made["branch"] == "software-factory/issue-42-fix-date-parse" and made["base"] == "development"
    assert made["created"] and made["path"].endswith(".software-factory-worktrees/acme__widgets/issue-42")
    assert main([REPO, "--issue", "42", "--slug", "fix date parse", "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["reused"]


def test_onboarding_and_default_base(env, capsys):
    make_origin(env, {"README.md": "x\n"}, branches=("main",))
    assert main([REPO, "--issue", "0", "--format", "json"]) == 0
    made = json.loads(capsys.readouterr().out)
    assert (made["branch"], made["base"]) == ("software-factory/onboard", "main")


def test_refusals(env, capsys):
    _, clone = make_origin(env, {"README.md": "x\n"})
    assert main([REPO, "--issue", "5"]) == 2                     # no slug
    assert main([REPO, "--issue", "5", "--slug", "a", "--base", "staging"]) == 2
    path = env / "repos" / ".software-factory-worktrees" / "acme__widgets" / "issue-6"
    path.mkdir(parents=True)
    assert main([REPO, "--issue", "6", "--slug", "b"]) == 1      # a folder that is not a worktree
    assert "not a worktree" in capsys.readouterr().err


def test_needs_a_clone_and_the_setting(env, monkeypatch, capsys):
    assert main([REPO, "--issue", "1", "--slug", "x"]) == 2
    monkeypatch.delenv("SOFTWARE_FACTORY_REPOS_DIR")
    assert main([REPO, "--issue", "1", "--slug", "x"]) == 2
    assert "repos_dir" in capsys.readouterr().err
