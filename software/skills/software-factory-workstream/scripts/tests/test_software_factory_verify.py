"""software_factory_verify.py: the base's declared checks, offline, the repro and diff coverage."""

import json
import sys
from pathlib import Path

from sf_support import commit, sh
from software_factory_verify import main, parse_minimum

PY = sys.executable
CALC = "def total(lines):\n    return sum(lines[1:])\n"
CALC_FIXED = "def total(lines):\n    return sum(lines)\n"


def repo(env, commands, rules=""):
    """A repo whose main has the commands (and rules), and a branch `fix` one commit ahead."""
    root = env / "wt"
    sh("git", "init", "-q", "-b", "main", str(root), cwd=env)
    files = {"calc.py": CALC, ".software-factory/commands.yaml": commands}
    if rules:
        files[".software-factory/SOFTWARE-FACTORY-RULES.md"] = rules
    base = commit(root, files, "base")
    sh("git", "checkout", "-q", "-b", "software-factory/issue-1-fix", cwd=root)
    return root, base


def verify(env, root, base, *extra):
    out = env / "evidence" / "verify.json"
    code = main([str(root), "--base", base, "--out", str(out), *extra])
    return code, json.loads(out.read_text()) if out.exists() else None


def test_verified_with_repro(env):
    root, base = repo(env, f'test: "{PY} -c \\"import calc; assert calc.total([1, 2]) == 3\\""\nlint: "true"\n')
    head = commit(root, {"calc.py": CALC_FIXED}, "fix")
    code, v = verify(env, root, base, "--repro", f"{PY} -c \"import calc; assert calc.total([5]) == 5\"")
    assert code == 0 and v["verdict"] == "verified", v["notes"]
    assert v["head_sha"] == head and v["commands_from"] == f".software-factory/commands.yaml@{base}"
    assert [s["name"] for s in v["steps"]] == ["test"]            # the placeholder lint is no command
    assert (v["repro"]["base_exit"], v["repro"]["head_exit"]) == (1, 0)


def test_a_branch_cannot_change_its_own_checks(env):
    root, base = repo(env, "test: \"test -f missing.txt\"\n")
    commit(root, {".software-factory/commands.yaml": "test: \"test -f calc.py\"\n"}, "cheat")
    code, v = verify(env, root, base)
    assert v["verdict"] == "failed" and v["steps"][0]["run"] == "test -f missing.txt"


def test_no_tests(env):
    root, base = repo(env, "lint: \"echo hi\"\ntest: \"true\"\n")
    assert verify(env, root, base)[1]["verdict"] == "no-tests"


def test_dirty_tree_and_repro_not_shown(env):
    root, base = repo(env, "test: \"test -f calc.py\"\n")
    (root / "scratch.txt").write_text("x")
    code, v = verify(env, root, base)
    assert v["verdict"] == "failed" and "uncommitted" in v["notes"][0]
    (root / "scratch.txt").unlink()
    code, v = verify(env, root, base, "--repro", "test -f calc.py")
    assert v["verdict"] == "repro-not-shown" and (v["repro"]["base_exit"], v["repro"]["head_exit"]) == (0, 0)


def test_commands_from_head_only_on_onboarding(env, capsys):
    root, base = repo(env, "test: \"test -f calc.py\"\n")
    assert main([str(root), "--base", base, "--commands-from", "head", "--out", str(env / "v.json")]) == 2
    sh("git", "checkout", "-q", "-b", "software-factory/onboard", cwd=root)
    code, v = verify(env, root, base, "--commands-from", "head")
    assert v["commands_from"].endswith("@" + v["head_sha"]) and "onboarding" in v["notes"][0]


WRITE_COV = ("import json\n"
             "json.dump({'files': {'calc.py': {'executed_lines': [1], 'missing_lines': [2]}}},"
             " open('coverage.json', 'w'))\n")


def test_diff_coverage_against_the_minimum(env):
    commands = f"test: \"test -f calc.py\"\ncoverage: \"{PY} write_cov.py\"\n"
    root, base = repo(env, commands, rules="- Minimum diff coverage: 80%\n")
    commit(root, {"calc.py": CALC_FIXED, "write_cov.py": WRITE_COV, ".gitignore": "coverage.json\n"}, "fix")
    code, v = verify(env, root, base)
    dc = v["diff_coverage"]
    assert (dc["covered"], dc["total"], dc["minimum"], dc["format"]) == (0, 1, 80.0, "coverage.py")
    assert dc["files"][0]["uncovered"] == [2]
    assert v["verdict"] == "failed" and "below the rules' minimum" in " ".join(v["notes"])


def test_parse_minimum_and_bad_arguments(env):
    assert (parse_minimum("80%"), parse_minimum("72.5 %"), parse_minimum("lots")) == (80.0, 72.5, None)
    root, base = repo(env, "test: \"test -f calc.py\"\n")
    assert main([str(root), "--base", base, "--steps", "dance"]) == 2
    assert main([str(root), "--base", "no-such-ref", "--out", str(env / "v.json")]) == 2
    assert main([str(root), "--base", base, "--out", str(root / "v.json")]) == 2


def test_guards_timeout_cwd_outside_and_no_token(env, monkeypatch):
    """A step that runs too long is killed (exit 124), a cwd outside the worktree never runs
    (exit 126), and a step sees no GitHub token."""
    monkeypatch.setenv("GH_TOKEN", "ghp_should_not_leak")
    monkeypatch.setenv("GITHUB_TOKEN", "should_not_leak")
    commands = ('setup: "test -z \\"$GH_TOKEN$GITHUB_TOKEN\\""\n'
                'lint: {run: "true; touch escaped", cwd: "../.."}\n'
                'test: "sleep 30"\n')
    root, base = repo(env, commands)
    code, v = verify(env, root, base, "--timeout-s", "1")
    steps = {s["name"]: s for s in v["steps"]}
    assert code == 0 and v["verdict"] == "failed"
    assert steps["setup"]["exit"] == 0                       # no token reached the step
    assert steps["lint"]["exit"] == 126 and not (env.parent / "escaped").exists()
    assert steps["test"]["exit"] == 124 and steps["test"]["seconds"] < 20
