#!/usr/bin/env python3
"""goal-alignment-gather: read the month's facts before the session, and pick the pass.

MONTH is 2030-02, a date in it, or blank for the last full month. The pass is pack (prepare
the note), approve (read the owner's answers) or auto: approve once the month's note is
published (publish.json in the month's folder), pack until then. Read only toward the Portal
and the time study; writes the Run folder only.

The pack pass reads the Portal (domains, goals, projects, tasks of every status), the time
study's tables for the month (--time-home: data/daily_domain_hours.csv, data/time_slots.csv
and domains.csv), the rules file's "## Settings" (--rules, GOAL-ALIGNMENT-RULES.md) and the
approved goal map in the home, and writes RUN/inputs/:
  stack.json     the trust score's goals and projects components, from task-stack-workstream's
                 task_stack_check.py
  domains.json   each active domain's hours and share of work hours, active goals and their top
                 priority, active projects, tasks finished in the month; `unserved`, the domains
                 that took time with no active goal
  goals.json     every active goal with the projects that drive it, what finished and moved
                 under it, its domain's hours, and the flags no_project, starved, quiet
  projects.json  every active project with its goal or none, its tasks, its last activity (bulk
                 edits left out), the goals it could serve, and stop_candidate
  time.json      the month's hours by domain, topic and evidence tier, or why there are none
  cadence.json   monthly or quarterly, the pulse domains in rotation, which of them agents may
                 read, and the strategic goals document and quarterly template paths
  goalmap.json   the approved Portal-goal-to-strategic-goal mapping, and the goals not mapped
  carried.json   last month's items the owner left unsettled
The approve pass reads the published review and every answer and writes RUN/answers.json, a
preview of what will be applied. Both write RUN/pass.json. The first line printed reaches the
session.

Settings: portal_mcp_config (and portal_server); state_dir, or --home (the home is
<state_dir>/goal-alignment); [goal-alignment-workstream] rules_file (or --rules, needed by the
pack pass), time_study_home (or --time-home), and telos_note and quarterly_template when the
rules file does not name them. Exit 0 when it ran; 2 on a bad argument, an unreadable input or a
Portal that cannot be read in the pack pass (a note without facts is not a note).

Example:
  python3 goal_alignment_gather.py --run RUN --rules GOAL-ALIGNMENT-RULES.md --time-home TIME_STUDY
"""

import argparse
import csv
import shutil
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import _common as c

STARVED_HOURS, UNSERVED_HOURS, STOP_DAYS = 4.0, 4.0, 90
PRIORITY = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}
NOT_WORK = ("sleep", "unaccounted")
# Time-study domain groups that are not work: outside work hours, never "time that serves no goal".
NOT_WORK_GROUPS = ("personal", "sleep", "unaccounted")
ITEM_CARRY = ("unanswered", "modified", "unclear", "unavailable", "partial", "refused", "deferred")


def key(name):
    return " ".join(str(name or "").split()).casefold()


def prio(item):
    return PRIORITY.get(str(item.get("priority") or "").upper(), 5)


def ref(kind, item):
    return f"portal://{kind}/{str(item.get('id')).lower()}"


def num(value):
    try:
        return float(value or 0)
    except ValueError:
        return 0.0


# --------------------------------------------------------------------------- project activity

def minute(value):
    when = c.parse_time(value)
    return when.strftime("%Y-%m-%dT%H:%M") if when else None


def bulk_minutes(projects, tasks):
    """`updated_at` minutes shared by 5 projects or 10 tasks: bulk edits, not activity."""
    out = set()
    for rows, floor in ((projects, 5), (tasks, 10)):
        counts = Counter(m for m in (minute(r.get("updated_at")) for r in rows) if m)
        out |= {m for m, n in counts.items() if n >= floor}
    return out


