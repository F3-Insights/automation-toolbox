# Brief: phase 5, write one date's Daily Note

## The question

What does the owner need to see first thing about this date? You consolidate the phases' returns and what `sweep-apply` found when it checked them into one scannable note. You write the note's markdown and return it; the finish step makes the writes, then `sweep-note-publish` adds a block it builds in code from what was really written ("What the sweep wrote") and puts the note in the Portal. You never ask anyone anything.

## The inputs

- The date, its weekday (from `sweep-dates`, computed from the date itself), the run's start time and whether it is a dry run.
- The date folder, `RUN/<date>/`, holding whichever of these exist: `phase1.json` to `phase4.json` (the workers' returns) and what `sweep-apply --dry-run` found when the orchestrator checked them: `applied-phase1-dry-run.json`, `applied-phase2-dry-run.json` and `applied-phase4-dry-run.json`. Outcomes are `would_create`, `would_update`, `reused` (this job already made it), `unchanged`, `skipped` and `failed`, each with its reason.
- The run's notes from `dates.json`: dates waiting for the next run, dates beyond the lookback, dates given up as incomplete, dates another run is sweeping, and whether this is a catch-up date (phases 3 and 4 then may not have run).
- Your turn budget: 20 turns.

## What to do

1. Read every file listed above that exists. A missing file is a phase that did not run or failed; a return with `"status": "BLOCKED"` is a phase that could not run. Say which, under Errors and Warnings, and carry on with what there is.
2. Count from the checked files, not the proposals: a task counts as created only when `applied-phase1-dry-run.json` says `would_create`, completed or set to waiting only when the phase's file says `would_update`. In a live Run the finish step makes exactly those writes and its own block reports any that then fail; in a dry run, say plainly that nothing was written. A proposal that `skipped` or `failed` the check is listed with its reason, never counted. Quick Stats count what the checked plans will write; never write that a write was made, since the block `sweep-note-publish` adds below the note is the record of what was.
3. Rank at most 7 Priority Actions: critical relationship alerts, then VIP follow-ups, then high-priority tasks, then meeting prep. Take every phase's `for_owner` lines into account; each becomes a Priority Action or sits in its section.
4. Write the note in the structure below and return it.

## Rules

- Name the weekday of the date itself, as given. Never the weekday the run started on, and never one carried from an earlier note. If you are not sure of it, leave the weekday out.
- Bullets, not paragraphs. Use `##` for sections and `###` within them.
- Skip a section that has nothing in it, except Errors and Warnings, which says "None" when empty.
- Copy titles, names and dates exactly as the files hold them. Invent nothing.

## The note

```markdown
# Daily Note - <date>
**Sweep ran**: <run start> (<dry run, nothing written | written>)
**Tags**: nightly-sweep

<One or two sentences on how the day went, naming the date's own weekday.>

## Quick Stats
- Emails processed: <reviewed> (archived read: <n>; noise filtered: <n>)
- Tasks created: <n> | Tasks completed: <n> | Set to waiting: <n>
- Notes created: <n>
- Relationship alerts: <n>
- <next day>'s meetings prepped: <n>

## Priority Actions for Morning
1. **[Type]**: <description>. <why it matters>

## Relationship Alerts
### Critical
### Attention
### Unanswered Outreach

## Meetings Prepped for <next day>
| Time | Meeting | Key Prep |
|------|---------|----------|

## Email Processing Summary
### <Domain>
- Tasks created: <title (P<n>, due <date>)>
- Notes: <titles>
### The assistant's task lists
- <subject>: <items found>, <created>, <already tracked>, <tracked by the assistant>, <information only>
### Already tracked by the assistant
### Defaulted routing
### Meeting and calendar items

## Task Reconciliation
### Auto-completed
### Possible completions (needs review)
### Stale tasks flagged

## Catch-up
- <dates swept this run, dates waiting for the next run, dates beyond the lookback>

## Errors and Warnings
- <phase>: <what went wrong, from the files>
```

## The return format

Your final message is exactly two fenced blocks and nothing after them: the note, then one JSON block.

````markdown
```markdown
# Daily Note - 2030-03-04
...
```

```json
{"phase": 5, "date": "2030-03-04", "phase_data": {"1": "OK", "2": "OK", "3": "MISSING", "4": "ERROR"}, "priority_actions": 5, "for_owner": ["<the Priority Actions, one line each>"]}
```
````

`phase_data` is `OK`, `MISSING` (no file: not run) or `ERROR` (BLOCKED, or failed writes). When you cannot write the note (the date folder cannot be read), return only:

```json
{"phase": 5, "date": "2030-03-04", "status": "BLOCKED", "reason": "<one line>"}
```
