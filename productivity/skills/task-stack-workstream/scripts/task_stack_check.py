#!/usr/bin/env python3
"""task-stack-check: the trust score of the owner's task stack in the Insights Portal.

Reads every domain, goal, project and task (open, DONE and CANCELLED) and judges nine
components, each a pool of items and the ones flagged in it:

  filing       0.20  open tasks with no project, or a project in no domain
  next_action  0.10  open tasks whose title does not start with a verb
  overdue      0.15  open tasks past their due date (or deadline)
  stale        0.10  open tasks not updated for --stale-days (30)
  no_due_date  0.05  open tasks with no date in a project that has one
  waiting      0.10  WAITING tasks with no follow-up date or no named party
  duplicates   0.10  open tasks that repeat an older open task in the same project or contact
  projects     0.15  active projects with no open task, no goal, no owner, or stale
  goals        0.05  active goals with no active project under them or a sub-goal

score = 100 * sum(weight * clean share) / sum(weight), over components whose pool is not
empty; `points_lost` per component adds up to 100 - score. The same score is given per
domain. A bulk edit (an `updated_at` minute shared by 5 projects or 10 tasks) is not activity.
A WAITING task's follow-up date is its due date, deadline or start date; its named party is
waiting_on_contact_id, waiting_on_name or assignees.

Inputs: the Portal (setting portal_mcp_config); setting [task-stack-workstream] lead_words
for words the owner puts before a verb. Read only.

Output: text (top issues first), or --format json (with owner_contact_id from whoami);
--out also writes the json to a new file; --precheck prints one line, WORK: or NOTHING:;
--baseline compares with an earlier json. Exit 0 when it ran, 2 for a bad argument. When the
Portal cannot be read the first line is STALE: and the exit is still 0.

Example:
  python3 task_stack_check.py --format json --out RUN/before.json
"""

import argparse
import json
import sys
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path

import _common as c

VERSION = 1
WEIGHTS, COMPONENTS, compare = c.WEIGHTS, c.COMPONENTS, c.compare
LABELS = {
    "filing": "open tasks with no project, or a project in no domain",
    "next_action": "open tasks whose title is not a next action (no leading verb)",
    "overdue": "open tasks past their due date",
    "stale": "open tasks not updated within the stale window",
    "no_due_date": "open tasks with no due date in a project that has a deadline",
    "waiting": "WAITING tasks with no follow-up date or no named party",
    "duplicates": "likely duplicates of an older open task",
    "projects": "active projects with no open task, no goal, no owner, or stale",
    "goals": "active goals with no active project",
}
STALE_DAYS, DUP_THRESHOLD = 30, 0.85
OPEN_TASK_STATUSES = ("TODO", "IN_PROGRESS", "WAITING")
NO_DOMAIN = "(no domain)"


def day(value):
    when = c.parse_time(value)
    return when.date() if when else None


def due_of(item):
    for key in c.DUE_KEYS:
        if day(item.get(key)):
            return day(item.get(key))
    return None


def ref(kind, item):
    return f"portal://{kind}/{item.get('id')}"


# --------------------------------------------------------------------------- reading

def read_stack(client):
    """Domains (inactive included: they still own tasks), goals, projects, and tasks of every
    status: the open listing, then one listing per closed status."""
    corpus, unreadable = {}, {}
    for kind in ("domain", "goal", "project", "task"):
        rows, skipped = c.page_through(client, kind, {"include_inactive": True} if kind == "domain" else None)
        corpus[kind] = rows
        if skipped:
            unreadable[kind] = skipped
    seen = {str(t.get("id")) for t in corpus["task"]}
    for status in ("DONE", "CANCELLED"):
        rows, skipped = c.page_through(client, "task", {"status": status})
        for row in rows:
            if str(row.get("id")) not in seen:
                seen.add(str(row.get("id")))
                corpus["task"].append(row)
        if skipped:
            unreadable[f"task:{status}"] = skipped
    return corpus, unreadable


# --------------------------------------------------------------------------- judging

def task_domain(task, projects):
    """A task's domain is its project's domain, else its own domain_id."""
    project = projects.get(str(task.get("project_id") or ""))
    if project and project.get("domain_id"):
        return str(project["domain_id"])
    return str(task["domain_id"]) if task.get("domain_id") else None


