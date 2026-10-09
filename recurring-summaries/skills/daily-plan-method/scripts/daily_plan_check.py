#!/usr/bin/env python3
"""daily-plan-check: whether the day's plan pass is done, computed from the Run's files, the
state folder and the Portal note, never claimed.

Tests of done.
  Morning
    plan        a plan file for the day and pass with the plan's shape; unless it is a dry
                run's or --offline, the day's note holds the morning block and is PRIVATE.
    top-three   one to three items, each with a reason, a portal:// reference and a slot
                (HH:MM to a later HH:MM) or a stated reason for none; no slot overlaps a
                meeting or hold in the pull.
    conflicts   every conflict the pull computed and every external meeting it found without
                prep appears in the plan.
  Evening
    plan        as above, for the evening block.
    close       every item of the morning's top three has an outcome; done carries evidence
                (portal:// or https://); moved carries a later date and an edit op setting
                that due date, not refused or failed in apply.json; carried and dropped carry
                a reason; tomorrow's three are named.

Inputs: DATE (blank: today in the owner's timezone), --pass (blank: by the clock), --run (the
Run folder with plan.json, pull.json, changes.json, apply.json; without it, the state folder's
published copy). The Portal (setting portal_mcp_config) for the note, unless --offline. The
state folder is --state or <state_dir>/daily-plan.

Output: text, or --format json. --precheck prints one line, WORK: or NOTHING: (weekend,
before the pass's time, or the note already holds the pass's block). Exit 0 whenever it ran,
2 on a bad argument.

Example:
  python3 daily_plan_check.py 2030-03-04 --pass morning --run RUN
"""

import argparse
import json
import re
import sys
from datetime import datetime

import _common as c

LINK = re.compile(r"^https://\S+$")
TASK_ID = re.compile(r"([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})")


def tid(ref):
    m = TASK_ID.search(str(ref or ""))
    return m.group(1).lower() if m else ""


def minutes(text):
    return int(text[:2]) * 60 + int(text[3:]) if c.HHMM.match(str(text or "")) else None


def test_plan(plan, problems, pass_, note, offline):
    gaps = (["no plan file for the day and pass"] if plan is None else []) + problems
    published = None
    if plan is not None and not problems:
        if plan.get("dry_run"):
            published = "dry run: not published"
        elif offline or note is None:
            published = "not checked (offline)"
        elif not note.get("exists"):
            gaps.append("the day's plan note is not in the Portal")
        elif not note.get(f"has_{pass_}"):
            gaps.append(f"the day's note has no {pass_} block")
        else:
            published = note.get("ref")
            if str(note.get("visibility") or "").upper() != "PRIVATE":
                gaps.append(f"the note is {note.get('visibility')}, not PRIVATE")
    return {"met": not gaps, "gaps": gaps, "published": published}


def busy_spans(pull):
    out = []
    for event in ((pull or {}).get("calendar") or {}).get("events") or []:
        if event.get("kind") in ("meeting", "hold"):
            s, e = minutes(event.get("start")), minutes(event.get("end"))
            if s is not None and e is not None:
                out.append((s, e, str(event.get("title") or "")))
    return out


def test_top_three(plan, pull):
    gaps, top = [], plan.get("top_three") or []
    if not 1 <= len(top) <= 3:
        gaps.append(f"{len(top)} top item(s); the plan names one to three")
    busy = busy_spans(pull)
    for n, item in enumerate(top, start=1):
        if not isinstance(item, dict):
            gaps.append(f"item {n} is not an object")
            continue
        name = str(item.get("title") or f"item {n}")[:60]
        if not str(item.get("reason") or "").strip():
            gaps.append(f"{name}: no reason")
        if not c.REF.match(str(item.get("ref") or "")):
            gaps.append(f"{name}: no portal:// reference")
        slot = item.get("slot") if isinstance(item.get("slot"), dict) else None
        if slot:
            s, e = minutes(slot.get("start")), minutes(slot.get("end"))
            if s is None or e is None or e <= s:
                gaps.append(f"{name}: slot {slot.get('start')}-{slot.get('end')} is not a time range")
            else:
                gaps += [f"{name}: slot {slot['start']}-{slot['end']} overlaps {t[:50]}"
                         for bs, be, t in busy if s < be and bs < e]
        elif not str(item.get("no_slot") or "").strip():
            gaps.append(f"{name}: no slot and no reason for none")
    return {"met": not gaps, "gaps": gaps, "items": len(top)}


