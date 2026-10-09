---
name: calendar-steward-method
description: "How the owner's calendar is stewarded: what a focus block, a conflict fix, a decline, a move and a prep task must satisfy before being proposed, the proposal file shared with the daily plan's focus-block proposals, and the approval rules calendar-apply enforces. Loaded by the calendar-steward agents after orchestration-workstream. Use it by hand for \"is my calendar in shape for the next two weeks\"; for the weekday pass, start calendar-steward-orchestrator. Not for today's plan; use daily-plan-method."
---

# Stewarding the owner's calendar

Load `orchestration-workstream` from `~/.claude/skills/orchestration-workstream/SKILL.md` if it is not loaded; keep its conduct and return its block. This skill is only what the calendar adds. The owner's rules come first: `TASK-STACK-RULES.md` (calendar events: propose, then make only what they approved) and the steward's settings file beside it (working hours, focus target, scope, what is worth proposing). They override this file.

Tools: `calendar-steward-scan` (the facts, computed before the session), `python3 ~/.claude/skills/calendar-steward-method/scripts/calendar_apply.py publish` (the approval list on their task, after the session), `python3 ~/.claude/skills/calendar-steward-method/scripts/calendar_apply.py apply` (the approved changes, journaled, with an undo) and `calendar-steward-check` (whether the pass is done). Those commands hold the proposal file's contract.

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

`RUN/proposals.json`, whose contract the calendar-steward commands hold: `tool`, `version`, `date`, `dry_run`, `summary`, `proposals` (`id`, `kind`, `date`, `start`, `end`, `title`, `why`, and `event`, `to`, `for`, `draft`, `prepare`, `due`, `source`, `from` by kind), `findings` (each `{ids: [...], proposal: <id>}` or `{ids: [...], dismissed: <reason>}`, so every finding id in the scan is covered), `questions`, `notes`. A focus block is the daily plan's `focus-block` proposal with `date` added: the two share one shape. A worker returns the same object in `extra.proposals` of its return block. Times are local `HH:MM`; every `event` is a `portal://calendar_event/` ref from the scan, never made up.

## What happens after

`python3 ~/.claude/skills/calendar-steward-method/scripts/calendar_apply.py publish` numbers the list and files it on the approval task; it refuses a proposal whose slot is not free, whose event is not in the scan, or that moves a meeting with others. `python3 ~/.claude/skills/calendar-steward-method/scripts/calendar_apply.py apply` acts on `ok` answers only, reads the calendar again first (expired, no longer free and gone are refused), never deletes and never sends. Where no calendar backend exists it makes each approved change a task with its times and writes an `.ics` file and a paste list beside it; say so in the report rather than claiming the calendar changed.
