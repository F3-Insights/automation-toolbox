---
name: calendar-steward-method
description: "How the owner's calendar is stewarded, loaded by calendar-steward and the productivity-reviewer it dispatches: what a focus block, a conflict fix, a decline, a move and a prep task must satisfy before being proposed, the proposal file shared with the daily plan's focus-block proposals, the approval rules calendar-apply enforces, and the sections Propose the changes and Check the proposals. Use it by hand for \"is my calendar in shape for the next two weeks\"; for the weekday pass, start calendar-steward. Not for today's plan; use daily-plan-method. Not for where meeting time went; use calendar-time."
---

# Stewarding the owner's calendar

This skill extends `orchestration-workstream`: keep its conduct and return its block. Load it if it is not loaded. The owner's rules come first: `TASK-STACK-RULES.md` (calendar events: propose, then make only what they approved) and the steward's settings file beside it (working hours, focus target, scope, what is worth proposing). They override this file.

Commands: `productivity-calendar-steward-scan` (the facts, before the session), `productivity-calendar-apply publish` (the approval list on the owner's task, after it), `productivity-calendar-apply apply` (the approved changes of earlier lists, journaled, with an undo) and `productivity-calendar-steward-check DATE --run RUN` (whether the pass is done). They hold the proposal file's contract. The steward never writes the Portal or the calendar itself.

## Steps

For `calendar-steward`.

1. [judgment] Orient. `whoami`; read the rules and settings and `RUN/scan.json`. Note the findings by kind, the open items of earlier lists and the read gaps. When the scan's line says `STALE`, read the calendar yourself (`list_entities` calendar_event for the window) and say so.
   → pass `approve`: step 5
2. [judgment] Propose the changes (section Propose the changes) and save the draft as `RUN/returns/proposals-draft.json`.
3. [hand-off: productivity-reviewer] Check every proposal and the coverage (section Check the proposals), with the draft and the scan's path only. Save its return as `RUN/returns/checker.json`. Revise a FAIL once with the fix; a proposal still failing is dropped and its finding dismissed with the reason.
   → FAIL: step 2 (max 1)
4. [judgment] Write `RUN/proposals.json`: the proposals with `tool: "calendar-steward"`, `version: 1`, `date` (the scan's) and `dry_run`. At most twelve; an empty list is fine on a calm fortnight, but every finding still needs its dismissal.
5. [judgment] Report: the fortnight in two lines, the list as the owner will see it (numbered, one line each), the findings left alone in one line per group, the answers the finish step will apply, what could not be read. Say plainly that approved changes become tasks with an `.ics` file while the Portal has no calendar write. Never claim the list was published or a change made.
   → reported: done

After the session the Automation runs `productivity-calendar-apply apply`, `productivity-calendar-apply publish` and `productivity-calendar-steward-check`. A dry run writes `"dry_run": true` and the finish step writes nothing. With no one present everything runs the same; a question goes in `proposals.json`, never live.

## The standard

A short list a chief of staff would put in front of the owner, each item one concrete change with its reason, every time checked against the calendar, every finding in the scan either acted on or knowingly left alone. They answer it in a minute, "1) ok 2) no", and nothing they did not approve changes.

## What the scan gives you

`RUN/scan.json`: fourteen days, cleaned (clones, cancelled and declined rows dropped), each day's events (`meeting`, `hold`, `focus`), `free` slots inside working hours, `conflicts`, `back_to_back` runs and `longest_free`; meetings read in full carry `organizer`, `owner_organizer`, `others` (attendees besides the owner), `agenda` and `prep_notes`. Then `findings` (each with an `id`), `daily_plan` (the daily plan's focus-block proposals not yet on the calendar), `open_items` (items of earlier lists still unanswered) and `unreadable`.

## The kinds of change

Every proposal names its finding's reason in `why`, a sentence the owner would accept.

- **focus-block**: a new busy block with no attendees, in a slot that is free in the scan for its whole length (`busy_overlap` is the test: no meeting or hold overlaps it), at least the focus target long unless the day has nothing longer. Title it `Focus: <what>`; name the task it is for in `for` when there is one. A day the scan calls focus-short gets one where a slot exists; a day with none gets a fix (move a hold, decline an optional meeting) or a dismissal.
- **move**: only the owner's own entry with no other attendees (a hold, a focus block, a solo reminder). `to` is a free slot. A meeting with other people on it is never moved: moving it sends them an update. Propose a decline whose draft offers a new time instead.
- **decline**: an invitation (the owner is not the organizer) that is optional, a large audience, has no purpose for them, or loses a clash to the meeting where a decision is made. `draft` is the reply in the owner's plain voice, two or three sentences, offering a delegate or a new time where that is right. It is a draft: nothing is ever sent by the steward.
- **prep**: an external meeting with no prep note. `prepare` says in one line what to prepare (the open question, the number, the document); `due` is the working day before, or the same morning for a meeting early in the window. Internal meetings get no prep task.

## Conflicts, focus overlaps, back-to-back days, unanswered invitations

- A conflict between two meetings: decline the one that gives way (the optional or large-audience one gives way to the decision meeting or the client), or dismiss it when one of the two is a placeholder the owner keeps on purpose (say which). A meeting against a hold: move the hold when it is their own, otherwise dismiss with the reason.
- A meeting sitting on a focus block: decline it when the block guards owed work, or propose a new focus block elsewhere that day.
- A back-to-back run: a short break is worth a proposal only when the run is three hours or more; otherwise dismiss.
- An unanswered invitation: decline it if it should be declined; otherwise dismiss ("accept by hand"): accepting is their click, not a change the steward makes.

## What not to propose

- Nothing on an item already open on an earlier list (`open_items`); the owner answers that list. Nothing in the past. Never more than twelve items; fewer is better.
- A no-agenda recurring internal meeting is one dismissal for the whole series, not a decline, unless the settings file or the owner's instructions say otherwise.
- The daily plan's focus blocks are proposed again here with `source: daily-plan` and `from` set to the scan's `from` (so the owner approves each once), or dismissed with the reason.

## The proposal file

`RUN/proposals.json`, whose contract the calendar-steward commands hold: `tool`, `version`, `date`, `dry_run`, `summary`, `proposals` (`id`, `kind`, `date`, `start`, `end`, `title`, `why`, and `event`, `to`, `for`, `draft`, `prepare`, `due`, `source`, `from` by kind), `findings` (each `{ids: [...], proposal: <id>}` or `{ids: [...], dismissed: <reason>}`, so every finding id in the scan is covered), `questions`, `notes`. A focus block is the daily plan's `focus-block` proposal with `date` added: the two share one shape. Times are local `HH:MM`; every `event` is a `portal://calendar_event/` ref from the scan, never made up.

## What happens after

`productivity-calendar-apply publish` numbers the list and files it on the approval task; it refuses a proposal whose slot is not free, whose event is not in the scan, or that moves a meeting with others. `productivity-calendar-apply apply` acts on `ok` answers only, reads the calendar again first (expired, no longer free and gone are refused), never deletes and never sends. Where no calendar backend exists it makes each approved change a task with its times and writes an `.ics` file and a paste list beside it; say so in the report rather than claiming the calendar changed.

## Propose the changes

Done by `calendar-steward` itself, from the scan.

1. Read the settings and the findings. Group what is alike: every instance of a recurring meeting is one decision.
2. For a finding that might deserve a change, read what the scan does not settle: the meeting in full (`get`), its context (`meeting_prep`) for a decline or a prep line, the task a focus block is for. A decline needs a reason the owner would give themselves.
3. Draft the proposals by the kinds above, the most valuable first, at most twelve. Check each time against the scan's `free` and events before writing it.
4. Cover every finding id: a proposal, or a one-line dismissal. A question only the owner can answer (which of two clashing client meetings they keep) goes in `questions` with `of: owner`.

## Check the proposals

For `productivity-reviewer`, given the draft proposals and the scan's path, nothing else. Nothing reaches the list that would surprise the owner if they said yes without reading it twice. For each proposal:

- **The facts.** Every `event` is in the scan and still on the calendar (`get` it). Every new time (a focus block's `start`-`end`, a move's `to`) overlaps no meeting or hold that day in the scan, and lies in the future.
- **focus-block**: in working hours, long enough to be worth it; `for` is a real task when given.
- **move**: the event has no attendee besides the owner. One that does is a FAIL.
- **decline**: the owner is not the organizer; the reason holds up (optional, large audience, no purpose for them, or it loses a clash to the decision meeting); the draft is polite, short, commits them to nothing new and is written as theirs.
- **prep**: the meeting is external, has no prep note, and `due` leaves time to prepare.
- **coverage**: every finding id in the scan appears once in `findings`, with a proposal or a specific dismissal.

Return the `orchestration-workstream` block: one `items` row per proposal (`test: review`, `item` the proposal id, `state` PASS or FAIL, `note` the fix for a FAIL), and `findings` for any coverage gap.
