# /// script
# dependencies = ["pyyaml"]
# ///
"""Whether one engagement's delivery is kept true, computed from its files.

Inputs: ENGAGEMENT (a Context name or path; _common.py says what it holds), and optionally
--working (a dry run's copy of the working folder), --pack (the Run folder or pack.json, for
the tasks and authority tests), --changes (the change set; default changes.json in the Run
folder), --as-of, --contexts-dir.

The eight tests:
 1 sow         the SOW the rules name is on disk, or the rules record there is none.
 2 plan        PLAN.md has a Milestones table; each milestone has an owner, a planned date and an
               acceptance test; every Scope baseline Id is in it.
 3 milestones  nothing not delivered is past due without a plan change to a later date, or inside
               its lead time without evidence of progress or a plan change.
 4 changes     a planned date that differs from its baseline has a change to that date, approved
               by the owner when it is a client date.
 5 raid        every open RAID item has an owner, a source and a review date not yet passed.
 6 tasks       (with --pack) every open task has an owner and a due date, or the change set holds
               an op or question for it.
 7 authority   (with --pack and a change set) the change set touches only the engagement's tasks
               and assigns work only to the owner or the Assignable people.
 8 session     a session is recorded for the as-of date.

Prints a text report, the JSON result (--format json), or with --precheck one line,
`WORK: <reason>` or `NOTHING: <reason>`, for a scheduler. --out also writes the JSON.
Exit 0 whenever it ran; 2 on a bad argument or a missing Context or rules file.

Example:
  python3 delivery_check.py northwind-delivery --pack RUN --working RUN/delivery/working --format json
"""

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import _common as dc

PRECHECK_TESTS = ("milestones", "changes", "raid")


