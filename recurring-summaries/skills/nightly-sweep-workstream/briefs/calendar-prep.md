# Brief: phase 4, prepare the next day's external meetings

## The question

Which meetings of the day after the swept date need a prep note, and what should each note say? The scheduled sweep runs just after midnight for the day that just ended, so that next day is today, which has just started; a daytime run of today preps tomorrow. Either way it is `next_day`. You rank, gather context and write the notes' content; the finish step creates them, through `sweep-apply`, after the session. You never ask anyone anything.

## The inputs

- The date, `next_day` and its calendar window (`next_day`'s local midnight to the next, as UTC instants), all from `sweep-dates`.
- The path of `rules.md` in this skill's folder. Read "Calendar prep (phase 4)" first.
- Your turn budget: 30 turns. Keep the last 3 for the return.

## What to do

1. List `next_day`'s events with the window exactly as given: `list_entities(entity_type="calendar_event", filters={"since": "<window since>", "until": "<window until>"})`. Never pass `<next_day>T00:00:00Z`: for an owner west of UTC that UTC window starts the previous afternoon and ends before the day's evening events, so they are missed. Events that already started before the run are still prepped: just after midnight none has.
2. Zero-result guard: a weekday with `total: 0` is not trusted. Run the same query once more, or with `event_kind: "meeting"`; the Portal has returned an empty window mid-sync while `get` and `meeting_prep` still found the events.
3. Classify each event. SKIP: personal ("lunch", "gym", "dentist", "doctor", "personal", "block", "focus time", "commute", "pickup", "dropoff", "kid", "family"), internal recurring ("standup", "team sync", "1:1" with internal people, "all-hands"), no external attendees and a generic title, cancelled. PREP: external attendees (another email domain), business meetings ("call", "sync", "review", "demo", "interview", "planning"), company names in the title or attendees, networking ("coffee", "happy hour", "intro", "catch up", "dinner").
4. Rank every PREP event with the five ranks in `rules.md` and keep the top 5. List each one the cap dropped under `skipped` with its rank, the owner's role and the attendees.
5. For each kept event, `meeting_prep(event_id_or_query="<event id>")`. When it comes back thin, `get(entity_type="contact", id_or_query="<attendee>", detail="full")`.
6. Check for an existing prep note: `search(query='"Meeting Prep: <Meeting Title> - <next_day>"')` and look for that exact title among the notes. When one exists, count it as already prepped and propose nothing for it.
7. Propose one `create_note` per remaining event, titled exactly `Meeting Prep: <Meeting Title> - <next_day>`, `note_type` "meeting-notes", associated with the calendar event (and the attendees' contacts you resolved), with the content below.
8. Return the block below.

## The prep note

```markdown
## Meeting: <Title>
**When**: <local time>
**Where**: <location or link>

### Attendees
- **<Name>**, <title> at <company>
  - Relationship: <how the owner knows them, priority>
  - Last interaction: <date, kind, one line>
  - Key context: <relevant notes, open items>

### Recent communications
- <recent threads or activities with the attendees>

### Open items
- <pending tasks about the attendees or their companies; unanswered mail; commitments>

### Talking points
- <topics from the context, questions from open items, follow-ups from last time>
```

## The return format

Your final message is exactly one fenced JSON block, and nothing after it:

```json
{"phase": 4, "date": "2030-03-04", "next_day": "2030-03-05",
 "writes": [
  {"kind": "create_note", "key": "prep:<event id>", "title": "Meeting Prep: Q4 planning - 2030-03-05",
   "content": "## Meeting: Q4 planning\n...", "note_type": "meeting-notes",
   "associations": [{"entity_type": "calendar_event", "entity_id": "<uuid>"},
                    {"entity_type": "contact", "entity_id": "<uuid>"}]}],
 "events": {"total": 7, "skipped": 3, "prep_proposed": 3, "already_prepped": 1},
 "prepped": [{"event_id": "<uuid>", "title": "Q4 planning", "time": "10:00", "attendees": ["..."],
              "key_context": "<one line>"}],
 "skipped": [{"title": "Gym", "reason": "personal"},
             {"title": "Vendor sync", "reason": "dropped by the 5-meeting cap", "rank": 4,
              "owner_role": "attendee", "attendees": ["..."]}],
 "for_owner": ["<one line per meeting dropped by the cap that the owner organizes or presents>"],
 "errors": []}
```

You may propose only `create_note`; `sweep-apply` refuses a plan holding anything else. When you cannot do the phase, return instead:

```json
{"phase": 4, "date": "2030-03-04", "status": "BLOCKED", "reason": "<one line>"}
```
