---
name: cash-forecast-method
description: "How a rolling 13-week cash forecast is built by the direct method and kept honest: the cash folder beside the Forecast folder, the week's inputs (bank balance, AR and AP agings, calendars), receipts by customer payment habit, payments by aging and calendar, last week's forecast against actual split into timing and permanent, the low point and headroom against a minimum, and the DONE checklist cash-forecast-orchestrator checks. Use for \"update the cash forecast\" or \"will we run short\", with or without that orchestrator. Not for the P&L forecast; use forecast-method."
---

# The 13-week cash forecast

A short-horizon, direct-method forecast: cash in and cash out by week, not a P&L turned into cash. It answers "what is the low point and when", and it earns trust by explaining its own misses every week. The budget's first-quarter `cash-13w.csv` (`budget-method`) is a fine seed; from then on the rolling forecast stands alone. Workers keep `orchestration-workstream`.

## Where it lives

`CASH-FORECAST-RULES.md` (beside the cash folder, or wherever the caller points) names the week-ending day, the lines and the bank mapping, the variance threshold, the minimum cash, the inputs' freshness window and who owns each input. It wins over this skill.

```
<Forecast folder>/cash/
  STATUS.md  LOG.md  CONFIRMATIONS.md       the orchestrator's only
  <yyyy-mm-dd>/                             one folder per week-ending date, never overwritten
    inputs/              bank export, AR aging, AP aging, payroll and debt calendars as saved
    actuals.csv          the week's actual receipts and payments by line
    variance.md          last week's forecast for this week against actual, misses explained
    forecast-13w.csv     week, line, amount, basis (aging:<ref>, calendar:<name>, assumption:<id>)
    assumptions.json     id, line, week, amount, owner (a role), source, fallback, confidence
    summary.md           one page for leadership
    reviews/
```

## Lines

Receipts: customer collections (by the largest customers named, the rest as one line), other receipts (financing draws, asset sales, tax refunds). Payments: payroll and benefits, rent, vendors (AP), debt service, taxes, capital spending, owner or investor distributions. The rules' mapping turns bank transactions into these lines; an unmapped transaction is a proposal to the mapping, not a guess.

## How each line is forecast

- **Collections.** Each open invoice lands in the week its customer usually pays: the customer's average days past invoice over the last six months, from the paid history. New billings come from the forecast or the budget's revenue by week. Disputed and over-90-day invoices land nowhere until a person says when.
- **AP.** Each open bill lands on its due date, or on the company's payment-run day when the rules say bills are paid in runs. Recurring vendors not yet billed come from the last three months' run rate.
- **Calendars.** Payroll on its pay dates, with the tax deposit; rent and debt service on their dates; taxes on the filing calendar.
- **One-offs.** Only what a person stated or a document shows, as an assumption with its owner.

## The variance

Each week, before rolling, compare last week's forecast for the closed week with actual by line. A miss over the threshold is either **timing** (the cash moved to a later week; carried forward) or **permanent** (it will not happen, or something new happened). Permanent misses in the same line two weeks running are a finding about the method, with a proposed fix.

## DONE checklist

The orchestrator checks each item with evidence; the reviewer confirms 2, 3 and 5.

1. The week's inputs are in `inputs/` and inside the freshness window, or the week is marked PRELIMINARY with the missing input on the Waiting on table.
2. Opening cash equals the bank balances at the week's end, account by account.
3. Every forecast row names its basis; no row is "other" or a plug.
4. Every variance miss over the threshold is classed timing or permanent with evidence.
5. Each week's closing balance equals opening plus receipts less payments, for all thirteen.
6. The low point and the headroom against the minimum are stated; any week under the minimum is a finding.
7. `summary.md` quotes only figures in the forecast or the variance.
8. Every open assumption is a question with an owner and a fallback.

## Later tools

- `cash-actuals`: map the bank export to forecast lines and write `actuals.csv`.
- `cash-roll`: lay the agings and calendars into weeks and prove DONE item 5 in code.
- `cash-forecast-check`: compute DONE items 1 to 6 from the week's folder.
