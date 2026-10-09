# /// script
# dependencies = ["pyyaml"]
# ///
"""Launch one registered orchestrator through the runner, or say why not.

    fleet_launch.py NAME [--params k=v ...] [--dry-run] [--authority LEVEL] [--cap N] [--by AGENT]
                    [--registry R] [--automations-dir D] [--format text|json]

The one launch permission a launching agent needs. In this order, it refuses:
- a name the registry does not hold;
- an entry whose status is `spec`, or that names no Automation;
- an entry whose authority is above the caller's --authority (dry-run-only < propose < trusted;
  the default is propose, so a person launching a trusted entry passes --authority trusted);
- a param the runner fills itself (the setting reserved_params), one the entry does not declare
  in `inputs`, a value its pattern does not fully match, or a dry_run other than true or false;
- an Automation whose folder is missing from the automations folder, when one is set;
- a propose launch with no cap (no --cap, no registry launch_cap_per_day) and no --by: with no
  cap here, the launching agent's own backstop is the fence, so an anonymous agent caller fails
  closed;
- a launch past the day's cap: --cap, else the registry's launch_cap_per_day, else none, counted
  from the runner's runs_command as today's agent launches (with --by AGENT, only that agent's).
  A run that names no source counts when it is of a registered Automation. When a cap applies
  and the Runs cannot be read, the launch is refused.

Otherwise it runs the setting launch_command with {automation}, {automation_path} and {by}
filled, and the words of param_args added for each param (see _common.py), and prints the
runner's queue line. --dry-run adds dry_run=true; so does an entry or a caller at dry-run-only,
whatever the flags say. The runner's own limits still bind: this is the second fence, not the only one.

JSON output: {"action", "name", ..., "output": [lines]}. A refusal carries "reason" (a cap
refusal's reason starts "daily cap reached"); a launch carries "automation", "params",
"launches_today" and "cap".

Exit codes: 0 queued, 1 refused (here or by the runner), 2 a bad argument, a missing setting or
an unreadable registry.

Example:
    python3 fleet_launch.py northwind-close-orchestrator --authority trusted --params period=2030-03 --dry-run
"""

import argparse
import json
import re
import sys

import _common as c


class Refused(Exception):
    pass


class Done(Exception):
    def __init__(self, code, payload, lines):
        self.code, self.payload, self.lines = code, payload, lines


def parse_params(pairs):
    params = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        key = key.strip()
        if not sep or not key:
            raise c.Bad(f"--params: '{pair}' is not k=v")
        params[key] = value
    return params


def params_problem(entry, params, reserved):
    inputs = entry.get("inputs") if isinstance(entry.get("inputs"), dict) else {}
    for key, value in params.items():
        if key == "dry_run":
            if value not in ("true", "false"):
                return "dry_run is true or false"
            continue
        if key in reserved:
            return f"param '{key}' is a name the runner fills itself"
        if key not in inputs:
            return f"param '{key}' is not one of {entry['name']}'s inputs ({', '.join(sorted(inputs)) or 'none'})"
        pattern = inputs[key]
        if pattern is not None and not re.fullmatch(str(pattern), value):
            return f"param '{key}'='{value}' does not match {pattern}"
    return None


def plan_launch(registry, name, params, dry_run, authority):
    """The entry, the params to pass and any notes; Refused when the launch may not happen."""
    entry = registry.get(name)
    if entry is None:
        raise Refused(f"{name} is not in the registry ({registry.path})")
    status = entry.get("status")
    if status == "spec" or status not in c.STATUSES:
        raise Refused(f"{name} is at status {status}: nothing is built to launch")
    if not entry.get("automation"):
        raise Refused(f"{name} names no Automation")
    level = entry.get("authority")
    if level not in c.AUTHORITIES:
        raise Refused(f"{name} has no valid authority ({level})")
    if c.AUTHORITIES.index(level) > c.AUTHORITIES.index(authority):
        raise Refused(f"{name} needs authority {level}; the caller has {authority}")
    problem = params_problem(entry, params, c.reserved_params())
    if problem:
        raise Refused(problem)
    notes, params = [], dict(params)
    forced = [who for who, lvl in (("the entry", level), ("the caller", authority)) if lvl == "dry-run-only"]
    if dry_run or forced:
        if forced and not dry_run and params.get("dry_run") != "true":
            notes.append(f"dry run forced: {' and '.join(forced)} at dry-run-only")
        params["dry_run"] = "true"
    return entry, params, notes


