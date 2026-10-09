#!/usr/bin/env python3
"""weekly-review-gather: read the week's facts before the session, and pick the pass.

WEEK is 2030-W10, a date in the week, or blank for the week of the latest Friday. The pass is
pack (prepare the review), approve (read the owner's answers) or auto: approve once the week's
pack is published (publish.json in the week's folder), pack until then. Read only toward the
Portal; writes the Run folder only.

The pack pass writes RUN/inputs/:
  stack.json     the trust score from task-stack-workstream's task_stack_check.py, compared with
                 last week's saved one (else the newest earlier one in the home, else --baseline)
  projects.json  every active project with its next action (the open TODO or IN_PROGRESS task
                 due first, then by priority) or its gap (no open task, only WAITING tasks)
  waiting.json   the owner's WAITING tasks by follow-up date: overdue, due by next Sunday, later, none
  tasks.json     the owner's overdue and stale tasks, the someday/maybe candidates (no goal,
                 long overdue or long untouched), and the queue worth their answer (--queue)
  calendar.json  next week's meetings from calendar-steward-method's calendar_time.py, with overlaps
  said.json      the time study's said-but-not-seen items of this week (--said-dir)
  cadence.json   whether this is the month's last review (the monthly pulse) and a quarter's
  carried.json   last week's items left unsettled, so they come back rather than rot
The approve pass reads the published review and every answer (the review task's comments,
ANSWERS.md, --answers) and writes RUN/answers.json, a preview of what will be applied. Both
write RUN/pass.json. The first line printed reaches the session.

Settings: portal_mcp_config (and portal_server); state_dir, or --home (the home is
<state_dir>/weekly-review). Exit 0 when it ran; 2 on a bad argument, an unreadable input, or a
Portal that cannot be read in the pack pass (a pack without facts is not a pack).

Example:
  python3 weekly_review_gather.py --run RUN --said-dir TIME_STUDY/out
"""

import argparse
import json
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import _common as c

QUEUE, STALE_DAYS = 30, 30
SOMEDAY_OVERDUE_DAYS, SOMEDAY_STALE_DAYS = 30, 60
PRIORITY = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}
CALENDAR_TIME = c.SKILLS_HOME / "calendar-steward-method" / "scripts" / "calendar_time.py"
CARRY_STATES = ("unanswered", "modified", "unclear", "unavailable", "partial", "refused", "deferred")


def due_of(task):
    for key in ("due_date", "deadline"):
        if c.day(task.get(key)):
            return c.day(task.get(key))
    return None


def prio(task):
    return PRIORITY.get(str(task.get("priority") or "").upper(), 5)


def ref(kind, item):
    return f"portal://{kind}/{item.get('id')}"


