---
name: meeting-log
description: Logs that a meeting happened in the Insights Portal (an activity, a note when there is substance, unknown attendees offered as contacts, action items offered as tasks) from a short conversational capture. Use for "log my meeting with X" when you just need the record. Not for substantive notes and follow-ups (meeting-followup) or a phone call (comms-log-call).
argument-hint: '[meeting topic or attendee name]'
allowed-tools: mcp__insights-portal__*, AskUserQuestion, Read
---

# Log Meeting

Capture meeting details with structured attendee linking and action item extraction.

**User provided:** $ARGUMENTS

## Instructions

### Step 1: Identify the Meeting

If arguments provided:
- Search calendar for matching meeting: Use topic or attendee name to find the meeting
- `list_entities(entity_type="calendar_event", filters={since: "<today 00:00 ISO>", until: "<today 23:59 ISO>"})`
- Match by title, attendee name, or topic

If no arguments:
- Check today's calendar
- Ask which meeting to log (if multiple)

### Step 2: Get Attendee Context

Once the meeting is identified, use `meeting_prep` for comprehensive prep data. It accepts either an event UUID or a title or attendee substring, so the same call covers both cases:
```
meeting_prep(event_id_or_query="...")
```

This returns all attendee contacts with company context and recent emails in a single call.

Show brief attendee context:
```
Meeting: Quarterly Review with Acme Corp
Attendees found:
- Sarah Chen (VP Sales, Acme Corp) - last contact: 3 days ago
- Mike Johnson (CEO, Acme Corp) - last contact: 2 weeks ago
- Unknown: john.new@example.com (not in contacts)
```

### Step 3: Capture Meeting Details

Ask conversationally (not a rigid form):

1. **What was the main topic/outcome?**
2. **Key discussion points?**
3. **Action items?**
4. **Follow-ups needed?**

### Step 4: Create Records

Before any create/update call, load the portal-write-safety skill and follow it: propose by default, resolve entities by UUID never by name, `CANCELLED` with evidence never `DONE`, `sync_health` first.

1. **Create Activity** (always):
```
create_activity(
    activity_type="meeting",
    title="Meeting: [Topic] with [Primary Contact]",
    description="[Structured meeting summary]",
    contact_id="..." (primary contact),
    company_id="..." (if applicable),
    activity_date="[meeting time]"
)
```

2. **Create Note** (if substantial content):
```
create_note(
    title="Meeting notes: [Topic] - [Date]",
    content="[Structured markdown with attendees, discussion, decisions, action items]",
    note_type="episodic",
    associations=[{entity_type: "contact", entity_id: "..."}, {entity_type: "company", entity_id: "..."}]
)
```
The `portal-note-types` skill holds the structure of each note type.

3. **Handle Unknown Attendees**:
```
John New (john.new@example.com) isn't in your contacts.
Based on the meeting, they seem to be [role inference].
Add them? I'll link them to Acme Corp.
```

### Step 5: Extract Action Items

Parse action items from the conversation and offer to create tasks.

### Step 6: Confirm Capture

Show what was captured:
```
Meeting logged: "Quarterly Review - Acme Corp"

Created:
- Activity: Linked to Sarah Chen, Acme Corp
- Note: Full meeting notes with action items
- New contact: John New (Product Manager, Acme Corp)

Action items identified:
- 3 tasks for you (create them?)
- 2 items waiting on others

Anything to add or correct?
```

## Smart Behaviors

### Calendar Integration
- Look up actual meeting from calendar if available
- Pre-fill attendees from calendar event
- Use scheduled time for activity timestamp

### Action Item Patterns
Recognize:
- "I need to..." means a user action
- "They'll..." means a waiting-on item
- "We agreed to..." means a mutual commitment
- "By [date]..." means a deadline to extract

### Keep It Efficient
- Accept messy input, structure it in output
- Don't require every field
- Infer what you can from context
- Something captured > perfect capture
