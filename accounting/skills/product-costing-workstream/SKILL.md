---
name: product-costing-workstream
description: Reference loaded by product-costing-analyst and product-costing-orchestrator, not for a user request; what a manufacturing client's monthly product-costing review adds to orchestration-workstream. Covers the costing folder and COSTING-RULES.md first, the client's extracts received and versioned before any number, the per-finished-good P&L by product-costing-variance, every re-issue a controlled revision by product-costing-revision, the cost review pack (workbook, revision log, client requests, memo) and the DONE checklist.
---

# Product costing workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Read it at `~/.claude/skills/orchestration-workstream/SKILL.md` if it is not loaded. The method is already written and is not repeated here:

- `product-costing-variance`: the twelve-step pipeline from extracts to the per-finished-good P&L, the tie-outs and the rules that hold. Its modes `build`, `refresh` and `explain`.
- `product-costing-revision`: how a workbook the client has seen is re-issued (a dated copy, the original's hash unchanged, the Revision Log and Client Requests sheets).
- `comms-client-status-update`: the voice of the memo that goes with the pack.

## Conduct here

- **The rules file first.** `COSTING-RULES.md` in the costing folder names the extracts the client sends each month and their expected columns, the factories, the standards source, the tie-out tolerances, the shared workbook's name, and who on the client side answers what (roles). It overrides this skill.
- **Extracts before numbers.** A month starts only when every extract the rules list is in `<yyyy-mm>/raw/`, dated as received. A missing or stale extract (the same quantities as last month for most products) is a client request, not a reason to estimate.
- **The tie comes first.** Standard plus variance ties to the trial balance per cost category and factory before any product-level statement is written.
- **Client data stays in the folder.** Nothing from it enters a repository or a message.

## The folder

```
<costing folder>/
  COSTING-RULES.md  BACKGROUND.md  STATUS.md
  <yyyy-mm>/
    raw/             the client's extracts as received, never edited
    work/            normalized tables, quantity and routing checks
    <shared workbook name> rev<N> <yyyy-mm-dd>.xlsx   the new revision
    memo.md          the cost review memo
    reviews/  LOG.md  CONFIRMATIONS.md    (the last two the orchestrator's only)
```

## The return here

The shared block with items `extracts` (item the extract, state `received`, `missing` or `stale`), `tieout` (item `<category>:<factory>`, state `tied` or `untied`, `amount` the gap), `revision` (item the new workbook, state `drafted`, `note` the original's hash and whether it is unchanged), `memo` (state `drafted`); client requests in `questions` with `of` the client role.

## DONE (the orchestrator checks each item and cites its evidence)

1. Every extract the rules list for the month is in `raw/`, or is a client request with an owner.
2. Quantity sanity ran: no unexplained carry-forward, every product with production has a labour standard or a flag.
3. Standard plus variance ties to the trial balance per category and factory within the rules' tolerance; factory pools sum to consolidated.
4. The revision is a new dated file; the original's SHA-256 is unchanged.
5. The Revision Log labels every changed metric correction, business change or new data.
6. The Client Requests sheet lists what the client still owes, each with an owner.
7. The memo's first sentence says whether the movement is mostly correction or mostly business, and quotes only figures in the workbook.
8. The checker (`numbers-reviewer`) re-derives the tie-outs and the memo's figures and says PASS.

## The scripts and the layout file

This skill's `scripts/` folder holds the costing commands, run as `python3 ~/.claude/skills/product-costing-workstream/scripts/<name>.py`: `sap_extract_normalize.py` (an SAP extract into one long table), `prodqty_check.py` (quantity sanity), `routing_rollup.py` (routing minutes per finished good), `fg_pl_extract.py` (the per-finished-good P&L workbook into long tables, revenue tied to the TB) and `costmodel_audit.py` (the workbook's tie-outs, margin arithmetic and month references, the tie-out of record).

`fg_pl_extract.py` and `costmodel_audit.py` read the client's workbook through a **cost-model layout file**, a JSON file that says which tabs, rows and columns hold what, because every client lays the model out differently. Keep one per client in the costing folder (for example `<costing folder>/cost-model-layout.json`) and pass it with `--layout`, or name it in the `cost_model_layout` setting under `[product-costing-workstream]`; without either the scripts stop. Its keys (`month_tab`, `tb_tab`, `first_row`, `info_columns`, `block_start`, `block_width`, `block_fields`, `tb_columns`, `tb_first_amount_col` and the optional ones) are described at the top of `scripts/_common.py`. Client header words the SAP normaliser does not know go in a synonyms file named by `--synonyms` or the `extract_synonyms` setting.

## Later tools

- `costing-check`: compute DONE items 1, 3 and 4 from the folder (extract list, the tie-out sheet, the hash).
