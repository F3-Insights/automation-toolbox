"""software_factory_ship.py: the guards, the order of writes, merges, the release PR, the outbox and
the dry run. gh and git are the fake from sf_support; nothing reaches a network."""

import json
from pathlib import Path

import pytest

import _common
from sf_support import OTHER, OWNER, REPO
from software_factory_ship import main

SHA, BASE_SHA = "a" * 40, "b" * 40
BRANCH = "software-factory/issue-42-fix-date-parse"


def raw_pr(n, head=BRANCH, sha=SHA, ci="SUCCESS", mergeable="MERGEABLE"):
    return {"number": n, "url": f"https://github.com/acme/widgets/pull/{n}", "title": "Fix dates", "body": "Refs #42",
            "state": "OPEN", "isDraft": False, "headRefName": head, "baseRefName": "development", "headRefOid": sha,
            "mergeable": mergeable, "mergeStateStatus": "CLEAN", "reviewDecision": None, "labels": [],
            "author": {"login": OWNER},
            "statusCheckRollup": [{"name": "tests", "status": "COMPLETED" if ci != "PENDING" else "IN_PROGRESS",
                                   "conclusion": "" if ci == "PENDING" else ci}]}


@pytest.fixture
def run(fake, env):
    """A Run folder whose manifest holds one branch for issue 42 that passes every guard."""
    r = env / "run"
    ev = r / "evidence" / "issue-42"
    ev.mkdir(parents=True)
    (r / "sync").mkdir()
    (r / "ship").mkdir()
    wt = env / "wt" / "issue-42"
    wt.mkdir(parents=True)
    info = {"owner": "acme", "name": "widgets", "default_branch": "main", "integration_branch": "development",
            "local_clone": str(env / "repos" / "widgets"), "owner_login": OWNER,
            "rules": {"auto-merge": "yes", "release pr": "yes", "protected paths": "migrations/; infra/"}}
    (r / "sync" / "repo.json").write_text(json.dumps(info))
    (r / "sync" / "prs.json").write_text("[]")
    (r / "ship" / "pr-42.md").write_text("Fix ISO week date parsing.\n\nRefs #42\n")
    (ev / "verify.json").write_text(json.dumps({"head_sha": SHA, "base_sha": BASE_SHA, "verdict": "verified",
                                                "commands_from": f".software-factory/commands.yaml@{BASE_SHA}",
                                                "steps": [{"name": "test", "run": "pytest -q", "exit": 0,
                                                           "summary": "12 passed"}], "offline": True}))
    (ev / "review.json").write_text(json.dumps({"review": "PASS", "head_sha": SHA, "summary": "Correct and tested"}))
    (r / "ship" / "manifest.json").write_text(json.dumps({"repo": REPO, "branches": [{
        "issue": 42, "branch": BRANCH, "worktree": str(wt), "head_sha": SHA, "base": "development",
        "title": "Fix date parsing for ISO week dates", "body_file": "ship/pr-42.md",
        "verify_file": "evidence/issue-42/verify.json", "review_file": "evidence/issue-42/review.json",
        "risk": "low", "action": "open"}]}))
    for prefix, out, code in [
            (("gh", "repo", "view"), {"defaultBranchRef": {"name": "main"}}, 0),
            (("gh", "api", "user"), OWNER + "\n", 0), (("gh", "api"), [], 0),
            (("git", "rev-parse", "HEAD"), SHA + "\n", 0), (("git", "rev-parse", "--abbrev-ref", "HEAD"), BRANCH + "\n", 0),
            (("git", "merge-base", "--is-ancestor"), "", 0), (("git", "merge-base", "--is-ancestor", "deadbeef"), "", 1),
            (("git", "diff", "--name-only"), "src/dates.py\ntests/test_dates.py\n", 0), (("git", "push"), "", 0),
            (("git", "fetch"), "", 0), (("git", "rev-list", "--count"), "0\n", 0),
            (("gh", "pr", "list", "-R", REPO, "--head", BRANCH), [], 0), (("gh", "label", "list"), [], 0),
            (("gh", "label", "create"), "", 0), (("gh", "pr", "create"), "https://github.com/acme/widgets/pull/77\n", 0),
            (("gh", "pr", "edit"), "", 0), (("gh", "pr", "comment"), "", 0), (("gh", "issue", "comment"), "", 0),
            (("gh", "issue", "edit"), "", 0), (("gh", "pr", "merge"), "", 0), (("gh", "pr", "diff"), "src/dates.py\n", 0),
            (("gh", "pr", "view"), {"comments": [], "reviews": []}, 0),
            (("gh", "pr", "view", "77", "-R", REPO, "--json", _common.PR_FIELDS), raw_pr(77, ci="PENDING"), 0)]:
        fake.on(*prefix, out=out, code=code)
    return r


