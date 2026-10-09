#!/usr/bin/env python3
"""chief-of-staff-fleet: what the cycle reads about the orchestrator fleet, and its one way to
launch an orchestrator.

    snapshot CYCLE_DIR [--registry R] [--no-checks]
    launch CYCLE_DIR NAME [--registry R]

`snapshot` runs before the decider. It runs orchestrator-fleet's fleet_status.py (every
registered orchestrator's status, last Run, live or queued, Runs waiting on the owner, its
check's headline) and task-stack-workstream's task_stack_check.py --precheck (the task stack's
WORK or NOTHING line, its full score in task-stack.json), and writes fleet.json in the cycle
folder: those two, the owner's launch switch, today's launches against the daily backstop,
and which orchestrators the cycle may launch, each with its mode and allowed triggers, and
every other built one with the reason it may not. It only reads, so it runs in a dry run too.

The rules, enforced here, again in the decide check and again at launch:
- The switch: the setting fleet_launches = "on" lets the cycle launch; missing or anything
  else is off, and nothing is launched.
- Which orchestrators: registered, past status spec and with an Automation; not the cycle
  itself; authority dry-run-only or propose (an entry at trusted is the owner's or its
  schedule's to launch, never the cycle's); none with a Run live or queued now; none that
  succeeded today unless the launch names new_evidence.
- Which mode: live only for an entry at authority propose whose registry status is live;
  every other launch is a dry run.
- Off schedule only: each launch names stall, event or priority; an orchestrator that fires on
  its own schedule (status scheduled) takes stall or event only.
- The backstop: the setting launch_backstop (default 12) launches a day, counted from today's
  cycle folders here and again by fleet_launch.py --cap in the runner's records. When it is
  hit the launch is refused and the owner gets one message.

`launch` runs one launch the decide check accepted. It refuses unless cycle.json says
whether the cycle is a dry run, takes the mode and checks the params against the registry
again (never trusting decision.json for either), runs fleet_launch.py NAME --authority propose
--cap BACKSTOP --by chief-of-staff-cycle-orchestrator --format json [--dry-run] --params k=v,
and records it in execution.json as launch:NAME with its status (launched, refused, failed)
and why. In a dry-run cycle it records dry-run, would launch, and runs nothing.

Results: snapshot ok (exit 0); launch launched or would_launch (0), refused or failed (3).
Exit 2 when it could not run.

Example:
    python3 chief_of_staff_fleet.py snapshot ~/state/chief-of-staff/cycles/2030-03-04/061500
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import _common as c

FLEET_STATUS = c.SKILLS_HOME / "orchestrator-fleet" / "scripts" / "fleet_status.py"
FLEET_REGISTRY = c.SKILLS_HOME / "orchestrator-fleet" / "scripts" / "fleet_registry.py"
FLEET_LAUNCH = c.SKILLS_HOME / "orchestrator-fleet" / "scripts" / "fleet_launch.py"
TASK_STACK_CHECK = c.SKILLS_HOME / "task-stack-workstream" / "scripts" / "task_stack_check.py"

DEFAULT_BACKSTOP = 12
AUTHORITY = "propose"
TRIGGERS = ("stall", "event", "priority")
SCHEDULED_TRIGGERS = ("stall", "event")
LAUNCHABLE_AUTHORITIES = ("dry-run-only", "propose")
LAUNCH_PREFIX = "launch:"
STATUS_TIMEOUT_S, CHECK_TIMEOUT_S, LAUNCH_TIMEOUT_S = 900, 300, 180


def launch_switch():
    """The owner's fleet_launches setting: "on" or "off"; anything but on reads off."""
    return "on" if str(c.setting("fleet_launches") or "").strip().lower() == "on" else "off"


def backstop():
    """The day's launch backstop: the setting launch_backstop, else 12. A bad value reads 12."""
    try:
        value = int(str(c.setting("launch_backstop", DEFAULT_BACKSTOP)).strip())
    except ValueError:
        return DEFAULT_BACKSTOP
    return value if value >= 0 else DEFAULT_BACKSTOP


