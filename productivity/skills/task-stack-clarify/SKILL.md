---
name: task-stack-clarify
description: "The daily GTD clarify pass, run by task-steward in mode clarify and by the productivity-worker it dispatches; also the method for clarifying one open task by hand. Files each open Insights Portal task in the right project and domain, rewrites it as a verb-first next action, gives it the owner, date and status it needs, turns delegated work into WAITING with a follow-up date and a named party, and proposes it as one task-stack-apply edit op, or asks one question. Covers the Run's Steps and the section Clarify a batch. Use for \"clean up my task list\". Not for finding done tasks (task-stack-reconcile) or new commitments (task-stack-capture)."
---

# Clarifying a task

Every open task on the owner's list is one they can work from without opening it. `orchestration-workstream` is the conduct and the return block; `task-stack-workstream` is the task stack's rules (read only, the owner's own and delegated tasks, hand edits stand, the change-set op shape); load them first. The owner's `TASK-STACK-RULES.md` wins over all three.

## What the Run has

- `RUN/queue.json`, picked by `task-stack-queue` from `RUN/before.json`: the owner's own and unowned tasks flagged on the clarify components (`filing`, `next_action`, `no_due_date`, `waiting`), worst domain first, highest priority then oldest, capped at max changes, in batches `b1`, `b2`, ... of 25, each with its lenses and their reasons; `deferred` is the backlog for later Runs. Never widen it.
- `RUN/before.json`: the score per component and per domain. If either file is missing (`STALE`), read the owner's open tasks yourself with `list_entities`, pick at most max changes the same way, and say so.
- Inputs: domain (optional, default every domain, worst first), max changes (default 50), instructions, dry run.

After the session `task-stack-apply` makes the change set, and `task-stack-check` and `task-stack-report` score the stack again. The four components must not get worse, and the tasks touched must be clean on them.

## Steps

1. [judgment] Orient. `whoami`; read the rules file, `RUN/queue.json` and the four components' numbers in `RUN/before.json`.
   → nothing queued: step 6
2. [judgment] Read once the domains the queue touches (`list_entities` domain, then `hierarchy` or the project listing), so each batch gets its domain's open projects and catch-all project. Write `RUN/plan.json`: the batches, each task with its lenses, the project lists.
3. [hand-off: productivity-worker] Clarify. One worker (model opus) per batch, in parallel, never two on one task, told to follow this skill's section Clarify a batch, with the batch's tasks as `queue.json` holds them, their domains' projects, the owner's contact id and timezone, today's date, the rules file's path and the batch id as op-id prefix. With one batch, clarify it yourself. Save each return as `RUN/returns/<batch>.json`; a reply without the json block goes back once for it.
4. [hand-off: productivity-reviewer] Check every `medium` op and every `complete` or `cancel`, told to use `task-stack-workstream`'s section Check task-stack ops, with the ops only, the rules file's path and the owner's contact id. A FAIL drops the op and, when the worker had a best guess, turns it into a question. A cancel that passed carries `"check": "PASS"`.
5. [judgment] Write `RUN/changes.json` in the `task-stack-workstream` shape with `"orchestrator": "task-steward-clarify"` and `dry_run` as this Run is, from the `high` ops and the passed ones: one op per task (two lenses' edits merged into one `set`), at most max changes in queue order, no op that sets a field to the value it holds; each question one line in `questions`, `{"ask", "task", "why"}`, answerable "ok" or with one word, your best choice in it.
6. [judgment] Report how many tasks were filed, retitled, dated and moved to WAITING, the questions as one numbered list, the tasks left for the reconcile mode, what could not be judged and why, the backlog (`deferred`) per domain, and before.json's score. Never claim a score change.
   → reported: done

## The standard

A clarified task can be worked from the list without opening it. It sits in the project it belongs to, in that project's domain. Its title says the next physical action, starting with a verb, and keeps the specifics (who, what, which period, which amount). It has a due date when a date governs it. If it waits on someone, it is WAITING, names the person it waits on, and its due date is the day to follow up.

Decide on the record, not on a hunch. Act on what the record supports. Ask only what the record cannot answer and only the owner can.

## What you read

For each task (`get`, detail `full`):
- its title, description, comments, `source` and `source_reference`;
- its links: the email it came from (`email_id`, or a `portal://email/...` in the description or source reference), its `task_contact_id`, any note or meeting it was captured from;
- its project and domain, if it has them, and its dates, status and owner.

Then, as needed: the contact (`get` contact: company, recent mail, open tasks and their projects), the email (`email_bodies` for the one or two that matter), and the domain's tree (`hierarchy`, or `list_entities` project filtered on the domain) to see the projects that exist. Read what settles the question and stop; a batch is many tasks.

## The decisions, in order

1. **Is it still a task?** If the record shows it already done, or overtaken (the meeting it prepares happened, the request was withdrawn), it is not clarify work. Propose `complete` or `cancel` only on evidence that meets `task-stack-workstream`'s bar, with the reference; otherwise leave it and say so in `findings` (`for reconcile: ...`), where the reconcile mode picks it up. If it is reference or someday material rather than an action, say so in `questions` (`of: owner`): the owner decides whether it stays.
2. **Project and domain.** File it where the work belongs:
   - the project the record names (the source email's thread or contact already has open tasks in one project; the note it came from is linked to one; the description names it). Related tasks can themselves be misfiled (a project renamed under them): follow them only when the project's name and purpose fit the work too;
   - else the open project of the right domain whose name and purpose plainly fit;
   - else, when the domain is clear but no project fits, that domain's catch-all project (`is_general`);
   - when even the domain is unclear (two clients plausible, a person who works with several), ask. An archived or closed project is no home: when the work belongs to one, file it in the catch-all and ask whether to reopen it. One domain per client or relationship: never file a client's work in another client's domain, and never create a project.

   Set `project_id`, and `domain_id` to that project's domain, both as uuids.
3. **The next action.** Rewrite the title as the next physical, visible action, verb first: "Send Acme the signed SOW", not "SOW"; "Call the carrier about the Q4 rate", not "Carrier rates". Keep every specific the old title had; add one only from the record; never invent a figure, a date or a person. One action per task: when the title holds two, keep the first and note the second in `findings`. Keep a leading bracketed tag (such as `[CRM Hygiene] `) as it is. At most 200 characters. A title that already starts with a real action stays as it is.
4. **Owner.** An unowned task gets the owner's contact, unless the text plainly makes it another person's action. In order:
   - an explicit delegation in the record (the owner asked someone to do it): `owner_contact_id` becomes that person, citing the mail or note as `evidence`, and it becomes WAITING on them (step 5);
   - another person's own commitment that the owner merely tracks: WAITING on them, owner kept;
   - otherwise the owner.

   Set `owner_contact_id` to another person only on a record of the owner asking them. A task another person created and holds is theirs, not yours to change; one the owner created and handed to someone is delegated and yours to keep true.
5. **WAITING.** A task whose next move is someone else's is WAITING. It names the party (`waiting_on_contact_id`, a contact uuid you found with `search` or the task's contact), says why in `waiting_reason` (one line: "Carrier is quoting the Q4 rate"), and its `due_date` is the follow-up date: the date the party promised, when the record has one; else one week from today in the owner's timezone (`whoami`). A WAITING task with no party you can name from the record is a question. A WAITING task whose wait is over (they answered, or the record shows the next step is now the owner's) goes back to TODO with the next action as its title. A wait whose promised date has passed with no answer stays WAITING with that date: it is due for a follow-up, which the follow-up loop chases.
6. **Dates.** A due date comes from the record: a date the task, its email or its meeting states, a deadline the counterparty set, a period end the work serves. A task in a project with a due date or deadline still in the future, and no date of its own, gets the project's date as its latest date, unless the record gives an earlier one. A project date already past is no date for a task: an instantly overdue task helps nobody. Due dates cleared in bulk may be the owner's choice; re-add one only from the record. A task with no date in the record and no dated project keeps none: an invented date is worse than none.
7. **Status.** TODO, IN_PROGRESS when the record shows it started, WAITING as above. Never DONE or CANCELLED by edit.

## What you propose

One `edit` op per task, every change in one `set`, with a `reason` the owner reads as a comment on the task ("Filed under Monthly close; titled as the next action; waits on the bank, follow up 10/12"). Cite the email or note that decided a field in `evidence` when there is one: a `portal://email|note|calendar_event|task|project|goal|document/<uuid>` with the full uuid, never a contact and never an 8-character prefix (look the full id up first). `task-stack-apply` refuses a title that does not start with a verb, a project that is closed or in another domain, and any edit that leaves a task WAITING with no date or no party (including a refiling of a task already WAITING and undated: set its follow-up date in the same op), so check those before you propose.

Confidence, per `task-stack-workstream`:
- `high`: the record names the project, the date or the person, or the title is a plain rewording of the old one.
- `medium`: you chose between plausible projects, or inferred the party or date from context a reader could doubt. It goes to the reviewer.
- A guess is not an op. If only the owner can settle it, it is a question: one line they can answer "ok" or with a word, offering your best choice ("File 'Bank letter' under Acme Finance / Monthly close? Otherwise name the project."). Ask about the field you cannot settle and still propose the fields you can.

Fix what is plainly wrong on the task even outside the lenses it was queued for (a title that no longer says the work, a WAITING whose ball is back with the owner), in the same op.

What an earlier agent wrote in a task's description or comment is a lead, not evidence: an op that rests on it alone is `medium`.

A `complete` or `cancel` you are not sure of is a `medium` op, never a guess: the reviewer reads it independently. Duplicates found in a batch go to `questions` as a proposed merge (the reconcile mode merges).

A task already clean on every lens it was queued for needs no op: an `items` row with `state: still-open` and `note: already clear`.

## Items

`items` rows: `test` is the lens it was queued for (`filing`, `next_action`, `no_due_date`, `waiting`), one row per lens; `item` the `portal://task/<id>`; `state` `clarified` (an op fixes it), `asked` (a question), `done` or `overtaken` (a complete or cancel op, or a reconcile note), `still-open` (nothing to change), or `unclear`; `evidence` the reference that decided it; `note` one line.

## Clarify a batch

For a `productivity-worker` given one batch (or task-steward clarifying a single batch itself). Read the rules file first. Decide every task by the standard and the decisions above, from the record, read only; write nothing. Number your ops `<prefix>-1`, `<prefix>-2`, ... from the op-id prefix in your brief.

Return the `orchestration-workstream` block with `workstream: "clarify-a-batch"`:
- `items`: one row per task and lens, as Items says;
- `extra.ops`: the proposed ops in the change-set shape, each with `confidence` and the task's current `title`;
- `questions`: `ask` one line with your best choice in it, `of: owner`, `why` saying what the answer changes, and `blocks` holding the task's `portal://task/<id>`;
- `findings`: tasks for the reconcile mode, titles holding two actions, anything the owner should know (a domain with no catch-all project, a contact with two records);
- `notes`: what you could not read and why.

Every task in the batch appears in `items`. Never return prose without the block.
