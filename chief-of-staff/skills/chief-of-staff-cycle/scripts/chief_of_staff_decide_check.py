#!/usr/bin/env python3
"""chief-of-staff-decide-check: validate the decider's output against the owner's doer registry.

    chief_of_staff_decide_check.py CYCLE_DIR [--raw FILE] [--max 2]

The owner's doer registry (the file the setting doer_registry names) is the execution
boundary: a doer name that is not in it is never dispatched, whatever the decider wrote, and
every argument must match the doer's pattern in full. With no registry, no doer is accepted.
At most --max dispatches are accepted (the overflow is skipped and named; --max can lower the
cap of two, never raise it), and at most one improvement: the first whose target is the
SKILL.md of a skill the registry runs, never this skill's own. A target may be
given as the skill's name or as a path ending in <skill>/SKILL.md.

The decider's launches of registered orchestrators are checked against the cycle's fleet
snapshot (fleet.json from chief_of_staff_fleet.py snapshot): the owner's switch, which
orchestrators the cycle may launch and in which mode, the trigger (off-schedule only), each
param against the entry's pattern, and nothing that succeeded today without new_evidence.
With no snapshot, or the switch off, every launch is skipped and named.

The reply may be bare JSON, fenced JSON or JSON inside prose; the first balanced object is
taken. Writes decision.json in the cycle folder. Results: ok (exit 0), parse_failed or empty
(exit 3: no dispatches this cycle; the receipt still runs). Exit 2 when it could not run.

Example:
    python3 chief_of_staff_decide_check.py ~/state/chief-of-staff/cycles/2030-03-04/061500
"""

import argparse
import json
import re
from pathlib import Path

import _common as c

MAX_DISPATCHES = 2
MAX_FIELD = 300
LAUNCH_PREFIX = "launch:"


def load_decision(raw):
    """The decision object from the worker's reply, a runner's JSON envelope, or prose."""
    try:
        env = json.loads(raw)
        if isinstance(env, dict):
            if "dispatches" in env or "priorities" in env:
                return env
            if isinstance(env.get("result"), dict):
                return env["result"]
            if isinstance(env.get("result"), str):
                raw = env["result"]
    except (ValueError, TypeError):
        pass
    return c.load_object(raw) or {}


def normalize_target(target):
    """A skill name from a target given as a name or as a path ending in <skill>/SKILL.md."""
    t = str(target or "").strip().rstrip("/")
    m = re.search(r"(?:^|/)([a-z0-9][a-z0-9-]*)/SKILL\.md$", t)
    if m:
        return m.group(1)
    return t if re.fullmatch(r"[a-z0-9][a-z0-9-]*", t) else ""


def classify(decision, registry, max_dispatches=MAX_DISPATCHES):
    accepted, skipped = [], []
    doers = registry["doers"]
    raw = decision.get("dispatches")
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict):
            skipped.append(("<malformed>", "dispatch entry is not an object"))
            continue
        doer, args = c.flat(entry.get("doer"), 80), c.flat(entry.get("args"), 200)
        spec = doers.get(doer)
        if spec is None:
            why = registry["retired"].get(doer) or (registry["problems"][0] if not doers and registry["problems"]
                                                   else "not in the doer registry")
            skipped.append((doer or "<empty>", why))
            continue
        pattern = spec["args"]
        if pattern is None and args:
            skipped.append((doer, f"takes no arguments, got: {args}"))
            continue
        if pattern is not None and args and not re.fullmatch(pattern, args):
            skipped.append((doer, f"arguments rejected by registry pattern: {args}"))
            continue
        if pattern is not None and not args and not spec["default_args"] and not re.fullmatch(pattern, ""):
            skipped.append((doer, "arguments are required and none were given"))
            continue
        if len(accepted) >= max_dispatches:
            skipped.append((doer, f"over the cap of {max_dispatches} dispatches per cycle"))
            continue
        accepted.append({"doer": doer, "args": args or spec["default_args"], "route": spec["route"],
                         "skill": spec.get("skill", ""), "worker": spec["worker"],
                         "confidence": c.flat(entry.get("confidence"), 20).lower() or "unstated",
                         "reason": c.flat(entry.get("reason"), MAX_FIELD)})
    return accepted, skipped


def first_improvement(decision, registry):
    rejected = []
    surface = set(c.doer_skills(registry["doers"]))
    raw = decision.get("improvements")
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict):
            rejected.append(("<malformed>", "improvement entry is not an object"))
            continue
        skill = normalize_target(c.flat(entry.get("target"), 200))
        change = c.flat(entry.get("change"), 600)
        if not skill or not change:
            rejected.append((c.flat(entry.get("target"), 80) or "<empty>", "missing target or change"))
            continue
        if skill not in surface:
            rejected.append((skill, "outside the improvement surface: only the SKILL.md of a doer skill in the registry"))
            continue
        return {"target": skill, "change": change, "rationale": c.flat(entry.get("rationale"), MAX_FIELD)}, rejected
    return None, rejected