def edit(run, **changes):
    path = run / "ship" / "manifest.json"
    m = json.loads(path.read_text())
    m["branches"][0].update(changes)
    path.write_text(json.dumps(m))


def ship(run, capsys, *args):
    code = main([REPO, "--run", str(run), "--format", "json", *args])
    text = capsys.readouterr().out
    return code, json.loads(text) if text.startswith("{") else None


def test_opens_a_pr_in_order(fake, run, capsys):
    code, out = ship(run, capsys)
    assert code == 0
    kinds = [" ".join(c[1:3]) if c[0] == "gh" else "git push" for c in fake.writes()]
    assert kinds == ["git push", "label create", "pr create", "pr edit", "issue comment"]
    assert fake.key(fake.writes()[0]) == ["git", "push", "origin", f"refs/heads/{BRANCH}:refs/heads/{BRANCH}"]
    create = fake.find("gh", "pr", "create")[0]
    assert create[create.index("--base") + 1] == "development"
    body = Path(create[create.index("--body-file") + 1]).read_text()
    assert _common.MARKER in body and "## Evidence" in body and "12 passed" in body
    comment = fake.find("gh", "issue", "comment", "42")[0]
    assert comment[comment.index("--body") + 1].startswith(_common.FIRST_LINE)
    row = _common.latest(_common.read_ledger(REPO))[42]
    assert (row["state"], row["pr"], row["review"], row["head_sha"]) == ("pr-open", "77", "PASS", SHA)
    assert not fake.find("gh", "pr", "merge") and out["not_merged"][0]["pr"] == 77   # CI still pending


@pytest.mark.parametrize("change,files,why", [
    ({"branch": "feature/issue-42"}, {}, "not a factory branch"),
    ({"branch": "software-factory/issue-41-other"}, {}, "not issue #42's"),
    ({"base": "main"}, {}, "not the integration branch"),
    ({"head_sha": "c" * 40}, {}, "HEAD"),
    ({}, {"verify": {"head_sha": SHA, "base_sha": BASE_SHA, "verdict": "failed"}}, "verdict is 'failed'"),
    ({}, {"verify": {"head_sha": SHA, "base_sha": "deadbeef", "verdict": "verified"}}, "not an ancestor"),
    ({}, {"verify": {"head_sha": SHA, "base_sha": SHA, "verdict": "verified"}}, "own head"),
    ({}, {"verify": {"head_sha": SHA, "base_sha": BASE_SHA, "verdict": "verified",
                     "commands_from": f".software-factory/commands.yaml@{SHA}"}}, "only the onboarding"),
    ({}, {"review": {"review": "FAIL", "head_sha": SHA}}, "not PASS"),
    ({}, {"review": {"review": "PASS", "head_sha": "c" * 40}}, "review.json is for"),
    ({"risk": "spicy"}, {}, "risk"),
    ({"verify_file": "evidence/nope.json"}, {}, "not found"),
])
def test_guard_refusals(fake, run, capsys, change, files, why):
    edit(run, **change)
    for name, data in files.items():
        (run / "evidence" / "issue-42" / f"{name}.json").write_text(json.dumps(data))
    code, out = ship(run, capsys)
    assert code == 0 and any(why in r for r in out["refused"][0]["reasons"]), out["refused"]
    assert not fake.find("git", "push") and not fake.find("gh", "pr", "create")


def test_protected_paths_need_a_one_way_door_and_are_never_merged(fake, run, capsys):
    fake.on("git", "diff", "--name-only", out="migrations/0007_add.sql\nsrc/a.py\n")
    code, out = ship(run, capsys)
    assert "touches protected paths" in out["refused"][0]["reasons"][0]
    edit(run, risk="one-way-door")
    fake.on("gh", "pr", "view", "77", "-R", REPO, "--json", _common.PR_FIELDS, out=raw_pr(77))
    code, out = ship(run, capsys)
    assert out["opened"][0]["pr"] == 77 and not fake.find("gh", "pr", "merge")
    assert any("one-way door" in r for r in out["not_merged"][0]["reasons"])


def test_merges_only_when_every_condition_holds(fake, run, capsys):
    fake.on("gh", "pr", "view", "77", "-R", REPO, "--json", _common.PR_FIELDS, out=raw_pr(77))
    code, out = ship(run, capsys)
    merge = fake.find("gh", "pr", "merge")[0]
    assert "--squash" in merge and merge[merge.index("--match-head-commit") + 1] == SHA
    assert out["merged"] == [{"pr": 77, "issue": 42, "head_sha": SHA}]
    assert _common.latest(_common.read_ledger(REPO))[42]["state"] == "merged"


