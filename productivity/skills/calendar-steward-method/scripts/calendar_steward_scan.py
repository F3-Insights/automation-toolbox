#!/usr/bin/env python3
"""calendar-steward-scan: the read-only calendar scan the steward starts from, computed before
the session.

The first line printed is `FRESH: <counts>` or `STALE: <reason>`, exit 0 either way, so a
prepare step never blocks the session: a stale scan tells the steward to read the Portal itself.

What it writes (--out, JSON):
- `owner` (contact, timezone, own addresses, internal domains), `window` and `settings`;
- `days`: every day of the window cleaned (clones, cancelled and declined rows dropped,
  availability blocks kept as holds, titles like "Deep Work" or "Focus" as focus blocks), each
  with its events, conflicts, free slots, back-to-back runs and longest free slot. A meeting
  with two or more people, or anyone external, is read in full once (at most --max-reads) for
  its organizer, agenda text, other attendees and linked prep notes;
- `findings`, each with a stable id `<kind>:<date>:<hash>`: conflict, focus-overlap, no-prep
  (an external meeting with no linked note), no-agenda (one per recurring series), back-to-back
  (three or more meetings under --break minutes apart), focus-short (a weekday with no free
  slot of --focus-target minutes), unanswered (an invitation not answered), daily-plan (a
  focus-block proposal the daily plan saved, not yet on the calendar or a steward list);
- `open_items` and `lists`: items of earlier steward lists not yet answered or applied.

Inputs: --date (first day; blank is today in the owner's zone), --days (14), --pass, --out,
--work-start, --work-end, --min-focus, --focus-target, --break, --max-reads, --focus-title,
--internal-domain (repeatable), --home, --daily-plan-state (the daily plan's state folder,
default <state_dir>/daily-plan), --tz. Exit 0 when it ran, 2 on a bad argument.

Example:
    python3 calendar_steward_scan.py --date 2026-10-05 --days 14 --out RUN/scan.json
"""

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta

import _common as c

DAYS, MIN_FOCUS, FOCUS_TARGET, BREAK, RUN_MIN, MAX_READS, AGENDA_CHARS = 14, 60, 90, 10, 3, 150, 40
NO_RESPONSE = ("needsaction", "tentativelyaccepted", "tentative", "notresponded")
BOILER = re.compile(r"(?i)(microsoft teams|join (the )?(meeting|zoom|on your)|meeting id|passcode|dial[- ]in|"
                    r"https?://|^_+$|^-+$|need help\?|for organizers|meeting options|zoom\.us|teams\.microsoft|"
                    r"one tap mobile|find your local number|tel:|\+\d[\d\s-]{6,})")


def agenda_text(description):
    """The description without the conferencing boilerplate: what a person wrote."""
    lines = []
    for line in str(description or "").splitlines():
        line = re.sub(r"<[^>]+>", " ", line).strip()
        if line and not BOILER.search(line):
            lines.append(line)
    return " ".join(" ".join(lines).split())


def span(e):
    s, f = c.minutes(e["start"]), c.minutes(e["end"])
    return s, (f if f > s else 24 * 60)


def back_to_back(events, gap, run_min=RUN_MIN):
    """Runs of `run_min` or more meetings with under `gap` minutes between each."""
    meetings = sorted((e for e in events if e.get("kind") == "meeting" and c.HHMM.match(str(e.get("start") or ""))
                       and c.HHMM.match(str(e.get("end") or ""))), key=lambda e: (e["start"], e["end"]))
    runs, current, reach = [], [], -1
    for e in meetings:
        s, f = span(e)
        if current and s - reach < gap:
            current.append(e)
            reach = max(reach, f)
        else:
            if len(current) >= run_min:
                runs.append(current)
            current, reach = [e], f
    if len(current) >= run_min:
        runs.append(current)
    return [{"start": r[0]["start"], "end": max(x["end"] for x in r), "count": len(r),
             "refs": [x["ref"] for x in r], "titles": [x["title"] for x in r]} for r in runs]


