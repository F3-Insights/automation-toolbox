---
name: month-end-expectations-brief
description: Before month end, ask leadership "what are the big things you expect to see this month", keep the answers as a brief in the month folder, and after the flux report each item as observed as expected, expected but not observed, or observed but not expected, turning a bare variance into "expected X, saw Y". Use at the start of a close (collect), on the first working day (confirm) and when the flux is explained (reconcile). The variance analysis itself is month-end-flux.
argument-hint: "[Month-End folder] [period yyyy-mm] [collect | confirm | reconcile]"
allowed-tools: Read, Glob, Grep, Write, Edit
---

# Management expectations brief

A close that knows what leadership expected can say "the settlement landed as planned" instead of "other income is favourable by $150k." This skill collects the expectations before the month ends, confirms them on working day one, and reconciles them against the books once the flux is explained.

## The one question

Ask top management, in one message or one five-minute call:

> **What are the big things you expect to see this month?**

Then prompt for the four kinds, in this order, because people answer the first kind and forget the rest:

1. **Expected one-off transactions.** Equity or financing events, settlements, asset purchases, unusual payments in or out. Amount and counterparty if known.
2. **Expected permanent changes.** Hires, raises, terminations, new or ended vendors, pricing changes, customers starting or stopping.
3. **Expected pipeline outcomes.** "We expect N signings" or "N go-lives", so the close can report expected N, saw M.
4. **Known risks and watch items** management wants eyes on.

Do not ask about the normal per-account expectations; those come from the budget or forecast. This brief is for what sits above it.

## Modes

**`collect`** (the last week of the month).
- The question goes out through comms-confirm, to the people the Month-End folder's BACKGROUND.md names as leadership.
- When answers arrive, write `reporting/EXPECTATIONS-{yyyy-mm}.md` in the month folder, one row per item:

| # | Kind | Item | Amount or count | Counterparty | Source (who said it, when) | Status |
|---|---|---|---|---|---|---|

Status starts as `expected`.

**`confirm`** (working day one). Re-read the list to the owner in one screen; ask what has changed since; append rather than overwrite, stamping the date.

**`reconcile`** (after the flux is explained). For each row, search the ledger pull and the findings and set exactly one status:

- **observed as expected**: say so in the findings and do not re-explain it.
- **expected but not observed**: is it unbooked, delayed or cancelled? Each becomes a question for its owner, through comms-confirm.
- **observed but not expected**: it is a genuine surprise in the findings, and the brief gets a new row so next month's question is better.

## Rules

- The brief is evidence about expectations, not about the books; it never changes a number.
- Items nobody said are not on the list; do not infer expectations from the forecast.
- Amounts are as stated, marked approximate if they were.
