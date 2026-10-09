---
name: comms-follow-ups
description: Chase what the owner is waiting on, interactively. The waiting-on-tracker agent finds work sitting with other people and threads nobody answered and proposes one action each; the owner says which to act on; one drafter per approved nudge writes it, and the drafts land in the owner's Outlook Drafts folder. Nothing is sent. Use for "what am I waiting on", "chase my follow-ups" or "nudge whoever owes me". For the unattended pass, start comms-follow-up-orchestrator.
argument-hint: "[staleness days] [silence business days] [scope: a project, a domain or a person]"
allowed-tools: Task, Bash, Read, mcp__insights-portal__whoami, mcp__insights-portal__draft_push,
  mcp__insights-portal__draft_compose_url, mcp__insights-portal__create_task,
  mcp__insights-portal__update_task, mcp__insights-portal__create_note
---

# Follow-ups

One agent and one question in the middle. `waiting-on-tracker` finds the work that has left the owner's hands and not come back, and proposes one action per item. You approve. `email-drafter`, one per approved nudge, writes the messages, and each draft goes into the owner's own Drafts folder. Nothing here sends anything.

This is the outbound twin of `comms-inbox-replies`. That skill answers what came in; this one chases what went out. Both end at the same two places: `outbound-check` in front of every draft, and `email-drafter` as the only writer of one.

**User provided:** $ARGUMENTS

## Step 1: find what is outstanding

Parse `$ARGUMENTS` into a staleness window in days (default 7), a silence window in business days (default 3) and an optional scope. Dispatch one `waiting-on-tracker`:

```
Task(
    subagent_type="waiting-on-tracker",
    description="Find what is outstanding",
    prompt="""
Find the work the owner is waiting on.

Staleness window: <n> days
Silence window: <n> business days
Scope: <a project, a domain, a person, or "everything the owner can see">

Return your standard report: the header counts, one block per item with its evidence,
context and proposed action, then the nudge array between the two marker lines.
"""
)
```

It comes back with up to fifteen items across its three lenses, each carrying who is being waited on, since when, the `_ref`s, the Portal context and one proposed action, then the nudge block. Do not repeat its reads; the report is the record.

## Step 2: ask the owner, once, as a numbered list

One numbered line per item, in the agent's words, short enough to scan:

```
<n>. <what is being waited on> · <who> · <how long> · proposed: <the action>
```

Group them so the shape is visible: the nudges together, then the items that want a meeting raised, then the escalations, then the decisions that are theirs, then the ones to close.

Ask one question, phrased so it can be answered in a line:

> Which of these should I act on? Answer per number: "ok" to do as proposed, a short
> instruction to change it, or "skip". For example: "1 ok, 2 skip, 3 ok but ask for
> Thursday, 4 close it."

Then wait. Nothing is drafted, created or updated before the answer arrives.

Where the proposed action was **convert to a decision the owner must make**, put the question itself in the numbered line, with the options the agent said the evidence supports. That is the one line on the list where their answer is the work rather than the permission for it.

## Step 3: check each approved nudge before drafting

For every item the owner approved whose action is a nudge, run the gate first:

```bash
python3 ~/.claude/skills/comms-draft-check/scripts/outbound_check.py --to <recipient email> --thread <the thread _ref, if there is one> --subject "<subject>" --json
```

Pass `--thread` when the nudge carries a `thread_ref` and `--subject` in either case, so the check has something to match on when there is no thread. Exit 0 is ALLOW and you dispatch a drafter. Any non-zero exit means do not draft: exit 3 is a rule tripping, exit 2 means the check could not run, and a gate that could not run has not been satisfied.

The three rules, and what each one means here:

- **`OPEN_DRAFT_SAME_THREAD` is never overridden**, in either mode. A draft for that thread is already waiting. Surface the existing draft id from the evidence, say it is in the Portal, and offer to deliver that one instead. A second draft is the exact thing this gate exists to stop.
- **`RECENT_CONTACT` may be overridden by the owner's explicit approval.** The cooldown is there to stop unprompted nudges stacking up on one person, and it does not outrank a person who has just read the item and said to chase it. Show them the rule and the reason in one line and ask whether to go ahead. Their yes in Step 2 is approval of the item, not of overriding a cooldown, so this one question is worth asking.
- **`DAILY_CAP` stops the batch.** It is a count of drafts that already exist since local midnight, so it is not about this recipient and overriding it for one nudge just moves the problem to the next one. Stop dispatching, report every remaining nudge as not drafted because the cap was reached, and say they can run the skill again tomorrow.

## Step 4: fan out the drafters

Dispatch one `email-drafter` per cleared nudge, **all in a single message** so they run in parallel. One draft per agent is the contract; do not hand one agent several nudges.

```
Task(
    subagent_type="email-drafter",
    description="Draft follow-up",
    prompt="""
Draft a follow-up in the owner's voice.

Recipient: <recipient_name> <<recipient_email>>
Thread: <thread_ref, or "no thread: this is a new message">
Task: <task_ref, or "none">
Intent: <the nudge's `ask`, verbatim>
Why now: <the nudge's `why_now`, verbatim>
Context the tracker found: <the item's Context line>

the owner's answer: <their instruction for this number, verbatim; or "chase as proposed">

Follow your standard process: read the owner's voice guide (setting voice_guide), resolve the recipient, find the source
email from the thread ref so the draft threads, sample prior sent mail, draft, run the voice
check, create the draft with draft_create, and return the terse summary.
"""
)
```

