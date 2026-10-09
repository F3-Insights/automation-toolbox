"""software_factory_record.py: upsert by id, attempts, the review rule, and refusals."""

import json
import subprocess
import sys

import _common
from sf_support import REPO, SCRIPTS
from software_factory_record import main

BY = ["--by", "software-factory-orchestrator"]


def test_create_update_and_attempts(env, capsys):
    assert main([REPO, "--issue", "42", "--state", "building", "--branch", "software-factory/issue-42-fix", *BY]) == 0
    assert main([REPO, "--issue", "42", "--state", "verified", "--head-sha", "a" * 40, "--verify", "verified", *BY]) == 0
    rows = _common.read_ledger(REPO)
    assert [r["id"] for r in rows] == ["42:1"]
    assert (rows[0]["state"], rows[0]["branch"], rows[0]["verify"]) == ("verified", "software-factory/issue-42-fix", "verified")
    assert main([REPO, "--issue", "42", "--state", "building", "--new-attempt", *BY]) == 0
    assert _common.latest(_common.read_ledger(REPO))[42]["attempt"] == "2"
    assert main([REPO, "--issue", "42", "--state", "building", "--attempt", "5", *BY]) == 2
    assert "skips ahead" in capsys.readouterr().err


def test_a_new_head_clears_the_review(env):
    main([REPO, "--issue", "7", "--state", "reviewed", "--head-sha", "a" * 40, "--review", "PASS", *BY])
    result = _common.record(REPO, 7, "verified", "orchestrator", head_sha="b" * 40)
    assert result["row"]["review"] == "" and result["warnings"]
    kept = _common.record(REPO, 7, "reviewed", "orchestrator", head_sha="c" * 40, review="pass")
    assert kept["row"]["review"] == "PASS" and not kept["warnings"]


def test_other_rows_keep_their_exact_text(env):
    _common.record(REPO, 1, "triaged-build", "orchestrator", note="first")
    path = _common.ledger_path(REPO)
    path.write_text(path.read_text().replace("first", '"first, with a comma"'))
    before = path.read_text().splitlines()[1]
    _common.record(REPO, 2, "triaged-ask", "orchestrator")
    _common.record(REPO, 2, "skipped", "orchestrator")
    lines = path.read_text().splitlines()
    assert lines[0] == ",".join(_common.COLUMNS) and lines[1] == before and len(lines) == 3


def test_onboarding_title_and_json(env, capsys):
    assert main([REPO, "--issue", "0", "--state", "building", "--branch", "software-factory/onboard",
                 "--title", "Onboarding", "--format", "json", *BY]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["id"] == "0:1" and out["action"] == "created"
    main([REPO, "--issue", "9", "--state", "triaged-build", "--title", "Export   totals wrong", *BY])
    assert _common.read_titles(REPO) == {9: "Export totals wrong"}


def test_bad_arguments_exit_2(env):
    for args in (["--issue", "x", "--state", "building"], ["--issue", "1", "--state", "dreaming"],
                 ["--issue", "1", "--state", "verified", "--verify", "great"],
                 ["--issue", "1", "--state", "verified", "--head-sha", "nope"],
                 ["--issue", "1", "--state", "building", "--attempt", "1", "--new-attempt"]):
        assert main([REPO, *args, *BY]) == 2
    assert main(["not-a-repo", "--issue", "1", "--state", "building", *BY]) == 2


def test_runs_standalone(env):
    out = subprocess.run([sys.executable, str(SCRIPTS / "software_factory_record.py"), REPO, "--issue", "3",
                          "--state", "skipped", *BY], capture_output=True, text=True)
    assert out.returncode == 0 and "created 3:1 (skipped)" in out.stdout