def focus_overlaps(events):
    out = []
    for f in (e for e in events if e.get("kind") == "focus"):
        fs, ff = span(f)
        for e in (e for e in events if e.get("kind") == "meeting"):
            es, ef = span(e)
            if es < ff and fs < ef:
                out.append({"focus": f["ref"], "focus_title": f["title"], "meeting": e["ref"], "meeting_title": e["title"],
                            "when": f"{max(e['start'], f['start'])}-{min(e['end'], f['end'])}"})
    return out


def enrich(portal, event, owner):
    """One full read of a meeting: organizer, agenda, prep notes, series, other attendees."""
    m = c.EVENT_REF.match(str(event.get("ref") or ""))
    try:
        out = portal.call("get", {"entity_type": "calendar_event", "id_or_query": m.group(1), "detail": "summary"}) if m else None
    except Exception:  # one unreadable meeting is a read gap, not a failed scan
        out = None
    if not isinstance(out, dict) or out.get("error"):
        event["read"] = False
        return
    rec = out.get("event") if isinstance(out.get("event"), dict) else out
    mine = set(owner.get("addresses") or [])
    organizer = str(rec.get("organizer_email") or "").strip().lower()
    emails = [str(a).strip().lower() for a in out.get("attendee_emails") or []] or \
             [str(a.get("email") or "").strip().lower() for a in rec.get("attendees") or [] if isinstance(a, dict)]
    agenda = agenda_text(rec.get("description"))
    event.update(read=True, organizer=organizer or None, owner_organizer=bool(organizer and organizer in mine),
                 others=sum(1 for e in set(emails) if e and e not in mine), agenda=agenda[:280],
                 agenda_chars=len(agenda), series=rec.get("recurring_event_id") or None)
    if event.get("external"):
        # A prep note is a note linked to this event; unknown when the read fails, so no finding.
        try:
            linked = portal.call("list_entities", {"entity_type": "note", "limit": 20,
                                                   "filters": {"entity_type": "calendar_event", "entity_id": m.group(1)}})
            linked = linked.get("items") if isinstance(linked, dict) else None
        except Exception:
            linked = None
        event["prep_notes"] = None if linked is None else len([n for n in linked if isinstance(n, dict) and n.get("id")])


def find(kind, day, refs, text, **extra):
    return dict({"id": c.finding_id(kind, day, refs), "kind": kind, "date": day, "refs": list(refs), "text": text}, **extra)


def day_findings(d, focus_target, weekday):
    day, label, out = d["date"], c.short_day(d["date"]), []
    for x in d["conflicts"]:
        out.append(find("conflict", day, [x["a"], x["b"]], f"{label} {x['when']}: {x['a_title']} and {x['b_title']} overlap",
                        when=x["when"]))
    for x in d["focus_overlaps"]:
        out.append(find("focus-overlap", day, [x["focus"], x["meeting"]],
                        f"{label} {x['when']}: {x['meeting_title']} sits on the focus block {x['focus_title']}", when=x["when"]))
    for r in d["back_to_back"]:
        out.append(find("back-to-back", day, r["refs"], f"{label} {r['start']}-{r['end']}: {r['count']} meetings back to back",
                        when=f"{r['start']}-{r['end']}"))
    if weekday and d["longest_free"] < focus_target:
        out.append(find("focus-short", day, [day], f"{label}: no free slot of {focus_target} minutes in working hours "
                                                   f"(longest {d['longest_free']} minutes, {d['meeting_minutes']} minutes of meetings)"))
    for e in d["events"]:
        if e.get("kind") != "meeting":
            continue
        if e.get("external") and e.get("read") and e.get("prep_notes") == 0:
            out.append(find("no-prep", day, [e["ref"]], f"{label} {e['start']}: {e['title']} (external: "
                                                        f"{', '.join(e.get('external_domains') or [])}) has no prep note",
                            when=e["start"]))
        if e.get("read") and not e.get("owner_organizer") and str(e.get("owner_response") or "").lower() in NO_RESPONSE:
            out.append(find("unanswered", day, [e["ref"]], f"{label} {e['start']}: {e['title']} is not answered "
                                                           f"({e.get('owner_response')})", when=e["start"]))
    return out


