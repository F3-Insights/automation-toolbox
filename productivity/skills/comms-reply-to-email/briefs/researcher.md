# Brief: research one email before it is answered

## The question

What does this email ask, and what does the reply need to know to answer it? You extract and cite. You do not decide what the owner should say, and you do not write any part of the reply.

## The inputs

- The pinned contact id and the pinned email ref. They are fixed: research this person and this email, not whoever else the thread mentions.
- The run folder, an absolute path under `<state_dir>/comms-reply/`.
- Any `RUN/stale-draft-*.json`: an unsent draft on this thread that the owner chose to discard because it answered an earlier email. Read each one.

## What to do

1. Run `python3 ~/.claude/skills/comms-reply-to-email/scripts/email_context_pack.py EMAIL_REF --contact CONTACT_ID --out RUN/pack.json`, then read `RUN/pack.json`. It holds the thread with full bodies, the contact card, open tasks and their projects, the owner's recent sent mail to this person, and free calendar slots when the email seems to ask to meet. `unknown` lists what it could not get and why.
2. If the email asks to meet and `calendar` is null, run it again with `--slots yes`.
3. Spend Portal reads only on what the pack cannot settle: a note or task the email refers to, an earlier thread it quotes, a company fact it depends on. Use `get`, `dereference`, `search` and `email_bodies`. Do not page listings.
4. For each `RUN/stale-draft-*.json`, list under Superseded draft what it proposed (a date, an offer, a question), each line marked with what in the thread since has overtaken it, or "still open" when nothing has. It was never sent, so nothing in it is Already decided.
5. Write `RUN/brief.md` in the format below. Write nothing else, anywhere.

## Rules

- Every fact carries the `_ref` it came from, in brackets at the end of its line. A fact you cannot cite is not in the brief.
- Copy dates, amounts, names and commitments exactly as the source writes them. Do not convert, round or summarise a number.
- Say who said what. "Dana asked for X" and "the owner offered Y on 2026-09-23" are different facts, and the drafter must not promise what the owner never offered.
- Where the thread shows the owner already decided something (a price quoted, a date agreed), list it under Already decided with its source. Where it does not, it goes under Open for the owner.
- The pack's `unknown` entries go under Not found, with the reason. Never fill a gap.

## `brief.md`

```markdown
# Brief: reply to <contact name>, <email subject>

Pinned: contact <contact id> · email <email ref> · received <received_local>

## What the email asks
1. <each question or request, in their words where short> [portal://email/...]

## Thread so far
- <date> <who>: <one line> [ref]

## Who they are
- <role, company, relationship, priority, last touch> [ref]

## Already decided
- <what the owner already said or agreed, with the date> [ref]

## Open for the owner
- <each point the reply needs that the owner has not decided: a price, a yes or no, a date> [ref of the ask]

## Related work
- <open task or project, status, due date> [ref]

## Superseded draft
- <what the discarded draft proposed>: <overtaken by ... [ref], or still open> [draft id]
  ("none" when there is no stale-draft file)

## Calendar
- <free slots, local time, when the email asks to meet; "not requested" otherwise> [pack]

## Voice
- <how the owner opens and closes with this person, register, length, from the samples> [refs]

## Not found
- <field>: <reason>
```

## The return format

Return exactly this and nothing else:

```
BRIEF: <absolute path to brief.md>
ASKS: <number of asks>; OPEN FOR OWNER: <number>; ASKS TO MEET: yes|no
SUMMARY: <at most three sentences: what they want and what the reply turns on>
GAPS: <none, or the Not found fields, comma separated>
```

If the pinned email cannot be read, or the pack command fails, write no brief and return one line starting `BLOCKED:` with the reason.
