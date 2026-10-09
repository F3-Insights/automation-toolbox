---
name: comms-follow-up-workstream
description: Reference loaded by comms-follow-up-orchestrator, not for a user request; what the unattended follow-up pass adds to orchestration-workstream and comms-follow-ups. Covers FOLLOW-UP-RULES.md first, the four lenses (WAITING, delegated and stalled, unanswered threads, the owner's own promises), one state per open commitment, the false-positive cap, which items may be drafted with nobody present, the outbound gate's three rules done by reading, promise tasks as task-stack ops, the DONE checklist and the shapes.
---

# Following up, unattended

This skill extends `orchestration-workstream`. The interactive method is the `comms-follow-ups` skill (load it): its gate rules, its drafter brief and its "when no one is present" section all apply. This skill adds the owner's own promises and the record a scheduled pass keeps.

## The rules file first

`FOLLOW-UP-RULES.md` (path in the inputs as `follow_up_rules`) holds the staleness and silence windows, the promise default date (5 business days when none is stated), the cooldown after a touch, the daily draft cap, the people and threads never to chase, and the false-positive cap (3 a Run). It wins.

## The lenses

`waiting-on-tracker` runs lenses A to C (what others owe the owner) and, with `lens_d: true`, lens D (what the owner promised in sent mail since the last Run). Its report and its two marker blocks are the record; never repeat its reads.

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

A lens D promise with no task becomes a `create` op in the `task-stack-workstream` change-set shape: verb-first title ("Send <thing> to <name>"), due the stated or default date, `source` `promise:<email id>`, evidence the email ref. A kept promise whose task is open becomes a `complete` op with the delivering email as evidence. All of them go through `task-reconcile-checker` before they enter the change set. A WAITING task's follow-up date stays task-clarify's; do not edit it here.

## DONE checklist

- [ ] Every item the tracker returned has one state, with its evidence ref (`commitments.json`).
- [ ] False positives are within the cap: lens D promises the checker failed, plus items the owner marked wrong on the last Run, at most 3 (checked).
- [ ] Every draft passed the gate and `comms-draft-checker`, or is listed with the reason (checked).
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

`RUN/changes.json` is the `task-stack-workstream` change set, `orchestrator` `comms-follow-up-orchestrator`.

## Later tools

- `outbound-check` granted to the session, replacing the gate by reading.
- `task-stack-apply` as the Automation's finish step over `RUN/changes.json` (until then the change set is a proposal the owner reads).
- `promise-scan`: lens D's promise matching over sent mail in code, so the tracker judges a short list.
