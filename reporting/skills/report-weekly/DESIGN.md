# Weekly report: design record

This is the process the weekly report follows, stated before any tool or system is named. `SKILL.md` is the procedure; this file is why it has that shape.

## What it is

One department head gives the rest of the leadership team an executive update. A dense one-pager, two pages at most: a header per area, bold-labelled bullets, tight tables for numbers, no filler. It is published as a Word or PDF file, normally by email, and sent by the author, never by the system.

## Principles

1. **Start from responsibility, not from data.** The outline is what the position answers for: operational responsibilities, projects led, and a final Other topics for reportable items that do not earn a category. Three to seven categories.
2. **The executive decides what matters.** The system owns recall and arithmetic. The gates exist because the data cannot say what the week was about.
3. **No number is ever produced by a language model.** Every figure comes from a named source through a deterministic routine, with an as-of date and a status of preliminary or final. The model explains figures. A figure that is not available is reported as not available.
4. **Every statement traces to evidence.** The evidence sits behind the document, not in it.
5. **Every report answers the last one.** A problem, a pending decision or a dated expectation in a prior report carries forward until the report says what happened.
6. **Noise is shown to the author, not the audience.** What matched no category is a time-management signal.
7. **The form is fixed and dense.** Length is a constraint, not a target.
8. **Publishing and record-keeping are separate.** The file goes to the team. The facts, the evidence, the gate answers and the final text are kept for continuity and audit.
9. **Stages connect through contracts, and sources plug in as adapters.** The process does not depend on any one work tracker, mail system or ledger.
10. **Nothing leaves without the author's approval.**
11. **Judgment happens in three places:** choosing what matters (the executive), explaining why (the model drafts, the executive confirms), and wording. Everything else is code.
12. **The unit is an author at an organisation.** Two seats at one company make one report.
13. **The audience sets the bar, not the author's activity.** The reader is the leadership team, so every candidate item is tested with one question: what would a member of the leadership team think is important here? An item earns its place when a reader has to know it, decide something because of it, or is affected by it: money that is material, a risk or an exposure, a decision needed from the team, a commitment made to or by them, an effect on another department, a customer or partner consequence, a date that binds others. Work that matters only inside the department stays in the department's own more detailed report, which is exactly what the cascade is for. How busy the author was is never a reason to include something.

    Above those reasons sits one test with three axes: is it significant by **risk**, by **dollar value**, or by **importance to the business**? An item clearing none of the three is left out whatever its evidence weight, and the audience editor names on every Keep line which axis it cleared. The materiality threshold quantifies the second axis and only the second.

    A **win** earns a bullet on the same terms as a risk: something completed, secured, delivered, resolved or improved that the leadership team benefits from knowing, with its size or its effect. Kudos are a legitimate element of this report rather than a softener bolted onto it.

    **Credit by name, never blame by name.** A person may be named for credit or for joint work, and a person is never named in a sentence that attaches them to a mistake, a delay, a gap, a failure or an unmet obligation: there the event is stated without the actor, which is always possible, or the role or the team is named instead. Organisation, vendor and product names are unaffected. It is a political question rather than a stylistic one, which is why it is settled here once and checked by `PERSON_BLAMED` rather than left to the week. **Bad news is phrased with care** for the same reason: the event and its effect rather than a culprit, the status and the next step in one bullet, the factual state rather than the fault verb, the magnitude given, and never the report as the place where another department first learns of something affecting it.

    The bar is written once, in the house style template, as "What earns a bullet" and "What is never a bullet"; the audience editor applies it selecting and the writer applies it wording, and both carry the short form and point at the file. **Nothing in it deletes an item.** A rule here either stops the writer wording something as activity, or raises a finding for the executive to overrule at Gate 3. The verifier reports and never rewrites. Without the bar written down, a sound pipeline still fills half the page with meeting hours, the state of a work tracker's rows, the author's own waiting list and figures too small to matter.

## Process

