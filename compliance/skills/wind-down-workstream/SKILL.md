---
name: wind-down-workstream
description: "An entity wind-down's procedure, loaded by compliance-entity-wind-down and compliance-reviewer, not for a user request; adds to orchestration-workstream. The Steps, WIND-DOWN-RULES.md, the reference sequence from authorization to records retention with each step's dependencies, step states and evidence, the filing packet, legal judgments routed to counsel, sensitive figures kept out of tasks, the section Plan the wind-down, the reviewer's checks and the DONE checklist."
---

# Entity wind-down

This skill extends `orchestration-workstream`: keep its conduct and return its block. Load it, and `task-stack-workstream` for the change set, with the Skill tool if they are not loaded.

A wind-down fails by order (paying owners before creditors, filing a dissolution while a franchise tax is unpaid) and by omission (a foreign registration never withdrawn keeps accruing fees). Agents place every step and prepare the paper; people decide, sign, pay and file.

## Steps

For `compliance-entity-wind-down`. `RUN` is the Run folder. The agent writes in the wind-down folder's `agent/` subfolder only, or under `RUN/` on a dry run.

1. [judgment] Orient. `whoami`; read `WIND-DOWN-RULES.md`, the owner's own plan and checklist files in the folder (read only), and `agent/WIND-DOWN-STATUS.md` and `agent/LOG.md` from the last session. Log each step in `LOG.md` as it happens.
   → WIND-DOWN-RULES.md is missing: stop
2. [judgment] Plan the wind-down (section Plan the wind-down): the step table, the packets for the next steps in `agent/prepared/`, and the claims list.
3. [hand-off: compliance-reviewer] Check the step table against the reference sequence (section Check the plan's completeness). Dispatch it together with step 4. Save its return as `RUN/returns/completeness.md`.
4. [hand-off: compliance-reviewer] Check every date, amount, file number and party in the status and the packets against the folder (section Check the plan's facts), with the claims list and the folder's sources only, never the plan's reasoning. Save its return as `RUN/returns/facts.md`.
   → a gap or a contradicted claim: step 2 (max 1)
5. [judgment] Tasks. For each step that is ready to file or waits on the owner, look in the Portal for an open task (`list_entities` task, `search`), and write a `create` or `comment` op for it in `RUN/changes.json` (`task-stack-workstream` shape, `orchestrator` `compliance-entity-wind-down`). Never a duplicate; tasks name the step and the entity only.
6. [judgment] Record `agent/WIND-DOWN-STATUS.md` (the step table with states and evidence) and the session's `agent/LOG.md` entry. A gap or claim still failing after one revision is a question, not a fix.
7. [judgment] Walk the DONE checklist with evidence and report: the entity and the next three steps with their owner and date, the step table by state, the packets prepared this session, the reviewer's results, the change set's ops, and the questions as one numbered list the owner can answer "1) ok 2) no", counsel's questions marked as such.
   → reported: done

After the session the Automation runs `task-stack-apply --run RUN --dry-run-if=<dry_run>`, the one writer of the owner's tasks.

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

## Plan the wind-down

Done by `compliance-entity-wind-down` itself, from the folder, the entity, the rules and the answers so far. The goal: every step placed on evidence, the next ones ready for a person to sign and file, and nothing done out of order. Read PDFs with `pdf-handle` and workbooks with `excel-handle`; make a folder with `mkdir -p`.

1. **Place each step** of the reference sequence for this entity, in the states above. Evidence is a filed copy, a receipt, an agency's acknowledgement or a signed document in the folder; a draft or a plan is not.
2. **Order** the open steps by their dependencies; name what blocks each.
3. **Prepare** each step that is next and not blocked, in `agent/prepared/<step-id>/`: `PACKET.md` and any notice or letter as `DRAFT-<name>.md`, beside the owner's files, never over them. Never prepare a step whose prerequisite is open.
4. **Claims.** List every date, amount, file number and party you wrote, with its source, for the reviewer.

A step that turns on a legal judgment (creditor priority, whether an asset may be distributed, whether a filing can be skipped) is a question for counsel, never a choice made here. Anything that creates liability if missed (an overdue filing, an accruing fee) is a finding at the top of the report. On a revision after a FAIL, fix exactly the reviewer's numbered findings.

## Check the plan's completeness

For `compliance-reviewer`, with `review-completeness` as the checklist (load it). The artifact is the step table; the reference model is the sequence S1 to S14 above, with the rules' reasons for steps that do not apply. Lines this job adds: a step placed `ready-to-file` while a step it comes after is open fails; a step marked `not-applicable` needs the rules' reason; a step that turns on a legal judgment and is decided in the plan, not asked of counsel, fails. Return the `review-completeness` return block.

## Check the plan's facts

For `compliance-reviewer`, with `review-facts` as the checklist (load it). The claims are the plan's list of dates, amounts, file numbers and parties; the sources are the wind-down folder's documents (read PDFs with `pdf-handle`). A value that only a draft or the plan itself supports is NOT IN MY SOURCES. Return the `review-facts` return block.

## Sensitive figures

Balances, loans, holders' names and settlement amounts stay in the wind-down folder. Portal tasks and notes name the step and the entity only.

## DONE checklist

The main agent checks each item with evidence; 2 is confirmed by the reviewer's section Check the plan's completeness, 4 by its section Check the plan's facts.

1. Every step S1 to S14 has a state and evidence or a reason.
2. No step of the reference sequence is missing for this entity, or its absence is explained.
3. No step is `ready-to-file` while a step it comes after is open.
4. Every date, amount, file number and party in the status and the packets is verified against a source in the folder.
5. Every step that is next has a packet or a question naming who must act.
6. Every legal judgment is a question for counsel, not a decision in the plan.
7. Every owner action has one Portal task op, with no duplicate of an open task.
8. Nothing was filed, paid, signed or sent by an agent.

## Later tools

- `compliance-wind-down-check`: compute DONE items 1, 3 and 5 from `WIND-DOWN-STATUS.md` and the packets.
- `compliance-state-filing-lookup`: fetch an entity's standing and filing history from a state's public registry for S6 evidence.