def last_activity(project, tasks, bulk):
    """The latest real timestamp over the project and its tasks."""
    latest = None
    for item in [project, *tasks]:
        for k in ("updated_at", "completed_at", "created_at"):
            if k == "updated_at" and minute(item.get(k)) in bulk:
                continue
            when = c.parse_time(item.get(k))
            if when is not None and (latest is None or when > latest):
                latest = when
    return latest.date() if latest else None


# --------------------------------------------------------------------------- the time study

def read_time(time_home, month):
    """The month's hours from the time study's tables, or why there are none. Topics and
    evidence tiers count work time only."""
    if not (time_home or "").strip():
        return {"present": False, "reason": "no time-study home given"}
    data = Path(time_home).expanduser() / "data"
    daily = data / "daily_domain_hours.csv"
    if not daily.is_file():
        return {"present": False, "reason": f"{daily} does not exist"}
    first, last = month["first"], month["last"]
    by_domain, days, work = {}, 0, 0.0
    skip = {"date", "weekday", "work_hours", "total_hours"}
    with daily.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if not first <= str(row.get("date") or "") <= last:
                continue
            days += 1
            work += num(row.get("work_hours"))
            for col, value in row.items():
                if col and col not in skip:
                    by_domain[col] = by_domain.get(col, 0.0) + num(value)
    if not days:
        return {"present": False, "reason": f"the time study's tables hold no day of {month['month']}"}
    not_work = set(NOT_WORK)
    groups = Path(time_home).expanduser() / "domains.csv"
    if groups.is_file():
        with groups.open(encoding="utf-8", newline="") as fh:
            not_work |= {key(r.get("domain")) for r in csv.DictReader(fh) if key(r.get("domain_group")) in NOT_WORK_GROUPS}
    topics, tiers, windows = {}, {}, set()
    slots = data / "time_slots.csv"
    if slots.is_file():
        with slots.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                if not first <= str(row.get("date") or "") <= last:
                    continue
                if row.get("window"):
                    windows.add(row["window"])
                if key(row.get("domain")) in not_work:
                    continue
                hours = num(row.get("hours"))
                k = (str(row.get("topic") or "unknown"), str(row.get("topic_label") or row.get("topic") or "unknown"))
                topics[k] = topics.get(k, 0.0) + hours
                tier = str(row.get("tier") or "unknown")
                tiers[tier] = tiers.get(tier, 0.0) + hours
    return {"present": True, "month": month["month"], "days_covered": days, "days": month["days"],
            "coverage": round(days / month["days"], 3), "work_hours": round(work, 2),
            "unaccounted_hours": round(sum(v for k, v in by_domain.items() if key(k) == "unaccounted"), 2),
            "windows": sorted(windows), "not_work": sorted(n for n in not_work if n),
            "by_domain": {k: round(v, 2) for k, v in sorted(by_domain.items(), key=lambda kv: -kv[1])},
            "topics": [{"topic": t, "label": lbl, "hours": round(h, 2)}
                       for (t, lbl), h in sorted(topics.items(), key=lambda kv: -kv[1])],
            "tiers": {k: round(v, 2) for k, v in sorted(tiers.items(), key=lambda kv: -kv[1])},
            "source": str(daily)}


# --------------------------------------------------------------------------- the derived inputs