def test_merge_blocked_without_auto_merge(fake, run, capsys):
    info = json.loads((run / "sync" / "repo.json").read_text())
    info["rules"]["auto-merge"] = "no"
    (run / "sync" / "repo.json").write_text(json.dumps(info))
    fake.on("gh", "pr", "view", "77", "-R", REPO, "--json", _common.PR_FIELDS, out=raw_pr(77))
    code, out = ship(run, capsys)
    assert not fake.find("gh", "pr", "merge") and "Auto-merge" in out["not_merged"][0]["reasons"][0]


def test_release_pr_is_opened_and_never_merged(fake, run, capsys):
    (run / "ship" / "manifest.json").write_text(json.dumps({"repo": REPO, "branches": []}))
    fake.on("git", "rev-list", "--count", out="3\n")
    fake.on("gh", "pr", "list", "-R", REPO, "--head", "development", out=[])
    fake.on("gh", "pr", "list", "-R", REPO, "--base", "development", out=[
        {"number": 70, "title": "Fix totals", "headRefName": "software-factory/issue-40-totals",
         "mergedAt": "2030-01-02T00:00:00Z", "mergeCommit": {"oid": "e" * 40}}])
    fake.on("git", "merge-base", "--is-ancestor", "e" * 40, code=1)
    fake.on("gh", "pr", "create", out="https://github.com/acme/widgets/pull/80\n")
    code, out = ship(run, capsys)
    create = fake.find("gh", "pr", "create")[0]
    assert (create[create.index("--base") + 1], create[create.index("--head") + 1]) == ("main", "development")
    assert out["release"] == {"action": "created", "pr": 80, "entries": [70]}
    assert not fake.find("gh", "pr", "merge")


def test_outbox_follows_the_owner_policy(fake, run, capsys):
    (run / "ship" / "manifest.json").write_text(json.dumps({"repo": REPO, "branches": []}))
    (run / "ship" / "outbox.json").write_text(json.dumps({
        "comments": [{"issue": 51, "body": "Which week rule?", "kind": "question"},
                     {"issue": 52, "body": "Which week rule?", "kind": "question"},
                     {"issue": 0, "body": "hello", "kind": "status"}],
        "labels": [{"issue": 51, "add": ["software-factory:needs-info"]}, {"issue": 52, "add": ["bug"]}]}))
    fake.on("gh", "issue", "view", "51", out={"number": 51, "author": {"login": OWNER}, "assignees": [], "labels": []})
    fake.on("gh", "issue", "view", "52", out={"number": 52, "author": {"login": OTHER}, "assignees": [], "labels": []})
    code, out = ship(run, capsys)
    assert [c["issue"] for c in out["comments"]] == [51]
    assert out["for_owner"][0]["issue"] == 52 and f"opened by {OTHER}" in out["for_owner"][0]["reasons"]
    assert out["labels"] == [{"issue": 51, "add": ["software-factory:needs-info"], "remove": []}]
    assert any("issue 0" in n for n in out["notes"]) and any("only software-factory" in n for n in out["notes"])


def test_dry_run_writes_nothing(fake, run, capsys):
    code, out = ship(run, capsys, "--dry-run")
    assert code == 0 and fake.writes() == []
    assert out["opened"] == [{"issue": 42, "branch": BRANCH, "pr": None}]
    assert any(a.startswith(f"would push {BRANCH}") for a in out["actions"])
    assert _common.read_ledger(REPO) == [] and not (run / "ship" / "pr-42.final.md").exists()


def test_failed_push_exits_1_and_bad_input_exits_2(fake, run, capsys, env):
    fake.on("git", "push", code=1)
    code, out = ship(run, capsys)
    assert code == 1 and out["failures"] and not fake.find("gh", "pr", "create")
    assert main([REPO, "--run", str(env / "missing")]) == 2
    (run / "sync" / "repo.json").write_text(json.dumps({"owner": "northwind", "name": "site"}))
    assert main([REPO, "--run", str(run)]) == 2