def derive(corpus, owner, today, week, stale_days=STALE_DAYS, queue=QUEUE):
    """projects, waiting and tasks, from one read of the stack. No I/O."""
    domains = {str(d.get("id")): d for d in corpus.get("domain", [])}
    projects = {str(p.get("id")): p for p in corpus.get("project", [])}
    tasks = [t for t in corpus.get("task", []) if c.is_open_task(t)]

    def dname(item, is_project=False):
        did = str(item.get("domain_id") or "") if is_project else c.task_domain(item, projects)
        return str((domains.get(did or "") or {}).get("name") or "") or None

    def mine(task):
        who = str(task.get("owner_contact_id") or "").lower()
        return not who or owner is None or who == owner

    by_project = {}
    for t in tasks:
        if t.get("project_id"):
            by_project.setdefault(str(t["project_id"]), []).append(t)
    rows = []
    for pid, p in projects.items():
        if not c.is_active_project(p):
            continue
        open_ = by_project.get(pid, [])
        actionable = sorted((t for t in open_ if c.status_of(t) in ("TODO", "IN_PROGRESS")),
                            key=lambda t: (due_of(t) or date.max, prio(t), str(t.get("created_at") or "")))
        nxt = actionable[0] if actionable else None
        rows.append({"ref": ref("project", p), "name": str(p.get("name") or ""), "domain": dname(p, True),
                     "goal": bool(p.get("goal_id")), "status": p.get("status"), "health": p.get("health_status"),
                     "open_tasks": len(open_),
                     "next_action": ({"ref": ref("task", nxt), "title": nxt.get("title"),
                                      "due": str(due_of(nxt) or "") or None, "owner": nxt.get("owner_name")}
                                     if nxt else None),
                     "gap": None if nxt else ("only WAITING tasks" if open_ else "no open task")})
    rows.sort(key=lambda r: (r["gap"] is None, (r["domain"] or "").lower(), r["name"].lower()))
    projects_out = {"active": len(rows), "with_next_action": sum(1 for r in rows if r["next_action"]),
                    "gaps": sum(1 for r in rows if r["gap"]), "no_goal": sum(1 for r in rows if not r["goal"]),
                    "projects": rows}

    next_sunday = date.fromisoformat(week["next_sunday"])
    waiting = []
    for t in tasks:
        if c.status_of(t) != "WAITING" or not mine(t):
            continue
        follow = due_of(t) or c.day(t.get("start_date"))
        bucket = ("no_follow_up" if follow is None else "follow_up_overdue" if follow < today
                  else "follow_up_due" if follow <= next_sunday else "later")
        waiting.append({"ref": ref("task", t), "title": t.get("title"), "follow_up": str(follow or "") or None,
                        "bucket": bucket, "waiting_on": t.get("waiting_on_name") or t.get("task_contact_name"),
                        "project": t.get("project_name"), "domain": dname(t), "priority": t.get("priority"),
                        "updated_at": t.get("updated_at")})
    order = {"follow_up_overdue": 0, "follow_up_due": 1, "no_follow_up": 2, "later": 3}
    waiting.sort(key=lambda w: (order[w["bucket"]], w["follow_up"] or "9999"))
    wcounts = {"waiting": len(waiting), **{b: sum(1 for w in waiting if w["bucket"] == b) for b in order}}

    flagged = []
    for t in tasks:
        if not mine(t) or c.status_of(t) == "WAITING":
            continue
        due = due_of(t)
        updated = c.day(t.get("updated_at")) or c.day(t.get("created_at"))
        days_overdue = (today - due).days if due and due < today else 0
        days_stale = (today - updated).days if updated else None
        stale = days_stale is not None and days_stale > stale_days
        if not days_overdue and not stale:
            continue
        p = projects.get(str(t.get("project_id") or "")) or {}
        linked = bool(t.get("goal_id") or p.get("goal_id"))
        someday = (not linked and prio(t) >= 3 and not str(t.get("title") or "").startswith(c.SOMEDAY.strip())
                   and (days_overdue > SOMEDAY_OVERDUE_DAYS or (not due and (days_stale or 0) > SOMEDAY_STALE_DAYS)))
        flagged.append({"ref": ref("task", t), "title": t.get("title"), "status": c.status_of(t),
                        "priority": t.get("priority"), "due": str(due or "") or None, "days_overdue": days_overdue,
                        "updated_at": t.get("updated_at"), "days_stale": days_stale, "stale": stale,
                        "overdue": bool(days_overdue), "project": t.get("project_name"), "domain": dname(t),
                        "goal_linked": linked, "source": t.get("source"), "someday_candidate": someday,
                        "queued": False})
    overdue = sorted((f for f in flagged if f["overdue"] and not f["someday_candidate"]),
                     key=lambda f: (prio(f), -f["days_overdue"]))
    someday = sorted((f for f in flagged if f["someday_candidate"]),
                     key=lambda f: -max(f["days_overdue"], f["days_stale"] or 0))
    stale_only = sorted((f for f in flagged if f["stale"] and not f["overdue"] and not f["someday_candidate"]),
                        key=lambda f: (prio(f), -(f["days_stale"] or 0)))
    picked = []
    for pool, share in ((overdue, queue // 2), (someday, queue // 3), (stale_only, queue)):
        for f in pool[:share]:
            if len(picked) >= queue:
                break
            f["queued"] = True
            picked.append(f)
    tasks_out = {"counts": {"overdue": sum(1 for f in flagged if f["overdue"]),
                            "stale": sum(1 for f in flagged if f["stale"]),
                            "someday_candidates": len(someday), "queued": len(picked)},
                 "queue": [f["ref"] for f in picked], "tasks": flagged}
    return {"projects": projects_out, "waiting": {"counts": wcounts, "tasks": waiting}, "tasks": tasks_out}


def conflicts(items):
    """Every overlap between two of the meetings, in minutes."""
    out = []
    spans = sorted(((datetime.fromisoformat(i["start_local"]), datetime.fromisoformat(i["end_local"]), n)
                    for n, i in enumerate(items) if i.get("start_local") and i.get("end_local")),
                   key=lambda s: (s[0], s[1]))
    for k, (s1, e1, a) in enumerate(spans):
        for s2, e2, b in spans[k + 1:]:
            if s2 >= e1:
                break
            minutes = int((min(e1, e2) - s2).total_seconds() // 60)
            if minutes > 0:
                out.append({"day": items[a]["day"], "a": items[a]["title"], "b": items[b]["title"],
                            "minutes": minutes, "a_ref": items[a].get("_ref"), "b_ref": items[b].get("_ref"),
                            "start": s2.isoformat(timespec="minutes")})
    return out


def calendar(week, config=None, server=None):
    """Next week's meetings from calendar_time.py --json, with every overlap; or why not."""
    since = week["next_monday"]
    until = (date.fromisoformat(since) + timedelta(days=7)).isoformat()
    cmd = [sys.executable, str(CALENDAR_TIME), "--since", since, "--until", until, "--json"]
    cmd += (["--config", config] if config else []) + (["--server", server] if server else [])
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if done.returncode != 0:
            raise RuntimeError((done.stderr or done.stdout or "no output").strip().splitlines()[0])
        res = json.loads(done.stdout)
    except Exception as exc:  # a calendar that cannot be read is said, not hidden
        return {"error": c.safe(f"{type(exc).__name__}: {exc}")}
    items = res["in_scope"]["items"]
    return {"period": res["period"], "meetings": res["in_scope"]["meetings"], "totals": res["totals"],
            "by_day": res["in_scope"]["by_day"], "conflicts": conflicts(items), "warnings": res.get("warnings") or [],
            "items": [{k: i.get(k) for k in ("day", "start_local", "end_local", "hours", "title", "attendee_count",
                                             "_ref")} for i in items]}


def said(said_dir, week):
    """The open said-but-not-seen items dated in this week, from every list whose window covers it."""
    if not (said_dir or "").strip():
        return {"present": False, "windows": [], "items": [], "reason": "no said-not-seen folder given"}
    folder = Path(said_dir).expanduser()
    monday, sunday = week["monday"], week["sunday"]
    windows, items = [], []
    for path in sorted(folder.glob("said-not-seen-*.json")):
        try:
            data = c.read_json(path)
        except c.Bad:
            continue
        if not isinstance(data, dict) or not str(data.get("schema") or "").startswith("time-study/said-not-seen"):
            continue
        since, until = str(data.get("since") or ""), str(data.get("until") or "")
        if not since or not until or until < monday or since > sunday:
            continue
        windows.append(str(data.get("window")))
        for it in data.get("items") or []:
            if it.get("status", "open") == "open" and monday <= str(it.get("date") or "") <= sunday:
                items.append({k: it.get(k) for k in ("id", "date", "time", "quote", "commitment", "to", "by",
                                                     "domain", "why_not_seen", "text")})
    return {"present": bool(windows), "windows": windows, "items": items,
            "reason": None if windows else f"no said-not-seen list in {folder} covers {week['week']}"}


def carried(home, week):
    """Last week's items still unanswered, answered with more than a verb, or not fully applied."""
    path = c.week_dir(home, week["previous"]) / c.items_ledger_name(week["previous"])
    if not path.is_file():
        return {"week": week["previous"], "present": False, "items": []}
    return {"week": week["previous"], "present": True,
            "items": [{k: r.get(k) for k in ("id", "section", "task", "title", "proposal", "answer", "state")}
                      for r in c.ledger_rows(path) if r.get("state") in CARRY_STATES]}


def cadence(week):
    friday = date.fromisoformat(week["friday"])
    last = (friday + timedelta(days=7)).month != friday.month
    return {"friday": week["friday"], "monthly_pulse_due": last,
            "quarter_end": last and friday.month in (3, 6, 9, 12), "month": friday.strftime("%Y-%m")}


def baseline_for(home, week, fallback):
    """Last week's saved score, else the newest earlier one in the home, else the fallback file."""
    candidates = [c.week_dir(home, week["previous"]) / "inputs" / "stack.json"]
    candidates += sorted((p for p in Path(home).glob("[0-9][0-9][0-9][0-9]/*-W[0-9][0-9]/inputs/stack.json")
                          if p.parent.parent.name < week["week"]), key=lambda p: p.parent.parent.name, reverse=True)
    if (fallback or "").strip():
        candidates.append(Path(fallback).expanduser())
    for path in candidates:
        try:
            data = c.read_json(path) if path.is_file() else None
        except c.Bad:
            continue
        if isinstance(data, dict) and data.get("tool") == "task-stack-check":
            return path
    return None


resolve_pass = c.resolve_pass


def read_corpus(client):
    """Domains (inactive included), projects and the open tasks."""
    return {"domain": c.page_through(client, "domain", {"include_inactive": True})[0],
            "project": c.page_through(client, "project")[0], "task": c.page_through(client, "task")[0]}


def pack_pass(client, run, home, week, today, said_dir, fallback, stale_days, queue, config=None, server=None):
    owner = c.owner_contact(client)
    corpus = read_corpus(client)
    folder = run / "inputs"
    folder.mkdir(parents=True, exist_ok=True)
    before = baseline_for(home, week, fallback)
    stack = c.stack_check(folder / "stack.json", today.isoformat(), stale_days, before, config, server)
    derived = derive(corpus, owner, today, week, stale_days, queue)
    inputs = {**derived, "calendar": calendar(week, config, server), "said": said(said_dir, week),
              "cadence": cadence(week), "carried": carried(home, week)}
    for name, value in inputs.items():
        c.write_json(folder / f"{name}.json", value)
    o, b = stack["overall"], stack.get("baseline") or {}
    delta = b.get("score_delta")
    since = (f" ({delta:+.1f} since {b.get('as_of')})" if isinstance(delta, (int, float))
             else " (no earlier score)" if before is None else "")
    t, w, cal, s = derived["tasks"]["counts"], derived["waiting"]["counts"], inputs["calendar"], inputs["said"]
    cal_text = (f"next week {cal.get('meetings')} meetings, {len(cal.get('conflicts') or [])} conflicts"
                if not cal.get("error") else "calendar unreadable")
    return c.safe(
        f"PACK: {week['week']}: trust score {o['score']}{since}; {derived['projects']['gaps']} of "
        f"{derived['projects']['active']} projects lack a next action; {t['overdue']} overdue, {t['stale']} stale, "
        f"{t['someday_candidates']} someday candidates, {t['queued']} queued; {w['waiting']} WAITING "
        f"({w['follow_up_overdue']} follow-ups overdue, {w['follow_up_due']} due); {cal_text}; said-not-seen "
        f"{len(s['items']) if s['present'] else 'none'}. Inputs in {folder}")


def approve_pass(client, run, folder, week, published, form):
    review = c.read_json(folder / "review.json")
    items, problems = c.validate_review(review, week["week"])
    if problems:
        raise c.Bad(f"the published review in {folder} does not validate: {problems[0]}")
    sources = c.answer_sources(folder, form, client, published.get("task"))
    result = c.resolve(items, sources)
    result.update(schema=c.ANSWERS_SCHEMA, week=week["week"], preview=True, at=c.now_iso())
    c.write_json(run / "answers.json", result)
    if (folder / "PACK.md").is_file():
        shutil.copyfile(folder / "PACK.md", run / "PACK.md")
    c.write_json(run / "review.json", review)
    return (f"APPROVE: {week['week']}: {len(items)} items; {c.answer_line(result['counts'])}; "
            f"{len(result['ops'])} ops to apply; answers from {len(sources)} source(s). Preview in "
            f"{run / 'answers.json'}")


def main(argv=None, client=None):
    p = argparse.ArgumentParser(prog="weekly_review_gather.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("week", nargs="?", default="")
    p.add_argument("--run", dest="run_dir", required=True, help="The Run folder")
    p.add_argument("--pass", dest="wanted", default="auto", help="auto, pack or approve")
    p.add_argument("--home", default="", help="The weekly-review home (default <state_dir>/weekly-review)")
    p.add_argument("--answers", default="", help="The owner's answers from the launch form")
    p.add_argument("--said-dir", default="", help="The time study's out/ folder with said-not-seen-*.json")
    p.add_argument("--baseline", default="", help="A task_stack_check.py json to compare with when no earlier week has one")
    p.add_argument("--as-of", default="", help="Judge as of this date (yyyy-mm-dd); blank: today")
    p.add_argument("--stale-days", type=int, default=STALE_DAYS)
    p.add_argument("--queue", type=int, default=QUEUE)
    p.add_argument("--config", default="", help="MCP config holding the Portal (default: setting portal_mcp_config)")
    p.add_argument("--server", default="", help="Server name in the MCP config (default: setting portal_server)")
    args = p.parse_args(argv)
    try:
        if not 1 <= args.stale_days <= 3650:
            raise c.Bad("--stale-days is 1 to 3650")
        if not 1 <= args.queue <= c.MAX_ITEMS:
            raise c.Bad(f"--queue is 1 to {c.MAX_ITEMS}")
        today = date.fromisoformat(args.as_of.strip()) if args.as_of.strip() else date.today()
        wk = c.resolve_week(args.week, today)
        root = c.home_path(args.home)
        folder = c.week_dir(root, wk["week"])
        run = c.guard_run_path(args.run_dir)
        run.mkdir(parents=True, exist_ok=True)
        chosen, published = resolve_pass(args.wanted, folder)
        client = client or c.Portal(args.config or None, args.server or None)
        if chosen == "pack":
            line = pack_pass(client, run, root, wk, today, args.said_dir, args.baseline, args.stale_days, args.queue,
                             args.config or None, args.server or None)
        else:
            line = approve_pass(client, run, folder, wk, published, args.answers)
        c.write_json(run / "pass.json", {"schema": c.PASS_SCHEMA, "week": wk, "pass": chosen, "home": str(root),
                                         "week_dir": str(folder), "published": published,
                                         "as_of": today.isoformat(), "at": c.now_iso()})
    except (c.Bad, ValueError) as exc:
        print(c.safe(f"ERROR {exc}"), file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # a Portal that cannot be read: no pack without facts
        print(c.safe(f"ERROR the Portal could not be read ({type(exc).__name__}: {exc})"), file=sys.stderr)
        sys.exit(2)
    print(line)
    sys.exit(0)


if __name__ == "__main__":
    main()
