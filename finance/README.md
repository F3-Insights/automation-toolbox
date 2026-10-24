# Finance

Financial planning and analysis: bridging each forecast revision to the one before it, the monthly rolling forecast, the annual three-way budget, the weekly 13-week cash forecast, one-off analyses requested by leadership, and contractual investor data-room postings. For a CFO, controller or FP&A lead who wants every number traced to a source and every draft reviewed before a person sends it. Agents never edit an issued workbook, upload, post or send.

## The plugin

This folder is a standalone Claude Code plugin named `finance` (`.claude-plugin/plugin.json`), built the way [software](../software/README.md#the-plugin) is: one short main agent per job, one `finance-worker` and one `finance-reviewer` for dispatched work, the know-how in the jobs' skills as `##` sections with a `## Steps` list each, and every script a named command in `bin/` (`python3 scripts/build_bins.py finance`). A main agent's first instruction is to load its skills with the Skill tool.

```bash
claude --plugin-dir ~/coding-projects/automation-toolbox/finance --agent finance:finance-forecast
```

From Sentinel, an Automation launches a main agent by name; the overlay's `subagents:` lists `finance-worker` and `finance-reviewer` (or the reviewer alone), and prepare, precheck and finish steps run the named commands.

## Jobs and agents

| Agent | Automation | What it does |
|---|---|---|
| `finance-forecast` | fpa-forecast | Bridges a new forecast revision to the prior (or builds the rolling vintage): hypotheses first, a bridge that foots, every material line cited, the calibration log kept, reviewed and signed off; done computed by `finance-forecast-check` |
| `finance-budget` | fpa-budget | The annual three-way budget, one pass per session: assumptions with owners, statements that tie, the board draft |
| `finance-cash-forecast` | cash-forecast | The 13-week cash forecast rolled a week, last week's misses explained, the low point and headroom stated |
| `finance-analysis` | fpa-analysis | A one-off analysis from its Portal task: intake, workbook, memo and figure ledger |
| `finance-investor-posting` | investor-posting | Each owed data-room posting staged from approved finals, with manifest, upload checklist and draft notice |
| `finance-worker` | | One slice: a vintage's hypotheses (isolated), a rolling vintage's proposals, a catch-up posting period |
| `finance-reviewer` | | Independent PASS or FAIL against the named checklist section; edits nothing |

### What was folded, and what stayed separate

The conversion on 2026-10-23 replaced thirteen agents with these seven:

| Now | Was |
|---|---|
| `finance-forecast` | `forecast-orchestrator` |
| hypotheses: `forecast-method` section Write the hypotheses, by `finance-worker` (isolation: it must not see the new forecast); flags: section Answer the flags, by `finance-forecast` | `forecast-drivers-analyst` |
| `forecast-method` section Propose the rolling forecast, by `finance-worker` (the context that explains the numbers did not choose them) | `forecast-modeler` |
| `forecast-method` section Explain the bridge and write the summary, by `finance-forecast` | `forecast-bridge-writer` |
| `finance-reviewer` with sections Check a vintage (opus) and Sign off the vintage (fable), plus `review-numbers` | `forecast-reviewer` |
| `finance-budget`; `budget-method` section Build a pass, by the main agent | `budget-orchestrator`, `budget-builder` |
| `finance-cash-forecast`; `cash-forecast-method` section Roll the week | `cash-forecast-orchestrator`, `cash-forecaster` |
| `finance-analysis`; `analysis-workstream` section Write the analysis | `analysis-orchestrator`, `analysis-writer` |
| `finance-investor-posting`; `investor-posting-workstream` section Stage a period (the worker for a catch-up) | `investor-posting-orchestrator`, `investor-posting-preparer` |
| `finance-reviewer` briefed with the copied `review-numbers` and `review-red-team` | `numbers-reviewer`, `executive-red-team` (reporting) |

Decided in the conversion (the migration plan's open questions for finance):

- **The forecast's stage chain** folds into `forecast-method` sections. Two slices stay with the worker for a reason of context: the hypotheses (written by a context that never saw the new forecast, the one property `finance-forecast-check` cannot verify) and the rolling model. The flags and the reasons are done by the main agent in one context, since both explain the same bridge from the same evidence; independence rests on `finance-reviewer`, which re-derives the vintage and signs it off on fable.
- **The reviewer is read-only.** `finance-forecast` writes the review note (`reviews/review <V> v<N>.md`) from the reviewer's return and records it with `finance-forecast-record`.
- **`forecast_score` and `calibration.jsonl`** are unchanged: `finance-forecast-score` runs in Steps 6 and 8 and appends each vintage's scores once; the reviewer reads `scores.json` against the hypotheses.
- **Budget and cash forecast stay their own jobs** (not modes of the forecast): a different calendar, rules file and done. Investor posting stays in finance; it reads reporting's approved board package by path, a file contract that does not change.
- **The Steps assume no Automation.** `budget-method` and `cash-forecast-method` are also run by hand; without a scheduler the questions go in the report.
- **Model tiers** are named per dispatch in Steps (hypotheses and proposals on opus, a catch-up period on sonnet, the sign-off on fable).
- Rules files and `LOG.md` headings in the owner's folders that name the old agents are prose: no command parses them. New log headings read `by finance-forecast`. The evidence ledger's `by` column is free text.

## Skills

| Skill | Run by | What it holds |
|---|---|---|
| `forecast-method` (with `contract.md`) | finance-forecast, worker, reviewer | The method, Steps; sections Write the hypotheses, Propose the rolling forecast, Answer the flags, Explain the bridge and write the summary, Explaining a variance; checklists Check a vintage, Sign off the vintage; the vintage folder and file shapes |
| `budget-method` | finance-budget, reviewer | Steps; section Build a pass; checklist Check the statements |
| `cash-forecast-method` | finance-cash-forecast, reviewer | Steps; section Roll the week; checklist Check the week |
| `analysis-workstream` | finance-analysis, reviewer | Steps; section Write the analysis; checklist Check the analysis |
| `investor-posting-workstream` | finance-investor-posting, worker, reviewer | Steps; section Stage a period; checklist Check a packet |
| `review-numbers`, `review-red-team`, `report-tieout` | reviewer (shared copies) | The numbers and red-team checklists, the cross-document tie-out |
| `orchestration-workstream`, `comms-confirm`, `office-files`, `unslop`, `unslop-deliverable` | shared copies | Worker conduct and return block; questions through the owner; workbook and PDF reads; plain writing |
| `erp-ledger-pull` | shared copy, after the accounting merge | The ledger reads: trial balance, GL detail, normalizer, AR/AP hygiene, budget-detail diff, the Sage Intacct reference |

## Commands

In `bin/`, one per script: `finance-forecast-prepare`, `-extract`, `-bridge`, `-sense-check`, `-score`, `-revise`, `-record`, `-check`. The shared copies' commands keep one unprefixed name: `confirm`, `confirm-portal`, `waiting` (comms-confirm), `excel-handle`, `pdf-handle`, `powerpoint-handler` (office-files), `report-tieout`, and from `erp-ledger-pull` `trial-balance`, `gl-normalize`, `intacct-gl-detail`, `intacct-snapshot`, `month-end-pull`, `ar-ap-hygiene`, `budget-detail-diff`. Each prints `--help`.

**The accounting coupling.** `erp-ledger-pull` becomes a shared skill in accounting's conversion (its source moves to `shared/skills/erp-ledger-pull`, with `ar_ap_hygiene` and `budget_detail_diff` moved in). Finance's agents and skills already name its unprefixed commands; when both conversions are merged, add `finance` to the `erp-ledger-pull` line of `shared/manifest.yaml`, then run `python3 scripts/build_shared.py` and `python3 scripts/build_bins.py finance`. Until then the budget, cash-forecast and analysis jobs lack those commands; the forecast and investor-posting jobs do not use them.

Planned but not yet written (named under "Later tools" in the skills): `budget-three-way`, `budget-check`, `budget-render`, `cash-actuals`, `cash-roll`, `cash-forecast-check`, `analysis-figures-check`, `analysis-queue`, `posting-stage`, `posting-check`.

## Settings and environment

The forecast commands read their settings from the Forecast folder, not from the owner settings file. The ledger commands need what `erp-ledger-pull` lists: the four `SAGE_INTACCT_*` environment variables, all required, for `intacct-gl-detail`. Python 3, with `pyyaml` and `openpyxl`, declared in each script's `# /// script` block. The keys are described in [docs/settings.md](../docs/settings.md).