def derive(corpus, month, time, today, goal_map, starved_hours=STARVED_HOURS, unserved_hours=UNSERVED_HOURS,
           stop_days=STOP_DAYS):
    """domains, goals, projects and the goal map, from one read of the stack and the month's
    hours. No I/O."""
    first, last = month["first"], month["last"]
    domains = {str(d.get("id")).lower(): d for d in corpus.get("domain", [])}
    projects = {str(p.get("id")).lower(): p for p in corpus.get("project", [])}
    goals = {str(g.get("id")).lower(): g for g in corpus.get("goal", [])}
    tasks = [t for t in corpus.get("task", []) if not t.get("is_archived")]

    def in_month(value):
        d = c.day(value)
        return bool(d) and first <= d.isoformat() <= last

    def tdomain(t):
        p = projects.get(str(t.get("project_id") or "").lower())
        if p and p.get("domain_id"):
            return str(p["domain_id"]).lower()
        return str(t.get("domain_id") or "").lower() or None

    present = bool(time.get("present"))
    hours_by_name = {key(k): v for k, v in (time.get("by_domain") or {}).items()} if present else {}
    work = float(time.get("work_hours") or 0) if present else 0.0
    not_work = set(time.get("not_work") or NOT_WORK)

    def share(name, hours):
        return None if hours is None or not work or key(name) in not_work else round(hours / work, 3)

    def dhours(did):
        return round(hours_by_name.get(key((domains.get(did) or {}).get("name")), 0.0), 2) if present else None

    active_goal = {gid: g for gid, g in goals.items() if c.is_active_goal(g) and not g.get("is_general")
                   and c.status_of(g) != "DEFERRED"}
    parked_goals = [g for g in goals.values() if c.status_of(g) == "DEFERRED" and not g.get("is_archived")]
    live_projects = {pid: p for pid, p in projects.items() if c.is_active_project(p)}
    children = {}
    for gid, g in goals.items():
        if g.get("parent_goal_id"):
            children.setdefault(str(g["parent_goal_id"]).lower(), []).append(gid)

    def family(gid):
        """The goal and its descendants: a goal is served by its sub-goals' projects too."""
        out, todo = [], [gid]
        while todo:
            x = todo.pop()
            if x not in out:
                out.append(x)
                todo += children.get(x, [])
        return out

    by_project = {}
    for t in tasks:
        by_project.setdefault(str(t.get("project_id") or "").lower(), []).append(t)
    bulk = bulk_minutes(projects.values(), tasks)

    goal_rows = []
    for gid, g in active_goal.items():
        fam = family(gid)
        drive = [p for p in live_projects.values() if str(p.get("goal_id") or "").lower() in fam]
        under = [t for p in drive for t in by_project.get(str(p.get("id")).lower(), [])]
        seen = {id(t) for t in under}
        under += [t for t in tasks if str(t.get("goal_id") or "").lower() in fam and id(t) not in seen]
        done = [t for t in under if c.status_of(t) == "DONE" and in_month(t.get("completed_at"))]
        moved = [t for t in under if in_month(t.get("updated_at")) or in_month(t.get("created_at"))]
        did = str(g.get("domain_id") or "").lower()
        hours = dhours(did)
        goal_rows.append({
            "ref": ref("goal", g), "title": g.get("title"), "domain": (domains.get(did) or {}).get("name"),
            "domain_ref": f"portal://domain/{did}" if did else None, "priority": g.get("priority"),
            "status": g.get("status"), "horizon": g.get("horizon"), "health": g.get("health_status"),
            "parent": f"portal://goal/{str(g['parent_goal_id']).lower()}" if g.get("parent_goal_id") else None,
            "projects": [{"ref": ref("project", p), "name": p.get("name"), "status": p.get("status")} for p in drive],
            "open_tasks": sum(1 for t in under if c.is_open_task(t)), "done_in_month": len(done),
            "done_examples": [{"ref": ref("task", t), "title": t.get("title")} for t in done[:5]],
            "moved_in_month": len(moved), "domain_hours": hours,
            "domain_share": share((domains.get(did) or {}).get("name"), hours),
            "no_project": not drive, "starved": hours is not None and hours < starved_hours and not done,
            "quiet": hours is not None and hours >= starved_hours and not moved, "updated_at": g.get("updated_at")})
    goal_rows.sort(key=lambda r: (prio(r), not r["starved"], not r["no_project"], str(r["domain"]), str(r["title"])))

    goals_by_domain = {}
    for g in active_goal.values():
        goals_by_domain.setdefault(str(g.get("domain_id") or "").lower(), []).append(g)
    project_rows = []
    for pid, p in live_projects.items():
        rows = by_project.get(pid, [])
        latest = last_activity(p, rows, bulk)
        quiet_days = (today - latest).days if latest else None
        gid = str(p.get("goal_id") or "").lower()
        g = goals.get(gid) if gid else None
        goal_live = bool(g) and c.is_active_goal(g)
        did = str(p.get("domain_id") or "").lower()
        project_rows.append({
            "ref": ref("project", p), "name": p.get("name"), "domain": (domains.get(did) or {}).get("name"),
            "status": p.get("status"), "priority": p.get("priority"),
            "goal": {"ref": ref("goal", g), "title": g.get("title"), "status": g.get("status")} if g else None,
            "no_goal": not gid, "goal_closed": bool(g) and not goal_live,
            "open_tasks": sum(1 for t in rows if c.is_open_task(t)),
            "done_in_month": sum(1 for t in rows if c.status_of(t) == "DONE" and in_month(t.get("completed_at"))),
            "last_activity": latest.isoformat() if latest else None, "quiet_days": quiet_days,
            "stop_candidate": (not goal_live) and (quiet_days is None or quiet_days >= stop_days),
            "candidate_goals": [{"ref": ref("goal", x), "title": x.get("title"), "priority": x.get("priority")}
                                for x in sorted(goals_by_domain.get(did, []), key=prio)] if not goal_live else []})
    project_rows.sort(key=lambda r: (not r["no_goal"], not r["stop_candidate"], str(r["domain"]), str(r["name"])))

    done_by_domain = {}
    for t in tasks:
        if c.status_of(t) == "DONE" and in_month(t.get("completed_at")) and tdomain(t):
            done_by_domain[tdomain(t)] = done_by_domain.get(tdomain(t), 0) + 1
    domain_rows, unserved, matched = [], [], set()
    for did, d in domains.items():
        if d.get("is_archived") or d.get("is_active") is False:
            continue
        gs = goals_by_domain.get(did, [])
        hours = dhours(did)
        matched.add(key(d.get("name")))
        top = min((str(x.get("priority")) for x in gs if x.get("priority")), default=None,
                  key=lambda v: PRIORITY.get(v.upper(), 5))
        row = {"ref": f"portal://domain/{did}", "name": d.get("name"), "hours": hours,
               "share": share(d.get("name"), hours), "work": key(d.get("name")) not in not_work,
               "active_goals": len(gs), "top_priority": top,
               "active_projects": sum(1 for p in live_projects.values() if str(p.get("domain_id") or "").lower() == did),
               "done_in_month": done_by_domain.get(did, 0)}
        domain_rows.append(row)
        if hours is not None and hours >= unserved_hours and not gs and row["work"]:
            unserved.append({"name": d.get("name"), "ref": row["ref"], "hours": hours, "why": "no active goal"})
    if present:
        for name, hours in (time.get("by_domain") or {}).items():
            if key(name) not in matched and key(name) not in not_work and hours >= unserved_hours:
                unserved.append({"name": name, "ref": None, "hours": round(hours, 2),
                                 "why": "a time-study domain with no active Portal domain"})
    domain_rows.sort(key=lambda r: -(r["hours"] or 0))

    mapped = {str(k).lower(): v for k, v in ((goal_map or {}).get("goals") or {}).items()}
    return {
        "domains": {"work_hours": work if present else None, "domains": domain_rows, "unserved": unserved},
        "goals": {"active": len(goal_rows), "no_project": sum(1 for r in goal_rows if r["no_project"]),
                  "starved": sum(1 for r in goal_rows if r["starved"]), "quiet": sum(1 for r in goal_rows if r["quiet"]),
                  "goals": goal_rows, "parked": [{"ref": ref("goal", g), "title": g.get("title")} for g in parked_goals]},
        "projects": {"active": len(project_rows), "no_goal": sum(1 for r in project_rows if r["no_goal"]),
                     "stop_candidates": sum(1 for r in project_rows if r["stop_candidate"]), "projects": project_rows},
        "goalmap": {"mapped": [dict(v, goal=f"portal://goal/{k}") for k, v in mapped.items() if k in active_goal],
                    "unmapped": [{"ref": ref("goal", g), "title": g.get("title")} for gid, g in active_goal.items()
                                 if gid not in mapped]}}


