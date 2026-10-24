---
name: intercompany-workstream
description: "The job skill of accounting-intercompany-reconciliation, also read by the accounting-worker it dispatches, not for a user request: what monthly intercompany reconciliation adds to month-end-workstream. Covers the session's Steps, INTERCOMPANY-RULES.md (entities, intercompany accounts, allocation bases and their agreements, tolerance), the entity-pair matrix, matching across entities, the three causes of a difference, true-ups that book both sides, the worker section Reconcile a batch of pairs, the HANDOFF file the close records and the DONE checklist. Not for the rest of the close; use month-end-close."
---

# Intercompany reconciliation

This skill extends `month-end-workstream`: keep its conduct and return its block. Load it with the Skill tool if it is not loaded. The reconciliation method is `month-end-reconciliation`; an entry is drafted as `month-end-journal-entry` says. The goal: every entity pair's intercompany balances net to zero at month end, or every difference is explained by a dated item and has a drafted entry or a named owner, so the consolidation eliminates cleanly and the auditor finds an agreement behind every cross-entity charge.

## Steps

1. [judgment] Orient. Read `INTERCOMPANY-RULES.md`, the close's `MONTH-END-RULES.md`, the period's `STATUS.md` and the prior month's `reconciliations/intercompany/`. The close owns the period's `STATUS.md`, `LOG.md` and evidence file; this job writes only under `reconciliations/intercompany/` and import files in `journal-entries/`.
2. [judgment] Check the pull. The period's ledger pull in `work/source/` must be dated after the last entry booked; a stale pull is reported and the work marked PRELIMINARY.
   → no pull for the period: stop
3. [script] Build the matrix. Run `trial-balance` with `--by-dimensions` over the period's pull (its `--help` names the inputs) or read the trial balance by entity it already wrote, and write `reconciliations/intercompany/MATRIX-{yyyy-mm}.csv`: each pair's due-from in one entity, due-to in the other, the difference, and the net across all pairs.
   → every pair within the tolerance and every allocation booked: step 6
4. [hand-off: accounting-worker] Reconcile: one worker (model opus) per batch of pairs with a difference over the tolerance, and one for the month's allocations the rules list, in parallel, told to follow this skill's section Reconcile a batch of pairs, with the folder, the period, its pairs or allocations, the rules file's path, the answers so far and any reviewer fixes. Log each dispatch and record each return at once in `reconciliations/intercompany/INTERCOMPANY-LOG-{yyyy-mm}.md`.
5. [hand-off: accounting-reviewer] Review every pair reconciliation and drafted entry, told to use `month-end-workstream`'s section Review an item, with the files and sources only. Save its note as `reconciliations/intercompany/REVIEW-{yyyy-mm}-{subject}.md`.
   → FAIL: step 4 (max 1)
6. [script] Ask. A difference only a person can explain, and a FAIL that came back twice, goes to its role through comms-confirm (`confirm new`, `confirm task`, one `confirm relay` at the end), recorded in the intercompany log.
7. [judgment] Hand off and close. Write `reconciliations/intercompany/HANDOFF-{yyyy-mm}.md` (The hand-off), walk the DONE checklist with evidence, and report the matrix totals (pairs, pairs at zero, net difference), each open pair with its difference, cause and drafted entry, the reviewer's verdicts, missing agreements, and the questions as one numbered list the owner can answer "1) ok 2) no".
   → reported: done

## The rules file

`INTERCOMPANY-RULES.md`, supplied with the Month-End folder, names:
- the entities and how the ledger tells them apart (an entity or location dimension);
- the intercompany accounts (due-from and due-to, or one clearing account) per entity;
- each recurring cross-entity charge (management fee, shared payroll, rent, equipment) with its basis, its source and its written agreement, or "no agreement";
- the tolerance, and who explains differences (a role).

It wins over this skill.

## The matrix

One row per entity pair with a balance: entity A's due-from B, entity B's due-to A, the difference. A single clearing account is read the same way by its counterparty dimension. The matrix's net across all pairs is zero when the books are right; its total is the first fact the report gives.

## Why a pair does not net

1. **One side only.** A charge booked in one entity and not the other (the usual cause).
2. **Timing.** Booked in different periods.
3. **Amount.** Booked at different amounts, often an allocation computed twice.

Each unmatched item is named by its GL references on the side where it exists. The true-up books both sides in the period so the pair nets, cites the agreement, and reverses nothing a person booked.

## The hand-off

The close (`accounting-month-end-close`) is the one writer of the period's state. This work writes only under `reconciliations/intercompany/` and import files in `journal-entries/` (STATE Posted, for a person to upload; agents never upload or post), and leaves `HANDOFF-{yyyy-mm}.md` with evidence rows (`test`, `item`, `state`, `evidence`, `amount`, `note`) the close records on its next session. The file is the contract between the two jobs: its name, its place and its row shape stay as they are.

## DONE checklist

The main agent checks each item with evidence; the reviewer confirms 3 and 4.

1. The matrix is built from a pull dated after the last booked entry, and its net is stated.
2. Every pair over the tolerance has a reconciliation file.
3. Every difference is traced to dated items or is an open question with an owner.
4. Every drafted true-up and allocation entry passes `je-import-check`, books both sides and cites its agreement.
5. Every recurring cross-entity charge has a written agreement or a finding saying it has none.
6. `HANDOFF-{yyyy-mm}.md` lists every pair's state for the close.

## Reconcile a batch of pairs

For an `accounting-worker` given the folder, the period, its entity pairs or the month's allocations, and the rules file's path. Read `INTERCOMPANY-RULES.md` and `MONTH-END-RULES.md` first. Commands: `intacct-gl-detail`, `trial-balance`, `gl-normalize`, `accounting-je-import`, `accounting-je-import-check`, `excel-handle`, `mkdir -p`. Skills: this one, `month-end-reconciliation`, `month-end-journal-entry`.

- **Already done?** A person's reconciliation or a booked true-up in the pull counts; return it as the evidence.
- **Tie each pair.** Pull the GL detail of both sides for the period. Match transactions across entities by amount, date and reference; list what is on one side only, in another period, or at a different amount. Write `reconciliations/intercompany/<pair> {yyyy-mm}.md` with the balances, the matched total, each unmatched item and its cause.
- **Allocations.** For each allocation the rules list, compute it from its stated basis and source, compare with what was booked, and draft the difference.
- **Draft entries** with `accounting-je-import` as `month-end-journal-entry` says (an import file a person uploads, STATE Posted), each line naming the agreement and the unmatched items it clears, and lint it with `accounting-je-import-check`. A true-up books both sides so the pair nets to zero.

A difference with no transaction behind it is a question, never an entry. Return the `month-end-workstream` block with `workstream: "intercompany"`: `items` with test `reconciliations` (item the pair as `<entity>-<entity>`, state reconciled or open, amount the difference) and `entries` (state drafted); `findings` for each pair with no written agreement and each allocation whose basis the record contradicts; `proposals` for rule changes with their source.

## Later tools

- `intercompany-matrix`: build the pair matrix from the trial balance pull by entity.
- `intercompany-match`: match both sides' GL detail and list the unmatched items per pair.
- `intercompany-check`: compute DONE items 1, 2, 4 and 6 from the folder.