def test_conflicts(plan, pull):
    if pull is None:
        return {"met": False, "gaps": ["no pull.json in the Run to check the conflicts against"]}
    cal = pull.get("calendar") or {}
    pair = lambda x: frozenset((str(x.get("a")), str(x.get("b"))))  # noqa: E731
    listed = {pair(x) for x in plan.get("conflicts") or [] if isinstance(x, dict)}
    gaps = [f"conflict {x.get('when')} not listed: {str(x.get('a_title'))[:40]} and {str(x.get('b_title'))[:40]}"
            for x in cal.get("conflicts") or [] if pair(x) not in listed]
    prepped = {str(p.get("ref")) for p in plan.get("prep") or [] if isinstance(p, dict)}
    gaps += [f"external meeting without prep not listed: {m.get('start')} {str(m.get('title'))[:50]}"
             for m in cal.get("needs_prep") or [] if str(m.get("ref")) not in prepped]
    return {"met": not gaps, "gaps": gaps, "conflicts": len(cal.get("conflicts") or []),
            "needs_prep": len(cal.get("needs_prep") or [])}


def test_close(plan, day, morning, changes, applied):
    close = plan.get("close") if isinstance(plan.get("close"), dict) else None
    if close is None:
        return {"met": False, "gaps": ["the evening plan has no close"]}
    gaps = []
    items = [i for i in close.get("items") or [] if isinstance(i, dict)]
    by_task = {tid(i.get("ref")): i for i in items if tid(i.get("ref"))}
    by_title = {str(i.get("title") or "").strip().lower(): i for i in items}
    for planned in morning:
        key = tid(planned.get("ref"))
        if not (by_task.get(key) if key else by_title.get(str(planned.get("title") or "").strip().lower())):
            gaps.append(f"no outcome for the planned {str(planned.get('title'))[:60]}")
    ops = [o for o in (changes or {}).get("ops") or [] if isinstance(o, dict)]
    results = {str(r.get("id")): r for r in (applied or {}).get("results") or [] if isinstance(r, dict)}
    for item in items:
        name = str(item.get("title") or item.get("ref") or "an item")[:60]
        outcome = item.get("outcome")
        if outcome not in c.OUTCOMES:
            gaps.append(f"{name}: outcome {outcome!r} is not one of {', '.join(c.OUTCOMES)}")
        elif outcome == "done":
            ev = str(item.get("evidence") or "")
            if not (c.REF.match(ev) or LINK.match(ev)):
                gaps.append(f"{name}: done with no evidence reference")
        elif outcome == "moved":
            new = str(item.get("new_date") or "")
            if not c.DAY.match(new) or new <= day.isoformat():
                gaps.append(f"{name}: moved without a later date")
                continue
            match = [o for o in ops if o.get("op") == "edit" and tid(o.get("task")) == tid(item.get("ref"))
                     and str((o.get("set") or {}).get("due_date")) == new]
            if not match:
                gaps.append(f"{name}: moved to {new} with no edit op setting that due date")
            elif results.get(str(match[0].get("id")), {}).get("outcome") in ("refused", "failed"):
                gaps.append(f"{name}: the re-date op {match[0].get('id')} was "
                            f"{results[str(match[0].get('id'))]['outcome']}")
        elif not str(item.get("reason") or "").strip():
            gaps.append(f"{name}: {outcome} with no reason")
    if not [t for t in close.get("tomorrow") or [] if isinstance(t, dict) and str(t.get("title") or "").strip()]:
        gaps.append("tomorrow's three are not named")
    return {"met": not gaps, "gaps": gaps, "items": len(items), "planned": len(morning)}


def check(day, pass_, run, state, note, offline):
    plan, problems, pull = None, [], None
    changes = applied = None
    if run is not None:
        if not run.is_dir():
            raise c.Stop(f"no Run folder {run}")
        source = run / "plan.json"
        pull = c.read_json(run / "pull.json")
        changes = c.read_json(run / "changes.json")
        applied = c.read_json(run / "apply.json") or c.read_json(run / "apply-dry-run.json")
    else:
        source = c.state_file(state, day, pass_)
    raw = c.read_json(source)
    if raw is not None:
        problems = c.plan_problems(raw, day, pass_)
        plan = raw if isinstance(raw, dict) else None
    tests = {"plan": test_plan(plan, problems, pass_, note, offline)}
    usable = plan is not None and not problems
    none = {"met": False, "gaps": ["no usable plan"]}
    if pass_ == "morning":
        tests["top-three"] = test_top_three(plan, pull) if usable else none
        tests["conflicts"] = test_conflicts(plan, pull) if usable else dict(none)
    else:
        if isinstance(pull, dict) and isinstance(pull.get("morning_plan"), dict):
            morning = pull["morning_plan"].get("top_three") or []
        else:
            saved = c.read_json(c.state_file(state, day, "morning")) if state else None
            morning = (saved.get("top_three") or []) if isinstance(saved, dict) else []
        tests["close"] = (test_close(plan, day, [m for m in morning if isinstance(m, dict)], changes, applied)
                          if usable else none)
    met = sum(1 for t in tests.values() if t["met"])
    return {"tool": "daily-plan-check", "date": day.isoformat(), "pass": pass_, "plan": str(source),
            "run": str(run) if run else None, "note": note, "tests": tests, "met": met, "of": len(tests),
            "done": met == len(tests)}


