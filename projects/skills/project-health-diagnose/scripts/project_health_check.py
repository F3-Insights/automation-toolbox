#!/usr/bin/env python3
"""The state of every active Insights Portal project, and the weekly pass's worklist.

An active project (not archived, not closed, not a domain's catch-all) should have a goal,
a next action (an open TODO or IN_PROGRESS task, or a WAITING one with a due date), an owner
(the project's assignee or an open task's owner) and activity within --stale-days. Its state
is the first that holds: dead (idle --dead-days and no goal), stalled (idle --stale-days),
gaps (missing a goal, next action or owner), healthy. A dead project with no open task is
close_eligible. Activity is the latest timestamp on the project or its tasks, except that an
updated_at minute shared by 5 or more projects or 10 or more tasks is a bulk edit, not work.

The worklist is at most --max projects: stalled first, then dead with open tasks, then gaps;
within each, priority, then mechanical score, then longest idle. Projects idle --dead-days or
more that are not close-eligible are close_candidates, one closing question each. A catch-all
project ("General Tasks", is_general) is a bucket: never scored; up to --drain of its open
tasks owned by the owner or nobody, in domains with a real project, are the drain batch.

Inputs: the owner setting `portal_mcp_config` (optionally `portal_server`); for --last-run,
`runs_dir` in the [project-health-diagnose] table. Reads domains, goals, projects and tasks
of every status, plus whoami for the owner's contact. Read only.

Prints text, json (--format json), or one WORK:/NOTHING: line (--precheck). --out also
writes the json to a new file, never overwriting. --baseline compares with an earlier json.
When the Portal cannot be read the first line is "STALE: ..." and the exit is 0. Exit 2 for a
bad argument or a missing setting.

Example:
  python3 project_health_check.py --format json --out RUN/health.json
"""

import argparse
import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

from _common import (DUE_KEYS, ACTIVITY_KEYS, PortalError, SettingMissing, connect, is_active_project,
                     is_open_task, owner_of, page_through, parse_time, safe, score_project, settings)

TOOL, VERSION = "project-health-check", 1
MAX_DEFAULT, DRAIN_DEFAULT, STALE_DEFAULT, DEAD_DEFAULT = 15, 25, 30, 90
BULK_PROJECTS, BULK_TASKS = 5, 10
STATES = ("dead", "stalled", "gaps", "healthy")
GAPS = ("no_goal", "no_next_action", "no_owner", "stale")
STATE_ORDER = {"stalled": 0, "dead": 1, "gaps": 2, "healthy": 3}


class BadArgument(Exception):
    pass


# --------------------------------------------------------------------------- reading

def read_stack(client):
    """Domains (inactive too, since they still own tasks), goals, projects, and tasks of every
    status: the open listing plus the DONE and CANCELLED ones, de-duplicated by id."""
    corpus, unreadable = {}, {}
    for kind in ("domain", "goal", "project", "task"):
        filters = {"include_inactive": True} if kind == "domain" else None
        corpus[kind], skipped = page_through(client, kind, filters=filters)
        if skipped:
            unreadable[kind] = skipped
    seen = {str(t.get("id")) for t in corpus["task"]}
    for status in ("DONE", "CANCELLED"):
        rows, skipped = page_through(client, "task", filters={"status": status})
        for row in rows:
            if str(row.get("id")) not in seen:
                seen.add(str(row.get("id")))
                corpus["task"].append(row)
        if skipped:
            unreadable[f"task:{status}"] = skipped
    return corpus, unreadable


def owner_contact(client):
    """The token's own contact id from whoami, or None."""
    try:
        who = client.call("whoami", {})
    except Exception:
        return None
    principal = who.get("principal") if isinstance(who, dict) else None
    return str((principal or {}).get("contact_id") or "").strip() or None


# --------------------------------------------------------------------------- judging one project

def minute(value):
    when = parse_time(value)
    return when.strftime("%Y-%m-%dT%H:%M") if when else None


def bulk_minutes(projects, tasks):
    """updated_at minutes shared by so many records that they are bulk edits."""
    out = set()
    for rows, floor in ((projects, BULK_PROJECTS), (tasks, BULK_TASKS)):
        counts = Counter(m for m in (minute(r.get("updated_at")) for r in rows) if m)
        out |= {m for m, n in counts.items() if n >= floor}
    return out


