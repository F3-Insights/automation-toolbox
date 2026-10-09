---
name: crm-relationship-workstream
description: Reference loaded by crm-relationship-tending-orchestrator and the checker it dispatches, not for a user request; what the weekly relationship-tending pass adds to orchestration-workstream. Covers RELATIONSHIP-RULES.md first, who may be picked (professional contacts in the Portal; personal ones never leave local processing), the weekly outreach target, the cold-VIP and unanswered-inbound lenses, one specific reason to write per pick, drafts staged and never sent, the sent count of last week's drafts, the DONE checklist and the return shapes.
---

# Tending relationships

This skill extends `orchestration-workstream`. Read it at `~/.claude/skills/orchestration-workstream/SKILL.md` if it is not loaded. How the week's candidate pool is built (health thresholds, priority weighting, relationship types, the pool steps) is `references/relationship-pool.md` in this skill's folder; this skill adds what a weekly unattended pass needs.

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

- One draft per pick, written by `email-drafter` in the owner's voice, staged in the Portal, `visibility: private`, `agent_slug` the orchestrator's name, `related_contact_id` set.
- Short: three to six sentences, one ask at most (a call, a coffee, a reply), no pitch, no promise of work, price, time or introduction the owner has not made.
- Never sent, never pushed to a mail client by this pass. The owner reads and sends.

## Last week's sent count

For each draft the previous Run staged (the Portal's drafts with this orchestrator's `agent_slug`, created 7 to 14 days ago), count it sent when the draft's state is `sent` or the contact shows an outbound touch after the draft was created. Report sent, deleted or edited when visible, and still open. This is the pass's grade: drafts the owner does not send are the review load the pass exists to avoid.

## DONE checklist

The orchestrator checks each item against evidence it can cite; the checker confirms the items marked (checked).

- [ ] Every pick is a professional contact outside the cooldown with no open draft (checked).
- [ ] Every draft's facts are in the record and it makes no commitment for the owner (checked).
- [ ] The week's drafts exist in the Portal, each with its draft id, or the shortfall is explained pick by pick.
- [ ] Unanswered inbound and networking-cadence lines are in the report, or "none".
- [ ] Last week's sent count is recorded, or `unavailable` with the reason.
- [ ] Nothing was sent or pushed, and no personal contact was read beyond its priority flag.

## Return shapes

The orchestrator writes `RUN/outreach.json`:

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

The checker returns the `orchestration-workstream` block with one `items` row per draft: `test` `outreach-draft`, `item` the draft id, `state` `PASS` or `FAIL`, `note` the fix.

## Later tools

- `outreach-sent-count`: last week's drafts by agent slug against draft state and outbound touches, in code.
- `relationship-pool`: the cooldown, open-draft and personal-class filters over the contact list, in code, so the scout reads a short pool.
