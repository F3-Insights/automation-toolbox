# Forecast workers' contract

What a forecast worker writes, where, and in what shape. `SKILL.md` in this skill is the method (why the files are shaped this way) and the worker's conduct; this file is the reference it points to. A worker also keeps `orchestration-workstream`'s conduct and returns its block.

## The folder

```
<Forecast folder>/
  FORECAST-RULES.md  FORECAST-SETTINGS.yaml  modules.yaml  driver-tree.yaml  BACKGROUND.md  STATUS.md
  calibration.jsonl                       every vintage's hypothesis scores (forecast-score appends)
  vintages/<vintage>/
    VINTAGE.yaml                          prior and new workbooks, kind, years, last actual month
    work/source/prior.json  new.json      the extracts (forecast-prepare); budget.json when named
    work/source/evidence.json             E-nnn: the revision's change log rows, the evidence files
    hypotheses.json                       drivers, before the bridge
    bridge.json  bridge.md                forecast-bridge
    flags.json                            forecast-sense-check
    flags-resolved.json                   drivers, after the bridge
    proposals.json                        model, rolling vintages only
    reasons.json  summary.md              bridge workstream
    scores.json                           forecast-score
    reviews/review <vintage> v<N>.md      reviewer
    FORECAST-EVIDENCE-<vintage>.csv       forecast-record, the orchestrator only
    STATUS.md  LOG.md  CONFIRMATIONS.md   the orchestrator only
```

## The files and their shapes

The examples below are for an invented manufacturer, Acme Components.

Line keys are `<year>:<line key>` (`2027:distributor_sales`), the line keys from `modules.yaml` plus the bridge's own `actuals`, `restated` and `unclaimed`. Amounts are dollars in EBITDA terms (a cost that rises is negative).

**`hypotheses.json`** (drivers, written before the bridge exists, from the prior, the requests and the calibration log; never from the new workbook or its change log):

```json
{"written_by": "forecast-drivers-analyst",
 "fy": {"2027": {"ebitda_expected": 3100000, "revenue_expected": 42000000}},
 "lines": {"2027:distributor_sales": {"direction": "up", "expected": 400000, "confidence": 0.6,
                              "rationale": "The request moves two distributor contracts into Q1."}},
 "key_events": [{"event": "Two distributor contracts move into Q1", "lines": ["2027:distributor_sales"],
                 "expected_impact": 400000, "probability": 0.6, "evidence_needed": "signed contracts"}]}
```

Every active line of every year needs an entry (`expected: 0` with a rationale is an answer).

**`flags-resolved.json`** (drivers): one entry per material flag id in `flags.json`.

```json
{"F-3eda16": {"resolution": "explained", "text": "Eliminations are negative by design.", "evidence": ["E-004"]},
 "F-0782e1": {"resolution": "revised", "text": "August tooling-charge reversal forecast as a trend; the model's owner corrects it.", "evidence": ["E-007"]},
 "F-6989f5": {"resolution": "open", "text": "September payroll doubles.", "owner": "Controller", "question": "Q-002"}}
```

**`proposals.json`** (model, rolling vintages only): forecast months only, workbook sign.

```json
{"rows": [{"account": "40000", "department": "", "location": "PLANT1", "cls": "OEM",
           "amounts": {"2026-10": 120000.0, "2026-11": 125000.0}, "node": "revenue_oem", "note": "E-003"}]}
```

**`reasons.json`** (bridge workstream): one entry per line at or above its materiality, and any other line worth a word.

```json
{"lines": {"2027:distributor_sales": {
   "driver": "Two distributor contracts moved from Q2 into Q1", "kind": "business",
   "evidence": ["E-003"], "questions": [],
   "detail": [{"text": "Northwind contract from April to January", "amount": 240000.0, "evidence": ["E-003"]},
              {"text": "Contoso contract from May to February", "amount": 160000.0, "evidence": ["E-003"]}]}}}
```

`kind` is `business`, `correction`, `timing`, `new-data` or `mixed`. `evidence` ids come from `work/source/evidence.json`; `questions` ids from the ledger. `detail`, when given, sums to the line within fifty cents: add a last item for the rest rather than leave a gap.

**`summary.md`** (bridge workstream): the executive summary to the contract in `SKILL.md`, with the headings `## Top drivers`, `## What would change it` and `## Anticipated questions` (bulleted or numbered items under each). Every `$` figure must be one the bridge carries, in $k to one decimal (`$(15.0)k`) or whole dollars.

## What forecast-check counts

`extracts`, `hypotheses`, `bridge`, `reasons`, `flags`, `scores`, `summary`, `questions`, `review`, `messages`, `delivered`. Run `python3 ~/.claude/skills/forecast-method/scripts/forecast_check.py FOLDER --vintage V --format json` before and after your work; your return's `items` name the tests your files satisfy.

## The return here

The shared block, with these item tests and states:

| Test | Item | States |
|---|---|---|
| `hypotheses` | `set` | `written` |
| `flags` | a flag id | `explained`, `revised`, `open` |
| `reasons` | a line key | `explained`, `open` |
| `summary` | `summary.md` | `drafted` |
| `proposals` | `proposals.json` | `drafted` |
| `review` | `vintage` | `PASS`, `FAIL` (the reviewer) |

`questions` carry `ask`, `of` (a role), `why`, `blocks` (line keys or flag ids) and, in `extra`, `fallback` (the assumption used if nobody answers) and `due` (yyyy-mm-dd). `proposals` for `modules.yaml`, `driver-tree.yaml` or the settings carry the evidence that justifies them.
