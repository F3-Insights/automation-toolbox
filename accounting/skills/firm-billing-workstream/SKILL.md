---
name: firm-billing-workstream
description: "The job skill of accounting-firm-billing, and the sections its accounting-worker and accounting-reviewer follow, not for a user request. A small professional-services firm's monthly client billing: every billable contract gets a draft invoice tied line by line to its rate basis in BILLING.yaml, independently re-derived, with its cover email as a file, or the owner question that says why not. Done is computed by accounting-firm-billing-check. Covers the Steps, the folder, Prepare contracts, Check a draft invoice, Sign off the period and the cover email. To bill the month, start accounting-firm-billing. Not for collecting AR; use accounting-collections-review."
---

# Firm billing

Firm billing is for a small professional-services firm billing its own clients: a consultancy, an advisory or accounting practice, a design or engineering studio. It drafts the invoices those clients owe for a month. A draft is good when the owner could send it after one read: every line names its rate basis in `BILLING.yaml`, every amount re-derives from that basis and the pull, the months it covers are the months owed, and nothing on it is invented. Nothing is ever sent and nothing is posted to any books; the owner issues the invoice and assigns its number.

`orchestration-workstream` is the conduct and the return block every section below keeps. The files, formats and every command's options are in `BILLING.md` beside this file; read it before the first command. `BILLING-RULES.md` in the billing folder overrides this skill and any brief.

## Steps

The main agent (`accounting-firm-billing`) runs these. The billing pull was computed before the session by the Automation's prepare step (`accounting-firm-billing-pull`); its first line, `FRESH` or `STALE`, is in the inputs. On a dry run the period folder is under the Run folder: pass `--period-dir` on every command, ask nothing through `confirm` (list the questions instead) and write nothing in the billing folder.

1. [script] Run `accounting-firm-billing-check FOLDER --period P --format json` to see which of the five tests are open.
   → every test met and the period signed off: step 10
2. [judgment] Orient. Read `BILLING-RULES.md`, `BILLING.yaml`, the root and period `STATUS.md`, the last `LOG.md` entries and `CONFIRMATIONS.md`; an answered question is input to this Run. Read the pull: the billable contracts, their unbilled months, warnings, issued invoices found and uncontracted work. STALE means work from what is there and say so.
   → BILLING.yaml cannot be read or names no contract: stop
3. [judgment] Plan. The contracts without a final row, and the drafts whose review is missing or FAIL, in batches of one to three contracts. Skip what is already recorded and still verifies. Write a `LOG.md` line per batch before dispatching it.
   → nothing open: step 7
4. [hand-off: accounting-worker] Prepare each batch (section Prepare contracts, model opus), in parallel, briefed with the billing folder, the period folder, the period, its contract ids, the engagement folders BILLING.yaml names for each, the owner's earlier answers and any reviewer fixes; never your own view of the answer.
5. [script] Record each return at once, contract by contract, with `accounting-firm-billing-record FOLDER --period P --contract ID --state S` and `--draft`, `--rate-basis`, `--months`, `--evidence` and `--note` as the row needs. A question goes through `confirm new` into the period's `CONFIRMATIONS.md`, then on the row with `--question`. Findings go in the period `STATUS.md`.
6. [hand-off: accounting-reviewer] Check each new draft (section Check a draft invoice), with the draft files, BILLING.yaml, the pull and the evidence files only. Write the reviewer's note as `review/<contract> <yyyy-mm> review.md` yourself (the reviewer writes nothing), then record it with `accounting-firm-billing-record ... --review PASS|FAIL --review-file F`.
   → FAIL: step 4 (max 2)
   → FAIL a third time: step 8
7. [script] Run `accounting-firm-billing-check FOLDER --period P --format json` again.
   → every test met: step 9
8. [judgment] Questions. One per contract, only what the folder, the engagement and the Portal cannot answer (terms to confirm, hours that look wrong, a milestone not evidenced, a client with work and no contract, months unbilled for a reason only the owner knows), through `confirm`, recorded in `CONFIRMATIONS.md`. A contract whose draft failed review three times becomes one of these questions. Then carry on.
   → asked: step 10
9. [hand-off: accounting-reviewer] Sign off the period (section Sign off the period, model fable), with the whole period folder, BILLING.yaml and the pull. Write its note as `review/period <yyyy-mm> sign-off.md`.
   → FAIL: step 3 (max 1)
