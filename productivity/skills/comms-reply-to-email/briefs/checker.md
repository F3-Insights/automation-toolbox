# Brief: check one reply draft before it reaches the owner's Drafts folder

## The question

Is this draft safe to put in the owner's Drafts folder: every fact true to the sources, nothing promised that they did not approve, in their voice, and addressed to the pinned person on the pinned thread? You check; you do not rewrite. You have not seen why the draft says what it says, and that is the point.

## The inputs

- The draft id.
- The pinned contact id and the pinned email ref.
- The paths of `brief.md` and, when the owner was asked, `answers.md`.

## What to do

1. Run `python3 ~/.claude/skills/comms-reply-to-email/scripts/email_draft_show.py DRAFT_ID`. It prints the subject, the body, the recipients, the contact and email the draft is tied to, and `content_hash`. Keep the hash exactly as printed; your record is valid only for that content.
2. Read `brief.md`, `answers.md` and the owner's voice guide (setting `voice_guide`).
3. Check, and number every problem you find:
   - **Dates and times.** Each one in the draft appears in the brief or the answers, with the same day, date and time zone. A weekday must match its date.
   - **Numbers.** Each amount, count, rate or percentage appears in the brief or the answers, exactly.
   - **Commitments.** Nothing is offered, agreed, promised or declined that the brief lists under Already decided or that `answers.md` approves. Anything under Open for the owner with no answer must not be decided in the draft.
   - **Superseded draft.** Nothing the brief's Superseded draft section marks as overtaken appears in the draft, and the draft never refers to that discarded draft as sent.
   - **Coverage.** Each point under What the email asks is answered or acknowledged.
   - **Tone.** The voice guide's forbidden phrases, opening, closing and framing rules. No em-dashes.
   - **Recipient and thread.** `contact_id` is the pinned contact, `email_ref` is the pinned email, `recipient_to` holds only that contact's address, and `recipient_cc` and `recipient_bcc` are empty.
4. Any problem means FAIL. Each fix says what is wrong, where (quote at most 15 words of the draft) and what the source says instead, with its ref.

## The return format

Return exactly one fenced JSON block and nothing else. The orchestrator saves it verbatim as the check record, and `email-deliver` refuses to deliver unless it reads `PASS` for this draft id and this content hash. The schema is `checker.schema.json` beside this file.

```json
{"verdict": "PASS",
 "draft_id": "<draft id>",
 "content_hash": "<content_hash exactly as email-draft-show printed it>",
 "contact_id": "<pinned contact id>",
 "email_ref": "<pinned email ref>",
 "checked": {"dates": "ok", "numbers": "ok", "commitments": "ok", "coverage": "ok",
             "tone": "ok", "recipient_and_thread": "ok"},
 "fixes": []}
```

On FAIL, `verdict` is `"FAIL"`, each failing entry in `checked` says `"fail"`, and `fixes` is the numbered list: `[{"n": 1, "what": "...", "where": "...", "source": "... [ref]"}]`.
