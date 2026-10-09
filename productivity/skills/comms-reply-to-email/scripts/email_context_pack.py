#!/usr/bin/env python3
"""email-context-pack: one email, to the data pack a reply is researched from.

Step 2 of comms-reply-to-email. The researcher starts from this JSON instead of paging the
Portal itself. Read only. Every item carries its `_ref`:

- `email` (the pinned message) and `thread` (every message the Portal returns on its thread,
  the newest when capped), each with its full readable body, direction, sender, To and Cc;
- `contact`: the person being answered (the sender, or --contact): name, title, company,
  addresses, priority, relationship notes, last touch;
- `tasks`: open tasks about that person, waiting on them, or linked to the email, and
  `projects`, the projects those tasks sit in;
- `voice_samples`: the owner's last N sent emails to this person, full bodies;
- `calendar`: free slots in working hours (09:00 to 17:00) over the next 10 working days in
  the owner's timezone, when the email seems to ask to meet (a keyword check, reported as one)
  or with --slots yes.

What could not be read is null with the reason in `unknown`, never an empty list: an empty
list means the read ran and found nothing.

Inputs: the email ref or id; --contact, --voice N, --slots auto|yes|no, --out FILE. Prints the
pack, or with --out writes it there (never inside the toolbox) and prints a summary. Exit 0,
or 2 on an error.

Example:
    python3 email_context_pack.py portal://email/5b1c... --contact 2f0c... --out RUN/pack.json
"""

import argparse
import json
import re
from datetime import datetime, time, timedelta, timezone

import _common as c

VOICE_DEFAULT = 5
SLOT_DAYS = 10
WORK_START, WORK_END = time(9, 0), time(17, 0)
MIN_SLOT_MINUTES = 30
MAX_TASKS = 25
MAX_PROJECTS = 10

# Decides only whether free slots are worth computing; the pack says it was a keyword check.
MEETING_WORDS = re.compile(
    r"(?i)\b(meet|meeting|call|chat|catch up|catch-up|sync|zoom|teams|availability|available|"
    r"schedule|calendar|time to talk|free (?:on|next|this)|what time|when (?:are|would) you|"
    r"coffee|lunch|next week|this week)\b")
CONTACT_FIELDS = ("full_name", "title", "department", "priority", "warmth", "relationship_context",
                  "how_they_help", "persona", "preferred_contact_method", "phone", "last_touch_at",
                  "last_touch_kind", "next_follow_up", "timezone", "is_active")
TASK_FIELDS = ("id", "_ref", "title", "status", "priority", "due_date", "project_id", "project_name",
               "waiting_on_name", "waiting_since", "owner_name")


def unknown(out, field, reason):
    out[field] = None
    out["unknown"].append({"field": field, "reason": reason})


def call(portal, tool, args):
    out = portal.call(tool, args)
    if isinstance(out, dict) and out.get("error"):
        raise c.Failure(f"{tool}: {out['error']}")
    return out


def bodies(portal, ids):
    """Readable bodies by email id, fifty at a time."""
    found = {}
    for start in range(0, len(ids), 50):
        out = call(portal, "email_bodies", {"ids": ids[start:start + 50]})
        for row in (out or {}).get("items") or []:
            if isinstance(row, dict) and row.get("found"):
                found[str(row["id"])] = row
    return found


