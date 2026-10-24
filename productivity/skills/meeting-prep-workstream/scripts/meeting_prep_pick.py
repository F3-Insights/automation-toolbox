#!/usr/bin/env python3
"""meeting-prep-pick: which of one day's meetings get a prep note, picked in code before the session.

Read only toward the Portal; writes nothing but --out. For the day asked, in the owner's own
timezone (from whoami), it lists the calendar with the day's window as UTC instants, keeps the
copy with the most attendees where a cloned event left duplicates, and gives every event one
outcome, the way the meeting-prep-workstream skill's section Which meetings says:

- skipped, with the reason: all day, an availability or focus block, cancelled, a personal
  title, an internal recurring meeting, or no attendee from outside the owner's own mail domains;
- a candidate: an attendee from outside those domains; a business or networking title on an
  event with nobody else on it; or a client's staff meeting longer than --staff-minutes (the
  owner holds an address at the client's domain, so its staff look internal; --home-domains
  names the owner's own firm's domains, and every other domain of the owner's is a client's).

Candidates are ranked, never taken in calendar order: 1 the owner organizes it, or the title
says he presents, hosts or trains; 2 an attendee at a company domain (not a public mail
service); 3 a one-off (no series) with only public-mail or no attendees; 4 any other
candidate; 5 a client's recurring staff meeting. Ties go by start time. Each candidate is then
searched for its prep note by the exact title `Meeting Prep: <title> - <yyyy-mm-dd>`. Walking
the ranks in order, a meeting that has its note is `prepped` and takes a place under the cap;
one that has none is `picked` while places remain, else `dropped` with its rank, the owner's
role and the attendees. A higher rank is never dropped to fit a lower one.

--day is a date (yyyy-mm-dd), `today`, `tomorrow` or `next-working-day`; blank is today before
noon in the owner's zone and the next working day from noon on (a morning Run preps today, an
evening Run the next working day). A weekday that comes back with no events at all is listed
once more before it is trusted.

--precheck prints one line, `WORK: ...` when a meeting is left to prep or `NOTHING: ...`, and
exits 0; a Portal that cannot be read prints the reason on stderr and exits 2, so a scheduler
records a failed check rather than a quiet day. Without it, the JSON is printed (exit 0, 2 on
an error). --out also writes the JSON, for the session to read as RUN/picks.json.

Example:
    python3 meeting_prep_pick.py --precheck --day next-working-day
    python3 meeting_prep_pick.py --day 2030-03-07 --cap 5 --home-domains firm.test --out RUN/picks.json
"""

import argparse
import json
import re
import sys
from datetime import date, datetime, time, timedelta, timezone

import _common as c

CAP, PAGE, NOON = 5, 50, 12
NOTE_TITLE = "Meeting Prep: {title} - {day}"
CANCELLED_PREFIXES = ("canceled:", "cancelled:")
BLOCK_KINDS = {"availability_block", "focus", "focus_time", "out_of_office", "working_location"}


def words(*items):
    return re.compile(r"(?i)\b(?:" + "|".join(items) + r")\b")


PERSONAL = words("lunch", "gym", "dentist", "doctor", "personal", "block", "focus time", "focus", "commute",
                 "family", "school", "pickup", "pick-up", "workout", "haircut", "birthday", "vacation", "ooo",
                 "out of office", "hold")
PRIVATE = words("gym", "dentist", "doctor", "commute", "family", "school", "pickup", "pick-up", "workout",
                "haircut", "birthday", "vacation", "ooo", "out of office")
INTERNAL = words("standup", "stand-up", "team sync", "1:1", "1-1", "one on one", "all-hands", "all hands")
BUSINESS = words("call", "review", "demo", "interview", "planning", "meeting", "proposal", "kickoff", "kick-off",
                 "coffee", "intro", "introduction", "catch up", "catch-up", "dinner", "breakfast", "drinks")
LEADS = words("present", "presents", "presenting", "presentation", "host", "hosting", "training", "train",
              "workshop", "webinar", "keynote", "teach", "teaching", "lecture")
_CLONE = re.compile(r"(?i)\s*[\(\[][^\)\]]*\bclone\b[^\)\]]*[\)\]]")


def norm(text):
    return " ".join(str(text or "").split()).casefold()


