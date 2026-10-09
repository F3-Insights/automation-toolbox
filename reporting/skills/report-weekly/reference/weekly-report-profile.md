# Weekly report profile

The role profile for one author's weekly report. Filled in once, in an interview, and reviewed every quarter. One document with twelve headed sections, so an executive can read and edit it and so it can live as a note wherever the organisation keeps its record.

**This is the only document the executive edits.** The report outline the pipeline sorts the week into is a projection of this file, not a second list to keep in step: `python3 ~/.claude/skills/report-weekly/scripts/report_profile.py show --outline` writes it, and `report-collect`, `report-organize` and `report-pack` take this file at `--outline-file` directly. Every heading below is read by code, so a relabelled one is a section nobody sets.

Describe every person by role. The only place a name belongs in this file is the optional `Names to roles` map, which exists so a sentence about a problem can carry the role instead of the person.

A blank form does not pass `python3 ~/.claude/skills/report-weekly/scripts/report_profile.py validate`, and should not: the tier, the seats and the review date are placeholders until somebody has answered for them.

Where the real profile lives: as a note titled `Weekly report profile` attached to the author's scope, so an assistant can edit it without touching a repository.

```
list_entities(entity_type="note", filters={"entity_type": "domain",
              "entity_id": "<the scope uuid>", "search": "Weekly report profile"}, limit=5)

create_note(title="Weekly report profile", content="<this form, filled in>",
            associations=[{"entity_type": "domain", "entity_id": "<the scope uuid>",
                           "is_primary": true}])
```

The run looks for that note first, then an older `Weekly report outline` note, and says which one it used. An older `Weekly report spec` note is no longer read: rewrite it as a profile (`weekly-report-spec.md` beside this file says what its fields meant).

## Author and organisation

Who writes this report, by role, and what the organisation does.

- Role: <the author's role, for example the controller>
- Organisation: <what the organisation does and roughly how large it is>

## Seats

One numbered item per seat: the seat's name, a colon, then one paragraph on what the position answers for. One person may hold two seats, and they share one report with a header per seat.

1. <Seat name>: <what this position answers for, in one paragraph>

## Leadership team

One item per member: their role and what they answer for. The audience test is run against this list, so an item earns its place in the report when one of these readers has to know it, has to decide something because of it, or is affected by it.

1. <Role>: <what this member answers for>

## Standing categories

The categories the week is sorted into, in the order the reader cares about, ending with `Other topics`. Between three and seven reads well; that is a range and not a rule. Write them from the job, not from last week's inbox. A category that exists because something happened once is a category that is silent for the next eleven weeks.

Three kinds, and every category is one of them:

- `operational`: a standing responsibility of the position, taken from what the job is. It appears every week whether or not anything happened. The month-end close, the forecast, the cash position, receivables. Warehouse output, safety, the delivery fleet.
- `project`: something the person leads or is involved in that has an end. A warehouse move, securing financing, kicking off the budget.
- `other`: **exactly one, always last.** The important smaller call-outs that belong to no category above.

**Signals** are what let code put a piece of evidence in a category rather than a model guessing. Six kinds, and a category may carry any of them. Titles and Subjects are regular expressions, matched case-insensitively against a task, note, project or meeting title and against a mail subject. Keywords are plain text, matched anywhere in the item including a note's body. Projects and Goals name a tracked project or goal, by name or by id. Counterparties are an email domain or a contact's role.

A keyword matches as a whole word or a whole phrase, case-insensitively and allowing a simple plural, so `invoice` matches "invoices" and no keyword is ever found inside a longer word. A keyword written in capitals is read as an acronym and matched case-sensitively, so `IT` never matches "it" and `AR` never matches "are" or "Shareables", while `tax` still matches "Tax".

**First match in category order wins.** An item goes into at most one category and the signal that matched is recorded beside it, so the order of the categories is their precedence: put the close above the forecast and a thread about the close forecast lands in the close. An item that matches nothing is unassigned and is never quietly folded into `Other topics`, because the size of the unassigned pile is the time-management signal the author is owed.

What the checker rejects outright: no category of kind `other`, more than one, or one that is not last; a category naming a seat this profile does not declare; a kind that is not one of the three; a signal pattern that is not a valid regular expression. A category with no signals is a warning rather than an error, because it will appear on the silent list every week, which may be exactly right for a responsibility nothing electronic ever touches.