def thread_part(portal, eid, out):
    got = call(portal, "get", {"entity_type": "email", "id_or_query": eid})
    messages = [m for m in got.get("thread") or [] if isinstance(m, dict)]
    ids = [str(m["id"]) for m in messages if m.get("id")]
    if eid not in ids:
        ids.append(eid)
    text = bodies(portal, ids)
    rows = []
    for m in messages or [{"id": eid}]:
        mid = str(m.get("id"))
        body = text.get(mid) or {}
        rows.append({"id": mid, "_ref": c.email_ref(mid), "direction": m.get("direction") or body.get("direction"),
                     "from_address": c.bare_address(m.get("from_address") or body.get("from_address")),
                     "from_name": m.get("from_name") or body.get("from_name"),
                     "to_addresses": m.get("to_addresses"), "cc_addresses": m.get("cc_addresses"),
                     "received_at": m.get("received_at") or body.get("received_at"),
                     "received_local": m.get("received_local"),
                     "subject": m.get("subject") or body.get("subject"),
                     "body": body.get("body"), "body_truncated": body.get("truncated"),
                     "body_found": bool(body)})
    out["thread"] = rows
    out["thread_meta"] = {"total": got.get("thread_total"), "truncated": got.get("thread_truncated")}
    pinned = next((r for r in rows if r["id"] == eid), None)
    out["email"] = pinned
    if pinned and not pinned["body_found"]:
        out["unknown"].append({"field": "email.body", "reason": "email_bodies did not return this message"})
    return got


def contact_part(portal, cid, out):
    got = call(portal, "get", {"entity_type": "contact", "id_or_query": cid, "detail": "full"})
    record = got.get("contact") if isinstance(got.get("contact"), dict) else {}
    company = got.get("company") if isinstance(got.get("company"), dict) else None
    rels = [{k: r.get(k) for k in ("other_name", "relationship_type", "title", "notes", "_ref")}
            for r in (got.get("relationships") or [])[:10] if isinstance(r, dict)]
    cid = record.get("id") or cid
    out["contact"] = {"id": cid, "_ref": f"portal://contact/{cid}", **{k: record.get(k) for k in CONTACT_FIELDS},
                      "addresses": c.contact_addresses(got),
                      "company": ({"name": company.get("name"), "_ref": company.get("_ref")
                                   or (f"portal://company/{company['id']}" if company.get("id") else None)}
                                  if company else None),
                      "relationships": rels,
                      "recent_notes": [{"title": n.get("title"), "created_at": n.get("created_at"),
                                        "_ref": f"portal://note/{n.get('id')}"}
                                       for n in (got.get("notes") or [])[:5] if isinstance(n, dict)]}


def tasks_part(portal, cid, email_ctx, out):
    rows = {}
    for key in ("related_contact", "waiting_on_contact_id"):
        got = call(portal, "list_entities", {"entity_type": "task", "limit": MAX_TASKS,
                                             "filters": {key: cid, "status": ["TODO", "IN_PROGRESS", "WAITING"]}})
        for t in got.get("items") or []:
            if isinstance(t, dict) and t.get("id"):
                rows.setdefault(str(t["id"]), dict(t, linked_by=key))
    for t in email_ctx.get("related_tasks") or []:
        if isinstance(t, dict) and t.get("id") and str(t.get("status") or "").upper() not in ("DONE", "CANCELLED"):
            rows.setdefault(str(t["id"]), dict(t, linked_by="email"))
    tasks = []
    for t in list(rows.values())[:MAX_TASKS]:
        entry = {k: t.get(k) for k in TASK_FIELDS}
        entry["_ref"] = entry["_ref"] or f"portal://task/{t['id']}"
        entry["linked_by"] = t["linked_by"]
        tasks.append(entry)
    out["tasks"] = tasks
    projects = []
    for pid in list(dict.fromkeys(t["project_id"] for t in tasks if t.get("project_id")))[:MAX_PROJECTS]:
        try:
            p = call(portal, "get", {"entity_type": "project", "id_or_query": pid, "detail": "summary"})
        except c.Failure as exc:
            out["unknown"].append({"field": f"projects.{pid}", "reason": str(exc)})
            continue
        rec = p.get("project") if isinstance(p.get("project"), dict) else p
        projects.append({"id": pid, "_ref": f"portal://project/{pid}", "name": rec.get("name"),
                         "status": rec.get("status"), "due_date": rec.get("due_date"),
                         "health_status": rec.get("health_status")})
    out["projects"] = projects