| # | Stage | Who | In and out |
|---|---|---|---|
| 0 | Role profile, set once and reviewed quarterly | Executive | Seats and responsibilities, audience, categories, standing metrics and their sources, direct reports, form rules |
| 1 | Collect | Code, through adapters | Work tracker, calendar, mail, direct reports' reports, and the report ledger, into an evidence ledger |
| 1F | Tables and figures, a separate subroutine | The executive supplies, code stores | A table the executive hands over, stored verbatim, and any figure, each with a source, an as-of date and a status |
| 2 | Organise | Code | Evidence by category, ranked; carry-overs; silent items; Other candidates; the noise report |
| 3 | Gate 1 | Executive | Confirms this week's categories, adds what was missed, keeps or strikes Other candidates |
| 4 | Gate 2 | Executive | Updates on silent items; missing figures supplied, or accepted as not available |
| 5 | Draft | Model for prose, code for tables | Confirmed outline, evidence and facts into a draft |
| 6 | Verify | Code | Traceability, figures tie to facts, carry-overs answered, form, length, exclusions |
| 7 | Gate 3 | Executive | Edits and approves |
| 8 | Publish | Code renders, executive sends | Word or PDF file, and an email draft to the team |
| 9 | Record | Code | Final text, facts, evidence and gate answers stored; next week reads them |
| 10 | Learn | Code proposes, executive approves | Gate 3 edits and gate answers into outline and style changes |

Stage 1F runs on its own clock with its own tie-out. The report consumes what 1F holds as of the cutoff, labels it, and never reaches around it for a number. Most weeks 1F is one command: the executive hands over a table and it is stored verbatim. See "The narrative is the product" below.

## Decisions

- **The system is an executive's admin preparing the executive's report.** The author owns the report, approves every number and answers every open question. Where anything is unclear the system asks the author; it never resolves an ambiguity by assumption. A worker that cannot ask returns its questions, and the procedure puts them to the author.
- **Categories recur by role and flex by week.** Some categories are standing because the role answers for them; others are added or dropped for what happened that week. The count is a rough range, not a rule: many categories is a prompt to ask whether the report is too wordy or the week unfocused, never a reason to merge or pad.
- **The role profile describes the audience as well as the author:** who sits on the leadership team, by role, and what each one answers for, so the importance test has something to test against. Gate 1 shows each proposed item with the reason a reader would care, and lists what was left out as internal so the author can pull one back.
- **Reports cascade.** A direct report's weekly report arrives the day before and is more detailed in their area. The head's report pulls out what is worth passing to the leadership team, and Gate 1 shows those items for that choice. The form of those reports is not fixed yet, so finding and ingesting them is an adapter: mail, a file or a note.
- **One report per person.** Two seats at one organisation share one document with a header per seat.
- **The week and the deadline.** The report covers the working week it is written in and goes out by end of business Friday, usually around 3 pm, on Thursday when Friday is a holiday, and occasionally on Saturday. The sweep therefore runs on the last working day and covers Monday to the moment it runs.
- **Results tables follow a close; other weeks carry operating figures.**
- **Gate 1 weight** follows what the week found: a full category confirmation when the system proposes a change, one line otherwise. To be tuned from use.
- **Two exclusion lists:** never published, and never recorded.
- **The size of the author's edits at Gate 3 is tracked** as the measure of whether this works.
- **Delivery:** a PDF attached to an email draft in the author's own Drafts folder, the Word file kept beside it in the organisation's document folder. The covering email is written by the one drafter, behind the outbound gate. The system never sends.
- **The role profile lives with the organisation's record** (for example a note an assistant can maintain), while the process stays source-agnostic.
- **Open:** whether any ledger system is ever read directly. The default path does not need one, because the executive supplies the table. A standing metric with no figure still reads "not available this week", and nothing estimates one.

## The gates when nobody is present

Recurring work can run unattended, act on evidence, and ask only what only the owner can answer. Run that way, the weekly report is `weekly-report-orchestrator`, in a Thursday collection run and a Friday assembly run, and the gates change as follows. The principles above stand; this changes how principle 2 and principle 10 are met when the owner is not in the room, not whether.

- **Gates 1 and 2 are asked every week, as one numbered list on the owner's task list** (`report-weekly-gates`, through `comms-confirm`), each question with its default written beside it before anyone relies on it.
- **An unanswered number takes its stated default.** For Gate 1 the default is the standing categories the owner wrote into the profile, with nothing moved, pulled back or struck: the owner's sense of what mattered as of the profile, rather than none at all. For Gate 2 it is no wins added and every missing figure "not available this week". The draft's covering note and `owner-input.md` name every default taken, so a report built on defaults never passes for one the owner shaped.
- **Gate 3 is never assumed.** The draft goes to the owner to approve; nothing is recorded to the ledger and nothing is sent until they do. A draft is not a report.
- **Done is computed** by `report-weekly-check` over the week's files.

