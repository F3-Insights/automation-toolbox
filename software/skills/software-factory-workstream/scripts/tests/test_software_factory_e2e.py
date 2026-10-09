"""One issue end to end on real git: sync, worktree, record, verify, ship into a bare origin, then
check. Only gh is faked; git runs for real against a local bare repository."""

import json
import subprocess
import sys
from pathlib import Path

import _common
import software_factory_check
import software_factory_record
import software_factory_ship
import software_factory_sync
import software_factory_verify
import software_factory_worktree
from sf_support import OWNER, REPO, Fake, commit, make_origin

PY = sys.executable
RULES = "# Factory rules\n\n- Integration branch: development\n- Auto-merge: yes\n- Release PR: no\n"
COMMANDS = f'test: "{PY} -c \\"import orders; assert orders.total([2, 3]) == 5\\""\n'
ORDERS = "def total(lines):\n    return sum(lines[1:])\n"
ORDERS_FIXED = "def total(lines):\n    return sum(lines)\n"
REPRO = f'{PY} -c "import orders; assert orders.total([4]) == 4"'
BY = ["--by", "software-factory-orchestrator"]


def test_issue_to_pull_request(env, monkeypatch, capsys):
    origin, clone = make_origin(env, {"orders.py": ORDERS, ".software-factory/commands.yaml": COMMANDS,
                                      ".software-factory/SOFTWARE-FACTORY-RULES.md": RULES})
    # The base itself fails the declared test; that is the bug the issue reports.
    fake = Fake(real=_common.run)
    monkeypatch.setattr(_common, "run", fake)
    fake.on("gh", "repo", "view", out={"defaultBranchRef": {"name": "main"}})
    fake.on("gh", "api", "user", out=OWNER + "\n")
    fake.on("gh", "api", out=[])
    fake.on("gh", "issue", "list", out=[{"number": 7, "title": "Order total skips the first line", "body": "",
                                         "labels": [], "assignees": [], "author": {"login": OWNER}, "comments": []}])
    fake.on("gh", "pr", "list", out=[])
    fake.on("gh", "run", "list", out=[])
    fake.on("gh", "label", "list", out=[])
    fake.on("gh", "label", "create", out="")
    fake.on("gh", "pr", "create", out="https://github.com/acme/widgets/pull/90\n")
    fake.on("gh", "pr", "edit", out="")
    fake.on("gh", "issue", "comment", out="")
    fake.on("gh", "pr", "view", out={"comments": [], "reviews": []})
    run = env / "run"

    assert software_factory_sync.main([REPO, "7", "--out", str(run / "sync")]) == 0
    assert capsys.readouterr().out.startswith("SYNCED: 1 issues, 0 factory PRs, CI none")
    assert fake.find("git", "fetch", "origin", "--prune")

    assert software_factory_worktree.main([REPO, "--issue", "7", "--slug", "order total", "--format", "json"]) == 0
    made = json.loads(capsys.readouterr().out)
    software_factory_record.main([REPO, "--issue", "7", "--state", "building", "--branch", made["branch"], *BY])
    head = commit(Path(made["path"]), {"orders.py": ORDERS_FIXED}, "Count every line")

    out = run / "evidence" / "issue-7" / "verify.json"
    assert software_factory_verify.main([made["path"], "--base", made["base_sha"], "--repro", REPRO,
                                         "--out", str(out)]) == 0
    v = json.loads(out.read_text())
    assert v["verdict"] == "verified", v["notes"]
    (out.parent / "review.json").write_text(json.dumps({"review": "PASS", "head_sha": head}))
    software_factory_record.main([REPO, "--issue", "7", "--state", "reviewed", "--head-sha", head,
                                  "--verify", "verified", "--review", "PASS", "--risk", "low", *BY])
    (run / "ship").mkdir()
    (run / "ship" / "pr-7.md").write_text("Count every line in the order total.\n")
    (run / "ship" / "manifest.json").write_text(json.dumps({"repo": REPO, "branches": [{
        "issue": 7, "branch": made["branch"], "worktree": made["path"], "head_sha": head, "base": "development",
        "title": "Count every line", "body_file": "ship/pr-7.md", "verify_file": "evidence/issue-7/verify.json",
        "review_file": "evidence/issue-7/review.json", "risk": "low", "action": "open"}]}))
    capsys.readouterr()

    assert software_factory_ship.main([REPO, "--run", str(run), "--format", "json"]) == 0
    shipped = json.loads(capsys.readouterr().out)
    assert shipped["refused"] == [] and shipped["opened"][0]["pr"] == 90
    pushed = subprocess.run(["git", "--git-dir", str(origin), "rev-parse", f"refs/heads/{made['branch']}"],
                            capture_output=True, text=True).stdout.strip()
    assert pushed == head
    assert software_factory_check.main([REPO, "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["counts"] == {"pr-open": 1}
