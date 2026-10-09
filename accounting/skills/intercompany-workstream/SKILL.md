---
name: intercompany-workstream
description: Reference loaded by intercompany-reconciler and intercompany-orchestrator, not for a user request; what monthly intercompany reconciliation adds to month-end-workstream. Covers INTERCOMPANY-RULES.md (entities, intercompany accounts, allocation bases and their agreements, tolerance), the entity-pair matrix, matching across entities, the three causes of a difference, true-ups that book both sides, the hand-off to the close orchestrator and the DONE checklist.
---

# Intercompany reconciliation

This skill extends `month-end-workstream`: keep its conduct and return its block. Read it at `~/.claude/skills/month-end-workstream/SKILL.md` if it is not loaded. The reconciliation method is `month-end-reconciliation`; an entry is drafted as `month-end-journal-entry` says.

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

The close orchestrator is the one writer of the period's state. This work writes only under `reconciliations/intercompany/` and import files in `journal-entries/` (STATE Posted, for a person to upload; agents never upload or post), and leaves `HANDOFF-{yyyy-mm}.md` with evidence rows (`test`, `item`, `state`, `evidence`, `amount`, `note`) the close records on its next session.

## DONE checklist

The orchestrator checks each item with evidence; the reviewer confirms 3 and 4.

1. The matrix is built from a pull dated after the last booked entry, and its net is stated.
2. Every pair over the tolerance has a reconciliation file.
3. Every difference is traced to dated items or is an open question with an owner.
4. Every drafted true-up and allocation entry passes `je-import-check`, books both sides and cites its agreement.
5. Every recurring cross-entity charge has a written agreement or a finding saying it has none.
6. `HANDOFF-{yyyy-mm}.md` lists every pair's state for the close.

## Later tools

- `intercompany-matrix`: build the pair matrix from the trial balance pull by entity.
- `intercompany-match`: match both sides' GL detail and list the unmatched items per pair.
- `intercompany-check`: compute DONE items 1, 2, 4 and 6 from the folder.
