---
name: meeting-prep-workstream
description: Reference loaded by meeting-prep-orchestrator and meeting-prep-checker, not for a user request; what the daily meeting-prep pass adds to orchestration-workstream and meeting-prep. Covers MEETING-PREP-RULES.md first, which meetings get a pack (external, ranked, capped), what a pack holds (attendees, last touch, open items, what the owner owes them, the goal of the meeting), the already-prepped check, the note title and associations, the findability check that defines done, the DONE checklist and the shapes.
---

# Preparing meetings

This skill extends `orchestration-workstream`. The single-meeting method is `meeting-prep` (the `meeting_prep` call and the note). This skill adds which meetings get a pack, what a pack must hold and when it is done.

## The rules file first

`MEETING-PREP-RULES.md` (path in the inputs as `prep_rules`) holds the cap (default 5), which internal meetings count as external (for example a client's staff, over 30 minutes), titles and attendees never to prep, and the timing (the evening before for a next-morning meeting, the morning of for the rest). It wins.

## Which meetings

External meetings of the day in the owner's local day, at most the cap. List the events with the day's window as UTC instants computed from the owner's timezone (from `whoami`), never `<day>T00:00:00Z`, which misses evening events for an owner west of UTC. A weekday that comes back with no events at all is queried once more before it is trusted.

Skip personal events ("lunch", "gym", "dentist", "personal", "block", "focus time", "commute", "family"), internal recurring ones ("standup", "team sync", an internal "1:1", "all-hands"), generic titles with no external attendee, and cancelled events. Prep events with external attendees (another email domain), business meetings ("call", "review", "demo", "interview", "planning"), company names in the title or attendees, and networking ("coffee", "intro", "catch up", "dinner").

Rank, never in calendar order: (1) events the owner organizes or presents, hosts or trains at, (2) events with external attendees from a client or prospect domain, (3) first occurrences of a series or first-time meetings, (4) all other external meetings, (5) internal recurring reviews and syncs last. Never drop a higher rank to fit a lower one. Every meeting the cap drops is listed with its rank, the owner's role and the attendees, never as a bare count. A meeting that already has a prep note (search its exact title) is counted as prepped and left alone.

## What a pack holds

The `meeting-prep` note sections (meeting, when and where, attendees with relationship, last interaction and key context, recent communications, open items, talking points), plus two:

- **What the owner owes them**: the owner's open promises and tasks toward these attendees or their company, each with its ref, from the follow-up lenses (the waiting-on tracker's lens D and the owner's own open tasks about them). "Nothing found" is said, never omitted.
- **The goal of this meeting**: one line, from the invitation, the thread that set it up or the last meeting's actions. "Not stated" when the record does not say; never invented.

The full layout is in `references/pack-template.md` inside this skill.

Every attendee line, every open item and every owed item carries a ref. Nothing private to another client and nothing from the owner's private notes goes in a note; the Portal is shared.

## The note

`create_note`, title exactly `Meeting Prep: <Meeting Title> - <yyyy-mm-dd>`, `note_type` `meeting-notes`, associated with the calendar event and each resolved attendee contact, ending with a `**Tags**: meeting-prep` line.

## DONE checklist

- [ ] Every external meeting of the day is prepped, already prepped, or listed as dropped by the cap or skipped with its reason.
- [ ] Every pack's owed items and attendee facts are in the record (checked).
- [ ] Every note written was read back with `get` and found by `search` on its exact title; a note not found by search is reported as a defect, with its id.
- [ ] No duplicate note: none written where one existed.
- [ ] Nothing was sent and no task was written.

## Shapes

`RUN/prep.json`:

```json
{"day": "2026-10-06", "dry_run": false,
 "meetings": [{"event": "portal://calendar_event/<id>", "title": "...", "time": "10:00",
               "rank": 2, "state": "prepped", "note": "portal://note/<id>",
               "found_by_search": true, "check": "PASS", "owed": 2, "goal_stated": true}],
 "dropped": [{"title": "...", "rank": 4, "owner_role": "attendee", "reason": "cap"}],
 "skipped": [{"title": "...", "reason": "personal"}],
 "questions": [], "notes": []}
```

The checker returns the `orchestration-workstream` block, one `items` row per pack: `test` `prep`, `item` the event ref, `state` PASS or FAIL, `note` the claim it could not find.

## Later tools

- `meeting-prep-pick`: the day's events, the ranking, the cap and the already-prepped check in code, before the session.
- `note-findable`: write-then-search verification of a note by title, in code.
