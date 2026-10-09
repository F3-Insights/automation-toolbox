# Weekly report spec

The contract a scope once carried for its periodic report. One spec per domain, and optionally one per project or goal that got its own report. No script reads its delivery or cadence fields: delivery now comes from the role profile's **Delivery** section (recipients and folder), which the digest prints and the admin carries out by hand at Step 16, and the deadline from the profile's **Form rules**; the profile projects these into the outline's Delivery and Cadence lines, which the digest prints for the writer's covering note.

**No command reads this format any more.** `report-collect` looks for a `Weekly report profile` note, then a `Weekly report outline` note, and `report-pack` no longer falls back to a `Weekly report spec` note or to this file. The format is kept so an old spec note can be read and rewritten as a role profile (`weekly-report-profile.md` beside this file). Where this file says what "the pack" or "the report" does with a field, it describes the old behaviour.

When it was read, the spec note was parsed into fields by their labels, so every label was spelled exactly as the table below spells it, in one of the forms the worked examples use (`- **Field.** text`, `**Field**: text`, `## Field` or `Field: text`). A relabelled field was not read at all: it fell back to this file's own guidance for that field, and the pack recorded the fallback.

Two different readers want two different documents. An operating update written inside one company and a client engagement update for a consulting project share almost no sections, and that is the point of a per-scope spec rather than one house format.

## Where the real spec lives

The spec for a real scope lives **in the Portal**, as a note attached to that domain and titled `Weekly report spec`, so an assistant can edit it without touching this repository. This file is the default, used only when no such note exists, and a report written from the default says so on its first line.

Find it:

```
list_entities(
    entity_type="note",
    filters={
        "entity_type": "domain",
        "entity_id": "<the domain uuid>",
        "search": "Weekly report spec",
    },
    limit=5,
)
```

The `note` filter set is exactly `{entity_type, entity_id, note_type, search, since}`. An unknown key is an error rather than a silent drop, so a listing that came back is a listing that was filtered. Confirm the title before using a hit: `search` matches the body as well as the title, so a note that merely mentions the phrase can come back. Where more than one matches, take the most recently updated and say in the report that there were several.

Create one:

```
create_note(
    title="Weekly report spec",
    content="<the filled fields below>",
    associations=[{"entity_type": "domain", "entity_id": "<the domain uuid>", "is_primary": true}],
)
```

Scoping the report to a project or a goal instead uses the same note title with `"entity_type": "project"` or `"entity_type": "goal"` and that entity's id.

## The fields

The first nine fields are required. A spec that leaves one out is filled from this file for that field alone, and the report says which fields fell back. **Meeting signals** and **Meeting categories** are optional and have no default: without the first, the report's time section falls back to a best-effort count; without the second, it gives one hours total and no breakdown.

| Field | What to write |
|---|---|
| **Audience and recipients** | Who reads it, their role, and the named recipients if it is delivered to people. One line. |
| **Purpose** | One sentence. What the report is for. A section that does not serve it gets cut when the length binds. |
| **Sections** | The sections in order, one line each on what belongs there. These become the report's headings verbatim. |
| **Length** | A word count or a page count, and what to cut first when it binds. |
| **Tone** | How it reads, in a sentence, with an example phrase that belongs and one that does not. |
| **Never appears** | The absolute exclusion list. Internal notes, other clients, margin, unratified numbers, anything else. |
| **Sources** | Which sources to emphasise and which to ignore, from goals, projects and tasks, notes and meetings, calendar, received mail. |
| **Delivery** | A Portal note, a file at a path the owner names, an email draft to named recipients, or a combination. |
| **Cadence** | How often, and on what day. This is what tells a reader which period they last saw. |
| **Meeting signals** *(optional)* | How to recognise this scope's meetings: the counterpart's email domain, a title pattern, or both. A calendar event carries no domain in this Portal, so this is the only thing that lets `calendar-time` report hours for the scope instead of a best-effort count. |
| **Meeting categories** *(optional)* | What to split those hours into: a category name, then the title patterns that belong to it, one entry per category. |

**Meeting signals** is written as an email domain, a title pattern, or both, for example `domain: fabrikam-logistics.example` and `title: /fabrikam|slotting/i`. A pattern carrying a backslash reads better in plain backticks, `` Title pattern `\bpick path\b` ``, and both forms are parsed. The skill passes them to `python3 ~/.claude/skills/calendar-steward-method/scripts/calendar_time.py --scope-domain` and `--scope-title`; without them it falls back to a title match on the scope's short name and says so. The match is a heuristic either way, and what it measures is meeting time, not working time.

