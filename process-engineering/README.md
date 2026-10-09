# Process Engineering

The front half of a client engagement, before anything is built: reading a pre-engagement assessment, synthesizing stakeholder interviews, mapping a process as-is and to-be with every box traced to a quote, preparing and summarizing workshops, ranking what to automate with a business case, and running a recurring client survey season. For consultants and internal improvement teams who need findings a sponsor can read cold and an auditor can trace.

Most orchestrators work on an engagement named by its Context, a small file the runtime supplies that lists the engagement's folders by role (rules, transcripts, background, assessment exports). Each engagement keeps its own rules file (`DISCOVERY-RULES.md`, `PROCESS-FLOW-RULES.md` or `SURVEY-RULES.md`), which wins over every agent and skill.

Process engineering is forward-deployed work: working inside the client's operation to understand how it runs today and find what to automate.

## Agents

| Agent | What it does | Needs |
|---|---|---|
| `assessment-intake-orchestrator` | Turns assessment survey exports into an anonymized summary, interview topics and candidate opportunities | engagement Context |
| `discovery-synthesis-orchestrator` | Turns interview transcripts into an internal Read-Out, an anonymized Feedback by Topic and a one-page BASELINE | engagement Context; command `srt-transcript-collapse` |
| `process-flow-orchestrator` | Maps one process as-is and to-be from transcripts, fact-checked, audited for completeness and red-teamed | commands `process-flow-prepare`, `claim-ledger`, `process-flow-check`, `process-flow-render` |
| `workshop-orchestrator` | Prepares a workshop's run of show, cards and pre-read, and summarizes it afterwards | engagement Context; command `srt-transcript-collapse` |
| `automation-scoping-orchestrator` | Turns a to-be map into a ranked automation backlog with business cases | engagement Context; a reviewed process map |
| `survey-analytics-orchestrator` | Runs a client survey season as a checklist and drafts the readout from aggregate tables only | the engagement's `SURVEY-RULES.md`; a local categorization pipeline |
| `discovery-writer` | Writes one discovery document (summary, Read-Out, BASELINE, workshop pack, backlog), every statement cited | none |
| `discovery-checker` | Independent PASS or FAIL on counts, anonymization, tracing and time-box arithmetic | none |
| `process-flow-mapper` | Draws one version of the swim-lane map from the claim ledger and renders it | commands `claim-ledger`, `process-flow-check`, `process-flow-render` |
| `survey-analytics-writer` | Drafts the survey readout and figure ledger from aggregate tables | none |
| `transcript-reader` | Reads one transcript into a numbered claim inventory with verbatim quotes and leading-question flags | none |
| `completeness-audit` | Compares a map or checklist against a reference model and returns about fifteen questions to ask | none |

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `discovery-workstream` | The rules file, sources, Run folder, four products and their DONE checklists for discovery work | none |
| `process-flow-workstream` | The method (evidence to claim inventory to stakeholder decisions to generated visuals to three audits to two variants), plus the staged folder, map file contract, commands and reviewer json blocks of a process-flow Run; includes a rules template | commands listed below |
| `interview-synthesis` | Turns three or more interview transcripts into a Read-Out and an anonymized Feedback by Topic | command `srt-transcript-collapse` |
| `transcript-tools` | Loaded by other skills: `srt-transcript-collapse` (SRT or WebVTT to one line per speaker turn) and `transcript-hygiene` (duplicate and undated transcripts in a folder) | none |
| `workshop-design` | Assembles a workshop run of show from eight exercise cards; holds the workshop pack and session log templates | none |
| `survey-analytics-workstream` | The data fence, season jobs, readout shape and DONE checklist for a client survey season | none |
| `reference-process-models` | Reference models (order to cash, procure to pay, proposal to contract, record to report) for completeness audits | none |

## Scripts

Each script runs by path, `python3 ~/.claude/skills/<skill>/scripts/<script>.py`, and prints `--help`. A command name used elsewhere in this README, such as `trial-balance`, is a label for the script of that name with underscores (`trial_balance.py`). Nothing is installed.

**`process-flow-workstream`**
- `process_flow_prepare.py`: stages one engagement process into a Run folder, writing nothing outside it.
- `claim_ledger.py`: builds the claim ledger from the inventories and records each review (`build`, `add`, `brief`, `record`, `memo`).
- `process_flow_check.py`: whether the process map is done, with every map error by step.
- `process_flow_render.py`: draws the current map version into HTML pages and a narrative.
- `process_flow_publish.py`: writes the staged folder back to the engagement and its drafts to the delivery folder, never overwriting.
- `process_flow_template.py`: stamps the swim-lane generator into an engagement folder, or runs its demo.
- `swimlane_generator.py`: the generic as-is and to-be swim-lane generator the template stamps.

**`transcript-tools`**
- `srt_transcript_collapse.py`: collapses an SRT or WebVTT transcript into speaker-attributed text.
- `transcript_hygiene.py`: finds duplicate and undated transcripts in a folder; reports only.

Planned but not yet written anywhere: `discovery-prepare`, `assessment-tally`, `scoping-check`, `discovery-check`, `discovery-publish`, `survey-season-check`, `survey-fence-check`.

### Settings and environment

The keys are described in [docs/settings.md](../docs/settings.md).

- `contexts_dir` (top level): where `process_flow_prepare.py` finds an engagement's Context by name.
- `[process-flow-workstream]`: `client_subfolder`, `delivery_dir`, `reference_models_dir` and `screenshot_command`, all optional; `process_flow_render.py` uses headless Chrome or Chromium for screenshots unless `screenshot_command` names another.
- Python 3.11 or later, with `pyyaml` and `openpyxl`, declared in each script's `# /// script` block.

## Depends on other departments

`orchestration-workstream` (software); `comms-confirm`, `portal-write-safety`, `task-stack-capture`, `meeting-summary`, `meeting-portal-notes`, `meeting-followup` (productivity); `fact-check`, `executive-red-team`, `numbers-reviewer`, `client-update-workstream` (reporting); `report-tieout` (accounting); `project-engagement-baseline` (projects); `unslop-deliverable`, `brand-guide` (marketing); `writing-seminar-builder` (learning); `bd-proposal-orchestrator` (sales).