def last_activity(project, tasks, bulk):
    latest, basis = None, ""
    for item, kind in [(project, "project"), *((t, "task") for t in tasks)]:
        for key in ACTIVITY_KEYS:
            if key == "updated_at" and minute(item.get(key)) in bulk:
                continue
            when = parse_time(item.get(key))
            if when is not None and (latest is None or when > latest):
                latest, basis = when, f"{kind}.{key}"
    return latest, basis


def status(t):
    return str(t.get("status") or "").strip().upper()


def next_actions(open_tasks):
    """TODO or IN_PROGRESS, or WAITING with a due date; soonest due, then priority, then oldest."""
    picked = [t for t in open_tasks if status(t) in ("TODO", "IN_PROGRESS")
              or (status(t) == "WAITING" and any(t.get(k) for k in DUE_KEYS))]
    return sorted(picked, key=lambda t: (next((str(t.get(k))[:10] for k in DUE_KEYS if t.get(k)), "9999-99-99"),
                                         str(t.get("priority") or "P9"), str(t.get("created_at") or "")))


def judge(project, tasks, today, bulk, stale_days, dead_days):
    open_tasks = [t for t in tasks if is_open_task(t)]
    actions = next_actions(open_tasks)
    owned, basis = owner_of(project, open_tasks)
    latest, where = last_activity(project, tasks, bulk)
    idle = (today - latest.date()).days if latest else None
    gaps = [g for g, missing in (("no_goal", not project.get("goal_id")), ("no_next_action", not actions),
                                 ("no_owner", not owned), ("stale", idle is None or idle > stale_days)) if missing]
    if (idle is None or idle >= dead_days) and not project.get("goal_id"):
        state = "dead"
    elif "stale" in gaps:
        state = "stalled"
    else:
        state = "gaps" if gaps else "healthy"
    return {"state": state, "gaps": gaps, "idle_days": idle,
            "last_activity": latest.date().isoformat() if latest else None, "activity_basis": where or None,
            "open_tasks": len(open_tasks), "waiting_tasks": sum(status(t) == "WAITING" for t in open_tasks),
            "next_actions": [f"portal://task/{t.get('id')}" for t in actions[:3]],
            "owner_basis": basis or None, "close_eligible": state == "dead" and not open_tasks}


def priority(value):
    text = str(value or "").strip().upper().lstrip("P")
    return int(text) if text.isdigit() else 9


# --------------------------------------------------------------------------- the whole result

