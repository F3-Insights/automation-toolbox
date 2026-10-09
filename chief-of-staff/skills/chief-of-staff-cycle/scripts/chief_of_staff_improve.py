#!/usr/bin/env python3
"""chief-of-staff-improve: guard, apply and commit the cycle's one improvement to a doer's
instructions, on a branch of the repository the owner names, never in a live checkout.

    check CYCLE_DIR                      may the improvement in decision.json be applied, or proposed?
    apply CYCLE_DIR --result FILE [--dry-run]   make the improver's one edit and commit it on the branch

At most one small edit per cycle, committed on a branch, to the SKILL.md of a doer skill the
owner's registry runs (the decide check already kept only such a target). The setting
improvements chooses what happens:
- "off": nothing is applied or proposed (check answers none).
- "propose" (the default): check answers proposed and the receipt files the change as a
  decision task for the owner to apply or drop. Nothing is edited.
- "commit": the edit is made and committed, but only in a separate git worktree of the
  repository the setting improve_repo names, on the branch improve_branch (default
  chief-of-staff/improvements), kept at <state>/improve-worktree. The repository's own
  checkout is never touched and nothing is pushed: the owner reviews and merges the branch.
  With no improve_repo, commit falls back to propose.

`check` prepares the worktree (created on first use, from the branch, or from the
repository's HEAD when the branch does not exist yet), refuses a worktree with uncommitted
changes, and finds the target: exactly one file tracked by git at <...>/skills/<skill>/SKILL.md,
not a symlink. It records the file's path and hash in improve.json; the improver reads it there.

`apply` reads the improver's reply, one JSON object: {"result": "APPLIED: <one sentence>",
"old": "<exact text in the file>", "new": "<its replacement>"} or {"result": "SKIPPED: <why>"}.
The edit is made here, in code, so the improver needs no write tool. It is refused when the
file changed since check (CHANGED), when the old text is not found exactly once (NOT_FOUND),
when it would change more than 30 lines added plus removed (TOO_LARGE; nothing is written),
when the worktree holds any other change (DIRTY), or when the folder is not a separate linked
worktree of improve_repo or the target is outside it (NOT_A_WORKTREE, OUTSIDE). Nothing is ever
pushed: the script runs no git command that reaches a remote. Otherwise the one file is committed as
"chief-of-staff: <summary>" with a "Chief-of-Staff-Cycle: <cycle id>" trailer.

In a cycle started with --dry-run, or with --dry-run, nothing is edited or committed: check
answers would_apply and apply answers would_commit. Results: ok, would_apply, proposed, none,
refused (check); committed, not_applied, unchanged, refused, would_commit (apply). Exit 0 to
go on, 3 for a refusal, 2 when it could not run.

Example:
    python3 chief_of_staff_improve.py check ~/state/chief-of-staff/cycles/2030-03-04/061500
"""

import argparse
import difflib
import hashlib
import subprocess
from pathlib import Path

import _common as c

MAX_DIFF_LINES = 30
DEFAULT_BRANCH = "chief-of-staff/improvements"
MODES = ("off", "propose", "commit")
CYCLE_TRAILER = "Chief-of-Staff-Cycle"


def mode():
    value = str(c.setting("improvements") or "propose").strip().lower()
    return value if value in MODES else "propose"


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=60)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _is_dry(folder):
    return bool((c.read_json(Path(folder) / "cycle.json") or {}).get("dry_run"))


def worktree(root, repo, branch):
    """The improvement worktree: (path, "") ready on the branch, or (None, why)."""
    repo = Path(repo).expanduser()
    if not repo.is_dir() or _git("rev-parse", "--git-dir", cwd=repo).returncode != 0:
        return None, f"improve_repo is not a git repository ({repo.name})"
    wt = Path(root) / "improve-worktree"
    if not wt.exists():
        exists = _git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", cwd=repo).returncode == 0
        args = ["worktree", "add", str(wt), branch] if exists else ["worktree", "add", "-b", branch, str(wt), "HEAD"]
        done = _git(*args, cwd=repo)
        if done.returncode != 0:
            return None, f"git worktree add failed: {c.flat(done.stderr, 200)}"
    problem = not_linked(repo, wt)
    if problem:
        return None, problem
    head = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=wt)
    if head.returncode != 0 or head.stdout.strip() != branch:
        return None, f"the improvement worktree is not on {branch}"
    if _git("status", "--porcelain", cwd=wt).stdout.strip():
        return None, "the improvement worktree has uncommitted changes"
    return wt, ""


