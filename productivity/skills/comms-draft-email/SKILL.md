---
name: comms-draft-email
description: "Draft a new email in the owner's voice, one that answers no email received: an introduction, a first outreach, a note after a call. Pulls prior sent emails, applies the voice guide, creates the draft and delivers it to Outlook Drafts; never sends. Use for \"write an email to X about Y\". Not for replying to someone's email (comms-reply-to-email), a batch of inbox replies (comms-inbox-replies) or nudging people who owe the owner something (comms-follow-ups)."
argument-hint: '[recipient name] -- [what you want to say]'
allowed-tools: Task, Bash, mcp__insights-portal__search, mcp__insights-portal__whoami,
  mcp__insights-portal__draft_push, mcp__insights-portal__draft_compose_url, Read
---

# Draft Email

Produce an email draft that actually sounds like the owner by delegating to the `email-drafter` subagent. The subagent reads the voice guide, samples prior sent emails to the recipient, drafts, self-checks against the voice rules, and creates the draft in the Portal. This skill then delivers it into the owner's real Outlook Drafts folder (`draft_push`), where they review it and send it themselves. Nothing here can send.

**Replying to an email someone sent?** Follow `comms-reply-to-email` instead. It supersedes this skill for replies: it pins the contact and the exact email in code, has the context researched into a sourced brief, asks only the decisions that are the owner's, has the draft checked against the brief, and delivers only a draft that passed. This skill stays for a new message that answers no email: an introduction, a first outreach, a note after a call.

One recipient, one intent, one draft. To answer a batch of inbound mail, run `comms-inbox-replies` instead: it triages the inbox first, asks which threads to answer as one numbered list, fans out a drafter per thread, and delivers each draft the same way this skill does.

**User provided:** $ARGUMENTS

## Instructions

### Step 1: Parse Input

Split `$ARGUMENTS` on the first em dash (U+2014), `--`, or ` - ` (a hyphen with a space on each side):

- **Left side** = recipient (name, email, or both)
- **Right side** = intent (what the owner wants to say)

If no separator, ask:
> Who's the recipient and what do you want to say?

### Step 2: Resolve Ambiguity (minimally)

Only ask questions if a critical detail is missing:

- No recipient at all → ask
- No intent at all → ask
- Intent is "reply to <some email>" → stop here and follow `comms-reply-to-email` with the recipient and the intent

Do NOT ask the user about tone, register, opening, or closing; those are the subagent's job to derive from the voice guide + prior emails.

### Step 3: Check before drafting

Run the gate before you dispatch anything:

```bash
python3 ~/.claude/skills/comms-draft-check/scripts/outbound_check.py --to <recipient email> --thread <source email _ref, if this is a reply> --json
```

Without a thread, pass `--subject` instead so the check has something to match on.

Exit 0 is ALLOW and you go on to Step 4. Any non-zero exit means do not draft: exit 3 is a rule tripping, exit 2 means the check could not run, and a gate that could not run has not been satisfied.

On a HOLD, show the owner the rule and the reason in one line and ask whether to draft anyway:

> `outbound-check` says HOLD: <rule>, <reason>. Draft anyway?

A `RECENT_CONTACT` hold may be overridden; they asked for this message, and the cooldown is there to stop unprompted nudges stacking up, not to argue with them. An `OPEN_DRAFT_SAME_THREAD` hold is never overridden: a draft for this thread is already waiting in the Portal. Give them the draft id from the evidence and offer to push that one to Outlook instead, which is Step 6 with a draft they already have.

In a run with no one present, a HOLD means skip and list it with the rule and the reason. Never override on your own authority.

### Step 4: Delegate to email-drafter

Spawn the `email-drafter` subagent with a self-contained prompt:

```
Task(
    subagent_type="email-drafter",
    description="Draft voice-matched email",
    prompt="""
Draft an email in the owner's voice.

Recipient: <parsed recipient>
Intent: <parsed intent>

<Include any extra context the user provided: source email to reply to, subject hint, deadline, related meeting, etc.>

Follow your standard process: read the owner's voice guide (setting voice_guide), sample recent sent emails
to this recipient and generally, draft, run the voice-check pass, create the draft
via draft_create (pass related_email_id if this is a reply), and return the terse summary.
"""
)
```

