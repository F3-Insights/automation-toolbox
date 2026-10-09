# Settings and mechanics for comms-reply-to-email

The first half is the owner's current settings for this flow: theirs to change, in this file, in their own words. The second half is how the steps run. Any standing rules the owner keeps on outbound mail elsewhere are not here; they are read, never copied.

## The owner's settings

**Revision rounds: 2.** A FAIL from the checker sends the draft back to the drafter with the numbered fixes, at most twice. A third FAIL stops the run: the owner is told the draft id and the open issues, and the draft stays in the Portal, undelivered.

**Ask only when there is a real decision.** The owner is asked when the reply would commit them to something they have not already said, and only then. Their decisions are:

- a price, a rate, a discount, a fee or any other number with money in it;
- a yes or a no to a request, an offer, an introduction or an invitation;
- a commitment of their time or their team's: a meeting, a call, a deliverable, a deadline;
- a date or a time offered to someone, including picking among free slots;
- anything that changes scope, terms or who does what;
- anything the brief marks as unknown that the reply cannot be written around.

Not their decisions, so never asked: the greeting, the tone, the length, the order of points, acknowledging what was said, restating something they already decided in the thread or in a Portal note the brief cites, and proposing a follow-up whose date they already set.

**The cooldown does not apply to a reply they asked for.** `outbound-check`'s RECENT_CONTACT hold exists to stop unprompted nudges stacking up. The owner asked for this reply, so step 1 proceeds past it and step 7 passes `--allow-recent-contact`. OPEN_DRAFT_SAME_THREAD and DAILY_CAP always stop the run, and so does a reply of theirs already sent after the email.

**A stale draft is their call, not a stop.** `outbound-check` reports STALE_DRAFT when the only unsent draft on the thread answers an earlier email and was created before this one arrived: the conversation has moved past it. Ask one question, `stale_draft`, with the draft's id and date and what it answered: `discard` (recommended: the new reply is researched from the whole thread, so anything still true in the old draft reaches it) or `stop` (keep the old draft, make nothing). There is no "revise the old one": it answers the earlier email, and `email-deliver` refuses a draft that does not answer the pinned email. `draft_delete` is a Portal soft delete; a draft still at status `draft` was never pushed, so no Outlook copy exists to clean up.

**An email that needs no reply: stop and tell them.** A thank-you, an FYI, an automatic notice, or a confirmation of something already settled gets one line saying so and no draft.

**Delivery follows the request.** Asking for the reply is asking for it to be in their Drafts folder, so step 7 does not ask again. A Gmail inbox cannot take a push; they get the compose link instead.

## The run folder

One folder per run, outside the toolbox (the commands refuse a path inside it), under the owner's state folder (setting `state_dir`): `<state_dir>/comms-reply/YYYY-MM-DD-<contact-slug>-<first 8 of the email id>/`. A runner may name another folder under `<state_dir>/comms-reply/`; the researcher may write only there. Files, in the order the steps write them:

| File | Written at | By |
|---|---|---|
| `find.json` | step 1 | the orchestrator: the three command outputs, keyed `contact`, `email`, `outbound` |
| `pack.json` | step 2 | `python3 ~/.claude/skills/comms-reply-to-email/scripts/email_context_pack.py --out` |
| `brief.md` | step 2 | the researcher |
| `plan.md` | step 3 | the orchestrator |
| `answers.md` | step 4 | the orchestrator, the owner's answers verbatim |
| `check.json` | step 6 | the orchestrator, the checker's JSON block verbatim (overwritten each round; earlier rounds kept as `check-1.json`, `check-2.json`) |
| `deliver.json` | step 7 | the orchestrator, `email-deliver`'s output |

Nothing else keeps state. The Portal's drafts and the thread are the ledger `outbound-check` reads, so a second run for the same email stops at step 1 on the open draft.

## Exit codes

Every command prints one JSON object. `find-contact`, `find-email`, `outbound-check` and `email-deliver` exit 0 to go on, 3 to stop (none or several contacts; no email or already replied; a hold; a refusal), 2 when they could not run. A command that could not run is a stop, never a pass. `email-context-pack` and `email-draft-show` exit 0 or 2.

## The workers

| Agent | Model | May touch | Brief |
|---|---|---|---|
| `email-context-researcher` | sonnet | Portal reads, `email-context-pack`, Write in the run folder | `briefs/researcher.md` |
| `email-drafter` | opus | Portal reads, `draft_create`, `draft_update` | `briefs/drafter.md` |
| `email-checker` | opus | Read, `email-draft-show` | `briefs/checker.md` |

The researcher only extracts and cites; the planning in step 3 and the drafting and checking are Opus work. Each worker's brief is its whole instruction for this flow: paste the brief's text and the inputs it names into the dispatch.

## What the tools enforce, so no prompt has to

- `draft_create` cannot be limited to one recipient, so `email-deliver` refuses a draft whose contact is not the pinned one, whose recipients are not that contact's addresses, which carries a Cc or Bcc, or which answers any email but the pinned one.
- `email-deliver` refuses a draft with no PASS check record, or whose content hash (subject, body, recipients, the email it answers, the contact) changed after the check.
- `email-deliver` re-runs `outbound-check` with the draft itself left out, so a duplicate open draft on the thread holds at delivery even if step 1 was skipped, and refuses when the owner already replied on the thread after the email.
