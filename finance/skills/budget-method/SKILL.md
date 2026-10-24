---
name: budget-method
description: "How an annual three-way budget or operating plan (P&L, balance sheet, cash) is built from drivers and defended, on top of forecast-method, and the finance-budget job's Steps: the budget as a vintage in the Forecast folder, assumptions with owners before any number, the P&L by driver tree, balance sheet and cash tied, a 13-week cash view for the first quarter, the bridge from the current-year forecast, the board draft, and the DONE checklist. Sections Build a pass (finance-budget) and Check the statements (finance-reviewer). Use for \"build next year's budget\", with or without finance-budget. Not for a reforecast; use forecast-method."
argument-hint: "[Forecast folder] [fiscal year] [pass]"
allowed-tools: Read, Glob, Grep, Bash(finance-forecast-extract:*), Bash(budget-detail-diff:*), Bash(trial-balance:*), Bash(excel-handle:*)
---

# The budget method

A budget is a forecast with no prior to revise: the method of `forecast-method` holds (driver tree, citation rule, questions with owners and fallbacks, a bridge that foots, versions as submissions). Load it first. This skill adds what a budget needs that a revision does not, and the Steps `finance-budget` follows. It is built in passes over several sessions across the budget calendar; each session moves it forward and leaves the folder resumable. Whoever does a section also keeps `orchestration-workstream`.

## Inputs

- **Forecast folder** (required), with `FORECAST-RULES.md` and `budgets/<fy>/BUDGET.yaml`.
- **Fiscal year** (optional): default the next fiscal year in `FORECAST-SETTINGS.yaml`.
- **Pass** (optional): `assumptions`, `statements`, `board` or `auto`. Default `auto`, the first pass whose DONE items are not met.
- **Instructions** (optional): override the defaults here, never `FORECAST-RULES.md`.
- **Dry run**: build the budget folder inside the Run folder (or a scratch folder by hand); write nothing in the Forecast folder and ask no one.

## Steps

For `finance-budget`, and by hand. Without an Automation, the same steps run in one session; the questions then go in the report.

1. [judgment] Orient. Read the rules file, BUDGET.yaml, the driver tree, the budget's STATUS.md, LOG.md and CONFIRMATIONS.md, and the latest vintage's summary; pick the pass. If the budget folder does not exist, create it from Where it lives and write BUDGET.yaml for the owner to confirm the calendar.
   → the budget folder was just created: step 8
2. [script] Collect answers: `confirm check FOLDER/budgets/<fy>`; each answered assumption takes its value and source, each one past due takes its fallback, and is closed with `confirm close` as the comms-confirm skill says.
3. [judgment] The assumptions pass (section Build a pass, assumptions). Record each open assumption's question in CONFIRMATIONS.md.
   → pass is not assumptions: step 4
4. [judgment] The statements pass, once every assumption has a value or a fallback (section Build a pass, statements): the three statements, the 13-week cash and the bridge, read through `finance-forecast-extract`, `trial-balance`, `budget-detail-diff` and `excel-handle`.
   → an assumption has neither value nor fallback: step 7
5. [hand-off: finance-reviewer] Check the statements (section Check the statements), on opus, with the statements, assumptions.json, the last closed balance sheet and the forecast it bridges from, never your reasoning. Write its return to `reviews/`.
   → FAIL: step 4 (max 1)
6. [hand-off: finance-reviewer] The board pass, once the statements PASS: write board-draft.md (section Build a pass, board), then have it read cold with `review-red-team` (the draft only, the board as audience, approval as the purpose) and its figures re-derived with Check the statements; one revision on their findings. Write each return to `reviews/`.
   → FAIL: step 6 (max 1)
7. [script] Ask. Each open assumption goes to its owner's role with `confirm new` and `confirm task`, then one batched message with `confirm relay`, at most one a week. Skip on a dry run.
8. [judgment] Close. Walk the DONE checklist, citing evidence for each item; update STATUS.md with the next pass and its date; append the session to LOG.md; report.
   → reported: done

Nobody watches a scheduled session: never end with `needs_owner` unless BUDGET.yaml is missing.

## Where it lives

The Forecast folder (`forecast-method`, its `contract.md`), so the budget shares the rules, `modules.yaml` and `driver-tree.yaml` with the forecasts it will later be measured against:

```
<Forecast folder>/budgets/<fy>/
  BUDGET.yaml            fiscal year, calendar (kickoff, board draft, approval), comparator forecast,
                         who owns each assumption area (roles), materiality
  assumptions.json       A-nnn: every driver assumption, its value, owner, source, confidence, fallback
  pl.csv bs.csv cash.csv the three statements by month, account and dimension, built from assumptions
  cash-13w.csv           the first thirteen weeks of cash
  bridge.md              the current-year forecast (annualized run rate) to the budget, by driver
  board-draft.md         the board's view: the plan in one page, the asks, the risks
  reviews/  STATUS.md  LOG.md  CONFIRMATIONS.md   (written by finance-budget only)
```

