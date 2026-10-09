"""Report the health of every git repository under a directory, in one table.

For each repository found under the root (to --depth levels) it reports the branch,
uncommitted and untracked files, stashes, commits ahead of and behind the upstream, the
remotes, days since the last commit, whether there are tests and whether it is a
worktree, and turns those into flags:

    dirty        uncommitted changes (and so no chore may run in it)
    unpushed     ahead of its upstream, or has commits and a remote but no upstream
    no-remote    nothing to push to, so a disk failure loses it
    stale        no commit in --stale-days (default 90)
    no-tests     no tests folder, pytest configuration or package.json test script
    no-git       a top-level directory under the root that holds no repository

The chore column says what housekeeping could run: never in a dirty tree, and a
repository without tests gets "add the first tests" as its only chore.

Inputs: ROOT, or the setting `repos_root` in the [software-portfolio-review] table.
Prints a text table, or JSON with --format json. Read-only: runs `git` locally and never
fetches. Exits 1 when any repository has no remote or is unpushed, 2 when no root is given.

Example: python3 repo_sweep.py path/to/projects --only-flagged
"""

import argparse
import json
import os
import subprocess
import sys
import time
import tomllib
from datetime import date
from pathlib import Path

TEST_MARKERS = ("tests", "test", "pytest.ini", "conftest.py", "spec", "__tests__")
FLAGS = ("dirty", "unpushed", "no-remote", "stale", "no-tests")


def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


def git(repo, *args):
    """Run one read-only git command in the repository; None when it fails."""
    try:
        out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def has_tests(repo):
    if any((repo / m).exists() for m in TEST_MARKERS):
        return True
    for cfg in ("pyproject.toml", "setup.cfg", "tox.ini"):
        p = repo / cfg
        if p.is_file() and "pytest" in p.read_text(encoding="utf-8", errors="ignore"):
            return True
    pkg = repo / "package.json"
    if pkg.is_file():
        try:
            return "test" in json.loads(pkg.read_text(encoding="utf-8")).get("scripts", {})
        except (json.JSONDecodeError, AttributeError):
            return False
    return False


def inspect(repo, stale_days):
    """One row of the table for one repository."""
    status = git(repo, "status", "--porcelain") or ""
    lines = status.splitlines()
    remotes = (git(repo, "remote") or "").split()
    row = {
        "repo": repo.name,
        "path": str(repo),
        "worktree": (repo / ".git").is_file(),
        "branch": git(repo, "rev-parse", "--abbrev-ref", "HEAD") or "?",
        "modified": sum(1 for l in lines if not l.startswith("??")),
        "untracked": sum(1 for l in lines if l.startswith("??")),
        "stashes": len((git(repo, "stash", "list") or "").splitlines()),
        "remotes": remotes,
    }
    counts = git(repo, "rev-list", "--left-right", "--count", "@{u}...HEAD")
    if counts:
        behind, ahead = (int(x) for x in counts.split())
        row.update(ahead=ahead, behind=behind, upstream=True)
    else:
        row.update(ahead=None, behind=None, upstream=False)
    last = git(repo, "log", "-1", "--format=%ct")
    row["commits"] = int(git(repo, "rev-list", "--count", "HEAD") or 0) if last else 0
    row["last_commit_days"] = round((time.time() - int(last)) / 86400) if last else None
    row["has_tests"] = has_tests(repo)

    flags = []
    if row["modified"] or row["untracked"]:
        flags.append("dirty")
    if (row["ahead"] or 0) > 0 or (row["commits"] and not row["upstream"] and remotes):
        flags.append("unpushed")
    if not remotes:
        flags.append("no-remote")
    if row["last_commit_days"] is not None and row["last_commit_days"] > stale_days:
        flags.append("stale")
    if not row["has_tests"]:
        flags.append("no-tests")
    row["flags"] = flags
    if "dirty" in flags:
        row["chore"] = "skip: uncommitted changes"
    elif not row["has_tests"]:
        row["chore"] = "add the first tests"
    else:
        row["chore"] = "eligible"
    return row


def sweep(root, depth=2, stale_days=90):
    """Walk the root to the given depth; every folder holding .git is a repository."""
    repos, not_git = [], []

    def walk(folder, level):
        try:
            children = sorted(p for p in folder.iterdir() if p.is_dir() and not p.name.startswith("."))
        except OSError:
            return
        for child in children:
            if (child / ".git").exists():
                repos.append(inspect(child, stale_days))
            elif level < depth:
                before = len(repos)
                walk(child, level + 1)
                if len(repos) == before and level == 1:
                    not_git.append(str(child))
            elif level == 1:
                not_git.append(str(child))

    walk(root, 1)
    counts = {f: sum(1 for r in repos if f in r["flags"]) for f in FLAGS}
    counts.update({"no-git": len(not_git), "repos": len(repos)})
    today = date.today().isoformat()
    return {"root": str(root), "date": today, "janitor_branch": f"janitor/{today}",
            "repos": repos, "not_git": not_git, "counts": counts}


def print_table(result, only_flagged):
    c = result["counts"]
    print(f"{result['root']}: {c['repos']} repos, {c['dirty']} dirty, {c['unpushed']} unpushed, "
          f"{c['no-remote']} without remote, {c['stale']} stale, {c['no-tests']} without tests, "
          f"{c['no-git']} dirs not under git")
    print(f"{'repo':30} {'branch':18} {'dirty':>5} {'ahead':>5} {'age d':>5}  flags / chore")
    for row in result["repos"]:
        if only_flagged and not row["flags"]:
            continue
        name = row["repo"] + (" (worktree)" if row["worktree"] else "")
        dirty = row["modified"] + row["untracked"]
        ahead = "" if row["ahead"] is None else str(row["ahead"])
        age = "" if row["last_commit_days"] is None else str(row["last_commit_days"])
        print(f"{name[:30]:30} {row['branch'][:18]:18} {dirty:>5} {ahead:>5} {age:>5}  "
              f"{' '.join(row['flags']) or '-'}  |  {row['chore']}")
    for d in result["not_git"]:
        print(f"{Path(d).name[:30]:30} {'':18} {'':>5} {'':>5} {'':>5}  no-git")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Health table for every git repository under a directory.")
    ap.add_argument("root", nargs="?", help="folder to sweep (default: setting repos_root)")
    ap.add_argument("--depth", type=int, default=2, help="directory levels to search (default 2)")
    ap.add_argument("--stale-days", type=int, default=90)
    ap.add_argument("--only-flagged", action="store_true", help="hide repositories with nothing to fix")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args(argv)

    root = args.root or settings("software-portfolio-review").get("repos_root")
    if not root:
        print("repo_sweep: give ROOT or set repos_root in [software-portfolio-review]", file=sys.stderr)
        return 2
    root = Path(root).expanduser()
    if not root.is_dir():
        print(f"repo_sweep: not a directory: {root}", file=sys.stderr)
        return 2
    result = sweep(root, args.depth, args.stale_days)
    if args.format == "json":
        print(json.dumps(result, indent=1))
    else:
        print_table(result, args.only_flagged)
    return 1 if result["counts"]["no-remote"] or result["counts"]["unpushed"] else 0


if __name__ == "__main__":
    sys.exit(main())
