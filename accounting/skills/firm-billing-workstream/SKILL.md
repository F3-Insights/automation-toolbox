---
name: firm-billing-workstream
description: Reference loaded by firm-billing-preparer and firm-billing-reviewer, not for a user request; adds to orchestration-workstream. Covers BILLING-RULES.md and BILLING.yaml first, the pull's expected lines per contract, the lines file firm-billing-draft takes, the states the orchestrator records with firm-billing-record, and what makes a cover email draft. To bill the month, start firm-billing-orchestrator. Read it when writing or changing either agent.
---

# Firm billing workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Read it at `~/.claude/skills/orchestration-workstream/SKILL.md` if it is not loaded. The files, formats and commands are in `BILLING.md` beside this file; read it before your first command.

Firm billing is for a small professional-services firm billing its own clients: a consultancy, an advisory or accounting practice, a design or engineering studio. It drafts the invoices those clients owe for a month. A draft is good when the owner could send it after one read: every line names its rate basis in `BILLING.yaml`, every amount re-derives from that basis and the pull, the months it covers are the months owed, and nothing on it is invented. Nothing is ever sent and nothing is posted to any books; the owner issues the invoice and assigns its number.

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

A firm that bills no time leaves the time records out; one that bills no milestones has none. The checks below apply to whichever bases a contract uses.

## Conduct here

- **The rules first.** `BILLING-RULES.md` in the billing folder overrides this skill and your brief. `BILLING.yaml` is the only source of rates, amounts, bill-to and terms. If the contract file it names disagrees with it, that is a question, never a correction.
- **Already done?** The pull lists the issued invoices it found (`invoices_since_period_start`, `last_invoice`). An issued invoice that covers the period means `already-billed` with the file as evidence. Look in the folders BILLING.yaml names before concluding a month is unbilled.
- **Hours come from the pull.** Hourly lines use the hours the pull computed from the time records source for that month and client key. When the pull warns it is short of the month, or the hours look wrong against the engagement's record, draft with the pull's hours and ask, or ask before drafting; never adjust them yourself. An `override_reason` must point to the owner's answer.
- **Milestones and pass-through need evidence.** A milestone is billed only when a file in the engagement's folders (the ones BILLING.yaml names) or the Insights Portal shows it was met: a delivered readout, an acceptance email. A pass-through is billed only from a receipt or an expense report on file. No evidence: `question` or `not-billable`, with the reason.
- **Unbilled months.** When the pull shows months owed before the period, draft one invoice covering them all (`months` in the lines file), or say in the note why not (a hold the owner placed, a dispute). Never let an owed month drop silently.
- **Unconfirmed terms.** A contract with `confirmed: false` is still drafted, and the row carries the question that asks the owner to confirm the terms.
- **No bookkeeping.** The orchestrator writes STATUS, LOG, CONFIRMATIONS and the evidence file. You write only the lines file, the cover email (the preparer) or the review note (the reviewer).

## The cover email

A short note in the owner's voice to the bill-to contact: the invoice attached, the months it covers, the total, the due date, one line of thanks. No sales language, nothing the invoice does not say. Run `unslop-email` over it. It is a file, `invoices/<contract> <yyyy-mm> cover email DRAFT.md`, with `To:`, `Subject:` and the body. It reaches the drafts folder of the owner's mail client (for example Outlook) only through `firm-billing-deliver`, and only where BILLING.yaml says `email_delivery: outlook-drafts` (the setting's name for "the mail client's drafts folder") and a reply thread is pinned. Otherwise the file is the delivery, and the owner sends it from whatever mail client they use.

## The return here

The shared block. Each `items` entry is one contract:

| Field | Value |
|---|---|
| `test` | `contract` |
| `item` | the contract id |
| `state` | `drafted`, `already-billed`, `not-billable` or `question` (the reviewer: `PASS` or `FAIL`) |
| `evidence` | the draft JSON (drafted), the issued invoice file (already-billed), the file or reference that decides it |
| `amount` | the draft's total, or null |
| `note` | the reason for anything not drafted, and any earlier owed month left out |

`extra` carries `{"rate_basis": {"<contract>": ["retainer", "hours"]}, "months": {"<contract>": ["2026-08", "2026-09"]}}` from the preparer, and `{"review_files": {"<contract>": "<review note>"}, "content_sha256": {"<contract>": "<hash reviewed>"}}` from the reviewer. A question names the contract in `blocks` (`contract:<id>`).