def agenda_findings(days):
    """One no-agenda finding per series (or single meeting), dated on its first instance."""
    groups, order = {}, []
    for d in days:
        for e in d["events"]:
            if (e.get("kind") == "meeting" and e.get("read") and (e.get("external") or (e.get("others") or 0) >= 2)
                    and (e.get("agenda_chars") or 0) < AGENDA_CHARS):
                key = str(e.get("series") or e["ref"])
                if key not in groups:
                    groups[key] = []
                    order.append(key)
                groups[key].append((d["date"], e))
    out = []
    for key in order:
        first_day, first = groups[key][0]
        refs = [e["ref"] for _, e in groups[key]]
        out.append(find("no-agenda", first_day, refs, f"{c.short_day(first_day)} {first['start']}: {first['title']} has no agenda"
                        + (f" ({len(refs)} instances in the window)" if len(refs) > 1 else ""), when=first["start"]))
    return out


def daily_plan_proposals(dp_state, start, end, days, open_from, now_local):
    """The daily plan's focus-block proposals (<state>/<day>/morning.json) for days in the
    window, still in the future, not yet on the calendar and not on a steward list."""
    by_day = {d["date"]: d for d in days}
    today, clock = now_local.date().isoformat(), now_local.strftime("%H:%M")
    out, day = [], start - timedelta(days=1)
    while day <= end:
        saved = c.read_json(dp_state / day.isoformat() / "morning.json")
        for p in (saved.get("proposals") if isinstance(saved, dict) else None) or []:
            if not isinstance(p, dict) or (p.get("kind") or "focus-block") != "focus-block":
                continue
            if not (c.HHMM.match(str(p.get("start") or "")) and c.HHMM.match(str(p.get("end") or ""))):
                continue
            pday = str(p.get("date") or day.isoformat())
            if pday < today or (pday == today and p["start"] <= clock) or pday > end.isoformat():
                continue
            src = f"{day.isoformat()}:{p.get('id')}"
            d = by_day.get(pday)
            if src in open_from or (d and any(e.get("kind") == "focus" and e["start"] <= p["start"] and e["end"] >= p["end"]
                                              for e in d["events"])):
                continue
            out.append({"from": src, "date": pday, "start": p["start"], "end": p["end"], "title": p.get("title"),
                        "for": p.get("for"), "why": p.get("why")})
        day += timedelta(days=1)
    return out


def earlier_lists(home, today):
    """(earlier lists still answerable, their items not yet final and not yet past)."""
    lists, items = [], []
    rows = {r["id"]: r for r in c.Ledger(home).rows()}
    for folder in c.day_folders(home):
        listed = c.folder_day(folder)
        if listed is None or listed >= today or listed < today - timedelta(days=c.LIST_DAYS):
            continue
        published, frozen = c.read_json(folder / "publish.json"), c.read_json(folder / "items.json")
        if not isinstance(published, dict) or not isinstance(frozen, dict):
            continue
        open_n = []
        for it in frozen.get("items") or []:
            row = rows.get(f"{folder.name}:{it['n']}") or {}
            if row.get("state") in c.FINAL or str(it.get("date") or "") < today.isoformat():
                continue
            open_n.append(it["n"])
            items.append({"list": folder.name, "n": it["n"], "kind": it.get("kind"), "date": it.get("date"),
                          "start": it.get("start"), "end": it.get("end"), "title": it.get("title"),
                          "event": it.get("event"), "from": it.get("from"), "state": row.get("state") or "proposed"})
        lists.append({"date": folder.name, "task": published.get("task"), "items": len(frozen.get("items") or []),
                      "open": open_n})
    return lists, items