### Step 5: Relay the Subagent's Summary

The subagent returns a ≤500 char summary with draft_id, recipient, subject, whether it's a reply, and voice notes. Relay it verbatim to the user.

Do NOT paste the draft body into the conversation. It lives in the Portal.

### Step 6: Deliver it to the mailbox it belongs in

The same rule the batch skill follows, for one email. The owner asked for this message, so putting it in their own Drafts folder is carrying out the request, not a new decision. Do not ask a second time.

Call `whoami` and read `inboxes`. Each row carries the inbox and its `provider`. For a reply, the inbox is the one that received the source email; for a new message it is whichever inbox this is going out from. The provider decides the path.

**An Outlook inbox:**

```
draft_push(id="<draft_id>")
```

One call, no approval step before it. The draft lands in the owner's own mailbox and Outlook's Send button is the gate. A reply threads under the original and delivers to the inbox that received it, so it needs no `mailbox` argument; a new standalone message takes `mailbox="<address>"` only when they have more than one Outlook inbox. Push once: a second push of the same draft is refused, because it would duplicate the message in the folder.

Relay the returned `web_link` so they can jump straight to it:

```
Delivered to Outlook Drafts. Review and send there: <web_link>
```

**A Gmail inbox:** the Portal cannot deliver into Gmail. Say so plainly and hand over the link instead:

```
draft_compose_url(id="<draft_id>", target="gmail")
```

```
Gmail delivery is not supported by the Portal yet. Open the draft here and send from
Gmail: <url>
```

**Error handling for draft_push:**

- *"lacks the Mail.ReadWrite permission"* → tell the owner: reconnect the inbox via Portal → Settings → Connections → "Update permissions", then run `draft_push` again. The draft is unharmed.
- *"multiple Outlook inboxes"* → the error lists the addresses; ask which one and retry with `draft_push(id=..., mailbox="<address>")`. (Replies never need this: they deliver to the inbox that received the original.)
- *Anything else* → report the error in one line and say the draft is still in the Portal under its id. Never retry an error you do not understand.

**With no one present**, never push and never build a compose link. Leave the draft in the Portal, report its id, and say it is awaiting delivery.

## Key Rules

- **One-shot compose**: no back-and-forth iteration on the body inside this skill. If the user wants revisions, they can run `/comms-draft-email` again or edit in the Portal/Outlook.
- **Never show the draft body**: the Portal is the source of truth for the draft content. Showing it here invites in-conversation editing that doesn't sync back.
- **Never send**: `draft_create` stages, `draft_push` delivers to the Drafts folder; the Portal never holds a send scope, and the owner always sends from Outlook themselves.
- **Delivery follows the request**. Asking for this email is asking for it to be where they write email. With no one present, nothing is delivered.
- **Every path that ends in a draft goes through `outbound-check` first**. Step 3 is not optional and there is no thread obvious enough to skip it for. A non-zero exit means no draft.
- **Trust the subagent's voice check**: don't re-judge the output in this skill.
- **Portal write safety**: before any create/update/draft call, load the portal-write-safety skill and follow it (propose by default, resolve entities by UUID never by name, `CANCELLED` with evidence never `DONE`, `sync_health` first).

## Example

**User:** `/comms-draft-email Sarah Chen -- follow up on today's call, confirm Q3 rollout, propose next Wednesday 10am for check-in`

**You:**
1. Parse: recipient="Sarah Chen", intent="follow up on today's call, confirm Q3 rollout, propose next Wednesday 10am for check-in"
2. Run `python3 ~/.claude/skills/comms-draft-check/scripts/outbound_check.py --to sarah@example.com --subject "follow up: today's call" --json`; it exits 0 ALLOW.
3. Spawn `email-drafter` with that prompt.
4. Relay:
   ```
   Draft created: d_456 (reply to Sarah's Tue email)
   To: Sarah Chen (sarah@example.com)
   Subject: Follow up: today's call
   Voice notes: Used "Hi Sarah," matching 9/10 prior opens; 3 short paragraphs with bulleted recap; clear scheduling ask at end.
   ```
5. `whoami` says the inbox this goes out from is an Outlook inbox.
6. `draft_push(id="d_456")`, then:
   ```
   Delivered to Outlook Drafts. Review and send there: https://outlook.office.com/...
   ```
