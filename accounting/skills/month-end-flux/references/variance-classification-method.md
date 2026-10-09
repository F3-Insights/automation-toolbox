# Variance analysis: hypotheses, then verification

Read by `month-end-flux`, and useful to any work that explains a P&L against a budget or forecast.

Variances are provisional until verified. Every claim traces to snapshot rows (JE ids, customers, vendors, amounts) and carries an `account:period:amount` citation a gate can resolve. Each item is tagged **real / timing / mapping / misclassification / needs-business-input**.

## Build the comparison

- Budget comes from the ledger's budget detail; the forecast is the forecast of record for the month, named explicitly. Tie its EBITDA to the number the owner expects before analysing anything; uploads have disagreed with the workbook they came from. Budget amounts are stored positive; apply contra signs.
- **Calibrate first.** Compute the prior closed month from the GL the same way and tie it to the known reference to $0.00. Only then trust the target month.
- Rollups by account family (revenue, cost of sales, SG&A, other); EBITDA = revenue minus cost of sales minus SG&A. Name the account ranges once, in the client calibration file, not in prose.
- Check first whether the day-2-to-7 close entries exist. A mid-close P&L shows negative expense accounts and $0 travel, and EBITDA "as booked" is overstated by the missing accruals. Say so rather than analysing a half-closed month.

## Segment revenue by entity first

Decompose the headline revenue variance by legal entity on both actuals and budget before looking at any account. A consolidated miss has decomposed, in practice, into one entity favourable and the others not billing: a different story than the account view tells.

## The classification loop before declaring any variance

- **Offsetting-pair test.** Opposite-sign, similar-magnitude variances within account families or across departments and entities usually mean one pot of spend booked or forecast in different places. Resolution is exactly one of: a reclass JE, a forecast remap, or one joint explanation. Never two stories.
- **Vendor-versus-forecast-line test.** Is the same vendor simply on a different line in the model?
- **Net standing pairs before presenting.** Consulting complexes, IT subscriptions, meetings, payroll nets: list the pairs in the client calibration file and net them.

## Drill-down toolkit

- Revenue by customer from AR invoice lines; expense by vendor from AP bill lines (memos carry service periods). GL batch lines hide counterparties.
- **Run-rate context.** Account versus trailing five-month median separates "forecast wrong" from "business changed." Favourable surprises get the same suspicion as unfavourable ones: missing expense masquerades as savings.
- Expected one-offs come from the management expectations brief; label them as expected rather than re-explaining them.
- Reversal mechanics: month-M accrual reversals landing in M+1 distort single-month views.

## Output

Three-way table first (actual, forecast, budget), then buckets in the results format the `month-end-results-report` skill sets: bold claim, one fact per sub-bullet, compositions labelled and visibly summing. Quantify how much of the "favourability" is artifact (mapping, timing, reconciliation) versus genuine.
