---
name: month-end-results-report
description: "The reporting phase of a month-end close, run by accounting-month-end-close once the close's four tests pass: an accounting-worker follows its section Write the results memo, and accounting-reviewer checks the figures with review-numbers. Writes the month's results memo (a self-contained HTML file, versioned, never overwriting a reviewed version) from the closed trial balance, comparators and findings file, to the shared results format and QA rules, with every figure tied to the trial balance. Read it to write or check a results memo by hand. Not for the board deck, which is the reporting department's board package."
---

# The results report

The monthly results memo is the close's last phase, because the findings and the results live in the same month folder and one writer keeps them consistent. The format and the checks are in this skill's `references/` folder and are not repeated here:

- `references/month-end-report-format.md`: what the memo says and how it looks (three-way table first, entity and revenue tables, compositions that sum, caveat boxes, the bottom line, the meta block). Violations are defects.
- `references/month-end-report-qa.md`: the QA log, sections A to D, run until clean.
- `month-end-flux`: the variance explanations the memo draws on, already in `reporting/MONTH-END-FINDINGS-{yyyy-mm}.md`.
- `report-tieout`: the cross-report tie when the board package or a lender pack quotes the same months.

The worker also keeps `orchestration-workstream` and `month-end-workstream`.

## When it runs

After `accounting-month-end-check` reports the four tests met (or the owner asks for a preliminary version, which says PRELIMINARY in its title and meta block). A version after the owner's review is a new version; the prior file is never touched.

## Inputs, from the month folder

- the closed trial balance from the latest ledger pull (`work/source/`), dated;
- the comparators (budget and forecast ids) where `SYSTEMS.md` says they are;
- `reporting/MONTH-END-FINDINGS-{yyyy-mm}.md` and the flux;
- the client's own format additions: report folder, name pattern, entity table, standing offset pairs, revenue buckets (in `MONTH-END-RULES.md`);
- the prior version and the prior month's memo, for the style block and the version diff.

## The work

1. Compute the headline figures (Revenue, COGS, Gross profit, SG&A, EBITDA) for actual, budget and forecast from the pull, net the standing offsets, and write `reporting/results-figures-{yyyy-mm}.csv` (figure, value, source: account range and pull file).
2. Write the memo to the format, quoting only figures in that ledger.
3. Run the QA log, write it to `reporting/results-qa-{yyyy-mm} v{n}.md`, fix defects, re-run.
4. Run `report-tieout` over the memo and any other report already issued for the month.

## DONE (the main agent checks each item and cites its evidence)

1. The memo exists in the report folder under the client's name pattern, a new version, with a change list against the prior version.
2. Every headline figure is in the figures ledger and ties to the trial balance pull to the dollar.
3. The QA log shows sections A to D clean.
4. `report-tieout` exits 0 across the month's issued reports, or each difference is a finding.
5. `accounting-reviewer`, briefed with `review-numbers`, re-derives the figures and says PASS.
6. No employee is named and no close-process language remains (QA section B).
7. The review request is on the owner's list; the memo is not sent.

## The file contract with the board package

The reporting department's board package reads two things this phase writes, and both keep their names and shapes: the memo in the report folder under the client's name pattern (`MONTH-END-RULES.md`), and `reporting/results-figures-{yyyy-mm}.csv` with the columns `figure, value, source` (source: account range and pull file). A change to either is a change to that contract.

## Write the results memo

For an `accounting-worker` (model opus) given the folder, the period and any reviewer findings. The goal: a memo the leadership team reads in five minutes, where every figure ties to the closed books and nothing reads like the close's own mechanics. Commands: `trial-balance`, `intacct-gl-detail`, `budget-detail-diff`, `report-tieout`, `mkdir -p`. Skills: this one, `report-tieout`, `month-end-flux`.

Read `MONTH-END-RULES.md` first, then the two files in `references/`. Follow the four steps of The work. Already done? A version the owner has reviewed stands; write the next version, with its change list. On a second dispatch, answer each of the reviewer's findings: fixed, or declined with the reason.

Return the `month-end-workstream` block with `workstream: "results"`, `period` and `pull_date`; `items` with test `flux` for each variance the memo explains (state `explained`); a `rows` entry for the procedures row that asks for the results report; `files` the memo, the figures ledger and the QA log; and `findings` for every tie-out difference.

## Later tools

- `results-figures`: compute the headline figures and the ledger from the pull and the comparators in code, so DONE item 2 is a command.
- `results-check`: run QA sections A to C in code and add a `results` test to `accounting-month-end-check`.
