"""software_factory_sync.py: the snapshot's files and shapes, filters, STALE, and the precheck. gh and
git are the fake from sf_support; nothing reaches a network."""

import json

import pytest

import _common
from sf_support import OTHER, OWNER, REPO
from software_factory_sync import main

SHA = "a" * 40
BRANCH = "software-factory/issue-42-fix-date-parse"
RULES = "# Factory rules\n\n- Integration branch: development\n- Auto-merge: yes  # merge passing PRs\n- Release PR: yes\n" \
        "- Protected paths: migrations/; infra/\n"


def issue(n, title="Date parse fails", author=OWNER, assignees=(OWNER,), labels=("bug",), comments=()):
    return {"number": n, "title": title, "body": "Steps to reproduce", "state": "OPEN",
            "labels": [{"name": l} for l in labels], "assignees": [{"login": a} for a in assignees],
            "author": {"login": author}, "createdAt": "2030-01-01T00:00:00Z", "updatedAt": "2030-01-02T00:00:00Z",
            "comments": [{"author": {"login": a}, "body": b, "createdAt": t} for a, b, t in comments]}


def pr(n, head=BRANCH, ci="FAILURE", mergeable="MERGEABLE"):
    return {"number": n, "url": f"https://github.com/acme/widgets/pull/{n}", "title": "Fix dates", "body": "Refs #42",
            "state": "OPEN", "isDraft": False, "headRefName": head, "baseRefName": "development", "headRefOid": SHA,
            "mergeable": mergeable, "mergeStateStatus": "CLEAN", "reviewDecision": None, "labels": [],
            "author": {"login": OWNER},
            "statusCheckRollup": [{"name": "tests", "status": "COMPLETED", "conclusion": ci,
                                   "detailsUrl": "https://github.com/acme/widgets/actions/runs/900/job/1"}]}


@pytest.fixture
def gh(fake, env):
    (env / "repos" / "widgets" / ".git").mkdir(parents=True)
    fake.on("gh", "repo", "view", out={"defaultBranchRef": {"name": "main"}, "nameWithOwner": REPO})
    fake.on("gh", "api", "user", out=OWNER + "\n")
    fake.on("git", "fetch", out="")
    fake.on("git", "show", "origin/main:.software-factory/SOFTWARE-FACTORY-RULES.md", out=RULES)
    fake.on("git", "cat-file", "-e", out="")
    fake.on("git", "rev-parse", "--verify", "--quiet", "refs/remotes/origin/development", out="")
    fake.on("git", "rev-parse", "refs/remotes/origin/development", out="d" * 40 + "\n")
    fake.on("git", "show", "refs/remotes/origin/development:.software-factory/commands.yaml", out="test: pytest -q\n")
    fake.on("gh", "issue", "list", out=[issue(42), issue(43, title="Inventory export", author=OTHER, assignees=())])
    fake.on("gh", "pr", "list", "-R", REPO, "--state", "open", out=[])
    fake.on("gh", "run", "list", out=[])
    fake.on("gh", "run", "view", out="line1\nAssertionError: expected week 1\n")
    fake.on("gh", "api", out=[])
    fake.on("gh", "pr", "view", out={"comments": [], "reviews": []})
    return fake


def test_writes_the_contract_shapes(gh, env, capsys):
    out = env / "run" / "sync"
    assert main([REPO, "--out", str(out)]) == 0
    assert capsys.readouterr().out.startswith("SYNCED: 2 issues, 0 factory PRs, CI none")
    repo = json.loads((out / "repo.json").read_text())
    assert (repo["integration_branch"], repo["rules"]["auto-merge"], repo["protected_paths"]) == (
        "development", "yes", ["migrations/", "infra/"])
    assert repo["test_command"] is True and repo["needs_onboarding"] is False and repo["owner_login"] == OWNER
    issues = json.loads((out / "issues.json").read_text())
    assert [i["excluded"] for i in issues] == [None, f"opened by {OTHER}"]
    assert (out / "SYNC.md").read_text().startswith("SYNCED:") and (out / "ci.json").exists()