def find_duplicates(tasks, threshold):
    """{task id: (older task id, similarity)} for each duplicate. Compared only within one
    project or one task contact; clusters keep their oldest task clean."""
    groups = {}
    for t in tasks:
        if t.get("project_id"):
            groups.setdefault(("project", str(t["project_id"])), []).append(t)
        if t.get("task_contact_id"):
            groups.setdefault(("contact", str(t["task_contact_id"])), []).append(t)
    parent, best = {}, {}
    norm = {str(t.get("id")): c.normalise_title(t.get("title") or "") for t in tasks}

    def root(x):
        while parent.get(x, x) != x:
            x = parent[x]
        return x

    for members in groups.values():
        for i, a in enumerate(members):
            na = norm[str(a.get("id"))]
            for b in members[i + 1:]:
                nb = norm[str(b.get("id"))]
                if not na or not nb or SequenceMatcher(None, na, nb).real_quick_ratio() < threshold:
                    continue
                score = c.similarity(na, nb)
                if score >= threshold:
                    ia, ib = str(a.get("id")), str(b.get("id"))
                    parent.setdefault(ia, ia)
                    parent.setdefault(ib, ib)
                    parent[root(ia)] = root(ib)
                    best[ia] = max(best.get(ia, 0.0), score)
                    best[ib] = max(best.get(ib, 0.0), score)
    by_id = {str(t.get("id")): t for t in tasks}
    clusters = {}
    for tid in parent:
        clusters.setdefault(root(tid), []).append(by_id[tid])
    out = {}
    for members in clusters.values():
        members.sort(key=lambda t: (str(t.get("created_at") or ""), str(t.get("id"))))
        for dup in members[1:]:
            out[str(dup.get("id"))] = (str(members[0].get("id")), round(best.get(str(dup.get("id")), 0.0), 3))
    return out


def judge(corpus, today, stale_days=STALE_DAYS, dup_threshold=DUP_THRESHOLD):
    """Every judgment, per component: one row per pooled item, flagged or clean."""
    rows = {k: [] for k in COMPONENTS}

    def add(component, ref, domain_id, project_id, flagged, title="", reason="", **extra):
        rows[component].append({"ref": ref, "domain_id": domain_id, "project_id": project_id,
                                "flagged": flagged, "title": title, "reason": reason, **extra})

    projects = {str(p.get("id")): p for p in corpus.get("project", [])}
    goals = {str(g.get("id")): g for g in corpus.get("goal", [])}
    tasks = corpus.get("task", [])
    open_tasks = [t for t in tasks if c.is_open_task(t)]
    by_project = {}
    for t in tasks:
        if t.get("project_id"):
            by_project.setdefault(str(t["project_id"]), []).append(t)
    duplicates = find_duplicates(open_tasks, dup_threshold)
    skip = c.lead_words()

    for t in open_tasks:
        pid = str(t.get("project_id") or "") or None
        project = projects.get(pid or "")
        title = str(t.get("title") or "")
        row = dict(ref=ref("task", t), domain_id=task_domain(t, projects), project_id=pid, title=title)
        if not pid:
            add("filing", flagged=True, reason="no project", **row)
        elif project is not None and not project.get("domain_id"):
            add("filing", flagged=True, reason="project in no domain", **row)
        else:
            add("filing", flagged=False, **row)
        ok = c.is_next_action(title, skip)
        add("next_action", flagged=not ok,
            reason="" if ok else f"starts with {c.first_word(title, skip)!r}, not a verb", **row)
        due = due_of(t)
        late = due is not None and due < today
        add("overdue", flagged=late, reason=f"due {due.isoformat()}, {(today - due).days} days ago" if late else "",
            due=due.isoformat() if due else None, **row)
        touched = day(t.get("updated_at")) or day(t.get("created_at"))
        idle = (today - touched).days if touched else None
        old = idle is None or idle > stale_days
        add("stale", flagged=old,
            reason=(f"no update for {idle} days" if idle is not None else "never dated") if old else "", **row)
        if project is not None and due_of(project) is not None:
            add("no_due_date", flagged=due is None,
                reason=f"project due {due_of(project).isoformat()}" if due is None else "", **row)
        if c.status_of(t) == "WAITING":
            follow = due or day(t.get("start_date"))
            party = bool(t.get("waiting_on_contact_id") or str(t.get("waiting_on_name") or "").strip()
                         or t.get("assignees"))
            missing = [m for m, have in (("no follow-up date", follow), ("no named party", party)) if not have]
            add("waiting", flagged=bool(missing), reason="; ".join(missing),
                no_follow_up=follow is None, no_party=not party, **row)
        dup = duplicates.get(str(t.get("id")))
        add("duplicates", flagged=dup is not None,
            reason=f"duplicate of portal://task/{dup[0]} (similarity {dup[1]})" if dup else "",
            duplicate_of=f"portal://task/{dup[0]}" if dup else None, **row)

    active = [p for p in projects.values() if c.is_active_project(p)]
    bulk = c.bulk_minutes(projects.values(), tasks)
    for p in active:
        pid = str(p.get("id"))
        mine = by_project.get(pid, [])
        open_mine = [t for t in mine if c.is_open_task(t)]
        reasons = []
        if not open_mine:
            reasons.append("no open task")
        if not p.get("goal_id"):
            reasons.append("no goal")
        if not c.owner_of(p, open_mine)[0]:
            reasons.append("no owner")
        when, _ = c.last_activity(p, mine, bulk)
        latest = when.date() if when else None
        if latest is None or (today - latest).days > stale_days:
            reasons.append(f"no activity for {(today - latest).days} days" if latest else "never dated")
        add("projects", ref=ref("project", p), domain_id=str(p.get("domain_id") or "") or None, project_id=pid,
            flagged=bool(reasons), title=str(p.get("name") or ""), reason="; ".join(reasons),
            no_next_action="no open task" in reasons, no_goal="no goal" in reasons,
            no_owner="no owner" in reasons, stale=any(r.startswith(("no activity", "never dated")) for r in reasons))

    # A goal is served when it or any descendant goal has an active project.
    served = {str(p.get("goal_id")) for p in active if p.get("goal_id")}
    changed = True
    while changed:
        changed = False
        for g in goals.values():
            gid, parent = str(g.get("id")), str(g.get("parent_goal_id") or "")
            if gid in served and parent and parent not in served:
                served.add(parent)
                changed = True
    for g in goals.values():
        if c.is_active_goal(g):
            ok = str(g.get("id")) in served
            add("goals", ref=ref("goal", g), domain_id=str(g.get("domain_id") or "") or None, project_id=None,
                flagged=not ok, title=str(g.get("title") or g.get("name") or ""),
                reason="" if ok else "no active project")
    return rows


