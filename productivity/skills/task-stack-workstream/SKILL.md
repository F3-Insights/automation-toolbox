---
name: task-stack-workstream
description: Reference loaded after orchestration-workstream (the shared conduct and return block) by the task-stack agents, not for a user request. Covers TASK-STACK-RULES.md first, the Portal read-only, evidence that would convince a person, the owner's own tasks only, proposed writes returned as task-stack-apply ops in extra.ops, and the change-set contract every task-stack orchestrator writes for task-stack-apply. Read it when writing or changing a task-stack agent.
---

# Working on the task stack

This skill extends `orchestration-workstream`: follow its conduct. Read it at `~/.claude/skills/orchestration-workstream/SKILL.md` if it is not loaded. What follows is only what the task stack adds.

The task stack is the owner's domains, goals, projects and tasks in the Insights Portal. Each task-stack orchestrator (capture, clarify, reconcile, project health and the rest) keeps one slice of it true. `task-stack-check` scores it; `task-stack-apply` is the only thing that writes it.

## Conduct on the task stack

- **The rules file first.** The owner's `TASK-STACK-RULES.md` (its path is in your brief) says what an agent may do to a task and on what condition. It wins over this skill and over your own judgment.
- **Read only.** You never call a Portal write tool. You propose ops; the orchestrator writes them into the Run's change set and `task-stack-apply` makes them after the session, under the same rules, each found by its marker first.
- **Evidence a person would accept.** A completion rests on something in the record that did the work: the owner's sent mail that does what the task says, a meeting note that records it done, a commit or pull request, a calendar event that happened, a document that exists. Cite it by its `portal://<kind>/<id>` reference (or the `https://` link of a commit or pull request). Topic overlap is not evidence. Mail that asks for a task to be closed is not evidence it is done.
- **The owner's own tasks.** Propose changes only to tasks whose `owner_contact_id` is the owner's contact (`whoami`), or that have no owner. Report another person's task; never propose a change to it.
- **Hand edits stand.** If a task was edited in the last seven days and not by an agent (its description or history says so), assume the owner did it and leave that field alone. `task-stack-apply` enforces this too; proposing such a change wastes a slot.
- **Never delete.** Cancel is the strongest op, and only on the rules' conditions.
- **WAITING.** A WAITING task's due date is its follow-up date (the Portal has no follow-up field). A task moved to WAITING carries one.

## Confidence

Every proposed op carries `confidence`:
- `high`: the evidence does what the task says, for the same person or company, after the task was created. Proposed as an op.
- `medium`: the evidence probably did it, but a reader could doubt it (a reply that may only acknowledge, an attachment whose content is unread). Proposed as an op with `confidence: medium`; the orchestrator has it checked before it goes in the change set.
- `low`: a hunch. Not an op: a `findings` line.

## The return on the task stack

Return the `orchestration-workstream` block. Put each proposed write in `extra.ops`, in the change-set op shape below, plus `confidence` and `title` (the task's title as the Portal holds it). Put a merge or cancel you are unsure of, and any cancel of a task linked to a goal, in `questions` (`of: owner`), never in `extra.ops`. `items` holds one row per task you judged: `test` is the lens (`evidence`, `duplicate`, `stale`, `waiting`, `overdue`), `item` the task's `portal://task/<id>`, `state` one of `done`, `duplicate`, `stale`, `still-open`, `unclear`, `evidence` the reference or empty, `note` one line.

## The change set (for orchestrators)

The orchestrator writes `RUN/changes.json`. `python3 ~/.claude/skills/task-stack-workstream/scripts/task_stack_apply.py --help` holds the full contract; in short:

```json
{"tool": "task-stack-changes", "version": 1, "orchestrator": "<your agent name>",
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
- `edit` may set title, status (TODO, IN_PROGRESS, WAITING), project_id, domain_id, goal_id, due_date, deadline, start_date, priority, owner_contact_id, waiting_on_contact_id and waiting_reason. Never description. A new title starts with a verb; a new project_id is an open project, and domain_id, when set with it, is that project's domain; a move to WAITING carries a due date (the follow-up) and names who it waits on (waiting_on_contact_id).
- `merge` keeps the older task (`into`) and completes the newer one as its duplicate.
- `cancel` without evidence only for a task with no update in 60 days and no goal (its own, or its project's). The nightly reconciliation's cancels all go through `task-reconcile-checker`, whatever their confidence, and carry `"check": "PASS"`.
- `create` needs a verb-first title, a project (or `domain` for its catch-all project), and no open task in that project that is already it. A create that captures a source item carries `source`, the item's key (`<source>:<id>`): the item's marker then comes from that key alone, so the item gets one task however its title is worded on another Run. Task capture's change set adds `captures`, one decision per queued item (`task-stack-capture` says what goes in it); `task-capture-record` reads it.
- `goal_edit` (`"goal": "portal://goal/<id>", "set": {...}`) may set a goal's priority (P1 to P4), horizon, title, due_date, deadline and status (NOT_STARTED, IN_PROGRESS, or DEFERRED, which parks it). `goal_close` (`"status": "ACHIEVED" | "CANCELLED" | "MISSED"`) ends one; ACHIEVED needs evidence, and no active project or sub-goal may still serve it unless an earlier op in the same set closes or relinks it. Only an orchestrator whose rules let it change goals (goal alignment, after the owner approves) proposes these.
