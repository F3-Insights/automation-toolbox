---
name: meeting-followup
description: "Turns one meeting's notes or transcript, in any format (bullets, prose, a voice memo, pasted chat, a raw transcript), into everything that should follow it in the Insights Portal: an activity, a structured meeting note, matched or new contacts and companies, tasks for the owner's action items, approved contact updates and an optional follow-up draft in the owner's voice, behind one preview and one confirmation. Use after a meeting with substantive notes, for \"file my notes from the call with X and draft the follow-up\", and for messy notes from a meeting that is not on the calendar or has people not yet in the Portal. Not for a quick record (meeting-log) or a polished shareable summary (meeting-summary)."
argument-hint: '[meeting topic or attendee name, or paste notes/transcript, or describe the meeting]'
allowed-tools: mcp__insights-portal__*, AskUserQuestion, Task, Read, Bash
model: opus
---

# Meeting Follow-up

Richer post-meeting capture than `/meeting-log`. Takes notes or a transcript in whatever shape the owner has them and produces the full downstream fan-out: activity record, structured meeting note, contacts and companies matched or created, tasks for action items, contact updates when warranted, and an optional voice-matched follow-up draft via the `email-drafter` subagent. It works with or without a calendar event: a meeting that is not on the calendar, or that brought in people and companies not yet in the Portal, takes the off-calendar path in Step 1 and the matching in Step 3.

**Relationship to `/meeting-log`:** use `/meeting-log` when you just need to log that a meeting happened. Use `/meeting-followup` when you have substantive notes and follow-ups to issue in one pass.

**User provided:** $ARGUMENTS

## Instructions

### Step 1: Resolve the Meeting

If `$ARGUMENTS` contains a topic or attendee name:
```
meeting_prep(event_id_or_query="<topic or name>")
```

This single call resolves the meeting (by title or attendee substring, or event UUID) and returns attendee context and related notes and tasks.

Prefer recent meetings (today or within the last 2 days). If multiple candidates, ask which one.

If `$ARGUMENTS` is clearly a pasted transcript/notes (multi-line, >200 chars), treat the whole input as the meeting content and ask:
> Which meeting do these notes belong to? Today's calendar: [list external meetings]

If `$ARGUMENTS` is empty, ask which meeting and request the notes ("Paste your meeting notes or describe what happened"; messy is expected).