def reserved():
    extra = c.settings("orchestrator-fleet").get("reserved_params") or []
    return {"dry_run", *[str(x) for x in extra if isinstance(extra, list)]}


def launches_today(root, day):
    """Launches made today by every live (not dry-run) cycle, from the cycle folders."""
    folder = Path(root) / "cycles" / day
    if not folder.is_dir():
        return 0
    return sum(1 for cycle in folder.iterdir() if cycle.is_dir() and not cycle.name.endswith("-dry-run")
               for row in c.read_json(cycle / "execution.json") or []
               if isinstance(row, dict) and str(row.get("doer") or "").startswith(LAUNCH_PREFIX)
               and row.get("status") == "launched")


def succeeded_today(row, day):
    last = row.get("last_run") if isinstance(row.get("last_run"), dict) else {}
    outcome = str(last.get("outcome") or "")
    return outcome.startswith("completed") and "not accepted" not in outcome and str(last.get("when") or "").startswith(day)


def classify_entry(entry, row, day=None):
    """(the launchable record, "") or (None, why it may not be launched)."""
    name, status, authority = entry.get("name"), entry.get("status"), entry.get("authority")
    if name in c.OWN_AGENTS:
        return None, "the cycle is never launched by the cycle"
    if status in (None, "spec") or not entry.get("automation"):
        return None, "not built: no Automation to launch"
    if authority not in LAUNCHABLE_AUTHORITIES:
        return None, f"authority {authority}: never launched by the cycle; the owner or its schedule launches it"
    row = row or {}
    if row.get("live"):
        return None, "a Run is live now"
    if row.get("queued"):
        return None, "a Run is queued now"
    if authority == "propose" and status == "live":
        mode, why = "live", "authority propose, status live"
    elif authority == "dry-run-only":
        mode, why = "dry-run", "authority dry-run-only: every launch runs dry"
    else:
        mode, why = "dry-run", f"status {status}: only registry status live runs for real"
    triggers = entry.get("triggers") if isinstance(entry.get("triggers"), dict) else {}
    inputs = entry.get("inputs") if isinstance(entry.get("inputs"), dict) else {}
    skip = reserved()
    return {
        "name": name, "domain": entry.get("domain"), "purpose": c.flat(entry.get("purpose"), 300),
        "status": status, "authority": authority, "mode": mode, "mode_reason": why,
        "triggers_allowed": list(SCHEDULED_TRIGGERS if status == "scheduled" else TRIGGERS),
        "schedule": triggers.get("schedule"), "cadence": triggers.get("cadence"), "events": triggers.get("events") or [],
        "inputs": {k: v for k, v in inputs.items() if k not in skip},
        "succeeded_today": bool(day and succeeded_today(row, day)),
        "last_run": row.get("last_run"), "waiting_on_owner": row.get("waiting_on_owner") or 0, "check": row.get("check"),
    }, ""


def registry_entries(registry_file):
    """Every registry entry, through fleet_registry.py list --format json; (entries, error)."""
    argv = [sys.executable, str(FLEET_REGISTRY), "list", "--format", "json"]
    if registry_file:
        argv += ["--registry", registry_file]
    code, out, err = c.run_script(argv, 60)
    if code != 0:
        return [], f"registry: exit {code}: {c.first_line(err, out)}"[:300]
    try:
        rows = json.loads(out)
    except ValueError:
        return [], "registry: no JSON"
    return [e for e in rows if isinstance(e, dict)], ""


