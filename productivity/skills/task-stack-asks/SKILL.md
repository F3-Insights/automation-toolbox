---
name: task-stack-asks
description: "Ask capture, run by task-steward in mode asks and by the productivity-worker it dispatches, not for a user request: turns asks in one domain's mail and meetings into tasks, never twice. An ask the owner made of someone in sent mail becomes a task that person owns, WAITING on them; an ask made of the owner (inbound mail, a Fellow meeting, Teams when the session can read it) becomes the owner's task, VIP asks first, created and completed together when the owner already delivered it. Covers the Run's Steps and the section Decide asks in a batch. Not for the owner's own promises (comms-follow-up-workstream, lens D) or other capture sources (task-stack-capture)."
---

# Capturing asks

Every ask in a domain's mail and meetings is on the task list once, held by whoever owes it, and no VIP ask is missed. `orchestration-workstream` is the conduct and the return block, `task-stack-workstream` the task stack's rules, delegation and change set, and `task-stack-clarify` how a task is filed, titled and dated; load them first. Sent mail is read as `waiting-on-tracker-method` reads it: the owner's new text, above the first quoted `From:` line. The owner's `TASK-STACK-RULES.md` wins over all of them; the domain file adds the domain's facts.

## What the Run has

- `RUN/asks-queue.json`, gathered by `productivity-task-asks-queue` before the session: `domain` (with its catch-all project), `owner_contact_id`, `owner_addresses`, `timezone`, `window`, `vips` (each with why), `warnings`, and `items` (VIPs first, then newest, in batches `b1`, `b2`, ...), each with `key`, `ref`, `date`, `local_date`, `direction` (sent, received, meeting), `subject`, `snippet`, `counterparties` (a meeting's with `people`, each attendee's address and contact id), `vip`, `vips`, `default_due` and `already`, and on a meeting `owner_attended` and `delegated_due`. Never widen it. Missing: no work, write an empty change set.
- `RUN/before.json`: the stack's score before the session.
- Inputs: domain, `domain_file`, max items (default 40), instructions, dry run.

After the session `task-stack-apply` makes the change set and `productivity-task-asks-record` moves the domain's cursor past the items decided; an item not decided comes back next Run, and the queue re-reads two days before the cursor for mail that synced late.

## Steps

1. [judgment] Orient. `whoami`; read the rules file, the domain file and `RUN/asks-queue.json` (counts, warnings).
   → nothing queued and no Teams tools: step 6
2. [judgment] Read once the domain's open projects (`hierarchy` or `list_entities` project). When the session has a Microsoft 365 connector's tools, read the domain's Teams chats since `window.since` and add each message that may hold an ask as an item keyed `asks:teams:<message id>`, `ref` its link, VIP marked as the queue marks mail; without them, Teams is not read. Write `RUN/plan.json`: the batches, their item keys and the project list.
3. [hand-off: productivity-worker] Decide. One worker (model opus) per batch, in parallel, told to follow this skill's section Decide asks in a batch, with the batch's items as the queue holds them, the domain and its catch-all project, the projects read, the owner's contact id, addresses and timezone, today's date, the rules and domain files' paths and the batch id as op-id prefix. With one batch, decide it yourself. Save each return as `RUN/returns/<batch>.json`; a reply without the json block goes back once for it.
4. [hand-off: productivity-reviewer] Check every create from a VIP item and every `medium` one, told to use `task-stack-workstream`'s section Check task-stack ops, with the ops only (each with the item's ref and the quoted ask, never the worker's notes), the rules file's path and the owner's contact id. A FAIL drops the op (and its paired complete): it becomes a question when the worker had a best guess, else the item is `skip` with the reviewer's reason.
5. [judgment] Write `RUN/changes.json` in the `task-stack-workstream` shape with `"orchestrator": "task-steward-asks"`, `dry_run` as this Run is, plus `asks`: one decision per queued item, `{"source": <key>, "decision": "create" | "done" | "exists" | "skip" | "ask", "ops": [<op ids>], "task": "portal://task/<id>", "reason": "..."}`. Each `ask` is one line in `questions`, answerable "ok" or with one word, your best choice in it.
6. [judgment] Report the VIP asks first (each with its task or why none), then how many asks became delegated tasks, the owner's tasks, already-done tasks, existing tasks and skips (by kind), the questions as one numbered list, the queue's warnings and deferred count, and "Teams not read" when it was not. Never claim a write.
   → reported: done