def day(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def result(met, gaps, **extra):
    return {"met": met, "gaps": gaps, **extra}


def test_sow(sow):
    if sow["state"] == "files":
        return result(True, [], state="files", files=[str(p) for p in sow["files"]], note=sow["note"])
    if sow["state"] == "none":
        return result(True, [], state="none", note=f"no SOW, by the owner's word: {sow['note']}")
    return result(False, [f"no signed SOW on file ({sow['note']}): ask the owner for it, or for their word "
                          "that there is none; the plan carries no baseline until then"],
                  state="missing", question=True)


def test_plan(plan, rules):
    gaps, seen = list(plan["problems"]), {}
    for m in plan["milestones"]:
        seen[m["id"]] = seen.get(m["id"], 0) + 1
        missing = [k for k in ("milestone", "owner", "planned due", "acceptance") if not m.get(k)]
        if missing:
            gaps.append(f"{m['id']}: no {', '.join(missing)}")
        for key in ("planned due", "baseline due"):
            if m.get(key) and not dc.DATE_RE.match(m[key]):
                gaps.append(f"{m['id']}: {key} {m[key]!r} is not yyyy-mm-dd")
    gaps += [f"{i}: listed {n} times" for i, n in seen.items() if n > 1]
    if plan["present"]:
        for b in rules["baseline"]:
            if b["id"] not in seen:
                what = b.get("deliverable") or b.get("milestone") or ""
                gaps.append(f"baseline {b['id']}{f' ({what})' if what else ''} is not in the plan")
    return result(not gaps, gaps, milestones=len(plan["milestones"]))


def changes_for(rows, milestone):
    return [r for r in rows if r.get("kind") == "change" and r.get("item") == milestone
            and r.get("state") in ("proposed", "approved")]


def test_milestones(plan, rows, rules, today):
    by_id = {r["id"]: r for r in rows}
    gaps, late = [], []
    horizon = today + timedelta(days=rules["lead_time_days"])
    for m in plan["milestones"]:
        row = by_id.get(f"milestone:{m['id']}") or {}
        state = row.get("state") or "planned"
        due = day(m.get("planned due"))
        if state in dc.DONE_MILESTONE or due is None:
            continue
        changes = changes_for(rows, m["id"])
        if due < today:
            late.append(m["id"])
            if not any((day(c.get("due")) or date.min) >= today for c in changes):
                gaps.append(f"{m['id']} was due {due} and is {state}, with no plan change to a later date")
        elif due <= horizon and not dc.blank(row.get("evidence")) and not changes:
            gaps.append(f"{m['id']} is due {due}, inside the {rules['lead_time_days']}-day lead time, "
                        "with no evidence of progress and no plan change")
    return result(not gaps, gaps, late=late)


def test_changes(plan, rows):
    gaps, waiting = [], []
    for m in plan["milestones"]:
        changes = changes_for(rows, m["id"])
        client = m.get("client date") == "yes"
        waiting += [f"{c['id']} moves client date {m['id']} to {c.get('due')}: waiting on the owner"
                    for c in changes if c.get("state") == "proposed" and client]
        base, planned = m.get("baseline due"), m.get("planned due")
        if not base or not planned or base == planned:
            continue
        if not any(c.get("due") == planned and (c.get("state") == "approved" or not client) for c in changes):
            what = "an approved change" if client else "a recorded change"
            gaps.append(f"{m['id']} is planned {planned} against baseline {base} without {what} to that date")
    return result(not gaps, gaps, waiting_on_owner=waiting)


def test_raid(rows, today):
    gaps = []
    open_rows = [r for r in rows if r.get("state") == "open"]
    for r in open_rows:
        missing = [n for n in ("owner", "source", "review_by") if not dc.blank(r.get(n))]
        if missing:
            gaps.append(f"{r['id']}: no {', '.join(missing)}")
        review = day(r.get("review_by"))
        if review and review < today:
            gaps.append(f"{r['id']} ({r.get('title')}) was due for review {review}")
    return result(not gaps, gaps, open=len(open_rows))


def test_tasks(pack, changes):
    if pack is None:
        return result(True, [], judged=False, note="not judged without --pack")
    tasks = pack.get("tasks") or {}
    if not tasks.get("read"):
        return result(False, [f"the engagement's tasks could not be read ({tasks.get('error') or 'not read'})"],
                      judged=True)
    owner = str(pack.get("owner_contact") or "").lower()
    handled = set()
    for op in (changes or {}).get("ops") or []:
        if isinstance(op, dict):
            handled |= {dc.uuid_in(op.get(k)) for k in ("task", "into")} - {""}
    for q in (changes or {}).get("questions") or []:
        if isinstance(q, dict) and dc.uuid_in(q.get("task")):
            handled.add(dc.uuid_in(q.get("task")))
    gaps = []
    for t in tasks.get("items") or []:
        tid, who = str(t.get("id") or "").lower(), str(t.get("owner_contact_id") or "").lower()
        problems = (["no owner"] if not who else []) + \
                   (["no due date"] if not t.get("due_date") and (not who or who == owner) else [])
        if problems and tid not in handled:
            gaps.append(f"{t.get('title') or tid} ({tid}): {', '.join(problems)}")
    return result(not gaps, gaps, judged=True, open=len(tasks.get("items") or []))


def test_authority(pack, changes):
    if pack is None or changes is None:
        return result(True, [], judged=False, note="not judged without --pack and a change set")
    gaps = [f"{oid}: {why}" for oid, why in dc.authority_problems(changes, pack)]
    return result(not gaps, gaps, judged=True, ops=len(changes.get("ops") or []))


def test_session(rows, today):
    last = dc.latest_session(rows)
    met = last is not None and last >= today
    return result(met, [] if met else [f"no session recorded for {today}" + (f" (last {last})" if last else "")],
                  last=last.isoformat() if last else None)


def changes_file(pack_path, changes):
    if dc.blank(changes):
        return Path(changes.strip()).expanduser()
    if dc.blank(pack_path):
        base = Path(pack_path.strip()).expanduser()
        for run in (base, base.parent, base.parent.parent):
            if (run / dc.CHANGES_JSON).is_file():
                return run / dc.CHANGES_JSON
    return None


def check(engagement, working=None, pack=None, changes=None, as_of=None, contexts=None):
    eng = dc.load_engagement(engagement, contexts)
    pack_data = dc.load_pack(pack.strip()) if dc.blank(pack) else None
    if not dc.blank(working) and pack_data is not None:
        working = (pack_data.get("folders") or {}).get("working")
    folder = dc.working_folder(eng, working)
    today = dc.as_of_date(as_of)
    rules = eng["rules"]
    plan = dc.read_plan(folder / dc.PLAN_MD)
    rows = dc.evidence_ledger(folder).rows()
    raid = dc.raid_ledger(folder).rows()
    changes_path = changes_file(pack, changes)
    change_set = dc.load_json(changes_path, dc.CHANGES_JSON) if changes_path else None
    tests = {
        "sow": test_sow(rules["sow"]),
        "plan": test_plan(plan, rules),
        "milestones": test_milestones(plan, rows, rules, today),
        "changes": test_changes(plan, rows),
        "raid": test_raid(raid, today),
        "tasks": test_tasks(pack_data, change_set),
        "authority": test_authority(pack_data, change_set),
        "session": test_session(rows, today),
    }
    met = sum(1 for t in tests.values() if t["met"])
    last = dc.latest_session(rows)
    return {"engagement": eng["name"], "working": str(folder), "working_exists": folder.is_dir(),
            "plan_present": plan["present"], "rules": str(eng["rules_file"]), "as_of": today.isoformat(),
            "changes": str(changes_path) if changes_path else None,
            "last_session": last.isoformat() if last else None,
            "session_stale_days": rules["session_stale_days"],
            "tests": tests, "met": met, "of": len(tests), "done": met == len(tests)}


def precheck_line(res):
    name = res["engagement"]
    if not res["plan_present"]:
        return f"WORK: {name} has no plan yet: the first plan"
    reasons = [f"{t} ({len(res['tests'][t]['gaps'])} gap(s))" for t in PRECHECK_TESTS if not res["tests"][t]["met"]]
    last = res.get("last_session")
    if last is None:
        reasons.append("no session recorded")
    elif (date.fromisoformat(res["as_of"]) - date.fromisoformat(last)).days >= res["session_stale_days"]:
        reasons.append(f"last session {last}")
    if reasons:
        return f"WORK: {name}: " + "; ".join(reasons)
    waiting = "; the SOW waits on the owner" if not res["tests"]["sow"]["met"] else ""
    return f"NOTHING: {name} is on plan with its RAID reviewed, last session {last}{waiting}"


def render(res):
    out = [f"delivery-check {res['engagement']} as of {res['as_of']} ({res['working']})",
           f"{'DONE' if res['done'] else 'NOT DONE'} ({res['met']} of {res['of']} tests met)"]
    for number, (name, test) in enumerate(res["tests"].items(), start=1):
        label = "MET" if test["met"] else "NOT MET"
        if test.get("judged") is False:
            label += " (not judged)"
        out.append(f"{number} {name}: {label}")
        out += [f"  - {gap}" for gap in test["gaps"]]
        out += [f"  . {line}" for line in test.get("waiting_on_owner") or []]
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(description="Whether one engagement's delivery is kept true, test by test.")
    p.add_argument("engagement", nargs="?", default="", help="Context name or path to a Context YAML file")
    p.add_argument("--working", default="", help="Use this folder as the working folder (a dry run's copy)")
    p.add_argument("--pack", default="", help="The Run folder or pack.json, for the tasks and authority tests")
    p.add_argument("--changes", default="", help="The change set (default: changes.json in the Run folder)")
    p.add_argument("--as-of", default="", help="Judge as of this date (yyyy-mm-dd); blank: today")
    p.add_argument("--contexts-dir", default="", help="Where Context YAML files are found by name")
    p.add_argument("--out", default="", help="Also write the JSON result to this file")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--precheck", action="store_true", help="One line, WORK: or NOTHING:, for a scheduler")
    a = p.parse_args(argv)
    try:
        res = check(a.engagement, a.working, a.pack, a.changes, a.as_of, a.contexts_dir)
    except (dc.Bad, dc.Refused) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    if dc.blank(a.out):
        target = Path(a.out.strip()).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    if a.precheck:
        print(precheck_line(res))
    elif a.format == "json":
        print(json.dumps(res, indent=1))
    else:
        print(render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
