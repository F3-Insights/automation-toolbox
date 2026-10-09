---
name: portal-note-types
description: "Reference only, loaded by skills that write Insights Portal notes (comms-log-call, meeting-log, crm-contact-update, crm-data-review and the like), not for a user request: the four note types (background, episodic, meeting, research) with the structure of each, the content rules that make a note an executive summary rather than a transcript, and how to associate a note with its contacts, companies and projects."
user-invocable: false
---

# Portal note types

How to write a good note in the Insights Portal. Load `portal-write-safety` before the write itself.

## Core principle: executive summaries

Notes are intelligence, not transcripts. They capture key facts and decisions, actionable insights, business intelligence and relationship context.

Never include conversational filler ("Thanks!", "Sounds great!"), pleasantries and small talk, redundant information or raw unprocessed text.

## Note types

The types are fixed names; pass `note_type` directly on `create_note` as one of `background`, `episodic`, `meeting`, `research`. No lookup is needed.

### Background

**Purpose:** standing context about a person, company or topic. **Use when** building a profile, capturing general knowledge or recording preferences.

```markdown
## Overview
- [Key identifying facts]
- [Role, position, relationship]

## Key Details
- [Important preferences]
- [Communication style]
- [Decision-making patterns]

## Business Context
- [Company situation]
- [Industry position]
- [Current priorities]

## Relationship Notes
- [How we connected]
- [Shared interests]
- [Mutual connections]
```

Example:

```markdown
## Overview
- CEO of Northwind Traders since 2019
- Previously VP Operations at Fabrikam Logistics

## Key Details
- Prefers email over calls
- Available early mornings
- Direct communicator, values brevity

## Business Context
- Northwind: privately held distributor, expanding into a second region next year
- Main challenge: scaling the operations team

## Relationship Notes
- Met at an industry conference
- Both know Priya Shah (Acme Components)
```

### Episodic

**Purpose:** one event, milestone or decision at a point in time. **Use when** recording a call, an announcement or a decision.

```markdown
## Event: [What happened]
**Date**: [When]
**Context**: [Why it matters]

## Key Points
- [Major fact or decision 1]
- [Major fact or decision 2]

## Action Items
- [ ] [What] - [Who] - [When]

## Implications
- [What this means for the relationship or the business]
```

Example:

```markdown
## Event: Quarterly planning call
**Date**: January 11
**Context**: Quarterly alignment on project scope

## Key Points
- Approved a larger budget for Phase 2
- Launch moves from March to April
- Two dedicated people added

## Action Items
- [ ] Send the revised SOW - Me - Jan 15
- [ ] Confirm the staffing - Dana - Jan 12

## Implications
- Larger scope is a chance to expand the engagement
- The delay moves revenue out of Q1
```

### Meeting

**Purpose:** a meeting's record with attendees and outcomes. **Use when** writing up any significant meeting. A full meeting summary follows the `meeting-summary-style-guide` skill instead.

```markdown
## Meeting: [Topic]
**Date**: [When]
**Attendees**: [Who]

## Agenda / Topics Covered
1. [Topic 1]
2. [Topic 2]

## Decisions Made
- [Decision 1]

## Action Items
### My Tasks
- [ ] [Task] - Due: [Date]

### Waiting On
- [ ] [Person]: [What] - Expected: [Date]

## Key Insights
- [Insight about a person, company or opportunity]

## Next Steps
- [Follow-up meeting or action]
```

### Research

**Purpose:** analysis, findings and recommendations. **Use when** documenting research, a competitive analysis or a pass by an agent.

```markdown
## Research: [Topic]
**Date**: [When conducted]
**Sources**: [What was analysed]

## Key Findings
- [Finding 1]

## Analysis
[Interpretation of the findings]

## Recommendations
- [Recommendation 1]

## Open Questions
- [What still needs investigation]
```

## Content rules

Do:
- use bullet points for facts;
- include specific dates, numbers and names;
- extract what someone can act on, and note who said or decided what;
- capture the business implications;
- link the note to the entities it is about.

Do not:
- keep thanks, "sounds good" or enthusiasm markers;
- write in narrative or transcript form;
- repeat what another note already holds.

Bad (raw conversation): "Hey! Just following up on our chat. That sounds AMAZING! Let's definitely do it."

Good (extracted): "Follow-up on the partnership discussion. Positive reception to the proposal. Ready to move forward."

Bad (vague): "Had a good call with Sam. Discussed stuff. Will follow up."

Good (specific):

```markdown
## Call with Sam Ortiz (Lakeview Hardware, CTO)
**Date**: Jan 11

## Key Points
- Approved the integration approach
- Wants the proof of concept done by Feb 1
- Phase 1 budget agreed

## Action Items
- [ ] Send the integration specs - Me - Jan 13
- [ ] Schedule the technical deep-dive - Sam - week of Jan 20
```

## Associations

Associate every note with the entities it is about:

```python
create_note(
    content="...",
    title="...",
    note_type="...",          # background | episodic | meeting | research
    associations=[
        {"entity_type": "contact", "entity_id": "...", "is_primary": True},
        {"entity_type": "company", "entity_id": "..."},
        {"entity_type": "project", "entity_id": "..."}
    ]
)
```

The primary association is, in order of preference: the contact when the note is mainly about a person, the company when it is about an organisation, the project when it is about specific work.

## Where notes come from

- **After a call or meeting:** find the contact (`search`, or `get` with an id or email), write the note, log the activity (`create_activity` with `call` or `meeting`).
- **Background research:** read the contact (`get`) and its existing notes, then add to or update the background note rather than starting another.
- **An insight:** identify the entities, choose the type, write bullets, associate every entity it concerns.
