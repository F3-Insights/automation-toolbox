---
name: work-survey
description: A full survey of one person's working life from their own email, calendar and meetings, measured against what they owe (contracts, scopes, recurring obligations) and what they say they want (goals). Fast-model gatherers read in parallel, strong-model analysts reason across them, a reviewer challenges the draft. Produces an operating plan with an hours ledger, a deliverables ledger, an attention audit, joinable CSVs and build specs for the automations that survive. Works cold from five intake questions, or warm from existing goals, profile and contract documents; runs as a pasted prompt too. Use when someone asks "where does my time go and what would get hours back". Not for a recurring time study (report-time-study) or a single week's plan.
argument-hint: "[subject name] [output folder] [data source: m365 | portal]"
disable-model-invocation: true
---

# Work survey

One orchestrator, a team of subagents, one folder of output. The question the survey answers: **where do this person's hours actually go, against what they owe and what they want, and what would get the target number of hours back.**

It is an evaluation tool first and a build backlog second. The build specs at the end are for whoever will build the automations; they are not the point. A survey that returns only automation ideas has failed. Delegation, dropping work, and protecting time for owed deliverables count as much as anything built.

**User provided:** $ARGUMENTS

## How to run it

- As a skill: `/work-survey <subject> <output folder> <m365|portal>`.
- As a pasted prompt: paste this whole file into Claude Code, then fill in the parameters block below. Everything the run needs is in this file. It creates no agent files; the orchestrator starts general-purpose subagents with a `model` override.

## PARAMETERS (fill in, or ask for anything missing in one message)

