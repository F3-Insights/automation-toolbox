---
name: collections-workstream
description: "The job skill of accounting-collections-review, not for a user request: order-to-cash between closes for one company, before each AR and collections review. Covers the O2C folder and O2C-RULES.md first, the Steps, the aging read from the ERP never from memory, section Work the aging (one AR register row per past-due invoice with an owner, a next action and a date), disputes, the internal nudge to the AR owner, the review agenda and the DONE checklist. Billing completeness is month-end-workstream's AR, billing and revenue section. To chase AR, start accounting-collections-review. Not for billing the firm's own clients; use accounting-firm-billing."
---

# Collections

Every past-due invoice owned, worked and dated, the disputes known, billing proven complete, and the decisions only the owner can make written as one numbered list, before each AR and collections review. `orchestration-workstream` is the conduct and return block. Billing completeness and the AR reconciliation are the close's method (`month-end-workstream`, section AR, billing and revenue, with `month-end-reconciliation` and `erp-ledger-pull`); this skill adds only what order-to-cash between closes needs.

## Conduct

- **The rules file first.** `O2C-RULES.md` in the O2C folder names the AR owner (a role), the age at which an invoice must be owned (default 60 days), the review's cadence and date, the collection policy documents, the Month-End folder billing completeness is proved in, and what may be drafted to whom. It overrides this skill.
- **The aging from the ERP.** Read open AR from the ledger (`erp-ledger-pull`: `intacct-snapshot`, then `ar-ap-hygiene`), dated. A spreadsheet someone keeps is a source to compare, never the record.
- **Nothing to a customer.** No email, call note, credit memo, write-off, late fee or payment plan reaches a customer or the books from this work. A nudge goes to the AR owner, a colleague, as a draft the owner forwards or approves.
- **Policy is the owner's.** A late fee, interest, a write-off, a discount or an allowance change is a question with a recommendation and its support, never a decision.
- **Already done?** Before proposing a next action, look for what a person already did: a payment received after the aging date, a reply in the thread, a promise to pay, a dispute logged. Record it as the row's evidence.
- **Roles, not names.** No employee is named in the agenda.

## Steps

The main agent (`accounting-collections-review`) runs these. On a dry run the review folder is built inside the Run folder, nothing is written in the O2C folder and nothing goes through `confirm`.

1. [judgment] Orient. `whoami`; read `O2C-RULES.md`, `BACKGROUND.md`, `STATUS.md`, `AR-REGISTER.csv`, and the last review's `AGENDA.md` and `CONFIRMATIONS.md`. Each answered question is input. Set the review date (default the next one in the rules).
2. [judgment] Set up `reviews/<date>/` with `LOG.md` (`mkdir -p` for its folders); log before each step that writes and record each result at once.
3. [script] Pull the dated aging with `intacct-snapshot --period <yyyy-mm> --out reviews/<date>/work/source --live`, then run `ar-ap-hygiene --snap <that folder> --month <yyyy-mm> --as-of <review date>`.
   → the pull fails: stop
