---
name: sage-intacct-reference
description: "Reference for Sage Intacct in a close, loaded by other skills rather than for a user request: how its REST API behaves for any company (objects, fields, sign conventions, report services, the traps that cost a day) and, in import-format.md beside it, the GL journal-entry import CSV layout that actually imports. Load it before reading the ledger with erp-ledger-pull or drafting an import file with month-end-journal-entry on an Intacct company."
user-invocable: false
---

# Sage Intacct REST v1: behaviour that holds for any company

Generic; do not rediscover. What is specific to one company (its entities, its integration users, its permission history, its data start date) belongs in that company's Month-End folder, in `SYSTEMS.md`.

## Access and credentials
- Read Intacct through a read-only REST client that `SYSTEMS.md` names. Credentials come from the process environment or a secrets store; never read, print or copy one into a folder.
- An API user can see **draft and submitted** entries. Every header and line carries `state`; analysis uses posted only and lists drafts separately.
- AP `payment-detail` / `payment-line` answer REST-3007 until the API user's role has AP "Posted payments". Duplicate-payment checks stay manual until then.
- The ideal end state: the API user may enter journal entries but never post.

## Objects and fields
- Object names use slashes (`general-ledger/journal-entry-line`); dotted refs traverse and work in filters (`glAccount.id`, `journalEntry.glJournal.id`, `bill.postingDate`, `invoice.customer.name`).
- `journal-entry.automaticReversalDate` cannot be queried. Use `reversedFromDate`, `reversedBy.id`, and the "Reversed - " description prefix for reversal linkage.
- `journal-entry-line.accountingPeriod` is always null; bucket by `entryDate`.
- `general-ledger/journal` has no `title` (use `id`, `name`).
- **Headers may not cover all lines.** The `journal-entry` query can omit entries created by an integration user (a payment platform's own journal and its receipts in the cash journals) while `journal-entry-line` returns their lines. A pull should list the known integration creators and journals in the company's settings and fail on any other header-less line in the period.
- `$contains` is case-sensitive; customer and vendor names are often UPPERCASE.
- AR adjustments: header date is `glPostingDate`; amounts are not on the header (GET each, or use GL lines); line ref is `arAdjustment.*`. AR `payment` is thin (no amount, no customer); trace applications via `accounts-receivable/payment-detail`.
- Budgets: `general-ledger/budget` has only id/key; detail is `budget-detail` filtered on `budget.id` with `reportingPeriod.id` like "Month Ended August 2026". Amounts are stored positive; apply contra signs from the company's chart.
- Subledger GL lines carry batch-summary descriptions (no counterparty): customer attribution needs `invoice-line`, vendor attribution needs `bill-line`.

## Conventions
- Sign convention: revenue (4xxxx) = credit - debit; every other P&L = debit - credit. Use `baseAmount`.
- Entity = `dimensions.location.id`. The company's entities, and which intercompany accounts must net to zero, are in its own folder.
- Always check `len(rows) == totalCount`; always re-pull after the team books entries (a month can move after "final"); state the data vintage on every output.

## Imports
- GL journal-entry import CSVs: see `import-format.md` beside this file.

## Trial balance and GL reports
- Balances are not query objects (`general-ledger/account-balance` etc. answer REST-1033 'not supported in version 1'). Intacct's reports are REPORT SERVICES: `services/reports/general-ledger/trial-balance`, `.../account-balance`, `.../details` (POST with parameters; then `services/reports/status` and `services/reports/download`). They answer REST-3007 until the API user's role has Run permission on the GL reports.
- `services/core/model` with no name lists every object and service; with a name it returns the request/response model. An unknown name returns an EMPTY field list, not an error; query the object to tell 'missing' (REST-1033) from 'no permission' (REST-3007).
- Fallback while the report permission is pending: the `trial-balance` command computes it from posted lines (history, a bridge, and the close's live pull; balance sheet cumulative, P&L fiscal-year-to-date, prior years' net income on one computed line).
