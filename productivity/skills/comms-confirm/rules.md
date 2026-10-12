# Confirmation requests: the contract

A confirmation request is one question to one person, kept in the caller's store until it is closed. The examples describe a made-up company, Acme Components.

## The store

`CONFIRMATIONS.md`, a plain markdown file in the work's own folder, never in this skill's folder. For an engagement folder it sits in the period folder beside STATUS.md. The script creates it on the first request. Each request is a `## CR-xxxxxxxxxx` section of field lines:

```markdown
## CR-3fa91b2c7d

- Question: Was the carrier invoice dated 28 September for September freight?
- State: open
- Asked of: AP lead
- Person: Jordan Lee <jordan@example.com>
- Contact: 11111111-2222-3333-4444-555555555555
- Portal user:
- Channels: task
- Delivery: relay
- Asked at: 2026-10-02T16:40-07:00
- Due: 2026-10-05
- Fallback: proceed: accrue it in September
- Context: [invoice](sources/carrier-inv.pdf)
- Record: waiting-on W2 in ../.. period 2026-09
- Task: portal://task/66666666-7777-8888-9999-000000000000
- Email subject:
- Email thread:
- Draft:
- Relayed: 2026-10-02T16:42-07:00
- Reminded:
- Answer:
- Answered by:
- Evidence:
- Answered at:
- Seen:
- Log: 2026-10-02 16:40 asked by close; 2026-10-02 16:41 task created by close; 2026-10-02 16:42 relayed to the owner to ask Jordan Lee (teams) by close
```

