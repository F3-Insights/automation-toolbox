---
name: budget-method
description: "How an annual three-way budget or operating plan (P&L, balance sheet, cash) is built from drivers and defended, on top of forecast-method: the budget as a vintage in the Forecast folder, assumptions with owners before any number, the P&L by driver tree, balance sheet and cash tied, a 13-week cash view for the first quarter, the bridge from the current-year forecast, the board draft, and the DONE checklist budget-orchestrator checks. Use for \"build next year's budget\", with or without that orchestrator. Not for a reforecast; use forecast-method."
---

# The budget method

A budget is a forecast with no prior to revise: the method of `forecast-method` holds (driver tree, citation rule, questions with owners and fallbacks, a bridge that foots, versions as submissions). Load it first. This skill adds what a budget needs that a revision does not. Workers also keep `orchestration-workstream`.

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
  reviews/  STATUS.md  LOG.md  CONFIRMATIONS.md   (the last three the orchestrator's only)
```

## Assumptions before numbers

Write `assumptions.json` before any statement. Each assumption: `id`, `area` (revenue, headcount, compensation, non-payroll opex, capital, working capital, financing, tax), `driver` (a node of the driver tree), `value`, `unit`, `owner` (a role), `source` (an evidence id, or `judgment`), `confidence` (0 to 1), `fallback` (the value used if the owner does not answer by the date). The headcount plan is the usual weak link: every planned hire has a role, a start month, a cost and an owner who asked for it.

## The three statements tie

- The P&L is built by driver from the assumptions, account by account and month by month; every row names the assumption ids it uses.
- The balance sheet rolls from the last closed balance (or the forecast's year-end balance) through the P&L, working-capital days (receivable, payable, deferred revenue, prepaid), capital spend and depreciation, debt and equity movements.
- Cash is the change in the balance sheet's cash line, and the indirect cash flow foots to it to the dollar. Assets equal liabilities plus equity every month.
- The 13-week view starts from the latest actual cash balance and the known weekly timing (payroll dates, rent, debt service, the largest customers' payment habits).

## The bridge and the board draft

`bridge.md` takes the current-year forecast, annualizes it as the forecast-method bridge would treat a run rate, and walks to the budget by driver, each line citing its assumptions, corrections apart from business changes. `board-draft.md` follows the forecast-method executive-summary contract: the plan, top drivers, what would change it, the asks of the board.

## DONE (the orchestrator checks each item and cites its evidence)

1. Every assumption has an owner, a source or `judgment`, a confidence and a fallback; every open one is a question with a due date.
2. Every P&L row cites assumption ids; no row is a plug.
3. The balance sheet balances every month and cash ties to the cash flow (the checker re-derives both).
4. The bridge from the current-year forecast foots to the budget's EBITDA and revenue.
5. `cash-13w.csv` starts from a dated actual balance.
6. The board draft quotes only figures in the three statements or the bridge, and the executive red team has read it cold.
7. The checker (`numbers-reviewer`) says PASS on the statements, the bridge and the board draft.
8. No issued workbook was edited; the budget is a new submission.

## Later tools

- `budget-three-way`: roll the balance sheet and cash from the P&L and the working-capital assumptions and prove DONE item 3 in code.
- `budget-check`: compute DONE items 1 to 5 and 8 from the folder.
- `budget-render`: write the three statements into the company's budget workbook template as a new file for upload by a person.