4. [judgment] Work the aging (section Work the aging) yourself: every invoice past the rules' age gets a proposed register row, with the movers since the last review and the nudge drafts.
5. [hand-off: accounting-worker] Billing completeness for the last closed month, only when the close has not already proved it (no `reporting/billing-completeness-{yyyy-mm}.md` in the Month-End folder the rules name): the worker follows `month-end-workstream`, section AR, billing and revenue, for billing completeness only, model opus, writing its table to `reviews/<date>/billing-completeness.md`.
6. [judgment] Record. Write the rows into `AR-REGISTER.csv` (one row per invoice; an earlier row's history is kept in `updated`, never overwritten), the nudges under `reviews/<date>/nudges/`, and the questions in `CONFIRMATIONS.md`. Write `AGENDA.md` (below).
7. [hand-off: accounting-reviewer] Check the numbers (`review-numbers`), with `AGENDA.md`, `AR-REGISTER.csv` and the aging pull only, never your reasoning. Save its note as `reviews/<date>/review.md`.
   → FAIL: step 4 (max 1)
   → FAIL again: step 8
8. [judgment] Ask. Each decision only the owner or the AR owner can make goes on the owner's list through `confirm`, one question per decision; a second review FAIL is one of them.
9. [judgment] Close. Walk the DONE checklist into `reviews/<date>/done.md`, citing the evidence for each item, update `STATUS.md`, and report: the review folder, invoices past the age by state, the total past due by bucket against the last review, the disputes, the nudges drafted, the reviewer's verdict and the questions as one numbered list the owner can answer "1) ok 2) no".
   → reported: done

## The O2C folder

```
<O2C folder>/
  O2C-RULES.md  BACKGROUND.md  STATUS.md
  AR-REGISTER.csv                       one row per invoice past the rules' age, kept across reviews
  reviews/<yyyy-mm-dd>/                 one folder per review meeting
    work/source/                        the dated aging and hygiene pulls
    AGENDA.md                           the review agenda
    nudges/<customer>.md                internal nudge drafts to the AR owner
    billing-completeness.md             when the review covers a month's billing
    review.md  done.md  LOG.md  CONFIRMATIONS.md
```

Only the main agent writes `STATUS.md`, `LOG.md`, `CONFIRMATIONS.md`, `AR-REGISTER.csv` and the review note.

## Work the aging

Run by the main agent itself: the aging is one slice. The goal: every invoice past the age in `O2C-RULES.md` has a register row a person can act on without opening anything else, and every row rests on evidence.

1. For each invoice past the age: check the ledger for payment since the aging date (`intacct-gl-detail` on the AR and cash accounts, or `trial-balance` for the balance), the mail and Portal for the customer's last word (`search`, `get`, `email_bodies`), and the register for its history. Decide its state, owner, next action and date.
2. List what moved since the last review: new past-due invoices, paid ones, ones that aged into a new bucket.
3. Draft one internal nudge per customer that needs the AR owner to act, `reviews/<date>/nudges/<customer>.md`: the invoices, the amounts, what the record shows, the action asked. Nothing addressed to the customer.

## The register row

`invoice, customer, invoice_date, due_date, days_past_due, open_amount, owner, next_action, action_date, state, dispute, evidence, updated`

- `owner` is a person by role (`AR owner`, `account lead`), never blank for a row past the age.
- `next_action` starts with a verb and names who does what ("Call AP at the customer about the short pay"); `action_date` is yyyy-mm-dd.
- `state` is one of `new`, `working`, `promised`, `disputed`, `escalated`, `paid`, `written-off` (the last only on a person's evidence).
- `dispute` is empty or one line: what the customer disputes and the amount.
- `evidence` cites the source: the aging pull's file and line, a `portal://email/<id>`, a payment in the ledger pull.

## The agenda

`AGENDA.md`: totals by aging bucket against the last review, the movers since the last review, the disputes, the rows that need a decision, billing completeness (the worker's table, or the close's file cited), and each decision as a numbered question with a recommendation and its support. Every figure ties to the aging pull.

## DONE (the main agent checks each item and cites its evidence)

1. The aging pull is dated within two days of the review and saved in `work/source/`.
2. Every invoice past the rules' age has a register row with an owner, a verb-first next action and a date in the future or today.
3. Every dispute has a state, an amount and the evidence that it is disputed.
4. Billing completeness for the last closed month is checked, or the close already proved it (cite `reporting/billing-completeness-{yyyy-mm}.md`).
5. `AGENDA.md` is written: totals by aging bucket, the movers, the rows that need a decision, and each decision as a numbered question.
6. Every figure in the agenda ties to the aging pull: `accounting-reviewer` with `review-numbers` says PASS.
7. Each nudge is internal, names the invoices it covers, and promises nothing on the owner's behalf.
8. Every question is on the owner's list (`confirm`) or in the report's numbered list.

Items 2, 3 and 6 rest on the reviewer's PASS, not the main agent's reading.

## Later tools

- `ar-aging-check`: compute DONE items 1 to 3 and 5 from the folder and the pull; `--precheck` says WORK when the aging moved since the last review.
- `collections-record`: the one writer of `AR-REGISTER.csv`, by invoice, with history.
