---
name: project-health-diagnose
description: "The weekly project-health pass, loaded by projects-health-review and by the projects-worker and projects-reviewer it dispatches, not for a user request; adds to orchestration-workstream and task-stack-workstream. Covers the Steps over the worklist projects-health-check picks, the closed list of eight diagnoses, the smallest unblocking step and the fixes (goal link, next action, owner, close) as task-stack-apply ops, nudges, when a project is dead, and the sections Diagnose a batch, Drain a bucket and What the stalled projects wait on, with diagnoses.json, the file the weekly review and project-checkin read. For the weekly pass, start projects-health-review."
---

# The weekly project-health pass

Load `orchestration-workstream` and `task-stack-workstream` first, by name: the conduct, the return block, the owner's rules file and the change-set op shapes come from them.

The goal is a project list the owner can trust in a five-minute look: every active project says what it serves (a goal), what happens next (an open next-action task) and who does it (an owner), and has moved recently. A project that has stopped carries one word saying why and the one smallest step that starts it again, taken where it is the owner's to take. A project that died is closed, or put to the owner as one closing question. The domains' catch-all "General Tasks" projects are buckets, not projects: never scored, drained into the real projects their tasks belong to.

Bias to action. The owner asked for autonomy on evidence: link a goal, set an owner, create a next action, chase a person, close what the rules let you close, without asking. Only what the record cannot settle and only the owner can answer becomes a question. Nothing in the session writes to the Portal: `task-stack-apply` makes the change set after the session, under the owner's rules, and refuses any op that breaks them.

## What the Run has

- `RUN/health.json` from `projects-health-check`: `projects` (every active project with its state, gaps, idle days, last activity, open, waiting and overdue counts, next actions, goal, mechanical score), `worklist` (the projects to diagnose, ranked), `close_eligible` (dead: no goal, no open task, no activity for 90 days), `close_candidates` (idle 90 days or more but linked to a goal or still holding open tasks), `drain` (bucket tasks to file in real projects), `buckets`, `deferred` (worklist backlog left for later weeks), and the owner's contact id.
- `RUN/before.json`: the trust score's `projects` component before the session (`task-stack-check`).
- If either is missing (the prepare line said `STALE`), read the projects yourself with `list_entities`, pick at most max projects of the stalled ones, and say so in the report.
- The owner's `TASK-STACK-RULES.md`, at the `rules_file` input. Read it first; it wins.
- Inputs: Domain (optional), Max projects (default 15, already applied by the check), Max changes (default 60; `task-stack-apply` defers the rest), Instructions, Dry run.

## Steps

For `projects-health-review`.

1. [judgment] Orient. `whoami`; read the rules file, `RUN/health.json` and `RUN/before.json`.
2. [judgment] Plan. Cut the worklist into batches: two projects per batch for `stalled` and `dead`, five for `gaps`. For each batch gather once what every worker would otherwise read again: the active goals and the other projects of its domains. Write `RUN/plan.json`: the batches, the drain batch, and the worklist projects with WAITING tasks.
3. [hand-off: projects-worker] In one message: a worker per batch on section Diagnose a batch (op-id prefix the batch id); one on section Drain a bucket with the drain batch and the open projects of those domains; and, when a worklist project has WAITING tasks, one on section What the stalled projects wait on, scoped to those projects. Each brief: its projects or tasks, the goals and projects it needs, the owner's contact id and timezone, today's date, the rules file's path; nothing of your own view. Save each return as `RUN/returns/<id>.json` the moment it arrives; a reply without its json block goes back once.
4. [hand-off: projects-reviewer] Every `medium` task op, and every `complete` or `cancel`, with the ops only, the rules file's path and the owner's contact id: `task-stack-workstream`, section Check task-stack ops. A FAIL drops the op; where the worker had a best guess it becomes a question. A `medium` project op (a goal link, an owner) is not checked: it becomes a question.
   → nothing to check: step 5
5. [judgment] Decide, by section Build the change set, and write `RUN/changes.json` (`"orchestrator": "projects-health-review"`, `dry_run` as this Run is) and `RUN/diagnoses.json`.
6. [judgment] Report, by section The report. Never claim a score change: the finish step computes it.
   → reported: done