# --------------------------------------------------------------------------- scoring

def score_components(rows):
    comps, total = {}, 0.0
    wsum = sum(WEIGHTS[k] for k, r in rows.items() if r)
    for k in COMPONENTS:
        pool = len(rows.get(k, []))
        flagged = sum(1 for r in rows.get(k, []) if r["flagged"])
        entry = {"weight": WEIGHTS[k], "pool": pool, "flagged": flagged, "clean_share": None, "points_lost": 0.0}
        if pool:
            share = 1 - flagged / pool
            entry["clean_share"] = round(share, 4)
            entry["points_lost"] = round(100 * WEIGHTS[k] * (flagged / pool) / wsum, 2)
            total += WEIGHTS[k] * share
        if k == "waiting":
            entry["no_follow_up"] = sum(1 for r in rows[k] if r.get("no_follow_up"))
            entry["no_party"] = sum(1 for r in rows[k] if r.get("no_party"))
        if k == "projects":
            for flag in ("no_next_action", "no_goal", "no_owner", "stale"):
                entry[flag] = sum(1 for r in rows[k] if r.get(flag))
        comps[k] = entry
    return (round(100 * total / wsum, 1) if wsum else None), comps


def status_counts(items):
    out = {}
    for item in items:
        key = c.status_of(item) or "UNKNOWN"
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def top_components(comps, n=3):
    return sorted((k for k in COMPONENTS if comps[k]["flagged"]), key=lambda k: (-comps[k]["points_lost"], k))[:n]


