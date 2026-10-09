# /// script
# dependencies = ["pyyaml"]
# ///
"""Make, check and commit the toolbox audit's fix branch. It never merges and never pushes.

    toolbox_audit_fix.py open   --run RUN [--repo TOOLBOX] [--base BRANCH]
    toolbox_audit_fix.py verify --run RUN [--format text|json]
    toolbox_audit_fix.py commit --run RUN [--dry-run | --dry-run-if VALUE]

The repository is --repo, else the `repo` setting under [toolbox-audit-workstream]. Edits happen
only in a worktree inside the Run folder, never in the live checkout.

open (before the session) adds a worktree at RUN/toolbox on a new branch
`toolbox-audit/fixes-<yyyy-mm-dd>` (`-2`, `-3` when that exists) from the base (default the
repository's `main`, else `master`), offline, and writes RUN/fix-branch.json. It refuses a Run
folder inside any working tree of the repository. A worktree already made for this Run is reused.
verify and commit first prove fix-branch.json names RUN/toolbox, a linked worktree (never the live
checkout) on its own toolbox-audit/fixes-* branch, and refuse otherwise. Private names in what
they print or store are replaced by "(withheld)".
First line `FRESH: ...`; exit 0, 1 when git refuses, 2 on a bad argument.

verify checks the worktree's changes against the fix rule (see _common.py) and the Run's
findings.json: `PASS`, `FAIL` with each problem, or `NOTHING` when nothing changed. Exit 0 on PASS
or NOTHING, 1 on FAIL.

commit (after a session that ended done) verifies again, requires every changed file to belong to
a finding marked fixed with the checker's PASS and the commit message to carry no private name, and
runs the toolbox's own scripts/toolbox_check.py over the changed files in the worktree (no check
script, no commit); then it commits those files by name on the branch with the Run's findings in
the message, and removes the worktree; the branch stays for review. Nothing changed: the worktree and the empty branch are removed. A diff that breaks the
rule or the check is never committed: the worktree is left and the first line says `REFUSED`.
Writes RUN/fix-commit.json (RUN/fix-commit-dry-run.json on a dry run, which verifies only).
Exit 0 when it ran, 2 on a bad argument.

Example:
    python3 toolbox_audit_fix.py open --run ~/runs/toolbox-audit/2026-10-05
"""

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import _common as c

BRANCH_PREFIX = "toolbox-audit/fixes-"
WORKTREE = "toolbox"


def default_base(repo):
    for name in ("main", "master"):
        if c.git("rev-parse", "--verify", "--quiet", f"refs/heads/{name}", cwd=repo, check=False).returncode == 0:
            return name
    raise c.AuditError(f"{repo}: no main or master branch; pass --base")


def free_branch(repo, today):
    name, n = f"{BRANCH_PREFIX}{today}", 1
    while c.git("rev-parse", "--verify", "--quiet", f"refs/heads/{name}", cwd=repo, check=False).returncode == 0:
        n += 1
        name = f"{BRANCH_PREFIX}{today}-{n}"
    return name


def open_worktree(run, repo, base=None, today=None):
    info = c.read_json(run / "fix-branch.json")
    worktree = run / WORKTREE
    if info and worktree.is_dir():
        return {**worktree_info(run), "reused": True}
    if worktree.exists():
        raise c.AuditError(f"{worktree} exists and is not this Run's fix worktree; nothing done")
    top = c.refuse_run_inside(run, repo)
    base = base or default_base(repo)
    base_sha = c.git("rev-parse", "--verify", f"{base}^{{commit}}", cwd=repo).stdout.strip()
    branch = free_branch(repo, today or date.today().isoformat())
    c.git("worktree", "add", "-b", branch, str(worktree), base_sha, cwd=repo)
    info = {"repo": str(top), "worktree": str(worktree), "branch": branch, "base": base, "base_sha": base_sha, "created": True}
    c.write_json(run / "fix-branch.json", info)
    return info


