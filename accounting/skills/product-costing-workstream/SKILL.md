---
name: product-costing-workstream
description: "The job skill of accounting-product-costing-review, not for a user request: a manufacturing client's monthly product-costing review. Covers the costing folder and COSTING-RULES.md first, the client's extracts received and versioned before any number, the Steps, the section Build the month (the per-finished-good P&L by product-costing-variance, re-issued as a controlled revision by product-costing-revision), the section The cost review memo, the return and the DONE checklist, with accounting-reviewer's review-numbers as the independent check. For one product's margin question by hand, use product-costing-variance."
---

# Product costing workstream

Each month a cost review pack the client can rely on: product margins from standards and actuals that tie to their own books per factory, every change since the last version labelled a correction or a business change, and a precise list of what the client still owes. `accounting-product-costing-review` runs it; the method is already written and not repeated here:

- `product-costing-variance`: the twelve-step pipeline from extracts to the per-finished-good P&L, the tie-outs and the rules that hold. Its modes `build`, `refresh` and `explain`.
- `product-costing-revision`: how a workbook the client has seen is re-issued (a dated copy, the original's hash unchanged, the Revision Log and Client Requests sheets).
- The cost review memo, below: the voice of the memo that goes with the pack.

Keep `orchestration-workstream`'s conduct.

## Conduct here

- **The rules file first.** `COSTING-RULES.md` in the costing folder names the extracts the client sends each month and their expected columns, the factories, the standards source, the tie-out tolerances, the shared workbook's name, and who on the client side answers what (roles). It overrides this skill.
- **Extracts before numbers.** A month starts only when every extract the rules list is in `<yyyy-mm>/raw/`, dated as received. A missing or stale extract (the same quantities as last month for most products) is a client request, not a reason to estimate.
- **The tie comes first.** Standard plus variance ties to the trial balance per cost category and factory before any product-level statement is written.
- **Client data stays in the folder.** Nothing from it enters a repository or a message.
- **Never edit the shared workbook or the extracts.** Write only new files in the period folder; plug no tie-out difference; never allocate a variance by one driver where the source places it.

## The folder

```
<costing folder>/
  COSTING-RULES.md  BACKGROUND.md  STATUS.md
  <yyyy-mm>/
    raw/             the client's extracts as received, never edited
    work/            normalized tables, quantity and routing checks
    <shared workbook name> rev<N> <yyyy-mm-dd>.xlsx   the new revision
    memo.md          the cost review memo
    reviews/  LOG.md  CONFIRMATIONS.md    (written by the main agent only)
```

## Inputs

- Costing folder and `COSTING-RULES.md`, from the launch.
- Period (yyyy-mm): default the latest month with extracts in `raw/` and no review.
- Mode: `build` for a first version, `refresh` for new extracts into the model (default), `explain <product>` for one product's question.
- Instructions (override the defaults, never the rules file) and dry run (work on copies in the Run folder; write nothing in the costing folder and ask no one).

## Steps

1. [judgment] Orient. Read `COSTING-RULES.md`, `BACKGROUND.md`, `STATUS.md`, the period's `LOG.md` and `CONFIRMATIONS.md`, and the last version's Revision Log and Client Requests. An answered request is input to this session.
2. [judgment] Check the extracts: list the rules' extracts against `<period>/raw/`, each received, missing or stale.
   → an extract missing or stale: step 7
3. [script] Hash the shared workbook before anything else: `sha256sum <shared workbook>`, recorded in `LOG.md`.
   → no hash: step 7
4. [judgment] Build the month yourself, following section Build the month, with `accounting-sap-extract-normalize`, `accounting-prodqty-check`, `accounting-routing-rollup`, `accounting-fg-pl-extract`, `accounting-costmodel-audit` and `excel-handle`, one command per call. Expect two passes in `build`: the first tie-out usually fails.
   → the model does not tie per category and factory: step 7
5. [hand-off: accounting-reviewer] Check the numbers with `review-numbers`, given the new revision, the trial balance, `raw/`, `work/` and `memo.md` only, never your reasoning. Save its note as `reviews/<yyyy-mm> numbers review.md`.
   → FAIL: step 4 (max 1)
6. [script] Prove the original unchanged: `sha256sum <shared workbook>` again, both hashes in the revision item's note.
   → the hash differs: stop
7. [script] Ask. The client requests and the owner's review request go through `confirm` as one batched list, recorded in `CONFIRMATIONS.md`; on a dry run, list them instead. A second reviewer FAIL becomes a question here.
8. [judgment] Close. Walk the DONE checklist, citing evidence per item; update `STATUS.md` and the period's `LOG.md`; report the period and mode, extracts by state, the tie-out per category and factory, the revision file and hash check, the top movements labelled correction or business, the reviewer's verdict, and the requests and questions as one numbered list the owner can answer "1) ok 2) no".
   → reported: done

## Build the month

Your goal: per-product margins the client can trust because the model ties to their books, with every change explained and nothing estimated that an extract should have supplied.

1. The SHA-256 of the shared workbook is recorded (step 3). Without it, the hash check is a question and the revision is not written.
2. Run `product-costing-variance` in the mode given, through `product-costing-revision` for the new revision: normalize the extracts (`accounting-sap-extract-normalize` for SAP extracts, `accounting-fg-pl-extract` for the per-finished-good workbook), run the quantity and routing checks (`accounting-prodqty-check`, `accounting-routing-rollup`), and audit the copy before and after (`accounting-costmodel-audit`, the tie-out of record). Stop at the tie-out when it fails, find the gap, and report it rather than write product-level results on an untied model.
3. Draft `memo.md` as section The cost review memo says, quoting only figures in the revision.
4. On a second pass after a reviewer FAIL, answer each finding: fixed, or declined with the reason.

Return the `orchestration-workstream` block with `workstream: "product-costing"` and the items below. The main agent records it in `LOG.md` and `STATUS.md`.

## The cost review memo

The memo goes with the pack to the client's finance lead, who has three minutes and will forward it. Its first sentence says whether this version's movement is mostly correction or mostly business. It quotes only figures in the revision; margin percentages are recomputed from summed dollars.

Voice, six principles:

1. **Matter-of-fact, not promotional.** No "on track," "great progress," "successfully completed," "key milestone." Say what was done.
2. **Factually precise.** Every statement defensible. If a thing is not ready, do not say it is ready. A preliminary finding says so.
3. **Not alarmist.** A surprising finding is normal project work. No "discovered," "uncovered," "critical," "alarming"; use "the analysis showed" or "we identified."
4. **Explanatory without condescension.** When a costing concept matters to the finding (absorbed standard, a tier-3 allocation), explain it in one sentence for a reader who does not know it.
5. **Consultative, not directive.** "We are recommending X because Y," not "X must be done."
6. **Measured confidence.** Confirmed things stated plainly; uncertain things marked "under review."

Cut on sight: on track, ahead of schedule, great progress, successfully completed, key milestone achieved, critical finding, alarming, major concern, discovered, uncovered, going forward, it should be noted that, as previously discussed, leverage, robust, seamless, deep dive, circle back.

Shape: each section a bold heading, a two-to-five-sentence paragraph that explains and connects, then bullets of discrete facts of twenty words or fewer that do not repeat the paragraph. A product finding reads `**Product:** finding, with the number.` Open requests name the client role, the ask and the date asked. Never include how the model was built (formulas, tabs, scripts) or a status judgment.

## The return here

The shared block with items `extracts` (item the extract, state `received`, `missing` or `stale`), `tieout` (item `<category>:<factory>`, state `tied` or `untied`, `amount` the gap), `revision` (item the new workbook, state `drafted`, `note` the original's hash and whether it is unchanged), `memo` (state `drafted`); client requests in `questions` with `of` the client role.

## DONE (the main agent checks each item and cites its evidence)

1. Every extract the rules list for the month is in `raw/`, or is a client request with an owner.
2. Quantity sanity ran: no unexplained carry-forward, every product with production has a labour standard or a flag.
3. Standard plus variance ties to the trial balance per category and factory within the rules' tolerance; factory pools sum to consolidated.
4. The revision is a new dated file; the original's SHA-256 is unchanged.
5. The Revision Log labels every changed metric correction, business change or new data.
6. The Client Requests sheet lists what the client still owes, each with an owner.
7. The memo's first sentence says whether the movement is mostly correction or mostly business, and quotes only figures in the workbook.
8. `accounting-reviewer`, with `review-numbers`, re-derives the tie-outs and the memo's figures and says PASS.

## The commands and the layout file

This skill's `scripts/` folder holds the costing commands: `accounting-sap-extract-normalize` (an SAP extract into one long table), `accounting-prodqty-check` (quantity sanity), `accounting-routing-rollup` (routing minutes per finished good), `accounting-fg-pl-extract` (the per-finished-good P&L workbook into long tables, revenue tied to the TB) and `accounting-costmodel-audit` (the workbook's tie-outs, margin arithmetic and month references, the tie-out of record). Each prints `--help`.

`accounting-fg-pl-extract` and `accounting-costmodel-audit` read the client's workbook through a **cost-model layout file**, a JSON file that says which tabs, rows and columns hold what, because every client lays the model out differently. Keep one per client in the costing folder (for example `<costing folder>/cost-model-layout.json`) and pass it with `--layout`, or name it in the `cost_model_layout` setting under `[product-costing-workstream]`; without either the commands stop. Its keys (`month_tab`, `tb_tab`, `first_row`, `info_columns`, `block_start`, `block_width`, `block_fields`, `tb_columns`, `tb_first_amount_col` and the optional ones) are described at the top of the skill's `_common.py` helper. Client header words the SAP normaliser does not know go in a synonyms file named by `--synonyms` or the `extract_synonyms` setting.

## Later tools

- `costing-check`: compute DONE items 1, 3 and 4 from the folder (extract list, the tie-out sheet, the hash).
