# /// script
# dependencies = ["pyyaml"]
# ///
"""Where every registered orchestrator stands.

    fleet_status.py [--format text|json] [--domain D] [--status S] [--no-checks] [--registry R]

Per orchestrator: its registry status, its last Run (id, outcome, when, source), whether a Run
is live now, whether one is queued, how many Runs wait on the owner, and its check's headline.
The Runs come from the runner's `runs_command` (setting in [orchestrator-fleet]; see
_common.py), matched by the entry's Automation name. When the runner cannot be read the rows
still print, and the reason is given as runs_error.

The check runs only when it is cheap: the entry is past `spec`, the command has no
`{placeholder}` (one that needs launch params is skipped), and its program is on PATH. It runs
with `--precheck` added and a 60-second limit; the headline is its first line of output.

JSON output: {"registry": path, "runs_error": text or null, "orchestrators": [row, ...]}, each row
{name, domain, status, authority, automation, last_run: {id, outcome, when, source} or null,
live, queued, waiting_on_owner, check}.

Exit codes: 0 when it ran (an unreadable runner is reported, not fatal), 2 when the registry
could not be read.

Example:
    python3 fleet_status.py --format json --no-checks
"""

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import _common as c

CHECK_TIMEOUT_S = 60
HEADLINE_MAX = 120


def check_headline(command, status, timeout=CHECK_TIMEOUT_S):
    """The check's first line, or why it was not run; None when there is no check."""
    if not command:
        return None
    if status == "spec":
        return "skipped: not built"
    if c.has_placeholder(command):
        return "skipped: needs launch params"
    try:
        argv = [os.path.expanduser(word) for word in shlex.split(command)]
    except ValueError:
        return "skipped: does not parse"
    if not argv or not shutil.which(argv[0]):
        return f"skipped: {argv[0] if argv else 'nothing'} not on PATH"
    if "--precheck" not in argv:
        argv.append("--precheck")
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return f"timed out after {timeout}s"
    except OSError as exc:
        return f"could not run: {exc}"
    lines = [line.strip() for line in (done.stdout or "").splitlines() if line.strip()]
    if not lines:
        errors = [line.strip() for line in (done.stderr or "").splitlines() if line.strip()]
        return f"exit {done.returncode}: {errors[0] if errors else 'no output'}"[:HEADLINE_MAX]
    return lines[0][:HEADLINE_MAX] if done.returncode == 0 else f"exit {done.returncode}: {lines[0]}"[:HEADLINE_MAX]


def outcome(run):
    if run.accepted is None or run.status not in c.TERMINAL:
        return run.status
    return f"{run.status}, {'accepted' if run.accepted else 'not accepted'}"


def when(run):
    return run.started_at.astimezone().strftime("%Y-%m-%d %H:%M") if run.started_at else None


def row_for(entry, runs, headline):
    automation = entry.get("automation")
    mine = [r for r in runs if r.automation == automation] if runs is not None and automation else []
    started = [r for r in mine if not r.is_queued]
    last = started[0] if started else None
    return {
        "name": entry.get("name"),
        "domain": entry.get("domain"),
        "status": entry.get("status"),
        "authority": entry.get("authority"),
        "automation": automation,
        "last_run": None if last is None else {"id": last.id, "outcome": outcome(last), "when": when(last),
                                               "source": last.source_kind},
        "live": any(r.is_live for r in mine),
        "queued": any(r.is_queued for r in mine),
        "waiting_on_owner": sum(1 for r in mine if r.is_waiting) + (last.for_owner if last else 0),
        "check": headline,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="fleet_status.py", description="Where every registered orchestrator stands.")
    parser.add_argument("--registry", help="registry YAML (default: setting [orchestrator-fleet] registry)")
    parser.add_argument("--domain", help="only this domain")
    parser.add_argument("--status", choices=c.STATUSES, help="only this status")
    parser.add_argument("--no-checks", action="store_true", help="do not run the check commands")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--check-timeout", type=int, default=CHECK_TIMEOUT_S, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        registry = c.load_registry(args.registry)
    except c.Bad as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    entries = c.filtered(registry, args.domain, args.status)
    runs, problem = None, None
    try:
        runs = c.read_runs()
    except c.RunnerError as exc:
        problem = str(exc)
    if args.no_checks:
        headlines = [None] * len(entries)
    else:
        with ThreadPoolExecutor(max_workers=4) as pool:
            headlines = list(pool.map(
                lambda e: check_headline(e.get("check"), e.get("status"), args.check_timeout), entries))
    rows = [row_for(e, runs, h) for e, h in zip(entries, headlines)]
    if args.format == "json":
        print(json.dumps({"registry": str(registry.path), "runs_error": problem, "orchestrators": rows}, indent=2))
        return 0
    if problem:
        print(f"runs unavailable: {problem}")
    header = ["name", "status", "last run", "outcome", "when", "live", "queued", "waiting", "check"]
    table = []
    for r in rows:
        last = r["last_run"] or {}
        table.append([r["name"], r["status"], last.get("id") or "-", last.get("outcome") or "-",
                      last.get("when") or "-", "yes" if r["live"] else "-", "yes" if r["queued"] else "-",
                      str(r["waiting_on_owner"] or "-"), r["check"] or "-"])
    print(c.table(table, header) if table else "no orchestrators match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