def build(corpus, today, domain="", owner=None, max_projects=MAX_DEFAULT, drain=DRAIN_DEFAULT,
          stale_days=STALE_DEFAULT, dead_days=DEAD_DEFAULT):
    """The result from the listings. No I/O and no clock, so it can be tested."""
    domains = {str(d.get("id")): d for d in corpus.get("domain", [])}
    goals = {str(g.get("id")): str(g.get("title") or g.get("name") or "") for g in corpus.get("goal", [])}
    projects, tasks = corpus.get("project", []), corpus.get("task", [])
    scope = None
    if domain.strip():
        want = domain.strip().lower()
        scope = {i for i, d in domains.items() if i.lower() == want or want in str(d.get("name") or "").lower()}
        if not scope:
            raise BadArgument(f"no domain matches --domain {domain!r}")

    def dname(did):
        d = domains.get(str(did or ""))
        return str(d.get("name") or did) if d else "(no domain)"

    by_project = {}
    for t in tasks:
        if t.get("project_id"):
            by_project.setdefault(str(t["project_id"]), []).append(t)
    bulk = bulk_minutes(projects, tasks)
    now = datetime(today.year, today.month, today.day, 12, tzinfo=timezone.utc)
    names = {i: str(d.get("name") or "") for i, d in domains.items()}

    rows, buckets, real_domains = [], [], set()
    for p in projects:
        pid, did = str(p.get("id")), str(p.get("domain_id") or "")
        if scope is not None and did not in scope:
            continue
        mine = by_project.get(pid, [])
        if p.get("is_general"):
            if p.get("is_archived"):
                continue
            open_ = [t for t in mine if is_open_task(t)]
            latest, _ = last_activity(p, mine, bulk)
            buckets.append({"ref": f"portal://project/{pid}", "id": pid, "name": str(p.get("name") or ""),
                            "domain_id": did or None, "domain": dname(did), "open_tasks": len(open_),
                            "oldest_open": min((str(t.get("created_at") or "") for t in open_), default="")[:10] or None,
                            "last_activity": latest.date().isoformat() if latest else None})
            continue
        if not is_active_project(p):
            continue
        real_domains.add(did)
        score = score_project(p, mine, names, goals, now)
        gid = str(p.get("goal_id") or "") or None
        rows.append({"ref": f"portal://project/{pid}", "id": pid, "name": str(p.get("name") or ""),
                     "domain_id": did or None, "domain": dname(did), "status": p.get("status"),
                     "priority": p.get("priority"), "goal_id": gid, "goal": goals.get(gid or "") or None,
                     "assignee_contact_id": p.get("assignee_contact_id"),
                     **judge(p, mine, today, bulk, stale_days, dead_days),
                     "overdue_tasks": score["mechanical"]["load"]["overdue_tasks"],
                     "mechanical_score": score["mechanical_score"], "flags": score["flags"]})

    never = 10 ** 6
    rows.sort(key=lambda r: (STATE_ORDER[r["state"]], priority(r["priority"]), -r["mechanical_score"],
                             -(r["idle_days"] if r["idle_days"] is not None else never), r["name"].lower(), r["id"]))
    long_idle = [r for r in rows if not r["close_eligible"] and (r["idle_days"] is None or r["idle_days"] >= dead_days)]
    candidates = {r["ref"] for r in long_idle}
    needs = [r for r in rows if r["state"] != "healthy" and not r["close_eligible"] and r["ref"] not in candidates]
    worklist = needs[:max_projects] if max_projects > 0 else needs
    close_eligible = [r["ref"] for r in rows if r["close_eligible"]]
    long_idle.sort(key=lambda r: (-(r["idle_days"] if r["idle_days"] is not None else never), r["name"].lower()))

    owner_l = str(owner or "").lower()
    drainable = []
    for b in buckets:
        if b["domain_id"] not in real_domains:
            continue  # nowhere to move them to
        for t in by_project.get(b["id"], []):
            who = str(t.get("owner_contact_id") or "").lower()
            if not is_open_task(t) or (owner_l and who and who != owner_l):
                continue
            drainable.append({"ref": f"portal://task/{t.get('id')}", "title": str(t.get("title") or ""),
                              "status": status(t), "priority": t.get("priority"),
                              "created_at": t.get("created_at"), "updated_at": t.get("updated_at"),
                              "due": next((str(t.get(k))[:10] for k in DUE_KEYS if t.get(k)), None),
                              "owner_contact_id": t.get("owner_contact_id"), "domain_id": b["domain_id"],
                              "domain": b["domain"], "bucket": b["ref"]})
    drainable.sort(key=lambda t: (priority(t["priority"]), str(t["created_at"] or ""), t["ref"]))
    buckets.sort(key=lambda b: (-b["open_tasks"], b["domain"].lower()))

    counts = {s: sum(r["state"] == s for r in rows) for s in STATES}
    unhealthy = len(rows) - counts["healthy"]
    per_domain = {}
    for r in rows:
        d = per_domain.setdefault(r["domain"], {"domain": r["domain"], "domain_id": r["domain_id"], "active": 0,
                                                **{s: 0 for s in STATES}})
        d["active"] += 1
        d[r["state"]] += 1
    return {
        "tool": TOOL, "version": VERSION, "as_of": today.isoformat(), "scope": {"domain": domain or None},
        "params": {"max": max_projects, "drain": drain, "stale_days": stale_days, "dead_days": dead_days},
        "owner_contact_id": owner,
        "summary": {"active": len(rows), **counts, "unhealthy": unhealthy, "close_eligible": len(close_eligible),
                    "close_candidates": len(long_idle), "gap_counts": {g: sum(g in r["gaps"] for r in rows) for g in GAPS},
                    "buckets": len(buckets), "bucket_open_tasks": sum(b["open_tasks"] for b in buckets),
                    "drainable": len(drainable), "bulk_minutes": sorted(bulk)},
        "tests": {"coverage": {"state": "pending", "text": "the session decides each worklist project"},
                  "gaps": {"state": "pass" if not unhealthy else "fail", "unhealthy": unhealthy},
                  "no_worse": {"state": "n/a", "text": "needs --baseline"}},
        "worklist": [r["ref"] for r in worklist],
        "deferred": max(0, len(needs) - len(worklist)),
        "close_eligible": close_eligible,
        "close_candidates": [r["ref"] for r in long_idle],
        "drain": drainable[:drain] if drain > 0 else [],
        "buckets": buckets,
        "domains": sorted(per_domain.values(), key=lambda d: (-(d["active"] - d["healthy"]), d["domain"].lower())),
        "projects": rows,
    }