def build(corpus, today, domain="", project="", stale_days=STALE_DAYS, dup_threshold=DUP_THRESHOLD,
          evidence=False):
    """The full result: overall score, per-domain scores, every flagged item."""
    domains = {str(d.get("id")): d for d in corpus.get("domain", [])}
    projects = {str(p.get("id")): p for p in corpus.get("project", [])}
    scope_domains = scope_projects = None
    if domain:
        want = domain.strip().lower()
        scope_domains = {i for i, d in domains.items() if i == domain.strip() or want in str(d.get("name") or "").lower()}
        if not scope_domains:
            raise c.Stop(f"no domain matches --domain {domain!r}")
    if project:
        want = project.strip().lower()
        scope_projects = {i for i, p in projects.items()
                          if (i == project.strip() or want in str(p.get("name") or "").lower())
                          and (scope_domains is None or str(p.get("domain_id") or "") in scope_domains)}
        if not scope_projects:
            raise c.Stop(f"no project matches --project {project!r}")

    def in_scope(row):
        return ((scope_domains is None or row["domain_id"] in scope_domains)
                and (scope_projects is None or row["project_id"] in scope_projects))

    judged = judge(corpus, today, stale_days, dup_threshold)
    rows = {k: [r for r in judged[k] if in_scope(r)] for k in COMPONENTS}

    def dom_name(did):
        if did is None:
            return NO_DOMAIN
        return str(domains[did].get("name") or did) if did in domains else f"(unknown domain {did[:8]})"

    def task_row(t):
        return {"domain_id": task_domain(t, projects), "project_id": str(t.get("project_id") or "") or None}

    tasks_in = [t for t in corpus.get("task", []) if in_scope(task_row(t))]
    projects_in = [p for p in projects.values()
                   if in_scope({"domain_id": str(p.get("domain_id") or "") or None, "project_id": str(p.get("id"))})]
    goals_in = [g for g in corpus.get("goal", []) if scope_projects is None
                and in_scope({"domain_id": str(g.get("domain_id") or "") or None, "project_id": None})]
    score, comps = score_components(rows)
    overall = {"score": score, "components": comps, "top_components": top_components(comps),
               "counts_by_status": {"task": status_counts(tasks_in), "project": status_counts(projects_in),
                                    "goal": status_counts(goals_in)},
               "items_flagged": len({r["ref"] for k in COMPONENTS for r in rows[k] if r["flagged"]})}

    per_domain = []
    for did in sorted({r["domain_id"] for k in COMPONENTS for r in rows[k]}, key=lambda d: dom_name(d).lower()):
        sub = {k: [r for r in rows[k] if r["domain_id"] == did] for k in COMPONENTS}
        dscore, dcomps = score_components(sub)
        per_domain.append({
            "id": did, "name": dom_name(did), "score": dscore,
            "flagged": {k: dcomps[k]["flagged"] for k in COMPONENTS},
            "pool": {k: dcomps[k]["pool"] for k in COMPONENTS},
            "top_components": top_components(dcomps),
            "items_flagged": len({r["ref"] for k in COMPONENTS for r in sub[k] if r["flagged"]}),
            "counts_by_status": {"task": status_counts(t for t in tasks_in if task_row(t)["domain_id"] == did)}})
    per_domain.sort(key=lambda d: (d["score"] if d["score"] is not None else 101, d["name"].lower()))

    # What a consumer needs to order and route a task without reading it again.
    meta = {ref("task", t): {"status": c.status_of(t) or None, "priority": t.get("priority"),
                             "created_at": t.get("created_at"), "updated_at": t.get("updated_at"),
                             "due": due_of(t).isoformat() if due_of(t) else None,
                             "owner_contact_id": t.get("owner_contact_id"), "domain_id": task_domain(t, projects),
                             "project_id": str(t.get("project_id") or "") or None}
            for t in corpus.get("task", []) if c.is_open_task(t)}
    findings = {}
    for k in COMPONENTS:
        ordered = sorted(rows[k], key=lambda r: r.get("due") or "") if k == "overdue" else rows[k]
        found = []
        for r in ordered:
            if not r["flagged"]:
                continue
            is_project = r["ref"].startswith("portal://project/")
            item = {"ref": r["ref"], "title": r["title"], "domain": dom_name(r["domain_id"]),
                    "project": None if is_project or r["project_id"] not in projects
                    else str(projects[r["project_id"]].get("name") or ""),
                    "reason": r["reason"]}
            if r.get("duplicate_of"):
                item["duplicate_of"] = r["duplicate_of"]
            item.update({key: v for key, v in meta.get(r["ref"], {}).items() if key not in item})
            found.append(item)
        findings[k] = found

    open_in = [t for t in tasks_in if c.is_open_task(t)]
    linked = sum(1 for t in open_in if t.get("email_id"))
    return {
        "tool": "task-stack-check", "version": VERSION, "as_of": today.isoformat(),
        "scope": {"domain": domain or None, "project": project or None},
        "params": {"stale_days": stale_days, "dup_threshold": dup_threshold},
        "weights": dict(WEIGHTS), "reads": {k: len(v) for k, v in corpus.items()},
        "overall": overall, "domains": per_domain, "findings": findings,
        "evidence": {"included": False, "requested": evidence, "open_tasks_with_linked_email": linked,
                     "reason": (f"not part of the score: the task listing does not surface completion evidence "
                                f"cheaply. {linked} of {len(open_in)} open tasks carry a linked email (email_id) "
                                "and meeting notes are not linked from the listing, so the check would cost a "
                                "search per task. The nightly reconciliation matches sent mail and meeting "
                                "notes with a model.")},
    }


