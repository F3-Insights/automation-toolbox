#!/usr/bin/env python3
"""daily-plan-pull: the day's read-only Insights Portal pull for the daily plan, written before
the session so the planner starts from facts computed in code.

What it writes (--out, JSON):
  owner      contact id, timezone, the owner's own addresses and internal mail domains.
  calendar   the day's events after the clean-up below, each a meeting, a focus block (by
             title) or a hold, with local start and end, attendee count, a few names, external
             domains, the owner's response and linked prep notes; all_day; conflicts (each
             overlapping pair of meetings, or of a meeting and a hold); free (gaps of at least
             --min-focus minutes inside the working hours, focus blocks counted free);
             needs_prep (external meetings with no prep note).
  tasks      the owner's open tasks that matter today, each with its lenses (overdue,
             due_today, due_soon, waiting_due, waiting_no_date, in_progress, p1), project,
             domain and goal; goals (active, by domain); domains.
  note       whether the day's plan note exists and which passes it holds.
  evening    also done_today, sent (mail sent today), notes (created today), morning_plan
             (from --morning, else the state folder, else parsed from the note), packets (the
             day by domain, for the accomplishment gatherer) and tomorrow (the next working
             day's calendar).

The calendar clean-up: cancelled rows and rows the owner declined are dropped; rows sharing
start, end and a title with clone markers removed are one event (the copy with most
attendees kept); an availability block at exactly the time of a kept event is a clone and is
dropped; any other block is a hold, busy time. An attendee is internal when the address is
one of the owner's, or its domain is one of the owner's own (public mail providers excluded)
or an --internal-domain.

Inputs: the Portal (setting portal_mcp_config), read only. Timezone from --tz, else the
Portal's whoami, else setting [daily-plan-method] timezone. State folder for the evening's
morning plan: --state or <state_dir>/daily-plan (optional; without it the note is parsed).

The first line printed is FRESH: <counts> or STALE: <reason>; the exit is 0 either way, so a
prepare step never blocks the session. Exit 2 on a bad argument.

Example:
  python3 daily_plan_pull.py --date 2030-03-04 --pass morning --out RUN/pull.json
"""

import argparse
import json
import re
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import _common as c

PUBLIC_MAIL = frozenset({"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com",
                         "yahoo.com", "icloud.com", "me.com", "aol.com", "proton.me", "protonmail.com"})
CLONE = re.compile(r"(?i)\s*[\(\[][^\)\]]*\bclone\b[^\)\]]*[\)\]]")
CLONE_MARKER = re.compile(r"(?i)\s*[\(\[]\s*clone(?:\s*\d+)?\s*[\)\]]")
REPLY_PREFIX = re.compile(r"^\s*(re|fwd|fw|aw|antw|rv|vs)\s*(\[\d+\])?\s*:\s*", re.I)
CANCELLED = ("canceled:", "cancelled:")
FOCUS_TITLE = r"(?i)\b(deep work|focus( time| block)?)\b"
MAX_TASKS, HORIZON_DAYS, DESCRIPTION_CHARS, NAMES = 150, 7, 280, 6
LENS_ORDER = ("overdue", "due_today", "waiting_due", "p1", "in_progress", "due_soon", "waiting_no_date")


# --------------------------------------------------------------------------- small helpers

def local_hm(moment, tz):
    return moment.astimezone(tz).strftime("%H:%M") if moment else ""


def day_bounds(day, tz):
    return datetime.combine(day, time(0, 0), tz), datetime.combine(day + timedelta(days=1), time(0, 0), tz)


def iso(moment):
    return moment.astimezone(timezone.utc).isoformat()


def short(text, limit):
    value = " ".join(str(text or "").split())
    return value if len(value) <= limit else value[: limit - 1] + "…"


def domain_of(address):
    return address.rsplit("@", 1)[-1].strip().lower() if "@" in address else ""


def normalise_title(title):
    """The comparable part of an event title: clone markers, Cancelled and Re/Fw prefixes gone."""
    text = CLONE_MARKER.sub("", str(title or ""))
    for prefix in CANCELLED:
        if text.strip().lower().startswith(prefix):
            text = text.strip()[len(prefix):]
    while True:
        stripped = REPLY_PREFIX.sub("", text, count=1)
        if stripped == text:
            break
        text = stripped
    return " ".join(text.split()).casefold()


