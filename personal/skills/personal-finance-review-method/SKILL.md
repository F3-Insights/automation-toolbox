---
name: personal-finance-review-method
description: How the owner's monthly household finance review is prepared, on top of personal-workstream. A household review engine (a local repository that loads the banks' exports, ties them out and builds the review workbook) is the system of record; the owner's recurring-check procedure is the checklist; tax-advantaged and debt paydown deadlines are dated reminders; the output is a one-page review agenda, every figure traced to the engine's outputs. The rules file, the DONE checklist and the return fields. Loaded by personal-finance-review-orchestrator and personal-finance-review-analyst. Use when preparing the month's household review by hand. Not for gathering tax documents; use personal-tax-season-method.
---

# The monthly household finance review

This skill extends `personal-workstream`. Read it, and `orchestration-workstream`, from `~/.claude/skills/<name>/SKILL.md` if they are not loaded.

## The engine, reused

The household review engine is a local repository the owner keeps, named in the Context. The owner saves each institution's export by hand; the engine's own scripts load them, write the derived outputs (monthly by account, category grid, income, recurring payees, transfers, balances, and a business block when the household owns a business) and tie every output back to the raw exports. This work reads those outputs; it never rewrites the engine, re-derives what it already computes, or writes to the folder the exports come from.

- Read the engine's `STATUS.md` first. An output it lists as a known defect is never quoted; it becomes a `check` item in state `attention` naming the defect.
- The derived outputs must be newer than the latest raw pull. Older is `stale`: say so and stop at the agenda's "not current" banner.
- Whether the engine's tie-out checks passed on these outputs is cited from the check output the owner saved beside them, or reported "not verified this Run".

## The rules file: `PERSONAL-FINANCE-RULES.md`

The owner's. It holds: the recurring-check procedure (weekly, monthly, quarterly, annual items) or the path of the note that does; the standing targets (cash reserve, paydown order, savings order); the dated deadlines (retirement contributions, estimated tax payments, any other the owner tracks); who reviews with the owner; what the agenda may and may not show; and the engine's known caveats. An invented example target: `cash reserve: six months of core spend`.

## Method

1. List the month's checks from the procedure: each monthly item, plus the quarterly and annual items whose month this is.
2. Answer each from the engine's outputs, citing file and line: balances against targets, spend against the budget lines, income received against expected, recurring payees new or changed, unmatched transfers, and, when there is a business block, the business's draws against the household's receipts.
3. Date every deadline inside the next 90 days as a reminder with its source.
4. Write `runs/<date>/AGENDA.md`: one page, the headline (where the household stands against its targets), the five to eight lines that need a decision, each decision as a numbered question, and the reminders. Write `runs/<date>/FIGURES.md`: every figure in the agenda with the engine file and line it came from.

## DONE (the orchestrator checks each item and cites its evidence)

1. The engine's outputs are current for the month (newer than the latest raw pull), or the agenda opens with "not current" and names what is missing.
2. No figure comes from an output the engine's `STATUS.md` lists as defective.
3. Every monthly check of the procedure, and each quarterly or annual one due this month, has an answer with a cited source or is `not-found`.
4. Every figure in `AGENDA.md` is in `FIGURES.md` with its source, and the checker (`numbers-reviewer`) re-derived them: PASS.
5. Every deadline in the next 90 days is in `REMINDERS.md` with its source.
6. Every decision is a numbered question the owner can answer "1) ok 2) no".
7. Nothing was written outside the domain folder (or the Run folder on a dry run).

## The return here

`extra.checks` (one per procedure item: `{item, answer, source, state}`), `extra.figures` (`{figure, value, source}`), `extra.reminders` and the agenda's path in `files`.

## Later tools

- `personal-finance-pull`: a `prepare:` that copies the month's exports into the engine, runs its summarize and check scripts, and saves the check output in the Run folder.
- `personal-finance-check`: compute DONE items 1, 2, 4 and 5 from the Run folder and the engine.