**Off-calendar path.** When no calendar event matches (a hallway conversation, a call that was never booked, a meeting on someone else's calendar) or the owner says there is none, carry on without an `event_id`: take the date and time from the notes or ask, and resolve the attendees from the notes in Step 3 instead of from `meeting_prep`. No step below depends on an event; the activity simply carries the meeting time given.

Once resolved, you have: `event_id`, attendees (with contact IDs), and meeting metadata from the `meeting_prep` call above (or, on the off-calendar path, the date and the names in the notes).

### Step 2: Accept the Notes

Ask (or receive from `$ARGUMENTS`):
> Paste the notes or transcript.

Do not require a specific format. Recognize the input type and handle each the right way:
- **Bulleted notes**: extract directly
- **Prose or stream of consciousness** (a transcribed voice memo, a narrative): parse for entities and actions
- **Raw transcript** (speaker-tagged or not) or **pasted chat log**: identify the speakers and summarize the dialogue
- **Mixed**: handle each section by its own type

If it's a transcript, summarize into structured notes before proceeding. Use your judgment: 2-3 paragraphs capturing topics, decisions, and action items. Do NOT transcribe verbatim.

Whatever the format, pull out: **attendees** (names, email addresses, roles, company references), **topics discussed** (subjects, problems, solutions), **decisions made** (explicit decisions, agreements, approvals), **action items** (for the owner, for others, deadlines), **follow-ups** (future meetings, documents to share, people to loop in) and **key insights** (business intelligence, preferences, relationship dynamics).

### Step 3: Match People and Companies

Attendees that came back from `meeting_prep` with contact IDs are already resolved. For every other person the notes name, and for every company, run `search(query="<name>")` (contacts and companies both rank in the results). For richer context on a key attendee: `get(entity_type="contact", id_or_query="...", detail="summary")`.

- **Confident match**: use it without asking.
- **Several matches**: ask which one.
- **No match**: propose creating the contact or company; it goes in the preview (Step 7) with the fields the notes give, never created silently.

### Step 4: Parse Action Items Deterministically

When a deterministic action-item parser is installed (a pattern-based extractor of action items and deadline phrases), run it over the notes first: it hallucinates less than model-only parsing.

Then layer your own judgment on top, because a pattern pass misses nuance (implicit commitments, sub-tasks). Without a parser, do the extraction yourself in two passes: explicit markers first ("I'll", "will send", "action:", a name followed by a commitment, a date phrase), then the implicit ones. Merge the two passes into a single deduplicated list with:
- `text` (the action description)
- `owner` (`me` / `them` / `mutual`)
- `deadline` (raw phrase if present, normalized to an ISO date)
- `priority` (P1-P4; default P3 if nothing hints otherwise)
- `assignee_contact_id` (if owner=them, resolve via attendees list)

### Step 5: Detect Contact-Worthy Updates

Scan the notes for signals a contact record should change:
- Role/title changes ("Sarah's been promoted to SVP")
- Company moves ("Michael's at a new firm now")
- Relationship shifts ("She'll be our primary POC going forward")
- Priority-level signals ("we should treat them as a VIP from now on")

If any detected, flag them for the preview (Step 7); do NOT apply silently.

### Step 6: Decide Whether a Follow-up Draft Is Warranted

A draft is warranted when the notes imply:
- An explicit commitment to send something ("I'll send the proposal")
- A thank-you opportunity (external meeting, new intro, significant ask)
- A summary/recap that closes the loop for the other party

Skip the draft when:
- Internal team meeting with no outside attendee
- Notes explicitly say "no follow-up needed"
- A draft already exists in the Portal for this thread (check `list_entities(entity_type="draft", filters={"status": "draft"})`)

### Step 7: Preview Everything, Confirm Once

Before building it, check for existing meeting notes on the same date with the same attendees. If one exists, ask once: "You have notes from a meeting with Sarah on this date. Add to those instead?"

Show a single consolidated preview (an invented example):

```
**Meeting:** Q2 Planning with Acme Corp (Sarah Chen, Michael Jones), Apr 19, 10am

**Will create:**
- Activity: meeting record linked to Sarah, Michael, Acme Corp
- Note (type=meeting): structured summary with topics, decisions, action items
- 3 tasks (your action items):
  1. P2 | Send pricing proposal | due Apr 23 (by Friday)
  2. P3 | Schedule next check-in | due Apr 26 (next Wednesday)
  3. P3 | Loop in legal on MSA | due Apr 30
- 2 waiting-on items (logged in note, no task created): Sarah's team reviewing SLA; Michael approving budget
- Contact update: **Sarah Chen** title to SVP Sales (promoted per notes)
- New contact: **Dana Ruiz**, Operations Director, Acme Corp (not in the Portal; named in notes)

**Follow-up draft:** yes: thank-you + recap + pricing proposal commitment, to Sarah

Proceed? (yes / edit / skip items)
```

Accept edits as natural language ("drop task 3", "skip the draft", "change Sarah's title to VP Enterprise instead").

### Step 8: Execute

On confirmation, execute in this order:

0. **New contacts and companies** the owner approved: `create_company` first, then `create_contact` linked to it, so the records below can carry their IDs.
1. **Activity**: `create_activity(activity_type="meeting", title=..., description=<summary>, contact_id=<primary>, company_id=..., activity_date=<meeting time>)`
2. **Meeting note**: `create_note(note_type="episodic", title="Meeting: <Topic> - <date>", content=<structured markdown>, associations=[{entity_type: "contact", entity_id: ...}, {entity_type: "company", entity_id: ...}, {entity_type: "project", entity_id: ...} (if applicable)])`. Markdown template:
   ```
   # Meeting: <Topic> - <Date>

   **Attendees:** <list with roles>
   **Duration:** <if known>

   ## Discussion
   <2-4 paragraphs, bold lead phrases>

   ## Decisions
   - <decision 1>
   - <decision 2>

   ## Action Items
   **Mine:**
   - [ ] <action> (due <date>) [P2]

   **Waiting on:**
   - <name>: <action>

   ## Open Questions
   - <question>
   ```
3. **Tasks**: one `create_task` per action item where `owner=me`. Link `project_id` if a project is associated. Set `priority` and `due_date` from parse results.
4. **Contact updates**: if user approved, `update_contact` for each; always pair with a `create_note(note_type="episodic")` explaining why.
5. **Follow-up draft**: if user approved, spawn `email-drafter`:
   ```
   Task(
       subagent_type="email-drafter",
       description="Meeting follow-up draft",
       prompt="""
   Draft a follow-up email in the owner's voice for the meeting below.

   Recipient: <primary external attendee, name + email>
   Intent: Thank them for the meeting; recap the key decisions; confirm commitments the owner made; propose/confirm next step.

   Source material (pasted for reference, do not quote verbatim):
   <meeting summary + the owner's action items>

   Follow your standard process: read the owner's voice guide (setting `voice_guide`), sample recent sent
   emails to this recipient, draft, voice-check, create via draft_create (pass
   related_email_id if this follows up a specific email), return summary.
   """
   )
   ```

### Step 9: Summary Card

End with a single summary:

```
**Captured: Q2 Planning with Acme Corp**

- Activity logged (linked to Sarah Chen, Michael Jones, Acme Corp)
- Meeting note created (id: n_123)
- 3 tasks created (ids: t_201, t_202, t_203)
- Contact update: Sarah Chen to SVP Sales (note: n_124)
- New contact: Dana Ruiz (id: c_310), linked to Acme Corp
- Follow-up draft: d_456, review in the Portal
```

## Smart Behaviors

- **One confirmation, not many**: never ask for per-item confirmation. Show the whole plan, get one "yes", execute.
- **Deterministic parsing first**: when an action-item parser is installed, run it for action items and date normalization before layering model judgment.
- **No silent contact writes**: contact changes always appear in the preview and require explicit approval.
- **Delegate voice work**: the `email-drafter` subagent handles the draft; this skill never writes email body content inline.
- **Format is never the owner's problem**: bullets, prose, voice memos, chat logs and transcripts are all accepted as they come.
- **No silent creates**: new contacts and companies appear in the preview like contact updates.
- **No duplicate notes**: an existing note for the same meeting is offered for appending before a new one is made.
- **Project inference**: if the meeting clearly maps to a project (calendar title match, attendees match the project's key contacts), link the note and tasks to the project automatically.
- **External-only drafts**: never generate a follow-up draft for internal-only meetings.

## Reuses

- `meeting_prep`: meeting resolution and attendee context in a single call
- `search` and `get`: attendee and company matching when there is no event or a name is new
- An action-item parser and date normalizer, when installed: deterministic extraction
- The `email-drafter` agent: voice-matched draft generation
- The Portal's note structure conventions

## Key Rules

- **Never impersonate**: drafts only, reviewed in the Portal.
- **One pass, one preview, one confirmation**: this is a fan-out skill, not a conversation.
- **Honor the voice guide** via the `email-drafter` agent; do not inline draft any email body in this skill.
- **Portal write safety**: before any create/update/draft call in Step 8, load the portal-write-safety skill and follow it (propose by default, resolve entities by UUID never by name, `CANCELLED` with evidence never `DONE`, `sync_health` first).

## Relationship to quick capture

For quick, unstructured input, a quick-capture skill routes it. Use this skill when there is substantial meeting content, several attendees to link, or structured extraction is needed: quick capture for speed, this skill for depth.