| Parameter | Meaning | Example |
|---|---|---|
| `SUBJECT` | Whose work is surveyed | Alex Morgan, CEO of Acme Components |
| `ROLE_FOCUS` | What the person should be spending time on | Sales, BD, partnerships, strategy |
| `COUNTERPARTS` | People whose split of work matters (co-CEO, partner, EA) | Dana Whitfield (co-CEO); Jordan Lee (EA) |
| `BUILDER` | Who will build the automations | the owner |
| `TARGET_HOURS` | Hours per week to get back | 20 |
| `DATA_SOURCE` | `m365` (Microsoft 365 MCP tools) or `portal` (Insights Portal MCP) | m365 |
| `OUTPUT_DIR` | Absolute path for all output | `%USERPROFILE%\Downloads\Work-Survey-<date>\` |
| `CONTEXT_SOURCES` | Existing documents that already describe the person: goals, profile, contracts, prior audits, a toolkit inventory. `none` means a cold start | goals doc path; SOW folder; prior audit |
| `EXCLUDE` | What is out of scope | family calendars; personal notes; HR detail |
| `WINDOW` | Email and calendar window | email 90 days, deal threads 12 months, calendar 90 back + 30 ahead |
| `TOOLKIT` | Optional. Paths to automations the builder already has, for the transfer map | a skills directory; a cron harness |
| `INTERACTIVE` | `yes` if the subject is at the keyboard for the intake | yes |

## HARD RULES

1. Read only. Never send, reply, forward, archive, flag, categorize, delete, accept, decline or move anything in email or calendar. Never write to a CRM, task system or Portal.
2. Never copy passwords, account numbers, ID numbers or credentials into any output.
3. HR, legal and compensation threads are summarized at topic level only ("ongoing HR matter, about 2 hrs/week"), no personal details.
4. Every finding cites evidence: date plus sender and subject, or event title, or file path.
5. Every conclusion carries a confidence: High, Medium or Low.
6. Every hours figure shows its method (meeting minutes summed, messages x assumed minutes, log timestamps). No invented numbers.
7. If a mailbox, calendar or context source cannot be read, say which one in the output and carry on with the rest. Do not guess to fill the gap.
8. Stay inside `EXCLUDE`. A family or personal calendar may be counted as blocked hours only, never described.
9. Never stop and wait for the subject after the intake. If a question comes up mid-run, write it to `03_final/questions.md` and continue.

## PHASE 0: CONTEXT LOAD (warm start only; skip if `CONTEXT_SOURCES` is `none`)

Before asking anything, find out what is already known, so the intake asks only what the documents cannot answer.

Launch one Sonnet subagent to write `00_recon/context.md` from `CONTEXT_SOURCES`, with:
- roles and engagements (client, contracting entity, role, term, status)
- **contracted deliverables**, exhaustively: every deliverable, cadence or due date, hours or fee basis, with the source document and section. This becomes the deliverables ledger
- recurring obligations not in any contract (month-end close, board prep, standing reports)
- stated goals with their priority, quoted briefly
- declared workstreams (from a task system, project list or CRM, if one is available)
- attention evidence from any prior audit, numbers verbatim with their source
- mismatches already visible, labelled as inferred, and gaps

## PHASE 1: INTAKE

**Cold start:** the five questions below, one at a time, about 10 minutes total. Give 3 or 4 short example answers with each. At most one follow-up per question, only if the answer is vague.

1. **Biggest time drains:** "In a typical week, what eats the most time that you feel shouldn't need you?"
2. **Repeat work:** "What tasks or emails do you find yourself doing over and over that you'd happily never do again?"
3. **Things slipping:** "What worries you most about falling through the cracks right now?"
4. **Best use of the hours:** "If you got `TARGET_HOURS` hours a week back, what would you spend them on, and what work do you believe only you can do?"
5. **Boundaries:** "What should never be automated or handed off? How comfortable are you with AI drafting emails for your approval, versus sending routine ones on its own?"

**Warm start:** replace those with a delta intake built from `context.md`. Play back the declared picture in five to eight bullets (engagements, owed deliverables, top goals, what prior audits found), then ask, one at a time, at most five questions such as: what has changed since these documents were written; which owed deliverable worries you most; where you think your time goes that the documents would not show; what you would do with the hours; your boundaries for automation. Ask only what the documents do not already answer.

After the last answer:
1. Write `00_recon/intake.md`: the answers in the subject's own words, then **binding constraints** (never automate, AI may do alone, needs approval, to confirm), then **pain points to verify** as numbered hypotheses (ID, hypothesis, what would confirm or challenge it).
2. Play back a three-to-five bullet summary. If `INTERACTIVE` is `yes`, ask "Did I get that right?" **and continue as soon as the subject answers or moves on**. If the subject has stepped away (no reply in the same session turn) or `INTERACTIVE` is `no`, write the summary to `intake.md` marked "unconfirmed" and continue. The survey must never sit idle waiting at this step.

The intake is binding on everything after it. Every gatherer and analyst gets `intake.md` (and `context.md` when it exists). The boundaries are constraints on every recommendation.

## PHASE 2: SETUP

1. List every mailbox and calendar the data source exposes. Confirm read access to each; mark any in `EXCLUDE` as out of scope. Write `00_recon/sources.md`.
2. Create `OUTPUT_DIR` if it does not exist:
   ```
   00_recon/   context, intake, sources, workstreams, people map
   01_raw/     gatherer outputs (Markdown + CSV per slice)
   02_analysis/ analyst outputs
   03_final/   operating plan, questions
     data/        joinable CSV and JSON
     build_specs/ one spec per automation, plus README with build order
   ```
3. State the absolute path in chat.

### Data source notes

- `m365`: the Microsoft 365 MCP tools (`outlook_email_search`, `outlook_calendar_search`, `read_resource`, Teams chat search). Metadata first, bodies only for threads that matter.
- `portal`: the Insights Portal MCP. Call `whoami` first (timezone, inboxes, calendars; every timestamp is UTC). `list_entities` for email and calendar_event with `since`/`until`, `email_bodies` in batches of up to 50, `list_fellow_meetings` and `get_fellow_recording` for transcripts, `hierarchy` for goals and projects. Follow `next_offset` until `has_more` is false. Calendar events with `event_kind: availability_block` are clones; count the original meeting once.

## PHASE 3: RECON (orchestrator, metadata only)

1. Pull sender, recipients, subject and date for the email window across every in-scope mailbox (sample if volume is very large, and say so).
2. Pull calendar titles, attendees, durations, recurrence; drop clones and duplicates.
3. Build `00_recon/people_map.md`: counterparts, each colleague and their apparent area, top clients, prospects, partners, vendors. Tag external domains by company.
4. Write `00_recon/workstreams.md`: 6 to 12 workstreams. On a warm start, begin from the declared engagements and workstreams in `context.md` and add what the data shows that they miss; flag any declared workstream with no traffic. On a cold start, cluster from the data.
5. Show the workstream list in chat and continue.

## PHASE 4: GATHER (Sonnet subagents, in parallel)

Launch each as a general-purpose subagent with `model: sonnet`. Each gets: its slice, the absolute output paths, `intake.md`, `context.md` if any, `workstreams.md`, the hard rules and the output schema. Keep the total at six to eight gatherers; group small workstreams.

**G1. Calendar and meetings.** The full calendar window:
- meeting hours per week, focus hours per week, and days with no 90-minute free block
- hours by workstream; client-facing versus internal; one-off versus recurring
- every recurring series: cadence, duration, attendees, whether the subject looks essential, whether a counterpart also attends
- meetings with a transcript or notes versus none; meetings with no follow-up evidence
- travel days and knock-on effects

**G2. Workstreams (one to three agents, grouped).** Per workstream, threads read in full: outcome being driven; key people and the subject's role with each (decision maker, approver, relationship owner, bottleneck); volume sent and received; open loops both directions; decisions made and pending; recurring asks; anything stalled or at risk.

**G3. Deliverables and scope.** Start from the contracted deliverables in `context.md` (on a cold start, find them: SOWs, proposals, engagement letters, recurring reports in sent mail). For each deliverable find the evidence of delivery in email, calendar and files:
- delivered on time, delivered late, partly delivered, not delivered, not yet due
- last delivery date and the one before, so cadence slips show
- time spent on it (meetings and threads), with method
- deliverables the client asked for that are in no contract (scope creep), and contracted deliverables nobody has asked about (quiet risk)

**G4. Sent mail and follow-ups.** The subject's sent mail only: what they chase and whom; promises made ("I'll send", "let me check") and whether they closed; delegable work they do themselves (scheduling, forwarding, recaps, status requests); response times by sender type.

**G5. Attention.** Where the hours go that the calendar does not show.
- For each working day in the window: calendar hours, sent-mail activity by hour, and any other activity log the subject has (for a builder, local Claude Code or Codex session timestamps in `~/.claude/projects/*/*.jsonl` and `~/.claude/history.jsonl`, counted as active minutes from typed-prompt timestamps with a 10-minute idle cutoff).
- Classify self-directed time as **delivery** (tied to a contracted deliverable or client workstream), **enablement** (internal tooling that a deliverable used in the window), or **build** (tooling with no deliverable consuming it in the window). Cite the session or thread for each classification.
- Hours per week by class, and which owed deliverables slipped in weeks where build hours were high. Correlation only; say so.
- Skip this slice if no activity log exists beyond email and calendar.

**G6. Automation candidates and existing capability.** Scan everything for repetitive, rules-based work: recurring reports, scheduling back-and-forth, standard replies, meeting prep and recaps, predictable approvals, repeated look-ups. If `TOOLKIT` is set, inventory it: one row per skill, agent or scheduled job, with what it does, what data it needs, whether it ran in the window and whether it worked (from its logs), and whether it depends on infrastructure only this builder has.

**Output schema for every gatherer**, Markdown in `01_raw/<slice>.md`:
```
# [Slice name]
## Summary (5 bullets max)
## Findings
- Finding | Evidence (date, sender/subject, event, or path) | Confidence
## Open loops
- Item | Waiting on (subject / them) | Since | Evidence
## Time and volume estimates (with method)
## Delegation or automation signals
## Gaps
```
Plus `01_raw/<slice>_evidence.csv`, one row per finding, loop or signal: `id, slice, workstream, type (finding|open_loop|decision|deliverable|recurring_task|automation_signal|delegation_signal|attention), description, people, company, date_first, date_last, source, est_minutes_per_week, estimate_method, confidence`

Be exhaustive in the CSVs; the Markdown summarizes. Gatherers stay in their slice and flag cross-workstream items rather than analysing them. When all finish, check each against the schema and re-run any that is thin, uncited or off-slice.

## PHASE 5: ANALYZE (Opus subagents)

Launch as general-purpose subagents with `model: opus`, each reading all of `01_raw/`.

**A1. Time, deliverables and responsibilities** → `02_analysis/time_and_scope.md`
- Hours per week by workstream against where `ROLE_FOCUS` says they should go; client-facing time as its own line; the biggest mismatches.
- The deliverables ledger: each owed deliverable, status, hours it takes, hours it should take, and the risk if it slips.
- Attention: delivery, enablement and build hours per week, and what the build hours displaced.
- Every responsibility classified **Keep**, **Hand to counterpart**, **Delegate** (named person), **Automate**, or **Drop/Reduce**. Where the subject is the bottleneck; where the subject and a counterpart duplicate effort.
- Open loops, de-duplicated and ranked by risk and age, client and deliverable items first.

**A2. Automation and transfer** → `02_analysis/automation.md`
- The backlog, keeping only what the data supports. For each: name, purpose, type (skill, subagent, scheduled job, mail rule, template), trigger, inputs and outputs, hours saved with method, effort S/M/L, dependencies, human checkpoints. Nothing reaches a client without the subject's approval unless the intake explicitly allows it.
- If `TOOLKIT` is set: a **transfer map** matching each backlog item and each G6 inventory row to one of: already built and working; built, needs repair; built, portable to another person as is; built, depends on this builder's infrastructure; missing. For the portable ones, what a second person needs to run it.
- Anything in the toolkit that ran in the window and served no deliverable: name it.

## PHASE 6: SYNTHESIZE AND REVIEW

1. Merge and de-duplicate into `03_final/data/`, then draft `03_final/operating_plan.md`.
2. Launch one reviewer (general-purpose, `model: opus`) on the draft with the raw files. It challenges: whether the hours total is real or double-counted; whether delegation targets have capacity; whether anything client-facing is automated too aggressively; whether any recommendation is generic rather than grounded in this person's data; and whether the plan recommends more building where the attention audit shows build time already displacing owed work.
3. Revise. Keep unresolved disagreements in the plan, marked as such.

## DELIVERABLES

### `03_final/operating_plan.md`

Extensive, not a slide summary. One-screen executive summary first, then every section in depth with tables, evidence and reasoning. Each section links to its CSV.

1. **Executive summary**: where time goes, the three biggest problems, the path to `TARGET_HOURS`.
2. **Pain points, checked**: each intake hypothesis, what the data showed, the fix.
3. **Deliverables ledger**: owed work, status, time it takes, what is at risk.
4. **Attention audit**: delivery, enablement and build hours, and what build displaced. Omit if G5 was skipped.
5. **The hours ledger**: every change (automate, delegate, hand off, drop, protect time), hours saved, confidence, running total; conservative and optimistic totals.
6. **Workstream map**: goal, key people, the subject's role, weekly time, health.
7. **Time audit**: actual versus recommended allocation, and an ideal weekly calendar that protects `ROLE_FOCUS` and owed-deliverable time.
8. **Counterpart split**: overlap now and a proposed clean division.
9. **Responsibilities matrix** with named owners.
10. **Client and pipeline snapshot**: active opportunities, owner, next step, risk.
11. **Top 15 open loops** with next action and owner.
12. **Follow-up patterns**: what the subject chases, why, and how to stop needing to.
13. **Recurring meetings**: keep, shorten, delegate or cancel, one by one.
14. **Automation backlog and transfer map** (summary; the specs are separate).
15. **30 / 60 / 90 day plan**: actions, owners, and how recovered hours will be measured.
16. **Questions** the data could not answer (also in `questions.md`).
17. **Appendix**: method, window, sources covered, gaps, confidence notes.

### `03_final/data/`

Clean, de-duplicated, joinable on consistent IDs (`person_id`, `workstream_id`, `deliverable_id`). Every row carries `source` and `confidence` where it applies.

| File | One row per | Key columns |
|---|---|---|
| `workstreams.csv` | workstream | workstream_id, name, goal, subject_role, hours_per_week, pct_of_time, strategic_value, health, owner_recommended |
| `people.csv` | person | person_id, name, email, company, relationship, workstreams, emails_in_window, meetings_in_window, hours_per_week_with_subject, subject_role |
| `companies.csv` | external company | company_id, name, domain, type, primary_contact_id, owner, last_touch, activity_level |
| `meetings.csv` | calendar event | event_id, date, start, duration_min, title, recurring, series_id, attendees, internal_or_external, workstream_id, meeting_type, subject_essential, counterpart_attends, has_notes |
| `recurring_meetings.csv` | series | series_id, title, cadence, duration_min, hours_per_month, attendees, recommendation, hours_saved_per_week, rationale |
| `deliverables.csv` | owed deliverable | deliverable_id, workstream_id, client, description, source_contract, cadence_or_due, status, last_delivered, hours_per_month_actual, hours_per_month_expected, risk, source |
| `attention_daily.csv` | working day | date, calendar_hours, email_active_hours, delivery_hours, enablement_hours, build_hours, method |
| `time_allocation_weekly.csv` | week x workstream | week_start, workstream_id, meeting_hours, est_email_hours, other_hours, total_hours |
| `open_loops.csv` | open item | loop_id, description, workstream_id, waiting_on, counterparty_id, opened_date, age_days, risk, suggested_action, suggested_owner, source |
| `commitments.csv` | promise made | commitment_id, date, to_person_id, promise_text, status, days_open, source |
| `follow_up_patterns.csv` | chase pattern | pattern_id, what_is_chased, who, frequency_per_month, est_minutes_per_week, root_cause, fix |
| `responsibilities.csv` | responsibility | resp_id, description, workstream_id, hours_per_week, classification, recommended_owner, rationale, confidence |
| `automation_backlog.csv` | automation | auto_id, name, type, trigger, inputs, outputs, hours_saved_per_week, effort, dependencies, approval_checkpoint, priority_rank, spec_file, transfer_status |
| `capability_inventory.csv` | existing tool (if `TOOLKIT`) | cap_id, name, kind, purpose, data_needed, ran_in_window, worked, served_deliverable_id, portable, dependency |
| `hours_ledger.csv` | change | change_id, change_type, description, related_ids, hours_saved_conservative, hours_saved_optimistic, confidence, owner, start_by |
| `pain_points.csv` | intake hypothesis | pain_id, statement, evidence_summary, verdict, related_ids, fix |

Also `data/summary.json` (headline totals) and `data/README.md` (data dictionary, joins, estimation methods). Before finishing, validate: every referenced ID exists in its home file, no duplicate rows, ledger totals match the plan.

### `03_final/build_specs/`

One Markdown file per automation, ordered by hours saved against effort: purpose and hours; type; step-by-step behaviour; data read and where output lands; trigger (a cron expression for scheduled jobs); approval checkpoints and failure handling (a failure must reach a human, not only a log); for skills a draft `SKILL.md`; how to test it and how to measure time saved. `build_specs/README.md` gives the build order: week-one quick wins, then the larger builds. Items already built get a repair or hand-over note instead of a spec.

## Finish

A chat summary under 150 words: conservative and optimistic hours, deliverables at risk, build hours per week if measured, row counts per CSV, and the absolute output path.