def stack_part(built):
    """The trust score and its goals and projects components, with their flagged items."""
    comps = built["overall"]["components"]
    return {"tool": "task-stack-check", "as_of": built.get("as_of"), "score": built["overall"]["score"],
            "components": {k: comps.get(k) for k in ("goals", "projects")},
            "findings": {k: (built.get("findings") or {}).get(k) for k in ("goals", "projects")}}


def carried(home, month):
    """Last month's items the owner never settled, so they come back rather than rot."""
    path = c.month_dir(home, month["previous"]) / c.items_ledger_name(month["previous"])
    if not path.is_file():
        return {"month": month["previous"], "present": False, "items": []}
    return {"month": month["previous"], "present": True,
            "items": [{k: r.get(k) for k in ("id", "section", "target", "title", "proposal", "answer", "state")}
                      for r in c.ledger_rows(path) if r.get("state") in ITEM_CARRY]}


resolve_pass = c.resolve_pass


def read_corpus(client):
    """Domains (inactive included), goals, projects, and tasks of every status."""
    corpus = {"domain": c.page_through(client, "domain", {"include_inactive": True})[0],
              "goal": c.page_through(client, "goal")[0], "project": c.page_through(client, "project")[0],
              "task": c.page_through(client, "task")[0]}
    seen = {str(t.get("id")) for t in corpus["task"]}
    for status in ("DONE", "CANCELLED"):
        for row in c.page_through(client, "task", {"status": status})[0]:
            if str(row.get("id")) not in seen:
                seen.add(str(row.get("id")))
                corpus["task"].append(row)
    return corpus