## Assumptions before numbers

Write `assumptions.json` before any statement. Each assumption: `id`, `area` (revenue, headcount, compensation, non-payroll opex, capital, working capital, financing, tax), `driver` (a node of the driver tree), `value`, `unit`, `owner` (a role), `source` (an evidence id, or `judgment`), `confidence` (0 to 1), `fallback` (the value used if the owner does not answer by the date). The headcount plan is the usual weak link: every planned hire has a role, a start month, a cost and an owner who asked for it. Plan headcount by role; never name an employee.

## The three statements tie

- The P&L is built by driver from the assumptions, account by account and month by month; every row names the assumption ids it uses.
- The balance sheet rolls from the last closed balance (or the forecast's year-end balance) through the P&L, working-capital days (receivable, payable, deferred revenue, prepaid), capital spend and depreciation, debt and equity movements.
- Cash is the change in the balance sheet's cash line, and the indirect cash flow foots to it to the dollar. Assets equal liabilities plus equity every month.
- The 13-week view starts from the latest actual cash balance and the known weekly timing (payroll dates, rent, debt service, the largest customers' payment habits).

## The bridge and the board draft

`bridge.md` takes the current-year forecast, annualizes it as the forecast-method bridge would treat a run rate, and walks to the budget by driver, each line citing its assumptions, corrections apart from business changes. `board-draft.md` follows the forecast-method executive-summary contract: the plan, top drivers, what would change it, the asks of the board.

## Build a pass

Done by `finance-budget` itself, one pass per session, one slice at a time. The goal: work the board and the team can rely on, where every figure names the assumption it came from and the three statements agree.

- **assumptions**: from the closed actuals (`trial-balance`), the latest forecast vintage, the driver tree, prior budgets and the answers given, write `assumptions.json` as Assumptions before numbers says. Every assumption without a source is a question to its owner's role with its fallback.
- **statements**: build `pl.csv`, `bs.csv`, `cash.csv`, `cash-13w.csv` and `bridge.md` from the assumptions only. Read workbooks through `finance-forecast-extract` or `excel-handle` and never save one; compare budget detail with `budget-detail-diff`. Check the ties yourself before the review; a tie that fails is a finding, never a plug.
- **board**: write `board-draft.md` from the statements and the bridge; on a second round, answer the reviewers' findings (fixed, or declined with the reason).

## Check the statements

For `finance-reviewer`, given the statements, `assumptions.json`, the last closed balance sheet, the forecast the budget bridges from and, for the board pass, `board-draft.md`; never the builder's reasoning. Load `review-numbers` too and run its checks over every file; this section adds:

1. Every P&L row cites assumption ids that exist in `assumptions.json`; recompute a sample of rows from their assumptions. A row with no assumption is a plug: FAIL.
2. The balance sheet balances every month; cash in `bs.csv` equals `cash.csv`'s closing cash every month, re-derived from the P&L and the movements, not read off the file.
3. `cash-13w.csv` opens on a dated actual balance that matches its source.
4. The bridge starts at the comparator forecast's figures and foots to the budget's revenue and EBITDA.
5. Every figure in `board-draft.md` is in the statements or the bridge.

Return `review-numbers`' verdict and findings, with these lines' results first.

## DONE (finance-budget checks each item and cites its evidence)

1. Every assumption has an owner, a source or `judgment`, a confidence and a fallback; every open one is a question with a due date.
2. Every P&L row cites assumption ids; no row is a plug.
3. The balance sheet balances every month and cash ties to the cash flow (the reviewer re-derives both).
4. The bridge from the current-year forecast foots to the budget's EBITDA and revenue.
5. `cash-13w.csv` starts from a dated actual balance.
6. The board draft quotes only figures in the three statements or the bridge, and the red-team read was answered.
7. `finance-reviewer` says PASS on the statements, the bridge and the board draft (Check the statements).
8. No issued workbook was edited; the budget is a new submission, and nothing was sent or uploaded.

Items 3, 6 and 7 rest on the reviewer's return, not the builder's reading. A pass is done when its items are met; the budget is done when all are.

## Later tools

- `budget-three-way`: roll the balance sheet and cash from the P&L and the working-capital assumptions and prove DONE item 3 in code.
- `budget-check`: compute DONE items 1 to 5 and 8 from the folder.
- `budget-render`: write the three statements into the company's budget workbook template as a new file for upload by a person.