The risk this accepts, named: a week whose biggest item sits outside every standing category reaches the draft only if the owner pulls it back. The gate list puts the catch-all candidates and the audience editor's Leave out list in front of the owner for exactly that reason, and Gate 3 is the last chance to add it.

## The narrative is the product

The critical part of this exercise is the narrative report, not the financial table. Embedding financial data is a side quest the method does not over-fit to.

So the default path for a table is that the executive hands one over. `python3 ~/.claude/skills/report-weekly/scripts/report_facts.py add-table` takes whatever they have, a CSV file, a Markdown pipe table, or a block of cells pasted out of a spreadsheet, and stores it verbatim as a table of kind `supplied` with a title, a required as-of date and a source that defaults to "supplied by the executive". Nothing is computed from it, nothing is footed, and no row or column shape is expected. It renders at `{{table:<key>}}` exactly as a computed table does, and the tie-out checks the prose numbers under the marker against its cells exactly as for a computed one.

Gate 2 carries one line about it: "Any table to add this week?"

The computed month-end table, `python3 ~/.claude/skills/report-weekly/scripts/report_facts.py import-table` with its variances, its percent-of-revenue lines and its footing check, stays as an option. **The flow never requires it and the setup interview never asks about it.** Standing metrics in the profile are optional and an empty list is valid. **No ledger-system adapter is written**: the source of a real organisation's figures is a decision for the executive, not for this toolbox.

Principle 3 stands unchanged, and it is why this is safe. The writer never types a number that is not in a supplied table, in a figure, or in the evidence. Where the figures come from stopped being the question; whether a model produced one never was.

The care goes on the narrative path: the profile, collect, organise, continuity, the audience editor, Gate 1, the questions, the writer and verify.

## The store is the author's folder

`--store`, else `REPORT_STORE_DIR`, and no default path anywhere, because a default path belongs to whoever wrote it. One layout, and every command reads the same one:

| Path | What it holds | Written by |
|---|---|---|
| `<store>/profile.md` | the role profile | `report-profile`, and the setup interview |
| `<store>/report-ledger.jsonl` | the continuity ledger, one entry per published bullet | `report-ledger` |
| `<store>/records/<date>/` | one week's record and its manifest | `report-record` |
| `<store>/edit-size.jsonl` | the Gate 3 edit size, one row per week including the skipped ones | `report-record` |
| `<store>/workorder/<period>.json` | the week's work order state, and what `resume` reads | `report-workorder` |
| `<store>/work/<period>/` | the week's working files when it runs unattended across two sessions | `report-weekly-prepare`, `report-weekly-gates` and the orchestrator |

## The week is a work order

Each week's report is a task assigned to the agent. The state file is the source of truth for resuming and is always written: the stage reached, the gate pending, the files so far. The Portal task mirrors it where the Portal tier is in use. An agent name that is not installed, or a Portal that cannot be reached, is reported as a finding and the run carries on with the state file alone.

Where the work tracker cannot yet hold something (task comments, recurrence, a link to the delivered file, the detail of what a WAITING task waits on, a gate answered in chat), the work order carries it in the state file or an activity note instead.

## The gates run in the terminal, with a heads-up

A gate is answered where the agent runs. Where the Portal tier is in use the agent posts **one** text heads-up per gate to its own member through `teams_post`: "Your weekly report is waiting on you at Gate N: M questions." Never more than one per gate, never the report's content, and silently skipped where the tool is absent.

## Continuity is a ledger, not a look-back window

Reading the last few reports is not enough: something from six weeks, a quarter or a year ago can be exactly what this week's report has to answer, and there can be no blind spots. Every published report is therefore broken into ledger entries, one per bullet: date, seat, category, topic label, text, the figures it cited, and a kind (an open issue, a pending decision, an expectation with a date, a recurring item with its cycle of weekly, monthly, quarterly or annual, or plain information), with a closed flag once a later report resolves it. Retrieval is deterministic and age-blind: every open entry; every dated expectation that falls in or before this week; every entry sharing a topic label, counterparty or project with this week's evidence; and every recurring entry whose cycle comes due (the same week last quarter or last year). A continuity worker then reads those candidates against this week's topics and says which must be answered, and the writer answers them or the author strikes them at a gate.

