---
name: task-stack-clarify
description: "The GTD clarify-and-organize method for one open task in the owner's Insights Portal task stack, loaded after orchestration-workstream and task-stack-workstream by the task-clarify agents: file it in the right project and domain, rewrite it as a verb-first next action, give it the owner, date and status it needs, turn delegated work into WAITING with a follow-up date and a named party, and propose it as one task-stack-apply edit op, or ask one question. For \"clean up my tasks\", start task-clarify-orchestrator."
---

# Clarifying a task

This skill is the method. `orchestration-workstream` is the conduct and the return block; `task-stack-workstream` is the task stack's rules (read only, the owner's own tasks, hand edits stand, the change-set op shape). Read them first, at `~/.claude/skills/<name>/SKILL.md` if they are not loaded. The owner's `TASK-STACK-RULES.md` wins over all three.

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

1. **Is it still a task?** If the record shows it already done, or overtaken (the meeting it prepares happened, the request was withdrawn), it is not clarify work. Propose `complete` or `cancel` only on evidence that meets `task-stack-workstream`'s bar, with the reference; otherwise leave it and say so in `findings` (`for reconcile: ...`), where the nightly reconciliation picks it up. If it is reference or someday material rather than an action, say so in `questions` (`of: owner`): the owner decides whether it stays.
2. **Project and domain.** File it where the work belongs:
   - the project the record names (the source email's thread or contact already has open tasks in one project; the note it came from is linked to one; the description names it). Related tasks can themselves be misfiled (a project renamed under them): follow them only when the project's name and purpose fit the work too;
   - else the open project of the right domain whose name and purpose plainly fit;
   - else, when the domain is clear but no project fits, that domain's catch-all project (`is_general`);
   - when even the domain is unclear (two clients plausible, a person who works with several), ask. An archived or closed project is no home: when the work belongs to one, file it in the catch-all and ask whether to reopen it. One domain per client or relationship: never file a client's work in another client's domain, and never create a project.

   Set `project_id`, and `domain_id` to that project's domain, both as uuids.
3. **The next action.** Rewrite the title as the next physical, visible action, verb first: "Send Acme the signed SOW", not "SOW"; "Call the carrier about the Q4 rate", not "Carrier rates". Keep every specific the old title had; add one only from the record; never invent a figure, a date or a person. One action per task: when the title holds two, keep the first and note the second in `findings`. Keep a leading bracketed tag (such as `[CRM Hygiene] `) as it is. At most 200 characters. A title that already starts with a real action stays as it is.
4. **Owner.** An unowned task gets the owner's contact, unless the text plainly makes it another person's action. In order:
   - an explicit delegation in the record (the owner asked someone to do it): the owner keeps it and it becomes WAITING on that person (step 5);
   - another person's own commitment that the owner merely tracks: WAITING on them, owner kept;
   - otherwise the owner.

   Never set `owner_contact_id` to another person; another person's task is not yours to change.
5. **WAITING.** A task whose next move is someone else's is WAITING. It names the party (`waiting_on_contact_id`, a contact uuid you found with `search` or the task's contact), says why in `waiting_reason` (one line: "Carrier is quoting the Q4 rate"), and its `due_date` is the follow-up date: the date the party promised, when the record has one; else one week from today in the owner's timezone (`whoami`). A WAITING task with no party you can name from the record is a question. A WAITING task whose wait is over (they answered, or the record shows the next step is now the owner's) goes back to TODO with the next action as its title. A wait whose promised date has passed with no answer stays WAITING with that date: it is due for a follow-up, which the follow-up loop chases.
6. **Dates.** A due date comes from the record: a date the task, its email or its meeting states, a deadline the counterparty set, a period end the work serves. A task in a project with a due date or deadline still in the future, and no date of its own, gets the project's date as its latest date, unless the record gives an earlier one. A project date already past is no date for a task: an instantly overdue task helps nobody. Due dates cleared in bulk may be the owner's choice; re-add one only from the record. A task with no date in the record and no dated project keeps none: an invented date is worse than none.
7. **Status.** TODO, IN_PROGRESS when the record shows it started, WAITING as above. Never DONE or CANCELLED by edit.

## What you propose

One `edit` op per task, every change in one `set`, with a `reason` the owner reads as a comment on the task ("Filed under Monthly close; titled as the next action; waits on the bank, follow up 10/12"). Cite the email or note that decided a field in `evidence` when there is one: a `portal://email|note|calendar_event|task|project|goal|document/<uuid>` with the full uuid, never a contact and never an 8-character prefix (look the full id up first). `task-stack-apply` refuses a title that does not start with a verb, a project that is closed or in another domain, and a move to WAITING with no date or no party, so check those before you propose.

Confidence, per `task-stack-workstream`:
- `high`: the record names the project, the date or the person, or the title is a plain rewording of the old one.
- `medium`: you chose between plausible projects, or inferred the party or date from context a reader could doubt. It goes to the checker.
- A guess is not an op. If only the owner can settle it, it is a question: one line they can answer "ok" or with a word, offering your best choice ("File 'Bank letter' under Acme Finance / Monthly close? Otherwise name the project."). Ask about the field you cannot settle and still propose the fields you can.

Fix what is plainly wrong on the task even outside the lenses it was queued for (a title that no longer says the work, a WAITING whose ball is back with the owner), in the same op.

What an earlier agent wrote in a task's description or comment is a lead, not evidence: an op that rests on it alone is `medium`.

A `complete` or `cancel` you are not sure of is a `medium` op, never a guess: the checker reads it independently. Duplicates found in a batch go to `questions` as a proposed merge (the nightly reconciliation merges).

A task already clean on every lens it was queued for needs no op: an `items` row with `state: still-open` and `note: already clear`.

## Items

`items` rows: `test` is the lens it was queued for (`filing`, `next_action`, `no_due_date`, `waiting`), one row per lens; `item` the `portal://task/<id>`; `state` `clarified` (an op fixes it), `asked` (a question), `done` or `overtaken` (a complete or cancel op, or a reconcile note), `still-open` (nothing to change), or `unclear`; `evidence` the reference that decided it; `note` one line.
