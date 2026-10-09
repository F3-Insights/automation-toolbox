---
name: comms-draft-check
description: "Reference loaded by the comms-draft-checker agent, not for a user request: how an independent checker judges one staged Portal email draft from an unattended orchestrator (relationship outreach, follow-up nudges, promise deliveries, cover notes) before the owner sees it. Right recipient, every fact and date in the record, no commitment the owner has not made, only the ask the brief asked, the owner's voice, nothing private, no duplicate of an open draft or recent touch; PASS or FAIL per draft with the fix. Replies from comms-reply-to-email are checked by email-checker."
---

# Checking a staged draft

This skill extends `orchestration-workstream`. Load that skill if it is not loaded.

You get, per draft: the draft id, the brief the drafter was given (recipient, intent, the source refs), and the orchestrator's rules file path. You never get the drafter's reasoning, and you never edit a draft.

## The tests, in order

1. **Recipient.** `get` the draft: its `recipient_to` resolves to the contact the brief named (`related_contact_id` and the address match a message that contact sent, or the contact record found by that address). A different person, a group address or a guess is FAIL.
2. **Not a duplicate.** No other open draft to that recipient or on that thread (`list_entities` drafts), and no sent mail, meeting or call with them inside the cooldown the rules give (default 3 business days for a nudge, 21 days for outreach), unless the brief says the owner approved the override.
3. **Facts.** Every date, number, name, event and claim in the body is in a source ref the brief lists or in the Portal record of that contact. One fact you cannot find is FAIL.
4. **No commitment.** The draft promises no price, scope, date, deliverable, introduction or time the owner has not already stated in the record. An honest re-date carries the date the brief gave and no other.
5. **The ask.** It asks for what the brief's intent says, once, and nothing else. A chase says what is needed and by when, never that the person is late.
6. **Voice and form.** It reads as the owner (the owner's voice guide (setting `voice_guide`)): short, plain, no dashes used as punctuation, no emojis, no flattery, no sales language.
7. **Nothing private.** No content from the owner's private notes or profile, no other client's matter, no deal terms, health, family or internal strategy, no other agent's notes quoted.

## The return

The `orchestration-workstream` block, `workstream: "comms-draft-checker"`, one `items` row per draft: `test` `draft`, `item` the draft id, `state` `PASS` or `FAIL`, `evidence` the ref you checked against, `note` the failed test and the one fix ("remove the second ask", "the call was on the 3rd, not the 4th"). Never prose without the block.

## Later tools

- `email-draft-show` and `outbound-check` granted to the checker, so tests 1 and 2 run in code.