# --------------------------------------------------------------------------- output

def parse_components(value):
    """--components as a list, or None for every component (a blank value means every one)."""
    names = [n.strip() for n in str(value or "").replace(" ", ",").split(",") if n.strip()]
    if not names:
        return None
    unknown = [n for n in names if n not in COMPONENTS]
    if unknown:
        raise c.Stop(f"unknown component {', '.join(unknown)} (known: {', '.join(COMPONENTS)})")
    return list(dict.fromkeys(names))


def precheck_line(result, components=None):
    """WORK: or NOTHING:. With components, only those count."""
    overall = result["overall"]
    comps = overall["components"]
    if components:
        n = len({f["ref"] for k in components for f in result["findings"].get(k) or []})
        ranked = sorted((k for k in components if comps[k]["flagged"]), key=lambda k: (-comps[k]["points_lost"], k))
        what = f" in {', '.join(components)}"
    else:
        n, ranked, what = overall["items_flagged"], overall["top_components"], ""
    if not n:
        return f"NOTHING: task stack clean{what}, trust score {overall['score']}"
    tops = ", ".join(f"{k} {comps[k]['flagged']}" for k in ranked[:3])
    return f"WORK: {n} items need attention ({tops}); trust score {overall['score']}"


def fmt(value):
    return "-" if value is None else f"{value:.1f}"


def as_text(result, sample=5):
    overall = result["overall"]
    counts = overall["counts_by_status"]["task"]
    scope = ", ".join(f"{k} {v!r}" for k, v in result["scope"].items() if v) or "all domains"
    lines = [f"Task stack trust score {fmt(overall['score'])} / 100 ({scope}, as of {result['as_of']})",
             f"{sum(counts.get(s, 0) for s in OPEN_TASK_STATUSES)} open tasks, {overall['items_flagged']} items "
             f"need attention. Stale after {result['params']['stale_days']} days; duplicate threshold "
             f"{result['params']['dup_threshold']}.", "", "Top issues"]
    comps = overall["components"]
    ranked = sorted((k for k in COMPONENTS if comps[k]["flagged"]), key=lambda k: -comps[k]["points_lost"])
    if not ranked:
        lines.append("  none")
    for i, k in enumerate(ranked, 1):
        e = comps[k]
        lines.append(f"{i}. {k}: {e['flagged']} of {e['pool']} {LABELS[k]} (-{e['points_lost']:.1f} points)")
        for f in result["findings"][k][:sample]:
            where = f" [{f['project']}]" if f.get("project") else f" [{f['domain']}]"
            lines.append(f"   {f['ref']}  {f['title'][:70]}{where}  {f['reason']}")
        if len(result["findings"][k]) > sample:
            lines.append(f"   ... and {len(result['findings'][k]) - sample} more (json lists every item)")
    lines += ["", "By domain (lowest first)", f"  {'score':>5}  {'open':>5}  {'flagged':>7}  domain  (top components)"]
    for d in result["domains"]:
        dopen = sum(d["counts_by_status"]["task"].get(s, 0) for s in OPEN_TASK_STATUSES)
        lines.append(f"  {fmt(d['score']):>5}  {dopen:>5}  {d['items_flagged']:>7}  {d['name']}"
                     f"  ({', '.join(d['top_components']) or 'clean'})")
    lines += ["", "Status counts"]
    for kind in ("task", "project", "goal"):
        cnt = overall["counts_by_status"][kind]
        lines.append(f"  {kind}: " + (", ".join(f"{k} {v}" for k, v in cnt.items()) or "none"))
    b = result.get("baseline")
    if b:
        lines += ["", f"Since {b.get('as_of')}: score {fmt(b['score_before'])} -> {fmt(b['score_after'])}"
                  + (f" ({b['score_delta']:+.1f})" if b["score_delta"] is not None else "")]
        for k, e in b["components"].items():
            lines.append(f"  {k}: {e['flagged_before']} -> {e['flagged_after']} flagged, {e['direction']} "
                         f"(+{e['new_items']} new, -{e['resolved_items']} resolved)")
    lines += ["", "Evidence of done: " + result["evidence"]["reason"]]
    return "\n".join(lines)


