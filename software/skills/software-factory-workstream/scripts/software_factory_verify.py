# /// script
# dependencies = ["pyyaml"]
# ///
"""Run the base commit's declared checks in a worktree, offline, and write verify.json.

Which commands: .software-factory/commands.yaml as committed at the base, read with
`git show <base_sha>:<file>`; the worktree's own copy is never read, so a branch cannot change
the checks it is judged by. On the onboarding branch only (software-factory/onboard, whose base
has no commands yet), --commands-from head reads the commands and the rules from the branch's
head instead; on any other branch it is refused. A placeholder command (empty, true, :, exit 0,
echo, printf) counts as none; with no real test command the verdict is no-tests.

How they run: setup, lint, typecheck, test, build, coverage in that order (narrowed by
--steps), each with `bash -c` in its folder of the worktree, stdin closed, in its own process
group (a timeout kills the group and records exit 124), with no GitHub token, SSH agent or
credential helper. A cwd outside the worktree is refused (exit 126). A failing setup skips the
rest. Each step's output goes to its own log beside --out.

The repro: --repro CMD runs in a temporary detached worktree at the base SHA (after the setup)
and in the worktree. Shown means it fails on the base and passes on the head.

Diff coverage: when `coverage` is declared it runs last and must leave coverage.json
(coverage.py), coverage/lcov.info or lcov.info (lcov), or coverage/coverage-final.json
(istanbul). Diff coverage is the covered share of the lines the branch added or changed among the
lines the report knows. The minimum is the rules' `- Minimum diff coverage: N%` at the base. With a
minimum set, coverage below it or no usable report fails the verdict; with none it is reported.

Verdict: verified when every declared step exits 0, the coverage minimum is met, the worktree was
clean when the checks started, and the repro (when given) is shown; failed when a step failed or
the tree was dirty; repro-not-shown when only the repro is missing; no-tests as above.

Inputs: WORKTREE, --base REF, --repro, --out (default <worktree parent>/evidence/<name>/verify.json),
--steps, --timeout-s, --commands-from base|head. Writes verify.json (shape in SOFTWARE-FACTORY.md)
and step logs, prints a summary or the JSON. Exit 0 whenever it ran, 2 on a bad argument.

Example:
  python3 software_factory_verify.py path/to/worktree --base origin/development \
      --repro "pytest tests/test_dates.py::test_iso_week" --out RUN/evidence/issue-42/verify.json
"""

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from _common import (COMMANDS_FILE, RULES_FILE, STEP_ORDER, FactoryError, UsageError, is_onboarding,
                     offline_env, offline_git, parse_commands, rules_fields)

TIMEOUT_EXIT, REFUSED_EXIT, MISSING_DIR_EXIT = 124, 126, 127
REPORTS = (("coverage.json", "coverage.py"), ("coverage/lcov.info", "lcov"), ("lcov.info", "lcov"),
           ("coverage/coverage-final.json", "istanbul"), ("coverage-final.json", "istanbul"))
SUMMARY_ONLY = ("coverage/coverage-summary.json", "coverage-summary.json")


# ---------------------------------------------------------------------------------------------
# Running one step


def step_env():
    env = offline_env()
    for key in ("BASH_ENV", "ENV"):     # so no shell start-up file can export a token back
        env.pop(key, None)
    env.setdefault("CI", "1")
    env.update(PYTHONDONTWRITEBYTECODE="1", SOFTWARE_FACTORY_OFFLINE="1")
    return env


def summarize(log):
    """A test runner's pass and fail counts from the log's last lines, else its last line."""
    try:
        lines = [l.strip() for l in log.read_text(errors="replace").splitlines() if l.strip()]
    except OSError:
        return ""
    for line in reversed(lines[-40:]):
        counts = re.findall(r"\b(\d+)\s+(passed|failed)\b", line, re.I)
        if counts:
            return ", ".join(f"{n} {word.lower()}" for n, word in counts)
    return lines[-1][:200] if lines else ""


def folder_for(root, cwd):
    """The step's folder, or None when cwd is absolute or resolves outside the worktree."""
    if Path(cwd).is_absolute():
        return None
    folder = (root / cwd).resolve()
    return folder if folder.is_relative_to(root.resolve()) else None


