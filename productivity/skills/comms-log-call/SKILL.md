---
name: comms-log-call
description: Quickly log a phone call in the Insights Portal as an activity and a note, and offer tasks for its follow-ups. Use right after a call, with the person's name or company, for "log my call with X". Not for a meeting; use meeting-log, or meeting-followup when there are notes and follow-ups.
argument-hint: '[person name or company]'
allowed-tools: mcp__insights-portal__*, AskUserQuestion, Read
---

# Log Call

Quickly capture a phone call interaction.

**User provided:** $ARGUMENTS

## Instructions

### Step 1: Identify the Contact

If user provided a name/company in arguments:
- Search for matching contact: `search(query="$ARGUMENTS")`
- If multiple matches, ask which one
- If no matches, offer to create new contact

If no arguments provided:
- Ask: "Who did you speak with?"
- Then search/match

### Step 2: Get Call Context

If contact found, pull their context in one hydrated call:
```
get(entity_type="contact", id_or_query="...", detail="summary")
```

Show brief context:
```
Found: Sarah Chen, VP Sales at Acme Corp
Last interaction: Email 3 days ago about Q2 proposal
```

### Step 3: Capture Call Details

Ask these questions (but keep it conversational, not a rigid form):

1. **What was discussed?**
   - Let them give a brief summary
   - Don't need every detail

2. **Any action items?**
   - Things they need to do
   - Things you committed to

3. **Anything important to remember?**
   - Insights, preferences, personal details
   - Future opportunities or concerns

### Step 4: Create Records

Before any create/update call, load the portal-write-safety skill and follow it: propose by default, resolve entities by UUID never by name, `CANCELLED` with evidence never `DONE`, `sync_health` first.

Based on the conversation:

1. **Create Activity**:
```
create_activity(
    activity_type="call",
    title="Call with [Name]",
    description="[Summary of discussion]",
    contact_id="...",
    company_id="..." (if applicable)
)
```

2. **Create Note** (if substantial content):
```
create_note(
    title="Call notes: [Name] - [Topic]",
    content="[Detailed notes]",
    note_type="episodic",
    associations=[{entity_type: "contact", entity_id: "..."}]
)
```
(`note_type` is one of the four fixed names: background, episodic, meeting, research; "episodic", a dated interaction record, fits call notes. The `portal-note-types` skill holds each type's structure.)

3. **Mention follow-up tasks**:
   - If action items mentioned, remind user they can create tasks
   - "Want me to create tasks for: [action items]?"

### Step 5: Confirm

Show what was captured:
```
Logged call with Sarah Chen (Acme Corp):
- Activity: "Call with Sarah - Q2 expansion discussion"
- Note: Added details about their timeline concerns
- Updated: Last activity date for Sarah

Any follow-up tasks to create?
```

## Handling New Contacts

If contact doesn't exist:
```
I don't have a contact record for "John at TechCo".
Want me to create one?

I'll need:
- Full name
- Email (if you have it)
- Company (I can look up TechCo)
```

## Keep It Fast

The goal is **minimum friction** for maximum capture:
- Accept brief answers
- Don't demand every field
- Something logged is better than nothing
- Can always enrich later
