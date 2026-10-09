---
name: wind-down-workstream
description: Reference loaded by wind-down-planner and wind-down-orchestrator, not for a user request; what winding down a legal entity adds to orchestration-workstream. Covers WIND-DOWN-RULES.md, the reference sequence from authorization to records retention with each step's dependencies, step states and evidence, the filing packet (form, authority, fields with sources, fee, signer, proof), legal judgments routed to counsel, sensitive figures kept out of tasks and the DONE checklist. completeness-audit compares a plan with its reference sequence.
---

# Entity wind-down

This skill extends `orchestration-workstream`: keep its conduct and return its block. Load that skill if it is not loaded.

A wind-down fails by order (paying owners before creditors, filing a dissolution while a franchise tax is unpaid) and by omission (a foreign registration never withdrawn keeps accruing fees). Agents place every step and prepare the paper; people decide, sign, pay and file.

## The rules file

`WIND-DOWN-RULES.md` names the entity, its form (corporation or LLC) and home state, its foreign registrations, its tax status, the directors, officers and holders by role, the known creditors and agreements, counsel and the tax preparer by role, the registered agent, and which steps do not apply with why. It wins over this skill. The owner's own plan files are read, never edited.

## The reference sequence

| Id | Step | After |
|---|---|---|
| S1 | Inventory: assets, bank accounts, contracts, licenses, IP, registrations, creditors, holders | |
| S2 | Authorize: board resolution and holder consent to dissolve, plan of dissolution | S1 |
| S3 | Federal notice of the dissolution resolution where the entity's tax form requires it (Form 966 for a corporation, within its deadline) | S2 |
| S4 | Notify holders, licensors and counterparties as the agreements require (notice periods) | S2 |
| S5 | Creditors: every known claim paid, settled, released or waived in writing, in the order the law and counsel set | S1, S2 |
| S6 | Bring filings current: annual reports, franchise taxes, statements of information, in every state | S1 |
| S7 | Close tax accounts: payroll, sales and use, state withholding, where open | S5 |
| S8 | Assets: sell, assign or abandon; IP decided; remaining cash distributed only after S5 | S5 |
| S9 | Dissolve in the home state (certificate of dissolution or cancellation) | S5, S6 |
| S10 | Withdraw or surrender each foreign registration | S6, S9 |
| S11 | Final federal and state returns marked final; final K-1s for a pass-through | S8, S9 |
| S12 | Terminate the registered agent, after the state filings that need it | S9, S10 |
| S13 | Close bank accounts after the last payment clears | S5, S8, S11 |
| S14 | Close the tax ID account with the IRS; keep records for the retention period, with their custodian named | S11, S13 |

## Step states

`done` (evidence of the act), `ready-to-file` (packet prepared and checked, prerequisites done), `prepared` (packet drafted, a prerequisite open), `blocked` (waits on a decision or a person), `not-started`, `not-applicable` (the rules say why). Evidence is a filed copy, a receipt, an acknowledgement or a signed document; a draft, a reminder or a plan is not.

## The filing packet

`agent/prepared/<step-id>/PACKET.md`: the form and its current version, the authority and how it is filed, every field with its value and the source of the value, the fee, the signer by role, the deadline, and the proof to keep afterwards. Notices and letters are `DRAFT-<name>.md`.

When S9, S10 or S12 is `done`, the entity's recurring items in the owner's compliance calendar stop applying: return a `proposals` line for the calendar's rules owner, with the evidence.

## Sensitive figures

Balances, loans, holders' names and settlement amounts stay in the wind-down folder. Portal tasks and notes name the step and the entity only.

## DONE checklist

The orchestrator checks each item with evidence; 2 is confirmed by `completeness-audit`, 4 by `fact-check`.

1. Every step S1 to S14 has a state and evidence or a reason.
2. No step of the reference sequence is missing for this entity, or its absence is explained.
3. No step is `ready-to-file` while a step it comes after is open.
4. Every date, amount, file number and party in the status and the packets is verified against a source in the folder.
5. Every step that is next has a packet or a question naming who must act.
6. Every legal judgment is a question for counsel, not a decision in the plan.
7. Every owner action has one Portal task op, with no duplicate of an open task.
8. Nothing was filed, paid, signed or sent by an agent.

## Later tools

- `wind-down-check`: compute DONE items 1, 3 and 5 from `WIND-DOWN-STATUS.md` and the packets.
- `state-filing-lookup`: fetch an entity's standing and filing history from a state's public registry for S6 evidence.
- Finish step: `task-stack-apply` on `RUN/changes.json`, after the session.
