---
name: weekly-review-workstream
description: Reference loaded last by the weekly-review agents, not for a user request; adds to orchestration-workstream and task-stack-workstream. Covers the review item contract (one line the owner reads, the verbs they answer with, the task-stack-apply ops each verb makes), how to propose for an overdue, stale, WAITING or someday task, and parking as someday/maybe. For the review itself, start weekly-review-orchestrator.
---

# Working on the weekly review

This skill extends `orchestration-workstream` and `task-stack-workstream`: follow both. Read them at `~/.claude/skills/<name>/SKILL.md` if they are not loaded. What follows is only what the weekly review adds.

The weekly review is the owner's GTD sweep, prepared so they can settle the week in thirty minutes by answering one numbered list. Nothing they do not approve is ever written: the approval pass applies exactly the ops of the verb they answered, through `task-stack-apply`. So the proposals are the whole value. A proposal they cannot judge from one line is a proposal they answer `no`.

## The item

Each thing proposed is one review item, returned in `extra.items`:

```json
{"section": "overdue", "task": "portal://task/<uuid>", "task_title": "<the title as the Portal holds it>",
 "title": "<what the item is about, at most 160 characters>",
 "proposal": "Move the due date to 2030-03-08",
 "why": "The client asked for Friday (their mail of 3/1)",
 "evidence": "portal://email/<uuid>",
 "default": "ok",
 "options": {"ok": [{"op": "edit", "task": "portal://task/<uuid>", "set": {"due_date": "2030-03-08"}}],
             "done": [{"op": "complete", "task": "portal://task/<uuid>", "evidence": "portal://email/<uuid>"}]}}
```

- `section`: `overdue` (overdue or stale), `someday`, `waiting`, `projects`, `calendar`, `said` or `decisions`.
- `proposal` is one sentence the owner reads and agrees with or not, with the date, the person or the project in it. "Review this" is not a proposal.
- `why` is the fact that makes the proposal right, in one line, from the record.
- `options` maps each verb the item offers to the task-stack-apply ops it would make (`task-stack-workstream` has the op shape; leave out `id` and `reason`, the pack fills them). The verbs: `ok` (do the proposal), `done` (complete it; evidence required), `cancel`, `waiting` (WAITING with a follow-up date, which is the due date, and the party), `park`. `no` is always offered and never writes; do not list it.
- A choice between alternatives uses letters `a` to `f`, each with a label in `choices` and its ops in `options` (an empty list records their answer without writing anything).
- `default` is the verb or letter `ok` means for this item.

## Proposing for a task

- **Overdue.** Decide what is true now. Done on the evidence: offer `done` with the evidence and make it the default. Still wanted: a realistic new due date (`ok`). Overtaken: `cancel` with the evidence. Dead and goalless: `park`.
- **Stale.** Untouched for a month: they either still mean it (give it a date) or do not (park it). Say which, and why.
- **WAITING.** A follow-up date passed or is missing: the follow-up date and the party (`ok` as an edit of `due_date`, `waiting_on_contact_id` or `waiting_reason`), or `done` if the answer came.
- **Someday candidates.** No goal, long untouched or long overdue: `park` is the default.
- **Meetings next week** (the orchestrator's): the time-weighted questions the calendar raises, each meeting tagged in the note as advancing a goal, defending a commitment, or low signal.

Only the owner's own tasks and unowned ones; another person's task is a `findings` line.

## Park

The Portal has no someday/maybe list. Parking is an edit the pack adds by itself to every item with a `task`: the title gains `[Someday] `, the status goes to TODO and the due date is cleared, with a comment saying the weekly review parked it. Write park ops yourself only when an item needs something different.

## The return

The `orchestration-workstream` block, with the items in `extra.items`. `items` holds one row per task judged (`test` the section, `item` the task ref, `state` `proposed` or `skipped`, `evidence`, `note`). A task that could not be judged is a `findings` line, not an item.

## The scripts

In `scripts/`, run as `python3 ~/.claude/skills/weekly-review-workstream/scripts/<name>.py`: `weekly_review_gather.py` (before the session), `weekly_review_pack.py` and `weekly_review_check.py` (in it), `weekly_review_changes.py` and `weekly_review_publish.py` (after it, around `task_stack_apply.py`). Every task write, the review task included, goes through `task_stack_apply.py`. Settings: `state_dir`, `portal_mcp_config`, and `[weekly-review-workstream] review_project` or `review_domain` for the review task.
