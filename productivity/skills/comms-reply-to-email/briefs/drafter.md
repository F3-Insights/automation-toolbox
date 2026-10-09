# Brief: draft the reply to one pinned email

## The question

Write the owner's reply to the pinned email, in their voice, saying what the plan says and nothing the owner has not approved, and stage it as one Portal draft.

## The inputs

- The pinned contact id and the pinned email ref (`portal://email/<id>`).
- The paths of `brief.md`, `plan.md` and, when the owner was asked, `answers.md`, all in the run folder.
- On a revision round only: the draft id and the checker's numbered fixes.

## What to do

1. Read the owner's voice guide (setting `voice_guide`) as your standing process says, then `brief.md`, `plan.md` and `answers.md`. Take the voice samples from the brief's Voice section; pull more sent mail only if it has fewer than three.
2. The recipient is the pinned contact and no one else. Do not search for the person again and do not resolve anyone by name. Address the draft to the contact's address the pinned email came from (the brief's Pinned line and the thread show it). No Cc and no Bcc: a pushed reply applies neither, and the draft will be refused if it carries one.
3. Every fact in the draft comes from `brief.md` or `answers.md`: dates, amounts, names, commitments. Answer each point under What the email asks, in the order the plan gives. The brief's Superseded draft section is a draft that was never sent: nothing in it was offered to anyone, so never write as if it was, and never carry over a line the brief marks as overtaken.
4. Where the plan marks something as the owner's decision, write only what `answers.md` says they decided. A decision with no answer is not written around and not guessed: return `BLOCKED:` naming it.
5. First round: `draft_create` with `recipient_to` the one address, `related_contact_id` the pinned contact id, `related_email_id` the pinned email id (the bare id, without `portal://email/`), and no `thread_id` (the Portal fills it in when the draft is delivered, which is how it later notices the owner sent it). Report provenance: `agent_slug="email-drafter"`, `trigger_ref={"kind": "email", "id": "<pinned email id>"}`.
6. Revision round: apply every numbered fix to the same draft with `draft_update(id=<draft id>, fields={"content": ..., "subject": ...})`. Change only the subject and the body; never the recipients. Never create a second draft for the same email.

## The return format

Return exactly this, at most 500 characters:

```
Draft created: <draft id> (reply to <pinned email ref>) | Draft revised: <draft id> (round <n>)
To: <name> (<address>)
Subject: <subject>
Fixes applied: <the fix numbers, or "none, first round">
Voice notes: <two or three short points>
```

Or one line starting `BLOCKED:` with the question the owner has to answer.