def not_linked(repo, wt):
    """Why `wt` is not a separate linked worktree of `repo`, or "". The edit must never land in
    the repository's own checkout: the folder must be its own worktree top, a different one
    from the repository's, and share the repository's object store."""
    def ask(*args, cwd):
        done = _git("rev-parse", *args, cwd=cwd)
        return done.stdout.strip() if done.returncode == 0 else ""
    top = ask("--show-toplevel", cwd=wt)
    main_top = ask("--show-toplevel", cwd=repo)
    if not top or Path(top).resolve() != Path(wt).resolve():
        return "the improvement worktree is not a git worktree of its own"
    if main_top and Path(main_top).resolve() == Path(top).resolve():
        return "the improvement worktree is the repository's own checkout; refusing to edit it"
    common = ask("--path-format=absolute", "--git-common-dir", cwd=wt)
    repo_common = ask("--path-format=absolute", "--git-common-dir", cwd=repo)
    git_dir = ask("--path-format=absolute", "--git-dir", cwd=wt)
    if not common or Path(common).resolve() != Path(repo_common).resolve():
        return "the improvement worktree does not belong to improve_repo"
    if Path(git_dir).resolve() == Path(common).resolve():
        return "the improvement folder is a main checkout, not a linked worktree"
    return ""


def find_target(wt, skill):
    """The one tracked <...>/skills/<skill>/SKILL.md in the worktree: (relative path, "") or (None, why)."""
    out = _git("ls-files", cwd=wt)
    hits = [p for p in out.stdout.splitlines()
            if p == f"skills/{skill}/SKILL.md" or p.endswith(f"/skills/{skill}/SKILL.md")]
    if len(hits) != 1:
        return None, f"{len(hits)} tracked files are skills/{skill}/SKILL.md; expected exactly one"
    if (Path(wt) / hits[0]).is_symlink():
        return None, "the target is a symlink"
    return hits[0], ""


def check(folder, root):
    folder = Path(folder)
    imp = (c.read_json(folder / "decision.json") or {}).get("improvement")
    if not isinstance(imp, dict) or not imp.get("target"):
        out = {"status": "none", "reason": "no improvement proposed inside the improvement surface"}
    elif mode() == "off":
        out = {"status": "none", "reason": "improvements are off (setting improvements)"}
    else:
        skill, change, rationale = imp["target"], imp.get("change", ""), imp.get("rationale", "")
        base = {"target": skill, "change": change, "rationale": rationale}
        repo = c.setting("improve_repo")
        if mode() == "propose" or not repo:
            why = ("the setting improvements is propose" if mode() == "propose"
                   else "no improve_repo setting, so the change is proposed")
            out = {"status": "proposed", **base, "reason": f"{why}; filed as a decision, not applied"}
        elif _is_dry(folder):
            out = {"status": "would_apply", **base}
        else:
            branch = str(c.setting("improve_branch") or DEFAULT_BRANCH)
            wt, why = worktree(root, repo, branch)
            rel, why = find_target(wt, skill) if wt else (None, why)
            if not rel:
                out = {"status": "refused", "code": "NOT_READY", **base, "reason": why}
            else:
                path = wt / rel
                out = {"status": "ok", **base, "path": str(path), "relative": rel, "branch": branch,
                       "worktree": str(wt), "before_sha256": _sha(path)}
    c.atomic_json(folder / "improve.json", out)
    return out


def diff_size(before, after):
    return sum(1 for line in difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="", n=0)
               if line[:1] in "+-" and not line.startswith(("+++", "---")))


