---
name: month-end-workstream
description: "Reference loaded by accounting-worker and accounting-reviewer for a close's work, not for a user request; adds to orchestration-workstream. Covers the rules file first, \"already done?\" from the ledger pull and the folder, never editing an import file, the return block the main agent records with accounting-month-end-record, the worker sections Cash, AR billing and revenue, and Accruals and AP, and the reviewer checklists Review an item and Sign off the close. Briefed by accounting-month-end-close, accounting-firm-books-close, accounting-intercompany-reconciliation and accounting-collections-review. To run a close, start accounting-month-end-close."
---

# Working as a month-end workstream

This skill extends `orchestration-workstream`: follow its conduct and return its block. Load it with the Skill tool if it is not loaded. What follows is only what a month-end close adds.

A workstream owns a set of checklist rows and balance-sheet accounts for one month, assigned by the main agent from `MONTH-END-PROCEDURES-{yyyy-mm}.md`. It does the work or proves that a person did.

## Conduct in a close

- **Read the rules first.** `MONTH-END-RULES.md` says what you may do and the thresholds and tolerances you work to. It overrides your own instructions.
- **Already done?** Check every row and account from the ledger pull and the folder. A person's evidence is a JE number or a file.
- **Check a tool's output against its source before it counts.** A script's or command's result is a claim. Tie its totals to the source, trace a sample of its rows to the source columns and the maps it used, and carry every gap it reports into your return, not just the first. A figure you did not tie is reported as not tied.
- **Import files.** Never edit an import file after it is written; a correction is a new file.
- **No bookkeeping.** The state you never write is `STATUS.md`, `LOG.md`, the procedures copy and the evidence file.

## The return in a close

The shared block, with `period` (yyyy-mm) and `pull_date` (the ledger pull you used, yyyy-mm-dd) beside `workstream` at the top, and each finding naming its `account`:

```json
{
  "workstream": "cash",
  "period": "2026-09",
  "pull_date": "2026-10-05",
  "items": [
    {"test": "reconciliations", "item": "1010", "state": "reconciled",
     "evidence": "reconciliations/1010 Operating checking recon 2026-09.xlsx",
     "amount": 125400.00, "note": "GL equals statement; 3 outstanding checks, all cleared 10/2"},
    {"test": "entries", "item": "cc-accrual", "state": "drafted",
     "evidence": "journal-entries/(ACME) GL upload - September 2026 card accrual (reversing) DRAFT.csv",
     "amount": 4210.50, "note": "lint PASS; 2 unmapped merchants coded to 6999"},
    {"test": "entries", "item": "payroll-accrual", "state": "booked",
     "evidence": "JE 1234", "amount": 32500.00, "note": "booked by a person; agrees to the register"}
  ],
  "rows": [
    {"task": "Reconcile the bank accounts", "status": "done", "evidence": "reconciliations/"}
  ],
  "files": ["reconciliations/1010 Operating checking recon 2026-09.xlsx"],
  "findings": [
    {"account": "1050", "amount": -100000.00, "text": "Money market down 100k on the month; transfer to operating checking, matched on both statements"}
  ],
  "questions": [
    {"ask": "Can the September statement for account 1020 be saved to the 2026-09 folder?",
     "of": "controller", "why": "No statement in the folder; the reconciliation cannot tie", "blocks": ["reconciliations:1020"]}
  ],
  "proposals": [
    {"document": "METADATA_FIELDS.md", "change": "Map merchant NEWCO SOFTWARE to 6120 Software",
     "source": "card report line 14; coded the same way in July and August"}
  ],
  "notes": [],
  "extra": {}
}
```

- `items` are the evidence rows the main agent records with `accounting-month-end-record`:
  - `test` is one of entries, reconciliations, flux or questions;
  - `state` is one of open, waiting, drafted, booked, reconciled, explained, answered or not-needed (drafted and booked belong to entries, reconciled to reconciliations, explained to flux, answered to questions; the rest fit any test);
  - `amount` is the GL balance a reconciliation tied to, or an entry's total debits;
  - an account range from the procedures table uses the table's Account text as its `item`.
- `rows` are the checklist rows you were assigned, by their Task text, with status open, waiting or done.

## Cash