def run_command(command, folder, log, timeout_s):
    """(exit, seconds, timed out). Output to the log; a timeout kills the whole process group."""
    started = time.time()
    with log.open("w") as out:
        out.write(f"$ (cd {folder} && {command})\n")
        out.flush()
        proc = subprocess.Popen(["bash", "-c", command], cwd=str(folder), env=step_env(), stdin=subprocess.DEVNULL,
                                stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            proc.wait(timeout=timeout_s)
            timed_out = False
        except subprocess.TimeoutExpired:
            timed_out = True
            for signum in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.killpg(proc.pid, signum)
                    proc.wait(timeout=5)
                    break
                except ProcessLookupError:
                    break
                except subprocess.TimeoutExpired:
                    continue
            try:
                os.killpg(proc.pid, signal.SIGKILL)   # the group may outlive its leader
            except ProcessLookupError:
                pass
            proc.wait()
            out.write(f"\n# timed out after {timeout_s:g}s; process group killed\n")
    return (TIMEOUT_EXIT if timed_out else proc.returncode), round(time.time() - started, 2), timed_out


def shown_path(path):
    rel = os.path.relpath(path)
    return str(path) if rel.startswith("..") else rel


class Runner:
    """Runs steps, each into its own log file in the logs folder."""

    def __init__(self, logs, timeout_s):
        self.logs, self.timeout_s, self.used = logs, timeout_s, set()

    def log_for(self, stem):
        name, n = stem, 1
        while name in self.used:
            n += 1
            name = f"{stem}-{n}"
        self.used.add(name)
        return self.logs / f"{name}.log"

    def step(self, name, entry, root, stem=None):
        log = self.log_for(stem or name)
        rec = {"name": name, "run": entry["run"], "cwd": entry["cwd"], "exit": None, "seconds": 0.0,
               "log": shown_path(log), "summary": ""}
        folder = folder_for(root, entry["cwd"])
        if folder is None:
            why = f"refused: cwd {entry['cwd']!r} is outside the worktree"
            log.write_text(why + "\n")
            return {**rec, "exit": REFUSED_EXIT, "summary": why}
        if not folder.is_dir():
            why = f"cwd {entry['cwd']!r} is not a folder in the worktree"
            log.write_text(why + "\n")
            return {**rec, "exit": MISSING_DIR_EXIT, "summary": why}
        code, seconds, timed_out = run_command(entry["run"], folder, log, self.timeout_s)
        return {**rec, "exit": code, "seconds": seconds,
                "summary": f"timed out after {self.timeout_s:g}s" if timed_out else summarize(log)}


def run_repro(command, worktree, base_sha, setup, runner):
    """The repro once at the base (in a temporary detached worktree, after setup) and once at the head."""
    out = {"command": command, "base_exit": None, "head_exit": None}
    tmp = Path(tempfile.mkdtemp(prefix="software-factory-repro-"))
    base_tree = tmp / "base"
    try:
        offline_git("worktree", "add", "--detach", str(base_tree), base_sha, cwd=worktree)
        for entry in setup:
            rec = runner.step("setup", entry, base_tree, stem="repro-base-setup")
            if rec["exit"] != 0:
                out["base_setup_exit"] = rec["exit"]
                break
        else:
            out["base_exit"] = runner.step("repro", {"run": command, "cwd": "."}, base_tree, stem="repro-base")["exit"]
    finally:
        offline_git("worktree", "remove", "--force", str(base_tree), cwd=worktree, check=False)
        shutil.rmtree(tmp, ignore_errors=True)
        offline_git("worktree", "prune", cwd=worktree, check=False)
    out["head_exit"] = runner.step("repro", {"run": command, "cwd": "."}, worktree, stem="repro-head")["exit"]
    return out


# ---------------------------------------------------------------------------------------------
# Diff coverage


def parse_minimum(value):
    """80%, 80 or 72.5 % as a number from 0 to 100; None when it is not one."""
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*%?\s*", value or "")
    return float(m.group(1)) if m and 0 <= float(m.group(1)) <= 100 else None


def changed_lines(worktree, base_sha):
    """{path: head-side line numbers} the branch added or changed since the merge base."""
    diff = offline_git("diff", "-U0", "--no-color", "--no-ext-diff", f"{base_sha}...HEAD", cwd=worktree).stdout
    out, path = {}, None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip()
            path = None if target == "/dev/null" else target.removeprefix("b/")
            continue
        m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
        if m and path:
            start, count = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
            if count:
                out.setdefault(path, set()).update(range(start, start + count))
    return out


def find_report(folders, since):
    """(report, format, folder, notes): the first report written since the coverage step started."""
    notes = []
    for folder in folders:
        for rel, fmt in REPORTS:
            path = folder / rel
            if path.is_file():
                if path.stat().st_mtime + 1 < since:
                    notes.append(f"{path} is older than this run's coverage command; not read")
                    continue
                return path, fmt, folder, notes
    for folder in folders:
        for rel in SUMMARY_ONLY:
            if (folder / rel).is_file():
                notes.append(f"{folder / rel} has totals only, no line data; diff coverage needs "
                             "coverage-final.json, lcov.info or coverage.json")
    return None, None, None, notes


def read_report(path, fmt, base_dir, root):
    """{path relative to the worktree: (known lines, covered lines)}. ValueError when unreadable."""
    text = path.read_text(encoding="utf-8", errors="replace")
    raw = {}
    if fmt == "coverage.py":
        try:
            files = json.loads(text)["files"]
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"{path} is not coverage.py JSON: {exc}")
        for name, entry in files.items():
            ran = {int(n) for n in entry.get("executed_lines") or []}
            raw[name] = (ran | {int(n) for n in entry.get("missing_lines") or []}, ran)
    elif fmt == "lcov":
        current = None
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("SF:"):
                current = line[3:]
                raw.setdefault(current, (set(), set()))
            elif line.startswith("DA:") and current is not None:
                parts = line[3:].split(",")
                try:
                    number, hits = int(parts[0]), int(float(parts[1]))
                except (IndexError, ValueError):
                    continue
                raw[current][0].add(number)
                if hits > 0:
                    raw[current][1].add(number)
            elif line == "end_of_record":
                current = None
        if not raw:
            raise ValueError(f"{path} has no SF: records")
    else:   # istanbul: a line is known when a statement starts on it, covered when one ran
        try:
            items = json.loads(text).items()
        except (ValueError, AttributeError) as exc:
            raise ValueError(f"{path} is not istanbul coverage-final.json: {exc}")
        for name, entry in items:
            if not isinstance(entry, dict) or "statementMap" not in entry:
                raise ValueError(f"{path} has no statementMap for {name}")
            known, covered, hits = set(), set(), entry.get("s") or {}
            for sid, loc in (entry.get("statementMap") or {}).items():
                try:
                    number = int(loc["start"]["line"])
                except (KeyError, TypeError, ValueError):
                    continue
                known.add(number)
                if int(hits.get(sid) or 0) > 0:
                    covered.add(number)
            raw[str(entry.get("path") or name)] = (known, covered)
    out = {}
    for name, value in raw.items():
        p = Path(name) if Path(name).is_absolute() else base_dir / name
        rel = os.path.relpath(os.path.normpath(str(p)), str(root))
        # A path from another checkout is kept marked, and matched later by its ending.
        out["\0" + name if rel.startswith("..") else rel.replace(os.sep, "/")] = value
    return out