A Run is done when the change set is written and every worklist project has a decision (ops, a question, or a stated reason it needs nothing), every close-eligible project has a close op, and every close candidate has a question. Whether the projects got better is computed: before the session the Automation runs `task-stack-check` (the `projects` component, `before.json`) and `projects-health-check` (`health.json`); after it `task-stack-apply`, then both checks again (`after.json`, `health-after.json`) and `task-stack-report`. The `projects` component and the unhealthy count must not get worse. With no one present everything runs the same: questions go in `changes.json` and the report, never live.

## Build the change set

- the `high` ops and the checked `medium` ones, one decision per project, task ops before their project's `project_close`;
- a `project_close` (`CANCELLED`) for every `close_eligible` project, reason "No goal, no open task, no activity since <last_activity>";
- one question per `close_candidate` from health.json's facts alone: "Close <name>? Idle <n> days, <k> open tasks, linked to <goal>." Do not diagnose them;
- each nudge, from a diagnosis or the waiting-on scan, as one `create` task "Chase <name> for <the thing>" in that project, due within three working days, with the nudge's fields in its `description`, unless an open task already is that chase; the scan's items for projects outside the worklist are reported, not acted on;
- the drain's ops, filing bucket tasks in the projects they belong to;
- drop an op that sets a field to the value it holds; keep at most max changes ops, closes and next actions first.

`RUN/diagnoses.json` is a file contract: the weekly review (productivity) and `project-checkin` read it from the newest Run folder. One row per worklist project, exactly `{project, name, domain, diagnosis, reason, smallest_step, who, needs_owner, ops, question}`.

## The report

The diagnoses counted by word; the owner's decisions as one numbered list, `WAITING_ON_OWNER_DECISION` first, then closing questions, then the rest, each answerable "1) ok 2) no"; what the change set does by op (next actions, chases, goal links, owners, closes, bucket tasks filed); what could not be judged and why; the worklist backlog (`deferred`); before.json's `projects` component.

## Diagnose a batch

For a `projects-worker` given a few projects. Read the rules file named in the brief; it overrides this skill. Read only; write nothing. Every project in the batch gets an `items` row with one of the eight diagnosis words and its smallest step, and either the ops that take that step, a question, or a note saying why neither (a `MOVING` project with no gap needs nothing). Every op rests on something in the record, cited.

### The standard

