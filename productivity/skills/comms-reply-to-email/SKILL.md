---
name: comms-reply-to-email
description: "Reply to one person's email in the owner's voice, end to end: pins the exact contact and email in code, has a researcher write a sourced brief, plans the reply, asks the owner only their decisions (a price, a yes or no, a commitment, a date), has the drafter write it and an independent checker verify every fact against the brief, then puts the checked draft in their Outlook Drafts and tells them. Never sends. Use for \"respond to Dana Whitfield's last email\"; run as email-reply-orchestrator. Not for a batch (comms-inbox-replies) or a new email (comms-draft-email)."
argument-hint: "[name or address] [optional: which email, or what to say]"
allowed-tools: Read, Write(~/.local/state/comms-reply/**), Agent, Bash(python3 ~/.claude/skills/comms-reply-to-email/scripts/find_contact.py:*), Bash(python3 ~/.claude/skills/comms-reply-to-email/scripts/find_email.py:*), Bash(python3 ~/.claude/skills/comms-draft-check/scripts/outbound_check.py:*), Bash(python3 ~/.claude/skills/comms-reply-to-email/scripts/email_context_pack.py:*), Bash(python3 ~/.claude/skills/comms-reply-to-email/scripts/email_draft_show.py:*), Bash(python3 ~/.claude/skills/comms-reply-to-email/scripts/email_deliver.py:*), Bash(python3 ~/.claude/skills/comms-reply-to-email/scripts/notify_owner.py:*), Bash(mkdir -p:*), mcp__insights-portal__whoami, mcp__insights-portal__get, mcp__insights-portal__search, mcp__insights-portal__draft_compose_url, mcp__insights-portal__draft_delete
---

# Reply to an email

One email, one reply, one draft. This skill is the orchestrator: run it in the main session (or as the `email-reply-orchestrator` agent), because it dispatches three workers and may have to ask the owner something. For a batch of inbound mail use `comms-inbox-replies`; for a new message that answers no email use `comms-draft-email`.

Nothing here sends. The last step puts the draft in the owner's own Outlook Drafts folder, where they read it and press Send. The Portal holds no send scope, and no command this skill runs can send.

The commands, all read-only except `email-deliver`, whose one write is `draft_push`. The one other write is `draft_delete`, on a stale draft, and only when the owner has answered "discard":

```bash
python3 ~/.claude/skills/comms-reply-to-email/scripts/find_contact.py "Dana Whitfield"                     # name or address -> pinned contact id, or not
python3 ~/.claude/skills/comms-reply-to-email/scripts/find_email.py CONTACT_ID                             # -> the latest email they sent, and whether the owner replied after it
python3 ~/.claude/skills/comms-draft-check/scripts/outbound_check.py --to ADDRESS --thread EMAIL_REF --json
python3 ~/.claude/skills/comms-reply-to-email/scripts/email_context_pack.py EMAIL_REF --contact CONTACT_ID --out RUN/pack.json
python3 ~/.claude/skills/comms-reply-to-email/scripts/email_draft_show.py DRAFT_ID                         # the checker's view, with the content hash
python3 ~/.claude/skills/comms-reply-to-email/scripts/email_deliver.py --draft DRAFT_ID --check RUN/check.json --contact CONTACT_ID --email EMAIL_REF --allow-recent-contact
python3 ~/.claude/skills/comms-reply-to-email/scripts/notify_owner.py --title "..." --link URL --record-ref portal://draft/DRAFT_ID
```

`rules.md` beside this file holds the owner's current settings (the revision rounds, what counts as their decision, the cooldown, an email that needs no reply) and the mechanics (the run folder, exit codes, the worker models). The briefs for the three workers are `briefs/researcher.md`, `briefs/drafter.md` and `briefs/checker.md`, each with a fixed return format; the check record the checker returns is validated by `email-deliver` against `briefs/checker.schema.json`. If the owner keeps standing rules on outbound mail elsewhere (setting `owner_profile`), read them, never quote them into a draft, a brief or a message.

## Steps

1. [script] Pin the target. Run `python3 ~/.claude/skills/comms-reply-to-email/scripts/find_contact.py "NAME OR ADDRESS"` and take the contact id from `pinned`; then `python3 ~/.claude/skills/comms-reply-to-email/scripts/find_email.py CONTACT_ID` and take `email._ref`; then `python3 ~/.claude/skills/comms-draft-check/scripts/outbound_check.py --to ADDRESS --thread EMAIL_REF --json` with the pinned email's `from_address`. When the owner's request names a different email than the latest ("the one about the invoice"), take it from `other_recent_inbound` only when one plainly matches, else ask. Make the run folder (`rules.md`) and save the three outputs there as `find.json`. From here on the contact id and the email ref are pinned: every later step uses exactly those two. A STALE_DRAFT hold is an unsent draft on the thread that answers an earlier email and predates this one; ask the owner whether to discard it and write a new reply (recommended) or stop and keep it. On "discard", save each draft's `email-draft-show` output as `RUN/stale-draft-ID.json` (the researcher reads what it proposed), call `draft_delete` on each id in `evidence.draft_ids`, re-run `outbound-check`, and carry on from its new verdict. Nothing is deleted without that answer. RECENT_CONTACT does not stop a reply the owner asked for (`rules.md`). → find-contact `several` or `partial`: ask → find-contact `none`: stop → find-email `none`: stop → find-email `replied`: stop → outbound-check `STALE_DRAFT`: ask → outbound-check `OPEN_DRAFT_SAME_THREAD`: stop → outbound-check `DAILY_CAP`: stop → outbound-check `RECENT_CONTACT`: step 2 → a command could not run, or any result not named here: ask
2. [hand-off: email-context-researcher] Dispatch the researcher with `briefs/researcher.md`, the pinned contact id and email ref and the run folder. It runs `email-context-pack`, reads what the pack cannot settle, writes `brief.md` in the run folder with every fact carrying its source ref, and returns the path and a short summary in the brief's fixed format. Do not read the pack yourself; `brief.md` is the record. → BLOCKED: stop
3. [judgment] Plan the reply from `brief.md` and the owner's request, and write `plan.md` in the run folder: what the email asks, what the reply says to each point, and the decisions that are the owner's (`rules.md` says what counts), each with its options and your recommendation. Decide nothing that is theirs. When the email needs no reply (a thank-you, an FYI, a confirmation of something already settled), stop and tell them why in one line. → no reply needed: stop → no decisions: step 5
4. [ask] Put the decisions to the owner in the format below and wait for their answers. Save them as `answers.md` in the run folder, verbatim. → the owner says not to reply: stop → answered: step 5
5. [hand-off: email-drafter] Dispatch the drafter with `briefs/drafter.md`, the pinned contact id and email ref, and the paths of `brief.md`, `plan.md` and `answers.md`. On a revision round, add the draft id and the checker's numbered fixes; the drafter revises that same draft in place rather than creating a second one. It returns the draft id. → BLOCKED: ask
6. [hand-off: email-checker] Dispatch the checker with `briefs/checker.md`, the draft id, the pinned contact id and email ref, and the paths of `brief.md` and `answers.md`, never `plan.md`: the check is worth something only if the checker has not seen the reasoning. It reads the draft with `email-draft-show` and returns PASS, or FAIL with numbered fixes, as one JSON block. Save that block verbatim as `check.json` in the run folder. → FAIL: step 5 (max 2) → FAIL after the last round: stop
7. [script] Run `python3 ~/.claude/skills/comms-reply-to-email/scripts/email_deliver.py --draft DRAFT_ID --check RUN/check.json --contact CONTACT_ID --email EMAIL_REF --allow-recent-contact` and save its JSON as `deliver.json`. It refuses without a PASS for this exact draft content, re-runs `outbound-check`, then pushes the draft into the Outlook inbox that received the email, threaded. On `delivered`, run `python3 ~/.claude/skills/comms-reply-to-email/scripts/notify_owner.py --title "Draft reply to NAME is in your Drafts" --link WEB_LINK --record-ref portal://draft/DRAFT_ID`. On `handoff_link` (the email came to a Gmail inbox), give the owner the compose link instead and do not notify. → email-deliver `refused` or `push_failed`: stop → email-deliver `delivered` or `handoff_link`: done

**Stop only where a branch says stop, and only when its premise holds.** A branch names what a command returned; before you act on it, read the evidence the command gave. When that evidence contradicts what the branch assumes (a "duplicate" draft that is days older than the email and answers an earlier one, a "reply already sent" dated before the email), do not stop: ask the owner, with the command's reason and the evidence, verbatim. A result no branch names is asked the same way, never guessed at and never treated as a stop. A stop the owner did not need costs them a second launch; a question costs them one answer.

On a stop, say why in one line and what the owner can do about it: the candidates to choose from, the existing draft's id, the date of the reply they already sent, the checker's open issues with the draft id (never the body), or `email-deliver`'s refusals.

## Asking the owner

In an interactive session, ask in chat as one numbered list they can answer in a line ("1) 450 2) yes 3) Thursday"), each decision with its options and your recommendation.

With no person in the session (a runner started it), end the turn with exactly one fenced JSON block and nothing after it:

```json
{"status": "needs_owner",
 "questions": [
  {"id": "meeting", "label": "Dana asks to meet next week. Offer a time?", "kind": "choice",
   "options": [{"id": "tue10", "label": "Tuesday 10:00"}, {"id": "thu14", "label": "Thursday 14:00"},
               {"id": "decline", "label": "Not next week"}],
   "recommended": "tue10"},
  {"id": "discount", "label": "Agree to the 10% discount Dana asks for?", "kind": "toggle", "recommended": "no"},
  {"id": "note", "label": "Anything to add?", "kind": "text"}]}
```

`kind` is `choice` (with `options`), `toggle` (yes or no) or `text`; `recommended` is an option id, `yes` or `no`, or omitted. The session is resumed with a message starting `The owner's answers:` followed by one `id: answer` line per question; save it as `answers.md` and carry on from the step that asked.

## Finishing

The last message of a run is one fenced JSON block:

```json
{"status": "done", "draft_id": "...", "delivered_to": "owner@example.com", "check": "PASS"}
```

or, for any stop:

```json
{"status": "stopped", "reason": "The owner already replied to Dana on 2026-09-23 after that email."}
```

`delivered_to` is the inbox `email-deliver` reports, or `"gmail compose link"` for a handoff.

## When no one is present

The steps are the same. Every `ask` becomes the `needs_owner` block above and the turn ends; nothing that is the owner's decision is guessed, and a blocked drafter is asked about, not worked around. Delivery still happens at step 7, because the owner asked for this reply and their own Drafts folder is where they answer mail; `notify-owner` tells them it is there.