def build(portal, start, days, pass_, *, work, min_focus, focus_target, gap, max_reads, focus_title, internal, home,
          dp_state, tz_name="", now=None):
    unread = []
    me = portal.call("whoami")
    if not isinstance(me, dict):
        raise c.Failure("whoami gave no answer")
    owner = c.owner_info(me, internal)
    tz = c.zone(tz_name or owner.get("timezone"))
    end = start + timedelta(days=days - 1)
    rows, lost = c.page_events(portal, c.day_bounds(start, tz)[0], c.day_bounds(end, tz)[1])
    if lost:
        unread.append(f"calendar: {lost} row(s) unreadable")
    grouped = {}
    for row in rows:
        moment = c.parse_time(row.get("start_time")) if isinstance(row, dict) else None
        if moment:
            grouped.setdefault(moment.astimezone(tz).date(), []).append(row)
    out_days, reads, day = [], 0, start
    while day <= end:
        cal = c.day_calendar(grouped.get(day, []), day, tz, owner, work, min_focus, focus_title)
        for e in cal["events"]:
            if e["kind"] == "meeting" and (e["attendees"] >= 2 or e["external"]):
                if reads < max_reads:
                    reads += 1
                    enrich(portal, e, owner)
                else:
                    e["read"] = False
        cal["back_to_back"] = back_to_back(cal["events"], gap)
        cal["focus_overlaps"] = focus_overlaps(cal["events"])
        cal["longest_free"] = max((f["minutes"] for f in cal["free"]), default=0)
        out_days.append(cal)
        day += timedelta(days=1)
    skipped = sum(1 for d in out_days for e in d["events"] if e.get("read") is False)
    if skipped:
        unread.append(f"{skipped} meeting(s) not read in full (over --max-reads {max_reads} or unreadable): "
                      "no agenda or prep finding for them")
    findings = []
    for d in out_days:
        findings += day_findings(d, focus_target, date.fromisoformat(d["date"]).weekday() < 5)
    findings += agenda_findings(out_days)
    now_local = (now or datetime.now(tz)).astimezone(tz)
    lists, open_items = earlier_lists(home, start)
    if dp_state is None:
        dp_props = []
        unread.append("daily plan: no state folder (set state_dir or pass --daily-plan-state)")
    else:
        dp_props = daily_plan_proposals(dp_state, start, end, out_days,
                                        [str(i.get("from")) for i in open_items if i.get("from")], now_local)
    for p in dp_props:
        findings.append(find("daily-plan", p["date"], [p["from"]],
                             f"{c.short_day(p['date'])} {p['start']}-{p['end']}: the daily plan proposed a focus block "
                             f"{p.get('title') or ''}".rstrip(), when=f"{p['start']}-{p['end']}", proposal=p))
    findings.sort(key=lambda f: (f["date"], f.get("when") or "", f["kind"]))
    counts = {}
    for f in findings:
        counts[f["kind"]] = counts.get(f["kind"], 0) + 1
    (sh, sm), (eh, em) = work
    return {"tool": c.SCAN_TOOL, "version": 1, "date": start.isoformat(), "pass": pass_,
            "pulled_at": now_local.isoformat(timespec="seconds"), "timezone": str(tz), "owner": owner,
            "window": {"start": start.isoformat(), "end": end.isoformat(), "days": days},
            "settings": {"work_hours": f"{sh:02d}:{sm:02d}-{eh:02d}:{em:02d}", "min_focus": min_focus,
                         "focus_target": focus_target, "break": gap, "max_reads": max_reads},
            "days": out_days, "findings": findings, "finding_counts": counts, "daily_plan": dp_props,
            "lists": lists, "open_items": open_items, "raw_rows": len(rows), "reads": reads, "unreadable": unread}


def headline(result):
    meetings = sum(1 for d in result["days"] for e in d["events"] if e["kind"] == "meeting")
    parts = [f"{meetings} meeting(s)", f"{len(result['findings'])} finding(s)"]
    parts += [f"{n} {k}" for k, n in sorted(result["finding_counts"].items())]
    if result["open_items"]:
        parts.append(f"{len(result['open_items'])} item(s) open on earlier lists")
    if result["unreadable"]:
        parts.append(f"{len(result['unreadable'])} read gap(s)")
    w = result["window"]
    return f"FRESH: {w['start']} to {w['end']} ({result['pass']} pass): " + ", ".join(parts)


def number(name, value):
    text = c.blank(value)
    if not re.fullmatch(r"\d{1,4}", text):
        raise c.Bad(f"{name} wants a whole number, got {value!r}")
    return int(text)