def addresses(entries):
    out = []
    for entry in entries or []:
        value = entry if isinstance(entry, str) else next(
            (str(entry[k]) for k in ("email", "address", "email_address", "value")
             if isinstance(entry, dict) and str(entry.get(k) or "").strip()), "")
        address = c.bare_address(value)
        if address and address not in out:
            out.append(address)
    return out


def event_id(row):
    return c.bare_id(row.get("id") or row.get("_ref"))


def event_ref(row):
    return row.get("_ref") or f"portal://calendar_event/{event_id(row)}"


def page_events(portal, since, until, page=PAGE, max_calls=200):
    """Every calendar row in [since, until). A page the server will not serialise is asked for
    again at half the size, down to one row, which is then stepped over. Reading nothing at all
    is an error, never an empty day."""
    filters = {"since": c.iso_z(since), "until": c.iso_z(until)}
    items, offset, total, calls, skipped, failure, read_any = [], 0, None, 0, 0, "", False
    while calls < max_calls:
        served, size = None, page
        while calls < max_calls:
            args = {"entity_type": "calendar_event", "filters": filters, "limit": size}
            if offset:
                args["offset"] = offset
            calls += 1
            try:
                out = portal.call("list_entities", args)
            except c.PortalUnreachable:
                raise
            except c.PortalError as exc:
                failure = str(exc)
                if size == 1:
                    break
                size = max(1, size // 2)
                continue
            served = out if isinstance(out, dict) and not out.get("error") else None
            if served is None:
                failure = str((out or {}).get("error") if isinstance(out, dict) else "no answer")
                if size == 1:
                    break
                size = max(1, size // 2)
                continue
            break
        if served is None:
            if not read_any:
                raise c.PortalError(f"could not list the calendar ({failure})")
            skipped += 1
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
        if total is not None and offset >= total:
            break
        if not served.get("has_more") and size >= page:
            break
    return items, skipped


def resolve_day(text, today, hour):
    text = str(text or "").strip().lower()
    if text in ("", "auto"):
        text = "today" if hour < NOON else "next-working-day"
    if text == "today":
        return today
    if text == "tomorrow":
        return today + timedelta(days=1)
    if text in ("next-working-day", "next working day"):
        day = today + timedelta(days=1)
        while day.weekday() >= 5:
            day += timedelta(days=1)
        return day
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise c.Failure(f"--day {text!r} is a date (yyyy-mm-dd), today, tomorrow or next-working-day") from None


def deduplicate(rows):
    """One row per start, end and title (clone markers and Canceled: aside), the copy with the most attendees."""
    best, order = {}, []
    for row in rows:
        title = _CLONE.sub("", str(row.get("title") or ""))
        for prefix in CANCELLED_PREFIXES:
            if title.strip().lower().startswith(prefix):
                title = title.strip()[len(prefix):]
        key = (str(row.get("start_time") or ""), str(row.get("end_time") or ""), norm(title))
        seen = best.get(key)
        if seen is None:
            best[key] = row
            order.append(key)
        elif len(addresses(row.get("attendees"))) > len(addresses(seen.get("attendees"))):
            best[key] = row
    return [best[k] for k in order]


def classify(row, me, home_domains, staff_minutes):
    """(candidate facts, None) or (None, the reason it is skipped)."""
    title = " ".join(str(row.get("title") or "").split())
    kind = str(row.get("event_kind") or "").strip().lower()
    start, end = c.parse_time(row.get("start_time")), c.parse_time(row.get("end_time"))
    if row.get("is_all_day"):
        return None, "all day"
    if kind in BLOCK_KINDS:
        return None, "availability or focus block"
    if title.lower().startswith(CANCELLED_PREFIXES) or row.get("is_cancelled") or \
            str(row.get("status") or "").lower() in ("cancelled", "canceled"):
        return None, "cancelled"
    if not title:
        return None, "no title"
    mine, internal = set(me["addresses"]), set(me["internal_domains"])
    others = [a for a in addresses(row.get("attendees")) if a not in mine]
    external = [a for a in others if c.domain_of(a) not in internal]
    minutes = int((end - start).total_seconds() // 60) if start and end and end > start else 0
    facts = {"title": title, "start": start, "end": end, "minutes": minutes, "others": others,
             "external": external, "series": row.get("recurring_event_id") or row.get("series_master_id") or None,
             "organizer": c.bare_address(row.get("organizer_email") or "") or None, "staff": False, "why": ""}
    if external:
        if PRIVATE.search(title):
            return None, "personal"
        facts["why"] = "external attendees"
        return facts, None
    if PERSONAL.search(title):
        return None, "personal"
    client_domains = sorted({c.domain_of(a) for a in others} - set(home_domains)) if home_domains else []
    if others and client_domains and staff_minutes is not None and minutes > staff_minutes:
        facts.update(staff=True, why=f"a client's staff meeting over {staff_minutes} minutes",
                     client_domains=client_domains)
        return facts, None
    if INTERNAL.search(title):
        return None, "internal recurring"
    if others:
        return None, "internal"
    if BUSINESS.search(title):
        facts["why"] = "a business or networking title with nobody else invited"
        return facts, None
    return None, "no external attendee"


def complete(portal, row, facts, warnings):
    """Organizer and series from one read of the event, when the listing left them out."""
    if facts["organizer"] and facts["series"] is not None:
        return
    try:
        out = portal.call("get", {"entity_type": "calendar_event", "id_or_query": event_id(row), "detail": "summary"})
    except c.PortalUnreachable:
        raise
    except c.PortalError as exc:
        warnings.append(f"{event_ref(row)}: could not read the event ({exc}); organizer unknown")
        return
    rec = out.get("event") if isinstance(out, dict) and isinstance(out.get("event"), dict) else out
    if not isinstance(rec, dict):
        return
    facts["organizer"] = facts["organizer"] or c.bare_address(rec.get("organizer_email") or "") or None
    facts["series"] = facts["series"] or rec.get("recurring_event_id") or rec.get("series_master_id") or None


def rank(facts, mine):
    if (facts["organizer"] and facts["organizer"] in mine) or LEADS.search(facts["title"]):
        return 1
    if facts["staff"]:
        return 5 if (facts["series"] or INTERNAL.search(facts["title"])) else 4
    if any(c.domain_of(a) not in c.PUBLIC_MAIL for a in facts["external"]):
        return 2
    if not facts["series"]:
        return 3
    return 4


def prepped(portal, title):
    """The prep note already written under this exact title, or None."""
    found = portal.call("search", {"query": title, "limit": 10})
    hits = (found.get("notes") if isinstance(found, dict) else None) or []
    for hit in hits:
        if isinstance(hit, dict) and hit.get("id") and norm(hit.get("title")) == norm(title):
            return f"portal://note/{c.bare_id(hit['id'])}"
    return None


def pick(portal, day_text="", cap=CAP, home_domains=(), staff_minutes=None, now=None):
    me = c.owner(portal)
    tz, mine = me["tz"], set(me["addresses"])
    now = now or datetime.now(timezone.utc)
    local_now = now.astimezone(tz)
    day = resolve_day(day_text, local_now.date(), local_now.hour)
    since = datetime.combine(day, time.min, tz)
    until = datetime.combine(day + timedelta(days=1), time.min, tz)
    warnings = []
    if not me["addresses"]:
        warnings.append("whoami returned no inbox address, so the owner cannot be told from an attendee")
    rows, skipped_rows = page_events(portal, since, until)
    if not rows and day.weekday() < 5:
        rows, skipped_rows = page_events(portal, since, until)
        if not rows:
            warnings.append(f"{day} is a weekday with no events at all, listed twice")
    if skipped_rows:
        warnings.append(f"{skipped_rows} calendar row(s) could not be read and were stepped over")
    rows = deduplicate(rows)

    candidates, skipped = [], []
    for row in rows:
        facts, reason = classify(row, me, home_domains, staff_minutes)
        start = facts["start"] if facts else c.parse_time(row.get("start_time"))
        if facts is None:
            skipped.append({"event": event_ref(row), "title": " ".join(str(row.get("title") or "").split()),
                            "start_local": start.astimezone(tz).strftime("%H:%M") if start else None,
                            "reason": reason})
            continue
        complete(portal, row, facts, warnings)
        candidates.append((rank(facts, mine), start or since, row, facts))
    candidates.sort(key=lambda x: (x[0], x[1]))

    picks, done, dropped, places = [], [], [], cap
    for n, start, row, facts in candidates:
        title = NOTE_TITLE.format(title=facts["title"], day=day.isoformat())
        role = ("organizer" if facts["organizer"] in mine else "attendee") if facts["organizer"] else "unknown"
        entry = {"event": event_ref(row), "title": facts["title"], "rank": n, "why": facts["why"],
                 "start_local": start.astimezone(tz).strftime("%H:%M"),
                 "end_local": facts["end"].astimezone(tz).strftime("%H:%M") if facts["end"] else None,
                 "minutes": facts["minutes"], "owner_role": role, "series": bool(facts["series"]),
                 "attendees": facts["others"][:12], "attendee_count": len(facts["others"]),
                 "external_domains": sorted({c.domain_of(a) for a in facts["external"]}), "note_title": title}
        note = prepped(portal, title)
        if note:
            done.append(dict(entry, note=note))
            places = max(0, places - 1)
        elif places > 0:
            picks.append(entry)
            places -= 1
        else:
            dropped.append(dict(entry, reason="cap"))

    counts = {"events": len(rows), "candidates": len(candidates), "picked": len(picks), "prepped": len(done),
              "dropped": len(dropped), "skipped": len(skipped)}
    return {"tool": "meeting-prep-pick", "version": 1, "day": day.isoformat(), "timezone": me["timezone"],
            "window": {"since": c.iso_z(since), "until": c.iso_z(until)}, "cap": cap,
            "rules": {"home_domains": list(home_domains), "staff_minutes": staff_minutes},
            "counts": counts, "picks": picks, "prepped": done, "dropped": dropped, "skipped": skipped,
            "warnings": warnings}


def line(result):
    n = result["counts"]
    if not n["picked"]:
        return (f"NOTHING: no external meeting left to prep on {result['day']} ({n['prepped']} already prepped, "
                f"{n['skipped']} skipped of {n['events']} events)")
    return (f"WORK: {n['picked']} meeting(s) to prep on {result['day']}; {n['prepped']} already prepped, "
            f"{n['dropped']} dropped by the cap of {result['cap']}")


def main(argv=None, portal=None, now=None):
    p = argparse.ArgumentParser(prog="meeting_prep_pick.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--day", default="", help="yyyy-mm-dd, today, tomorrow or next-working-day (blank: by the hour)")
    p.add_argument("--precheck", action="store_true", help="one line, WORK: or NOTHING:, for a scheduler")
    p.add_argument("--out", default="", help="also write the JSON to this file (the Run's picks.json)")
    p.add_argument("--cap", type=int, default=CAP, help=f"meetings prepped per day, prepped ones included (default {CAP})")
    p.add_argument("--home-domains", default="",
                   help="the owner's own firm's mail domains, comma separated; the owner's other domains are clients'")
    p.add_argument("--staff-minutes", default="",
                   help="a client's staff meeting longer than this counts as external (blank: never)")
    p.add_argument("--config", default="", help="the MCP config holding the Portal (default: the setting)")
    a = p.parse_args(argv)
    try:
        if not 0 <= a.cap <= 50:
            raise c.Failure("--cap is 0 to 50")
        staff = a.staff_minutes.strip()
        if staff and not staff.isdigit():
            raise c.Failure("--staff-minutes is a whole number of minutes")
        home = tuple(d.strip().lower().lstrip("@") for d in a.home_domains.split(",") if d.strip())
        result = pick(portal or c.client(a.config or None), a.day, a.cap, home, int(staff) if staff else None, now)
        if a.out:
            out = c.guard_run_path(a.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, indent=1, default=str) + "\n", encoding="utf-8")
    except Exception as exc:  # a check that could not run is never a quiet day
        reason = str(exc) if isinstance(exc, (c.Failure, ValueError)) else f"{type(exc).__name__}: {exc}"
        if a.precheck:
            print(c.safe(f"meeting-prep-pick: {reason}"), file=sys.stderr)
            sys.exit(c.ERROR)
        c.fail(reason)
    if a.precheck:
        print(c.safe(line(result)))
        sys.exit(c.OK)
    c.emit(result, c.OK)


if __name__ == "__main__":
    main()
