---
name: cash-forecast-method
description: "How a rolling 13-week cash forecast is built by the direct method and kept honest, and the finance-cash-forecast job's Steps: the cash folder beside the Forecast folder, the week's inputs (bank balance, AR and AP agings, calendars), receipts by customer payment habit, payments by aging and calendar, last week's forecast against actual split into timing and permanent, the low point and headroom against a minimum, and the DONE checklist. Sections Roll the week (finance-cash-forecast) and Check the week (finance-reviewer). Use for \"update the cash forecast\" or \"will we run short\", with or without finance-cash-forecast. Not for the P&L forecast; use forecast-method."
argument-hint: "[Forecast folder] [week ending]"
allowed-tools: Read, Glob, Grep, Bash(ar-ap-hygiene:*), Bash(trial-balance:*), Bash(gl-normalize:*), Bash(excel-handle:*), Bash(pdf-handle:*)
---

# The 13-week cash forecast

A short-horizon, direct-method forecast: cash in and cash out by week, not a P&L turned into cash. It answers "what is the low point and when", and it earns trust by explaining its own misses every week. The budget's first-quarter `cash-13w.csv` (`budget-method`) is a fine seed; from then on the rolling forecast stands alone. Whoever does a section keeps `orchestration-workstream`. Leadership should know, every week, how much cash the company will have in each of the next thirteen weeks, where the low point is, and why this week's view differs from last week's.

## Inputs

- **Forecast folder** (required), its `cash/` folder as laid out below, and `CASH-FORECAST-RULES.md` (its path from the caller).
- **Week** (optional): the week-ending date the roll starts from, yyyy-mm-dd. Default: the last week-ending date the rules name before today.
- **Instructions** (optional): override the defaults here, never the rules.
- **Dry run**: build the week's folder inside the Run folder (or a scratch folder by hand); write nothing in the Forecast folder and ask no one.

## Steps

For `finance-cash-forecast`, and by hand; without an Automation the questions go in the report.

1. [judgment] Orient. Read CASH-FORECAST-RULES.md, the cash folder's STATUS.md, last week's forecast and CONFIRMATIONS.md. With no prior week, seed from the latest budget's cash-13w.csv or from the rules' opening list, and say so.
2. [script] Collect answers: `confirm check FOLDER/cash`; use each answer, take each past-due fallback, and close each with `confirm close` as the comms-confirm skill says.
3. [judgment] Check the inputs. The week's bank balance export, AR aging and AP aging are in the week's `inputs/` and dated inside the rules' freshness window. A missing or stale input goes on the Waiting on table; the roll then runs from the last good input and is marked PRELIMINARY.
   → no bank balance for the week at all: stop
4. [judgment] Roll the week (section Roll the week), yourself.
5. [hand-off: finance-reviewer] Check the week (section Check the week), on opus, with the week's folder, its inputs and last week's forecast, never your reasoning. Write its return to the week's `reviews/`.
   → FAIL: step 4 (max 1)
6. [script] Ask. Each assumption only a person can give (a large customer's payment date, a capital purchase, a tax payment) goes to its role with `confirm new` and `confirm task`, then one batched message with `confirm relay`, at most one a week. Skip on a dry run.
7. [judgment] Close. Walk the DONE checklist with evidence; update STATUS.md and LOG.md; report the week, opening cash and its source, the thirteen closing balances, the low point and the headroom, last week against actual, the reviewer's verdict, and the questions as one numbered list.
   → reported: done

Nobody watches a scheduled session: never end with `needs_owner` unless the week's bank balance is missing. Never move, schedule or approve a payment, contact a bank, customer or vendor, edit a person's cash workbook or the ERP, or overwrite an earlier week.

## Where it lives

`CASH-FORECAST-RULES.md` (beside the cash folder, or wherever the caller points) names the week-ending day, the lines and the bank mapping, the variance threshold, the minimum cash, the inputs' freshness window and who owns each input. It wins over this skill.

```
<Forecast folder>/cash/
  STATUS.md  LOG.md  CONFIRMATIONS.md       finance-cash-forecast's only
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

## Roll the week

Done by `finance-cash-forecast` itself, into the week's folder. The goal: a forecast leadership can act on, where every line says where it came from, and an honest account of how last week's forecast did.

1. **Actuals.** From the week's bank export, the actual receipts and payments by line, mapped to the forecast's lines with the rules' mapping. Write `actuals.csv`. Read a PDF statement with `pdf-handle`, a workbook with `excel-handle`; never save one.
2. **Variance.** Last week's forecast for the week against `actuals.csv`, by line. Explain every miss over the rules' threshold as timing or permanent (The variance, above), with the evidence. Write `variance.md`.
3. **Roll.** Opening cash is the bank balance at the week's end. Build weeks 1 to 13 by line, as How each line is forecast says: receipts from the AR aging and each customer's payment habit (`ar-ap-hygiene` over the agings; `trial-balance` and `gl-normalize` when the paid history comes from the ledger), payments from the AP aging, the payroll, rent and debt calendars, taxes and known one-offs. Every row names its basis. Write `forecast-13w.csv` and `assumptions.json`.
4. **Summary.** One page, `summary.md`: the low point, the headroom, the three biggest changes from last week and why. Quote only figures in `forecast-13w.csv` and `variance.md`.

An assumption only a person can give is a question with its owner (a role) and its fallback, never a guess. An unexplained amount is a finding, never "other".

## Check the week

For `finance-reviewer`, given the week's folder (inputs, `actuals.csv`, `variance.md`, `forecast-13w.csv`, `assumptions.json`, `summary.md`) and last week's forecast; never the maker's reasoning. Load `review-numbers` and run its checks; this section adds, each a blocker:

1. **Opening cash** (DONE 2) equals the bank balances in `inputs/` at the week's end, account by account, read from the export itself.
2. **Every row has a basis** (DONE 3) that resolves: an aging line that exists, a calendar entry, or an assumption id in `assumptions.json`. A row called "other" or with no basis is a FAIL.
3. **The roll foots** (DONE 5): for each of the thirteen weeks, closing equals opening plus receipts less payments, and each week's opening is the prior week's closing; recompute all thirteen.
4. **The variance** compares last week's forecast for this week, not another week's, and every miss over the threshold is classed.
5. **The summary** quotes only figures in the forecast or the variance, and the low point and headroom are the ones the forecast produces.

Return `review-numbers`' verdict and findings, with these lines' results first.

## DONE checklist

`finance-cash-forecast` checks each item with evidence; items 2, 3 and 5 count only with `finance-reviewer`'s PASS (Check the week).

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
