---
name: email-drafter-method
description: "Reference run by productivity-worker (dispatched with model opus), one draft per dispatch, for comms-steward, comms-follow-ups, comms-inbox-replies, comms-reply-to-email and other departments' drafting, not for a user request: the procedure for writing one email in the owner's voice and staging it as a Portal draft. Covers loading the voice guide, resolving the recipient, finding the source email for a reply, sampling the owner's sent mail to that recipient, drafting, the mandatory voice-check pass, draft_create and the terse summary returned to the parent. Never sends. Not for drafting a new email interactively; use comms-draft-email, or comms-reply-to-email for a checked reply."
---

# Email drafter: the procedure

Write one email that genuinely sounds like the owner, and stage it as a Portal draft. Run it as `productivity-worker` with model opus, one draft per dispatch, briefed to follow this skill. This is the only place drafts in the owner's voice are made. You never send: `draft_create` (and `draft_update` on a draft you were told to revise) are your only writes; the caller owns delivery.

## Inputs

The parent (skill or user) should give you:

- **Recipient** (name and/or email; may be ambiguous)
- **Intent**: what the owner wants to say, in their words or as a summary
- **Optional context**: meeting notes, a source email to reply to, action items to include, deadline, subject line hint
- **Optional Memo context**: a scoped packet of positions, relationship context, and cross-channel conversation state, or a local file path to that packet. It is local private data, not a complete Portal search.

### A triager block

The common batch case is a REPLY block produced by a triage on `email-triager-method`, passed to you verbatim. It carries the fields you need under other names, so map them straight across:

| Triager field | What you do with it |
|---|---|
| `Ref` | the source email. Dereference or `get` it; this is your `related_email_id`. |
| `Inbox` | which of the owner's accounts the reply goes out from. Mention it in your summary. |
| `From` | the recipient. The relationship note tells you the register to start from. |
| `Context` | who this person is to the owner, read from the Portal: priority, company, open tasks, the last and next meeting, unanswered mail. It sets the register and it is why a line like "ahead of Tuesday" can be written at all. It is not a fact to repeat back at them. |
| `Asked` | what the reply has to address. Every point here gets answered or acknowledged. |
| `Reply intent` | the intent. If it reads `UNKNOWN`, the caller must supply the owner's decision alongside the block; draft nothing on an unanswered UNKNOWN and say so instead. |
| `Urgency` | whether the message proposes a date or asks for one. |
| `Drafter needs to know` | attachments, deadlines, prior commitments. Honour every one. |

### A pinned reply (comms-reply-to-email)

When the brief comes from `comms-reply-to-email` it names a **pinned contact id** and a **pinned email ref**, and gives you the paths of `brief.md`, `plan.md` and `answers.md` in a run folder. That brief (`briefs/drafter.md` in the skill) replaces Steps 2 and 3 below and narrows the rest:

- Read those three files with `Read`. Every fact in the draft comes from `brief.md` or `answers.md`; a decision the plan marks as the owner's is written only as `answers.md` states it.
- The recipient is the pinned contact, at the address the pinned email came from. Do not search for the person or resolve anyone by name. No Cc, no Bcc.
- `related_contact_id` is the pinned contact id and `related_email_id` the pinned email's bare id. Leave `thread_id` unset.
- On a revision round you are given the draft id and numbered fixes: apply them with `draft_update` on that draft, subject and body only, and never create a second draft. `draft_update` is for that and nothing else.

`email-deliver` refuses a draft tied to any other contact or email, addressed to anyone else, or carrying a Cc or Bcc, so a draft that strays from the pin is simply never delivered.

**You cannot ask the caller a question.** If something critical is missing, or the recipient resolves to two equally plausible contacts, or an UNKNOWN intent arrived with no decision, do not guess and do not create a draft. Return the blocking question as your whole summary, prefixed `BLOCKED:`, and stop. One round trip through the caller is cheaper than a wrong draft in the owner's name.

## Reference sources

Your three reference sources are:

1. **The owner's voice guide (setting `voice_guide`)**: openings, closings, framing rules, forbidden phrases and register by recipient. Read it first, every time. If the setting is missing, say so and stop.
2. **Recent sent emails**: the owner's actual corpus for per-recipient tone calibration
3. **The `unslop-email` skill**: load it with the Skill tool. It is the editing standard for a message: the opening sentence test, one decision stated as choices, words a forwarded reader could take badly, and the mechanics (no dashes, ranges spelled out, sentence case). Where it and the voice guide disagree, the voice guide wins, because it describes this writer and `unslop-email` describes the genre.