def diff_coverage(changed, lines):
    """{percent, covered, total, files}: the changed lines the report knows, and how many ran."""
    files, covered_all, total_all = [], 0, 0
    for path in sorted(changed):
        entry = lines.get(path) or next((v for k, v in lines.items()
                                         if k.startswith("\0") and k[1:].endswith("/" + path)), None)
        if entry is None:
            continue
        mine = changed[path] & entry[0]
        if not mine:
            continue
        hit = mine & entry[1]
        files.append({"path": path, "covered": len(hit), "total": len(mine),
                      "percent": round(100.0 * len(hit) / len(mine), 1), "uncovered": sorted(mine - hit)})
        covered_all += len(hit)
        total_all += len(mine)
    return {"percent": round(100.0 * covered_all / total_all, 1) if total_all else None,
            "covered": covered_all, "total": total_all, "files": files}


def check_coverage(result, worktree, base_sha, declared, started, steps, rules_sha):
    """Fill result['diff_coverage']; False when the rules' minimum is not met."""
    notes = result["notes"]
    proc = offline_git("show", f"{rules_sha}:{RULES_FILE}", cwd=worktree, check=False)
    raw = rules_fields(proc.stdout).get("minimum diff coverage", "") if proc.returncode == 0 else ""
    minimum = parse_minimum(raw) if raw else None
    blank = {"percent": None, "covered": 0, "total": 0, "minimum": minimum, "files": [], "report": None,
             "format": None}
    if raw and minimum is None:
        notes.append(f"the rules' Minimum diff coverage {raw!r} is not a percentage")
        result["diff_coverage"] = {**blank, "minimum": raw}
        return False
    if "coverage" not in declared or "coverage" not in steps or started is None:
        if minimum is None:
            return True
        result["diff_coverage"] = blank
        why = ("no coverage command is declared at the base" if "coverage" not in declared
               else "the coverage step did not run")
        notes.append(f"the rules set a minimum diff coverage of {minimum:g}% but {why}")
        return False
    out = result["diff_coverage"] = blank
    if any(s["exit"] is None for s in result["steps"] if s["name"] == "coverage"):
        notes.append("the coverage step did not run")
        return minimum is None
    folders = []
    for entry in declared["coverage"]:
        folder = folder_for(worktree, entry["cwd"])
        if folder is not None and folder not in folders:
            folders.append(folder)
    if worktree not in folders:
        folders.append(worktree)
    report, fmt, where, found_notes = find_report(folders, started)
    notes.extend(found_notes)
    if report is None:
        notes.append("the coverage command left no coverage.json, coverage/lcov.info or coverage/coverage-final.json"
                     + (" (needed: the rules set a minimum)" if minimum is not None else ""))
        return minimum is None
    out["report"], out["format"] = shown_path(report), fmt
    try:
        lines = read_report(report, fmt, where, worktree)
    except (ValueError, OSError) as exc:
        notes.append(str(exc))
        return minimum is None
    out.update(diff_coverage(changed_lines(worktree, base_sha), lines))
    if minimum is None:
        return True
    if out["total"] == 0:
        notes.append("no changed line is in the coverage report, so the minimum diff coverage does not apply")
        return True
    if 100.0 * out["covered"] / out["total"] < minimum:
        notes.append(f"diff coverage {out['percent']:g}% ({out['covered']} of {out['total']} changed lines) "
                     f"is below the rules' minimum of {minimum:g}%")
        return False
    return True


