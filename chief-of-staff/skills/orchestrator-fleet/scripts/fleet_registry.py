# /// script
# dependencies = ["pyyaml"]
# ///
"""List and validate the orchestrator fleet's registry.

    fleet_registry.py list [--domain D] [--status S] [--format text|json] [--registry R]
    fleet_registry.py validate [--agents-dir D] [--automations-dir D] [--format text|json] [--registry R]

The registry is the owner's YAML file, named by the setting `registry` in the
`[orchestrator-fleet]` table of the owner settings, or by --registry. It names Automation
folders and machine paths, so it lives with the owner, never in this repository.

THE SCHEMA. Top level, all optional but `orchestrators`:

    version: 1
    automations_dir: <path>      # used when neither --automations-dir nor the setting names one;
                                 # relative to the registry's folder
    launch_cap_per_day: 12       # fleet_launch.py's default --cap; absent means no cap
    orchestrators: [<entry>, ...]

Each entry has every one of these keys (null or empty where there is nothing yet):

    name        <domain>-<thing>-orchestrator, the agent's name once built
    domain      the fleet domain, a slug
    tier        A | B | C
    status      spec | drafted | built | dry-run-passed | live | scheduled
    automation  the Automation's name (its folder in automations_dir), or null
    triggers    mapping: schedule (five-field cron), tz (IANA zone), precheck (a command),
                cadence (words), events (list of words), manual (true or false)
    inputs      mapping: launch param -> regex the value must fully match, or null for any
                value. dry_run is always allowed and is not listed.
    record      the system of record and the working folder (words)
    authority   dry-run-only | propose | trusted: what a Run may do, so who may launch it
    check       the command that computes done, or null
    outputs     list: what the owner sees
    replaces    list: what it retires once live
    wave        build wave (a whole number), or null
    value       H | M | L, or null

and may have `plan` (a catalogue number) and `purpose` (one sentence).

WHAT VALIDATE CHECKS
- every entry has the keys above, with values of the right kind, and no others;
- names are unique, kebab-case, and end `-orchestrator`;
- an entry past `spec` has its agent file, <name>.md anywhere under the agents folder
  (--agents-dir, else the setting agents_dir, else ~/.claude/agents);
- no two entries share an Automation, and a `live` or `scheduled` entry names one;
- when an automations folder is known, each named Automation's folder exists in it;
- no input uses a param name the runner fills itself (the setting reserved_params, and dry_run);
- triggers parse: the cron line, the zone, the precheck command.
It does not read an Automation's own definition file: that format belongs to the runner.

Exit codes: 0 when it ran and found no error, 1 when validation found errors, 2 when the
registry could not be read.

Example:
    python3 fleet_registry.py validate --format json
"""

import argparse
import json
import re
import shlex
import sys

import _common as c

CRON_RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))
CRON_NAMES = (
    {}, {}, {},
    {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())},
    {d: i for i, d in enumerate("sun mon tue wed thu fri sat".split())},
)


# --------------------------------------------------------------------------- triggers

def cron_value(text, names):
    return int(text) if text.isdigit() else names.get(text.lower())


def cron_problem(line):
    """None when `line` is a valid five-field cron line, else what is wrong."""
    if not isinstance(line, str):
        return "schedule must be a string"
    fields = line.split()
    if len(fields) != 5:
        return f"schedule '{line}' needs five fields, has {len(fields)}"
    for index, (text, (low, high), names) in enumerate(zip(fields, CRON_RANGES, CRON_NAMES)):
        for part in text.split(","):
            if index == 4 and "#" in part:   # the nth weekday of the month, such as 1#1 (first Monday)
                day, _, nth = part.partition("#")
                value = cron_value(day, names)
                if value is None or not low <= value <= high or nth not in ("1", "2", "3", "4", "5"):
                    return f"schedule '{line}': bad nth weekday '{part}'"
                continue
            base, _, step = part.partition("/")
            if step and not (step.isdigit() and int(step) > 0):
                return f"schedule '{line}': bad step in '{part}'"
            if base == "*":
                continue
            ends = base.split("-")
            if len(ends) > 2 or not all(ends):
                return f"schedule '{line}': bad range '{part}'"
            values = [cron_value(end, names) for end in ends]
            bad = next((end for end, v in zip(ends, values) if v is None), None)
            if bad is not None:
                return f"schedule '{line}': '{bad}' is not a value"
            if any(v < low or v > high for v in values):
                return f"schedule '{line}': '{part}' is outside {low}-{high}"
            if len(values) == 2 and values[0] > values[1]:
                return f"schedule '{line}': range '{part}' runs backwards"
    return None