For an `accounting-worker` given the folder, the period and the cash accounts assigned (the root `MONTH-END-PROCEDURES.md` says which accounts are Cash's). The goal: a GL balance for every cash account that agrees with the bank's statement to the cent, every reconciling item explained, and a cash movement that makes sense. Commands: `accounting-cash-walk`, `trial-balance`, `intacct-gl-detail`, `gl-normalize`, `accounting-je-import`, `accounting-je-import-check`, `excel-handle`, `pdf-handle`. Skills: `month-end-reconciliation`, `month-end-journal-entry`, `erp-ledger-pull`.

- **Bank reconciliations**, with `month-end-reconciliation`, one per account. The GL balance comes from the ledger pull; the statement balance from the statement where `SYSTEMS.md` says statements land. List the outstanding items (deposits in transit, uncleared payments) with dates, and say which cleared in the first days of the next month when that statement is available. A missing statement is a question for the person `BACKGROUND.md` names.
- **Payment processors and sweeps.** Tie each clearing account (card processor, payment portal, sweep or money-market account) to its own report. Look for deposits recorded twice, or never recorded, across the processor and the bank.
- **Cash movement.** Run `accounting-cash-walk` over the month's lines. Explain every material movement (the floor in `MONTH-END-RULES.md`) by its offset account, and flag anything unclassified or unusual: a large transfer, a payment to a new party, a round amount.
- **Debt and leases.** Agree each loan and lease balance to its schedule or statement, with interest and the current portion right. Draft a correcting entry only with backup, through `month-end-journal-entry`.

An unexplained cash difference is never plugged: it is a finding and a question. Each reconciliation's `amount` is the GL balance it tied to. Return the block above with `workstream: "cash"`.

## AR, billing and revenue

For an `accounting-worker` given the folder, the period and the rows and accounts assigned. Also briefed by `accounting-firm-books-close` (revenue and AR against the firm's billing, beside `firm-books-workstream`) and by `accounting-collections-review` for billing completeness only. The goal: every customer billed for everything it owes for the month and nothing billed twice, revenue recognized in the right period at the right amount, deferred revenue, customer deposits and AR right, the allowance supported. `BACKGROUND.md` and `METADATA_FIELDS.md` say how the company earns revenue. Commands: `ar-ap-hygiene`, `trial-balance`, `intacct-gl-detail`, `intacct-snapshot`, `gl-normalize`, `accounting-je-import`, `accounting-je-import-check`, `excel-handle`, `pdf-handle`. Skills: `month-end-reconciliation`, `month-end-journal-entry`, `erp-ledger-pull`.

- **Billing completeness.** Build the expected bill for the month, customer by customer and fee type by fee type, from the contracts, rate sheets and master files the folder names, the activity that drives usage fees (units shipped, hours, pass-through costs) and the prior three months' invoices. Compare it with what was invoiced (the AR invoice lines in the ledger pull, or the sales orders before they convert). List each customer or fee missing, each amount off its expected value beyond the threshold, each new or ended customer, and each invoice that looks duplicated. Save the table as `reporting/billing-completeness-{yyyy-mm}.md` (customer, fee type, expected, billed, difference, source), list it in `files`, and return a `rows` entry for "Prove billing complete". Billing early in the close is a person's act: the list goes to the person who bills, through the main agent, before the sales orders convert when the timing allows.
- **Revenue recognition and cut-off.** Each revenue line is earned in the month, pass-through amounts are treated as the company's policy says, and one-time fees (setup, tooling, onboarding) follow their contract terms. A judgment under ASC 606 not already settled in the folder is a question with your recommendation, never a decision.
- **Deferred revenue and deposits.** Roll each balance forward (opening, plus billed in advance, less earned, equals closing), tie it to its schedule, and draft any reclass through `month-end-journal-entry`.
- **AR and the allowance.** Reconcile AR (intercompany included) to the aging with `month-end-reconciliation`. Run `ar-ap-hygiene` for unapplied cash, credits, stale and silent customers. Check the allowance against the aging and the collection history; propose a change as a question with its support.
- **Revenue flux.** Explain the month's revenue against budget or forecast and the prior month, by customer and fee type, above the thresholds, as findings.

Never send an invoice or email a customer. A missing fee is a question to the person who bills, naming the customer, the fee and the amount expected. Return the block above with `workstream: "ar-billing-revenue"`.

## Accruals and AP

For an `accounting-worker` given the folder, the period and the rows and accounts assigned. The goal: the right liability on every account assigned (what the company owes but has not been billed for, and what it was billed for but has not paid), every entry drafted and backed up, every account reconciled. Commands: `accounting-accruals`, `accounting-card-export`, `accounting-cc-accrual`, `accounting-service-period-accrual`, `accounting-recurring-je-scan`, `accounting-je-import`, `accounting-je-import-check`, `trial-balance`, `intacct-gl-detail`, `gl-normalize`, `excel-handle`. Skills: `month-end-accrual-drafts`, `month-end-journal-entry`, `month-end-reconciliation`, `erp-ledger-pull`.

- **Card accrual and post-cutoff vendor accrual.** Use `month-end-accrual-drafts` (`accounting-accruals config`, `done`, `build`). It reads the folder's maps, writes the import file (STATE Posted) and its backup into `journal-entries/`, and counts a file already there as done. Add your judgment to the backup it wrote, and return its questions rather than asking them.
- **Check the build against the source before you report it.** The draft's total ties to the card report's rows for the period, summed from the report itself, not the script's CSV; each row's department and account trace to the export's department column, the label map, the people map and the card account map (a sample in `card-coding-<yyyy-mm>.csv` covering every department source); every gap in `department_reconciliation` and the queues goes into the return, not just the first. A card draft whose `ready` is false is `drafted` with its gaps as questions and proposals, never reported as clean.
- **The missing-accrual scan, on every vendor accrual run.** Decide each flagged vendor, accrue or not, with a reason grounded in its evidence (months seen, typical amount, last month seen, what was searched), write the decisions file and rebuild with `--decisions` (`rules.md` in `month-end-accrual-drafts`). The return lists every flagged vendor with its typical amount, evidence and decision, and the excluded vendors with their reasons; a vendor you cannot decide is a question, never silently dropped.
- **Other recurring accruals** on the checklist or the standard-entry list (board fees, bonuses, benefits): check the ledger pull and the prior months for the pattern (`accounting-recurring-je-scan`), then draft with `month-end-journal-entry`.
- **Payroll accrual.** A person calculates and posts it. Verify it is in the ledger and reasonable against the payroll register and prior months; draft it only when the brief says the person asked.
- **Reconciliations** of accrued expenses, AP and the payroll-related liabilities, with `month-end-reconciliation`: roll forward the company's own workbook where `SYSTEMS.md` or the prior month names one, and check each accrual reversed on the 1st and was replaced by the actual bill.
- **Overlaps.** Before any accrual, look for the same cost already accrued by someone else, or already billed into the period. An overlap is a question, never a correction.

Return the block above with `workstream: "accruals"`.

## Review an item

The checklist for `accounting-reviewer`, given the folder, the period and the items to review with their sources (never the worker's reasoning; set any aside and say so). `MONTH-END-RULES.md`'s tolerances, thresholds and definition of done are the standard. Commands: `accounting-je-import-check`, `trial-balance` (never with `--out`), `report-tieout`, `excel-handle`.

- **A journal entry** (import file plus backup):
  - Ties: debits equal credits, each amount re-derives from the backup, `accounting-je-import-check` passes.
  - Coding: accounts and dimensions are valid and follow `METADATA_FIELDS.md`.
  - Dates: the date and the reversal date are right for the period.
  - Description and duplicates: the description says what and why; nothing duplicates an entry already in the ledger pull.
  - Authority: STATE is the one the rules require (Posted for an import file a person uploads, since that upload is the human review).
- **A reconciliation:**
  - Ties: the GL balance equals the ledger pull's trial balance for that account and date; the support balance equals its source document; the difference is zero or within tolerance.
  - Reconciling items: each is real, dated, explained, and not stale beyond the rules' limit.
  - Roll-forward: it continues from last month's reconciliation.
- **A finding or the flux:** every figure re-derives from the trial balance or GL detail, and every variance above the thresholds is explained or listed.

Every FAIL names its fix: the file, the location, the figure found, the figure expected and the source. Edit nothing; the main agent saves your note as `reporting/REVIEW-{yyyy-mm}-{subject}.md`. Return a short note for a person, then one fenced `json` block:

```json
{"review_note": "reporting/REVIEW-2026-09-cash.md",
 "items": [{"test": "reconciliations", "item": "1010", "review": "PASS", "fixes": []},
           {"test": "entries", "item": "cc-accrual", "review": "FAIL",
            "fixes": ["Line 7: 6110 Travel should be 5110 Travel - COGS for PRODUCTION (METADATA_FIELDS.md card map)"]}],
 "close": null,
 "noticed": ["Anything outside the brief the main agent should know"]}
```

`review_note` is the file name the note should be saved under; `item` and `test` are as the worker returned them.

## Sign off the close

The checklist for `accounting-reviewer` on model fable, given the whole month folder once `accounting-month-end-check` shows every test met. Check each of the four tests of done (`month-end-close`) against the evidence: run `accounting-month-end-check FOLDER --period P --format json` yourself, open a sample of the evidence each test rests on (the import files against the pull, the reconciliations against the trial balance, the findings against the flux, the Waiting on table against `CONFIRMATIONS.md`), and say what is missing. Return the block of Review an item with `close` set to `{"met": true|false, "tests": {"entries": "...", "reconciliations": "...", "flux": "...", "questions": "..."}}`.
