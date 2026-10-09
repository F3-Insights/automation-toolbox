"""repo_sweep.py: flags, the chore column and the exit code, over tiny local git repos."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
from repo_sweep import inspect, sweep  # noqa: E402

GIT_ENV = {"GIT_AUTHOR_NAME": "Dana", "GIT_AUTHOR_EMAIL": "dana@example.com",
           "GIT_COMMITTER_NAME": "Dana", "GIT_COMMITTER_EMAIL": "dana@example.com"}


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                   text=True, env={**os.environ, **GIT_ENV})


def new_repo(path, files):
    path.mkdir(parents=True)
    git(path, "init", "-q")
    for name, text in files.items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_text(text)
    git(path, "add", ".")
    git(path, "commit", "-q", "-m", "first")
    return path


@pytest.fixture
def projects(tmp_path):
    root = tmp_path / "projects"
    root.mkdir()
    new_repo(root / "acme-ledger", {"README.md": "x\n", "tests/test_a.py": "def test_a(): pass\n"})
    dirty = new_repo(root / "northwind-site", {"README.md": "x\n"})
    (dirty / "README.md").write_text("changed\n")
    (dirty / "notes.txt").write_text("new\n")
    bare = root / "upstream.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True, capture_output=True)
    pushed = new_repo(root / "fabrikam-api", {"README.md": "x\n"})
    git(pushed, "remote", "add", "origin", str(bare))
    git(pushed, "push", "-q", "-u", "origin", "HEAD")
    (pushed / "more.txt").write_text("more\n")
    git(pushed, "add", "more.txt")
    git(pushed, "commit", "-q", "-m", "second")
    return root


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPTS / "repo_sweep.py"), *args],
                          capture_output=True, text=True,
                          env={**os.environ, "F3I_TOOLBOX_SETTINGS": "/nonexistent.toml"})


def test_rows(projects):
    clean = inspect(projects / "acme-ledger", 90)
    assert clean["has_tests"] and clean["flags"] == ["no-remote"] and clean["chore"] == "eligible"
    dirty = inspect(projects / "northwind-site", 90)
    assert (dirty["modified"], dirty["untracked"]) == (1, 1)
    assert "dirty" in dirty["flags"] and dirty["chore"] == "skip: uncommitted changes"
    ahead = inspect(projects / "fabrikam-api", 90)
    assert (ahead["ahead"], ahead["behind"], ahead["upstream"]) == (1, 0, True)
    assert "unpushed" in ahead["flags"] and "no-remote" not in ahead["flags"]
    assert "stale" in inspect(projects / "acme-ledger", -1)["flags"]


def test_sweep_counts_and_not_git(projects):
    (projects / "loose-folder").mkdir()
    result = sweep(projects)
    assert {r["repo"] for r in result["repos"]} == {"acme-ledger", "northwind-site", "fabrikam-api"}
    assert result["counts"]["no-remote"] == 2 and result["counts"]["unpushed"] == 1
    assert str(projects / "loose-folder") in result["not_git"]


def test_cli_json_and_exit_code(projects):
    out = run(str(projects), "--format", "json")
    assert out.returncode == 1
    assert json.loads(out.stdout)["counts"]["repos"] == 3


def test_cli_text_table(projects):
    out = run(str(projects), "--only-flagged")
    assert "skip: uncommitted changes" in out.stdout and "northwind-site" in out.stdout


def test_missing_root_needs_setting():
    out = run()
    assert out.returncode == 2 and "repos_root" in out.stderr
