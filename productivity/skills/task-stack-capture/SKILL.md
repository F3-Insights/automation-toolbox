---
name: task-stack-capture
description: "Task capture, run by task-steward in mode capture and by the productivity-worker it dispatches, not for a user request: turns commitments no other job reads (the time study's said-but-not-seen lists, the owner's quick-capture inbox) into one task each in the owner's Insights Portal task stack, never twice. Covers the Run's Steps, the decision for one source item (create, exists, skip or ask), the create op carrying the item's source key, and the section Decide a batch. Not for clarifying existing tasks (task-stack-clarify) or finding done ones (task-stack-reconcile)."
---

# Capturing a commitment

Nothing the owner commits to gets lost, and nothing is captured twice. Email belongs to the nightly email sweep and recorded meetings to the meeting worker: a commitment they already filed is a duplicate here, not a new task. `orchestration-workstream` is the conduct and the return block, `task-stack-workstream` the task stack's rules and change set, and `task-stack-clarify` how a task is filed, titled and dated; load them first. The owner's `TASK-STACK-RULES.md` wins over all of them.

## What the Run has

- `RUN/capture-queue.json`, gathered by `productivity-task-capture-queue` before the session: `items` (the undecided source items, newest first, capped at max items, in batches `b1`, `b2`, ... of 10), each with `key`, `ref`, `date`, `text`, from the time study `quote`, `to`, `by`, `domain` and `why_not_seen`, its `marker`, and from the Portal `already`, `candidates` and `domain_hint`; plus `owner_contact_id`, every active domain with its catch-all project, and the `expired`, `closed` and `deferred` items. Never widen it. Missing: no work, write an empty change set. `portal` says `STALE`: no hints, so search yourself.
- `RUN/before.json`: the stack's score before the session.
- Inputs: max items (default 40), horizon days (default 14; older unseen items were set aside as expired), source (optional), instructions, dry run.

After the session `task-stack-apply` makes the change set and `productivity-task-capture-record` writes each item's outcome to the capture ledger. Whether capture is done overall is `productivity-task-capture-check`'s verdict, not a claim.

## Steps

1. [judgment] Orient. `whoami`; read the rules file and `RUN/capture-queue.json` (its counts, sources and any unreadable one).
   → nothing queued: step 6
2. [judgment] Read once the open projects of the domains the items point at (`hierarchy` or `list_entities` project). Write `RUN/plan.json`: the batches, their item keys and the project lists.
3. [hand-off: productivity-worker] Decide. One worker (model opus) per batch, in parallel, never two on one item, told to follow this skill's section Decide a batch, with the batch's items as the queue holds them, the domains with their catch-all projects, the projects read, the owner's contact id and timezone, today's date, the rules file's path and the batch id as op-id prefix. With one batch, decide it yourself by the same section. Save each return as `RUN/returns/<batch>.json`; a reply without the json block goes back once for it.
4. [hand-off: productivity-reviewer] Check every `medium` create, told to use `task-stack-workstream`'s section Check task-stack ops, with the ops only (each with the item's text, quote and ref, never the worker's notes), the rules file's path and the owner's contact id. A FAIL drops the op: it becomes a question when the worker had a best guess, else the item is `skip` with the reviewer's reason.
5. [judgment] Write `RUN/changes.json` in the `task-stack-workstream` shape with `"orchestrator": "task-steward-capture"`, `dry_run` as this Run is, plus `captures`: one decision per queued item, `{"source": <key>, "decision": "create" | "exists" | "skip" | "ask", "op": <op id>, "task": "portal://task/<id>", "reason": "..."}`. One create op per `create`, carrying `source`, at most max items; two items that are one commitment get one create and the other is `skip` ("same commitment as <key>"); each `ask` is one line in `questions`, `{"ask", "why"}`, answerable "ok" or with one word, your best choice in it.
6. [judgment] Report how many items became tasks, were already tasks, were skipped and why (by kind), the questions as one numbered list, the sources that could not be read, and the queue's expired, closed and deferred counts. Never claim a write.
   → reported: done

## The standard

Each source item ends in exactly one of four places, and a reader of the item and the record would agree with the choice:

- **create**: a new task, written as the owner would write it, verb first, filed, owned and dated, so the clarify pass has nothing left to do with it;
- **exists**: a task already holds this commitment, open or recently done; that task is the answer and no second one is made;
- **skip**: not an action the owner owes (a remark, a wish, another person's commitment, done already, overtaken);
- **ask**: only the owner can say, as one line they can answer "ok" or with a word.

A missed commitment costs the owner a broken promise; a junk task costs them trust in the list. Weigh both. Something plainly theirs to do is captured; something doubtful is asked, not guessed.

## What an item gives you

- `text`: what was said or written. For the time study it is the assessor's line: the commitment, often with the quote, a recording hash and what was or was not seen after. For the inbox it is the owner's own words.
- `quote`, `to`, `by`, `domain`, `why_not_seen` when the source has them; `date` the day it was said or written.
- `already`: a task already carries this item's marker. Then the decision is `exists` with that task; nothing else to read.
- `candidates`: the owner's tasks whose titles are close, open or closed in the last 60 days, with a score. A hint, not a verdict: read the likely ones.
- `domain_hint`: the Portal domain the source named, with its catch-all project.

## The decisions, in order

1. **Is it the owner's action?** A commitment is something the owner said they would do ("I'll send it today", "let me look at the file"), or a line they wrote to themselves. Not one: something someone else said they would do (that is a WAITING on them: say so in `findings` for the follow-up loop, decision `skip`), a wish or an opinion, a household remark with no action the task list should carry, a question they asked. The assessor's words around the quote say who acted; trust the quote over the gloss.
2. **Is it already done or overtaken?** The time study often says what it saw after ("Seen, same day", "a new revision exists"). Seen done, or the moment has passed (the call was that day, the event is over): `skip`, with the reason. Partly seen: capture the part not seen, if it still matters.
3. **Does a task already hold it?** Read each likely candidate (`get`) and, when none fits, `search` the item's key words (the counterparty, the deliverable). The same commitment, same owner, is `exists` with that task's `portal://task/<id>`, even when the wording differs, and even when the task is done. Different numbers, periods or counterparties are different commitments. Email and meetings feed the list through other jobs, so a commitment from a recorded meeting may already be a task the meeting worker made.
4. **Write the task.** As `task-stack-clarify` says for project, title, owner, dates and WAITING:
   - the project the record points at (the counterparty's open tasks, the domain the source named), else the domain's catch-all project (`domain` in the op instead of `project`), never another client's domain;
   - a title that starts with a verb and keeps the specifics (who, what, which period): "Send Dana the freight summary", not "Freight item";
   - owner: the owner (leave `owner` out; the apply fills the token's contact);
   - `due_date` only when the item or the record gives one ("today" on the item's date is that date; "by Friday" is that Friday). A promised date that has passed still goes in: the task is overdue, which is the truth;
   - `description`: the quote and where it came from (`ref`, the date, the recording hash), so the owner recognises it;
   - `source`: the item's `key`, always. It is the marker that makes a re-run find this task instead of making another.
5. **Ask** when the domain is unclear (two clients plausible), when you cannot tell whether it is their action or still wanted, or when it would be a task for someone else. Offer your best choice: "Capture 'Send the pallet forecast to the controller' under Acme Finance? Or skip."

## What you propose

One `create` op per item you capture:

```json
{"id": "b1-1", "op": "create", "title": "Send Dana the inventory summary",
 "domain": "<domain uuid>", "due_date": "2030-03-04", "source": "said-not-seen:0a1b2c3d4e5f",
 "description": "\"I'll get the summary over to her today.\" (said 2030-03-04 09:15, 2030-03-04#2)",
 "reason": "Said on 3/4 they would send it that day; no mail to her was seen", "confidence": "high"}
```

- `project` (a uuid) or `domain` (a uuid, for its catch-all project), never both guessed.
- `evidence` only when there is a Portal record of the commitment itself (a meeting note, an email): a `portal://<note|email|...>/<uuid>`, full uuid. A recording hash is not one; it goes in the description.
- Confidence: `high` when the item plainly is the owner's commitment and the project is plain; `medium` when you chose between projects or read the commitment from an assessor's gloss without a clear quote. Medium creates go to the reviewer.

## Items

`items` rows: `test` `capture`; `item` the item's key; `state` one of `create`, `exists`, `skip`, `ask`; `evidence` the task found or the record that decided it; `note` one line.

## Decide a batch

For a `productivity-worker` given one batch (or task-steward deciding a single batch itself). Read the rules file first. Decide every item by the standard and the decisions above, from the item and the Portal, read only; write nothing. Number your ops `<prefix>-1`, `<prefix>-2`, ... from the op-id prefix in your brief.

Return the `orchestration-workstream` block with `workstream: "decide-a-batch"`:
- `items`: one row per source item, as Items says;
- `extra.captures`: one decision per item, `{"source": <key>, "decision": "create" | "exists" | "skip" | "ask", "op": <op id>, "task": "portal://task/<id>", "reason": "..."}`;
- `extra.ops`: the create ops, each with `source: <key>` and `confidence`;
- `questions`: `ask` one line with your best choice in it, `of: owner`, `why` saying what the answer changes, and `blocks` holding the item's key;
- `findings`: what the owner should know (a commitment someone else owes them, for the follow-up loop; a domain with no catch-all project);
- `notes`: what you could not read and why.

Every item in the batch appears in `items` and in `extra.captures`. Never return prose without the block.