**Meeting categories** is written as `Name: pattern, pattern`, one entry per category, either on one line or as a nested list:

```
- **Meeting categories.**
  1. Close: `close`, `month end`, `flux`
  2. Client work: `review`, `workshop`
  3. Internal: `standup`, `one to one`
```

The first category whose pattern matches a meeting's title wins, so the field's order is its precedence, and a meeting matching none is reported as uncategorised.

A field written as a nested numbered or bulleted list is read item by item, so **Sections** and **Meeting categories** can both be laid out that way. For **Sections**, the heading is the text before the first colon, or before the first full stop where the item carries no colon, and the rest of the item is the guidance for what belongs under it.

## Worked example one: executive operating update

For an executive writing inside one organization. The reader is the operator, not a client, and the report is internal to that company.

- **Audience and recipients.** The chief executive and the two other members of the leadership team at Northwind Logistics. Delivered to them by name, read before the Monday leadership meeting.
- **Purpose.** Tell the leadership team where the month stands against plan and what needs a decision this week.
- **Sections.**
  1. Results against plan. Revenue, gross margin and operating expense for the month to date against budget, with the two largest variances explained.
  2. Cash. Balance, the next four weeks of expected receipts and payments, and the date of the tightest point.
  3. Close status. Which close steps are done, which are open, and what is blocking any that have slipped.
  4. Board and compliance calendar. What falls in the next thirty days, with owners.
  5. Decisions needed. Numbered, each one a question with the options and a recommendation.
- **Length.** Between six hundred and nine hundred words. Cut the calendar section first, then the explanations under the variances, never the decisions.
- **Tone.** Operator to operator, factual, no hedging on settled numbers. "Gross margin came in at thirty one percent against a plan of thirty four, and the gap is entirely freight" belongs. "We are pleased to report continued strong performance" does not.
- **Never appears.** Anything from another organization the author serves. Individual salaries. Numbers that have not been through the close, unless they are labelled preliminary in the same sentence.
- **Sources.** Emphasise goals with a financial target, the close project's tasks and notes, and the board and audit calendar. Ignore routine internal scheduling mail.
- **Delivery.** A Portal note on the domain, plus an email draft to the three named recipients. Nothing is sent by the automation.
- **Cadence.** Weekly, Sunday evening, so it is waiting before the Monday meeting.
- **Meeting signals.** Domain `northwind-logistics.example`. Title pattern `/northwind|leadership|close/i`.

## Worked example two: client engagement update

For a consulting engagement. The reader is the client sponsor, the document is work product, and it may be forwarded inside the client's organisation.

- **Audience and recipients.** The engagement sponsor at Fabrikam Logistics, who forwards it to their own leadership. Written to survive being forwarded without the owner present.
- **Purpose.** Show the sponsor what moved on the statement of work this week and what the engagement needs from them next.
- **Sections.**
  1. Progress against the statement of work. Each workstream, one short paragraph, where it stands against the scoped deliverable.
  2. Delivered this period. What was handed over, with the date and who received it.
  3. Next period. What will be done, with dates.
  4. Needed from the client. Owner by name, the specific ask, and the date it is needed by.
  5. Risks. Only the ones that change a date or a deliverable, each with what is being done about it.
- **Length.** One page, four hundred to six hundred words. Cut the risk detail first, never the asks.
- **Tone.** Matter of fact and consultative. State what was done, not how it is going. "Completed the pick-path study for both warehouses" belongs. "Great progress this week, we are on track" does not. The phrase list in the `comms-client-status-update` skill is the reference for this voice.
- **Never appears.** Internal notes about the client's staff. Anything from another organization the author serves. Fees, margin or the author's own hours. Findings that have not been walked through with the sponsor first.
- **Sources.** Emphasise the engagement project's tasks and notes, meeting notes from the period, and received mail from the client's team. Ignore the owner's internal goal hierarchy, which is not the client's business.
- **Delivery.** A file written to the engagement folder at a path the owner names, plus an email draft to the sponsor. The owner reviews and sends.
- **Cadence.** Weekly, Friday afternoon.
- **Meeting signals.** Domain `fabrikam-logistics.example`. Title pattern `/fabrikam|slotting|pick path/i`.

## Notes for whoever fills this in

Write the exclusion list first. It is the field that most often turns a usable report into one that cannot be sent, and it is the field people leave until last.

Name the sections for their content rather than their function. "Slotting findings" tells a reader what is under the heading; "Analysis" does not.

The sections field is the one the reporter follows literally. If a section is not in the list, it does not appear in the report, however interesting the material.
