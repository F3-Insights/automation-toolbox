---
name: weekly-review-workstream
description: "The GTD weekly review's method, loaded by gtd-weekly-review and by the productivity-worker it dispatches, not for a user request; adds to orchestration-workstream and task-stack-workstream. Covers the pack and approve passes, the review item contract (one line the owner reads, the verbs they answer with, the task-stack-apply ops each verb makes), how to propose for an overdue, stale, WAITING or someday task, parking as someday/maybe, and the section Triage a batch. For the review itself, start gtd-weekly-review."
---

# Working on the weekly review

This skill extends `orchestration-workstream` and `task-stack-workstream`: keep their conduct and return their block. Load them if they are not loaded. What follows is only what the weekly review adds.

The weekly review is the owner's GTD sweep, prepared so they can settle the week in thirty minutes by answering one numbered list, "1) ok 2) park 3) no". Nothing they do not approve is ever written: after they answer, the finish step applies exactly the ops of each approved verb through `task-stack-apply`. So the proposals are the whole value. A proposal they cannot judge from one line is a proposal they answer `no`. Bias to action: propose what the record supports without hedging. A good pack is short: at most about forty items; the nightly passes (reconcile, clarify) handle the long tail, and the pack says how many were left to them.

## What you have

- `RUN/pass.json`: the week (Monday to Sunday, next week, the previous week), the pass (`pack`, `approve` or `auto`, resolved before the session), the weekly-review home and the week's folder.
- `RUN/inputs/` (pack pass), gathered by `productivity-weekly-review-gather` read only from the Portal: `stack.json` (the trust score, with last week under `baseline`), `projects.json` (each active project's next action or gap), `waiting.json`, `tasks.json` (overdue, stale and someday-candidate tasks, and `queue`, the ones picked for this week's answer), `calendar.json` (next week's meetings and overlaps), `said.json`, `cadence.json`, `carried.json` (last week's unsettled items).
- `RUN/answers.json` and `RUN/review.json` (approve pass): the published review and a preview of how each answer resolves.
- The owner's `TASK-STACK-RULES.md` and `WEEKLY-REVIEW-RULES.md` (paths in the Run's inputs). Read both first; they override this skill. The weekly rules carry the cadence (monthly pulse, quarterly review, the reflection question) and where the pack goes.
- The Portal, read only. `RUN` is the working folder; only the main agent writes there, by absolute path.