def compare(result, before):
    """What changed since an earlier json output."""
    then = {r["ref"]: r for r in before.get("projects") or []}
    now = {r["ref"]: r for r in result["projects"]}
    resolved = sorted(ref for ref, r in then.items() if r.get("state") != "healthy"
                      and (ref not in now or now[ref]["state"] == "healthy"))
    worse = sorted(ref for ref, r in now.items() if r["state"] != "healthy"
                   and (ref not in then or then[ref].get("state") == "healthy"))
    b, a = before.get("summary") or {}, result["summary"]
    keys = ("active", "unhealthy", *STATES, "close_eligible", "bucket_open_tasks")
    return {"as_of": before.get("as_of"), "counts": {k: [b.get(k), a.get(k)] for k in keys},
            "resolved": resolved, "newly_unhealthy": worse,
            "worklist_now_healthy": sorted(ref for ref in before.get("worklist") or []
                                           if ref in now and now[ref]["state"] == "healthy"),
            "no_worse": isinstance(b.get("unhealthy"), int) and a["unhealthy"] <= b["unhealthy"]}


def precheck_line(result):
    s = result["summary"]
    tail = f"; buckets hold {s['bucket_open_tasks']} open tasks"
    base = result.get("baseline")
    if base:
        u = base["counts"]["unhealthy"]
        tail += f"; since {base['as_of']}: unhealthy {u[0]} -> {u[1]}, {len(base['resolved'])} resolved"
    if not s["unhealthy"]:
        return f"NOTHING: all {s['active']} active projects healthy{tail}"
    return (f"WORK: {s['unhealthy']} of {s['active']} active projects need attention (stalled {s['stalled']}, "
            f"dead {s['dead']}, gaps {s['gaps']}; {s['close_eligible']} close eligible, "
            f"{s['close_candidates']} to propose closing){tail}")


def as_text(result):
    s, dead = result["summary"], result["params"]["dead_days"]
    by_ref = {r["ref"]: r for r in result["projects"]}
    lines = [precheck_line(result), "", "Gaps: " + ", ".join(f"{k} {v}" for k, v in s["gap_counts"].items()),
             f"Bulk-edit minutes skipped as activity: {len(s['bulk_minutes'])} (json lists them)", "",
             f"Worklist ({len(result['worklist'])}, {result['deferred']} deferred)"]
    for i, ref in enumerate(result["worklist"], 1):
        r = by_ref[ref]
        idle = r["idle_days"] if r["idle_days"] is not None else "?"
        lines.append(f"{i:>3}. {r['state']:<7} {r['name'][:40]:<40} [{r['domain'][:20]}] idle {idle}d  {' '.join(r['gaps'])}")
    lines += ["", f"Close eligible ({len(result['close_eligible'])}): no goal, no open task, no activity for {dead} days"]
    lines += [f"     {by_ref[ref]['name'][:50]} [{by_ref[ref]['domain'][:20]}]" for ref in result["close_eligible"]]
    lines += ["", f"Close candidates ({len(result['close_candidates'])}): idle {dead}+ days, a closing question each"]
    for ref in result["close_candidates"]:
        r = by_ref[ref]
        lines.append(f"     {r['name'][:46]:<46} [{r['domain'][:20]}] idle {r['idle_days']}d, {r['open_tasks']} open, "
                     f"goal {'yes' if r['goal_id'] else 'no'}")
    lines += ["", "Buckets (catch-all projects; not scored)"]
    lines += [f"  {b['open_tasks']:>4} open  {b['domain']}  (oldest {b['oldest_open'] or '-'})" for b in result["buckets"]]
    return "\n".join(lines)


def last_run(runs_dir):
    """The newest project-health-* Run folder under runs_dir and the files it holds."""
    root = Path(str(runs_dir)).expanduser()
    runs = sorted((d for d in root.glob("project-health-*") if d.is_dir()), key=lambda d: d.name, reverse=True)
    if not runs:
        return {"run": None, "reason": f"no project-health Run under {root}"}
    files = {n: str(runs[0] / n) for n in ("diagnoses.json", "health.json", "health-after.json",
                                          "changes.json", "REPORT.md") if (runs[0] / n).is_file()}
    return {"run": str(runs[0]), "files": files}


