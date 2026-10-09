---
name: collections-workstream
description: Reference loaded by collections-analyst and collections-orchestrator, not for a user request; what collections work between closes adds to orchestration-workstream. Covers the O2C folder and O2C-RULES.md first, the aging read from the ERP never from memory, the AR register row (one per past-due invoice with an owner, a next action and a date), disputes, the internal nudge to the AR owner, the review agenda and the DONE checklist. To chase AR, start collections-orchestrator.
---

# Collections workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Read it at `~/.claude/skills/orchestration-workstream/SKILL.md` if it is not loaded. Billing completeness and the AR reconciliation are the close's method (`month-end-ar-billing-revenue`, with `month-end-reconciliation` and `erp-ledger-pull`); this skill adds only what order-to-cash between closes needs: every past-due invoice owned, worked and on the review agenda.

## Conduct here

- **The rules file first.** `O2C-RULES.md` in the O2C folder names the AR owner (a role), the age at which an invoice must be owned (default 60 days), the review's cadence and date, the collection policy documents, and what may be drafted to whom. It overrides this skill.
- **The aging from the ERP.** Read open AR from the ledger (`erp-ledger-pull`, `ar-ap-hygiene`), dated. A spreadsheet someone keeps is a source to compare, never the record.
- **Nothing to a customer.** No email, call note, credit memo, write-off, late fee or payment plan reaches a customer or the books from this work. A nudge goes to the AR owner, a colleague, as a draft the owner forwards or approves.
- **Policy is the owner's.** A late fee, interest, a write-off, a discount or an allowance change is a question with a recommendation and its support, never a decision.
- **Already done?** Before proposing a next action, look for what a person already did: a payment received after the aging date, a reply in the thread, a promise to pay, a dispute logged. Record it as the row's evidence.

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
    LOG.md  CONFIRMATIONS.md            the orchestrator only
```

Only the orchestrator writes `STATUS.md`, `LOG.md`, `CONFIRMATIONS.md` and `AR-REGISTER.csv`.

## The register row

`invoice, customer, invoice_date, due_date, days_past_due, open_amount, owner, next_action, action_date, state, dispute, evidence, updated`

- `owner` is a person by role (`AR owner`, `account lead`), never blank for a row past the age.
- `next_action` starts with a verb and names who does what ("Call AP at the customer about the short pay"); `action_date` is yyyy-mm-dd.
- `state` is one of `new`, `working`, `promised`, `disputed`, `escalated`, `paid`, `written-off` (the last only on a person's evidence).
- `dispute` is empty or one line: what the customer disputes and the amount.
- `evidence` cites the source: the aging pull's file and line, a `portal://email/<id>`, a payment in the ledger pull.

## The return here

The shared block with these item tests and states, and the proposed register rows in `extra.register`:

| Test | Item | States |
|---|---|---|
| `aging` | an invoice number | `owned`, `unowned`, `paid`, `disputed` |
| `billing` | a customer and fee type | `billed`, `missing`, `off`, `duplicate` |
| `nudge` | a customer | `drafted`, `not-needed` |

`questions` go to a role (`AR owner`, `controller`, `owner`) with `why` and `blocks`.

## DONE (the orchestrator checks each item and cites its evidence)

1. The aging pull is dated within two days of the review and saved in `work/source/`.
2. Every invoice past the rules' age has a register row with an owner, a verb-first next action and a date in the future or today.
3. Every dispute has a state, an amount and the evidence that it is disputed.
4. Billing completeness for the last closed month is checked, or the close already proved it (cite `reporting/billing-completeness-{yyyy-mm}.md`).
5. `AGENDA.md` is written: totals by aging bucket, the movers since the last review, the rows that need a decision, and each decision as a numbered question.
6. Every figure in the agenda ties to the aging pull: the checker (`numbers-reviewer`) says PASS.
7. Each nudge is internal, names the invoices it covers, and promises nothing on the owner's behalf.
8. Every question is on the owner's list (comms-confirm) or in the report's numbered list.

## Later tools

- `ar-aging-check`: compute DONE items 1 to 3 and 5 from the folder and the pull; `--precheck` says WORK when the aging moved since the last review.
- `collections-record`: the one writer of `AR-REGISTER.csv`, by invoice, with history.
