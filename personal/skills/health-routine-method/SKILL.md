---
name: health-routine-method
description: "How the owner's weekly health check-in is made, on top of personal-workstream: the week's figures from the data exports the owner's rules name, set against the owner's own goals with a four-week trend and confirmed by the reviewer, plus appointment and coverage dates as local reminders. Medical records are never read; a draft that ships without commands. The Steps, Read the week, the reviewer's Check the values, and DONE. Loaded by personal-health-check-in and personal-reviewer. Use when running the check-in by hand. Not for household obligations; use household-method."
maturity: draft
---

# The weekly health check-in

This skill is a draft: it ships without commands and is not yet runnable as is, because the owner supplies the data exports, or grants a read-only command, privately once they are audited.

This skill extends `personal-workstream`, which extends `orchestration-workstream`. Load both with the Skill tool if they are not loaded.

This is a mirror, not a coach. It reports the week against the owner's own goals in the owner's own terms, and the dates not to miss. It gives no medical advice and draws no medical conclusion.

## Steps

For `personal-health-check-in`. `RUN` is `runs/<week start>/` in the health folder, or the Run folder on a dry run.

1. [judgment] Orient. Read the rules file, `STATUS.md`, `QUESTIONS.md`, `REMINDERS.md` and the last four check-ins (for the trend).
2. [judgment] Set up `RUN` with `LOG.md`; log a line before each dispatch and record each return.
3. [judgment] Read the week (section Read the week): a copy of each source saved under `RUN/source/`, one value per metric, the reminders, and `RUN/CHECKIN.md` as a draft.
   → no source could be read: step 5
4. [hand-off: personal-reviewer] Confirm every value (section Check the values), given each value in the draft as a claim and the saved copies under `RUN/source/` as the only sources. Save its return as `RUN/review-values.md`.
5. [judgment] Record. A value that fails becomes `not-found` with the reason. Write `CHECKIN.md` in its final form, the reminders in `REMINDERS.md`, the questions in `QUESTIONS.md`, and `STATUS.md`.
6. [judgment] Close. Walk the DONE checklist below, citing the evidence for each item, and report: one line per metric with value, target and trend, the reminders of the next 30 days, the reviewer's verdict, and the questions as one numbered list the owner can answer "1) ok 2) no".
   → reported: done

## The sources

- The data exports the rules file names (files the owner or a private tool saved for the week), read only. Where the rules list a read-only command instead, it is one the owner granted to the session outside this repository; this repository ships and grants none. An export missing for the week, or a command that fails, is a `source` item in state `missing` with the reason; never try another route or other credentials.
- The owner's health goals, at the path the Context names, read only.
- `REMINDERS.md` in the domain folder for appointments and coverage dates.

Medical records, lab results, prescriptions and insurance documents are fenced. A date the owner needs from one is a question to the owner.

## The rules file: `HEALTH-ROUTINE-RULES.md`

The owner's. It holds: the metrics tracked and their weekly targets, which export or command answers each (a metric with no source says so), the appointment and coverage dates to be reminded of and how far ahead, and the week's start day. An invented example metric line: `metric A, target 100 weekly average, source export-1`.

## Read the week

Done by `personal-health-check-in` itself.

1. Read the week from each source the rules name. Save a copy of each export, or each command's output, that a value rests on under `RUN/source/`, so the reviewer reads exactly what you read.
2. For each metric: the week's value, the target, the four-week trend, the source. A metric with no data is `not-found`, never zero.
3. List reminders due in the next 30 days from `REMINDERS.md` and any new date the owner gave.
4. Draft `RUN/CHECKIN.md`: one line per metric, the reminders, and at most two questions (a target to restate, a source to retire).

## Check the values

For `personal-reviewer`, with `review-facts` as the checklist (load it). The claims are the draft's values, one per metric (`metric, week, value`); the only sources are the copies under `RUN/source/`. Lines this job adds:

- Recompute each value from the copy (a weekly average, a total) rather than finding a matching number; a value the copy does not produce is CONTRADICTED.
- A value of zero where the copy has no data for the week is CONTRADICTED: it should be `not-found`.
- Nothing in the draft gives medical advice or draws a medical conclusion; a sentence that does is a fix.
- Skip the omissions check: the copies hold more than the metrics in scope.

Return the `review-facts` return block.

## DONE (the main agent checks each item and cites its evidence)

1. Every metric in the rules has a value with its source, or `not-found` with the reason.
2. Every value in `CHECKIN.md` was confirmed against its saved source by the reviewer (section Check the values): PASS, in `RUN/review-values.md`.
3. Every reminder due in the next 30 days is in `CHECKIN.md`.
4. No fenced source was read and nothing gives medical advice.

## The record of the Run

`items` with tests `source` and `metric` (metric states `on-target`, `below`, `above`, `not-found`), the metrics (`{metric, value, target, trend, source}`) and the reminders, as `LOG.md` records them.

## Later tools

- `health-pull`: a `prepare:` that copies the week's exports the rules name into the Run folder.
- `health-check`: compute DONE items 1 and 3 from the Run folder and the rules.