# ---------------------------------------------------------------------------------------------
# The verify


def verify(worktree, base, repro, out, steps, timeout_s, commands_from="base"):
    worktree = worktree.resolve()
    if offline_git("rev-parse", "--is-inside-work-tree", cwd=worktree, check=False).stdout.strip() != "true":
        raise UsageError(f"{worktree} is not a git worktree")
    proc = offline_git("rev-parse", "--verify", "--quiet", f"{base}^{{commit}}", cwd=worktree, check=False)
    if proc.returncode != 0:
        raise UsageError(f"--base {base!r} does not resolve to a commit in {worktree}")
    base_sha = proc.stdout.strip()
    head_sha = offline_git("rev-parse", "HEAD", cwd=worktree).stdout.strip()
    if commands_from == "head":
        on = offline_git("rev-parse", "--abbrev-ref", "HEAD", cwd=worktree, check=False).stdout.strip()
        if not is_onboarding(on):
            raise UsageError(f"--commands-from head is only for the onboarding branch software-factory/onboard; "
                             f"{worktree} is on {on or 'a detached HEAD'}")
    source_sha = head_sha if commands_from == "head" else base_sha
    out.parent.mkdir(parents=True, exist_ok=True)
    result = {"worktree": str(worktree), "base": base, "base_sha": base_sha, "head_sha": head_sha,
              "commands_from": "", "steps": [], "repro": None, "verdict": "failed", "offline": True, "notes": []}
    notes = result["notes"]
    where = "the head" if commands_from == "head" else "the base"
    if commands_from == "head":
        notes.append(f"onboarding: the commands and rules were read from the branch's head {head_sha[:12]}, "
                     f"not the base {base_sha[:12]}, which has none yet")
    shown_file = offline_git("show", f"{source_sha}:{COMMANDS_FILE}", cwd=worktree, check=False)
    if shown_file.returncode != 0:
        notes.append(f"no {COMMANDS_FILE} at {where} {source_sha[:12]}")
        result["verdict"] = "no-tests"
        return result
    result["commands_from"] = f"{COMMANDS_FILE}@{source_sha}"
    try:
        declared = parse_commands(shown_file.stdout)
    except ValueError as exc:
        notes.append(f"{result['commands_from']} does not parse: {exc}")
        return result
    if "test" not in declared or "test" not in steps:
        notes.append(f"no test command declared at {where} (or every one is a placeholder)"
                     if "test" not in declared else "--steps leaves out test")
        result["verdict"] = "no-tests"
        return result

    status = offline_git("status", "--porcelain", cwd=worktree).stdout.strip()
    if status:
        notes.append(f"uncommitted changes in the worktree when the checks started, so the result is not "
                     f"head_sha's: {status[:300]}")
    runner = Runner(out.parent, timeout_s)
    setup_failed, coverage_started = False, None
    for name in [s for s in STEP_ORDER if s in steps and s in declared]:
        if name == "coverage" and coverage_started is None:
            coverage_started = time.time()
        for entry in declared[name]:
            if setup_failed:
                result["steps"].append({"name": name, "run": entry["run"], "cwd": entry["cwd"], "exit": None,
                                        "seconds": 0.0, "log": "", "summary": "skipped: setup failed"})
                continue
            rec = runner.step(name, entry, worktree)
            result["steps"].append(rec)
            if name == "setup" and rec["exit"] != 0:
                setup_failed = True
                notes.append("setup failed; the remaining steps were skipped")
    steps_ok = all(s["exit"] == 0 for s in result["steps"])
    coverage_ok = check_coverage(result, worktree, base_sha, declared, coverage_started, steps, source_sha)

    shown = True
    if repro:
        if setup_failed:
            result["repro"] = {"command": repro, "base_exit": None, "head_exit": None}
            shown = False
        else:
            setup = declared.get("setup", []) if "setup" in steps else []
            r = result["repro"] = run_repro(repro, worktree, base_sha, setup, runner)
            shown = r["base_exit"] not in (None, 0) and r["head_exit"] == 0
            if not shown:
                notes.append(f"repro not shown: base exit {r['base_exit']}, head exit {r['head_exit']} "
                             "(it must fail on the base and pass on the head)")
    if not steps_ok or status or not coverage_ok:
        result["verdict"] = "failed"
    else:
        result["verdict"] = "verified" if shown else "repro-not-shown"
    return result