def snapshot(folder, registry_file=None, checks=True):
    folder = Path(folder)
    cycle = c.read_json(folder / "cycle.json") or {}
    day = str(cycle.get("date") or c.local_now().date().isoformat())
    errors = []
    argv = [sys.executable, str(FLEET_STATUS), "--format", "json"]
    if registry_file:
        argv += ["--registry", registry_file]
    if not checks:
        argv.append("--no-checks")
    code, out, err = c.run_script(argv, STATUS_TIMEOUT_S)
    status = {}
    if code == 0:
        try:
            status = json.loads(out)
        except ValueError:
            errors.append("fleet_status.py gave no JSON")
    else:
        errors.append(f"fleet_status.py exit {code}: {c.first_line(err, out)}"[:300])
    if status.get("runs_error"):
        errors.append(f"runs: {status['runs_error']}"[:300])
    rows = {r.get("name"): r for r in status.get("orchestrators") or [] if isinstance(r, dict)}

    stack_file = folder / "task-stack.json"
    code, out, err = c.run_script([sys.executable, str(TASK_STACK_CHECK), "--precheck", "--out", str(stack_file)],
                                  CHECK_TIMEOUT_S)
    line = c.first_line(out, err) if code == 0 else f"exit {code}: {c.first_line(err, out)}"
    task_stack = {"precheck": line[:300], "file": str(stack_file) if stack_file.exists() else ""}

    entries, problem = registry_entries(registry_file)
    if problem:
        errors.append(problem)
    launchable, not_launchable = [], []
    for entry in entries:
        record, why = classify_entry(entry, rows.get(entry.get("name")), day)
        if record:
            launchable.append(record)
        elif entry.get("status") not in (None, "spec"):
            not_launchable.append({"name": str(entry.get("name")), "reason": why})
    used, limit, switch = launches_today(c.root_of(folder), day), backstop(), launch_switch()
    out = {
        "status": "ok", "date": day, "launches": switch, "launches_today": used, "backstop": limit,
        "remaining_today": max(0, limit - used), "task_stack": task_stack,
        "fleet": [{k: r.get(k) for k in ("name", "domain", "status", "authority", "last_run", "live", "queued",
                                         "waiting_on_owner", "check")} for r in rows.values()],
        "launchable": launchable if switch == "on" else [],
        "would_be_launchable": [] if switch == "on" else [r["name"] for r in launchable],
        "not_launchable": not_launchable, "errors": errors,
    }
    c.atomic_json(folder / "fleet.json", out)
    return out


def _record(folder, doer, args, status, outcome):
    rows = c.read_json(Path(folder) / "execution.json", default=[]) or []
    row = {"doer": c.flat(doer, 80), "args": c.flat(args, 200), "status": status,
           "outcome": c.flat(outcome, 300), "at": c.now_utc().isoformat(timespec="seconds")}
    rows = [r for r in rows if not (r.get("doer") == row["doer"] and r.get("args") == row["args"])] + [row]
    c.atomic_json(Path(folder) / "execution.json", rows)