Where a Memo packet or cross-channel state is supplied, newer correspondence and the owner's corrections win over it: latest captured does not mean independently verified current.

## Rules

- **Never send.** `draft_create`, and `draft_update` on a draft you were told to revise, are your only writes, you don't approve, and you don't push; the parent skill owns delivery, gated on the user's explicit yes. Where a hook enforces this, never try to work around it.
- **Read the voice guide every invocation**: you don't have persistent memory across calls.
- **No fabrication**: if you don't have the prior email corpus or can't resolve the recipient, return `BLOCKED:` with what is missing. Never invent a fact, a date, a number, or a commitment the owner has not made.
- **Never decide for the owner.** Price, scope, a yes or no to a person, a commitment of their time: if the intent does not carry their answer, you do not have it. `BLOCKED:` and stop.
- **Output cap**: your summary to the parent is at most 500 chars. The draft body lives in the Portal.
- **One draft per invocation**: if the parent asks for multiple drafts, handle them sequentially, one summary per draft.

## Procedure

### Step 1: Load the Voice Guide (ALWAYS)

Read the file the `voice_guide` setting names.

This contains forbidden phrases, opening/closing conventions, framing rules, register-by-recipient-type table, and pre-send checks. Hold this in working memory while drafting, you will self-check against it before emitting.

### Step 2: Resolve the Recipient

If you have a name but no contact id:
```
search(query="<name>")
```

Contacts rank in the results. Pick the best match; `get(entity_type="contact", id_or_query="<id or email>")` hydrates full context (company, recent emails, notes) if you need it. If two or more are equally plausible, return `BLOCKED:` with the candidates named rather than picking one. For a cold external recipient with no Portal record, proceed without a contact id if you were given their address, and return `BLOCKED:` if you were not.

### Step 3: Identify the Source Email (replies only)

If the intent is a reply to something the owner received, find that email and keep its id:
```
list_entities(entity_type="email", filters={"contact_id": "<resolved_id>", "direction": "received"}, limit=5)
```
(or `search(query="<subject fragment>")`.)

This matters: `related_email_id` is what lets the Portal deliver the draft threaded under the original conversation in Outlook. Without it the draft can only be delivered as a new standalone message. If you can't find the source email, say so in your summary rather than guessing.

### Step 4: Sample the Owner's Voice for This Recipient

Before selecting wording, read any supplied Memo packet (use `Read` if a path was supplied). Preserve the distinctions between explicit positions, open options, user observations, hypotheses, and assistant interpretations. Use only entries relevant to this recipient AND the matter being discussed. Private relationship context may inform tone; do not repeat speculative motives or unrelated business positions to the recipient. Latest captured does not mean independently verified current: newer correspondence and the owner's corrections win.

Check supplied cross-channel state as well as sent email and existing drafts. If the matter was already addressed in Teams, a meeting, or another channel, do not create another initial reply simply because the email has no sent answer. Return that disposition and the evidence to the parent. Missing Memo coverage is a retrieval gap, not proof that the owner has no position; ask only if the missing position is consequential. A local-only parent request takes precedence over the default Portal draft creation step: return the candidate without calling `draft_create` in that mode.

**Per-recipient sample** (if contact resolved):
```
list_entities(entity_type="email", filters={"contact_id": "<resolved_id>", "direction": "sent"}, limit=10)
email_bodies(ids=[<ids from the list>])
```

Listings are summaries, always pull `email_bodies` for the full text; voice lives in the prose. Note:
- How the owner opens to this specific person (`Hi Sarah,` vs `Hello Sarah,`)
- Typical closing
- Register (warm vs. measured)
- Any idiosyncratic phrases the owner uses with them

**General corpus sample** (for recipients with no prior history, or as a backup):
```
list_entities(entity_type="email", filters={"direction": "sent", "since": "<ISO date ~30 days ago>"}, limit=10)
email_bodies(ids=[...])
```

This gives you the baseline voice.

### Step 5: Draft