def pack_pass(client, run, home, month, today, time_home, rules, cadence_override, config=None, server=None):
    corpus = read_corpus(client)
    folder = run / "inputs"
    folder.mkdir(parents=True, exist_ok=True)
    built = c.stack_check(folder / "stack-full.json", today.isoformat(), config=config, server=server)
    (folder / "stack-full.json").unlink()
    time = read_time(time_home, month)
    derived = derive(corpus, month, time, today, c.maybe_json(home / c.GOAL_MAP) or {},
                     starved_hours=c.rule_number(rules, "starved hours", STARVED_HOURS),
                     unserved_hours=c.rule_number(rules, "unserved hours", UNSERVED_HOURS),
                     stop_days=int(c.rule_number(rules, "stop days", STOP_DAYS)))
    cadence = c.resolve_cadence(month, rules, cadence_override)
    if time.get("present"):
        time["below_minimum"] = time["coverage"] < c.rule_number(rules, "minimum coverage", 0.0)
    inputs = {"stack": stack_part(built), **derived, "time": time, "cadence": cadence, "carried": carried(home, month)}
    for name, value in inputs.items():
        c.write_json(folder / f"{name}.json", value)
    g, p, d = derived["goals"], derived["projects"], derived["domains"]
    time_text = (f"{time['work_hours']:.1f} work hours over {time['days_covered']}/{month['days']} days"
                 if time.get("present") else f"no time study ({time.get('reason')})")
    return c.safe(
        f"PACK: {month['month']} ({cadence['cadence']}): {g['active']} active goals ({g['no_project']} with no project, "
        f"{g['starved']} starved, {g['quiet']} quiet); {p['no_goal']} of {p['active']} projects serve no goal, "
        f"{p['stop_candidates']} stop candidates; {len(d['unserved'])} domain(s) took time with no goal; {time_text}; "
        f"pulse {', '.join(cadence['pulse_domains']) or 'none'}; {len(derived['goalmap']['unmapped'])} goals unmapped. "
        f"Inputs in {folder}")