def test_factory_prs_with_ci_and_unanswered_comments(gh, env):
    gh.on("gh", "pr", "list", "-R", REPO, "--state", "open", out=[pr(77), pr(78, head="feature/other")])
    gh.on("gh", "pr", "view", "77", "-R", REPO, "--json", "comments,reviews", out={"comments": [
        {"author": {"login": "bot"}, "body": f"From the software factory: done\n{_common.MARKER}",
         "createdAt": "2030-01-03T00:00:00Z"},
        {"author": {"login": OTHER}, "body": "Please also cover leap years", "createdAt": "2030-01-04T00:00:00Z"},
        {"author": {"login": "ci[bot]"}, "body": "coverage 90%", "createdAt": "2030-01-05T00:00:00Z"}], "reviews": []})
    out = env / "sync"
    assert main([REPO, "--out", str(out)]) == 0
    prs = json.loads((out / "prs.json").read_text())
    assert [p["number"] for p in prs] == [77]
    p = prs[0]
    assert (p["issue"], p["ci"], p["mergeable"]) == (42, "failure", "mergeable")
    assert "expected week 1" in p["failing_checks"][0]["log_tail"]
    assert [c["author"] for c in p["unanswered_comments"]] == [OTHER]


def test_filters_and_numbers(gh, env):
    out = env / "sync"
    assert main([REPO, "#43", "--out", str(out)]) == 0
    assert [i["number"] for i in json.loads((out / "issues.json").read_text())] == [43]
    assert main([REPO, "--topic", "inventory", "--out", str(out)]) == 0
    assert [i["number"] for i in json.loads((out / "issues.json").read_text())] == [43]


def test_stale_when_github_cannot_be_read(gh, env, capsys):
    gh.on("gh", "repo", "view", code=1)
    out = env / "sync"
    assert main([REPO, "--out", str(out)]) == 0
    assert capsys.readouterr().out.startswith("STALE:")
    assert [p.name for p in out.iterdir()] == ["SYNC.md"]


def test_protected_integration_branch_falls_back(gh, env):
    gh.on("git", "show", "origin/main:.software-factory/SOFTWARE-FACTORY-RULES.md", out="- Integration branch: release\n")
    out = env / "sync"
    main([REPO, "--out", str(out)])
    repo = json.loads((out / "repo.json").read_text())
    assert repo["integration_branch"] == "main" and "protected" in repo["notes"][0]


def test_bad_arguments(gh, env):
    assert main([REPO]) == 2
    assert main([REPO, "--precheck", "--out", str(env / "x")]) == 2
    assert main(["nope", "--precheck"]) == 2
    assert main([REPO, "abc", "--precheck"]) == 2


def test_precheck(gh, env, capsys):
    assert main([REPO, "--precheck"]) == 0
    assert capsys.readouterr().out.startswith("WORK: 1 eligible issue not in the ledger (#42)")
    _common.record(REPO, 42, "triaged-human", "o")
    main([REPO, "--precheck"])
    assert capsys.readouterr().out.startswith("NOTHING: 2 open issues (1 excluded")
    assert not gh.find("git", "fetch")                    # the precheck never fetches
    gh.on("gh", "pr", "list", "-R", REPO, "--state", "open", out=[pr(77)])
    main([REPO, "--precheck"])
    assert "PR #77 CI failing (tests)" in capsys.readouterr().out


def test_precheck_onboarding(gh, env, capsys):
    gh.on("git", "show", "refs/remotes/origin/development:.software-factory/commands.yaml", code=1)
    _common.record(REPO, 42, "triaged-human", "o")
    main([REPO, "--precheck"])
    assert "onboarding: development has no" in capsys.readouterr().out
    gh.on("gh", "pr", "list", "-R", REPO, "--state", "open", out=[pr(5, head="software-factory/onboard", ci="SUCCESS")])
    main([REPO, "--precheck"])
    assert "onboarding" not in capsys.readouterr().out