## The standard

An ask is a request that someone do something: "can you", an instruction, a deadline given. Each item ends in one place a reader of the item would agree with: a task held by the person who owes the ask (`create`), the same plus its completion when the owner already delivered it (`done`), a task that already holds it (`exists`), nothing to capture (`skip`), or a question only the owner can answer (`ask`). A missed VIP ask costs the owner most; a junk task costs them trust in the list.

## Decide asks in a batch

For a `productivity-worker` given one batch (or task-steward deciding a single batch). Read the rules file and the domain file first. Read each item's text (`email_bodies` for mail; the meeting note, and the transcript only when the note is unclear), the Portal read only; write nothing. Number ops `<prefix>-1`, `<prefix>-2`, ... from your brief's prefix.

1. **Is there an ask?** Skip FYIs, thanks, answers to someone's question, scheduling and other clerical mail, newsletters and notifications, and senders the domain file ignores. In sent mail only the owner's new text counts; in a meeting, an action the note puts on a person.
2. **Who owes it?** In sent mail the owner asked someone: that person owes it (several people, several asks). Inbound, someone asked the owner: the owner owes it. In a meeting, an action the note puts on the owner is the owner's; one it clearly puts on another attendee is delegated to them, like a sent-mail ask, when `owner_attended`; else `skip`, "another's action". A promise the owner made is not an ask (lens D of `comms-follow-up-workstream` holds it): skip, "owner's promise".
3. **Already a task?** `already` names a task carrying this key: `exists`. Else `search` the ask's key words and the person; the same ask, same holder, open or recently done, is `exists` with that task.
4. **Already done?** For an ask of the owner, read their sent mail to the asker after the ask (`list_entities` email, direction sent, `participant_contact_id`, since the item's date). Sent mail that delivers it is `done`: a create plus a `complete` with `"task": "op:<create id>"` citing that email. A reply that only acknowledges is not delivery.
5. **Write the op.** One `create` per ask, `source` the item's key (`<key>:2`, `<key>:3` for a second and third ask in one item), `evidence` the item's `ref` (a Portal reference; a Teams item puts its link in the description instead), `source_email` the `ref` when the item is mail, filed as `task-stack-clarify` says (the thread's project, else the domain's catch-all via `domain`), `description` the ask quoted with who asked and when.
   - Delegated (sent mail, or a meeting action on an attendee): title verb-first naming the person and the thing ("Collect the Q3 lease schedule from Kim"), `owner` and `waiting_on` the person's contact id (from `counterparties`, a meeting's `people`; when it is not there, `ask`), `waiting_reason` what is owed, `due_date` the date given them, else `default_due` (a meeting's `delegated_due`).
   - Of the owner: verb-first title, owner left out, `due_date` the date the asker gave, else `default_due` (a VIP's); `priority` 1 for a VIP ask with a date inside two business days or an urgent tone, 2 for other VIP asks, else left out.
6. **Ask** when the holder, the domain or whether it is still wanted is unclear; offer your best choice.

Confidence: `high` when the ask is plain and the holder and project are plain; `medium` when you chose between projects or read the ask from context. Return the `orchestration-workstream` block with `workstream: "decide-asks"`: `items` one row per item (`test` `ask`, `item` the key, `state` the decision, `evidence` the task or record that decided it, `note` one line); `extra.asks` one decision per item as step 5 of the Steps shapes it; `extra.ops` the create and complete ops, each with `confidence`; `questions` each `ask` with your best choice, `of: owner`, `blocks` the key; `findings` what the owner should know (a VIP ask already late, a VIP the domain file's rule misses); `notes` what you could not read. Every item appears in `items` and `extra.asks`.