def main():
    parser = argparse.ArgumentParser(description="The read-only two-week calendar scan for the calendar steward. "
                                                 "Prints FRESH: or STALE: first; exit 0 when it ran, 2 on a bad argument.")
    parser.add_argument("--date", default="", help="first day of the window, yyyy-mm-dd (blank: today)")
    parser.add_argument("--days", default=str(DAYS), help="days in the window (1 to 31)")
    parser.add_argument("--pass", dest="pass_", default="", help="auto, propose or approve (blank: auto)")
    parser.add_argument("--out", default="", help="write the scan here (JSON); without it, print it")
    parser.add_argument("--work-start", default="08:00")
    parser.add_argument("--work-end", default="17:30")
    parser.add_argument("--min-focus", default=str(MIN_FOCUS), help="shortest free slot listed, minutes")
    parser.add_argument("--focus-target", default=str(FOCUS_TARGET), help="a weekday without a free slot this long is focus-short")
    parser.add_argument("--break", dest="gap", default=str(BREAK), help="under this many minutes between meetings is back to back")
    parser.add_argument("--max-reads", default=str(MAX_READS), help="at most this many meetings read in full")
    parser.add_argument("--focus-title", default=c.FOCUS_TITLE, help="regex: a title that is a focus block")
    parser.add_argument("--internal-domain", dest="internal", action="append", default=[],
                        help="a mail domain whose people are not external (repeatable)")
    parser.add_argument("--home", default="", help="the steward's home folder")
    parser.add_argument("--daily-plan-state", default="", help="the daily plan's state folder")
    parser.add_argument("--tz", default="", help="IANA timezone (default the owner's, from whoami)")
    args = parser.parse_args()
    try:
        work = (c.hhmm(args.work_start, "--work-start"), c.hhmm(args.work_end, "--work-end"))
        if work[1] <= work[0]:
            raise c.Bad("--work-end must be after --work-start")
        n_days = number("--days", args.days)
        if not 1 <= n_days <= 31:
            raise c.Bad("--days is 1 to 31")
        numbers = {k: number(k, v) for k, v in (("--min-focus", args.min_focus), ("--focus-target", args.focus_target),
                                                ("--break", args.gap), ("--max-reads", args.max_reads))}
        pattern = c.blank(args.focus_title) or c.FOCUS_TITLE
        try:
            re.compile(pattern)
        except re.error as exc:
            raise c.Bad(f"--focus-title does not compile: {exc}") from None
        the_pass = c.resolve_pass(args.pass_)
        out = c.guard_run_path(args.out) if c.blank(args.out) else None
        start = c.resolve_day(args.date, c.zone(c.blank(args.tz) or None))
        home = c.home_dir(args.home)
        dp_state = c.state_folder(args.daily_plan_state, "daily_plan_state", "daily-plan")
    except c.Bad as exc:
        print(f"ERROR {c.safe(exc)}", file=sys.stderr)
        sys.exit(2)
    try:
        result = build(c.client(), start, n_days, the_pass, work=work, min_focus=numbers["--min-focus"],
                       focus_target=numbers["--focus-target"], gap=numbers["--break"], max_reads=numbers["--max-reads"],
                       focus_title=pattern, internal=args.internal, home=home, dp_state=dp_state, tz_name=c.blank(args.tz))
    except Exception as exc:  # a prepare step reports, never blocks the session
        print(f"STALE: the calendar could not be read from {start} ({type(exc).__name__}: {c.safe(exc)[:200]}); "
              "read it in the session")
        if out is not None:
            c.write_json(out, {"tool": c.SCAN_TOOL, "version": 1, "date": start.isoformat(), "pass": the_pass,
                               "stale": True, "reason": c.safe(exc)[:300]})
        sys.exit(0)
    line = headline(result)
    if out is not None:
        c.write_json(out, result)
        print(line)
        print(f"  wrote {out}")
    else:
        print(line)
        print(c.safe(json.dumps(result, indent=1, default=str)))


if __name__ == "__main__":
    main()
