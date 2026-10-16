---
name: crm-relationship-workstream
description: The weekly relationship-tending pass, run by comms-steward in mode relationships and by the productivity-worker and productivity-reviewer it dispatches, not for a user request; adds to orchestration-workstream. Covers RELATIONSHIP-RULES.md first, the Steps, who may be picked (professional contacts in the Portal; personal ones never leave local processing), the weekly outreach target, the cold-VIP and unanswered-inbound lenses, one specific reason to write per pick, drafts staged and never sent, the sent count of last week's drafts, the DONE checklist and the return shapes.
---

# Tending relationships

Keep the owner's professional network warm without costing them more than the minutes it takes to read and send a few short emails. Each week: the target number of outreach drafts, each to a contact worth keeping, each with one specific reason to write now, each checked; plus the inbound mail left unanswered, the networking events not registered for, and how many of last week's drafts were sent. This skill extends `orchestration-workstream`. How the week's candidate pool is built (health thresholds, priority weighting, relationship types, the pool steps) is `references/relationship-pool.md` in this skill's folder.

## Inputs

- `relationship_rules`: the owner's RELATIONSHIP-RULES.md. Read it first; it wins.
- `target` (optional): the number of drafts this week. Default: the rules' number.
- `instructions` (optional), and `dry_run`: do everything except stage drafts, writing what each drafter would be briefed with.
- `RUN` is the working folder; write only there. The Portal is read only, except the drafts the drafting workers stage.

## Steps

1. [judgment] `whoami`; read the rules. Compute last week's sent count (Last week's sent count).
2. [judgment] Build the candidate pool by `references/relationship-pool.md`, reading only: twice the target in picks, with the rules' thresholds, exclusions and cooldown. Save it as `RUN/pool.json`.
3. [judgment] Drop every pick "Who may be picked" excludes, checking each against the Portal yourself (open drafts, last touch, personal class). Keep the target number, lens order first. Move unanswered inbound to its own list.
   → no pick left: step 7
4. [hand-off: productivity-worker] Research each kept pick, in parallel: model haiku, `portal-research`, section Research a person, topic "one specific reason to write now, with its source ref". No reason found: the pick is reported, with no draft.
   → dry run (each drafter brief written to `RUN/briefs/` instead): step 7
5. [hand-off: productivity-worker] Draft one email per pick with a reason, in parallel: model opus, `email-drafter-method`, with the recipient, the intent (reconnect, one ask at most), the reason and its ref, "new message, no thread", and `agent_slug` `comms-steward-relationships`.
6. [hand-off: productivity-reviewer] Check the drafts (`comms-draft-check`, section The tests, in order), with the draft ids and the drafters' briefs only.
   → FAIL: step 5 (max 1)
7. [judgment] Write `RUN/outreach.json` in the shape below, tick the DONE checklist citing a draft id, a ref or a count for each line, and report. A draft that failed twice is reported and left for the owner.
   → written: done

## The rules file first

The owner's `RELATIONSHIP-RULES.md` (path in the inputs as `relationship_rules`) holds the weekly outreach target, the cold thresholds if they differ from the method's, the contacts or classes never to pick, the networking groups and their cadence, the voice files, and the cooldown after a touch. It wins over this skill.

## Who may be picked

- **Professional contacts in the Portal only.** A contact the rules or the Portal mark as personal (family, friends, a personal domain) is never picked, researched or drafted to by this pass: personal relationships stay on local processing. When unsure, leave the contact out and say so in `notes`.
- **Not touched inside the cooldown** (default 21 days): no sent mail, meeting or call with them since. Not already holding an open Portal draft to them.
- **Not a live deal or a client thread.** Client work belongs to the delivery and update orchestrators; this pass writes to people the owner wants to keep warm, not to people they are working with this week.

## The lenses, in order