Write nothing but the blocks below under this heading. A line that is not a bullet continues the bullet above it, so a paragraph after a block lands inside that block's Covers.

### <Category name>
- Seat: <one of the seats above>
- Kind: <operational for a standing responsibility, project for something with an end>
- Covers: <what this category covers, in one line>
- Signals:
  - Titles: `<a pattern matched against a task, note, project or meeting title>`
  - Subjects: `<a pattern matched against a mail subject>`
  - Keywords: `<plain text matched anywhere in the item>`
  - Projects: `<a project by name>`
  - Goals: `<a goal by name>`
  - Counterparties: `<an email domain or a contact's role>`
- Standing metrics:
  - <Metric name> from `facts:<key>`
- Owner: <the role of the direct report who owns this category>

### Other topics
- Seat: <one of the seats above>
- Kind: other
- Covers: important smaller call-outs that belong to none of the categories above.

## Standing metrics

One item per figure the report carries every week, with where the number comes from and how often it moves. The source is `facts:<key>` for a figure the facts set supplies, or `supplied by hand` for one the executive gives at a gate. The cadence is weekly, monthly, quarterly or annual. A figure with no value is reported as not available; nothing is invented.

1. <Metric name> from `facts:<key>`, weekly
2. <Metric name>, supplied by hand, monthly

## Direct reports

One item each: the role, what they report on, and where and when their weekly report arrives. Three arrival forms, because three are how a weekly update actually reaches somebody:

```
mail from `<an address or a domain>` with subject `/<a pattern>/i`
note titled `/<a pattern>/i`
file `<a glob under the directory the run names>`
```

1. <Role>, reports on <what they report on>; mail from `<address>` with subject `/<pattern>/i`

## Collection tier and scope signals

The tier is how the week is collected: `portal` reads it in code, `harvester` has a worker read the mail and calendar, `manual` uses the reports in a folder and the executive's own account. The scope signals are what say a meeting or a thread is this seat's at all.

- Tier: <portal, harvester or manual>
- Attendee domains: `<a domain the seat meets with>`
- Title patterns: `/<a pattern in this seat's meeting titles>/i`
- Mail terms: `<a term that marks this seat's mail>`

## Form rules

Length is a constraint and not a target. The cap is the hard stop.

- Length: <one page, 450 to 600 words>
- Hard cap: <two pages, 1,100 words>
- Deadline: <Friday> by <3 pm>
- Holiday rule: <what happens when the deadline day is a holiday>
- Materiality: <the amount below which a figure is not reportable on its own>

A filled-in line reads `Materiality: $10,000`. Anything still inside angle brackets is a placeholder and is read as no answer at all, which is what the brackets are for: an example amount left inside them would parse as a real threshold and the week's figures would be judged against a number nobody chose.

A smaller figure may still appear inside a pattern that carries its own count and total, so "eleven billing errors this quarter, $4,900 recovered" is reportable where "$81.40 recovered" is not. Materiality is optional: with none stated no figure is judged immaterial, every amount may stand on its own, and `report-verify` skips its IMMATERIAL_FIGURE check and says so.

Then one numbered item per rule about the shape of the document itself: what opens a bullet, where figures go, what is cut first and what is never cut. The writer is what reads these.

1. <a rule about the shape of the document>

## Names to roles

**Optional, and the one section that holds names.** A person may be named in the report for credit or for joint work: "working with the controller to resolve the billing reconciliation" is right, and a win names the people or the team who delivered it. A person is never named in a sentence that attaches them to a mistake, a delay, a gap, a failure or an unmet obligation. This map is what the writer substitutes from when it has to rewrite one of those sentences. With no map it drops the actor entirely, which is also correct, so leaving this out is a warning at validation and never an error.

1. <the name as it appears in the mail and the meeting invitations>: <their role>

## Delivery

- Recipients: <the roles the report goes to>
- Folder: <where the file is filed>

## Never published

The absolute exclusion list. Nothing here ever reaches the report, whatever else is true.

1. <what never appears in the report>

## Never recorded

What is redacted even from the stored record, so it is not kept for continuity or audit.

1. <what is never stored>

## Review date

Dates are written as `YYYY-MM-DD`, which is the only spelling this reads. The next review is three months after the last unless a date is written here.

- Last reviewed: <YYYY-MM-DD>
- Next review: <YYYY-MM-DD>