def worktree_info(run):
    """The Run's fix worktree from fix-branch.json, or None when there is none. Before anything
    edits, commits or removes, it proves the worktree is RUN/toolbox, a linked worktree of the
    repository (never its live checkout), on this Run's own toolbox-audit/fixes-* branch."""
    info = c.read_json(run / "fix-branch.json")
    if not info or not Path(info.get("worktree") or "").is_dir():
        return None
    worktree, expected = Path(info["worktree"]).resolve(), (run / WORKTREE).resolve()
    branch = str(info.get("branch") or "")
    if worktree != expected:
        raise c.AuditError(f"fix-branch.json names {worktree}, not this Run's worktree {expected}; nothing done")
    if not branch.startswith(BRANCH_PREFIX):
        raise c.AuditError(f"fix-branch.json names the branch '{branch}', not a {BRANCH_PREFIX}* branch; nothing done")
    top = c.git("rev-parse", "--show-toplevel", cwd=worktree, check=False).stdout.strip()
    if not top or Path(top).resolve() != expected:
        raise c.AuditError(f"{expected} is not a git worktree of its own; nothing done")
    trees = c.worktree_paths(Path(info.get("repo") or worktree))
    if expected not in trees[1:]:
        raise c.AuditError(f"{expected} is not a linked worktree of {info.get('repo')} (or it is the live checkout); nothing done")
    head = c.git("symbolic-ref", "--short", "-q", "HEAD", cwd=worktree, check=False).stdout.strip()
    if head != branch:
        raise c.AuditError(f"the worktree is on '{head or 'a detached HEAD'}', not {branch}; nothing done")
    return info


def message(run, files):
    fixed = [f for f in c.findings_of(run) if f.get("state") == "fixed" and set(f.get("files") or []) & set(files)]
    lines = [f"Fix {len(files)} agent and skill frontmatter lint(s) from the toolbox audit", "",
             "Made under the toolbox audit's fix rule: only frontmatter name and description, each file a finding "
             "the session marked fixed and the checker passed. For review; never merged.", ""]
    lines += [f"- {', '.join(f.get('files') or [])}: {c.one_line(f.get('title') or f.get('id'))}" for f in fixed]
    return "\n".join(lines + ["", f"Toolbox-Audit-Run: {run.name}"]) + "\n"


def toolbox_check(worktree, files):
    """The toolbox's own check over the changed files: (ok, its output)."""
    script = worktree / "scripts" / "toolbox_check.py"
    if not script.is_file():
        return False, "no scripts/toolbox_check.py in the worktree; nothing is committed without the toolbox check"
    done = subprocess.run([sys.executable, str(script), *files], cwd=str(worktree), capture_output=True, text=True)
    return done.returncode == 0, (done.stdout + done.stderr).strip()


def commit(run, dry_run):
    info = worktree_info(run)
    if info is None:
        return {"committed": False, "state": "no-worktree", "files": [], "problems": [],
                "line": "NOTHING: no fix worktree for this Run (a dry run, or open did not run)"}
    worktree, repo, branch = Path(info["worktree"]), Path(info["repo"]), info["branch"]
    denylist = c.load_denylist()
    files, problems = c.verify_fix(run, worktree, denylist)
    if not files:
        if not dry_run:
            c.git("worktree", "remove", "--force", str(worktree), cwd=repo)
            c.git("branch", "-D", branch, cwd=repo, check=False)
        return {"committed": False, "state": "nothing", "branch": branch, "files": [], "problems": [],
                "line": "NOTHING: no fix was made; the worktree and its empty branch are " + ("kept (dry run)" if dry_run else "removed")}
    passed = {str(p) for f in c.findings_of(run) if f.get("state") == "fixed" and str(f.get("review") or "").upper() == "PASS"
              for p in (f.get("files") or [])}
    problems += [f"{rel}: no finding marked fixed with the checker's PASS names it" for rel in files if rel not in passed]
    text = message(run, files)
    if c.name_hits(text, denylist) or c.HOME_PATH.search(text):
        problems.append("the commit message (finding titles or the Run folder's name) carries a private name or a home path")
    if not problems:
        ok, output = toolbox_check(worktree, files)
        if not ok:
            problems = [line for line in output.splitlines() if line.strip()][:20]
    if problems:
        problems = c.scrub(problems, denylist)
        return {"committed": False, "state": "refused", "branch": branch, "worktree": str(worktree), "files": files,
                "problems": problems, "line": f"REFUSED: {len(problems)} problem(s); nothing committed, the worktree "
                                              f"{worktree} is left for the owner (first: {problems[0]})"}
    if dry_run:
        return {"committed": False, "state": "would-commit", "branch": branch, "files": files, "problems": [],
                "line": f"WOULD COMMIT: {len(files)} file(s) on {branch}"}
    c.git("add", "--", *files, cwd=worktree)
    done = subprocess.run(["git", "commit", "-q", "-F", "-"], cwd=str(worktree), input=text,
                          text=True, capture_output=True, check=False)
    if done.returncode != 0:
        return {"committed": False, "state": "commit-failed", "branch": branch, "files": files,
                "problems": c.scrub([(done.stderr or done.stdout).strip()[:500]], denylist),
                "line": f"REFUSED: git commit failed; the worktree {worktree} is left for the owner"}
    sha = c.git("rev-parse", "HEAD", cwd=worktree).stdout.strip()
    leftover = c.git("status", "--porcelain", cwd=worktree).stdout.strip()
    if not leftover:
        c.git("worktree", "remove", "--force", str(worktree), cwd=repo)
    return {"committed": True, "state": "committed", "branch": branch, "sha": sha, "base": info.get("base"),
            "files": files, "problems": [], "worktree_kept": bool(leftover),
            "line": f"COMMITTED: {sha[:7]} on {branch}, {len(files)} file(s); review it with git -C {repo} show {branch}; "
                    f"not merged, not pushed"}


