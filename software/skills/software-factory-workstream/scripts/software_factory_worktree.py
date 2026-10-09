"""Create or reuse the worktree and branch for one issue, from the local clone, offline.

The clone is <repos_dir>/<name>; the worktree is
<repos_dir>/.software-factory-worktrees/<owner>__<name>/issue-<n> on the branch
software-factory/issue-<n>-<slug>. Issue 0 is onboarding: branch software-factory/onboard,
worktree .../issue-0, and no --slug.

The base is --base when given; else the `- Integration branch:` line of the rules file on the
clone's default branch (origin/HEAD), when that branch exists at origin; else development when
origin/development exists; else the default branch. The branch starts at origin/<base> as the
clone last fetched it: this script never fetches (software_factory_sync.py does).

A worktree already at the path on the same branch is reused untouched (it holds the builder's
work in progress). A path holding anything else, or the branch checked out elsewhere, is
refused rather than overwritten. A branch that exists without a worktree is checked out again.

Inputs: OWNER/NAME, --issue, --slug, optional --base. Setting: repos_dir in
[software-factory-workstream] (or $SOFTWARE_FACTORY_REPOS_DIR).
Prints the worktree path, or with --format json {path, branch, base, base_sha, created|reused}.
Exit 0 done, 1 git refused, 2 a bad argument, a missing setting or no local clone.

Example: python3 software_factory_worktree.py acme/widgets --issue 42 --slug "fix date parse" --format json
"""

import argparse
import json
import sys
from pathlib import Path

from _common import (DEFAULT_INTEGRATION, ONBOARD_ISSUE, RULES_FILE, FactoryError, UsageError, branch_name,
                     local_clone, offline_git, rules_fields, split_repo, worktree_path)


def ref_exists(clone, ref):
    return offline_git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", cwd=clone, check=False).returncode == 0


def default_branch(clone):
    """The clone's default branch from origin/HEAD; main or master when origin/HEAD is unset."""
    proc = offline_git("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD", cwd=clone, check=False)
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip().removeprefix("refs/remotes/origin/")
    for name in ("main", "master"):
        if ref_exists(clone, f"origin/{name}"):
            return name
    raise FactoryError(f"{clone}: origin/HEAD is not set and there is no origin/main or origin/master")


def choose_base(clone):
    """The integration branch the rules name, else development, else the default branch."""
    default = default_branch(clone)
    rules = offline_git("show", f"origin/{default}:{RULES_FILE}", cwd=clone, check=False)
    if rules.returncode == 0:
        named = rules_fields(rules.stdout).get("integration branch", "")
        if named and ref_exists(clone, f"origin/{named}"):
            return named
    return DEFAULT_INTEGRATION if ref_exists(clone, f"origin/{DEFAULT_INTEGRATION}") else default


def worktrees(clone):
    """{resolved worktree path: its branch, or ''} from `git worktree list --porcelain`."""
    out, path = {}, None
    for line in offline_git("worktree", "list", "--porcelain", cwd=clone).stdout.splitlines():
        if line.startswith("worktree "):
            path = str(Path(line[len("worktree "):]).resolve())
            out[path] = ""
        elif line.startswith("branch ") and path:
            out[path] = line[len("branch "):].removeprefix("refs/heads/")
    return out


def make_worktree(repo, issue, slug=None, base=None):
    clone = local_clone(repo)
    if not (clone / ".git").exists():
        raise UsageError(f"no local clone of {repo} at {clone}")
    if issue < 0:
        raise UsageError("--issue must be an issue number, or 0 for onboarding")
    if issue != ONBOARD_ISSUE and not (slug or "").strip():
        raise UsageError("--slug is required for an issue (only onboarding, issue 0, goes without)")
    branch = branch_name(issue, slug)
    base = (base or "").removeprefix("origin/") or choose_base(clone)
    if not ref_exists(clone, f"origin/{base}"):
        raise UsageError(f"origin/{base} does not exist in {clone} (the sync step fetches)")
    base_sha = offline_git("rev-parse", f"origin/{base}^{{commit}}", cwd=clone).stdout.strip()
    path = worktree_path(repo, issue)
    offline_git("worktree", "prune", cwd=clone)
    known = worktrees(clone)
    result = {"path": str(path), "branch": branch, "base": base, "base_sha": base_sha}
    if path.exists():
        here = known.get(str(path.resolve()))
        if here is None:
            raise FactoryError(f"{path} exists and is not a worktree of {clone}; move it away first")
        if here != branch:
            raise FactoryError(f"{path} is a worktree on {here or 'a detached HEAD'}, not {branch}")
        return {**result, "reused": True}
    elsewhere = [p for p, b in known.items() if b == branch]
    if elsewhere:
        raise FactoryError(f"{branch} is already checked out at {elsewhere[0]}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if ref_exists(clone, f"refs/heads/{branch}"):
        offline_git("worktree", "add", str(path), branch, cwd=clone)
    else:
        offline_git("worktree", "add", "--no-track", "-b", branch, str(path), f"origin/{base}", cwd=clone)
    return {**result, "created": True}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Create or reuse one issue's worktree and branch, offline.")
    ap.add_argument("repo", help="OWNER/NAME")
    ap.add_argument("--issue", required=True, type=int, help="the issue number; 0 for onboarding")
    ap.add_argument("--slug", help="a few words for the branch name; not used for issue 0")
    ap.add_argument("--base", help="the base branch (default: the integration branch)")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args(argv)
    try:
        split_repo(args.repo)
        result = make_worktree(args.repo, args.issue, args.slug, args.base)
    except UsageError as exc:
        print(f"software_factory_worktree: {exc}", file=sys.stderr)
        return 2
    except FactoryError as exc:
        print(f"software_factory_worktree: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=1) if args.format == "json" else result["path"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
