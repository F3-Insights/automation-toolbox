---
name: meeting-analyst-method
description: "Reference loaded by the meeting-analyst agent, not for a user request: the step-by-step procedure for reading one meeting transcript and proposing its record. Covers whoami first, the three ways to get the transcript (file, Fellow recording, calendar event) and reading all of it, classifying the meeting, matching attendees to Portal contacts, the summary by meeting-summary-style-guide, decisions with quoted evidence, action items with owner, due date, status and the existing-task check, and one line per person. Not for filing a meeting's notes by hand; use meeting-followup."
---

# Meeting analyst: the procedure

This is the procedure the `meeting-analyst` agent works through, in order, for one transcript. The agent file holds the goal, the judgment calls, the hard rules and the return format. A brief that fixes the return format replaces Step 1 and the return format; everything else here still holds.

## Steps

### Step 0: whoami

Call `whoami` first. You need `principal.timezone` to resolve relative dates ("next Tuesday") from the meeting's own date, and `principal.contact_id` to know which speaker is the owner. Every timestamp the Portal returns is UTC; convert with that zone, never with a guess. If `timezone_source` is `"default"` the zone is UTC and nobody set it: resolve no relative date and say why.

### Step 1: get the transcript

Three ways in, in the order you should try them.

1. **A file path from the caller.** `Read` it. Prefer a collapsed `MM:SS Speaker: text` transcript over a raw subtitle export; if both exist for the same meeting, read the collapsed one and say so.
2. **A Fellow recording id.** `get_fellow_recording(recording_id="<id>")` returns that exact stored transcript with its revision.
3. **A calendar event.** `get(entity_type="calendar_event", id_or_query="<id>", detail="raw")` returns the Fellow `transcript` with its speech segments. The event's `fellow` block also tells you `matched_by`: `ical_uid` means the recording carries this event's own object id and the match is a fact; `time_attendees` means the Portal matched on a window and a shared attendee, which is a good guess and not a fact. Say which you had.

If the caller gave you only a date or a title, `list_fellow_meetings(since="<ISO date>")` discovers stored transcripts, paged with `next_offset`. A recording with no `calendar_event_id` is unmatched; report that rather than guessing which meeting it was.

**Read the whole transcript.** Long ones arrive in chunks; read every chunk and reconcile across them. Corrections and the closing minutes are where commitments get revised, and a summary of the source is not the source. If you read only part of it, say which part and stop short of the sections you did not read.

### Step 2: classify the meeting

One line: what kind of meeting this was, from the evidence in the room rather than the calendar title. Client working session, internal status, discovery interview, sales or scoping call, board or committee meeting, one to one, training. The kind sets what the caller files it as, so justify it in half a sentence ("agenda walked a task list and three attendees reported status": internal status).

### Step 3: attendees

An invitation does not establish attendance. Someone attended if they spoke, or if the transcript records them arriving, being addressed, or being thanked for coming.

For each attendee, in a table: the name as the transcript gives it, what they are called in the Portal, the `_ref` of the matched contact, and the match confidence.

- Resolve with `search(query="<name>")` and confirm with `get(entity_type="contact", id_or_query="<id or email>")`. A name plus the company in the room is a confident match; a common first name alone is not.
- Mark every uncertain match **UNCERTAIN** with the reason and the candidates you found. Never pick one of two plausible contacts to make the table tidy.
- Mark a speaker with no Portal record **NOT IN PORTAL**. That is a finding for the caller, not a problem for you to solve.
- Say which speaker is the owner, and say if the transcript's diarisation was unreliable (crosstalk, "Speaker 3", audio flagged low confidence). A label you do not trust is worse than no label.

### Step 4: the summary

Load the `meeting-summary-style-guide` skill before you write the summary, every run, and follow its voice, structure and anonymization rules. You do not have persistent memory across calls; last time's reading does not carry over.

The summary is what mattered: status and findings, their consequences, and the next steps the room accepted. Distil and synthesize; never transcribe. Every material claim carries a timestamp or a short quote so the caller can check it against the source without reading the whole thing. Preserve the numbers, system names and dates exactly as spoken.

### Step 5: decisions

A decision is something the room settled. Separate it from the three things it is often confused with, and label each accordingly: a **proposal** nobody accepted, a **suspected cause** still being investigated, and an **unresolved fact** somebody has to go and check.

For each decision: what was decided, who decided it, what it changes, and the evidence, which is a contiguous verbatim quote of at most 25 words with its timestamp or turn number. A decision you cannot quote is not a decision; move it to inferred.

### Step 6: action items

For each one: the action, the owner, the due date, the status, and the evidence quote with its location.

- **Owner** is the person who accepted it. Agreeing to look into something is not agreeing to fix it: preserve the scope that was actually accepted. An explicit intention to get another party to do something is the speaker's own coordination action; do not transfer ownership to an unnamed department.
- **Status** is `accepted` (someone took it), `requested` (asked but not accepted, still worth recording as a request) or `proposed` (floated, no taker).
- **Due date** only where it was stated. Resolve a relative date only from the meeting's own date and the owner's timezone, and show your arithmetic in the report ("said 'end of next week' on 2026-09-17, so 2026-09-25"). Where no date was given, write `none stated`. Never invent one.
- Do not drop an accepted action because its owner, project or date is unknown. Record it with the gap named.
- Keep related but distinct actions separate; do not merge two commitments into one line.
- Before you propose a new task, check whether one already exists: `list_entities(entity_type="task", filters={"search": "<key words>", "include_completed": false})` and `search(query="<the deliverable>")`. Match on owner, deliverable and scope, not on title alone. Report each action as **new**, **update to `<task _ref>`** (say what changes), or **already tracked by `<task _ref>`**. A broader existing task can cover part of an action: document the overlap and the remaining scope rather than calling it either a duplicate or unrelated.

### Step 7: one line per person

For each attendee who is worth remembering, one line that will be useful the next time the owner meets them: what they care about, what they own, a constraint they named, a preference they showed, a commitment they made. Sourced like everything else. Skip anyone the meeting revealed nothing about rather than padding the list.

This is relationship context, not gossip. Write what you would be content for that person to read.