An active project the owner can trust says three things without being opened: what it serves (a **goal**), what happens next (a **next action**: an open TODO or IN_PROGRESS task, or a WAITING task with its follow-up date as its due date), and who does it (an **owner**: the project's assignee or the owner of an open task). And something has happened on it recently. When one of those is missing, the fix is usually small, and it is yours to propose. When the project has stopped, the job is to say why in one word and name the one smallest step that would start it again.

The check tool has already done the arithmetic. Each project in your brief comes from `projects-health-check` with its state (`stalled`, `dead`, `gaps`), its gaps (`no_goal`, `no_next_action`, `no_owner`, `stale`), its idle days and last activity (bulk edits to the records are not counted as activity), its open, waiting and overdue task counts and its next actions. Do not recount; read the record for what the numbers cannot say.

### The work, per project

1. **Read it.** `get(entity_type="project", id_or_query=<id>, detail="full")`: the record, its tasks, notes and hierarchy. Then what explains it: the latest notes on it (a check-in or status note from the owner is the most authoritative thing there is; one from the last 7 days means they are managing it, so you propose no nudge and say so), mail with its key contacts in the last 30 days (`list_entities` email by contact, `email_bodies` only for the few that decide it), and `activity_stream` for its company if it has one. Keep reads small: `limit` 25, `detail="summary"` unless a record is known to be small.
2. **Diagnose.** Exactly one word from the closed list below, with the one-line reason that word must carry.
3. **The smallest step.** The least that would change the diagnosis. Not the plan, the next move: who takes it, and whether it needs the owner.
4. **Fix the gaps** the record lets you fix, as ops (below).
5. **Propose** the ops, the nudges and the questions. Everything goes in your return.

### The diagnoses (closed list)

| Diagnosis | When | Must carry | The step becomes |
|---|---|---|---|
| `MOVING` | Tasks progressing, mail flowing, nothing overdue. Usually a project whose only trouble was a gap. | Nothing. | Only the gap fixes. |
| `WAITING_ON_PERSON` | Someone other than the owner owes the next thing. | Their name, and since when. | A nudge, and a `create` task "Chase <name> for <thing>" due within 3 working days, unless an open task already is that chase (then `edit` it to WAITING on them with a due date). |
| `WAITING_ON_OWNER_DECISION` | Stuck on something only the owner can settle: a price, a scope, their time, a yes or no to a person. | The decision as a question, with the options the evidence supports. Never your answer. | A question, never a nudge. |
| `NO_NEXT_ACTION` | Nothing wrong and nothing scheduled. | One concrete next task. | A `create` task with a verb-first title someone could do this week. |
| `NO_OWNER` | The work belongs to no one. | Who the evidence suggests, or "nobody the Portal shows". | `project_edit` `assignee_contact_id` to the owner's contact when the evidence says the work is theirs; otherwise a question. |
| `TOO_BIG` | There is a next action, but it is a month of work in one line, so it never starts. | The first slice. | A `create` task for the first slice, due this week. |
| `BLOCKED_EXTERNAL` | Something outside anyone here must happen first: a vendor, a regulator, a counterparty, a system. | What blocks it and whose it is. | A WAITING task on that party with a follow-up date, or a nudge when a person can be asked. |
| `STALE_OR_DEAD` | The evidence says it stopped mattering: the deadline long past, nothing happening, the thing it was for happened another way. | The evidence for closing, not an impression. | The close (below). |

Never invent a ninth word, hyphenate two, or pick one the record does not support.

### The ops

All in the `task-stack-workstream` change-set shape, each with `reason` (one line a person reads), `confidence`, and `evidence` where the record has one. Propose only for the owner's own or unowned tasks and projects.

- **Next action.** `create` with `title` (a verb first: "Send", "Book", "Chase", "Decide"), `project` (the project id), `due_date` (this week unless the record names a date), `priority` (the project's), `reason`. One per project. Before proposing it, read the project's open tasks: when one already is the next action but is badly titled or undated, propose an `edit` of that task instead.
- **Goal link.** `project_edit` with `set: {"goal_id": <id>}`, when exactly one active goal in the project's domain is plainly what it serves (its name, its description, the goals of its sibling projects). Several plausible goals, or none: a question listing them.
- **Owner.** `project_edit` with `set: {"assignee_contact_id": <the owner's contact>}` when the record says the work is theirs. Another person as owner is the owner's call: a question.
- **Status.** `project_edit` with `set: {"status": "ON_HOLD"}` when the record says it is paused on purpose (the owner wrote so); "IN_PROGRESS" for a NOT_STARTED project that has plainly started.
- **Close.** `project_close` (`status` `CANCELLED` when it stopped mattering, `COMPLETED` when it was done, which needs evidence), with the ops that close or move its open tasks listed **before** it in your return: `cancel` for each open task that died with it, `complete` with evidence for one that was done, `edit` with a new `project_id` for one that still matters elsewhere. The writer refuses a close while any open task remains, and a close without evidence of a project linked to a goal or active in the last 90 days. A project linked to a goal, or one where the evidence is not plain, is a question: "Close <project>? <the evidence>. Its N open tasks would be cancelled."

### Nudges

A nudge is for a `WAITING_ON_PERSON` or `BLOCKED_EXTERNAL` project where a named person owes something and can be asked. The confidence gate: a check-in or status note from the owner in the last 7 days means no nudge; evidence (the mail or task change that shows the ask is open) less than 14 days old means a nudge; older evidence means a question ("Is <name> still the one to chase on <project>? The last word was on <date>") instead.

Each nudge goes in `extra.nudges`, one object per nudge, with exactly the keys of the nudge block productivity's follow-up pass reads, so the same code gates and drafts either:

<!-- NUDGES_JSON_START -->
[{"recipient_email": "...", "recipient_name": "...", "contact_id": "... or null", "thread_ref": "portal://email/... or null", "task_ref": "portal://task/... or null", "project": "...", "ask": "one or two sentences: what to ask for", "why_now": "one sentence", "evidence_date": "YYYY-MM-DD"}]
<!-- NUDGES_JSON_END -->

The main agent turns each into the chase task above, with the nudge's fields in its description, so the owner's follow-up pass can draft it in their voice. You never draft and never send.

### The return

The `orchestration-workstream` block with `workstream: "diagnose-a-batch"`, and:

- `items`: one row per project: `test` `diagnosis`, `item` the project's `portal://project/<id>`, `state` the diagnosis word, `evidence` the reference that decided it, `note` "<the reason>. Smallest step: <step>. Who: <the owner | a name | this pass>. Needs the owner: <yes | no>."
- `extra.ops`: the proposed ops, in the order they must run (task ops before the close of their project).
- `extra.nudges`: the nudges, as above.
- `questions`: `{ask, of: "owner", why, blocks: [the project ref]}`, phrased so the owner can answer "ok", "no" or one word, with your best choice in the question.
- `findings`: what the owner should know that is neither an op nor a question (a project that is plainly two projects, a goal nothing serves).

## Drain a bucket

For a `projects-worker` given the drain batch: bucket tasks (from a domain's catch-all "General Tasks" project) and the open projects of those domains. Read only; write nothing. Number the ops `drain-1`, `drain-2`, ...

For each task, read it (`get`, detail full: title, description, comments, source email, contact) and file it where the work belongs:

- the project the record names (the source email's thread or contact already has open tasks in one project; the note it came from is linked to one; the description names it);
- else the open project of that domain whose name and purpose plainly fit;
- else it stays in the bucket, with the reason in `findings`. Never file a client's work in another client's domain, never into an archived or closed project, and never create a project.

One `edit` op per task moving it, `set: {"project_id": <uuid>, "domain_id": <that project's domain>}`, with a `reason` the owner reads as a comment ("Filed under Monthly close: the bank's thread lives there") and the email or note that decided it as `evidence`. While there, retitle a title that does not start with a verb as the next physical action, keeping every specific and inventing none. Confidence: `high` when the record names the project, `medium` when you chose between plausible projects (the reviewer checks it).

Return the `orchestration-workstream` block with `workstream: "drain-a-bucket"`: `items` one row per task (`test` `filing`, `item` the task ref, `state` `clarified` or `still-open`, `evidence`, `note`), the ops in `extra.ops`, and what stayed and why in `findings`.

## What the stalled projects wait on

For a `projects-worker` given the worklist projects with WAITING tasks. Read only; write nothing. Staleness 7 days; silence 3 business days.

1. `whoami` first, for the owner's timezone.
2. List the WAITING tasks of those projects (`list_entities` task, `filters={"status": "WAITING", "project_id": ...}`, paged to the end). Who is waited on comes from the task's `waiting_on`, its `assigned_agent`, then its title and description; say which signal you used. A WAITING task with nobody named is `WAITING with no counterpart` (usually one to make TODO again or close).
3. For each, whether it has gone quiet: the last mail with that person on the subject (`list_entities` email by contact, `email_bodies` only for the one or two that decide it), and the task's own dates. "Since when" is the date it went WAITING where the record shows it, else its last update.
4. Propose exactly one action per item: a nudge by email (a named person with an address, a clear ask, nothing scheduled with them soon), raise at a named meeting inside 3 days, reassign or escalate (to a person the Portal shows, else "escalate, to whom is the owner's call"), a decision only the owner can make (as a question with the options), or close as no longer needed (with the evidence).

Return the `orchestration-workstream` block with `workstream: "what-the-stalled-projects-wait-on"`: `items` one row per WAITING task (`test` `waiting`, `item` the task ref, `state` the action, `evidence`, `note` who and since when), the nudges in `extra.nudges` in the shape Diagnose a batch gives, decisions in `questions`, and items for projects outside your brief in `findings`.