def test_onboarding_pr_opens_without_issue_comment_and_is_never_merged(fake, run, capsys, env):
    ev = run / "evidence" / "issue-0"
    ev.mkdir()
    (ev / "verify.json").write_text(json.dumps({"head_sha": SHA, "base_sha": BASE_SHA, "verdict": "verified",
                                                "commands_from": f".software-factory/commands.yaml@{SHA}"}))
    (ev / "review.json").write_text(json.dumps({"review": "PASS", "head_sha": SHA}))
    (run / "ship" / "pr-0.md").write_text("Adds the factory folder.\n")
    edit(run, issue=0, branch="software-factory/onboard", body_file="ship/pr-0.md", title="Onboard widgets",
         verify_file="evidence/issue-0/verify.json", review_file="evidence/issue-0/review.json")
    fake.on("git", "rev-parse", "--abbrev-ref", "HEAD", out="software-factory/onboard\n")
    fake.on("gh", "pr", "list", "-R", REPO, "--head", "software-factory/onboard", out=[])
    fake.on("gh", "pr", "view", "77", "-R", REPO, "--json", _common.PR_FIELDS,
            out=raw_pr(77, head="software-factory/onboard"))
    _common.record(REPO, 0, "reviewed", "o", head_sha=SHA, review="PASS")
    code, out = ship(run, capsys)
    assert out["refused"] == [] and out["opened"][0]["pr"] == 77
    assert not fake.find("gh", "issue", "comment") and not fake.find("gh", "pr", "merge")
    assert any("onboarding" in r for r in out["not_merged"][0]["reasons"])
    body = Path(fake.find("gh", "pr", "create")[0][-1]).read_text()
    assert "Refs #0" not in body and "read from this branch's head" in body


@pytest.mark.parametrize("route,verify,why", [
    (("git", "merge-base", "--is-ancestor", BASE_SHA, "origin/development"), None, "is not on origin/development"),
    (None, {"head_sha": SHA, "base_sha": BASE_SHA, "verdict": "verified",
            "commands_from": ".software-factory/commands.yaml@" + "c" * 40}, "not the base"),
    (("git", "rev-parse", "--abbrev-ref", "HEAD"), None, "the worktree is on"),
])
def test_guard_refusals_on_the_base_commands_and_checkout(fake, run, capsys, route, verify, why):
    if route:
        fake.on(*route, out="other-branch\n" if "--abbrev-ref" in route else "", code=0 if "--abbrev-ref" in route else 1)
    if verify:
        (run / "evidence" / "issue-42" / "verify.json").write_text(json.dumps(verify))
    code, out = ship(run, capsys)
    assert code == 0 and any(why in r for r in out["refused"][0]["reasons"]), out["refused"]
    assert not fake.find("git", "push") and not fake.find("gh", "pr", "create")


def test_update_pushes_with_lease_and_an_open_pr_on_another_base_is_refused(fake, run, capsys):
    edit(run, action="update")
    fake.on("gh", "pr", "list", "-R", REPO, "--head", BRANCH,
            out=[{"number": 77, "url": "https://github.com/acme/widgets/pull/77", "baseRefName": "development",
                  "headRefName": BRANCH}])
    code, out = ship(run, capsys)
    push = fake.find("git", "push")[0]
    assert f"--force-with-lease={BRANCH}" in push and out["updated"][0]["pr"] == 77
    assert not fake.find("gh", "pr", "create")
    fake.calls.clear()
    fake.on("gh", "pr", "list", "-R", REPO, "--head", BRANCH,
            out=[{"number": 77, "baseRefName": "main", "headRefName": BRANCH}])
    code, out = ship(run, capsys)
    assert "targets 'main'" in out["refused"][0]["reasons"][0] and not fake.find("git", "push")


def test_without_an_integration_branch_the_pr_targets_the_default_and_is_never_merged(fake, run, capsys):
    info = json.loads((run / "sync" / "repo.json").read_text())
    info["integration_branch"] = None
    (run / "sync" / "repo.json").write_text(json.dumps(info))
    edit(run, base="main")
    fake.on("git", "merge-base", "--is-ancestor", BASE_SHA, "origin/main", code=0)
    fake.on("gh", "pr", "view", "77", "-R", REPO, "--json", _common.PR_FIELDS, out=dict(raw_pr(77), baseRefName="main"))
    code, out = ship(run, capsys)
    assert out["opened"][0]["pr"] == 77 and not fake.find("gh", "pr", "merge")
    assert any("no integration branch" in r for r in out["not_merged"][0]["reasons"])
    body = Path(fake.find("gh", "pr", "create")[0][-1]).read_text()
    assert "only a person merges it" in body


def test_a_pr_whose_head_is_not_a_factory_branch_is_never_merged(fake, run, capsys):
    (run / "ship" / "manifest.json").write_text(json.dumps({"repo": REPO, "branches": []}))
    (run / "sync" / "prs.json").write_text(json.dumps([{"number": 90}]))
    fake.on("gh", "pr", "view", "90", "-R", REPO, "--json", _common.PR_FIELDS, out=raw_pr(90, head="feature/x"))
    code, out = ship(run, capsys)
    assert out["not_merged"] == [{"pr": 90, "reasons": ["not a factory branch"]}] and not fake.find("gh", "pr", "merge")