def approve_pass(client, run, folder, month, published, form):
    review = c.read_json(folder / "review.json")
    items, problems = c.validate_review(review, month["month"])
    if problems:
        raise c.Bad(f"the published review in {folder} does not validate: {problems[0]}")
    sources = c.answer_sources(folder, form, client, published.get("task"))
    result = c.resolve(items, sources)
    result.update(schema=c.ANSWERS_SCHEMA, month=month["month"], preview=True, at=c.now_iso())
    c.write_json(run / "answers.json", result)
    if (folder / "NOTE.md").is_file():
        shutil.copyfile(folder / "NOTE.md", run / "NOTE.md")
    c.write_json(run / "review.json", review)
    return (f"APPROVE: {month['month']}: {len(items)} items; {c.answer_line(result['counts'])}; "
            f"{len(result['ops'])} ops to apply, {len(result['maps'])} mapping(s) to record; answers from "
            f"{len(sources)} source(s). Preview in {run / 'answers.json'}")


def main(argv=None, client=None):
    p = argparse.ArgumentParser(prog="goal_alignment_gather.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("month", nargs="?", default="")
    p.add_argument("--run", dest="run_dir", required=True, help="The Run folder")
    p.add_argument("--pass", dest="wanted", default="auto", help="auto, pack or approve")
    p.add_argument("--cadence", default="", help="monthly or quarterly; blank: from the rules file")
    p.add_argument("--home", default="", help="The goal-alignment home (default <state_dir>/goal-alignment)")
    p.add_argument("--answers", default="", help="The owner's answers from the launch form")
    p.add_argument("--time-home", default="", help="The time study's home (default: setting time_study_home)")
    p.add_argument("--rules", default="", help="GOAL-ALIGNMENT-RULES.md (default: setting rules_file)")
    p.add_argument("--as-of", default="", help="Judge as of this date (yyyy-mm-dd); blank: today")
    p.add_argument("--config", default="", help="MCP config holding the Portal (default: setting portal_mcp_config)")
    p.add_argument("--server", default="", help="Server name in the MCP config (default: setting portal_server)")
    args = p.parse_args(argv)
    try:
        today = date.fromisoformat(args.as_of.strip()) if args.as_of.strip() else date.today()
        mo = c.resolve_month(args.month, today)
        root = c.home_path(args.home)
        folder = c.month_dir(root, mo["month"])
        run = c.guard_run_path(args.run_dir)
        run.mkdir(parents=True, exist_ok=True)
        chosen, published = resolve_pass(args.wanted, folder)
        rules_file = None
        if chosen == "pack":
            rules_file = c.rules_path(args.rules)
            rules = c.read_settings(rules_file)
            time_home = args.time_home or str(c.settings(c.SKILL).get("time_study_home") or "")
        client = client or c.Portal(args.config or None, args.server or None)
        if chosen == "pack":
            line = pack_pass(client, run, root, mo, today, time_home, rules, args.cadence,
                             args.config or None, args.server or None)
        else:
            line = approve_pass(client, run, folder, mo, published, args.answers)
        c.write_json(run / "pass.json", {"schema": c.PASS_SCHEMA, "month": mo, "pass": chosen, "home": str(root),
                                         "month_dir": str(folder), "published": published, "rules": rules_file,
                                         "as_of": today.isoformat(), "at": c.now_iso()})
    except (c.Bad, ValueError) as exc:
        print(c.safe(f"ERROR {exc}"), file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # a Portal that cannot be read: no note without facts
        print(c.safe(f"ERROR the Portal could not be read ({type(exc).__name__}: {exc})"), file=sys.stderr)
        sys.exit(2)
    print(line)
    sys.exit(0)


if __name__ == "__main__":
    main()
