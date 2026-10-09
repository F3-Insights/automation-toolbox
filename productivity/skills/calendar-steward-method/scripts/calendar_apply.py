#!/usr/bin/env python3
"""calendar-apply: the calendar steward's one writer. It publishes the day's approval list,
makes exactly the changes the owner approved, and undoes them.

    calendar_apply.py publish --run RUN [--home H] [--pass P] [--dry-run-if true] --project UUID
    calendar_apply.py apply   --run RUN [--home H] [--pass P] [--answers TEXT] [--dry-run-if true] --project UUID
    calendar_apply.py undo    --date yyyy-mm-dd [--item N] [--home H] [--dry-run]

The session only proposes (RUN/proposals.json, contract in _common.py). This runs after the
session and is the only way the steward changes anything.

publish: checks the proposals against RUN/scan.json (a focus block or move lands in free time,
the event is in the scan, no meeting with other attendees is moved, a decline carries its
draft), numbers them, keeps the list in <home>/<date>/ and puts it on the owner's approval
task ("Approve calendar changes for <date>", found by its marker or created once, in
--project or --domain). A list the owner has started answering is never replaced, since a new
list would renumber the items under their answers (exit 1). An unanswered list replaced the
same day moves to superseded-<stamp>/ and the new list is posted on the task as a comment. A
list with no items is kept and needs no task.

apply: for every list of the last 14 days, reads the owner's answers (comments on the approval
task, ANSWERS.md in the list's folder, then --answers for the newest list) and acts on items
answered `ok` and nothing else. Before any write it reads the calendar again: an item whose
time has passed is `expired`; a focus block or moved hold whose slot is no longer free, an
event that is gone, or a move of an event with other attendees is `refused`. The Portal offers
no calendar write, so each approved change becomes a Portal task with its date and times,
made through task-stack-apply (task-stack-workstream: markers, the owner's task rules, an undo
log), and EVENTS.md (a paste-ready list) and events.ics (the focus blocks and new times) are
written beside it. Nothing is ever deleted or sent: a decline is a draft reply on a task for
the owner to send. Each apply keeps approve-<stamp>/ (answers, change set, results, undo log,
EVENTS.md, events.ics), updates the item ledger, appends to journal.jsonl and comments the
outcomes on the approval task. undo has task-stack-apply cancel the tasks an apply made, from
its undo logs; nothing is deleted.

A dry run (--dry-run-if true) reads everything and writes nothing outside the Run folder and
nothing to the Portal: RUN/publish-dry-run.json and RUN/apply-dry-run.json say what it would do.
Prints one JSON object. Exit 0 when it ran, 1 when publish refused a list, 2 on a bad argument,
3 when a write failed.

Example:
    python3 calendar_apply.py publish --run RUN --project 3f2a6c10-0000-4000-8000-000000000001
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import _common as c

OK, REFUSE, BAD, FAILED = 0, 1, 2, 3
AGENT_SIGN = f"(posted by {c.ORCHESTRATOR}, an agent)"
TASK_STATUSES = ["TODO", "IN_PROGRESS", "WAITING", "DONE", "CANCELLED"]


class Refuse(Exception):
    """publish refused the list: exit 1."""


# --------------------------------------------------------------------------- the approval task

def find_by_marker(portal, mark, known=None):
    """The task carrying the list's marker: the one publish.json names, else a search."""
    ids = [c.task_uuid(known)] if c.task_uuid(known) else []
    found = portal.call("list_entities", {"entity_type": "task", "limit": 50,
                                          "filters": {"search": mark, "status": TASK_STATUSES}})
    for hit in (found.get("items") if isinstance(found, dict) else None) or []:
        if isinstance(hit, dict) and hit.get("id"):
            ids.append(str(hit["id"]).lower())
    for i in dict.fromkeys(ids):
        out = portal.call("get", {"entity_type": "task", "id_or_query": i, "detail": "full"})
        record = out.get("task") if isinstance(out, dict) and isinstance(out.get("task"), dict) else out
        if isinstance(record, dict) and mark in str(record.get("description") or "") and str(record.get("id")).lower() == i:
            return record
    return None


