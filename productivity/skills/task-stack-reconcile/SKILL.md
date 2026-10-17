---
name: task-stack-reconcile
description: "The nightly truth pass over the owner's Insights Portal task stack, run by task-steward in mode reconcile and by the productivity-worker it dispatches, not for a user request: closes tasks the evidence shows done, merges duplicates, cancels what the evidence shows overtaken or dropped (never on age alone), never deletes. Covers what to pick, the Run's Steps, and the section Prove a batch (what counts as evidence a task is done). Use for \"which of my tasks are already done\". Not for filing and retitling (task-stack-clarify) or the weekly review (weekly-review-workstream)."
---

# Reconciling the task stack

The owner's task list says only what is still true: every open task already done is closed with the evidence that did it, every duplicate is merged into the task it repeats, and every task overtaken or long dead is cancelled, never deleted. `orchestration-workstream` is the conduct and the return block; `task-stack-workstream` is the task stack's rules, evidence bar and change set; load them first. The owner's `TASK-STACK-RULES.md` wins over both.

Complete, merge and cancel on evidence without asking; never ask the owner. What the evidence does not settle stays as it is and is named in the report.

## What the Run has

- `RUN/before.json`: `task-stack-check`'s json from before the session. Its `findings` list every flagged item with its `portal://` ref; `findings.duplicates` names each likely duplicate with `duplicate_of`. Missing (`STALE`): read the open tasks yourself and say so.
- Inputs: domain (optional, default every domain), max changes (default 50), instructions (such as a wider window), local repository clones (optional, for commit evidence), dry run.

After the session `task-stack-apply` makes the change set, and `task-stack-check` and `task-stack-report` score again. Overdue, stale, duplicates and waiting must not get worse.

## Steps

1. [judgment] Orient. `whoami`; read the rules file and `RUN/before.json` (the overall score and the overdue, stale, duplicates and waiting counts).
2. [judgment] Pick the work, the owner's own and delegated tasks only, within the domain if given, until about four batches of 25: tasks `findings.duplicates` flags, with the task each duplicates; every open task captured from an ask (its description says `Captured from: asks:`) or linked to a source email, lens `asked`, in batches of its own; overdue tasks, oldest due date first; WAITING tasks; open tasks that sent mail, meeting notes or past events in the window plausibly touch (the last 3 days unless the instructions say otherwise; a first Run or a Run after a gap may take 14); stale tasks, oldest first. Write `RUN/plan.json`: the batches, each task with its lens.
   → nothing to pick: step 6
3. [hand-off: productivity-worker] Prove. One worker (model opus; model haiku for an `asked` batch, a cheap evidence lookup) per batch, in parallel, never two on one task, told to follow this skill's section Prove a batch, with the task refs and lenses, the window, the owner's contact id, the rules file's path, the batch id as op-id prefix and any clones the inputs list. Save each return as `RUN/returns/<batch>.json`; a reply without the json block goes back once for it.
4. [hand-off: productivity-reviewer] Check every `medium` op, every op from an `asked` batch, every merge and every cancel whatever its confidence, told to use `task-stack-workstream`'s section Check task-stack ops, with the ops only, never the worker's reasoning. A FAIL drops the op; note why for the report. A cancel that passed carries `"check": "PASS"`; `task-stack-apply` refuses one without it.
5. [judgment] Write `RUN/changes.json` in the `task-stack-workstream` shape with `"orchestrator": "task-steward-reconcile"` and `dry_run` as this Run is, from the `high` ops other than cancels and the ops the reviewer passed: one op per task (a task both done and duplicated is merged, not completed twice); at most max changes, completions first, then merges, cancels, edits; an ambiguous merge and any cancel of a goal-linked task go to `questions`, one line each the owner can answer yes or no.
6. [judgment] Report what will be completed, merged and cancelled and on what evidence, the ops the reviewer failed, what could not be judged and why, and before.json's score. Never claim a score change.
   → reported: done

## Prove a batch

For a `productivity-worker` given one batch of task refs, each with its lens (`overdue`, `stale`, `duplicate`, `waiting`, `recent`, `asked`). Read the rules file first. Your goal is a verdict on every task, each resting on evidence a person would accept. Read only; write nothing.

Read the task in full (`get`, detail full): description, comments, contact, project and dates. Then look for what would have done it:
- **Delivery of an ask** (lens `asked`, and any task with a source email). Read the source thread forward (`get` the email with its thread): delivery by the owner or anyone on their behalf counts, as the owner's sent mail, a later message in the thread showing it delivered, a share notification of the requested thing to the asker (SharePoint or OneDrive "shared with you", Box and the like), a later meeting note recording it done, or Teams when the session can read it. Acknowledgement alone is not delivery.
- **Sent mail.** `search` on the task's contact, company and distinctive words; `list_entities` email with `direction: sent` in the window. Read the body (`email_bodies`) before relying on it. A sent message counts when it does what the task says, to the person or company the task is about, after the task was created.
- **Meeting notes.** Notes linked to the task, its contact or its project in the window, recording the item decided, delivered or done, not merely discussed.
- **Calendar events.** For a task to schedule or hold a meeting: the event exists and its start is in the past.
- **Commits.** When the task names a repository and the brief gives its clone: `git -C <clone> log --oneline --since=<date> --grep=<words>`, then `git -C <clone> show` a candidate. Never fetch, pull, push or change anything.
- **Documents.** A document attached to the task or a note that is the deliverable.

And for each task:
- **Duplicate.** Another open task of the same owner for the same commitment (the check's `duplicate_of`, or one you find). The older is kept. A difference in a number, a period or a counterparty means two commitments.
- **Overtaken.** Evidence the task no longer applies (the meeting was cancelled, the client chose another route, someone else did it): a cancel with that evidence.
- **Stale.** Age alone is no reason to cancel (the owner, 2026-10-17). A stale task is cancelled only on evidence it was overtaken or dropped (the meeting it prepared happened, the request was withdrawn, the work went to someone else), goal-linked or not; otherwise it stays, named in the report as stale.
- **WAITING resolved.** Since the task last moved, an inbound email from the person it waits on, a meeting with them, or a note recording their answer plainly resolves the wait: an edit moving it to TODO (or IN_PROGRESS when work has started), citing that evidence. A reply that only acknowledges does not.
- **WAITING undated.** When the record shows when to follow up (a promised date, a stated cadence), an edit setting `due_date` to it; otherwise to one week from today. Any other edit of an undated WAITING task (a party, a reason) sets `due_date` the same way in the same op, or `task-stack-apply` refuses it.

A task with no evidence either way stays open (`still-open`). Never complete on a hunch.

Return the `orchestration-workstream` block with `workstream: "prove-a-batch"`: one `items` row per task in the batch, and the proposed ops in `extra.ops` as `task-stack-workstream` describes, each with `confidence` and `title`, op ids `<prefix>-<n>` from your brief.
