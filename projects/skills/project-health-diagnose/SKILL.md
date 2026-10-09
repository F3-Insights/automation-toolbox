---
name: project-health-diagnose
description: "Method loaded by project-health-diagnoser after orchestration-workstream and task-stack-workstream, not for a user request: diagnosing one Portal project in one word from a closed list of eight, the one smallest step that unblocks it, and the fixes that make it trustworthy (a goal link, a next action, an owner) as task-stack-apply ops; nudges for people who owe something; when a project is dead and how it closes. Read it when changing how projects are judged; for the weekly pass, start project-health-orchestrator."
---

# Diagnosing a project

Load the skills `orchestration-workstream` and then `task-stack-workstream` first, by name: the conduct, the return block, the owner's rules file and the change-set op shapes come from them. This skill is the method for one project.

## The standard

An active project the owner can trust says three things without being opened: what it serves (a **goal**), what happens next (a **next action**: an open TODO or IN_PROGRESS task, or a WAITING task with its follow-up date as its due date), and who does it (an **owner**: the project's assignee or the owner of an open task). And something has happened on it recently. When one of those is missing, the fix is usually small, and it is yours to propose. When the project has stopped, the job is to say why in one word and name the one smallest step that would start it again.

The check tool has already done the arithmetic. Each project in your brief comes from `project-health-check` with its state (`stalled`, `dead`, `gaps`), its gaps (`no_goal`, `no_next_action`, `no_owner`, `stale`), its idle days and last activity (bulk edits to the records are not counted as activity), its open, waiting and overdue task counts and its next actions. Do not recount; read the record for what the numbers cannot say.

## The work, per project

1. **Read it.** `get(entity_type="project", id_or_query=<id>, detail="full")`: the record, its tasks, notes and hierarchy. Then what explains it: the latest notes on it (a check-in or status note from the owner is the most authoritative thing there is; one from the last 7 days means they are managing it, so you propose no nudge and say so), mail with its key contacts in the last 30 days (`list_entities` email by contact, `email_bodies` only for the few that decide it), and `activity_stream` for its company if it has one. Keep reads small: `limit` 25, `detail="summary"` unless a record is known to be small.
2. **Diagnose.** Exactly one word from the closed list below, with the one-line reason that word must carry.
3. **The smallest step.** The least that would change the diagnosis. Not the plan, the next move: who takes it, and whether it needs the owner.
4. **Fix the gaps** the record lets you fix, as ops (below).
5. **Propose** the ops, the nudges and the questions. Everything goes in your return; you write nothing.

## The diagnoses (closed list)

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

## The ops

All in the `task-stack-workstream` change-set shape, each with `reason` (one line a person reads), `confidence`, and `evidence` where the record has one. Propose only for the owner's own or unowned tasks and projects.

- **Next action.** `create` with `title` (a verb first: "Send", "Book", "Chase", "Decide"), `project` (the project id), `due_date` (this week unless the record names a date), `priority` (the project's), `reason`. One per project. Before proposing it, read the project's open tasks: when one already is the next action but is badly titled or undated, propose an `edit` of that task instead.
- **Goal link.** `project_edit` with `set: {"goal_id": <id>}`, when exactly one active goal in the project's domain is plainly what it serves (its name, its description, the goals of its sibling projects). Several plausible goals, or none: a question listing them.
- **Owner.** `project_edit` with `set: {"assignee_contact_id": <the owner's contact>}` when the record says the work is theirs. Another person as owner is the owner's call: a question.
- **Status.** `project_edit` with `set: {"status": "ON_HOLD"}` when the record says it is paused on purpose (the owner wrote so); "IN_PROGRESS" for a NOT_STARTED project that has plainly started.
- **Close.** `project_close` (`status` `CANCELLED` when it stopped mattering, `COMPLETED` when it was done, which needs evidence), with the ops that close or move its open tasks listed **before** it in your return: `cancel` for each open task that died with it, `complete` with evidence for one that was done, `edit` with a new `project_id` for one that still matters elsewhere. The writer refuses a close while any open task remains, and a close without evidence of a project linked to a goal or active in the last 90 days. A project linked to a goal, or one where the evidence is not plain, is a question: "Close <project>? <the evidence>. Its N open tasks would be cancelled."

## Nudges

A nudge is for a `WAITING_ON_PERSON` or `BLOCKED_EXTERNAL` project where a named person owes something and can be asked. The confidence gate: a check-in or status note from the owner in the last 7 days means no nudge; evidence (the mail or task change that shows the ask is open) less than 14 days old means a nudge; older evidence means a question ("Is <name> still the one to chase on <project>? The last word was on <date>") instead.

Each nudge goes in `extra.nudges`, one object per nudge, with exactly the keys of the nudge block `waiting-on-tracker` and the comms skills share, so the same code gates and drafts either:

<!-- NUDGES_JSON_START -->
[{"recipient_email": "...", "recipient_name": "...", "contact_id": "... or null", "thread_ref": "portal://email/... or null", "task_ref": "portal://task/... or null", "project": "...", "ask": "one or two sentences: what to ask for", "why_now": "one sentence", "evidence_date": "YYYY-MM-DD"}]
<!-- NUDGES_JSON_END -->

The orchestrator turns each into the chase task above, with the nudge's fields in its description, so the follow-up pass (`comms-follow-ups`) can draft it in the owner's voice after `outbound-check`. You never draft and never send.

## The return

The `orchestration-workstream` block, with:

- `items`: one row per project: `test` `diagnosis`, `item` the project's `portal://project/<id>`, `state` the diagnosis word, `evidence` the reference that decided it, `note` "<the reason>. Smallest step: <step>. Who: <the owner | a name | this pass>. Needs the owner: <yes | no>."
- `extra.ops`: the proposed ops, in the order they must run (task ops before the close of their project).
- `extra.nudges`: the nudges, as above.
- `questions`: `{ask, of: "owner", why, blocks: [the project ref]}`, phrased so the owner can answer "ok", "no" or one word, with your best choice in the question.
- `findings`: what the owner should know that is neither an op nor a question (a project that is plainly two projects, a goal nothing serves).