def launch(folder, name, registry_file=None):
    folder = Path(folder)
    cycle = c.read_json(folder / "cycle.json")
    if not isinstance(cycle, dict) or cycle.get("dry_run") not in (True, False):
        return {"status": "refused", "reason": "no cycle.json with dry_run true or false: "
                                               "a cycle of unknown mode launches nothing"}, c.STOP
    decision = c.read_json(folder / "decision.json") or {}
    planned = next((a for a in decision.get("launches") or [] if isinstance(a, dict) and a.get("orchestrator") == name), None)
    doer = f"{LAUNCH_PREFIX}{name}"
    if planned is None:
        return {"status": "refused", "reason": f"{name} is not a launch the decide check accepted this cycle"}, c.STOP
    done = [r for r in c.read_json(folder / "execution.json", default=[]) or []
            if isinstance(r, dict) and r.get("doer") == doer]
    if done:
        return {"status": "refused", "reason": f"{name} was already handled this cycle ({done[-1].get('status')})"}, c.STOP
    args = " ".join(f"{k}={v}" for k, v in sorted((planned.get("params") or {}).items()))
    why = f"{planned.get('trigger')}: {planned.get('reason')}"

    def record(status, outcome):
        _record(folder, doer, args, status, outcome)

    day = str(cycle.get("date") or c.local_now().date().isoformat())
    entries, problem = registry_entries(registry_file)
    entry = next((e for e in entries if e.get("name") == name), None)
    if entry is None:
        refusal = problem or f"{name} is not in the registry"
        record("refused", f"registry: {refusal}")
        return {"status": "refused", "orchestrator": name, "reason": refusal}, c.STOP
    current, refusal = classify_entry(entry, None, day)
    if current is None:
        record("refused", f"registry: {refusal}")
        return {"status": "refused", "orchestrator": name, "reason": refusal}, c.STOP
    params, problem = c.check_params(planned.get("params"), current["inputs"])
    if problem:
        record("refused", f"registry: {problem}")
        return {"status": "refused", "orchestrator": name, "reason": problem}, c.STOP
    args = " ".join(f"{k}={v}" for k, v in sorted(params.items()))
    mode = "dry run" if current["mode"] == "dry-run" else "live"
    if cycle["dry_run"] is not False:
        record("dry-run", f"would launch ({mode}); {why}")
        return {"status": "would_launch", "orchestrator": name, "mode": current["mode"]}, c.OK
    if launch_switch() != "on":
        record("refused", "fleet launches are off (setting fleet_launches)")
        return {"status": "refused", "reason": "fleet launches are off"}, c.STOP
    limit = backstop()
    if launches_today(c.root_of(folder), day) >= limit:
        return backstop_hit(folder, record, limit)
    argv = [sys.executable, str(FLEET_LAUNCH), name, "--authority", AUTHORITY, "--cap", str(limit),
            "--by", c.CYCLE_AGENT, "--format", "json"]
    if current["mode"] == "dry-run":
        argv.append("--dry-run")
    for key, value in sorted(params.items()):
        argv += ["--params", f"{key}={value}"]
    code, out, err = c.run_script(argv, LAUNCH_TIMEOUT_S)
    answer = c.load_object(out) or {}
    lines = answer.get("output") if isinstance(answer.get("output"), list) else []
    said = c.flat(lines[0] if lines else c.first_line(out, err), 160)
    if code == 0:
        record("launched", f"{said} ({mode}); {why}")
        return {"status": "launched", "orchestrator": name, "mode": current["mode"], "queue": said,
                "at": datetime.now().astimezone().isoformat(timespec="seconds")}, c.OK
    if code == 1:
        reason = c.flat(answer.get("reason") or said or "refused", 200)
        if "daily cap reached" in reason:
            return backstop_hit(folder, record, limit)
        record("refused", f"fleet_launch.py refused: {reason}")
        return {"status": "refused", "orchestrator": name, "reason": reason}, c.STOP
    record("failed", f"fleet_launch.py exit {code}: {said or 'no output'}")
    return {"status": "failed", "orchestrator": name, "reason": said or f"exit {code}"}, c.STOP


def backstop_hit(folder, record, limit):
    """Refuse a launch at the backstop and tell the owner once a day (never fails the cycle)."""
    record("refused", f"the daily backstop of {limit} launches is reached")
    try:
        told = c.notify(folder, "backstop", c.root_of(folder), backstop=limit).get("status", "not sent")
    except Exception as exc:  # a message that did not go never fails a cycle
        told = f"not sent: {c.safe(exc)[:80]}"
    return {"status": "refused", "reason": "daily backstop reached", "backstop": limit, "owner_told": told}, c.STOP


def main(argv=None):
    p = argparse.ArgumentParser(description="The fleet as the cycle sees it, and its one launch path. One JSON object out.")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot", help="Write fleet.json")
    s.add_argument("cycle_dir")
    s.add_argument("--registry", default=None, help="Fleet registry (default: orchestrator-fleet's setting)")
    s.add_argument("--no-checks", action="store_true", help="Do not run each orchestrator's check")
    l = sub.add_parser("launch", help="Launch one accepted orchestrator, and record it")
    l.add_argument("cycle_dir")
    l.add_argument("name")
    l.add_argument("--registry", default=None)
    args = p.parse_args(argv)
    try:
        folder = c.cycle_dir(args.cycle_dir)
        if args.cmd == "snapshot":
            out = snapshot(folder, args.registry, checks=not args.no_checks)
            shown = {k: v for k, v in out.items() if k not in ("fleet", "launchable", "not_launchable")}
            shown["launchable"] = [f"{r['name']} ({r['mode']})" for r in out["launchable"]]
            c.emit(shown, c.OK)
        out, code = launch(folder, args.name, args.registry)
    except (c.Bad, OSError) as exc:
        c.fail(str(exc))
    c.emit(out, code)


if __name__ == "__main__":
    main()
