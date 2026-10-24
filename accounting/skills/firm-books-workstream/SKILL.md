---
name: firm-books-workstream
description: "The job skill of accounting-firm-books-close, also read by the accounting-worker it dispatches, not for a user request: what closing a small professional-services firm's own books adds to month-end-workstream. Covers the session's Steps, the Books folder and BOOKS-RULES.md, the ledger export standing in for an ERP pull, revenue and AR tied to the firm-billing period folder and issued invoices, owner and tax items kept apart from operating expense, reimbursable client expenses, vendor information-return coding and the DONE checklist. Not for a client company's close; use month-end-close."
---

# The firm's own books

This skill extends `month-end-workstream` (and through it `orchestration-workstream`): keep their conduct and return their block. Load them with the Skill tool if they are not loaded. What follows is only what a small professional-services firm closing its own books adds, whatever its legal form (sole proprietor, partnership, LLC, small company). The goal: the firm's books for the period closed and provable, every entry the month needs drafted with backup and seen booked, every balance-sheet account reconciled, the month's revenue tied to what the firm billed, and the firm-level owner and tax items the rules list set apart from operating expense.

The main agent is the only writer of the month's `STATUS.md`, `LOG.md`, procedures copy and evidence file. It records each worker return as `month-end-close` says under Recording a return, with `accounting-month-end-record` (which writes `{yyyy}/{yyyy-mm}/MONTH-END-EVIDENCE-{yyyy-mm}.csv` in the Books folder too). `accounting-month-end-check` does not read this layout (it expects `MONTH-END-PROCEDURES.md` and an ERP pull), so the DONE checklist below is walked by hand, item by item, with its evidence.

## Steps

1. [judgment] Orient. Read `BOOKS-RULES.md`, the standing documents and the period's `STATUS.md`, `LOG.md` and procedures copy, laid out as below.
   → the period is not set up: step 2
   → set up: step 3
2. [hand-off: accounting-worker] Set up the month: one worker (model sonnet) told to follow `month-end-close`'s section Set up a month, with the Books folder, the period and `BOOKS-RULES.md` and `BOOKS-PROCEDURES.md` in place of the month-end rules and procedures. Record its return.
3. [judgment] Get the ledger. Find the period's ledger export in `work/source/` (The ledger export). No export, or one older than the last booked entry: record it on the Waiting on table and work only what does not need it.
   → no export and nothing works without it: step 7
4. [judgment] Plan. List the open checklist rows and accounts by workstream; note what waits on a person or an input. Never redo what the owner already did.
5. [hand-off: accounting-worker] Dispatch in parallel, one worker each (model opus), told to follow `month-end-workstream`'s section Cash (every bank, card and loan account, plus the month's payments that are the firm-level items `BOOKS-RULES.md` names), AR billing and revenue (revenue and AR against the firm-billing period folder and the issued invoices, as this skill says), or Accruals and AP (AP, accrued expenses, reimbursable expenses, payroll liabilities where the firm has payroll), each also told to read this skill. Log before each dispatch and record each return at once with `accounting-month-end-record`.
6. [hand-off: accounting-reviewer] Review every entry, reconciliation and finding, told to use `month-end-workstream`'s section Review an item, with the files and sources only. Save its note as `reporting/REVIEW-{yyyy-mm}-{subject}.md` and record the verdict with `--review` and `--review-file`.
   → FAIL: step 5 (max 1)
7. [judgment] Walk the DONE checklist below, citing evidence per item; a FAIL that came back twice, and anything only the owner can settle, is a question in the report's numbered list.
   → an item other than 8 is not met: step 9
8. [hand-off: accounting-reviewer] Sign off: the reviewer on model fable, told to use `month-end-workstream`'s section Sign off the close, with the whole month folder and this skill's DONE checklist as the tests. Save and record its note as in step 6.
9. [judgment] Close. Update the period's and the root `STATUS.md` and write the session's `LOG.md` entry. Report the period and where it stands, the DONE checklist with evidence per item, the entries the owner must book (file, amount, account), the reviewer's verdicts, the firm-level items found, the Waiting on rows, and the questions as one numbered list the owner can answer "1) ok 2) no".
   → reported: done

## The folder

The Books folder follows the month-end layout (`<WORK>` is `BOOKS`): `BOOKS-PROCEDURES.md`, `BACKGROUND.md`, `SYSTEMS.md`, `METADATA_FIELDS.md` (the chart of accounts and classes), `STATUS.md`, and `{yyyy}/{yyyy-mm}/` per month with `STATUS.md`, `LOG.md`, `CONFIRMATIONS.md`, `journal-entries/`, `reconciliations/`, `reporting/`, `work/source/`. `BOOKS-RULES.md` (at the root) names the ledger in use, its export, the materiality and tolerance, and where the firm-billing folder and the bank statements are. It wins over this skill.

## The ledger export

The firm's ledger has no read API here. A person saves the period's general ledger and trial balance exports into `work/source/`, with `pulled.md` saying when and from which system. Read them through `gl-normalize` and `trial-balance`; otherwise read the CSV. An export older than the last booked entry is stale: say so, never work around it.

## What a firm's close adds

- **Revenue ties to billing.** Each month's revenue equals the firm-billing period's invoices (`firm-billing-workstream` folder: the lines files and the issued invoice files), by client and contract. A billed invoice not in the ledger, or ledger revenue with no invoice, is a finding. Unbilled work the billing run named is not revenue until invoiced unless the rules say accrue it.
- **AR ties to issued invoices less receipts**, client by client, aged.
- **Reimbursable expenses.** A client-reimbursable cost is billed through or is a receivable; one that was paid and never billed is a finding for the next billing run.
- **Firm-level items apart.** Items that belong to the owners or to the firm's tax position, not to its operations, go to the equity, due-from or tax accounts the rules name, never to operating expense. Which ones apply depends on the firm's legal form and jurisdiction; the rules list them. Examples: owner or partner draws and distributions, estimated or prepaid income tax payments, partner capital contributions, owner compensation booked differently from staff payroll, and personal costs paid by the firm.
- **Vendor information returns.** Where the firm's jurisdiction requires a year-end return on payments to contractors (in the US, Form 1099), each vendor paid this month carries its status in `METADATA_FIELDS.md`; an unknown status is a proposal, and the US year-end work is `vendor-1099-workstream`'s. Where no such return applies, the rules say so and this item is not applicable.
- **Independence.** In a small firm one person is often both preparer and approver. Where one person is both, the independent reviewer agent is the second pair of eyes: every entry and reconciliation needs the reviewer's PASS before it counts. Where the firm has a second person who approves, the reviewer's PASS still comes first.

## DONE checklist

The main agent checks each item against evidence it can cite; the reviewer confirms 2, 3 and 6.

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
