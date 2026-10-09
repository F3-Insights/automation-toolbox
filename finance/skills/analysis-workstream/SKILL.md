---
name: analysis-workstream
description: Reference loaded by analysis-writer and analysis-orchestrator, not for a user request; what a one-off financial analysis (a leadership request, a scenario model, a what-if) adds to orchestration-workstream. Covers intake questions with recommended defaults (grain, definitions, valuation basis, destination), one folder per analysis with raw data immutable, data hygiene first, the memo and workbook with a figure ledger tracing every figure, the owner's commitments flagged, and the DONE checklist. To run one, start analysis-orchestrator.
---

# Analysis workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Load it by name if it is not loaded. A first draft of an analysis is what the owner would otherwise build themselves; it is worth something only if they can trust every figure in it without redoing it.

## Conduct here

- **The rules file first.** `ANALYSIS-RULES.md` in the company's analysis folder says where analyses live, which data is confidential (compensation, equity, valuations) and must stay in the folder, the house format, and who may be asked what. It overrides this skill.
- **Intake before numbers.** Settle the grain (what one unit is), the definitions and thresholds, the valuation basis (run rate or in-period, the window) and the destination (board slide, working file, memo). Where the request does not say, write the question with a recommended default and proceed on the default, labelled.
- **Raw is immutable.** Source exports are saved dated in `raw/` and never changed; every transformation lands in `processed/` and is described in the README.
- **Hygiene before analysis.** Tie parsed data to the source totals and disclose every exclusion with its amount. A sharp break in a trend is a coding artifact until the transaction detail says otherwise. Normalize names with an explicit alias map.
- **Opinion labelled.** What the data says is apart from what it may mean. Every claim in the memo points at an exhibit.
- **The owner's voice is theirs.** A memo that states the owner's commitments, prices, or views is a draft for the owner to send; mark each such sentence for the owner's review.

## The folder

```
<analysis folder>/<yyyy-mm-dd>-<slug>/
  README.md        the request (with its Portal task), intake answers, sources, steps, status
  raw/             dated source exports, never edited
  processed/       derived tables
  <slug>.xlsx      the workbook, values with the formulas that matter
  memo.md          the draft memo
  figures.csv      every figure in the memo: figure_id, text as quoted, value, source (raw file and
                   range, processed table and row, or a calculation over other figure_ids)
  reviews/         the checker's and red team's notes
```

## The return here

The shared block with items `intake` (state `answered` or `defaulted`), `figures` (item the figure_id, state `traced` or `untraced`), `memo` and `workbook` (state `drafted`), `files` the folder's files, and the intake questions in `questions` with the default used in `extra.default`.

## DONE (the orchestrator checks each item and cites its evidence)

1. The README states the request, the intake answers or defaults, and every source.
2. Parsed data ties to the source totals, exclusions disclosed with amounts.
3. Every figure in the memo has a `figures.csv` row that traces it; none is `untraced`.
4. The checker (`numbers-reviewer`) re-derives the figures and says PASS.
5. The executive red team read the memo cold; each finding is answered or declined with a reason.
6. Every sentence that commits the owner is marked for the owner's review.
7. Confidential data stayed in the analysis folder; nothing was sent.

## Later tools

- `analysis-figures-check`: prove DONE item 3 in code (every number in `memo.md` is in `figures.csv`, every source resolves).
- `analysis-queue`: pick the Portal tasks the rules mark as analysis requests before the session.