## Architecture

Built for a terminal coding agent first (Claude Code, and Codex where it can follow), with prerequisites allowed. A desktop plugin is welcome where it fits; a chat-only assistant that cannot run code can carry the process and the style but not the tools, the verifier or the ledger, so it is not a target. No member names a person, a client or a local path.

| Layer | Members | Differs per person |
|---|---|---|
| Agent, who the executive talks to | `weekly-reporter`, a main-session agent: an executive's admin that runs the flow, owns the gates, asks when anything is unclear, never sends | No |
| Procedure (skill) | `report-weekly`: the weekly flow, with the role profile interview in its `setup.md` and the house style, profile template and older formats in `reference/` | No |
| Workers, which never talk to the executive | continuity (which ledger items must be answered), audience editor (the leadership test, with a reason per item and a left-out list), writer (house style), intake (structures a free-text report from a direct report), harvester (see below) | No |
| Tools, deterministic | `report-profile`, `report-workorder`, `report-collect`, `report-organize`, `report-ledger`, `report-questions`, `report-facts`, `report-verify`, `report-render`, `report-record` | No |
| Adapters, beneath collect and facts | See the three tiers | Yes |

**Workers are prompt files inside the skill folder**, `workers/`, so the whole workflow travels as one folder and a runtime without sub-agents can run a worker's instructions inline, in order. In Claude Code each worker also has a thin registered agent that points at its prompt file, because a registered agent's tool allowlist is what makes "the writer cannot reach a source system" a fact rather than a request.

**Three tiers of collection, one contract.** Every tier writes the same evidence ledger, so nothing downstream knows which one ran.

1. *Portal tier.* The executive's mail, calendar and work tracking are in the Insights Portal, which already holds the mail and calendar connection. Collection is code: fast, repeatable, no tokens. This is the recommended prerequisite, and some features may require it (the noise report, thread-level waiting status, anything that needs a complete read).
2. *Harvester tier.* No Portal. The procedure dispatches a harvester worker that reads the executive's Microsoft 365 mail and calendar through a connector and writes the evidence ledger itself. It costs tokens and minutes and it can miss things, so the pack records that the harvest was model-driven and the gates carry more weight. A worker cannot start another worker, so it is always the procedure that dispatches the harvester, never the writer or the editor.
3. *Manual tier.* No connection at all: the direct reports' reports in a folder, the figures the executive supplies, and the gates. The flow still produces a sound report, because the executive's own account of the week is the primary input by design.

Storage is a folder per author (profile, report ledger, weekly records), with an optional searchable copy elsewhere. Prerequisites: Python 3.11 or later, pandoc and LibreOffice for the Word and PDF files, and a Portal token for the first tier.

## Contracts between stages

Role profile; evidence ledger; facts set (figures and tables); confirmed weekly outline; draft with table markers; verification result; published file; record. Each is a file with a fixed shape, so any stage can be replaced without touching its neighbours.

## Open items

**The data side cannot see the week's wins.** The work tracker's listing omits completed tasks, and a listing of completed ones caps at 1,000 rows in no date order. So `report-collect` reads what is open and what is late and almost nothing that was finished, and the report's own principle is that a win earns a bullet. The answer for now is human and deliberate rather than a gap nobody noticed: Gate 2 asks the executive, in those words, what went well this week that the leadership team should know, and the answer is evidence cited `owner://gate2`. When the tracker can list a week's completions, the collection tier gains a completions pass and the Gate 2 question becomes a check on it rather than the only source.

**The names-to-roles map is optional and mostly absent.** The writer needs a role to put in place of a person when it rewrites a problem sentence. Without the map it drops the actor entirely, which is correct but blunter, and the profile warns rather than errors. A run of weeks with the warning standing is the signal to fill it in, not a reason to make it required.

**The blank form's Length placeholder has the trap the Materiality one had.** An unanswered `<one page, 450 to 600 words>` parses as a real target. Materiality was fixed because it silently judged figures against a number nobody chose; Length wants the same angle-bracket rule.
