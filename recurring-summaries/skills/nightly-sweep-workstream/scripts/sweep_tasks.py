"""sweep-tasks: every open task, compact, into the date's folder for the task reconciler.

Read only toward the Portal. A worker cannot page a thousand open tasks within its turns, so the
pull is done here and the reconciler reads and greps the file instead of listing tasks. For one
date it writes one file; with --run it reads the Portal once and writes RUN/<date>/tasks.json for
every date in RUN/dates.json (overdue_days counted from each date).

The reads: every open task (the default task listing, TODO, IN_PROGRESS and WAITING, paged past
a row the server will not serialise), the domains (inactive ones too, since they still own
tasks) and projects for names, and whoami for the owner's contact. A task's domain is its
project's domain, else its own.

The file holds a header and then one task per line, so Grep finds a task by any word and Read
can take it in slices. A row leaves out empty fields. Its keys:

    id, title, status, priority, due (due date, else deadline), overdue_days (days past due on
    the swept date), project, domain, owner ("self" for the owner's own task, else that
    contact's id, with owner_name), updated (date of the last update), contact and contact_id
    (who the task is about), company_id, waiting_on, waiting_on_id, waiting_since,
    waiting_reason, email_id (the email the task came from).

Rows are ordered P1 first, then by due date (undated last), then title.

Prints one JSON object (a summary). Exit 0 (`ok`, or `empty` with no open task), 3 when one date
of a --run failed, 2 on an error.

Examples:
    python3 sweep_tasks.py 2030-03-06 --out RUN/2030-03-06/tasks.json
    python3 sweep_tasks.py --run RUN
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import _common as c

STALE_PAST_DUE = 7  # the reconciler's stale scan: open and at least this many days past due
PRIORITY_ORDER = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}


def priority_rank(value):
    text = str(value or "").strip().upper()
    if text.isdigit():
        text = f"P{text}"
    return PRIORITY_ORDER.get(text, 9)


def day_of(value):
    text = str(value or "").strip()
    return text[:10] if len(text) >= 10 and c.DATE_RE.match(text[:10]) else None


def compact(task, day, owner, projects, domains):
    """One task as the reconciler needs it, empty fields left out."""
    due = c.due_of(task)
    domain_id = c.task_domain(task, projects)
    project = projects.get(str(task.get("project_id") or ""))
    owner_id = str(task.get("owner_contact_id") or "") or None
    mine = bool(owner) and owner_id == owner
    row = {
        "id": task.get("id"), "title": task.get("title"), "status": c.status_of(task) or None,
        "priority": task.get("priority"),
        "due": due.isoformat() if due else None,
        "overdue_days": (day - due).days if due and due < day else None,
        "project": (project or {}).get("name") or task.get("project_name"),
        "domain": (domains.get(domain_id) or {}).get("name") if domain_id else None,
        "owner": "self" if mine else owner_id,
        "owner_name": None if mine else task.get("owner_name"),
        "updated": day_of(task.get("updated_at")),
        "contact": task.get("task_contact_name"), "contact_id": task.get("task_contact_id"),
        "company_id": task.get("company_id"),
        "waiting_on": task.get("waiting_on_name"), "waiting_on_id": task.get("waiting_on_contact_id"),
        "waiting_since": day_of(task.get("waiting_since")), "waiting_reason": task.get("waiting_reason"),
        "email_id": task.get("email_id"),
    }
    return {k: v for k, v in row.items() if v not in (None, "", [])}


def pull(client):
    """The Portal reads, once: (owner, open task rows, projects, domains, unreadable count)."""
    try:
        owner = c.owner_contact(client)
    except Exception:  # noqa: BLE001 - the file stands without it; the header says so
        owner = None
    domain_rows, _ = c.page_through(client, "domain", filters={"include_inactive": True})
    project_rows, _ = c.page_through(client, "project")
    task_rows, unreadable = c.page_through(client, "task")
    domains = {str(d.get("id")): d for d in domain_rows if d.get("id")}
    projects = {str(p.get("id")): p for p in project_rows if p.get("id")}
    seen, tasks = set(), []
    for task in task_rows:
        tid = str(task.get("id") or "")
        # The default listing is the open statuses; a closed row that slips in is not work.
        if not tid or tid in seen or not c.is_open_task(task):
            continue
        seen.add(tid)
        tasks.append(task)
    return owner, tasks, projects, domains, unreadable


def build(day, pulled):
    owner, tasks, projects, domains, unreadable = pulled
    when = c.parse_date(day)
    rows = sorted((compact(t, when, owner, projects, domains) for t in tasks),
                  key=lambda r: (priority_rank(r.get("priority")), r.get("due") or "9999-99-99",
                                 str(r.get("title") or "").lower()))
    by_status, by_priority = {}, {}
    for r in rows:
        by_status[r.get("status", "?")] = by_status.get(r.get("status", "?"), 0) + 1
        key = str(r.get("priority") or "none")
        by_priority[key] = by_priority.get(key, 0) + 1
    errors = [f"{unreadable} open task rows could not be read from the Portal and are not in the file"] \
        if unreadable else []
    if owner is None:
        errors.append("whoami did not answer; no task is marked owner self")
    return {"date": day,
            "pulled_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "owner_contact_id": owner,
            "counts": {"open": len(rows), "mine": sum(1 for r in rows if r.get("owner") == "self"),
                       "by_status": by_status, "by_priority": by_priority,
                       "past_due_7_or_more": sum(1 for r in rows if r.get("overdue_days", 0) >= STALE_PAST_DUE),
                       "unreadable": unreadable},
            "errors": errors, "tasks": rows}


def render(result):
    """The header as indented JSON, then one task per line: valid JSON that Grep can search."""
    head = {k: v for k, v in result.items() if k != "tasks"}
    lines = json.dumps(head, indent=1, ensure_ascii=False)[:-2].rstrip()  # drop the closing "\n}"
    rows = [json.dumps(r, ensure_ascii=False, separators=(", ", ": ")) for r in result["tasks"]]
    if not rows:
        return f'{lines},\n "tasks": []\n}}\n'
    return f'{lines},\n "tasks": [\n' + ",\n".join(rows) + "\n ]\n}\n"


def write(day, pulled, target):
    result = build(day, pulled)
    c.atomic_text(target, render(result))
    return {"status": "ok" if result["tasks"] else "empty", "date": day, "counts": result["counts"],
            "errors": result["errors"], "out": str(target), "bytes": Path(target).stat().st_size}


def main(argv=None, client=None):
    ap = argparse.ArgumentParser(description="Every open task, one compact row per line, for the task reconciler. "
                                             "Exit 0 ok or empty, 3 a --run date failed, 2 error.")
    ap.add_argument("day", nargs="?", help="the date, YYYY-MM-DD (or use --run)")
    ap.add_argument("--out", help="where to write the rows, with DAY")
    ap.add_argument("--run", help="the run folder: every date in its dates.json")
    args = ap.parse_args(argv)
    out = {}

    def body():
        if bool(args.run) == bool(args.day):
            raise c.Stop("give DAY --out PATH, or --run RUN, not both")
        if args.run:
            run = c.guard_run_path(args.run)
            rows = c.run_date_rows(run)
            pulled = pull(client or c.Portal())
            dates = []
            for row in rows:
                try:
                    dates.append(write(row["date"], pulled, c.out_path(Path(run) / row["date"] / "tasks.json")))
                except Exception as exc:  # noqa: BLE001 - one date failing is that date's result
                    dates.append({"status": "error", "date": row["date"],
                                  "reason": c.safe(f"{type(exc).__name__}: {exc}")})
            failed = any(d["status"] == "error" for d in dates)
            out.update({"status": "partial" if failed else "ok", "run": str(run), "dates": dates})
            return
        c.parse_date(args.day)
        if not args.out:
            raise c.Stop("--out is required with DAY")
        target = c.out_path(args.out)
        out.update(write(args.day, pull(client or c.Portal()), target))

    c.run_main(body, "sweep_tasks")
    c.emit(out, c.STOP if out.get("status") == "partial" else c.OK)


if __name__ == "__main__":
    main()