def command_problem(command, what):
    try:
        if not isinstance(command, str) or not shlex.split(command):
            return f"{what} must be a non-empty command"
    except ValueError as exc:
        return f"{what} does not parse: {exc}"
    return None


def trigger_problems(triggers):
    if not isinstance(triggers, dict):
        return ["triggers must be a mapping"]
    out = [f"triggers: unknown key '{k}'" for k in triggers if k not in c.TRIGGER_KEYS]
    if "schedule" in triggers and (problem := cron_problem(triggers["schedule"])):
        out.append(f"triggers: {problem}")
    if "tz" in triggers:
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(str(triggers["tz"]))
        except Exception:   # any failure means the zone is unusable
            out.append(f"triggers: tz '{triggers['tz']}' is not an IANA zone")
    if "precheck" in triggers and (problem := command_problem(triggers["precheck"], "precheck")):
        out.append(f"triggers: {problem}")
    if "cadence" in triggers and not isinstance(triggers["cadence"], str):
        out.append("triggers: cadence must be words")
    if "events" in triggers and not (isinstance(triggers["events"], list)
                                     and all(isinstance(e, str) for e in triggers["events"])):
        out.append("triggers: events must be a list of words")
    if "manual" in triggers and not isinstance(triggers["manual"], bool):
        out.append("triggers: manual must be true or false")
    return out


# --------------------------------------------------------------------------- validation