10. [script] Close. Update the period and root `STATUS.md` (each contract's outcome and total, unbilled months, what waits on the owner; changes BILLING.yaml needs as proposals), write the session's `LOG.md` entry, and run `accounting-firm-billing-check FOLDER --period P` last. Report its verdict, never your own.
    → reported: done

## The folder

| Where | Holds | Writer |
|---|---|---|
| `BILLING-RULES.md` | Authority, thresholds, done, how questions are asked | the owner |
| `BILLING.yaml` | Settings, the invoice header, one entry per contract with its rate basis | the owner |
| `STATUS.md` | Where billing stands across periods, what waits on whom, the next action | the main agent |
| `{yyyy}/{yyyy-mm}/STATUS.md`, `LOG.md`, `CONFIRMATIONS.md` | The period's state, log and questions | the main agent |
| `{yyyy}/{yyyy-mm}/BILLING-EVIDENCE-{yyyy-mm}.csv` | One row per contract | `accounting-firm-billing-record`, run by the main agent |
| `{yyyy}/{yyyy-mm}/work/source/billing-pull.json` | The pull: expected lines, hours, issued invoices, unbilled months | `accounting-firm-billing-pull`, before the session |
| `{yyyy}/{yyyy-mm}/work/lines/`, `invoices/` | Lines files, drafts, cover emails | the worker (drafts through `accounting-firm-billing-draft`) |
| `{yyyy}/{yyyy-mm}/review/` | The review notes | the main agent, from the reviewer's return |

Only the main agent writes the STATUS files, LOG, CONFIRMATIONS and the evidence file. A worker writes only lines files, drafts (through the command) and cover emails.

## Done is computed

`accounting-firm-billing-check FOLDER --period P --format json` computes the five tests from the files, so done is never an agent's opinion:

1. **pull**: the period's billing pull exists and was computed from the current BILLING.yaml.
2. **contracts**: every billable contract, and every contract with unbilled months, has a row in a final state (drafted, already-billed, not-billable or question).
3. **drafts**: every drafted invoice verifies against its rate basis and the pull and totals to the recorded amount; earlier owed months are on it or named in the note.
4. **review**: every drafted invoice is PASS on its current content.
5. **reasons**: every row not drafted has its reason, every question row its question, and every draft on unconfirmed terms the question that confirms them.

Run it first and last. With `--precheck` it is the Automation's precheck.

## Billing bases

Each contract in `BILLING.yaml` combines whichever of these bases the firm agreed with that client; none is assumed. Every basis maps to one rate `kind` the tools check:

| Basis | Rate `kind` | What bills it |
|---|---|---|
| Fixed fee, recurring (a monthly or quarterly flat fee) | `retainer` | the amount, once per period the cadence bills |
| Fixed fee, one-off (a project price, or one instalment of it) | `milestone` | the amount, once the evidence shows it is due |
| Retainer (a flat fee for a block of availability or hours) | `retainer`, plus `hourly` for any overage | the amount; overage hours from the time records |
| Hourly or daily (time and materials) | `hourly` (a day rate is an hourly rate with days as the quantity) | the time records' hours times the rate, to any cap |
| Milestone (a payment tied to a deliverable or an acceptance) | `milestone` | the amount, once the evidence shows it was met |
| Pass-through (expenses, subcontractors, licences at cost or marked up) | `pass-through` | the receipt or expense report on file |

A firm that bills no time leaves the time records out; one that bills no milestones has none.

## Conduct

- **The rules first.** `BILLING.yaml` is the only source of rates, amounts, bill-to and terms. If the contract file it names disagrees with it, that is a question, never a correction.
- **Already done?** The pull lists the issued invoices it found (`invoices_since_period_start`, `last_invoice`). An issued invoice that covers the period means `already-billed` with the file as evidence. Look in the folders BILLING.yaml names before concluding a month is unbilled.
- **Hours come from the pull.** Hourly lines use the hours the pull computed from the time records for that month and client key. When the pull warns it is short of the month, or the hours look wrong against the engagement's record, draft with the pull's hours and ask, or ask before drafting; never adjust them. An `override_reason` must point to the owner's answer.
- **Milestones and pass-through need evidence.** A milestone is billed only when a file in the engagement's folders (the ones BILLING.yaml names) or the Insights Portal shows it was met: a delivered readout, an acceptance email. A pass-through is billed only from a receipt or an expense report on file. No evidence: `question` or `not-billable`, with the reason.
- **Unbilled months.** When the pull shows months owed before the period, draft one invoice covering them all (`months` in the lines file), or say in the note why not (a hold the owner placed, a dispute). Never let an owed month drop silently.
- **Unconfirmed terms.** A contract with `confirmed: false` is still drafted, and its row carries the question that asks the owner to confirm the terms.

## Prepare contracts

For an `accounting-worker` given one to three contracts. The outcome for each is one of four: a draft invoice tied line by line to its rate basis, the issued invoice that already covers the month, the reason nothing is owed, or the one question only the owner can answer. Read `BILLING-RULES.md` and `BILLING.yaml` first, then `work/source/billing-pull.json` in the period folder, and keep Conduct above. You may run only `accounting-firm-billing-draft` (with `--period-dir` when the brief says dry run) and `mkdir -p`; write only lines files and cover emails.

For each contract:

1. **Already billed?** The pull's `invoices_since_period_start` and the invoice folders. An issued invoice for the period ends it: `already-billed` with the file.
2. **Owed?** The pull's `billable`, `why`, `unbilled_months` and `warnings` are the start, not the end. For a milestone, find the evidence it was met in the engagement's folders (those the brief names) or the Portal; for pass-through, the receipts. A PO required and missing, a milestone not met, a paused engagement: `not-billable` with the reason, or `question` when only the owner knows.
3. **Draft.** Write `work/lines/<contract>.json` from the pull's `expected` lines for every owed month, adding the milestone and pass-through lines you have evidence for, with descriptions a client's payables clerk understands. Run `accounting-firm-billing-draft FOLDER --period P --contract ID --lines FILE`. A `REFUSED` line names what to fix; fix the lines, never the numbers' source. Two refusals you cannot fix: a question.
4. **Cover email.** Write the cover email file (below), then apply `unslop-email` to it.

Hours that look wrong against the engagement's record, terms that disagree with the contract file, a client with work and no contract: questions, each with why it matters and the contract it blocks. Never adjust a rate, an amount or the hours.

Return the `orchestration-workstream` block with `workstream: "firm-billing"`: one `items` entry per contract (table below), `files` the lines files, drafts and cover emails, `questions` (each naming `contract:<id>` in `blocks`), and `extra` as `{"rate_basis": {"<contract>": ["retainer", "hours"]}, "months": {"<contract>": ["2026-08", "2026-09"]}}`.

| Field | Value |
|---|---|
| `test` | `contract` |
| `item` | the contract id |
| `state` | `drafted`, `already-billed`, `not-billable` or `question` |
| `evidence` | the draft JSON (drafted), the issued invoice file (already-billed), the file or reference that decides it |
| `amount` | the draft's total, or null |
| `note` | the reason for anything not drafted, and any earlier owed month left out |

## Check a draft invoice

The checklist for `accounting-reviewer`, per contract, from the draft, BILLING.yaml, the pull and the evidence files alone. Read `BILLING-RULES.md` first.

1. `accounting-firm-billing-draft --verify <draft json>` passes. A refusal is a FAIL with its line.
2. The months billed are the months owed: every month in the pull's `unbilled_months` is on the draft or the reason it is not is on record; no month is billed twice against the issued invoices the pull found.
3. Each milestone and pass-through line's evidence file exists and shows what the line claims (the milestone met, the receipt's amount and date).
4. The bill-to, terms, due date and PO match BILLING.yaml; the header says DRAFT and the number is a proposal.
5. The cover email names the same total, months and due date as the invoice, promises nothing the invoice does not, and carries no sales language.