def ensure_task(portal, items, day, known, project, domain, replaced):
    mark = c.marker(day)
    found = find_by_marker(portal, mark, known)
    if found:
        if replaced:
            body = ("The steward prepared the list again; this list replaces the one above.\n\n"
                    + "\n".join(c.approval_lines(items)))[:3600] + f"\n\nMarker: {mark}\n{AGENT_SIGN}"
            portal.call("create_task_comment", {"task_id": str(found["id"]), "body": body})
        return {"ref": f"portal://task/{str(found['id']).lower()}", "outcome": "commented" if replaced else "found"}
    who = portal.call("whoami")
    owner = str(((who or {}).get("principal") or {}).get("contact_id") or "") if isinstance(who, dict) else ""
    args = {"title": f"Approve calendar changes for {day}", "description": c.task_text(items, day, mark),
            "owner_contact_id": owner or None, "due_date": day, "priority": 2, "source_reference": mark,
            "project_id": project or None, "domain_id_or_name": (domain or None) if not project else None}
    out = portal.call("create_task", {k: v for k, v in args.items() if v not in (None, "")})
    tid = (out.get("id") or (out.get("task") or {}).get("id")) if isinstance(out, dict) else None
    again = find_by_marker(portal, mark, tid)
    if not again:
        raise c.Failure("the approval task did not read back with its marker")
    return {"ref": f"portal://task/{str(again['id']).lower()}", "outcome": "created"}


def answered(folder, home, day, published, portal):
    """Why the published list is already being answered, or None."""
    if (folder / "ANSWERS.md").is_file():
        return f"{folder / 'ANSWERS.md'} exists"
    for row in c.Ledger(home).rows():
        if row.get("date") == day and row.get("state") not in ("proposed", "unanswered", ""):
            return f"item {row.get('n')} is {row.get('state')}"
    if published and published.get("task") and portal is not None and c.answer_sources(folder, portal, published["task"]):
        return "the owner has commented on the approval task"
    return None


# --------------------------------------------------------------------------- publish

def publish(run, home, pass_, dry, portal, project, domain):
    if pass_ == "approve":
        return {"status": "skipped", "reason": "the approve pass publishes no list"}
    scan = c.read_json(run / "scan.json")
    if isinstance(scan, dict) and scan.get("stale"):
        scan = None
    doc = c.read_json(run / "proposals.json")
    if doc is None:
        raise Refuse(f"{run / 'proposals.json'} does not exist; the session wrote no proposals")
    problems = c.proposals_problems(doc, scan, day=(scan or {}).get("date"))
    if problems:
        raise Refuse("the proposals are not publishable: " + "; ".join(problems[:12]))
    if doc["dry_run"] and not dry:
        raise Refuse("the proposals were written by a dry-run session; publish them with --dry-run-if true")
    day = doc["date"]
    folder = home / day
    items = c.number_items(doc)
    digest = c.items_hash(items)
    published = c.read_json(folder / "publish.json")
    result = {"date": day, "items": len(items), "hash": digest, "dry_run": dry,
              "coverage_gaps": len(c.coverage_gaps(doc, scan))}
    replaced = False
    if isinstance(published, dict):
        if published.get("hash") == digest:
            return dict(result, status="unchanged", task=published.get("task"))
        why = answered(folder, home, day, published, None if dry else portal)
        if why:
            raise Refuse(f"the list for {day} is already being answered ({why}); a new list would renumber it")
        replaced = True
    if dry:
        return dict(result, status="would_publish", replaces=replaced,
                    task_title=f"Approve calendar changes for {day}" if items else None, list=c.approval_lines(items))
    if items and not (project or domain):
        raise c.Bad("--project or --domain is required to file the approval task")
    if replaced:
        old = c.new_dir(folder, "superseded")
        for name in ("scan.json", "proposals.json", "items.json", "PROPOSALS.md", "publish.json"):
            if (folder / name).exists():
                shutil.move(str(folder / name), str(old / name))
    folder.mkdir(parents=True, exist_ok=True)
    if scan is not None:
        c.write_json(folder / "scan.json", scan)
    c.write_json(folder / "proposals.json", doc)
    c.write_json(folder / "items.json", {"date": day, "hash": digest, "items": items})
    c.write_text(folder / "PROPOSALS.md", c.render_list(doc, items, scan))
    task = ensure_task(portal, items, day, (published or {}).get("task"), project, domain, replaced) if items else None
    ledger = c.Ledger(home)
    for it in items:
        ledger.upsert(f"{day}:{it['n']}", {"date": day, "n": it["n"], "proposal": it.get("id"), "kind": it["kind"],
                                           "title": it.get("title"), "when": c.item_when(it), "event": it.get("event") or "",
                                           "answer": "", "state": "proposed", "outcome": "", "result": "",
                                           "updated_at": c.iso_now(), "by": "calendar-apply publish"})
    record = {"date": day, "task": (task or {}).get("ref"), "task_outcome": (task or {}).get("outcome"),
              "hash": digest, "items": len(items), "at": c.iso_now()}
    c.write_json(folder / "publish.json", record)
    return dict(result, status="published", task=record["task"], task_outcome=record["task_outcome"], folder=str(folder))


