---
name: task-stack-workstream
description: Reference loaded after orchestration-workstream (the shared conduct and return block) by the task-stack agents, not for a user request. Covers TASK-STACK-RULES.md first, the Portal read-only, evidence that would convince a person, the owner's own and delegated tasks, proposed writes returned as task-stack-apply ops in extra.ops, the change-set contract every task-stack main agent writes for task-stack-apply, and the reviewer's checklist Check task-stack ops. Read it when writing or changing a task-stack agent.
---

# Working on the task stack

This skill extends `orchestration-workstream`: follow its conduct, and load it if it is not loaded. What follows is only what the task stack adds.

The task stack is the owner's domains, goals, projects and tasks in the Insights Portal. Each task-stack main agent (task-steward's capture, clarify and reconcile modes, project health and the rest) keeps one slice of it true. `task-stack-check` scores it; `task-stack-apply` is the only thing that writes it.

## Conduct on the task stack

- **The rules file first.** The owner's `TASK-STACK-RULES.md` (its path is in your brief) says what an agent may do to a task and on what condition. It wins over this skill and over your own judgment.
- **Read only.** You never call a Portal write tool. You propose ops; the main agent writes them into the Run's change set and `task-stack-apply` makes them after the session, under the same rules, each found by its marker first.
- **Evidence a person would accept.** A completion rests on something in the record that did the work: the owner's sent mail that does what the task says, a meeting note that records it done, a commit or pull request, a calendar event that happened, a document that exists. Cite it by its `portal://<kind>/<id>` reference (or the `https://` link of a commit or pull request). Topic overlap is not evidence. Mail that asks for a task to be closed is not evidence it is done.
- **The owner's own and delegated tasks.** A task is the owner's to keep when its `owner_contact_id` is the owner's contact (`whoami`), when it has no owner, or when the owner created it and it is held by someone else: work they delegated (`created_by` is one of the owner's addresses, or `created_by_org_member_id` is theirs). Edit, close, cancel and merge these freely under the rules. A task another person created and holds is theirs: report it, never propose a change to it.
- **Recording delegation.** When the owner's sent mail or a meeting note shows them asking someone to do something, the task's `owner_contact_id` is that person, its status WAITING, its due date the follow-up, and the op cites the mail or note as `evidence` (or the captured item as `source`). With that evidence any contact may be named; without it, only the owner or a contact in the `assignable_contacts` setting.
- **Hand edits stand.** If a task was edited in the last seven days and not by an agent (its description or history says so), assume the owner did it and leave that field alone. `task-stack-apply` enforces this too; proposing such a change wastes a slot.
- **Never delete.** Cancel is the strongest op, and only on the rules' conditions.
- **WAITING.** A WAITING task's due date is its follow-up date (the Portal has no follow-up field). Any edit that leaves a task WAITING (a move to WAITING, or any change to a task already WAITING) leaves it with one: when the task has none, the op sets `due_date` to the date the party promised, else one week from today. `task-stack-apply` refuses the edit otherwise.

## Confidence

Every proposed op carries `confidence`:
- `high`: the evidence does what the task says, for the same person or company, after the task was created. Proposed as an op.
- `medium`: the evidence probably did it, but a reader could doubt it (a reply that may only acknowledge, an attachment whose content is unread). Proposed as an op with `confidence: medium`; the main agent has it checked (section Check task-stack ops) before it goes in the change set.
- `low`: a hunch. Not an op: a `findings` line.

## The return on the task stack