def _name(entry):
    return c.flat(entry.get("orchestrator") or entry.get("name"), 80) if isinstance(entry, dict) else ""


def check_launches(decision, fleet):
    """The decider's launches, checked against this cycle's fleet snapshot."""
    raw = decision.get("launches")
    entries = raw if isinstance(raw, list) else []
    accepted, skipped = [], []
    if not entries:
        return accepted, skipped
    if not isinstance(fleet, dict):
        return [], [(f"{LAUNCH_PREFIX}{_name(e)}", "no fleet snapshot this cycle") for e in entries]
    if fleet.get("launches") != "on":
        return [], [(f"{LAUNCH_PREFIX}{_name(e)}", "fleet launches are off (setting fleet_launches)") for e in entries]
    allowed = {r["name"]: r for r in fleet.get("launchable") or [] if isinstance(r, dict) and r.get("name")}
    refused = {r["name"]: r["reason"] for r in fleet.get("not_launchable") or [] if isinstance(r, dict)}
    for entry in entries:
        name = _name(entry)
        label = f"{LAUNCH_PREFIX}{name or '<empty>'}"
        if not isinstance(entry, dict):
            skipped.append((label, "launch entry is not an object"))
            continue
        record = allowed.get(name)
        if record is None:
            skipped.append((label, refused.get(name, "not a registered orchestrator the cycle may launch")))
            continue
        if any(a["orchestrator"] == name for a in accepted):
            skipped.append((label, "already launched this cycle"))
            continue
        trigger = c.flat(entry.get("trigger"), 20).lower()
        if trigger not in record["triggers_allowed"]:
            skipped.append((label, f"trigger '{trigger or 'none'}' is not one of "
                                   f"{', '.join(record['triggers_allowed'])}: a launch is off-schedule only"))
            continue
        params, problem = c.check_params(entry.get("params"), record["inputs"])
        if problem:
            skipped.append((label, problem))
            continue
        evidence = c.flat(entry.get("new_evidence"), 300)
        if record.get("succeeded_today") and not evidence:
            skipped.append((label, "it succeeded today and the launch names no new_evidence"))
            continue
        accepted.append({"orchestrator": name, "params": params, "mode": record["mode"], "trigger": trigger,
                         "new_evidence": evidence, "confidence": c.flat(entry.get("confidence"), 20).lower() or "unstated",
                         "reason": c.flat(entry.get("reason"), 300)})
    return accepted, skipped


def check(raw, registry, max_dispatches=MAX_DISPATCHES, fleet=None):
    max_dispatches = max(0, min(int(max_dispatches), MAX_DISPATCHES))
    decision = load_decision(raw)
    if not decision:
        return {"status": "parse_failed" if raw.strip() else "empty", "accepted": [], "launches": [],
                "skipped": [], "improvement": None, "decisions_needed": 0, "decision": {}}
    accepted, skipped = classify(decision, registry, max_dispatches)
    launches, launch_skipped = check_launches(decision, fleet)
    improvement, rejected = first_improvement(decision, registry)
    needed = decision.get("decisions_needed")
    return {"status": "ok", "accepted": accepted, "launches": launches,
            "skipped": [{"name": n, "reason": r} for n, r in skipped + launch_skipped + rejected],
            "improvement": improvement, "decisions_needed": len(needed) if isinstance(needed, list) else 0,
            "priorities": [c.flat(p, MAX_FIELD) for p in decision.get("priorities") or []][:5],
            "decision": decision}


def main(argv=None):
    p = argparse.ArgumentParser(description="Validate the decision against the doer registry; write decision.json.")
    p.add_argument("cycle_dir")
    p.add_argument("--raw", default=None, help="The decider's reply (default CYCLE_DIR/decide-raw.txt)")
    p.add_argument("--max", dest="max_dispatches", type=int, default=MAX_DISPATCHES,
                   help=f"Lower the cap for this cycle; above {MAX_DISPATCHES} is clamped")
    args = p.parse_args(argv)
    try:
        folder = c.cycle_dir(args.cycle_dir)
        source = Path(args.raw).expanduser() if args.raw else folder / "decide-raw.txt"
        text = source.read_text(encoding="utf-8", errors="replace") if source.exists() else ""
        out = check(text, c.load_doers(), args.max_dispatches, c.read_json(folder / "fleet.json"))
        c.atomic_json(folder / "decision.json", out)
    except (c.Bad, OSError) as exc:
        c.fail(str(exc))
    c.emit({k: v for k, v in out.items() if k != "decision"}, c.OK if out["status"] == "ok" else c.STOP)


if __name__ == "__main__":
    main()