# --------------------------------------------------------------------------- the change tasks

def op_for(it, listed, project, domain):
    """One task-stack create op for an approved item: the change, with its date and times."""
    kind, title, when = it["kind"], c._s(it.get("title")), c.item_when(it)
    if kind == "focus-block":
        new_title = f"Book focus block {when}: {title}"
        lines = [f"Add to the calendar: {title}, {it['date']} {it['start']}-{it['end']} (busy, no attendees).",
                 "It is also in events.ics and EVENTS.md in the steward's folder for this list."]
        if it.get("for"):
            lines.append(f"For: {it['for']}")
        due = it["date"]
    elif kind == "move":
        to = it["to"]
        new_title = f"Move {title} from {when} to {c.short_day(to['date'])} {to['start']}-{to['end']}"
        lines = [f"Move the owner's own calendar entry {it.get('event')} to {to['date']} {to['start']}-{to['end']}.",
                 "It has no other attendees, so moving it notifies no one."]
        due = min(it["date"], to["date"])
    elif kind == "decline":
        new_title = f"Send the decline for {title} ({when})"
        lines = [f"Decline {it.get('event')} with this reply (a draft: nothing has been sent):", "", c._s(it.get("draft"))]
        due = it["date"]
    else:
        new_title = f"Prepare for {title} ({when})"
        lines = [f"Meeting: {it.get('event')}", f"Prepare: {c._s(it.get('prepare'))}"]
        due = str(it.get("due") or (date.fromisoformat(it["date"]) - timedelta(days=1)).isoformat())
        if due < date.today().isoformat():
            due = it["date"]
    op = {"id": f"cal-{listed}-{it['n']}", "op": "create", "project": project or None, "domain": domain or None,
          "reason": f"The owner approved item {it['n']} of the calendar list for {listed}: {c._s(it.get('why'))}",
          "title": new_title[:200], "due_date": due, "description": "\n".join(lines)}
    return {k: v for k, v in op.items() if v not in (None, "")}


def task_stack_apply(changes_path, log_path, dry):
    """Run task-stack-apply (task-stack-workstream) on one change set; its JSON result."""
    argv = ["python3", str(Path.home() / ".claude" / "skills" / "task-stack-workstream" / "scripts" / "task_stack_apply.py"),
            str(changes_path), "--log", str(log_path), "--max-changes", "100"]
    if dry:
        argv.append("--dry-run")
    done = subprocess.run(argv, capture_output=True, text=True, timeout=600, stdin=subprocess.DEVNULL)
    try:
        out = json.loads(done.stdout or "{}")
    except ValueError:
        out = {}
    if not isinstance(out, dict) or (done.returncode not in (0, 3) and not out):
        raise c.Failure(f"task-stack-apply exited {done.returncode}: {c.safe((done.stderr or done.stdout).strip()[:300])}")
    return out


