---
name: health-routine-method
description: How the owner's weekly health check-in is made, on top of personal-workstream. The week's figures from the data exports the owner's rules file names, set against the owner's own health goals and metrics, plus a dated list of appointments and coverage dates kept as local reminders. Medical records are never read. A draft that ships without commands. The rules file, the DONE checklist and the return fields. Loaded by health-routine-orchestrator and health-routine-analyst. Use when running the check-in by hand. Not for household obligations; use household-method.
maturity: draft
---

# The weekly health check-in

This skill is a draft: it ships without commands and is not yet runnable as is, because the owner supplies the data exports, or grants a read-only command, privately once they are audited.

This skill extends `personal-workstream`. Read it, and `orchestration-workstream`, from `~/.claude/skills/<name>/SKILL.md` if they are not loaded.

This is a mirror, not a coach. It reports the week against the owner's own goals in the owner's own terms, and the dates not to miss. It gives no medical advice and draws no medical conclusion.

## The sources

- The data exports the rules file names (files the owner or a private tool saved for the week), read only. Where the rules list a read-only command instead, it is one the owner granted outside this repository; this repository ships and grants none. An export missing for the week, or a command that fails, is a `source` item in state `missing` with the reason; never try another route or other credentials.
- The owner's health goals, at the path the Context names, read only.
- `REMINDERS.md` in the domain folder for appointments and coverage dates.

Medical records, lab results, prescriptions and insurance documents are fenced. A date the owner needs from one is a question to the owner.

## The rules file: `HEALTH-ROUTINE-RULES.md`

The owner's. It holds: the metrics tracked and their weekly targets, which export or command answers each (a metric with no source says so), the appointment and coverage dates to be reminded of and how far ahead, and the week's start day. An invented example metric line: `metric A, target 100 weekly average, source export-1`.

## Method

1. Read the week from each source the rules name.
2. For each metric: the week's value, the target, the four-week trend, the source. A metric with no data is `not-found`, never zero.
3. List reminders due in the next 30 days from `REMINDERS.md` and any new date the owner gave.
4. Write `runs/<week start>/CHECKIN.md`: one line per metric, the reminders, and at most two questions (a target to restate, a source to retire).

## DONE (the orchestrator checks each item and cites its evidence)

1. Every metric in the rules has a value with its source, or `not-found` with the reason.
2. Every value in `CHECKIN.md` was confirmed against the source by the checker (`fact-check`): PASS.
3. Every reminder due in the next 30 days is in `CHECKIN.md`.
4. No fenced source was read and nothing gives medical advice.

## The return here

`items` with tests `source` and `metric` (metric states `on-target`, `below`, `above`, `not-found`), `extra.metrics` (`{metric, value, target, trend, source}`), `extra.reminders`.

## Later tools

- `health-pull`: a `prepare:` that copies the week's exports the rules name into the Run folder.
- `health-check`: compute DONE items 1 and 3 from the Run folder and the rules.