The pack shows, in this order: the trust score against last week and what moved; each active project's next action or its gap; what the owner waits on and which follow-ups are overdue or due by next Sunday; overdue and stale tasks; tasks to park; next week's calendar load and conflicts; what the time study heard promised and never saw kept; the decisions only the owner can make; the cadence (in the month's last review, a pointer to the monthly goal alignment) and the reflection question.

## Steps

For `gtd-weekly-review`.

1. [judgment] Orient. Read the rules files, `RUN/pass.json` and every input. Note the score and what moved, projects with a gap, follow-ups due, the queue, the conflicts. Items in `carried.json` come first, back as items where they still matter.
   → approve pass: step 6
2. [hand-off: productivity-worker] Triage. Batches of about ten from `tasks.json`'s queue and the WAITING tasks whose follow-up is overdue, due, or missing on a P1 or P2, all at once, never one task twice, each told to follow section Triage a batch. One more worker on `waiting-on-tracker-method`, threads lens, silence window 3 business days. Save each return as `RUN/returns/<name>.json` as it arrives.
3. [judgment] Decide. Build the items from the returns and inputs: the triage items, with your edits where a proposal is weak; a `projects` item per active project with no next action that matters this week (a `create` op with a verb-first next action, or leave or park the project); a `waiting` item per follow-up worth sending (record-only unless a task changes: drafting nudges is the follow-up job's); a `calendar` item per conflict next week (record-only letters naming both meetings); a `said` item per open said-but-not-seen commitment (a `create` op, or `no`); `decisions` for what only the owner can settle. The monthly pulse and the quarterly review belong to the goal alignment; in its week the cadence note names it.
4. [judgment] Write `RUN/review.json`: `summary` (three to five lines: the week in one breath, the score and its direction, the one thing that most needs them), `notes` per section (what the numbers mean, never a repeat of them), `reflection` (from the rules file), `items`.
5. [script] Render: `productivity-weekly-review-pack RUN`. Fix `review.json` until it prints `VALID`, then read `RUN/PACK.md` once as the owner would: cut what they do not need, sharpen what they cannot judge.
   → problems: step 4 (max 3)
   → VALID: step 7
6. [judgment] Approve pass. Read the preview; report how many items each answer settled, what will be applied, and each answer that cannot be applied (modified, unclear, a verb the item does not offer), quoting their words, so they can answer it again. Write nothing else.
7. [judgment] Report as the Automation asks. The finish step publishes and applies; you publish nothing.
   → reported: done

Done is computed: `productivity-weekly-review-check WEEK` tests the pack, its publication, the answers and what was applied. Before the session the Automation runs `productivity-weekly-review-gather --run RUN`; after it `productivity-weekly-review-changes --run RUN`, `task-stack-apply --run RUN` and `productivity-weekly-review-publish --run RUN` (each takes `--dry-run-if`). A dry run writes `"dry_run": true` in `review.json`, and nothing is published or applied. With no one present everything runs the same: what only the owner can decide is an item, never a wait.

## The item

Each thing proposed is one review item:

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
- `proposal` is one sentence the owner agrees with or not, with the date, the person or the project in it. "Review this" is not a proposal.
- `why` is the fact from the record that makes it right, in one line.
- `options` maps each verb to the task-stack-apply ops it would make (`task-stack-workstream` has the op shape; leave out `id` and `reason`, the pack fills them). Verbs: `ok` (do the proposal), `done` (complete; evidence required), `cancel`, `waiting` (WAITING with a follow-up date, which is the due date, and the party), `park`. `no` is always offered and never writes; do not list it.
- A choice between alternatives uses letters `a` to `f`, each with a label in `choices` and its ops in `options` (an empty list records the answer without writing).
- `default` is the verb or letter `ok` means for this item.

## Proposing for a task

- **Overdue.** Done on the evidence: offer `done` with the evidence as the default. Still wanted: a realistic new due date (`ok`). Overtaken: `cancel` with the evidence. Dead and goalless: `park`.
- **Stale.** Untouched for a month: they still mean it (a date) or do not (park). Say which, and why.
- **WAITING.** A follow-up date passed or is missing: the follow-up date and the party (`ok` as an edit of `due_date`, `waiting_on_contact_id` or `waiting_reason`), or `done` if the answer came.
- **Someday candidates.** No goal, long untouched or long overdue: `park` is the default.

Only the owner's own tasks and unowned ones; another person's task is a `findings` line.

## Park

The Portal has no someday/maybe list. The pack adds parking by itself to every item with a `task`: the title gains `[Someday] `, status TODO, due date cleared, with a comment saying the weekly review parked it. Write park ops yourself only when an item needs something different.

## Triage a batch

For `productivity-worker`. Brief: the task refs and titles, the week, the owner's contact id, the rules files' paths, the instructions that apply; nothing of the main agent's view.

For each task, find what is true of it now and propose the one action that makes the list true again:

1. Read it with `get` (full): title, description, comments, project, goal, dates, owner.
2. Look for what happened since: the owner's sent mail and meeting notes on its subject or with its person (`search`, `email_bodies` for the two or three that matter), its project's activity. Evidence that did the work is a `done` option with that evidence, and the default. Topic overlap is not evidence.
3. Otherwise decide whether it matters this month (a goal, a deadline, a person waiting, a P1 or P2). If so, a date they can keep (look at what else falls due that week in the batch) and why. If not, `park`.
4. Someone else's move is a WAITING proposal with the follow-up date and the party, not a new due date.
5. A task owned by another person: a `findings` line, no item.

When the record cannot decide, say what is missing in `why` and default to `no`. Write nothing.

Return the `orchestration-workstream` block with one item per task in `extra.items`; `items` holds one row per task judged (`test` the section, `item` the task ref, `state` `proposed` or `skipped`, `evidence`, `note`).

## The commands

`productivity-weekly-review-gather` (before the session), `productivity-weekly-review-pack` and `productivity-weekly-review-check` (in it), `productivity-weekly-review-changes` and `productivity-weekly-review-publish` (after it, around `task-stack-apply`). Every task write, the review task included, goes through `task-stack-apply`. Settings: `state_dir`, `portal_mcp_config`, and `[weekly-review-workstream] review_project` or `review_domain` for the review task.
