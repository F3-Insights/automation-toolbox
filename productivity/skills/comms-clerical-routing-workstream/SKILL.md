---
name: comms-clerical-routing-workstream
description: Routing the owner's clerical mail to their executive assistant, run by comms-steward in mode clerical and by the productivity-worker and productivity-reviewer it dispatches, not for a user request; adds to orchestration-workstream. Covers CLERICAL-ROUTING-RULES.md and its go switch (the assistant's agreement), the Steps, the routing rule (scheduling, forwarding a file already on disk, intros and cc routing, the named confirmations), precision over recall, one batched Portal task a day for the assistant, ageing items, cover notes the owner sends themselves as drafts, the reviewer's section Check routed threads, the DONE checklist and the shapes.
---

# Routing clerical mail

Take the clerical half of the owner's mail off their desk without ever handing their assistant something that was theirs to answer. Each Run, every clerical thread of the day is routed to the assistant in one clear task, kept with the owner for a stated reason, or answered by a cover note the owner sends themselves. This skill extends `orchestration-workstream`.

## Inputs

- `routing_rules`: CLERICAL-ROUTING-RULES.md; `rules_file`: TASK-STACK-RULES.md. Read both first.
- `date` (optional): the day of mail to route. Default: yesterday in the owner's timezone.
- `instructions` (optional) and `dry_run`. `RUN` is the working folder; write only there.

## Steps

1. [judgment] `whoami`; read both rules files. Note whether routing is on; if not, this Run is a rehearsal (classify and report only).
2. [hand-off: productivity-worker] Triage the day's mail: model opus, `email-triager-method` from Inputs to Return, with the date's window, the inboxes in scope, and the routing rule pasted as its DELEGATE definition, with "suggested owner: the assistant" for threads that fit it.
   → no DELEGATE thread: step 5
3. [judgment] Decide each DELEGATE thread: routed, kept with the owner (and why), or cover note.
4. [hand-off: productivity-reviewer] Check the routed threads (this skill, section Check routed threads), with their refs and the rules path only. A FAIL stays with the owner.
5. [judgment] Carry: find the open routed items of earlier days (the assistant's open tasks with `source` `clerical:`), their age, and the ones to return to the owner.
   → dry run, rehearsal or no cover note: step 8
6. [hand-off: productivity-worker] Draft each cover note: model opus, `email-drafter-method`, `agent_slug` `comms-steward-clerical`.
7. [hand-off: productivity-reviewer] Check the cover notes (`comms-draft-check`, section The tests, in order), with the draft ids and briefs only.
   → FAIL: step 6 (max 1)
8. [judgment] Write `RUN/routing.json` and `RUN/done.json` (the DONE checklist, cited) and, unless rehearsal, `RUN/changes.json` with at most one create op for the assistant's task. Report; a note that failed twice is listed, not delivered.
   → written: done

## The rules file first

`CLERICAL-ROUTING-RULES.md` (path in the inputs as `routing_rules`) holds: whether routing is on (the assistant has agreed, and the assistant's weekly cap), the assistant's Portal contact, the calendars the assistant may book and the booking link, the named recurring confirmations the assistant handles, the inboxes in scope, and senders never routed. **If routing is not on, the Run is a read-only rehearsal**: classify and report, write no change set and stage no draft.

## The routing rule

Route a thread to the assistant only when it is one of:

1. **Scheduling**: a request to set, move or confirm a meeting, on a calendar the assistant may book.
2. **Forwarding**: "please send me X" where X is a file already in the record (an attachment on an earlier message, a document the Portal links). Not a file that must be written.
3. **Intro and cc routing**: an introduction to make or acknowledge, a "looping in" with no question for the owner.
4. **Named confirmations**: the recurring confirmations the rules list.

Everything else stays with the owner. A thread that also asks the owner a question, mentions a price, scope, deadline or deliverable, comes from a client about the work, or is sensitive, is never routed. **Precision over recall**: a misrouted client question costs more than a missed scheduling email. When torn, do not route.

## The assistant's task

One Portal task a day, as a `create` op in the `task-stack-workstream` change-set shape: title `Handle today's routed mail (<n> items)`, owner the assistant's contact, due the next business day, `source` `clerical:<yyyy-mm-dd>`. Its description lists each thread: the ref, the sender, the ask in one line, and for scheduling the calendar and the booking link. Items from earlier tasks still open after 2 business days go first, marked as carried; after 5 they come back to the owner as one line in the report, once. External people never get a message from an agent.

## Cover notes

For a forwarding ask the owner must answer themselves (the rules say which senders), a cover note may be staged by a worker on `email-drafter-method`: short, the file named, nothing promised. It is checked on `comms-draft-check` like any draft. Never sent.

## Check routed threads

For `productivity-reviewer`: whether handing each thread to the assistant is safe, from the thread and the routing rules only, never the classifier's reasoning. Read the routing rules file first, then each thread in full (`get` the email, `email_bodies` for the bodies). PASS only when it fits one routing class (scheduling, forwarding a file already in the record, intro or cc routing, a named confirmation) and none of the exclusions: it asks the owner nothing, names no price, scope, deadline or deliverable, is not a client's question about the work, and is not from an excluded sender. When torn, FAIL: precision over recall.

Return the `orchestration-workstream` block, `workstream: "comms-clerical-routing-workstream"`, one `items` row per thread: `test` `route`, `item` the email ref, `state` PASS or FAIL, `evidence` the sentence that decided it, `note` one line.

## Report

Counts routed, kept and covered; the routed list as it will read in the assistant's task; carried and returned items; cover-note draft ids; reviewer FAILs; any question for the owner as one numbered list.

## Never

- Route anything while the rules say routing is off.
- Route a thread that asks the owner anything, touches price, scope, a deadline or a deliverable, or is a client's question about the work.
- Contact anyone outside, send, or push a draft.
- Write a Portal task in the session; the task goes in the change set.

## DONE checklist

- [ ] Every thread the triager classed DELEGATE has a decision: routed, kept with the owner, or cover note, each with its reason.
- [ ] Every routed thread passed the reviewer's Check routed threads (checked); a FAIL stays with the owner.
- [ ] At most one task create for the assistant, with carried items first, or none when routing is off or nothing qualified.
- [ ] The week's routed minutes stay under the assistant's cap, or the excess stays with the owner.
- [ ] Nothing was sent, no external person was contacted, and no task was written in the session.

## Shapes

`RUN/routing.json`:

```json
{"date": "2026-10-05", "routing_on": true, "dry_run": false,
 "threads": [{"ref": "portal://email/<id>", "from": "...", "class": "scheduling",
              "decision": "routed", "check": "PASS", "ask": "...", "reason": "..."}],
 "carried": [{"ref": "portal://email/<id>", "business_days": 3}],
 "returned_to_owner": [], "questions": [], "notes": []}
```

`RUN/changes.json` is the `task-stack-workstream` change set, `orchestrator` `comms-steward-clerical`.

## Later tools

- `task-stack-apply` as the finish step over `RUN/changes.json`.
- `clerical-carry`: the open routed items and their age from earlier tasks, in code.