def entry_problems(entry, reserved):
    """What is wrong with one entry's shape and values."""
    out = []
    missing = [k for k in c.REQUIRED if k not in entry]
    if missing:
        out.append(f"missing {', '.join(missing)}")
    unknown = [k for k in entry if k not in c.REQUIRED + c.OPTIONAL]
    if unknown:
        out.append(f"unknown field {', '.join(unknown)}")
    for key, allowed in (("tier", c.TIERS), ("status", c.STATUSES), ("authority", c.AUTHORITIES)):
        if key in entry and entry[key] not in allowed:
            out.append(f"{key} '{entry[key]}' is not one of {', '.join(allowed)}")
    if entry.get("value") is not None and entry["value"] not in c.VALUES:
        out.append(f"value '{entry['value']}' is not one of H, M, L or null")
    wave = entry.get("wave")
    if wave is not None and not (isinstance(wave, int) and not isinstance(wave, bool) and wave >= 0):
        out.append("wave must be a whole number or null")
    for key in ("domain", "record"):
        if key in entry and not (isinstance(entry[key], str) and entry[key].strip()):
            out.append(f"{key} must be words")
    for key in ("outputs", "replaces"):
        if key in entry and not (isinstance(entry[key], list) and all(isinstance(x, str) for x in entry[key])):
            out.append(f"{key} must be a list of words")
    automation = entry.get("automation")
    if automation is not None and not (isinstance(automation, str)
                                       and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", automation)):
        out.append(f"automation '{automation}' is not a folder name")
    if entry.get("check") is not None and (problem := command_problem(entry["check"], "check")):
        out.append(problem)
    inputs = entry.get("inputs")
    if "inputs" in entry and not isinstance(inputs, dict):
        out.append("inputs must be a mapping (param: regex or null)")
    elif isinstance(inputs, dict):
        for key, pattern in inputs.items():
            if key in reserved:
                out.append(f"input '{key}' is a name the runner fills itself")
            if pattern is not None:
                try:
                    re.compile(str(pattern))
                except re.error as exc:
                    out.append(f"input '{key}': pattern does not compile: {exc}")
    if "triggers" in entry:
        out += trigger_problems(entry["triggers"])
    return out


def has_agent_file(name, folder):
    return folder.is_dir() and any(folder.rglob(f"{name}.md"))


def validate(registry, agents_dir, automations_dir):
    """(errors, warnings) for the whole registry."""
    errors, warnings = [], []
    if automations_dir is None:
        warnings.append("registry: no automations_dir is set; Automation folders not checked")
    reserved = c.reserved_params()
    seen, owners = {}, {}
    for index, entry in enumerate(registry.entries, start=1):
        if not isinstance(entry, dict):
            errors.append(f"entry {index}: must be a mapping")
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            errors.append(f"entry {index}: has no name")
            continue
        problems = []
        seen[name] = seen.get(name, 0) + 1
        if seen[name] == 2:
            problems.append("the name is registered twice")
        if not c.NAME_RE.match(name):
            problems.append("a name is kebab-case <domain>-<thing>-orchestrator")
        problems += entry_problems(entry, reserved)
        status = entry.get("status")
        if status in c.STATUSES and status != "spec" and not has_agent_file(name, agents_dir):
            problems.append(f"status is {status} but there is no agent file {name}.md under {agents_dir}")
        automation = entry.get("automation")
        if isinstance(automation, str) and automation:
            if automation in owners:
                problems.append(f"Automation {automation} is already {owners[automation]}'s")
            owners.setdefault(automation, name)
            if automations_dir is not None and not (automations_dir / automation).is_dir():
                problems.append(f"Automation folder {automations_dir / automation} does not exist")
        elif status in ("live", "scheduled"):
            problems.append(f"status is {status} but it names no Automation")
        errors += [f"{name}: {p}" for p in problems]
    return errors, warnings


# --------------------------------------------------------------------------- commands

def cell(value):
    return "-" if value is None or value == "" else str(value)


def cmd_list(args, registry):
    rows = c.filtered(registry, args.domain, args.status)
    if args.format == "json":
        print(json.dumps(rows, indent=2, default=str))
        return 0
    if not rows:
        print("no orchestrators match")
        return 0
    header = ["name", "plan", "domain", "tier", "status", "authority", "automation", "wave"]
    print(c.table([[cell(e.get(k)) for k in header] for e in rows], header))
    print(f"{len(rows)} of {len(registry.entries)} orchestrators")
    return 0


def cmd_validate(args, registry):
    errors, warnings = validate(registry, c.agents_dir(args.agents_dir),
                                registry.automations_dir(args.automations_dir))
    counts = {}
    for entry in registry.entries:
        if isinstance(entry, dict):
            counts[str(entry.get("status"))] = counts.get(str(entry.get("status")), 0) + 1
    if args.format == "json":
        print(json.dumps({"ok": not errors, "registry": str(registry.path), "entries": len(registry.entries),
                          "by_status": counts, "errors": errors, "warnings": warnings}, indent=2))
    else:
        by_status = ", ".join(f"{counts[s]} {s}" for s in c.STATUSES if s in counts)
        print(f"{'FAIL' if errors else 'OK'}: {len(registry.entries)} orchestrators ({by_status}); "
              f"{len(errors)} errors, {len(warnings)} warnings")
        for line in errors:
            print(f"  error: {line}")
        for line in warnings:
            print(f"  warning: {line}")
    return 1 if errors else 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="fleet_registry.py", description="List and validate the fleet registry.")
    sub = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--registry", help="registry YAML (default: setting [orchestrator-fleet] registry)")
    common.add_argument("--format", choices=["text", "json"], default="text")
    p_list = sub.add_parser("list", parents=[common], help="the registered orchestrators, one line each")
    p_list.add_argument("--domain", help="only this domain")
    p_list.add_argument("--status", choices=c.STATUSES, help="only this status")
    p_val = sub.add_parser("validate", parents=[common], help="check every entry; exit 1 on any error")
    p_val.add_argument("--agents-dir", help="folder searched for <name>.md (default: setting agents_dir, "
                                            "else ~/.claude/agents)")
    p_val.add_argument("--automations-dir", help="folder of Automations (default: setting automations_dir, "
                                                 "else the registry's)")
    args = parser.parse_args(argv)
    try:
        registry = c.load_registry(args.registry)
    except c.Bad as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return cmd_list(args, registry) if args.command == "list" else cmd_validate(args, registry)


if __name__ == "__main__":
    sys.exit(main())