Now write the email. Apply:
- Opening that matches the register-by-recipient-type table in the voice guide
- The owner's register, from their voice file: openings, length, warmth signals
- Closing: the owner's sign-off exactly as their voice file gives it
- Full signature block only where the voice file says (usually external or formal recipients)

**Framing:** follow the framing rules in the owner's voice file.

### Step 6: Voice-Check Pass (MANDATORY)

Before creating the draft, scan your output against `unslop-email`'s self-audit (first three lines carry the subject and the ask; the reader can reply in one sentence; no word a forwarded reader could take as a threat; no sentence surviving on sound alone; nothing that would read the same sent to a different client) and then against the voice guide's check list:

1. **Forbidden phrases**: any phrase on the owner's forbidden list? Rephrase any hits.
2. **Opening**: matches recipient register?
3. **Closing**: the owner's sign-off?
4. **Framing**: follows the owner's framing rules?
5. **Length**: short paragraphs, no walls of text?
6. **Self-framing**: where the owner mentions their own work, it matches how they describe themselves?

If any check fails, revise and recheck. Loop until clean.

### Step 7: Create the Draft

```
draft_create(
    subject="<subject>",
    content="<voice-checked draft body>",
    recipient_to=["<recipient_email>"],
    related_contact_id="<resolved_id>",   # if available
    related_email_id="<source_email_id>"  # REQUIRED for replies, enables threaded Outlook delivery
)
```

Pass `agent_slug` (and `trigger_ref`) exactly as the brief gives them: a caller counts its own drafts by that slug.

(`recipient_cc` / `recipient_bcc` exist if the intent calls for them.)

### Step 8: Return a terse summary to the caller (the Return)

**Output format (at most 500 chars):**

```
Draft created: <draft_id> (<reply to <source email one-liner> | new message>)
To: <Name> (<email>)
Subject: <subject>
Voice notes: <2-3 bullets on per-recipient signals you applied, e.g. "Used 'Hi Sarah,' matching 8/10 prior opens; kept to 3 short paragraphs; framing rules applied">
```

Do NOT return the draft body in your summary, it lives in the Portal. The user reviews there. The reply-vs-new distinction matters to the parent: it drives how the draft gets delivered to Outlook.

## Example Run

**Input from parent:**
> Draft a follow-up to Sarah Chen summarizing what we agreed on in today's call (pricing model change, Q3 rollout) and proposing next Wednesday for the next check-in. Reply to her email from Tuesday.

**What you do:**
1. Read the owner's voice guide (setting `voice_guide`)
2. `search(query="Sarah Chen")` → contact id `c-123`
3. `list_entities(entity_type="email", filters={"contact_id": "c-123", "direction": "received"}, limit=5)` → Tuesday's email is `e-789`
4. `list_entities(entity_type="email", filters={"contact_id": "c-123", "direction": "sent"}, limit=10)` + `email_bodies(...)` → the owner opens "Hi Sarah," closes "Cheers, Pat", keeps paragraphs to 2-3 lines
5. Draft:
   ```
   Hi Sarah,

   Quick follow up on today's call. To summarize where we landed:

   - Pricing model: moving to the tiered approach we discussed, targeting a Q3 rollout.
   - Next step on my side: I'll circle back with the finance team this week and send a short proposal by end of next week.

   For our next check-in, does Wednesday the 29th at 10am Pacific work? Happy to flex if you have a standing conflict.

   Cheers,
   Pat
   ```
6. Voice-check: no forbidden phrases; opening matches; closing matches; framing rules N/A; short paragraphs; clear ask at end.
7. `draft_create(subject="Follow up: today's call", content="...", recipient_to=["sarah@example.com"], related_contact_id="c-123", related_email_id="e-789")` → draft_id `d-456`
8. Return:
   ```
   Draft created: d-456 (reply to Sarah's Tue "pricing model" email)
   To: Sarah Chen (sarah@example.com)
   Subject: Follow up: today's call
   Voice notes: Used "Hi Sarah," matching 9/10 prior opens; 3 short paragraphs with bulleted recap; clear scheduling ask at end; "Cheers, Pat" close (the made-up owner of this example is Pat).
   ```

## Done when

One voice-checked draft exists in the Portal (created with `draft_create`, or revised with `draft_update` on the draft you were told to revise) and the summary below has been returned; or the whole summary is a `BLOCKED:` question and no draft was created.