- **Id**: `CR-` and ten hex characters, a hash of the scope (default the store's path), the question and the role. The same question to the same role in the same store is the same request, so asking twice returns the first.
- **State**: `open` (out, no answer), `answered` (an answer was found, the work has not yet used it), `closed` (used, assumed under its fallback, or withdrawn).
- **Asked of** is the role; **Person**, **Contact** and **Portal user** are who it resolved to. Portal user is recorded only; no task is ever assigned to the person.
- **Delivery** is `relay` or `direct` as the setting was when the request was made, or `owner` for a question to the owner, which needs no relay. A request from before the setting existed has none and is treated as direct.
- **Due** defaults to the end of the next full business day after asking: asked on a Friday, due the Monday; asked on a Monday, due the Tuesday. Weekends are skipped; holidays are not.
- **Record** links the request to where the work keeps its state: `waiting-on Wn in <engagement folder> period yyyy-mm` (paths relative to the store's folder), or `file <path>`, a file where each answer and close is appended as one line. Empty means the store is the record.
- **Relayed** is when the owner was asked to put the question; **Reminded** the last day it was in the owner's morning reminder.
- **Answer** and **Answered by** may be typed by a person. The next check records a typed answer as found.
- **Seen** lists evidence already judged not to be an answer (by `reopen`), so check does not find it again.
- **Log** gains one entry per change. Nothing is ever deleted.

## The Waiting on row

With `--engagement FOLDER`, the record is a row in the period's STATUS.md, at `FOLDER/yyyy/yyyy-mm/STATUS.md`. The period is `--period` when given, else the root `FOLDER/STATUS.md`'s `Current period: yyyy-mm` line. The period file holds a `## Phases` table (`Phase | State | Files | Note`; `--phase` must name one of its phases, matched without case) and the `## Waiting on` table:

```markdown
| Id | Phase | Question | Asked of | How | Asked at | State | Answer | Answered at |
|---|---|---|---|---|---|---|---|---|
| W2 | Standard entries | Was the carrier invoice dated 28 September for September freight? (CR-3fa91b2c7d) | AP lead | task | 2026-10-02 | open |  |  |
```

- **Id** is the next `Wn`. **How** is `task`, `email draft` or `question to owner`, from the first channel asked. **Asked at** and **Answered at** are dates.
- **State** is open, answered or closed. An answer sets answered and fills Answer. A close with no answer writes `(withdrawn)`. A reopen puts an answered row back to open and moves the answer seen into the question as `(earlier reply: ...)`.
- A `|` inside a cell is written `\|`. Only the row named and the file's `Last updated: yyyy-mm-dd HH:MM by WHO` line change; any other text in the file stays as a person wrote it.
- `scripts/waiting.py` keeps the row. The root STATUS.md's own Waiting on summary is the work's orchestrator's to keep; this skill does not write it.

## Who is asked

The role comes from the calling skill; the person from the caller's context, never from this skill. In an engagement folder, BACKGROUND.md's `## Roles` may list a role as a bullet, `- AP lead: Jordan Lee <jordan@example.com>`, which `who` reads. Prose roles, or a role found in a Context or a brief, are resolved by judgment. The Portal contact is pinned with `find_contact.py` (comms-reply-to-email), which never picks between two. The owner needs no lookup.

## Delivery: how the question reaches the person

A setting, decided by the owner and switched only by them:

- **relay** (the default): the skill does not contact the person. It asks the owner, in one message per session, to put the question to them (`relay`), and records the request as waiting on the person: the Portal task waits on their contact. No email is drafted to them and nothing goes on their task list. `new` refuses the email channel under relay.
- **direct** (kept, off): the caller may also draft an email to the person through `comms-draft-email`, for the owner to send. The Portal task still sits on the owner's list.

The setting is `--delivery` on `new`, else the environment's `CONFIRM_DELIVERY`, else relay.

## Channels

- **owner**: the question asked of the owner in the session, when present. With no one present it becomes a task on the owner's own list.
- **task**: a Portal task, always on the owner's own list, never assigned to the person (Portal user or not). With the person's contact it is WAITING, waiting on that contact; a question to the owner stays to do. Its description holds the question, the context, the due date, the fallback, how to answer (under relay: put the question to the person, then comment their answer), and the marker line `confirmation-request:<id>`, last. The marker is looked up before any create, so a re-run finds the task rather than making a second.
- **email** (delivery direct only): a draft to the person, made by `comms-draft-email` (which runs `outbound-check` and the voice-matched drafter, and delivers into the owner's Drafts folder only when the owner is present). Nothing sends it; the owner does. `record` notes the draft id and subject so a reply can be matched. Write the subject plainly; the reply keeps it.

## Telling the owner

Two commands send the owner one message each through the comms-reply-to-email skill's `notify_owner.py` (the owner's chat, email as its fallback), and never one message per question:

- **relay**, at the end of a session that asked: every open relay request in the stores given that is not yet relayed, one line each: "Ask Jordan Lee (AP lead): <question> Wanted by Mon 5 Oct; comment the answer on its Portal task." Each line sent is marked Relayed, so a second run sends nothing for it.
- **remind**, each business morning from a scheduler: every open request past due or due today, one line each with who, when it was asked, when it was due, the question and where to answer. The title says how many ("2 confirmations past due"). Each one listed is marked Reminded with the day, so a second run the same day sends nothing new, and the next morning lists it again while it is still open. With no request due it sends nothing. A request whose fallback reads `escalated to <id>` is left out: its owner request is listed instead.

Both print one line first: `NOTHING`, `SENT: ...`, `NOT SENT: <reason>` (notifications are off or rehearsing; nothing is marked, so the next run tries again) or `DRY RUN: ...` with `--dry-run`, then the message. A notifier that fails exits 2 and marks nothing. Where to answer is the Portal task when there is one, else the store's Answer line.

## How answers are found

`check` reads, for each open request, in this order, and stops at the first answer:

1. The store's Answer line, typed by a person.
2. The linked Waiting on row's Answer cell, typed by a person. A row closed by hand closes the request.
3. The Portal task: a comment newer than the request by a person (an agent's comment carries a "posted by ..., an agent" line and does not count); the task set DONE; the task CANCELLED, which withdraws the request.
4. Email: mail received from the person's contact after the request, on the recorded thread or with the recorded subject (less `Re:` and `Fwd:`).

A found answer sets the request answered with the evidence, and the Waiting on row answered. Whether it answers the question is judged in the next session; `reopen` puts back one that does not. The first output line is `NOTHING` or `WORK: answered <ids>; past due <ids>`. A request already answered and not yet closed is still WORK. A failure to reach the Portal exits 2 and prints neither, after recording what the local files held.

## Fallbacks

- **proceed: <assumption>**: past due, the work goes ahead on the assumption, closes the request with `--assumed` (the answer reads "(assumed, no answer by <due>) <assumption>") and logs it.
- **escalate** (the default): past due, the owner's morning reminder lists it each business day until it is answered or closed. Check lists it but does not report it as WORK: the reminder is the escalation. An owner request can still be made by hand with `new ... --of owner --escalates <first id>`; the first then stays open, so a late answer still counts, and its fallback becomes `escalated to <new id>`.
- **wait**: past due, listed by every check as still waiting but never WORK on its own; only an answer wakes the work. The morning reminder lists it too.

Past due is WORK only for proceed, once: the request is closed as assumed.

## Closing

`close` sets the request closed with the answer, who answered and the evidence, closes the Waiting on row (or appends to the record file), and finishes the Portal task: one comment with the answer and the evidence, then DONE, or CANCELLED when withdrawn. A task already done or cancelled is left alone. `--leave-task` skips the Portal.

## External commands

`confirm.py` and `confirm_portal.py` ship inside this skill's folder, and `confirm.py` runs `confirm_portal.py` beside it. `find_contact.py` and `notify_owner.py` belong to the comms-reply-to-email skill and run as `python3 ~/.claude/skills/comms-reply-to-email/scripts/<name>.py`. Nothing is on PATH. `CONFIRM_PORTAL_CMD` and `CONFIRM_NOTIFY_CMD` replace the Portal script and the notifier. Standard-library Python 3.8 or later for the scripts.

- `python3 scripts/confirm.py`
