---
name: meeting-prep
description: Prepares the context for one upcoming meeting (attendees, recent mail, notes and open tasks) from the Insights Portal and writes a prep note on the calendar event. Use before a meeting, or for "get me ready for my call with X". For all of a day's external meetings unattended, start meeting-prep-orchestrator; for a deep brief on one person, use the person-researcher agent.
argument-hint: '[meeting name, attendee, or company]'
allowed-tools: mcp__insights-portal__*, AskUserQuestion, Read
---

# Meeting Prep

Prepare comprehensive context for an upcoming meeting.

**User provided:** $ARGUMENTS

## Instructions

### Step 1: Clarify if Needed

If the user's input is ambiguous or could match multiple meetings, **ask for clarification first**:

- "I found 3 meetings today. Which one are you preparing for?"
- "Did you mean the 2pm call with Dana or the 4pm review meeting?"
- "I couldn't find a meeting matching that. Can you tell me more about it?"

### Step 2: Gather Context

Once you know which meeting, use `meeting_prep` for a comprehensive single-call prep brief. It accepts either an event UUID or a title or attendee substring, so the same call covers both a fuzzy search and a known event ID:

```
meeting_prep(event_id_or_query="[clarified search, or the event UUID if you already have it]")
```

This automatically fetches:
- Meeting details
- All attendee contacts with company context
- Recent emails with each attendee
- Related notes and tasks

### Step 3: Present and Offer More

After presenting the prep, **offer to dig deeper**:

- "Would you like me to pull up any specific email threads?"
- "Should I look up more context about [company name]?"
- "Do you want me to create a prep note to reference during the meeting?"

### Step 4: Take Action

Always write the prep note, whether or not anyone asked. When this skill runs headless (dispatched, with no interactive user present), Step 3's offers never fire, so a gated write means no note is ever created:

- Create a meeting prep note: `create_note(content="...", title="Prep: [meeting]", note_type="background", associations=[{entity_type: "calendar_event", entity_id: "<event_id>"}])`
- Then immediately verify it with `get(entity_type="note", id_or_query="<returned note id>")` and put the note id in the final output. If the write fails or the get finds nothing, say so plainly instead of reporting a prep note.

Before that write, load the portal-write-safety skill and follow it: propose by default, resolve entities by UUID never by name, `CANCELLED` with evidence never `DONE`, `sync_health` first. Propose by default applies when a user is present: show the note and write on confirmation. Headless runs (a scheduled calendar-prep run) write the note directly, because a proposal nobody sees is no note; the safety rules on UUIDs, status and `sync_health` still apply.

If the user asks, you can also:

- Pull more context: `get(entity_type="email", id_or_query="...")`
- Look up full contact context: `get(entity_type="contact", id_or_query="...")`

## Output Format

### Meeting Prep: [Title]
**When:** [Date/Time] **Where:** [Location]

---

**Attendees:**
- **[Name]** - [Title] at [Company]
  - Relationship: [context]
  - Last interaction: [date/type]
  - Key notes: [relevant info]

---

**Recent Communications:** [Summary of recent emails/activities]

---

**Things to Consider:** [Insights based on the gathered context]

---

*Would you like me to [suggested next actions]?*
