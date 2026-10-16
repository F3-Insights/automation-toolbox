---
name: task-stack-reconcile
description: "The nightly truth pass over the owner's Insights Portal task stack, run by task-steward in mode reconcile and by the productivity-worker it dispatches, not for a user request: closes tasks the evidence shows done, merges duplicates, cancels the overtaken and the long dead, never deletes. Covers what to pick, the Run's Steps, and the section Prove a batch (what counts as evidence a task is done). Use for \"which of my tasks are already done\". Not for filing and retitling (task-stack-clarify) or the weekly review (weekly-review-workstream)."
---

# Reconciling the task stack

The owner's task list says only what is still true: every open task already done is closed with the evidence that did it, every duplicate is merged into the task it repeats, and every task overtaken or long dead is cancelled, never deleted. `orchestration-workstream` is the conduct and the return block; `task-stack-workstream` is the task stack's rules, evidence bar and change set; load them first. The owner's `TASK-STACK-RULES.md` wins over both.

Complete on solid evidence without asking. Only an ambiguous merge, or a cancel of a task linked to a goal, becomes a question.

## What the Run has

- `RUN/before.json`: `task-stack-check`'s json from before the session. Its `findings` list every flagged item with its `portal://` ref; `findings.duplicates` names each likely duplicate with `duplicate_of`. Missing (`STALE`): read the open tasks yourself and say so.
- Inputs: domain (optional, default every domain), max changes (default 50), instructions (such as a wider window), local repository clones (optional, for commit evidence), dry run.

After the session `task-stack-apply` makes the change set, and `task-stack-check` and `task-stack-report` score again. Overdue, stale, duplicates and waiting must not get worse.

## Steps

1. [judgment] Orient. `whoami`; read the rules file and `RUN/before.json` (the overall score and the overdue, stale, duplicates and waiting counts).
2. [judgment] Pick the work, the owner's own tasks only, within the domain if given, until about four batches of 25: tasks `findings.duplicates` flags, with the task each duplicates; overdue tasks, oldest due date first; WAITING tasks; open tasks that sent mail, meeting notes or past events in the window plausibly touch (the last 3 days unless the instructions say otherwise; a first Run or a Run after a gap may take 14); stale tasks, oldest first. Write `RUN/plan.json`: the batches, each task with its lens.
   → nothing to pick: step 6
3. [hand-off: productivity-worker] Prove. One worker (model opus) per batch, in parallel, never two on one task, told to follow this skill's section Prove a batch, with the task refs and lenses, the window, the owner's contact id, the rules file's path, the batch id as op-id prefix and any clones the inputs list. Save each return as `RUN/returns/<batch>.json`; a reply without the json block goes back once for it.
4. [hand-off: productivity-reviewer] Check every `medium` op, every merge and every cancel whatever its confidence, told to use `task-stack-workstream`'s section Check task-stack ops, with the ops only, never the worker's reasoning. A FAIL drops the op; note why for the report. A cancel that passed carries `"check": "PASS"`; `task-stack-apply` refuses one without it.
5. [judgment] Write `RUN/changes.json` in the `task-stack-workstream` shape with `"orchestrator": "task-steward-reconcile"` and `dry_run` as this Run is, from the `high` ops other than cancels and the ops the reviewer passed: one op per task (a task both done and duplicated is merged, not completed twice); at most max changes, completions first, then merges, cancels, edits; an ambiguous merge and any cancel of a goal-linked task go to `questions`, one line each the owner can answer yes or no.
6. [judgment] Report what will be completed, merged and cancelled and on what evidence, the ops the reviewer failed, the questions as one numbered list, what could not be judged and why, and before.json's score. Never claim a score change.
   → reported: done

## Prove a batch

For a `productivity-worker` given one batch of task refs, each with its lens (`overdue`, `stale`, `duplicate`, `waiting`, `recent`). Read the rules file first. Your goal is a verdict on every task, each resting on evidence a person would accept. Read only; write nothing.

Read the task in full (`get`, detail full): description, comments, contact, project and dates. Then look for what would have done it:
- **Sent mail.** `search` on the task's contact, company and distinctive words; `list_entities` email with `direction: sent` in the window. Read the body (`email_bodies`) before relying on it. A sent message counts when it does what the task says, to the person or company the task is about, after the task was created.
- **Meeting notes.** Notes linked to the task, its contact or its project in the window, recording the item decided, delivered or done, not merely discussed.
- **Calendar events.** For a task to schedule or hold a meeting: the event exists and its start is in the past.
- **Commits.** When the task names a repository and the brief gives its clone: `git -C <clone> log --oneline --since=<date> --grep=<words>`, then `git -C <clone> show` a candidate. Never fetch, pull, push or change anything.
- **Documents.** A document attached to the task or a note that is the deliverable.

And for each task:
- **Duplicate.** Another open task of the same owner for the same commitment (the check's `duplicate_of`, or one you find). The older is kept. A difference in a number, a period or a counterparty means two commitments.
- **Overtaken.** Evidence the task no longer applies (the meeting was cancelled, the client chose another route, someone else did it): a cancel with that evidence.
- **Stale.** No update in 60 days and no goal (its own or its project's): a cancel without evidence is allowed. Anything linked to a goal goes to `questions`.
- **WAITING resolved.** Since the task last moved, an inbound email from the person it waits on, a meeting with them, or a note recording their answer plainly resolves the wait: an edit moving it to TODO (or IN_PROGRESS when work has started), citing that evidence. A reply that only acknowledges does not.
- **WAITING undated.** When the record shows when to follow up (a promised date, a stated cadence), an edit setting `due_date`; otherwise leave it for the clarify mode and say so in `notes`.

A task with no evidence either way stays open (`still-open`). Never complete on a hunch.

Return the `orchestration-workstream` block with `workstream: "prove-a-batch"`: one `items` row per task in the batch, and the proposed ops in `extra.ops` as `task-stack-workstream` describes, each with `confidence` and `title`, op ids `<prefix>-<n>` from your brief.