def text_report(result, out):
    lines = [f"{result['verdict'].upper()}  {result['head_sha'][:12]} against {result['base']} "
             f"({result['base_sha'][:12]})"]
    for s in result["steps"]:
        code = "skipped" if s["exit"] is None else f"exit {s['exit']}"
        lines.append(f"  {s['name']:<9} {code:<8} {s['seconds']:>7.1f}s  {s['summary']}  [{s['run']} in {s['cwd']}]")
    r = result.get("repro")
    if r:
        lines.append(f"  repro     base exit {r['base_exit']}, head exit {r['head_exit']}  [{r['command']}]")
    dc = result.get("diff_coverage")
    if dc:
        pct = "n/a" if dc["percent"] is None else f"{dc['percent']:g}%"
        floor = "" if dc["minimum"] is None else (f", minimum {dc['minimum']:g}%" if isinstance(dc["minimum"], float)
                                                  else f", minimum {dc['minimum']!r}")
        lines.append(f"  diff coverage {pct} ({dc['covered']} of {dc['total']} changed lines{floor})")
    lines += [f"  note: {n}" for n in result["notes"]]
    lines.append(f"  wrote {shown_path(out)}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run the base commit's declared checks in WORKTREE, offline.")
    ap.add_argument("worktree", type=Path)
    ap.add_argument("--base", required=True, help="the base ref the branch is judged against")
    ap.add_argument("--repro", help="a command that must fail on the base and pass on the head")
    ap.add_argument("--out", type=Path, help="verify.json path; logs go beside it")
    ap.add_argument("--steps", default=",".join(STEP_ORDER), help="declared steps to run, comma-separated")
    ap.add_argument("--timeout-s", type=float, default=1800, help="per-step timeout in seconds")
    ap.add_argument("--commands-from", choices=["base", "head"], default="base",
                    help="read the commands at the base, or at the head (onboarding branch only)")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args(argv)

    def usage(message):
        print(f"software_factory_verify: {message}", file=sys.stderr)
        return 2

    chosen = [s.strip() for s in args.steps.split(",") if s.strip()]
    unknown = [s for s in chosen if s not in STEP_ORDER]
    if unknown or not chosen:
        return usage(f"--steps takes {', '.join(STEP_ORDER)}; not {', '.join(unknown) or 'nothing'}")
    if args.timeout_s <= 0:
        return usage("--timeout-s must be more than 0")
    if not args.worktree.is_dir():
        return usage(f"{args.worktree} is not a folder")
    if args.repro is not None and not args.repro.strip():
        return usage("--repro is empty")
    worktree = args.worktree.resolve()
    out = args.out or worktree.parent / "evidence" / worktree.name / "verify.json"
    if out.resolve().is_relative_to(worktree):
        return usage("--out must be outside the worktree")
    try:
        result = verify(worktree, args.base, args.repro, out, chosen, args.timeout_s, args.commands_from)
    except FactoryError as exc:
        return usage(str(exc))
    out.write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(result, indent=1) if args.format == "json" else text_report(result, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