def owner_info(me, extra_internal):
    principal = me.get("principal") if isinstance(me.get("principal"), dict) else {}
    addresses = [str(i["address"]).strip().lower() for i in me.get("inboxes") or []
                 if isinstance(i, dict) and "@" in str(i.get("address") or "")]
    primary = str(principal.get("primary_email") or "").strip().lower()
    if primary and primary not in addresses:
        addresses.append(primary)
    domains = sorted({domain_of(a) for a in addresses if domain_of(a) not in PUBLIC_MAIL}
                     | {d.strip().lower() for d in extra_internal if d.strip()})
    return {"contact_id": principal.get("contact_id"), "timezone": principal.get("timezone"),
            "timezone_source": principal.get("timezone_source"), "addresses": addresses,
            "internal_domains": [d for d in domains if d]}


# --------------------------------------------------------------------------- the calendar

def page_events(client, since, until, page=50, max_calls=200):
    """Every calendar row in the window: (rows, rows it could not read). A page the server
    will not serialise is halved down to one row, and that row is stepped over."""
    filters = {"since": since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "until": until.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    items, offset, unreadable, total, calls, failure, read_any = [], 0, 0, None, 0, "", False
    while calls < max_calls:
        served, size = None, page
        while calls < max_calls:
            args = {"entity_type": "calendar_event", "filters": filters, "limit": size}
            if offset:
                args["offset"] = offset
            calls += 1
            try:
                out = client.call("list_entities", args)
            except Exception as exc:
                failure = type(exc).__name__
                if size == 1:
                    break
                size = max(1, size // 2)
                continue
            served = out if isinstance(out, dict) else None
            break
        if served is None:
            unreadable += 1
            offset += 1
            if total is None or offset >= total:
                break
            continue
        read_any = True
        rows = [r for r in served.get("items") or [] if isinstance(r, dict)]
        if isinstance(served.get("total"), int):
            total = served["total"]
        items.extend(rows)
        if not rows:
            break
        offset += len(rows)
        if (total is not None and offset >= total) or (not served.get("has_more") and size >= page):
            break
    if failure and not read_any:
        raise c.PortalError(f"could not read any calendar rows from the Portal ({failure})")
    return items, unreadable


class Row:
    """One calendar row, read without ever raising on a bad shape."""

    def __init__(self, raw):
        self.raw = raw
        self.ref = str(raw.get("_ref") or "")
        self.title = str(raw.get("title") or "").strip()
        kind = str(raw.get("event_kind") or "").strip().lower()
        self.is_meeting, self.is_availability = kind == "meeting", kind == "availability_block"
        self.all_day = bool(raw.get("is_all_day"))
        self.start, self.end = c.parse_time(raw.get("start_time")), c.parse_time(raw.get("end_time"))
        self.cancelled = self.title.lower().startswith(CANCELLED)
        self.calendar_name = str(raw.get("calendar_name") or "")
        self.people = [a for a in raw.get("attendees") or [] if isinstance(a, dict)]
        self.attendees = []
        for entry in raw.get("attendees") or []:
            address = entry if isinstance(entry, str) else next(
                (str(entry[k]) for k in ("email", "address", "email_address", "value")
                 if isinstance(entry, dict) and str(entry.get(k) or "").strip()), "")
            address = address.strip().strip("<>").lower()
            if "@" in address and address not in self.attendees:
                self.attendees.append(address)
        self.base = normalise_title(CLONE.sub("", self.title))

    @property
    def span(self):
        return (self.start.isoformat() if self.start else "", self.end.isoformat() if self.end else "")


def owner_response(row, addresses):
    for person in row.people:
        if str(person.get("email") or "").strip().lower() in addresses:
            return str(person.get("response_status") or "")
    return ""


def clean_calendar(rows, addresses):
    """(timed events kept, all-day events, counts dropped by reason)."""
    dropped = {"cancelled": 0, "declined": 0, "duplicate": 0, "clone": 0}
    timed, all_day = [], []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        row = Row(raw)
        if row.cancelled:
            dropped["cancelled"] += 1
        elif owner_response(row, addresses).lower() == "declined":
            dropped["declined"] += 1
        elif row.all_day:
            all_day.append(row)
        elif row.start and row.end and row.end > row.start:
            timed.append(row)
    best, order = {}, []
    for row in timed:
        key = (*row.span, row.base)
        seen = best.get(key)
        if seen is None:
            best[key] = row
            order.append(key)
            continue
        dropped["duplicate"] += 1
        if (row.is_meeting, len(row.people)) > (seen.is_meeting, len(seen.people)):
            best[key] = row
    kept = [best[k] for k in order]
    meeting_spans = {r.span for r in kept if not r.is_availability}
    block_spans, out = set(), []
    for row in kept:
        if row.is_availability:
            # A block at exactly the time of a kept meeting, or of a block already kept, is
            # the same busy time under another name.
            if row.span in meeting_spans or row.span in block_spans:
                dropped["clone"] += 1
                continue
            block_spans.add(row.span)
        out.append(row)
    out.sort(key=lambda r: (r.start, r.end, r.title))
    return out, all_day, dropped


def kind_of(row, focus):
    if focus.search(CLONE.sub("", row.title)):
        return "focus"
    return "meeting" if row.is_meeting else "hold"


def event_view(row, kind, owner, tz):
    mine, internal = set(owner["addresses"]), set(owner["internal_domains"])
    ext = []
    if kind == "meeting":
        for address in row.attendees:
            d = domain_of(address)
            if address not in mine and d and d not in internal and d not in ext:
                ext.append(d)
    names = [str(p.get("name") or p.get("email") or "") for p in row.people
             if str(p.get("email") or "").strip().lower() not in mine]
    where = str(row.raw.get("location") or "").lower()
    return {"ref": row.ref, "title": row.title, "kind": kind,
            "start": local_hm(row.start, tz), "end": local_hm(row.end, tz),
            "minutes": int((row.end - row.start).total_seconds() // 60),
            "attendees": len(row.people), "names": names[:NAMES],
            "external": bool(ext), "external_domains": ext[:5], "owner_response": owner_response(row, mine),
            "online": bool(row.raw.get("meeting_url")) or "teams" in where or "zoom" in where,
            "calendar": row.calendar_name}


def merge_spans(spans):
    out = []
    for start, end in sorted(spans):
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


def day_calendar(rows, day, tz, owner, work, min_focus, focus_title):
    """The day's calendar, cleaned, with conflicts and free slots. No Portal calls."""
    focus = re.compile(focus_title)
    kept, all_day, dropped = clean_calendar(rows, set(owner["addresses"]))
    kinds = [(row, kind_of(row, focus)) for row in kept]
    conflicts = []
    for i, (a, ka) in enumerate(kinds):
        for b, kb in kinds[i + 1:]:
            if "focus" in (ka, kb) or (ka, kb) == ("hold", "hold"):
                continue
            s, e = max(a.start, b.start), min(a.end, b.end)
            if e > s:
                conflicts.append({"a": a.ref, "b": b.ref, "a_title": a.title, "b_title": b.title, "kinds": [ka, kb],
                                  "when": f"{local_hm(s, tz)}-{local_hm(e, tz)}",
                                  "minutes": int((e - s).total_seconds() // 60)})
    (sh, sm), (eh, em) = work
    w0, w1 = datetime.combine(day, time(sh, sm), tz), datetime.combine(day, time(eh, em), tz)
    busy = merge_spans((max(r.start, w0), min(r.end, w1)) for r, k in kinds
                       if k in ("meeting", "hold") and r.end > w0 and r.start < w1)
    free, cursor = [], w0
    for start, end in busy + [(w1, w1)]:
        if start > cursor:
            mins = int((start - cursor).total_seconds() // 60)
            if mins >= min_focus:
                free.append({"start": local_hm(cursor, tz), "end": local_hm(start, tz), "minutes": mins,
                             "focus_blocks": [r.title for r, k in kinds
                                              if k == "focus" and r.start < start and r.end > cursor]})
        cursor = max(cursor, end)
    meeting_minutes = sum(int((e - s).total_seconds() // 60)
                          for s, e in merge_spans((r.start, r.end) for r, k in kinds if k == "meeting"))
    return {"date": day.isoformat(), "weekday": day.strftime("%A"),
            "work_hours": f"{sh:02d}:{sm:02d}-{eh:02d}:{em:02d}", "min_focus": min_focus,
            "events": [event_view(r, k, owner, tz) for r, k in kinds],
            "all_day": [{"ref": r.ref, "title": r.title} for r in all_day],
            "conflicts": conflicts, "free": free, "free_minutes": sum(f["minutes"] for f in free),
            "meeting_minutes": meeting_minutes, "dropped": dropped, "raw_rows": len(rows)}


# --------------------------------------------------------------------------- tasks

def task_view(task, day, horizon, projects, goals, domains):
    status = str(task.get("status") or "").upper()
    # A WAITING task's follow-up date is its due date, never its deadline.
    due_text = str(task.get("due_date") or ("" if status == "WAITING" else task.get("deadline")) or "")[:10]
    try:
        due = date.fromisoformat(due_text) if due_text else None
    except ValueError:
        due = None
    lenses = []
    if due:
        if status == "WAITING":
            if due <= day:
                lenses.append("waiting_due")
        elif due < day:
            lenses.append("overdue")
        elif due == day:
            lenses.append("due_today")
        elif due <= day + timedelta(days=horizon):
            lenses.append("due_soon")
    elif status == "WAITING":
        lenses.append("waiting_no_date")
    if status == "IN_PROGRESS":
        lenses.append("in_progress")
    if str(task.get("priority") or "").upper() == "P1":
        lenses.append("p1")
    project = projects.get(str(task.get("project_id") or ""), {})
    goal_id = str(task.get("goal_id") or project.get("goal_id") or "")
    domain_id = str(task.get("domain_id") or project.get("domain_id") or "")
    return {"ref": f"portal://task/{task.get('id')}", "title": short(task.get("title"), 200), "status": status,
            "priority": task.get("priority"), "due_date": task.get("due_date"), "deadline": task.get("deadline"),
            "lenses": lenses, "project": task.get("project_name") or project.get("name"),
            "project_id": task.get("project_id"), "project_deadline": project.get("deadline") or project.get("due_date"),
            "domain": domains.get(domain_id), "domain_id": domain_id or None,
            "goal": goals.get(goal_id, {}).get("title"), "goal_id": goal_id or None,
            "waiting_on": task.get("waiting_on_name"), "source": task.get("source"),
            "completed_at": task.get("completed_at"), "created_at": task.get("created_at"),
            "updated_at": task.get("updated_at"), "description": short(task.get("description"), DESCRIPTION_CHARS)}


def task_rank(view):
    first = min((LENS_ORDER.index(lens) for lens in view["lenses"] if lens in LENS_ORDER), default=len(LENS_ORDER))
    return first, str(view.get("due_date") or "9999"), str(view.get("priority") or "P9")


def read_rows(client, entity, filters, unread):
    rows, lost = c.page_through(client, entity, filters)
    if lost:
        unread.append(f"{entity} {filters or {}}: {lost} row(s) unreadable")
    return rows


# --------------------------------------------------------------------------- the morning plan

LINE = re.compile(r"^\s*\d+\.\s+\*\*(?P<title>.+?)\*\*(?:\s+\[[^\]]*\])?(?:\s+\((?P<ref>portal://[^)\s]+)\))?")


def morning_from_note(content):
    """The top three as the morning block rendered them, when no state copy exists."""
    found = c.blocks(content, "morning")
    if not found:
        return {}
    top, section = [], ""
    for line in found[-1][2].splitlines():
        if line.startswith("### "):
            section = line[4:].strip().lower()
        elif section == "top three" and LINE.match(line):
            m = LINE.match(line)
            top.append({"title": m.group("title"), "ref": m.group("ref") or ""})
    return {"source": "note", "top_three": top, "also_today": []}


def morning_plan(state, day, note, explicit):
    for source, path in ((explicit, Path(explicit).expanduser() if explicit else None),
                         ("state", c.state_file(state, day, "morning") if state else None)):
        plan = c.read_json(path) if path else None
        if isinstance(plan, dict):
            return {"source": source, "top_three": plan.get("top_three") or [],
                    "also_today": plan.get("also_today") or [], "proposals": plan.get("proposals") or []}
    parsed = morning_from_note(str(note.get("content") or "")) if note else {}
    return parsed or {"source": None, "top_three": [], "also_today": []}


def packets(calendar, done, sent, made, goals):
    """The day by domain, in the accomplishment gatherer's packet shape. Mail, notes and
    meetings carry no domain in the Portal, so they go in one unfiled packet."""
    empty = {"meeting": [], "sent_email": [], "created_note": [], "completed_task": [], "started_task": [],
             "created_draft": []}
    by_domain = {}
    for task in done:
        by_domain.setdefault(task.get("domain") or "(no domain)", []).append(task)
    out = [{"domain": {"name": name}, "density": "active" if len(rows) >= 3 else "thin",
            "items": dict(empty, completed_task=rows),
            "strategic_context": {"missions": [], "goals": [g for g in goals if g.get("domain") == name]}}
           for name, rows in sorted(by_domain.items())]
    meetings = [e for e in calendar["events"] if e["kind"] == "meeting"]
    if meetings or sent or made:
        count = len(meetings) + len(sent) + len(made)
        out.append({"domain": {"name": "(unfiled: meetings, sent mail, notes)"},
                    "density": "active" if count >= 3 else "thin",
                    "items": dict(empty, meeting=meetings, sent_email=sent, created_note=made),
                    "strategic_context": {"missions": [], "goals": []}})
    return out


# --------------------------------------------------------------------------- the pull

def build(client, day, pass_, work, min_focus, focus_title, horizon, max_tasks, internal, state,
          morning="", tz_name=""):
    unread = []
    me = client.call("whoami")
    if not isinstance(me, dict):
        raise c.Stop("whoami gave no answer")
    owner = owner_info(me, internal)
    if not owner.get("contact_id"):
        raise c.Stop("whoami named no contact for the owner")
    tz = c.zone(tz_name or owner.get("timezone"))
    start, end = day_bounds(day, tz)
    rows, lost = page_events(client, start, end)
    if lost:
        unread.append(f"calendar: {lost} row(s) unreadable")
    calendar = day_calendar(rows, day, tz, owner, work, min_focus, focus_title)
    calendar["needs_prep"] = []
    for event in calendar["events"]:
        if event["kind"] == "meeting" and event["external"]:
            linked = c.list_all(client, "note", {"entity_type": "calendar_event",
                                                 "entity_id": event["ref"].rsplit("/", 1)[-1]}, limit=20, max_pages=1)
            event["prep_notes"] = [f"portal://note/{n.get('id')}" for n in linked if n.get("id")]
            if not event["prep_notes"]:
                calendar["needs_prep"].append({"ref": event["ref"], "title": event["title"], "start": event["start"],
                                               "external_domains": event["external_domains"]})

    domains = {str(d.get("id")): str(d.get("name") or "").strip() for d in read_rows(client, "domain", None, unread)}
    goal_rows = read_rows(client, "goal", None, unread)
    goals = {str(g.get("id")): g for g in goal_rows}
    projects = {str(p.get("id")): p for p in read_rows(client, "project", None, unread)}
    who = owner["contact_id"]
    tasks = {}
    for filters in ({"owner_contact_id": who, "due_before": (day + timedelta(days=horizon)).isoformat()},
                    {"owner_contact_id": who, "status": "WAITING"},
                    {"owner_contact_id": who, "status": "IN_PROGRESS"},
                    {"owner_contact_id": who, "priority": "P1"}):
        for task in read_rows(client, "task", filters, unread):
            if str(task.get("status") or "").upper() in ("TODO", "IN_PROGRESS", "WAITING") and task.get("id"):
                tasks[str(task["id"])] = task
    views = sorted((v for v in (task_view(t, day, horizon, projects, goals, domains) for t in tasks.values())
                    if v["lenses"]), key=task_rank)
    lens_counts = {}
    for v in views:
        for lens in v["lenses"]:
            lens_counts[lens] = lens_counts.get(lens, 0) + 1
    active_goals = [{"ref": f"portal://goal/{g.get('id')}", "title": g.get("title"),
                     "domain": domains.get(str(g.get("domain_id") or "")), "horizon": g.get("horizon"),
                     "health": g.get("health_status"), "target_date": g.get("target_date")}
                    for g in goal_rows
                    if str(g.get("status") or "active").lower() not in ("archived", "completed", "cancelled", "done")]
    found = c.find_notes(client, day)
    note = found[0] if found else None
    result = {"tool": "daily-plan-pull", "version": 1, "date": day.isoformat(), "pass": pass_,
              "pulled_at": datetime.now(tz).isoformat(timespec="seconds"), "timezone": str(tz),
              "owner": owner, "calendar": calendar, "tasks": views[:max_tasks], "tasks_total": len(views),
              "task_lenses": lens_counts, "goals": active_goals, "domains": sorted(n for n in domains.values() if n),
              "note": c.note_summary(note, max(0, len(found) - 1)), "unreadable": unread}
    if pass_ == "evening":
        done_rows = read_rows(client, "task", {"owner_contact_id": who, "status": "DONE",
                                               "completed_since": iso(start), "completed_before": iso(end)}, unread)
        done = [task_view(t, day, horizon, projects, goals, domains) for t in done_rows]
        sent = [{"ref": e.get("_ref") or f"portal://email/{e.get('id')}", "subject": short(e.get("subject"), 160),
                 "to": (e.get("to_addresses") or [])[:3], "at": str(e.get("received_local") or "")[11:16]}
                for e in c.list_all(client, "email", {"direction": "sent", "since": iso(start), "until": iso(end)})]
        made = []
        for n in c.list_all(client, "note", {"since": iso(start)}):
            created = c.parse_time(n.get("created_at"))
            if (not str(n.get("title") or "").startswith(("Daily Plan - ", "Daily Note - "))
                    and created is not None and start <= created < end):
                made.append({"ref": n.get("_ref") or f"portal://note/{n.get('id')}", "title": short(n.get("title"), 160),
                             "type": n.get("note_type"), "at": str(n.get("created_at") or "")})
        result.update(done_today=done, sent=sent, notes=made, morning_plan=morning_plan(state, day, note, morning),
                      packets=packets(calendar, done, sent, made, active_goals))
        nxt = c.next_workday(day)
        n_start, n_end = day_bounds(nxt, tz)
        n_rows, n_lost = page_events(client, n_start, n_end)
        if n_lost:
            unread.append(f"tomorrow's calendar: {n_lost} row(s) unreadable")
        tomorrow = day_calendar(n_rows, nxt, tz, owner, work, min_focus, focus_title)
        result["tomorrow"] = {k: tomorrow[k] for k in ("date", "weekday", "events", "conflicts", "free",
                                                       "free_minutes", "meeting_minutes")}
    return result


def headline(result):
    cal = result["calendar"]
    parts = [f"{sum(1 for e in cal['events'] if e['kind'] == 'meeting')} meeting(s)",
             f"{len(cal['free'])} free slot(s), {cal['free_minutes']} min", f"{len(cal['conflicts'])} conflict(s)",
             f"{len(cal['needs_prep'])} external without prep", f"{result['tasks_total']} candidate task(s)"]
    if result["pass"] == "evening":
        parts += [f"{len(result['done_today'])} done", f"{len(result['sent'])} sent",
                  f"morning plan from {result['morning_plan'].get('source') or 'nowhere'}"]
    if result["unreadable"]:
        parts.append(f"{len(result['unreadable'])} read gap(s)")
    return f"FRESH: {result['date']} {result['pass']}: " + ", ".join(parts)


def main(argv=None, client=None):
    p = argparse.ArgumentParser(prog="daily_plan_pull.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--date", dest="day", default="", help="The day, yyyy-mm-dd (blank: today in the owner's timezone)")
    p.add_argument("--pass", dest="pass_", default="", help="morning or evening (blank: by the clock)")
    p.add_argument("--out", dest="out_path", default="", help="Write the pull here (JSON); without it, print it")
    p.add_argument("--work-start", default="08:00", help="Start of the working day, HH:MM")
    p.add_argument("--work-end", default="17:30", help="End of the working day, HH:MM")
    p.add_argument("--min-focus", default="60", help="Shortest free slot worth listing, minutes")
    p.add_argument("--focus-title", default=FOCUS_TITLE, help="Regex: an event title that is a focus block")
    p.add_argument("--internal-domain", dest="internal", action="append", default=[],
                   help="A mail domain whose people are not external (repeatable)")
    p.add_argument("--horizon", default=str(HORIZON_DAYS), help="Days ahead a due date counts as soon")
    p.add_argument("--max-tasks", default=str(MAX_TASKS))
    p.add_argument("--morning", default="", help="Evening: the morning plan.json to account for")
    p.add_argument("--tz", dest="tz_name", default="", help="IANA timezone (default the owner's, from whoami)")
    p.add_argument("--state", dest="state_path", default="", help="The state folder (default <state_dir>/daily-plan)")
    p.add_argument("--config", default=None, help="MCP config holding the Portal (default: setting portal_mcp_config)")
    p.add_argument("--server", default=None, help="Server name in the MCP config (default: setting portal_server)")
    args = p.parse_args(argv)
    try:
        work = (c.hhmm(args.work_start, "--work-start"), c.hhmm(args.work_end, "--work-end"))
        if work[1] <= work[0]:
            raise c.Stop("--work-end must be after --work-start")
        numbers = {}
        for name, value in (("--min-focus", args.min_focus), ("--horizon", args.horizon),
                            ("--max-tasks", args.max_tasks)):
            if not re.fullmatch(r"\d{1,4}", c.blank(value)):
                raise c.Stop(f"{name} wants a whole number, got {value!r}")
            numbers[name] = int(c.blank(value))
        pattern = c.blank(args.focus_title) or FOCUS_TITLE
        try:
            re.compile(pattern)
        except re.error as exc:
            raise c.Stop(f"--focus-title does not compile: {exc}") from None
        out = c.guard_run_path(args.out_path) if c.blank(args.out_path) else None
        if c.blank(args.day) and not c.DAY.match(c.blank(args.day)):
            raise c.Stop(f"--date wants yyyy-mm-dd, got {args.day!r}")
        if c.blank(args.pass_) and c.blank(args.pass_).lower() not in c.PASSES:
            raise c.Stop(f"--pass is morning or evening, got {args.pass_!r}")
        try:
            state = c.state_root(args.state_path)
        except c.Stop:
            state = None  # only the evening's morning plan reads it; the note is the fallback
    except c.Stop as exc:
        print(c.safe(f"ERROR {exc}"), file=sys.stderr)
        sys.exit(2)
    label = f"{c.blank(args.day) or 'today'} {c.blank(args.pass_) or '(pass by the clock)'}"
    try:
        client = client or c.Portal(args.config, args.server)
        tz = c.zone(c.blank(args.tz_name) or c.owner_timezone(client))
        the_day, the_pass = c.resolve(args.day, args.pass_, tz)
        label = f"{the_day} {the_pass}"
        result = build(client, the_day, the_pass, work, numbers["--min-focus"], pattern, numbers["--horizon"],
                       numbers["--max-tasks"], args.internal, state, c.blank(args.morning), str(tz))
    except c.Stop as exc:
        print(c.safe(f"STALE: the Portal could not be read for {label} ({exc}); read it in the session"))
        sys.exit(0)
    except Exception as exc:  # a prepare step reports, never blocks the session
        print(f"STALE: the Portal could not be read for {label} ({type(exc).__name__}: {c.safe(exc)[:200]}); "
              "read it in the session")
        sys.exit(0)
    line = headline(result)
    if out is not None:
        c.write_json(out, result)
        print(line)
        print(f"  wrote {out}")
    else:
        print(line)
        print(c.safe(json.dumps(result, indent=1, default=str)))
    sys.exit(0)


if __name__ == "__main__":
    main()