def make_tasks(items, listed, project, domain, dry, folder, runner=task_stack_apply):
    """Each approved item as a task, through task-stack-apply. {n: {outcome, result, reason}}."""
    if not items:
        return {}
    ops = [op_for(it, listed, project, domain) for it in items]
    changes = {"tool": "task-stack-changes", "version": 1, "orchestrator": c.ORCHESTRATOR, "dry_run": dry,
               "ops": ops, "questions": [], "notes": [f"calendar-apply, list {listed}"]}
    with tempfile.TemporaryDirectory() as scratch:
        where = Path(scratch) if folder is None else folder
        c.write_json(where / "changes.json", changes)
        out = runner(where / "changes.json", where / "undo.jsonl", dry)
    if out.get("status") == "refused":
        return {it["n"]: {"outcome": "refused", "reason": f"{out.get('code')}: {out.get('reason')}"} for it in items}
    by_op = {op["id"]: it["n"] for op, it in zip(ops, items)}
    results = {}
    for r in out.get("results") or []:
        n = by_op.get(str(r.get("id") or r.get("op_id")))
        if n is not None:
            outcome = str(r.get("outcome") or "failed")
            results[n] = {"outcome": "failed" if outcome == "deferred" else outcome, "result": r.get("task") or "",
                          "reason": r.get("reason") or r.get("code") or ""}
    for it in items:
        results.setdefault(it["n"], {"outcome": "failed", "reason": "task-stack-apply returned no result"})
    return results