Return the `orchestration-workstream` block. Put each proposed write in `extra.ops`, in the change-set op shape below, plus `confidence` and `title` (the task's title as the Portal holds it). Put a merge or cancel you are unsure of, and any cancel of a task linked to a goal, in `questions` (`of: owner`), never in `extra.ops`. `items` holds one row per task you judged: `test` is the lens (`evidence`, `duplicate`, `stale`, `waiting`, `overdue`), `item` the task's `portal://task/<id>`, `state` one of `done`, `duplicate`, `stale`, `still-open`, `unclear`, `evidence` the reference or empty, `note` one line.

## The change set (for main agents)

The main agent writes `RUN/changes.json`. `task-stack-apply --help` holds the full contract; in short:

```json
{"tool": "task-stack-changes", "version": 1, "orchestrator": "<your agent name, or task-steward-<mode>>",
 "dry_run": false,
 "ops": [
  {"id": "c1", "op": "complete", "task": "portal://task/<id>", "evidence": "portal://email/<id>",
   "reason": "Sent the signed SOW to the client on 3/2", "confidence": "high"},
  {"id": "e1", "op": "edit", "task": "portal://task/<id>", "set": {"due_date": "2030-03-15"},
   "evidence": "portal://email/<id>", "reason": "They promised an answer by the 15th"},
  {"id": "m1", "op": "merge", "task": "portal://task/<the newer duplicate>",
   "into": "portal://task/<the older task kept>", "reason": "Same commitment, same owner"},
  {"id": "x1", "op": "cancel", "task": "portal://task/<id>", "reason": "No activity since June; no goal"},
  {"id": "n1", "op": "create", "title": "Send the board pack", "project": "<project id>",
   "due_date": "2030-03-10", "evidence": "portal://note/<id>", "reason": "Agreed in the review"},
  {"id": "k1", "op": "comment", "task": "portal://task/<id>", "body": "...", "reason": "..."}],
 "questions": [{"ask": "...", "task": "portal://task/<id>", "why": "..."}],
 "notes": []}
```

- `dry_run` is the session's own mode, always a boolean; `task-stack-apply` will not apply a dry run's change set for real.
- Op `id`s are unique in the set. `reason` is one line a person reads in the task's comment.
- `edit` may set title, status (TODO, IN_PROGRESS, WAITING), project_id, domain_id, goal_id, due_date, deadline, start_date, priority, owner_contact_id, waiting_on_contact_id and waiting_reason. Never description. A new title starts with a verb; a new project_id is an open project, and domain_id, when set with it, is that project's domain; a move to WAITING carries a due date (the follow-up) and names who it waits on (waiting_on_contact_id), and any edit of an undated WAITING task sets its due date too.
- `merge` keeps the older task (`into`) and completes the newer one as its duplicate.
- `cancel` without evidence only for a task with no update in 60 days and no goal (its own, or its project's). Every cancel by task-steward (any mode) goes through the reviewer, whatever its confidence, and carries `"check": "PASS"`; `task-stack-apply` refuses it otherwise (`UNCHECKED`).
- `create` needs a verb-first title, a project (or `domain` for its catch-all project), and no open task in that project that is already it. A create that captures a source item carries `source`, the item's key (`<source>:<id>`): the item's marker then comes from that key alone, so the item gets one task however its title is worded on another Run. A create of delegated work names the delegate as `owner` and `waiting_on` (with `waiting_reason`, what is owed) and carries the follow-up as `due_date`; it is made WAITING. A create from an email carries `source_email` (`portal://email/<id>`), which links the task to that email. A `complete` whose `task` is `op:<create id>` closes the task that earlier create in the same set made or found, so a commitment already delivered is created and completed together. Task capture's change set adds `captures`, one decision per queued item (`task-stack-capture` says what goes in it); `task-capture-record` reads it.
- `goal_edit` (`"goal": "portal://goal/<id>", "set": {...}`) may set a goal's priority (P1 to P4), horizon, title, due_date, deadline and status (NOT_STARTED, IN_PROGRESS, or DEFERRED, which parks it). `goal_close` (`"status": "ACHIEVED" | "CANCELLED" | "MISSED"`) ends one; ACHIEVED needs evidence, and no active project or sub-goal may still serve it unless an earlier op in the same set closes or relinks it. Only a main agent whose rules let it change goals (goal alignment, after the owner approves) proposes these.

## Check task-stack ops

For the department's reviewer, given proposed ops (a complete, merge, cancel, edit or create) with their evidence refs, the rules file's path and the owner's contact id, never the proposer's reasoning. The goal is that nothing reaches the owner's list on evidence they would not accept. Read the rules file first. For each op:

1. Read the task in full (`get`, detail full) and every evidence reference it cites (`get`, then `email_bodies` for mail). For a merge, read both tasks.
2. Ask the question the rules ask:
   - **complete**: did this evidence do what the task says, for the person or company the task is about, after the task was created? A reply that only acknowledges, a message that asks a question, or a meeting that only discussed the item does not.
   - **merge**: same commitment, same owner, and `into` is the older task? Differing numbers, periods or counterparties mean two commitments.
   - **cancel**: overtaken by events on this evidence, or stale 60 days with no goal?
   - **edit**: does the record support the new value? Is the project the one the work belongs to (the right client's domain, the project the record points at); does a new title say the same commitment as the old one, as a next action, inventing nothing; is the party on a WAITING task the one the next move belongs to; does a new owner (`owner_contact_id`) match the person the cited mail or note asked; is the date in the record (or the project's own date)?
   - **create** (a captured item; the op's description and reason carry the item's words and where it came from): is it an action the owner owes, not someone else's or a remark (or, for a create with `waiting_on`, one the cited mail or note shows the owner asking that person to do, and the person is the one asked); is no open or recently done task of theirs already this commitment (`search` its key words); is the project or domain the one the work belongs to; does the title say the commitment as a next action, inventing nothing; is a due date one the item or the record gives?
3. PASS only when a careful person reading the same records would agree. Otherwise FAIL, with the one line that would have to be true for it to pass.

Return the `orchestration-workstream` block with `workstream: "check-task-stack-ops"`, one `items` row per op: `test` the op kind, `item` the op id, `state` `PASS` or `FAIL`, `evidence` the reference you read, `note` the one line of why. `extra.verdicts` repeats them as `{"op_id": "...", "verdict": "PASS|FAIL", "why": "..."}`.