Return a short summary, then the `orchestration-workstream` block with `workstream: "firm-billing-review"`: one `items` entry per contract with `state` `PASS` or `FAIL`, `evidence` the draft reviewed, `amount` the total you re-derived, and the numbered fixes in `note`; `extra.content_sha256` (per contract, the draft's `content_sha256` you reviewed) and `extra.review_notes` (per contract, the note's full text: the verdict, each check's result and, for a FAIL, the fixes), which the main agent saves as the review file.

## Sign off the period

For `accounting-reviewer` on model fable, all contracts at once, once the check shows every test met: walk Check a draft invoice over every drafted contract whose review is older than its draft, then give a period-level verdict: every billable contract and every contract with unbilled months is drafted, already billed or carries its reason; every uncontracted client key has a row; the grand total equals the sum of the drafts. Return the same block with one extra `items` entry, `test` `period`, `item` the period, `state` `PASS` or `FAIL`, and the note text in `extra.review_notes.period`.

## The cover email

A short note in the owner's voice to the bill-to contact: the invoice attached, the months it covers, the total, the due date, one line of thanks. No sales language, nothing the invoice does not say. It is a file, `invoices/<contract> <yyyy-mm> cover email DRAFT.md`, with `To:`, `Subject:` and the body. It reaches the drafts folder of the owner's mail client (for example Outlook) only through `accounting-firm-billing-deliver` in the Automation's finish step, after the session, and only where BILLING.yaml says `email_delivery: outlook-drafts` and a reply thread is pinned. Otherwise the file is the delivery, and the owner sends it from whatever mail client they use.

## Authority

You may read BILLING.yaml, the pull, the engagement folders and the Portal, have drafts written in the period folder and ask the owner through `confirm`. Never send anything, post to any accounting system, assign a final invoice number, change BILLING.yaml or the rules (changes are proposals in the root STATUS), or edit an issued invoice. Never run `accounting-firm-billing-deliver` in a session.

## Report

End with `for_owner`: the period, each contract's outcome and total, the grand total drafted, the months found unbilled, the questions waiting on the owner, and the check's verdict, in under fifteen lines. `artifacts`: the draft invoices, the cover emails and the period STATUS.
