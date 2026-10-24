---
name: personal-finance-review-method
description: "How the owner's monthly household finance review is prepared, on top of personal-workstream: the household review engine's derived outputs as the system of record, the owner's recurring-check procedure as the checklist, deadlines as dated reminders, and a one-page agenda with every figure traced and re-derived. The Steps, Answer the checks, the reviewer's Check the figures, and DONE. Loaded by personal-finance-review-prep and personal-reviewer. Use when preparing the month's household review by hand. Not for gathering tax documents; use personal-tax-season-method."
---

# The monthly household finance review

This skill extends `personal-workstream`, which extends `orchestration-workstream`. Load both with the Skill tool if they are not loaded.

## Steps

For `personal-finance-review-prep`. `RUN` is `runs/<date>/` in the finance folder, or the Run folder on a dry run.

1. [judgment] Orient. Read the rules file, `STATUS.md`, `QUESTIONS.md` (answered questions are input), the engine's `STATUS.md` and the last Run's agenda. Note whether the engine's outputs are current (section The engine, reused).
   → the engine's outputs cannot be read at all: stop
2. [judgment] Set up `RUN` with `LOG.md`; log a line before each dispatch and record each return.
3. [judgment] Answer the checks (section Answer the checks): the checks, the figures, the reminders, and `RUN/AGENDA.md` and `RUN/FIGURES.md` as drafts.
4. [hand-off: personal-reviewer] Re-derive every figure (section Check the figures), given `AGENDA.md`, `FIGURES.md`, the engine's derived folder and its `STATUS.md`, and the fenced list; never your reasoning. Save its return as `RUN/review-figures.md`.
   → FAIL: step 3 (max 1)
5. [judgment] Record. A figure that fails a second time leaves the agenda and becomes a question. Write the agenda and `FIGURES.md` in their final form, the new reminders in `REMINDERS.md`, the questions in `QUESTIONS.md`, and `STATUS.md`.
6. [judgment] Close. Walk the DONE checklist below, citing the evidence for each item, and report: the headline against the targets, the checks by state, the reviewer's verdict, the reminders of the next 90 days, and the questions as one numbered list the owner can answer "1) ok 2) no".
   → reported: done

## The engine, reused

The household review engine is a local repository the owner keeps, named in the Context. The owner saves each institution's export by hand; the engine's own scripts load them, write the derived outputs (monthly by account, category grid, income, recurring payees, transfers, balances, and a business block when the household owns a business) and tie every output back to the raw exports. This work reads those outputs; it never rewrites the engine, re-derives what it already computes, or writes to the folder the exports come from.

- Read the engine's `STATUS.md` first. An output it lists as a known defect is never quoted; it becomes a `check` item in state `attention` naming the defect.
- The derived outputs must be newer than the latest raw pull. Older is `stale`: say so, and the agenda opens with a "not current" banner naming what is missing.
- Whether the engine's tie-out checks passed on these outputs is cited from the check output the owner saved beside them, or reported "not verified this Run".

## The rules file: `PERSONAL-FINANCE-RULES.md`

The owner's. It holds: the recurring-check procedure (weekly, monthly, quarterly, annual items) or the path of the note that does; the standing targets (cash reserve, paydown order, savings order); the dated deadlines (retirement contributions, estimated tax payments, any other the owner tracks); who reviews with the owner; what the agenda may and may not show; and the engine's known caveats. An invented example target: `cash reserve: six months of core spend`.

## Answer the checks

Done by `personal-finance-review-prep` itself, from the rules file, the engine's derived folder and its `STATUS.md`, the month and the last agenda.

1. List the month's checks from the procedure: each monthly item, plus the quarterly and annual items whose month this is.
2. Answer each from the engine's outputs, citing file and line: balances against targets, spend against the budget lines, income received against expected, recurring payees new or changed, unmatched transfers, and, when there is a business block, the business's draws against the household's receipts.
3. Date every deadline inside the next 90 days as a reminder with its source.
4. Write `RUN/AGENDA.md`: one page, the headline (where the household stands against its targets), the five to eight lines that need a decision, each decision as a numbered question, and the reminders. Write `RUN/FIGURES.md`: every figure in the agenda with the engine file and line it came from.

On a revision after a FAIL, fix exactly the reviewer's numbered findings and change nothing else.

## Check the figures

For `personal-reviewer`, with `review-numbers` as the checklist (load it), given `AGENDA.md`, `FIGURES.md`, the engine's derived folder and its `STATUS.md`, and nothing else. There is no prior package to diff against unless the brief names last month's agenda. Lines this job adds:

- Re-derive every figure in `AGENDA.md` from the engine's outputs, not from `FIGURES.md`; `FIGURES.md` only says where to look.
- A figure drawn from an output the engine's `STATUS.md` lists as defective is WRONG, whatever its value.
- Every figure in `AGENDA.md` has a row in `FIGURES.md`; one without is UNSUPPORTED.
- No full account number appears anywhere; one that does is a PRESENTATION finding that fails.
- You hold no scratch folder: lay out the tie-out by hand (review-numbers check 5) and say so under Assumptions.

Return the `review-numbers` return block.

## DONE (the main agent checks each item and cites its evidence)

1. The engine's outputs are current for the month (newer than the latest raw pull), or the agenda opens with "not current" and names what is missing.
2. No figure comes from an output the engine's `STATUS.md` lists as defective.
3. Every monthly check of the procedure, and each quarterly or annual one due this month, has an answer with a cited source or is `not-found`.
4. Every figure in `AGENDA.md` is in `FIGURES.md` with its source, and the reviewer re-derived them (section Check the figures): PASS, in `RUN/review-figures.md`.
5. Every deadline in the next 90 days is in `REMINDERS.md` with its source.
6. Every decision is a numbered question the owner can answer "1) ok 2) no".
7. Nothing was written outside the domain folder (or the Run folder on a dry run).

## The record of the Run

`extra.checks` (one per procedure item: `{item, answer, source, state}`), `extra.figures` (`{figure, value, source}`), `extra.reminders` and the agenda's path in `files`, as `LOG.md` records them.

## Later tools

- `personal-finance-pull`: a `prepare:` that copies the month's exports into the engine, runs its summarize and check scripts, and saves the check output in the Run folder.
- `personal-finance-check`: compute DONE items 1, 2, 4 and 5 from the Run folder and the engine.