1. **Unanswered inbound.** A contact wrote and the owner has not answered: 7 days for VIP (priority 1), 14 for others. These come first; a reply owed beats a reconnect. Hand them to the owner as a line, never as an outreach draft: the reply is `comms-reply-to-email`'s job.
2. **Cold VIP and High.** Priority 1 and 2 contacts past the method's critical threshold, most valuable times most stale first.
3. **Serendipity.** Priority 3 and 4 contacts stale six months or more, picked at random so each week surfaces different people.
4. **Networking cadence.** Each group in the rules with its cadence (for example one event a month): whether the owner is registered for the next one. A missing registration is a line for the owner, never a draft.

Fill the target from lens 2, then lens 3. Never pad: fewer good picks beat the target met with generic notes.

## One reason per pick

A pick carries one specific reason to write now, from the record: something they posted, announced or asked, a project they mentioned, a shared contact, an event coming up, a year since a milestone. "Checking in" is not a reason. No reason found means no draft: the pick is reported with what was missing.

## Drafts

- One draft per pick, written by a worker on `email-drafter-method` in the owner's voice, staged in the Portal, `visibility: private`, `agent_slug` `comms-steward-relationships`, `related_contact_id` set.
- Short: three to six sentences, one ask at most (a call, a coffee, a reply), no pitch, no promise of work, price, time or introduction the owner has not made.
- Never sent, never pushed to a mail client by this pass. The owner reads and sends.

## Last week's sent count

For each draft the previous Run staged (the Portal's drafts created 7 to 14 days ago with `agent_slug` `comms-steward-relationships`, or the old `crm-relationship-tending-orchestrator` until a month after productivity converted, so the count survives the rename), count it sent when the draft's state is `sent` or the contact shows an outbound touch after the draft was created. Report sent, deleted or edited when visible, and still open. This is the pass's grade: drafts the owner does not send are the review load the pass exists to avoid.

## DONE checklist

The main agent checks each item against evidence it can cite; the reviewer confirms the items marked (checked).

- [ ] Every pick is a professional contact outside the cooldown with no open draft (checked).
- [ ] Every draft's facts are in the record and it makes no commitment for the owner (checked).
- [ ] The week's drafts exist in the Portal, each with its draft id, or the shortfall is explained pick by pick.
- [ ] Unanswered inbound and networking-cadence lines are in the report, or "none".
- [ ] Last week's sent count is recorded, or `unavailable` with the reason.
- [ ] Nothing was sent or pushed, and no personal contact was read beyond its priority flag.

## Return shapes

The main agent writes `RUN/outreach.json`:

```json
{"week": "2026-W41", "target": 5, "dry_run": false,
 "picks": [{"contact": "portal://contact/<id>", "name": "...", "lens": "cold-vip",
            "last_touch_days": 74, "reason": "<one line with its source ref>",
            "source": "portal://email/<id>", "draft": "<draft id or null>",
            "check": "PASS", "note": ""}],
 "unanswered_inbound": [{"contact": "portal://contact/<id>", "email": "portal://email/<id>", "days": 9}],
 "networking": [{"group": "<from the rules>", "next_event": "YYYY-MM-DD or unknown", "registered": false}],
 "last_week": {"drafted": 5, "sent": 3, "open": 1, "unknown": 1},
 "questions": [], "notes": []}
```

The reviewer returns the `orchestration-workstream` block with one `items` row per draft: `test` `outreach-draft`, `item` the draft id, `state` `PASS` or `FAIL`, `note` the fix.

## Report

The drafts as a numbered list (contact, lens, reason, draft id, check); the unanswered inbound and networking lines; last week's sent count; the questions as one numbered list; anything left undone and why.

## Never

- Send, push to Outlook or build a compose link. Drafts stay in the Portal.
- Pick, research or draft to a personal contact, a client in active work, or anyone inside the cooldown.
- Write a draft outside `email-drafter-method`, or write to the Portal other than those drafts.

## Later tools

- `outreach-sent-count`: last week's drafts by agent slug against draft state and outbound touches, in code.
- `relationship-pool`: the cooldown, open-draft and personal-class filters over the contact list, in code, so the scout reads a short pool.
