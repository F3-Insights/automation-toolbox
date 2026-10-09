# Finance

Financial planning and analysis: bridging each forecast revision to the one before it, the monthly rolling forecast, the annual three-way budget, the weekly 13-week cash forecast, one-off analyses requested by leadership, and contractual investor data-room postings. For a CFO, controller or FP&A lead who wants every number traced to a source and every draft reviewed before a person sends it. Agents never edit an issued workbook, upload, post or send.

## Agents

| Agent | What it does | Needs |
|---|---|---|
| `forecast-orchestrator` | Bridges a new forecast revision to the prior and builds the rolling vintage; done is computed by `forecast-check` | commands `forecast-*` |
| `forecast-drivers-analyst` | Writes hypotheses before anyone looks, then answers every material sense-check flag | command `forecast-check` |
| `forecast-modeler` | Proposes a rolling vintage's forecast months as `proposals.json` | commands `forecast-extract`, `forecast-check` |
| `forecast-bridge-writer` | Explains each bridge line with cited evidence and writes the executive summary | command `forecast-check` |
| `forecast-reviewer` | Independent PASS or FAIL on a forecast vintage | command `forecast-check` |
| `budget-orchestrator` | Builds the annual three-way budget in passes: assumptions, statements, board draft | none |
| `budget-builder` | Writes the budget's assumptions, three statements, 13-week cash, bridge and board draft | commands `forecast-extract`, `budget-detail-diff`, `trial-balance`, `excel-handle` |
| `cash-forecast-orchestrator` | Rolls the 13-week cash forecast forward each week and reports the low point | none |
| `cash-forecaster` | Explains last week's misses and rolls the thirteen weeks by the direct method | commands `ar-ap-hygiene`, `trial-balance`, `gl-normalize`, `excel-handle`, `pdf-handle` |
| `analysis-orchestrator` | First draft of a one-off financial analysis from its request task | Insights Portal |
| `analysis-writer` | Settles the intake, builds the workbook and memo, traces every figure | Sage Intacct (`intacct-gl-detail`), commands `trial-balance`, `gl-normalize`, `excel-handle`; Insights Portal |
| `investor-posting-orchestrator` | Keeps contractual investor data-room postings on time, staged for a person to upload | none |
| `investor-posting-preparer` | Stages one period's approved finals with a manifest, upload checklist and draft notice | commands `pdf-handle`, `excel-handle` |

All orchestrators also use `numbers-reviewer` and `executive-red-team` (reporting) and `comms-confirm` (productivity).

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `forecast-method` | How a forecast is revised, bridged and defended; the Forecast folder and the shapes of the files each forecast worker writes | commands `forecast-*` |
| `budget-method` | How an annual three-way budget is built from drivers, on top of `forecast-method` | none |
| `cash-forecast-method` | How a rolling 13-week direct-method cash forecast is built and kept honest | none |
| `analysis-workstream` | Intake, folder, figure ledger and DONE checklist for a one-off analysis | none |
| `investor-posting-workstream` | Posting rules, status table, approved-finals-only staging and DONE checklist | none |

## Scripts

Each script runs by path, `python3 ~/.claude/skills/<skill>/scripts/<script>.py`, and prints `--help`. A command name used elsewhere in this README, such as `trial-balance`, is a label for the script of that name with underscores (`trial_balance.py`). Nothing is installed.

**`forecast-method`**
- `forecast_prepare.py`: opens or refreshes a forecast vintage before a session, reading the workbooks only.
- `forecast_extract.py`: reads one forecast workbook into an account by month extract, footed and tied.
- `forecast_bridge.py`: builds the vintage's bridge from the prior forecast to the new one, so that it foots.
- `forecast_sense_check.py`: flags what in the new forecast needs explaining; it never judges.
- `forecast_score.py`: scores the hypotheses against the bridge and keeps the calibration log.
- `forecast_revise.py`: builds a rolling vintage's workbook as a values-only copy of the prior forecast.
- `forecast_record.py`: records one row of the vintage's evidence ledger.
- `forecast_check.py`: whether a vintage is done, computed from its folder.

The other commands the finance agents run belong to other departments' skills: `trial-balance`, `gl-normalize` and `intacct-gl-detail` in `erp-ledger-pull`, `budget-detail-diff` in `month-end-flux`, `ar-ap-hygiene` in `collections-workstream` (accounting), and `excel-handle` and `pdf-handle` in `office-files` (productivity).

Planned but not yet written anywhere (named under "Later tools" in the skills): `budget-three-way`, `budget-check`, `budget-render`, `cash-actuals`, `cash-roll`, `cash-forecast-check`, `analysis-figures-check`, `analysis-queue`, `posting-stage`, `posting-check`.

### Settings and environment

The forecast scripts read their settings from the Forecast folder, not from the owner settings file. The scripts borrowed from accounting need what accounting's README lists: the four `SAGE_INTACCT_*` environment variables, all required, for `intacct-gl-detail`. Python 3, with `pyyaml` and `openpyxl`, declared in each script's `# /// script` block. The keys are described in [docs/settings.md](../docs/settings.md).