def owner_contact(client):
    """The token's own contact from whoami, or None when it cannot be read."""
    try:
        who = client.call("whoami", {})
    except Exception:
        return None
    principal = (who or {}).get("principal") if isinstance(who, dict) else None
    return str((principal or {}).get("contact_id") or "").strip() or None


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="task_stack_check.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--domain", default="", help="Only this domain (name contains this text, or its id)")
    p.add_argument("--project", default="", help="Only this project (name contains this text, or its id)")
    p.add_argument("--format", dest="fmt", choices=["text", "json"], default="text")
    p.add_argument("--precheck", action="store_true", help="One line, WORK: or NOTHING:, exit 0")
    p.add_argument("--components", default="", help="With --precheck, only these components count (comma list)")
    p.add_argument("--baseline", default="", help="An earlier --format json output to compare with")
    p.add_argument("--out", default="", help="Also write the json to this new file (never overwritten)")
    p.add_argument("--evidence", action="store_true", help="Ask for evidence of done (reported, not scored)")
    p.add_argument("--stale-days", type=int, default=STALE_DAYS)
    p.add_argument("--dup-threshold", type=float, default=DUP_THRESHOLD)
    p.add_argument("--as-of", default="", help="Judge against this date (YYYY-MM-DD) instead of today")
    p.add_argument("--config", default="", help="MCP config holding the Portal (default: setting portal_mcp_config)")
    p.add_argument("--server", default="", help="Server name in the MCP config (default: setting portal_server)")
    return p.parse_args(argv)


def bad(message):
    print(c.safe(f"ERROR {message}"), file=sys.stderr)
    sys.exit(2)


def main(argv=None, client=None):
    args = parse_args(argv)
    if not 1 <= args.stale_days <= 3650:
        bad("--stale-days is 1 to 3650")
    if not 0.5 <= args.dup_threshold <= 1.0:
        bad("--dup-threshold is 0.5 to 1.0")
    today = date.today()
    if args.as_of.strip():
        try:
            today = date.fromisoformat(args.as_of.strip())
        except ValueError:
            bad(f"--as-of wants YYYY-MM-DD, got {args.as_of!r}")
    try:
        only = parse_components(args.components)
    except c.Stop as exc:
        bad(exc)
    before = None
    if args.baseline:
        try:
            before = json.loads(Path(args.baseline).expanduser().read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            bad(f"--baseline {args.baseline!r} is not a readable json file ({type(exc).__name__})")
        if not isinstance(before, dict) or before.get("tool") != "task-stack-check":
            bad(f"--baseline {args.baseline!r} is not a task-stack-check json output")
    out_path = Path(args.out).expanduser() if args.out else None
    if out_path is not None and out_path.exists():
        bad(f"--out {args.out!r} exists; this command never overwrites a file")
    try:
        client = client or c.Portal(args.config or None, args.server or None)
        corpus, unreadable = read_stack(client)
    except Exception as exc:  # any failure to read is a stale score, not a crash
        print(c.safe(f"STALE: the Portal could not be read ({type(exc).__name__}: {exc}); no score computed"))
        sys.exit(0)
    try:
        result = build(corpus, today, args.domain, args.project, args.stale_days, args.dup_threshold, args.evidence)
    except c.Stop as exc:
        bad(exc)
    result["owner_contact_id"] = owner_contact(client)
    result["generated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    result["portal_calls"] = getattr(client, "calls", None)
    if unreadable:
        result["unreadable_rows"] = unreadable
    if before is not None:
        result["baseline"] = dict(compare(result, before), file=str(args.baseline))
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("x", encoding="utf-8") as fh:
            fh.write(json.dumps(result, indent=1, ensure_ascii=False, default=str) + "\n")
    if args.precheck:
        print(c.safe(precheck_line(result, only)))
    elif args.fmt == "json":
        print(c.safe(json.dumps(result, indent=1, ensure_ascii=False, default=str)))
    else:
        if unreadable:
            print(c.safe(f"warning: rows the Portal would not serialise were skipped: {unreadable}"))
        print(c.safe(as_text(result)))
    sys.exit(0)


if __name__ == "__main__":
    main()