def precheck(day, pass_, now, morning_at, evening_at, note, note_error=""):
    if day.weekday() >= 5:
        return f"NOTHING: {day.isoformat()} is a {day.strftime('%A')}; the daily plan runs on weekdays"
    at = morning_at if pass_ == "morning" else evening_at
    if (now.hour, now.minute) < at and now.date() == day:
        return f"NOTHING: the {pass_} pass starts at {at[0]:02d}:{at[1]:02d}"
    if note_error:
        return f"WORK: {day.isoformat()} {pass_}: the Portal note could not be read ({note_error}); plan anyway"
    if note and note.get(f"has_{pass_}"):
        return f"NOTHING: {day.isoformat()} {pass_} is already in {note.get('ref')}"
    return f"WORK: {day.isoformat()} {pass_} pass not written yet"


def render(result):
    out = [f"daily-plan-check {result['date']} {result['pass']}",
           f"{'DONE' if result['done'] else 'NOT DONE'} ({result['met']} of {result['of']} tests met)"]
    for n, (name, test) in enumerate(result["tests"].items(), start=1):
        extra = f" ({test['published']})" if test.get("published") else ""
        out.append(f"{n} {name}: {'MET' if test['met'] else 'NOT MET'}{extra}")
        out += [f"  - {gap}" for gap in test["gaps"]]
    return "\n".join(out)


def main(argv=None, client=None):
    p = argparse.ArgumentParser(prog="daily_plan_check.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("day", nargs="?", default="", help="yyyy-mm-dd (blank: today)")
    p.add_argument("--pass", dest="pass_", default="", help="morning or evening (blank: by the clock)")
    p.add_argument("--run", dest="run_dir", default="", help="The Run folder (plan.json, pull.json, changes.json, apply.json)")
    p.add_argument("--offline", action="store_true", help="Do not read the Portal; the note is not checked")
    p.add_argument("--format", dest="fmt", choices=["text", "json"], default="text")
    p.add_argument("--precheck", action="store_true", help="One line, WORK: or NOTHING:, for a scheduler")
    p.add_argument("--morning-at", default="06:30", help="Precheck: the morning pass's time")
    p.add_argument("--evening-at", default="18:00", help="Precheck: the evening pass's time")
    p.add_argument("--tz", dest="tz_name", default="", help="IANA timezone (default the owner's, from whoami)")
    p.add_argument("--state", dest="state_path", default="", help="The state folder (default <state_dir>/daily-plan)")
    p.add_argument("--config", default=None, help="MCP config holding the Portal (default: setting portal_mcp_config)")
    p.add_argument("--server", default=None, help="Server name in the MCP config (default: setting portal_server)")
    args = p.parse_args(argv)

    def bad(exc):
        print(c.safe(f"ERROR {exc}"), file=sys.stderr)
        sys.exit(2)

    try:
        times = (c.hhmm(args.morning_at, "--morning-at"), c.hhmm(args.evening_at, "--evening-at"))
        run = c.guard_run_path(c.blank(args.run_dir)) if c.blank(args.run_dir) else None
    except c.Stop as exc:
        bad(exc)
    tz_text, note_error = c.blank(args.tz_name), ""
    if not args.offline:
        try:
            client = client or c.Portal(args.config, args.server)
            tz_text = tz_text or c.owner_timezone(client)
        except Exception as exc:  # reported on the line, never fatal
            note_error, client = type(exc).__name__, None
    else:
        client = None
    day, pass_ = args.day, args.pass_
    try:
        tz = c.zone(tz_text)
        now = datetime.now(tz)
        if run is not None and not (c.blank(day) and c.blank(pass_)):
            # A blank date or pass with a Run is the Run's own: what the prepare step pulled.
            for name in ("plan.json", "pull.json"):
                found = c.read_json(run / name) if run.is_dir() else None
                if isinstance(found, dict):
                    day = c.blank(day) or str(found.get("date") or "")
                    pass_ = c.blank(pass_) or str(found.get("pass") or "")
                    break
        the_day, the_pass = c.resolve(day, pass_, tz, now)
    except c.Stop as exc:
        bad(exc)
    note = None
    if client is not None:
        try:
            found = c.find_notes(client, the_day)
            note = c.note_summary(found[0] if found else None, max(0, len(found) - 1))
        except Exception as exc:
            note_error = type(exc).__name__
    if args.precheck:
        print(precheck(the_day, the_pass, now, times[0], times[1], note, note_error))
        sys.exit(0)
    try:
        try:
            state = c.state_root(args.state_path)
        except c.Stop:
            if run is None:
                raise
            state = None  # with a Run the state folder is only a fallback for the morning plan
        result = check(the_day, the_pass, run, state, note, args.offline or client is None)
    except c.Stop as exc:
        bad(exc)
    if note_error:
        result["portal_error"] = note_error
    print(json.dumps(result, indent=1, default=str) if args.fmt == "json" else render(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
