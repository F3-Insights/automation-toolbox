"""Stage the skill harvest's checked drafts on a new branch of the toolbox for review. It never
merges and never pushes, and it never writes in the live checkout.

Inputs: a Run folder holding `drafts/`, laid out exactly as the files would sit in the toolbox
(`<department>/skills/<name>/SKILL.md` and anything beside it), and optionally `harvest-note.md`,
whose text becomes the commit message's body. The toolbox checkout is --repo, else the `repo`
setting under [skill-harvest-workstream].

What it does:
1. Refuses a Run folder inside any working tree of the toolbox (the live checkout above all), a
   draft that is a symbolic link, and any draft file that is not inside
   `<department>/skills/<name>/` of a department the toolbox already has.
2. Writes the commit message (the harvest note's text) to RUN/commit-message.md and runs the
   skills-extract name check over the drafts and that message (it reads the same private-name
   denylist files the toolbox check reads), with --pack and --names passed through.
3. Adds a worktree at RUN/toolbox on a new branch `skill-harvest/<yyyy-mm-dd>` (`-2`, `-3` when
   taken) from the base (default `main`, else `master`), copies the drafts in, and runs the
   toolbox's own scripts/toolbox_check.py over the copied files. No check script, no commit.
4. Commits the copied files by name in the worktree, after proving it is on the new branch,
   removes the worktree and keeps the branch. The live checkout's files and branch are never
   touched.

Any failure leaves nothing committed and says `REFUSED: ...` on the first line (the worktree is
kept when it was made, for the owner to look at). --dry-run does steps 1 and 2 only. Writes
RUN/branch.json. A denylisted name in anything it prints or stores is written "(withheld)". Exit 0 when it ran (committed, refused or nothing to stage), 2 on a bad argument.

Example:
    python3 skill_harvest_branch.py --run ~/runs/skill-harvest/2026-10 --pack ~/work/pack.json
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from datetime import date
from pathlib import Path

SKILL = "skill-harvest-workstream"
BRANCH_PREFIX = "skill-harvest/"
NAME_CHECK = "~/.claude/skills/skills-extract/scripts/name_check.py"
DEFAULT_DENYLIST = Path("~/.config/f3i-toolbox/denylist.txt").expanduser()


class Refused(Exception):
    """A bad argument: exit 2."""


def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


def load_denylist():
    """The private names the toolbox check reads, as compiled patterns: each file in
    F3I_TOOLBOX_DENYLIST (separated by ":") and ~/.config/f3i-toolbox/denylist.txt; one term per
    line, "#" a comment, "=" case-sensitive, "@" another list file. Used only to withhold names."""
    paths = [Path(p).expanduser() for p in os.environ.get("F3I_TOOLBOX_DENYLIST", "").split(":") if p]
    paths.append(DEFAULT_DENYLIST)
    terms, seen = [], set()
    while paths:
        path = paths.pop(0)
        if not path.is_file() or path.resolve() in seen:
            continue
        seen.add(path.resolve())
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("@"):
                paths.append(Path(line[1:]).expanduser())
                continue
            term = line[1:] if line.startswith("=") else line
            terms.append(re.compile(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", 0 if line.startswith("=") else re.I))
    return terms


def withhold(lines, denylist):
    """The lines with every denylisted name replaced by "(withheld)"."""
    out = []
    for line in lines:
        for rx in denylist:
            line = rx.sub("(withheld)", line)
        out.append(line)
    return out


def git(*args, cwd, check=True):
    done = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False)
    if check and done.returncode != 0:
        raise Refused(f"git {' '.join(args[:3])}: {(done.stderr or done.stdout).strip()[:300]}")
    return done


def draft_files(drafts, repo):
    """Every draft file, relative to the drafts folder, and the problems with where they would land."""
    files, problems = [], []
    for path in sorted(p for p in drafts.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        rel = path.relative_to(drafts)
        parts = rel.parts
        if any(q.is_symlink() for q in [path, *path.parents] if q.is_relative_to(drafts)):
            problems.append(f"{rel}: a symbolic link; drafts are copied as plain files only")
        elif len(parts) < 4 or parts[1] != "skills":
            problems.append(f"{rel}: not inside <department>/skills/<name>/")
        elif not (repo / parts[0]).is_dir():
            problems.append(f"{rel}: the toolbox has no department {parts[0]}")
        files.append(str(rel))
    return files, problems


def free_branch(repo, today):
    name, n = f"{BRANCH_PREFIX}{today}", 1
    while git("rev-parse", "--verify", "--quiet", f"refs/heads/{name}", cwd=repo, check=False).returncode == 0:
        n += 1
        name = f"{BRANCH_PREFIX}{today}-{n}"
    return name


def default_base(repo):
    for name in ("main", "master"):
        if git("rev-parse", "--verify", "--quiet", f"refs/heads/{name}", cwd=repo, check=False).returncode == 0:
            return name
    raise Refused(f"{repo}: no main or master branch; pass --base")


def name_check(script, targets, packs, names):
    argv = [sys.executable, str(script), *map(str, targets)]
    argv += [x for p in packs for x in ("--pack", p)] + [x for n in names for x in ("--names", n)]
    done = subprocess.run(argv, capture_output=True, text=True)
    return done.returncode == 0, (done.stdout + done.stderr).strip()


def worktree_paths(repo):
    """Every working tree of the repository: the live checkout and each linked worktree."""
    out = git("worktree", "list", "--porcelain", cwd=repo).stdout
    return [Path(line[len("worktree "):]).resolve() for line in out.splitlines() if line.startswith("worktree ")]


def stage(run, repo, base=None, packs=(), names=(), checker=NAME_CHECK, dry_run=False, today=None):
    drafts = run / "drafts"
    note = run / "harvest-note.md"
    if not drafts.is_dir() or not any(p.is_file() for p in drafts.rglob("*")):
        return {"state": "nothing", "line": "NOTHING: no drafts in the Run folder; nothing staged"}
    top = Path(git("rev-parse", "--show-toplevel", cwd=repo).stdout.strip()).resolve()
    for tree in [top, *worktree_paths(top)]:
        if run.resolve().is_relative_to(tree):
            raise Refused(f"the Run folder is inside the toolbox's working tree ({tree}); use a Run folder outside it")
    denylist = load_denylist()
    files, problems = draft_files(drafts, top)
    if problems:
        problems = withhold(problems, denylist)
        return {"state": "refused", "files": withhold(files, denylist), "problems": problems, "line": f"REFUSED: {problems[0]}"}
    body = note.read_text(encoding="utf-8").strip() if note.is_file() else ""
    message = f"Stage {len(files)} skill harvest draft file(s) for review\n\n" + (body + "\n\n" if body else "") + \
              f"Skill-Harvest-Run: {run.name}\n"
    message_file = run / "commit-message.md"
    message_file.write_text(message, encoding="utf-8")
    script = Path(checker).expanduser()
    if not script.is_file():
        raise Refused(f"the name check is not at {script}; install the skills-extract skill or pass --name-check")
    ok, output = name_check(script, [drafts, message_file], packs, names)
    if not ok:
        return {"state": "refused", "files": withhold(files, denylist), "problems": withhold(output.splitlines()[:20], denylist),
                "line": "REFUSED: the name check found hits in the drafts or the commit message; nothing staged"}
    if dry_run:
        return {"state": "would-stage", "files": files, "problems": [], "line": f"WOULD STAGE: {len(files)} file(s), name check CLEAN"}
    worktree = run / "toolbox"
    if worktree.exists():
        raise Refused(f"{worktree} already exists; remove it or use a new Run folder")
    base = base or default_base(top)
    branch = free_branch(top, today or date.today().isoformat())
    git("worktree", "add", "-q", "-b", branch, str(worktree), base, cwd=top)
    for rel in files:
        target = worktree / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(drafts / rel, target)
    check = worktree / "scripts" / "toolbox_check.py"
    if not check.is_file():
        return {"state": "refused", "branch": branch, "worktree": str(worktree), "files": files,
                "problems": ["no scripts/toolbox_check.py in the toolbox"],
                "line": f"REFUSED: the toolbox has no check script, so nothing is committed; the worktree {worktree} is left for the owner"}
    done = subprocess.run([sys.executable, str(check), *files], cwd=str(worktree), capture_output=True, text=True)
    if done.returncode != 0:
        return {"state": "refused", "branch": branch, "worktree": str(worktree), "files": files,
                "problems": withhold(done.stdout.strip().splitlines()[:20], denylist),
                "line": f"REFUSED: the toolbox check failed on the drafts; the worktree {worktree} is left for the owner"}
    head = git("symbolic-ref", "--short", "-q", "HEAD", cwd=worktree, check=False).stdout.strip()
    wtop = git("rev-parse", "--show-toplevel", cwd=worktree, check=False).stdout.strip()
    if head != branch or not wtop or Path(wtop).resolve() != worktree.resolve():
        return {"state": "refused", "branch": branch, "worktree": str(worktree), "files": files,
                "problems": [f"the worktree is not on {branch} in its own folder"],
                "line": f"REFUSED: the worktree {worktree} is not on {branch}; nothing committed"}
    git("add", "--", *files, cwd=worktree)
    done = subprocess.run(["git", "commit", "-q", "-F", "-"], cwd=str(worktree), input=message, text=True,
                          capture_output=True, check=False)
    if done.returncode != 0:
        return {"state": "refused", "branch": branch, "worktree": str(worktree), "files": files,
                "problems": withhold([(done.stderr or done.stdout).strip()[:500]], denylist),
                "line": f"REFUSED: git commit failed; the worktree {worktree} is left for the owner"}
    sha = git("rev-parse", "HEAD", cwd=worktree).stdout.strip()
    git("worktree", "remove", "--force", str(worktree), cwd=top)
    return {"state": "committed", "branch": branch, "sha": sha, "base": base, "files": files, "problems": [],
            "line": f"COMMITTED: {sha[:7]} on {branch}, {len(files)} file(s); review it with git -C {top} show {branch}; "
                    f"not merged, not pushed"}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Stage the skill harvest's drafts on a review branch of the toolbox; never merge or push.")
    ap.add_argument("--run", required=True, help="the Run folder holding drafts/ and harvest-note.md")
    ap.add_argument("--repo", help="the toolbox checkout (default: the `repo` setting under [skill-harvest-workstream])")
    ap.add_argument("--base", help="the branch to start from (default main, else master)")
    ap.add_argument("--pack", action="append", default=[], help="a session pack whose private_terms the name check uses; repeatable")
    ap.add_argument("--names", action="append", default=[], help="an owner context or names list for the name check; repeatable")
    ap.add_argument("--name-check", default=NAME_CHECK, help="the name check script (default: the skills-extract skill's)")
    ap.add_argument("--dry-run", action="store_true", help="check the drafts only; make no branch")
    args = ap.parse_args(argv)
    try:
        run = Path(args.run).expanduser()
        if not run.is_dir():
            raise Refused(f"{run} is not a folder")
        repo_value = args.repo or settings(SKILL).get("repo")
        if not repo_value:
            raise Refused(f"no toolbox checkout: pass --repo or set `repo` under [{SKILL}] in the settings file")
        repo = Path(str(repo_value)).expanduser()
        if not repo.is_dir():
            raise Refused(f"{repo} is not a folder")
        result = stage(run, repo, args.base, args.pack, args.names, args.name_check, args.dry_run)
    except Refused as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    (run / "branch.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(result["line"])
    for p in result.get("problems") or []:
        print(f"  {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