def to_utc(day, hhmm, tz):
    local = datetime.combine(date.fromisoformat(day), datetime.strptime(hhmm, "%H:%M").time(), tz)
    return local.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ics_escape(text):
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def event_files(items, listed, tz):
    """events.ics (the focus blocks, and the new time of each move) and EVENTS.md."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    vevents, lines = [], [f"# Approved calendar changes from the list of {listed}", ""]
    for it in items:
        if it["kind"] in ("focus-block", "move"):
            where = it if it["kind"] == "focus-block" else it["to"]
            vevents += ["BEGIN:VEVENT", f"UID:calendar-steward-{listed}-{it['n']}@calendar-steward", f"DTSTAMP:{stamp}",
                        f"DTSTART:{to_utc(where['date'], where['start'], tz)}",
                        f"DTEND:{to_utc(where['date'], where['end'], tz)}",
                        f"SUMMARY:{ics_escape(c._s(it.get('title')))}", f"DESCRIPTION:{ics_escape(c._s(it.get('why')))}",
                        "TRANSP:OPAQUE", "END:VEVENT"]
        lines.append(f"{it['n']}. {it['line']}")
        if it["kind"] == "decline":
            lines += ["", f"   Draft reply (not sent): {c._s(it.get('draft'))}", ""]
    ics = "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//calendar-steward//EN", "METHOD:PUBLISH"]
                      + vevents + ["END:VCALENDAR"]) + "\r\n"
    return {"events.ics": ics, "EVENTS.md": "\n".join(lines).rstrip() + "\n"}


# --------------------------------------------------------------------------- apply

def fresh_day(portal, day, tz, owner, scan):
    """The day's calendar read again, cleaned the scan's way, as a one-day scan."""
    the_day = date.fromisoformat(day)
    rows, _ = c.page_events(portal, *c.day_bounds(the_day, tz))
    hours = str(((scan or {}).get("settings") or {}).get("work_hours") or "08:00-17:30")
    work = (c.hhmm(hours[:5], "work"), c.hhmm(hours[6:11], "work"))
    return {"days": [c.day_calendar(rows, the_day, tz, owner, work, 30)]}


def precheck_item(it, portal, tz, owner, scan, now_local, cache):
    """None when the item may be made; otherwise its result (expired or refused)."""
    start = it.get("start") or "00:00"
    if (it["date"], start) <= (now_local.date().isoformat(), now_local.strftime("%H:%M")):
        return {"outcome": "expired", "reason": f"{it['date']} {start} has passed"}

    def day_of(d):
        if d not in cache:
            cache[d] = fresh_day(portal, d, tz, owner, scan)
        return cache[d]

    if it.get("event") and it["event"] not in c.scan_events(day_of(it["date"])):
        return {"outcome": "refused", "reason": f"{it['event']} is no longer on the calendar on {it['date']}"}
    if it["kind"] == "focus-block":
        hits = c.busy_overlap(day_of(it["date"]), it["date"], it["start"], it["end"])
        if hits:
            return {"outcome": "refused", "reason": f"the slot is no longer free ({'; '.join(hits[:3])})"}
    if it["kind"] == "move":
        m = c.EVENT_REF.match(str(it.get("event")))
        out = portal.call("get", {"entity_type": "calendar_event", "id_or_query": m.group(1), "detail": "summary"})
        emails = [str(a).lower() for a in out.get("attendee_emails") or []] if isinstance(out, dict) else []
        if any(e not in set(owner.get("addresses") or []) for e in emails):
            return {"outcome": "refused", "reason": "the event has other attendees; the steward never moves a meeting "
                                                    "with other people on it"}
        to = it["to"]
        hits = c.busy_overlap(day_of(to["date"]), to["date"], to["start"], to["end"], ignore=[it["event"]])
        if hits:
            return {"outcome": "refused", "reason": f"the new time is no longer free ({'; '.join(hits[:3])})"}
    return None


def summary_comment(listed, results):
    lines = [f"Calendar steward: the approved items of the list for {listed}."]
    for n in sorted(results):
        r = results[n]
        lines.append(f"{n}) {r['outcome']}" + (f": {r.get('result')}" if r.get("result") else "")
                     + (f" ({c._s(r.get('reason'))[:200]})" if r.get("reason") and r["outcome"] != "applied" else ""))
    lines.append("The Portal cannot write the calendar: each change is a task with its times, and the focus blocks are "
                 "in events.ics and EVENTS.md in the steward's folder.")
    return "\n".join(lines)[:3800] + f"\n{AGENT_SIGN}"


def apply(run, home, pass_, form, dry, portal, project, domain, now=None, runner=task_stack_apply):
    if pass_ == "propose":
        return {"status": "skipped", "reason": "the propose pass applies nothing"}
    me = portal.call("whoami")
    owner = c.owner_info(me if isinstance(me, dict) else {})
    tz = c.zone(owner.get("timezone"))
    now_local = (now or datetime.now(tz)).astimezone(tz)
    today = now_local.date()
    folders = [f for f in c.day_folders(home) if today - timedelta(days=c.LIST_DAYS) <= c.folder_day(f) <= today
               and (f / "publish.json").is_file() and (f / "items.json").is_file()]
    ledger = c.Ledger(home)
    rows = {r["id"]: r for r in ledger.rows()}
    lists_out, failed = [], False
    for idx, folder in enumerate(folders):
        listed = folder.name
        published = c.read_json(folder / "publish.json") or {}
        frozen = c.read_json(folder / "items.json") or {}
        items = {int(it["n"]): it for it in frozen.get("items") or []}
        if not items or frozen.get("hash") != published.get("hash"):
            lists_out.append({"date": listed, "status": "skipped",
                              "reason": "no items" if not items else "items.json does not match what was published"})
            continue
        sources = c.answer_sources(folder, portal, published.get("task"), form if idx == len(folders) - 1 else "")
        resolved = c.resolve_answers(list(items.values()), sources)
        scan = c.read_json(folder / "scan.json")
        results, todo, cache = {}, [], {}
        for r in resolved["items"]:
            n, row = int(r["n"]), rows.get(f"{listed}:{r['n']}") or {}
            if row.get("state") in c.FINAL:
                continue
            if r["state"] != "approved":
                if r["state"] != "unanswered" or row.get("state") not in ("proposed", ""):
                    results[n] = {"outcome": r["state"], "answer": r.get("answer"), "reason": r.get("extra") or ""}
                continue
            pre = precheck_item(items[n], portal, tz, owner, scan, now_local, cache)
            if pre:
                results[n] = dict(pre, answer=r.get("answer"))
            else:
                todo.append(dict(items[n], answer=r.get("answer")))
        if not results and not todo:
            lists_out.append({"date": listed, "status": "nothing", "counts": resolved["counts"]})
            continue
        if todo and not (project or domain):
            raise c.Bad("--project or --domain is required to apply approved items")
        work = None if dry else c.new_dir(folder, "approve")
        made = make_tasks(todo, listed, project, domain, dry, work, runner)
        for it in todo:
            results[it["n"]] = dict(made[it["n"]], answer=it.get("answer"))
        done_items = [items[n] for n, r in results.items() if r["outcome"] in ("applied", "unchanged", "would_apply")]
        files = event_files(done_items, listed, tz) if done_items else {}
        if work is not None:
            c.write_json(work / "answers.json", resolved)
            for name, text in files.items():
                c.write_text(work / name, text)
            for n, r in results.items():
                state = r["outcome"] if r["outcome"] in c.ITEM_STATES else "failed"
                ledger.upsert(f"{listed}:{n}", {"answer": r.get("answer") or "", "state": state,
                                                "outcome": c._s(r.get("reason"))[:300], "result": r.get("result") or "",
                                                "updated_at": c.iso_now(), "by": "calendar-apply portal-tasks"})
                if state in ("applied", "unchanged", "refused", "failed", "expired"):
                    c.append_jsonl(home / "journal.jsonl", {"at": c.iso_now(), "action": "apply", "list": listed, "n": n,
                                                            "kind": items[n]["kind"], "outcome": state,
                                                            "result": r.get("result"), "approve_dir": work.name,
                                                            "op": f"cal-{listed}-{n}"})
            acted = {n: r for n, r in results.items() if r["outcome"] in ("applied", "refused", "failed", "expired")}
            if acted and published.get("task"):
                portal.call("create_task_comment", {"task_id": c.task_uuid(published["task"]),
                                                    "body": summary_comment(listed, acted)})
            c.write_json(work / "apply.json", {"list": listed, "results": results, "at": c.iso_now()})
        failed = failed or any(r["outcome"] == "failed" for r in results.values())
        lists_out.append({"date": listed, "status": "would_apply" if dry else "applied", "counts": resolved["counts"],
                          "results": {str(n): r for n, r in sorted(results.items())}, "files": sorted(files),
                          "folder": str(work) if work else None})
    return {"status": "failed" if failed else ("would_apply" if dry else "applied"), "dry_run": dry,
            "backend": "portal-tasks", "lists": lists_out, "at": now_local.isoformat(timespec="seconds")}


# --------------------------------------------------------------------------- undo

def task_stack_undo(log_path, op_id, dry):
    """Run task-stack-apply --undo on one undo log; its JSON result."""
    argv = ["python3", str(Path.home() / ".claude" / "skills" / "task-stack-workstream" / "scripts" / "task_stack_apply.py"),
            "--undo", str(log_path)] + (["--op", op_id] if op_id else []) + (["--dry-run"] if dry else [])
    done = subprocess.run(argv, capture_output=True, text=True, timeout=600, stdin=subprocess.DEVNULL)
    try:
        return json.loads(done.stdout or "{}")
    except ValueError:
        raise c.Failure(f"task-stack-apply --undo exited {done.returncode}: "
                        f"{c.safe((done.stderr or done.stdout).strip()[:300])}") from None


def undo(home, day, item, dry, runner=task_stack_undo):
    """Undo the tasks an apply made for one list (or one item of it): each created task is
    cancelled by task-stack-apply, never deleted."""
    op_id = f"cal-{day}-{item}" if item is not None else None
    results, undone = [], []
    for log in sorted((home / day).glob("approve-*/undo.jsonl")):
        ops = []
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and (op_id is None or str(row.get("op_id")) == op_id):
                ops.append(str(row.get("op_id") or ""))
        if ops:
            out = runner(log, op_id, dry)
            # An undo that errored or was refused put nothing back: never record it as undone.
            if not isinstance(out, dict) or out.get("status") in ("error", "refused"):
                reason = out.get("reason") if isinstance(out, dict) else "no answer"
                raise c.Failure(f"task-stack-apply could not undo {log}: {reason}")
            results.append(out)
            undone += ops
    if not undone:
        return {"status": "nothing", "reason": f"no write of the list for {day}" + (f", item {item}" if item else "")}
    if not dry:
        ledger = c.Ledger(home)
        for op in dict.fromkeys(undone):
            n = op.rsplit("-", 1)[-1]
            ledger.upsert(f"{day}:{n}", {"state": "undone", "updated_at": c.iso_now(), "by": "calendar-apply undo"})
            c.append_jsonl(home / "journal.jsonl", {"at": c.iso_now(), "action": "undo", "list": day, "n": n})
    return {"status": "would_undo" if dry else "undone", "writes": len(undone), "results": results}


# --------------------------------------------------------------------------- the command

def main():
    parser = argparse.ArgumentParser(description="The calendar steward's one writer: publish the approval list, "
                                                 "apply what the owner approved, undo it.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, text in (("publish", "publish the day's approval list on the owner's approval task"),
                       ("apply", "make exactly the changes the owner approved")):
        p = sub.add_parser(name, help=text)
        p.add_argument("--run", required=True, help="the Run folder: scan.json and proposals.json; results land here")
        p.add_argument("--pass", dest="pass_", default="", help="auto, propose or approve")
        p.add_argument("--dry-run-if", default="", help="true: write nothing outside the Run folder")
        p.add_argument("--project", default="", help="the project the tasks go in (uuid)")
        p.add_argument("--domain", default="", help="or the domain whose catch-all project takes them")
        p.add_argument("--home", default="", help="the steward's home folder")
        if name == "apply":
            p.add_argument("--answers", default="", help="the owner's answers to the newest list (1) ok 2) no)")
    p = sub.add_parser("undo", help="cancel the tasks an apply made for one list, or one item of it")
    p.add_argument("--date", required=True, help="the list's date, yyyy-mm-dd")
    p.add_argument("--item", default="", help="only this item number")
    p.add_argument("--dry-run", action="store_true", help="say what would be put back; write nothing")
    p.add_argument("--home", default="", help="the steward's home folder")
    args = parser.parse_args()
    run, dry = None, False
    try:
        home = c.home_dir(args.home)
        if args.command == "undo":
            if not c.DAY.match(c.blank(args.date)) or (c.blank(args.item) and not c.blank(args.item).isdigit()):
                raise c.Bad("--date is yyyy-mm-dd and --item a number")
            result = undo(home, c.blank(args.date), int(args.item) if c.blank(args.item) else None, args.dry_run)
        else:
            run = c.guard_run_path(args.run)
            the_pass = c.resolve_pass(args.pass_)
            dry = c.truthy(args.dry_run_if)
            if args.command == "publish":
                portal = None if (dry or the_pass == "approve") else c.client()
                result = publish(run, home, the_pass, dry, portal, c.blank(args.project), c.blank(args.domain))
            elif the_pass == "propose":
                result = {"status": "skipped", "reason": "the propose pass applies nothing", "dry_run": dry}
            else:
                result = apply(run, home, the_pass, args.answers, dry, c.client(), c.blank(args.project),
                               c.blank(args.domain))
    except Refuse as exc:
        print(c.safe(f"REFUSED: {exc}"))
        sys.exit(REFUSE)
    except c.PortalError as exc:
        print(c.safe(f"ERROR the Portal call failed ({exc})"), file=sys.stderr)
        sys.exit(FAILED)
    except (c.Bad, c.Failure, ValueError) as exc:
        print(c.safe(f"ERROR {exc}"), file=sys.stderr)
        sys.exit(BAD)
    except Exception as exc:  # a write that failed some other way
        print(c.safe(f"ERROR the Portal write failed ({type(exc).__name__}: {exc})"), file=sys.stderr)
        sys.exit(FAILED)
    result = dict(result, tool=f"calendar-apply {args.command}")
    if run is not None:
        c.write_json(run / (f"{args.command}-dry-run.json" if dry else f"{args.command}.json"), result)
    print(c.safe(json.dumps(result, indent=1, default=str)))
    sys.exit(FAILED if result.get("status") == "failed" else OK)


if __name__ == "__main__":
    main()