def voice_part(portal, cid, addresses, n, out):
    got = call(portal, "list_entities", {"entity_type": "email", "limit": max(n * 3, 10),
                                         "filters": {"participant_contact_id": cid, "direction": "sent"}})
    rows = [r for r in got.get("items") or [] if isinstance(r, dict) and r.get("id")]
    to_them = [r for r in rows if set(c.addresses_in(r.get("to_addresses"))) & set(addresses)]
    to_them.sort(key=lambda r: c.parse_time(r.get("received_at")) or datetime.min.replace(tzinfo=timezone.utc),
                 reverse=True)
    chosen = to_them[:n]
    text = bodies(portal, [str(r["id"]) for r in chosen]) if chosen else {}
    out["voice_samples"] = [{"id": r["id"], "_ref": c.email_ref(r["id"]), "subject": r.get("subject"),
                             "sent_at": r.get("received_at"), "to_addresses": r.get("to_addresses"),
                             "body": (text.get(str(r["id"])) or {}).get("body")} for r in chosen]
    for sample in out["voice_samples"]:
        if sample["body"] is None:
            out["unknown"].append({"field": f"voice_samples.{sample['id']}.body",
                                   "reason": "email_bodies did not return this message"})


def asks_to_meet(email):
    """A keyword in the new text of the email (quoted history below "On ... wrote:" is cut)."""
    if not email:
        return False, "no email body to check"
    text = f"{email.get('subject') or ''}\n{email.get('body') or ''}"
    text = re.split(r"(?im)^(?:on .{0,120} wrote:|-{2,} ?original message|from: )", text)[0]
    hit = MEETING_WORDS.search(text)
    return (True, f"keyword {hit.group(0)!r}") if hit else (False, "no meeting keyword in the new text")


def working_days(start, count):
    out, day = [], start
    while len(out) < count:
        if day.weekday() < 5:
            out.append(day)
        day += timedelta(days=1)
    return out