def main(argv=None):
    ap = argparse.ArgumentParser(description="The toolbox audit's fix branch: open, verify, commit. Never merges or pushes.")
    sub = ap.add_subparsers(dest="command", required=True)
    op = sub.add_parser("open", help="make the Run's worktree on a new toolbox-audit/fixes-<date> branch")
    op.add_argument("--run", required=True)
    op.add_argument("--repo", help="the toolbox checkout (default: the `repo` setting under [toolbox-audit-workstream])")
    op.add_argument("--base", help="the branch to start from (default main, else master)")
    ve = sub.add_parser("verify", help="check the worktree's changes against the fix rule and the Run's findings")
    ve.add_argument("--run", required=True)
    ve.add_argument("--format", choices=["text", "json"], default="text")
    co = sub.add_parser("commit", help="commit the Run's passing fixes on its branch; never merge or push")
    co.add_argument("--run", required=True)
    co.add_argument("--dry-run", action="store_true", help="verify only; commit nothing")
    co.add_argument("--dry-run-if", default="", help="a runner's dry-run value: true means --dry-run")
    args = ap.parse_args(argv)
    try:
        run = c.run_folder(args.run)
        if args.command == "open":
            info = open_worktree(run, c.toolbox_repo(args.repo), args.base)
            print(f"FRESH: fix worktree {'reused' if info.get('reused') else 'made'} at {info['worktree']} on "
                  f"{info['branch']} from {info['base']} {info['base_sha'][:7]}")
            return 0
        if args.command == "verify":
            info = worktree_info(run)
            denylist = c.load_denylist()
            files, problems = c.verify_fix(run, Path(info["worktree"]), denylist) if info else ([], [])
            files, problems = c.scrub(files, denylist), c.scrub(problems, denylist)
            verdict = "NOTHING" if not files else ("PASS" if not problems else "FAIL")
            if args.format == "json":
                print(json.dumps({"verdict": verdict, "files": files, "problems": problems}, indent=2))
            else:
                print(f"{verdict}: {len(files)} file(s) changed" + (f", {len(problems)} problem(s)" if problems else ""))
                for p in problems:
                    print(f"  {p}")
                for f in files:
                    print(f"  changed: {f}")
            return 1 if verdict == "FAIL" else 0
        dry = args.dry_run or c.truthy(args.dry_run_if)
        result = commit(run, dry)
        c.write_json(run / ("fix-commit-dry-run.json" if dry else "fix-commit.json"), result)
        print(result["line"])
        for p in result.get("problems") or []:
            print(f"  {p}")
        return 0
    except c.AuditError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1 if "git " in str(exc) else 2


if __name__ == "__main__":
    sys.exit(main())