def apply(folder, result_text, dry_run=False):
    folder = Path(folder)
    if dry_run or _is_dry(folder):
        return {"status": "would_commit", "dry_run": True, "reason": "a dry run edits and commits nothing"}
    state = c.read_json(folder / "improve.json") or {}
    if state.get("status") != "ok":
        return {"status": "refused", "code": "NOT_CHECKED", "reason": "the check did not clear a target"}

    def done(out):
        c.atomic_json(folder / "improve.json", {**state, "result": out})
        return out

    reply = c.load_object(result_text) or {}
    line = c.flat(reply.get("result"), 400)
    if not line.startswith("APPLIED:"):
        return done({"status": "not_applied", "result": line or "unclear result"})
    wt, path = Path(state["worktree"]), Path(state["path"])
    repo = c.setting("improve_repo")
    problem = not_linked(Path(repo).expanduser(), wt) if repo else "no improve_repo setting"
    if problem:
        return done({"status": "refused", "code": "NOT_A_WORKTREE", "reason": problem})
    if wt.resolve() not in path.resolve().parents:
        return done({"status": "refused", "code": "OUTSIDE", "reason": "the target is not inside the improvement worktree"})
    if _git("status", "--porcelain", cwd=wt).stdout.strip():
        return done({"status": "refused", "code": "DIRTY", "reason": "the improvement worktree changed since the check"})
    if not path.is_file() or _sha(path) != state.get("before_sha256"):
        return done({"status": "refused", "code": "CHANGED", "reason": "the target changed since the check"})
    old, new = reply.get("old"), reply.get("new")
    text = path.read_text(encoding="utf-8")
    if not isinstance(old, str) or not old or not isinstance(new, str) or text.count(old) != 1:
        return done({"status": "refused", "code": "NOT_FOUND", "reason": "the old text is not in the file exactly once"})
    after = text.replace(old, new, 1)
    if after == text:
        return done({"status": "unchanged", "result": line})
    size = diff_size(text, after)
    if size > MAX_DIFF_LINES:
        return done({"status": "refused", "code": "TOO_LARGE", "lines": size,
                     "reason": f"the edit changes {size} lines; an improvement is at most {MAX_DIFF_LINES}"})
    path.write_text(after, encoding="utf-8")
    subject = f"chief-of-staff: {line[len('APPLIED:'):].strip()}"[:300]
    cycle_id = c.flat((c.read_json(folder / "cycle.json") or {}).get("cycle_id") or folder.name, 120)
    rel = state["relative"]
    added = _git("add", "--", rel, cwd=wt)
    commit = (_git("commit", "-q", "-m", subject, "-m", f"{CYCLE_TRAILER}: {cycle_id}", "--", rel, cwd=wt)
              if added.returncode == 0 else added)
    if commit.returncode != 0:
        _git("checkout", "--", rel, cwd=wt)
        return done({"status": "refused", "code": "COMMIT_FAILED", "reason": c.flat(commit.stderr, 300)})
    sha = _git("rev-parse", "--short", "HEAD", cwd=wt).stdout.strip()
    return done({"status": "committed", "target": state["target"], "branch": state["branch"], "commit": sha,
                 "message": subject, "lines": size})


def main(argv=None):
    p = argparse.ArgumentParser(description="Guard, apply and commit the cycle's one improvement. One JSON object out.")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("check")
    s.add_argument("cycle_dir")
    a = sub.add_parser("apply")
    a.add_argument("cycle_dir")
    a.add_argument("--result", required=True, help="The improver's reply, saved verbatim")
    a.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    try:
        folder = c.cycle_dir(args.cycle_dir)
        if args.cmd == "check":
            out = check(folder, c.root_of(folder))
        else:
            text = Path(args.result).expanduser().read_text(encoding="utf-8", errors="replace")
            out = apply(folder, text, args.dry_run)
    except (c.Bad, OSError, subprocess.SubprocessError) as exc:
        c.fail(str(exc))
    c.emit(out, c.STOP if out["status"] == "refused" else c.OK)


if __name__ == "__main__":
    main()
