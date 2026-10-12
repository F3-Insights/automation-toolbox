"""Merge one agent pull request into the integration branch, and refuse anything else.

The issue loop's lead merges verified agent PRs with this command instead of `gh pr merge`,
because nothing else stops a merge into production: branch protection is not available on
every plan, and a permission rule cannot see a PR's base. Reads through the gh CLI (signed
in), then merges only when all of these hold:

- the PR is open, not a draft, and carries the label `ai-agent`;
- its base is not the repository's default branch, nor main, master, prod or production;
- its base is the integration branch (`development` unless --integration names another);
- every check has passed (none pending or failed), and the PR has no merge conflict.

    software-pr-merge N -R OWNER/REPO [--integration development] [--strategy squash] [--dry-run]

The merge pins the head commit the checks ran on (--match-head-commit), so a push after the
read is not merged unchecked. The strategy defaults to squash; the design rules (F3-BRANCH)
name none. --allow-no-checks merges a PR in a repository with no checks at all.

Exit 0 merged (or, with --dry-run, would merge); 1 refused, with one line saying why;
2 when gh is missing or a gh call fails.
"""

import argparse
import json
import subprocess
import sys

LABEL = "ai-agent"
PRODUCTION = {"main", "master", "prod", "production"}
PASSED = {"SUCCESS", "SKIPPED", "NEUTRAL"}
PENDING = {"PENDING", "IN_PROGRESS", "QUEUED", "EXPECTED", "WAITING", "REQUESTED"}
FIELDS = "number,state,isDraft,baseRefName,headRefName,headRefOid,labels,statusCheckRollup,mergeable"


class GhError(Exception):
    pass


def gh(*args):
    """Run gh and return its stdout; the one place the command touches GitHub (tests replace it)."""
    try:
        out = subprocess.run(["gh", *args], capture_output=True, text=True)
    except FileNotFoundError:
        raise GhError("gh is not installed")
    if out.returncode:
        raise GhError(out.stderr.strip() or f"gh {args[0]} {args[1]} failed")
    return out.stdout


def check_states(rollup):
    """Split the PR's checks into (failed names, pending names); both empty means all passed."""
    failed, pending = [], []
    for c in rollup or []:
        name = c.get("name") or c.get("context") or "a check"
        state = (c.get("conclusion") or c.get("state") or "").upper()
        if not state or state in PENDING or (c.get("status") or "COMPLETED").upper() != "COMPLETED":
            pending.append(name)
        elif state not in PASSED:
            failed.append(name)
    return failed, pending


def refusal(pr, default, integration, allow_no_checks):
    """Why this PR must not be merged, or None when it may."""
    n, base = pr["number"], pr["baseRefName"]
    if pr.get("state") != "OPEN":
        return f"PR #{n} is {str(pr.get('state')).lower()}, not open"
    if pr.get("isDraft"):
        return f"PR #{n} is a draft"
    if LABEL not in {lb["name"] for lb in pr.get("labels") or []}:
        return f"PR #{n} has no '{LABEL}' label; only agent PRs are merged here"
    if base == default:
        return f"PR #{n} targets {base}, the default branch; promotion belongs to a person"
    if base.lower() in PRODUCTION:
        return f"PR #{n} targets {base}, a production branch; promotion belongs to a person"
    if base != integration:
        return f"PR #{n} targets {base}, not the integration branch {integration}"
    if pr.get("mergeable") == "CONFLICTING":
        return f"PR #{n} has a merge conflict with {base}"
    rollup = pr.get("statusCheckRollup") or []
    if not rollup and not allow_no_checks:
        return f"PR #{n} has no checks; pass --allow-no-checks only for a repository without CI"
    failed, pending = check_states(rollup)
    if failed:
        return f"PR #{n} has failed checks: {', '.join(failed)}"
    if pending:
        return f"PR #{n} has checks still pending: {', '.join(pending)}"
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("number", type=int, help="the pull request number")
    ap.add_argument("-R", "--repo", required=True, help="OWNER/REPO")
    ap.add_argument("--integration", default="development", help="the integration branch (default development)")
    ap.add_argument("--strategy", choices=["squash", "merge", "rebase"], default="squash")
    ap.add_argument("--allow-no-checks", action="store_true", help="merge even though the PR has no checks")
    ap.add_argument("--dry-run", action="store_true", help="say what would happen, merge nothing")
    a = ap.parse_args(argv)

    try:
        pr = json.loads(gh("pr", "view", str(a.number), "-R", a.repo, "--json", FIELDS))
        default = json.loads(gh("repo", "view", a.repo, "--json", "defaultBranchRef"))["defaultBranchRef"]["name"]
    except GhError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    why = refusal(pr, default, a.integration, a.allow_no_checks)
    if why:
        print(f"refused: {why}")
        return 1
    what = f"PR #{a.number} ({pr['headRefName']} -> {pr['baseRefName']}) in {a.repo} by {a.strategy}"
    if a.dry_run:
        print(f"would merge {what}")
        return 0
    try:
        gh("pr", "merge", str(a.number), "-R", a.repo, f"--{a.strategy}", "--match-head-commit", pr["headRefOid"])
    except GhError as exc:
        print(f"error: the merge failed: {exc}", file=sys.stderr)
        return 2
    print(f"merged {what}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
