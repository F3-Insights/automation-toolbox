---
name: household-method
description: How a household chief of staff works for one member of the owner's household, on top of personal-workstream. The first Run is an interview the owner carries to that person (the one weekly pain point, where obligations live, what is off limits, how reminders should arrive); until it is answered nothing else runs. After it, a weekly pass on that one pain point, a ledger of household obligations with dates and sources, durable memory of what was confirmed, and a short weekly page the owner hands over. The rules file, the DONE checklist and the return fields. Loaded by household-orchestrator and household-steward. Use when setting up or running the household pass by hand. Not for money or tax; use personal-finance-review-method or personal-tax-season-method.
---

# The household chief of staff

This skill extends `personal-workstream`. Read it, and `orchestration-workstream`, from `~/.claude/skills/<name>/SKILL.md` if they are not loaded.

This work helps one person with one named burden at a time. It does not watch anyone, track anyone's location or messages, or build a dashboard of the household.

Below, "the person" is the household member the rules file names as the one this serves.

## The interview comes first

`HOUSEHOLD-RULES.md` has an `## Interview` section. While it is empty, a Run does only this: write `runs/<date>/INTERVIEW.md` with the questions below, plain enough for the owner to read aloud, and return them as the owner's numbered list. Nothing else is read.

1. Which one chore, paper task or reminder eats the most of your week?
2. Where does it live today (a paper pile, a calendar, a list, someone's memory)?
3. What would "handled" look like on a good week?
4. How should a reminder reach you, and how far ahead?
5. What must this never read or keep (folders, people, subjects)?
6. Who besides the two of you may see what it writes?

The owner records the answers in the `## Interview` section. A later Run that finds them reads them as the rules.

## The rules file: `HOUSEHOLD-RULES.md`

The owner's, written with the person. It holds the person it serves (by role), the interview answers, the one pain point in scope, the sources that may be read for it, the fenced folders (identity papers and any minor's records always fenced), and the weekly page's day and shape.

## The ledger: `OBLIGATIONS.md`

One row per household obligation in scope: `what, for (role), due, recurs, source, state`. Renewals, appointments, deadlines, whatever the pain point covers. A row comes from a source the rules allow or from the owner; never from a guess.

An invented example row: `renewal A, for member A, 2030-05-31, yearly, notice-2030.pdf, open`.

## Method (after the interview)

1. Read the rules, `OBLIGATIONS.md`, `MEMORY.md` and the last week's page.
2. Look in the allowed sources for new obligations and for evidence that open ones were done.
3. Propose: new rows, rows done (with evidence), reminders for the next 14 days, renewals in the next 60 days, and facts for `MEMORY.md` the owner or the person confirmed.
4. Write `runs/<date>/WEEK.md`: what is coming, what is done, what needs a decision, under half a page, in the person's terms.

## DONE (the orchestrator checks each item and cites its evidence)

1. The interview is answered, or this Run wrote `INTERVIEW.md` and stopped there.
2. Every new or changed ledger row cites its source, and the checker (`fact-check`) confirmed the dates against those sources: PASS.
3. Every obligation due in the next 14 days is on `WEEK.md` and in `REMINDERS.md`.
4. No fenced folder was read: the Run log lists only allowed sources.
5. `WEEK.md` stays on the one pain point in scope.

## The return here

`items` with test `obligation` (states `new`, `open`, `done`, `dropped`), `extra.rows` in the ledger shape, `extra.reminders`, and `proposals` for `MEMORY.md`.

## Later tools

- `household-check`: compute DONE items 1, 3 and 4 from the folder and the Run log.