def whole_number(name, value, default):
    """An empty value (a blank launch-form field arrives as --max=) means the default."""
    text = str(value or "").strip()
    if not text:
        return default
    if not text.isdigit():
        raise BadArgument(f"{name} wants a whole number, got {value!r}")
    return int(text)


def main(argv=None, client=None):
    ap = argparse.ArgumentParser(description="Every active Portal project's state, and the weekly worklist. Read only.")
    ap.add_argument("--domain", default="", help="only this domain (name contains this text, or its id)")
    ap.add_argument("--max", default=str(MAX_DEFAULT), help="the most projects in the worklist (0: all)")
    ap.add_argument("--drain", default=str(DRAIN_DEFAULT), help="the most bucket tasks in the drain batch")
    ap.add_argument("--stale-days", type=int, default=STALE_DEFAULT)
    ap.add_argument("--dead-days", type=int, default=DEAD_DEFAULT)
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--precheck", action="store_true", help="one line, WORK: or NOTHING:, for a scheduler")
    ap.add_argument("--baseline", default="", help="an earlier --format json output to compare with")
    ap.add_argument("--out", default="", help="also write the json to this new file (never overwritten)")
    ap.add_argument("--as-of", default="", help="judge against this date (YYYY-MM-DD) instead of today")
    ap.add_argument("--last-run", action="store_true", help="print the newest project-health Run folder; no Portal read")
    ap.add_argument("--config", default="", help="MCP config file (default: the portal_mcp_config setting)")
    ap.add_argument("--server", default="", help="server name in the MCP config")
    args = ap.parse_args(argv)

    def bad(message):
        print(safe(f"ERROR {message}"), file=sys.stderr)
        return 2

    if args.last_run:
        runs_dir = settings("project-health-diagnose").get("runs_dir")
        if not runs_dir:
            return bad("set runs_dir in the [project-health-diagnose] table of the owner settings")
        print(safe(json.dumps(last_run(runs_dir), indent=1)))
        return 0
    try:
        cap, drain = whole_number("--max", args.max, MAX_DEFAULT), whole_number("--drain", args.drain, DRAIN_DEFAULT)
        if not (1 <= args.stale_days <= 3650 and 1 <= args.dead_days <= 3650):
            raise BadArgument("--stale-days and --dead-days must be between 1 and 3650")
        today = date.fromisoformat(args.as_of.strip()) if args.as_of.strip() else date.today()
    except (BadArgument, ValueError) as exc:
        return bad(exc)
    before = None
    if args.baseline:
        try:
            before = json.loads(Path(args.baseline).expanduser().read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return bad(f"--baseline {args.baseline!r} is not a readable json file ({type(exc).__name__})")
        if not isinstance(before, dict) or before.get("tool") != TOOL:
            return bad(f"--baseline {args.baseline!r} is not a {TOOL} json output")
    out_path = Path(args.out).expanduser() if args.out else None
    if out_path is not None and out_path.exists():
        return bad(f"--out {args.out!r} exists; this command never overwrites a file")
    try:
        client = client or connect(args.config or None, args.server or None)
    except SettingMissing as exc:
        return bad(exc)
    except PortalError as exc:  # an unusable config entry or URL is a Portal that cannot be read
        print(safe(f"STALE: the Portal could not be read ({exc}); nothing judged"))
        return 0
    try:
        corpus, unreadable = read_stack(client)
        owner = owner_contact(client)
    except Exception as exc:  # a Portal that cannot be read is a stale result, not a crash
        print(safe(f"STALE: the Portal could not be read ({type(exc).__name__}: {exc}); nothing judged"))
        return 0
    try:
        result = build(corpus, today, domain=args.domain, owner=owner, max_projects=cap, drain=drain,
                       stale_days=args.stale_days, dead_days=args.dead_days)
    except BadArgument as exc:
        return bad(exc)
    result["generated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    result["portal_calls"] = getattr(client, "calls", None)
    if unreadable:
        result["unreadable_rows"] = unreadable
    if before is not None:
        result["baseline"] = dict(compare(result, before), file=str(args.baseline))
        result["tests"]["no_worse"] = {"state": "pass" if result["baseline"]["no_worse"] else "fail",
                                       "unhealthy": result["baseline"]["counts"]["unhealthy"]}
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("x", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1, ensure_ascii=False, default=str)
            fh.write("\n")
    if args.precheck:
        print(safe(precheck_line(result)))
    elif args.format == "json":
        print(safe(json.dumps(result, indent=1, ensure_ascii=False, default=str)))
    else:
        print(safe(as_text(result)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