def refuse(name, reason, **extra):
    return Done(1, {"action": "refused", "name": name, "reason": reason, **extra}, [f"refused: {reason}"])


def error(name, text):
    return Done(2, {"action": "error", "name": name}, [f"error: {text}"])


def run(args):
    """Every step of the launch; raises Done with the exit code and what to print."""
    name = args.name
    try:
        registry = c.load_registry(args.registry)
        params = parse_params(args.params)
    except c.Bad as exc:
        raise error(name, exc)
    try:
        entry, params, notes = plan_launch(registry, name, params, args.dry_run, args.authority)
    except Refused as exc:
        raise refuse(name, str(exc))
    automations_dir = registry.automations_dir(args.automations_dir)
    folder = automations_dir / entry["automation"] if automations_dir is not None else None
    if folder is not None and not folder.is_dir():
        raise refuse(name, f"Automation folder {folder} does not exist")
    try:
        argv = c.launch_argv(entry["automation"], folder, args.by, params)
    except c.Bad as exc:
        raise error(name, exc)
    limit = registry.cap() if args.cap is None else args.cap
    if limit is None and args.authority == "propose" and not args.by:
        raise refuse(name, "no launch cap: pass --cap, set the registry's launch_cap_per_day, or name the "
                           "launching agent with --by so its own backstop applies")
    used = 0
    if limit is not None:
        try:
            runs = c.read_runs()
        except c.RunnerError as exc:
            raise refuse(name, f"cannot count today's launches: {exc}")
        used = c.count_today(runs, registry.automations(), c.today(), args.by)
        if used >= limit:
            how = f"launches by {args.by}" if args.by else "agent launches"
            raise refuse(name, f"daily cap reached: {used} {how} today, cap {limit}")
    for note in notes:
        print(f"note: {note}", file=sys.stderr)
    try:
        done = c.launch(argv)
    except c.RunnerError as exc:
        raise error(name, exc)
    lines = [line for line in (done.stdout or "").splitlines() if line.strip()]
    if done.returncode != 0:
        detail = [line for line in (done.stderr or "").splitlines() if line.strip()]
        raise Done(1, {"action": "refused", "name": name, "reason": "refused by the runner",
                       "automation": entry["automation"], "params": params},
                   lines + detail or [f"launch_command exit {done.returncode}"])
    action = lines[0].split()[0] if lines else "launched"
    raise Done(0, {"action": action, "name": name, "automation": entry["automation"], "params": params,
                   "launches_today": used + 1, "cap": limit}, lines)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="fleet_launch.py",
                                     description="Launch one registered orchestrator through the runner, or say why not.")
    parser.add_argument("name", help="the orchestrator's registered name")
    parser.add_argument("--params", "--param", nargs="+", action="extend", default=[], metavar="K=V",
                        help="launch params, k=v (several after one flag, or the flag repeated)")
    parser.add_argument("--dry-run", action="store_true", help="launch as a dry run (dry_run=true)")
    parser.add_argument("--authority", choices=c.AUTHORITIES, default="propose",
                        help="the caller's authority (default propose); an entry above it is refused")
    parser.add_argument("--cap", type=int, default=None,
                        help="agent launches allowed today (default: the registry's launch_cap_per_day, else none)")
    parser.add_argument("--by", help="count only this agent's launches toward the cap (the launching agent's name)")
    parser.add_argument("--registry", help="registry YAML (default: setting [orchestrator-fleet] registry)")
    parser.add_argument("--automations-dir", help="folder of Automations (default: setting automations_dir, "
                                                  "else the registry's)")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    if args.cap is not None and args.cap < 0:
        parser.error("--cap must be 0 or more")
    try:
        run(args)
    except Done as done:
        if args.format == "json":
            print(json.dumps({**done.payload, "output": done.lines}))
        else:
            print("\n".join(done.lines))
        return done.code
    return 2


if __name__ == "__main__":
    sys.exit(main())
