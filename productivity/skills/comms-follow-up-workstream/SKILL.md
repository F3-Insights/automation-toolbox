---
name: comms-follow-up-workstream
description: The unattended follow-up pass, run by comms-steward in mode follow-up and by the productivity-worker and productivity-reviewer it dispatches, not for a user request; adds to orchestration-workstream and comms-follow-ups. Covers FOLLOW-UP-RULES.md first, the Steps, the four lenses (WAITING, delegated and stalled, unanswered threads, the owner's own promises), one state per open commitment, the false-positive cap, which items may be drafted with nobody present, the outbound gate's three rules done by reading, promise tasks as task-stack ops, the DONE checklist, the report and the shapes.
---

# Following up, unattended

Nothing the owner is waiting on goes quiet without a next step, and nothing they promised goes stale without being delivered or honestly re-dated. This skill extends `orchestration-workstream`. The interactive method is the `comms-follow-ups` skill (load it): its gate rules, its drafter brief and its "when no one is present" section all apply. This skill adds the owner's own promises and the record a scheduled pass keeps.

## Inputs

- `follow_up_rules`: FOLLOW-UP-RULES.md; `rules_file`: TASK-STACK-RULES.md. Read both first.
- `since` (optional): the start of lens D. Default: the last Run's date, else 7 days ago.
- `scope` (optional): a project, a domain or a person.
- `instructions` (optional) and `dry_run`. `RUN` is the working folder; write only there.

## Steps

1. [judgment] `whoami`; read both rules files and `comms-follow-ups`.
2. [hand-off: productivity-worker] Find what is waiting: model sonnet, `waiting-on-tracker-method` from Inputs to Return, with the rules' windows, the scope, `lens_d: true` and `since`. Save its report to `RUN/tracker.md`.
   → nothing found: step 8
3. [judgment] Give every item one state on the evidence it carries (One state per commitment). Read the record yourself only where the state turns on it.
4. [hand-off: productivity-reviewer] Check the lens D promise task ops (`task-stack-workstream`, section Check task-stack ops), with the ops only. A failed op is dropped and counted as a false positive.
5. [judgment] Apply the gate by reading (The gate, by reading) to each item headed for a draft. A held item keeps its rule and evidence.
   → dry run (each drafter brief written to `RUN/briefs/` instead): step 8
6. [hand-off: productivity-worker] Draft one email per cleared item, in parallel: model opus, `email-drafter-method`, with the `comms-follow-ups` drafter brief, the tracker's `ask` and `why_now` verbatim, and `agent_slug` `comms-steward-follow-up`.
7. [hand-off: productivity-reviewer] Check the drafts (`comms-draft-check`, section The tests, in order), with the draft ids and briefs only.
   → FAIL: step 6 (max 1)
8. [judgment] Write `RUN/commitments.json`, `RUN/changes.json` and `RUN/done.json` (the DONE checklist, each line cited), and report. A draft that failed twice is `held` with the reason.
   → written: done

## The rules file first

`FOLLOW-UP-RULES.md` (path in the inputs as `follow_up_rules`) holds the staleness and silence windows, the promise default date (5 business days when none is stated), the cooldown after a touch, the daily draft cap, the people and threads never to chase, and the false-positive cap (3 a Run). It wins.

## The lenses

The tracker (`waiting-on-tracker-method`) runs lenses A to C (what others owe the owner) and, with `lens_d: true`, lens D (what the owner promised in sent mail since the last Run). Its report and its two marker blocks are the record; never repeat its reads.

## One state per commitment

Every item the tracker returns gets exactly one state:

| State | Means |
|---|---|
| `drafted` | A nudge, a delivery cover note or an honest re-date is staged as a Portal draft |
| `raise` | A meeting with that person is inside three days; a task to raise it there is proposed |
| `decision` | Only the owner can settle it (price, scope, their time, a yes or no); it is one question |
| `held` | The gate held it (open draft, cooldown, daily cap) or it needs a decision first |
| `kept` | The promise was already delivered; the evidence ref says how |
| `closed` | Overtaken: the evidence says it stopped mattering |
| `unclear` | Not enough in the record to act; listed, never drafted |

## What may be drafted with nobody present

- A nudge whose ask needs nothing from the owner ("send the file you said you would").
- A promise delivery only when the thing exists and its ref is in the record.
- An honest re-date only when the rules give the owner's standing re-date rule (how many days to push); otherwise it is a `decision`.
- Never: a chase that names a price, scope, deadline the owner has not set, or blame.

## The gate, by reading

Before each draft, check in the Portal the three rules of `outbound-check`: no open draft on that thread or to that recipient (never overridden), no touch with them inside the cooldown (held, listed with the rule), and today's drafts under the daily cap (stop drafting; the rest are `held`).

## Promise tasks

A lens D promise with no task becomes a `create` op in the `task-stack-workstream` change-set shape: verb-first title ("Send <thing> to <name>"), due the stated or default date, `source` `promise:<email id>`, evidence the email ref. A kept promise whose task is open becomes a `complete` op with the delivering email as evidence. All of them pass `productivity-reviewer` on `task-stack-workstream`'s Check task-stack ops before they enter the change set. A WAITING task's follow-up date stays task-clarify's; do not edit it here.

## DONE checklist

- [ ] Every item the tracker returned has one state, with its evidence ref (`commitments.json`).
- [ ] False positives are within the cap: lens D promises the checker failed, plus items the owner marked wrong on the last Run, at most 3 (checked).
- [ ] Every draft passed the gate and the reviewer's `comms-draft-check`, or is listed with the reason (checked).
- [ ] Every decision is one line in the owner's numbered list, with the options the evidence supports.
- [ ] The change set holds only checked ops, and `dry_run` matches the Run.
- [ ] Nothing was sent or pushed, and no task was written in the session.

## Shapes

`RUN/commitments.json`:

```json
{"date": "2026-10-05", "dry_run": false,
 "items": [{"key": "A:portal://task/<id>", "lens": "A", "who": "portal://contact/<id>",
            "what": "...", "since": "2026-09-22", "state": "drafted",
            "draft": "<draft id or null>", "evidence": ["portal://email/<id>"], "note": ""}],
 "false_positives": 0, "questions": [{"ask": "...", "why": "..."}], "notes": []}
```

`RUN/changes.json` is the `task-stack-workstream` change set, `orchestrator` `comms-steward-follow-up`.

## Report

Counts by state and lens; the drafts (who, what, draft id); the held items with their rule; the owner's decisions as one numbered list they can answer "1) ok 2) no"; the proposed promise tasks; the false-positive count.

## Never

- Send, push to a mail client or build a compose link.
- Draft anything that needs the owner's decision, or override a gate hold.
- Write a draft outside `email-drafter-method`, or write a Portal task; tasks go in the change set.
- Chase a person or thread the rules exclude, or invent a recipient.

## Later tools

- `outbound-check` granted to the session, replacing the gate by reading.
- `task-stack-apply` as the Automation's finish step over `RUN/changes.json` (until then the change set is a proposal the owner reads).
- `promise-scan`: lens D's promise matching over sent mail in code, so the tracker judges a short list.
