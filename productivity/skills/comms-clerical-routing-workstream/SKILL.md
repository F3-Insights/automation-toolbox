---
name: comms-clerical-routing-workstream
description: Reference loaded by comms-clerical-routing-orchestrator and comms-routing-checker, not for a user request; what routing the owner's clerical mail to their executive assistant adds to orchestration-workstream. Covers CLERICAL-ROUTING-RULES.md and its go switch (the assistant's agreement), the routing rule (scheduling, forwarding a file already on disk, intros and cc routing, the named confirmations), precision over recall, one batched Portal task a day for the assistant, ageing items, cover notes the owner sends themselves as drafts, the DONE checklist and the shapes.
---

# Routing clerical mail

This skill extends `orchestration-workstream`. Load that skill if it is not loaded.

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

For a forwarding ask the owner must answer themselves (the rules say which senders), a cover note may be staged by `email-drafter`: short, the file named, nothing promised. It is checked by `comms-draft-checker` like any draft. Never sent.

## DONE checklist

- [ ] Every thread the triager classed DELEGATE has a decision: routed, kept with the owner, or cover note, each with its reason.
- [ ] Every routed thread passed `comms-routing-checker` (checked); a FAIL stays with the owner.
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

`RUN/changes.json` is the `task-stack-workstream` change set, `orchestrator` `comms-clerical-routing-orchestrator`.

## Later tools

- `task-stack-apply` as the finish step over `RUN/changes.json`.
- `clerical-carry`: the open routed items and their age from earlier tasks, in code.
