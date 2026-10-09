---
name: firm-books-workstream
description: Reference loaded by firm-books-orchestrator and the month-end workstreams it dispatches, not for a user request; what closing a small professional-services firm's own books adds to month-end-workstream. Covers the Books folder and BOOKS-RULES.md, the ledger export standing in for an ERP pull, revenue and AR tied to the firm-billing period folder and issued invoices, owner and tax items kept apart from operating expense, reimbursable client expenses, vendor information-return coding and the DONE checklist.
---

# The firm's own books

This skill extends `month-end-workstream` (and through it `orchestration-workstream`): keep their conduct and return their block. Read them at `~/.claude/skills/<name>/SKILL.md` if they are not loaded. What follows is only what a small professional-services firm closing its own books adds, whatever its legal form (sole proprietor, partnership, LLC, small company).

## The folder

The Books folder follows the month-end layout (`<WORK>` is `BOOKS`): `BOOKS-PROCEDURES.md`, `BACKGROUND.md`, `SYSTEMS.md`, `METADATA_FIELDS.md` (the chart of accounts and classes), `STATUS.md`, and `{yyyy}/{yyyy-mm}/` per month with `STATUS.md`, `LOG.md`, `CONFIRMATIONS.md`, `journal-entries/`, `reconciliations/`, `reporting/`, `work/source/`. `BOOKS-RULES.md` (at the root) names the ledger in use, its export, the materiality and tolerance, and where the firm-billing folder and the bank statements are. It wins over this skill.

## The ledger export

The firm's ledger has no read API here. A person saves the period's general ledger and trial balance exports into `work/source/`, with `pulled.md` saying when and from which system. Read them through `gl-normalize` and `trial-balance` where a workstream has them; otherwise read the CSV. An export older than the last booked entry is stale: say so, never work around it.

## What a firm's close adds

- **Revenue ties to billing.** Each month's revenue equals the firm-billing period's invoices (`firm-billing-workstream` folder: the lines files and the issued invoice files), by client and contract. A billed invoice not in the ledger, or ledger revenue with no invoice, is a finding. Unbilled work the billing run named is not revenue until invoiced unless the rules say accrue it.
- **AR ties to issued invoices less receipts**, client by client, aged.
- **Reimbursable expenses.** A client-reimbursable cost is billed through or is a receivable; one that was paid and never billed is a finding for the next billing run.
- **Firm-level items apart.** Items that belong to the owners or to the firm's tax position, not to its operations, go to the equity, due-from or tax accounts the rules name, never to operating expense. Which ones apply depends on the firm's legal form and jurisdiction; the rules list them. Examples: owner or partner draws and distributions, estimated or prepaid income tax payments, partner capital contributions, owner compensation booked differently from staff payroll, and personal costs paid by the firm.
- **Vendor information returns.** Where the firm's jurisdiction requires a year-end return on payments to contractors (in the US, Form 1099), each vendor paid this month carries its status in `METADATA_FIELDS.md`; an unknown status is a proposal, and the US year-end work is `vendor-1099-workstream`'s. Where no such return applies, the rules say so and this item is not applicable.
- **Independence.** In a small firm one person is often both preparer and approver. Where one person is both, the independent reviewer agent is the second pair of eyes: every entry and reconciliation needs the reviewer's PASS before it counts. Where the firm has a second person who approves, the reviewer's PASS still comes first.

## DONE checklist

The orchestrator checks each item against evidence it can cite; the reviewer confirms 2, 3 and 6.

1. The period's ledger export is dated after the last entry booked for the period.
2. Every entry the procedures and the findings call for is drafted with backup and seen booked in a fresh export, or waits on a named person.
3. Every balance-sheet account in the trial balance is reconciled within the rules' tolerance.
4. Revenue by client equals the period's issued invoices; every difference is explained.
5. AR by client ties to open invoices; anything older than the rules' aging threshold (default 60 days) is a finding.
6. The firm-level items the rules list (for example owner draws, estimated tax payments, personal costs) are classified as the rules say.
7. Every question is answered or its effect stated; nothing waits without a Waiting on row.
8. The sign-off review on `fable` says PASS.

## Later tools

- `firm-books-pull`: export the firm ledger's GL and trial balance into `work/source/` with `pulled.md`, once the ledger has an API.
- `firm-books-check`: compute DONE items 1 to 5 from the folder and the exports.
- `billing-ledger-tie`: tie the firm-billing period's invoices to the ledger's revenue by client.