This is a chase, not a complaint. The owner still has to work with this person next week, so the intent you pass says what is needed and by when, never that they are late.

An agent that returns `BLOCKED:` did not create a draft. Relay the blocking question and move on; do not re-dispatch it with a guess.

## Step 5: deliver each draft to the mailbox it belongs in

Exactly as `comms-inbox-replies` does it, and for the same reason: a draft in the Portal is not where the owner answers mail, and their approval of the item in Step 2 covers delivery into their own Drafts folder.

Call `whoami` once before the first delivery and read `inboxes`, each row carrying its `provider`. For a nudge on an existing thread the inbox is the one that thread lives in; for a new message it is whichever inbox it goes out from.

- **An Outlook inbox:** `draft_push(id="<draft_id>")`. One call, no approval step before it. A reply threads under the original and delivers to the inbox that received it, so it needs no `mailbox` argument; a new standalone message takes `mailbox="<address>"` only when the owner has more than one Outlook inbox. Push once: a second push of the same draft is refused, because it would duplicate the message in the folder. Treat a refusal as already delivered.
- **A Gmail inbox:** the Portal cannot deliver into Gmail. Say so plainly and call `draft_compose_url(id="<draft_id>", target="gmail")`, then list the returned link.

On a failure, report the draft id, the reason in one line and the fact that the draft is still in the Portal. A permissions error means the inbox connection needs reauthorising in the Portal under Settings, Connections, Update permissions; the draft is unharmed and the push can be run again. Never retry an error you do not understand.

## Step 6: the actions that are not email

Only after the owner approved that item, and only what they approved.

- **Raise at a named upcoming meeting.** Create a task about that person so it is in front of the owner when the meeting comes: `create_task(title="<raise <the item> with <name>>", task_contact_id="<their contact id>", due_date="<the meeting date>", project_id=...)`. `task_contact_id` is who a task is about, which is what this is, and it is a different field from the assignee.
- **Reassign or escalate.** `update_task(id="<task id>", fields={"assignees": ["<user email or agent slug>"]})`. `assignees` is a replace, not an append: the list you pass becomes the whole set, so include anyone who should stay on it. Where the Portal showed nobody to escalate to, do not invent one; write it up as a note and leave the choice with the owner.
- **Convert to a decision.** Their answer in Step 2 is the decision. Record it with `create_note(content=..., associations=[{"entity_type": "project", "entity_id": "..."}], note_type="episodic")`, and create the task their answer implies. A note must carry at least one association.
- **Close as no longer needed.** `update_task(id="<task id>", status="CANCELLED")`, with the evidence in the update. `CANCELLED` with evidence, never `DONE`: the work did not happen, it stopped mattering, and the record should say which.

Load the portal-write-safety skill and follow it before any of these: resolve entities by UUID and never by name, and check the record you are about to change is the one you read.

## Step 7: report

One line per draft, ending in where it now is:

```
<n>. <recipient> · "<subject>" · draft <draft_id> · <pushed to Outlook Drafts | Gmail, no
     Portal delivery: <compose link> | left in the Portal>
```

Then a line for every push that failed and why. Then a line per nudge that was held or blocked, naming the `outbound-check` rule that caused it. Then one line per non-email action taken, naming the task or note id. Then the items the owner skipped, in one line each.

Close with the counts: how many items came back, how many were acted on, how many are still waiting on a decision, and how many the agent left out of its own report.

## When no one is present

- **Draft only nudges whose ask needs no decision from the owner.** "Send the file you said you would send" needs nothing from them. "Confirm the price" needs them. Draft the first kind, list the second kind with the question each one needs answered, and guess at neither.
- **Never override a HOLD.** Not `RECENT_CONTACT`, not `DAILY_CAP`, not anything. An override is a judgment the owner makes, and there is nobody to make it. Skip the nudge and list it with the rule, the reason and the evidence.
- **Never push and never build a compose link.** Every draft stays in the Portal and the report lists the ids as awaiting delivery. Delivery puts a message one click from going out in the owner's name.
- **Take no non-email action.** No task created, no assignee changed, no task cancelled. Step 6 runs on an approval that was not given. List what would have been done.

## Key rules

- **Nothing is ever sent.** The Portal holds no send scope and neither do you. A push puts the draft in the owner's own Drafts folder; they read it and press Send themselves.
- **One question, once.** Step 2 is the only time this skill asks anything, with one exception: a `RECENT_CONTACT` hold in an interactive run, which is a yes or no about one nudge.
- **Every path that ends in a draft goes through `outbound-check` first.** No exceptions for a nudge that looks obviously fine.
- **Drafts in the owner's voice come only from `email-drafter`.** Do not write a chase in this skill's own context, however short it looks.
- **Never show a draft body.** The Portal is the source of truth for draft content.
- **Never decide for the owner.** An item the tracker turned into a decision is theirs to answer. It is not drafted, acted on or closed until they do.