def free_slots(events, days, tz, now):
    """Gaps of at least 30 minutes between busy timed events, inside working hours, from now on.
    All-day events are listed, not counted busy."""
    busy = sorted((e.start, e.end) for e in events
                  if e.start and e.end and e.end > e.start and not e.all_day and not e.cancelled)
    all_day = [{"date": e.start.astimezone(tz).date().isoformat() if e.start else None,
                "title": e.title, "_ref": e.ref or None} for e in events if e.all_day and not e.cancelled]
    slots = []
    for day in days:
        open_at = datetime.combine(day, WORK_START, tzinfo=tz).astimezone(timezone.utc)
        close_at = datetime.combine(day, WORK_END, tzinfo=tz).astimezone(timezone.utc)
        cursor = max(open_at, now)
        for start, end in busy:
            if end <= cursor or start >= close_at:
                continue
            if start > cursor and (start - cursor).total_seconds() >= MIN_SLOT_MINUTES * 60:
                slots.append((cursor, start))
            cursor = max(cursor, end)
        if close_at > cursor and (close_at - cursor).total_seconds() >= MIN_SLOT_MINUTES * 60:
            slots.append((cursor, close_at))
    return {"slots": [{"start_local": s.astimezone(tz).isoformat(), "end_local": e.astimezone(tz).isoformat(),
                       "minutes": int((e - s).total_seconds() // 60)} for s, e in slots],
            "all_day_events": all_day}


def calendar_part(portal, me, out, mode, now):
    wanted, basis = asks_to_meet(out.get("email"))
    if mode == "no":
        unknown(out, "calendar", "not requested (--slots no)")
        return
    if mode == "auto" and not wanted:
        unknown(out, "calendar", f"the email does not appear to ask to meet ({basis}); rerun with --slots yes")
        return
    tz = me["tz"]
    days = working_days(now.astimezone(tz).date(), SLOT_DAYS)
    since = datetime.combine(days[0], time(0, 0), tzinfo=tz).astimezone(timezone.utc)
    until = datetime.combine(days[-1] + timedelta(days=1), time(0, 0), tzinfo=tz).astimezone(timezone.utc)
    rows, unreadable = c.page_events(portal, since, until)
    events = c.deduplicate([c.Event(r) for r in rows])
    out["calendar"] = {"asked_to_meet": wanted, "basis": basis if mode == "auto" else "--slots yes",
                       "timezone": me["timezone"], "working_hours": f"{WORK_START:%H:%M}-{WORK_END:%H:%M}",
                       "days": [d.isoformat() for d in days], "min_slot_minutes": MIN_SLOT_MINUTES,
                       "source": "list_entities calendar_event, every kind counted busy",
                       "events_read": len(rows), "unreadable_rows": unreadable,
                       **free_slots(events, days, tz, now)}


def build(portal, email, contact_id="", voice=VOICE_DEFAULT, slots="auto", now=None):
    eid = c.bare_id(email)
    if not eid:
        raise c.Failure("give an email ref or id")
    moment = now or datetime.now(timezone.utc)
    me = c.owner(portal)
    out = {"generated_at": moment.isoformat(), "email_ref": c.email_ref(eid), "timezone": me["timezone"],
           "owner_addresses": me["addresses"], "unknown": []}
    ctx = thread_part(portal, eid, out)
    sender = ctx.get("sender") if isinstance(ctx.get("sender"), dict) else {}
    cid = c.bare_id(contact_id) or str(sender.get("id") or "")
    if cid:
        try:
            contact_part(portal, cid, out)
        except c.Failure as exc:
            unknown(out, "contact", str(exc))
        addresses = (out.get("contact") or {}).get("addresses") or []
        try:
            tasks_part(portal, cid, ctx, out)
        except c.Failure as exc:
            unknown(out, "tasks", str(exc))
            unknown(out, "projects", "depends on the tasks read, which failed")
        try:
            voice_part(portal, cid, addresses, voice, out)
        except c.Failure as exc:
            unknown(out, "voice_samples", str(exc))
    else:
        unknown(out, "contact", "the sender resolves to no Portal contact and no --contact was given")
        for part in ("tasks", "projects", "voice_samples"):
            unknown(out, part, "no contact to read them for")
    try:
        calendar_part(portal, me, out, slots, moment)
    except c.Failure as exc:
        unknown(out, "calendar", str(exc))
    return out


def main():
    parser = argparse.ArgumentParser(description="The JSON data pack a reply to one email is researched from. Read only.")
    parser.add_argument("email", help="the email ref or id")
    parser.add_argument("--contact", default="", help="the pinned contact id (default: the sender's)")
    parser.add_argument("--voice", type=int, default=VOICE_DEFAULT,
                        help="how many of the owner's sent emails to this person to include")
    parser.add_argument("--slots", choices=["auto", "yes", "no"], default="auto",
                        help="free calendar slots: auto computes them only when the email asks to meet")
    parser.add_argument("--out", default="", help="write the pack to this file (outside the toolbox) and print a summary")
    args = parser.parse_args()
    try:
        target = c.guard_run_path(args.out) if args.out else None
        pack = build(c.client(), args.email, args.contact, max(0, args.voice), args.slots)
    except Exception as exc:
        c.fail(exc if isinstance(exc, c.Failure) else f"email-context-pack could not complete: {type(exc).__name__}: {exc}")
    if target is None:
        c.emit(pack, c.OK)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(pack, indent=1, default=str), encoding="utf-8")
    c.emit({"status": "ok", "path": str(target), "thread_messages": len(pack.get("thread") or []),
            "tasks": None if pack.get("tasks") is None else len(pack["tasks"]),
            "voice_samples": None if pack.get("voice_samples") is None else len(pack["voice_samples"]),
            "calendar_slots": None if pack.get("calendar") is None else len(pack["calendar"]["slots"]),
            "unknown": pack["unknown"]}, c.OK)


if __name__ == "__main__":
    main()
