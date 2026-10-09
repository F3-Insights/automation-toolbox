---
name: comms-inbox-replies
description: "Triage the inbox and draft replies in one pass: the email-triager agent classifies what came in and proposes a reply intent per thread, the owner says which to draft, then one drafter per thread stages a Portal draft delivered to Outlook Drafts. Nothing is sent. Use for \"go through my inbox\", \"what needs a reply\" or a batch of mail since a time. Not for one email; use comms-reply-to-email. Routing clerical mail to the assistant is comms-clerical-routing-orchestrator."
argument-hint: "[window, e.g. 'since 5pm yesterday'] [scope: one inbox, domain or contact]"
allowed-tools: Task, Bash, Read, mcp__insights-portal__whoami, mcp__insights-portal__draft_push,
  mcp__insights-portal__draft_compose_url
---

# Inbox replies

Two agents and one question in the middle. `email-triager` reads the mail and says what needs an answer, with Portal context on each sender. You approve. `email-drafter`, one per thread, writes the replies. Then each draft goes into the owner's own Drafts folder, where they read it and send it. Nothing here sends anything.

For a reply to a single email, stop here and run `comms-reply-to-email` instead. That skill is one email, one reply, checked before the same delivery at the end. This one is the batch, and it exists because triage and drafting both flood a main context if done inline.

**User provided:** $ARGUMENTS

## Step 1: triage

Parse `$ARGUMENTS` into a window and an optional scope. With no window, the default is since the start of the previous business day in the owner's timezone, and the agent resolves that itself from `whoami`.

Dispatch one `email-triager`:

```
Task(
    subagent_type="email-triager",
    description="Triage inbound mail",
    prompt="""
Triage inbound email.

Window: <the window, or "default: since the start of the previous business day">
Scope: <one inbox, one domain, one contact, or "all inboxes I may read">

Return your standard report: counts by class, then one block per REPLY thread, then the
compact DELEGATE and FYI lists.
"""
)
```

It comes back with counts and up to fifteen REPLY blocks, each carrying the email `_ref`, the inbox, the sender, what is being asked, a proposed reply intent, urgency and anything the drafter has to know. Do not re-read the mail yourself; the report is the record.

## Step 2: ask the owner, once, as a numbered list

Show the REPLY list and nothing else. One numbered line per thread: sender, subject, urgency and the proposed reply intent in the agent's words. Where the intent came back `UNKNOWN`, show the question instead, marked so it stands out.

Ask one question, phrased so it can be answered in a line:

> Which of these should I draft? Answer per number: "ok" to draft as proposed, a short
> instruction to change the intent, an answer where the intent is UNKNOWN, or "skip".
> For example: "1 ok, 2 say no for now, 3 skip, 4 ok but propose Thursday instead."

Then wait. Do not draft anything before the answer arrives.

Print the DELEGATE and FYI lists below the question so the owner sees them while they decide, and say plainly that you are doing nothing with them.

**In a headless run with no owner present**, skip the question and draft only the threads whose reply intent is not UNKNOWN. List the UNKNOWN threads in the report as awaiting a decision, with the question each one needs answered. A headless run never guesses a decision that is the owner's.

## Step 3: check each approved thread before drafting

For every thread the owner approved, run the gate first:

```bash
python3 ~/.claude/skills/comms-draft-check/scripts/outbound_check.py --to <recipient email> --thread <the email _ref> --json
```

Exit 0 is ALLOW and you dispatch a drafter. Any non-zero exit means do not draft: exit 3 is a rule tripping, exit 2 means the check could not run. The command reads the Portal's own drafts and sent mail and answers whether a draft to this person on this thread may be created now, which is the duplicate protection that used to be a request in a prompt.

On a HOLD:

- **Interactive.** Show the owner the rule and the reason in one line and ask whether to draft anyway. A `RECENT_CONTACT` hold may be overridden, and an approval the owner already gave for this thread in the Step 2 numbered list is such an override: they said to answer this person, so a cooldown meant for unprompted nudges does not outrank them.
- **No one present.** Skip the thread and list it in the report with the rule, the reason and the evidence. Do not override anything.

`OPEN_DRAFT_SAME_THREAD` is never overridden, in either mode. A draft for that thread already exists and a second one is the exact thing this gate is for. Surface the existing draft id from the evidence instead, and say it is waiting in the Portal.

Exit 2 is not a pass. A gate that could not run has not been satisfied: report it and move on.

## Step 4: fan out the drafters

Dispatch one `email-drafter` per thread that came back ALLOW or that the owner overrode, **all in a single message** so they run in parallel. One draft per agent is the contract; do not hand one agent several threads.

Each prompt carries the triager's block verbatim plus the owner's answer:

```
Task(
    subagent_type="email-drafter",
    description="Draft reply",
    prompt="""
Draft a reply in the owner's voice.

<the triager's REPLY block, pasted unchanged, including Ref, Inbox, From, Asked,
 Reply intent, Urgency and Drafter needs to know>

the owner's answer: <their instruction for this number, verbatim; or "draft as proposed">

Follow your standard process: read the owner's voice guide (setting voice_guide), resolve the recipient, find the source
email from the Ref so the draft threads, sample prior sent mail, draft, run the voice check,
create the draft with draft_create, and return the terse summary.
"""
)
```

Where the reply intent was UNKNOWN and the owner answered, put their answer in the `the owner's answer` line and leave the UNKNOWN text in the block so the drafter can see what was being decided. Where the intent was UNKNOWN and they did not answer, do not dispatch; the thread stays open.

An agent that returns `BLOCKED:` did not create a draft. Relay the blocking question and move on; do not re-dispatch it with a guess.

## Step 5: deliver each draft to the mailbox it belongs in

A draft sitting in the Portal is not where the owner answers mail. For every draft a drafter returned on a thread the owner approved in Step 2, put it where they will see it.

**Their approval in Step 2 covers this.** They said to answer that person on that thread, and delivery here means their own Drafts folder in their own mailbox, which they still have to open, read and send themselves. Do not ask a second question per draft.

### Which mailbox

The triager's block names the inbox the thread arrived in. Call `whoami` once, before the first delivery, and read `inboxes`: each row carries the inbox and its `provider`. Match the block's inbox to that row and let the provider decide the path. One `whoami` covers the whole batch.

### An Outlook inbox

```
draft_push(id="<draft_id>")
```

That is the whole call. No approval step comes first: the draft lands in the owner's own mailbox, which has not left the organisation, and Outlook's Send button is the gate. A reply threads under the original conversation and delivers to the inbox that received it, so a reply never needs a `mailbox` argument. A draft the drafter created as a new message rather than a reply takes `mailbox="<address>"` only when the owner has more than one Outlook inbox.

Push each draft once. A second push of the same draft is refused, because it would put the same message in the folder twice. Treat a refusal as already delivered rather than as a failure, and say so in the report.

### A Gmail inbox

The Portal cannot deliver into Gmail. Say that plainly rather than leaving the owner to wonder where the draft went, and hand over the link instead:

```
draft_compose_url(id="<draft_id>", target="gmail")
```

List the returned URL against that draft. The owner opens it, the compose window comes up with the draft in it, and they send from there.

### Failures

- *"lacks the Mail.ReadWrite permission"*: the inbox connection needs reauthorising in the Portal under Settings, Connections, Update permissions. The draft is unharmed; the push can be run again afterwards. Report it and move to the next draft.
- *"multiple Outlook inboxes"*: the error names the addresses. Retry once with `draft_push(id="<draft_id>", mailbox="<the inbox the triager block named>")`.
- Anything else: report the draft id, the error in one line, and that the draft is still in the Portal. Never retry an error you do not understand.

### When no one is present

Never push and never build a compose link. Leave every draft in the Portal and list the draft ids in the report as awaiting delivery. Delivery puts a message one click from being sent in the owner's name, and nobody approved it.

## Step 6: report

One line per draft, ending in where it now is:

```
<n>. <recipient> · "<subject>" · draft <draft_id> · <reply to <thread> | new message> ·
     <pushed to Outlook Drafts | Gmail, no Portal delivery: <compose link> | left in the Portal>
```

Then a line for every push that failed, naming the draft, the reason in one line and the fact that the draft is still in the Portal.

Then a line for each thread that was skipped, held or blocked and why, naming the `outbound-check` rule where that was the cause, then the DELEGATE list with the suggested owner for each, then the FYI list in one line each.

Close with the counts: how many came in, how many were drafted, how many are still waiting on a decision.

## Key rules

- **Nothing is ever sent.** The Portal holds no send scope and neither do you. A push puts the draft in the owner's own Drafts folder; they read it and press Send themselves.
- **Delivery follows the approval, it is not a second one.** The owner's yes in Step 2 is a yes to answering that person on that thread, and their Drafts folder is where an answer is written. With no one present, nothing is delivered at all.
- **One question, once.** Step 2 is the only time this skill asks anything, with one exception: an `outbound-check` HOLD in an interactive run, which is a yes or no about one thread. If a drafter comes back blocked, that goes in the report, not into a second round of questions.
- **Every path that ends in a draft goes through `outbound-check` first.** No exceptions for a thread that looks obviously fine, because "obviously fine" is what every job that drafted a duplicate believed.
- **Never show a draft body.** The Portal is the source of truth for draft content. Showing it here invites edits that do not sync back.
- **Never decide for the owner.** An UNKNOWN intent with no answer is not drafted, in an interactive run or a headless one.
- **Drafts in the owner's voice come only from `email-drafter`.** Do not write a reply in this skill's own context, however short it looks.
- **Portal write safety**: the drafters create Portal records. They follow the portal-write-safety skill; so do you if you touch anything else.
