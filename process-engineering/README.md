# Process Engineering

The front half of a client engagement, before anything is built: reading a pre-engagement assessment, synthesizing stakeholder interviews, mapping a process as-is and to-be with every box traced to a quote, preparing and summarizing workshops, ranking what to automate with a business case, and running a recurring client survey season. For consultants and internal improvement teams who need findings a sponsor can read cold and an auditor can trace.

Most jobs work on an engagement named by its Context, a small file the runtime supplies that lists the engagement's folders by role (rules, transcripts, background, assessment exports). Each engagement keeps its own rules file (`DISCOVERY-RULES.md`, `PROCESS-FLOW-RULES.md` or `SURVEY-RULES.md`), which wins over every agent and skill. Nothing here contacts a client or sends anything: drafts stay in the Run folder for the owner's review.

## The plugin

This folder is a standalone Claude Code plugin named `process-engineering` (`.claude-plugin/plugin.json`), built the way [software](../software/README.md#the-plugin) is: one short main agent per job, one `process-engineering-worker` and one `process-engineering-reviewer` for dispatched work, the know-how in the jobs' skills as `##` sections, and every script a named command in `bin/` (`python3 scripts/build_bins.py process-engineering`). A main agent's first instruction is to load its skills with the Skill tool.

```bash
claude --plugin-dir ~/coding-projects/automation-toolbox/process-engineering --agent process-engineering:process-engineering-process-flow
```

From Sentinel, an Automation launches a main agent by name; the overlay's `subagents:` lists `process-engineering-worker` and `process-engineering-reviewer` (or the reviewer alone, for the jobs with no transcript reading).

## Jobs and agents

| Agent | Automation | What it does | Dispatches |
|---|---|---|---|
| `process-engineering-assessment-intake` | assessment-intake | Assessment CSV exports to an anonymized summary, interview topics and candidate opportunities | reviewer: recount and anonymity, red team |
| `process-engineering-discovery-synthesis` | discovery-synthesis | Interview transcripts to the Read-Out, the anonymized Feedback by Topic and the BASELINE | worker per transcript; reviewer: two facts halves, counts and anonymity, red team |
| `process-engineering-workshop` | discovery-workshop | Prepare: run of show, cards, pre-read. Summarize: priorities, owners, dates, parking lot | worker per transcript (summarize); reviewer: time box and pre-read, facts halves, red team |
| `process-engineering-process-flow` | process-flow | One process mapped as-is and to-be, every step citing a claim, done when `process-engineering-process-flow-check` passes | worker per transcript; reviewer: two facts halves, completeness, red team |
| `process-engineering-automation-scoping` | automation-scoping | A reviewed to-be map to a ranked backlog, business cases and issue notes | reviewer: numbers, completeness, tracing, red team |
| `process-engineering-survey-analytics` | survey-analytics (one per client) | A client survey season as a checklist; the readout from aggregate tables only, behind a data fence | reviewer: numbers and cell size, red team |
| `process-engineering-worker` | | One transcript read into a claim inventory (`transcript-tools`, section Read one transcript) | none |
| `process-engineering-reviewer` | | Independent PASS or FAIL against the named checklist section; edits nothing | none |

## Skills

| Skill | Run by | What it holds |
|---|---|---|
| `assessment-intake`, `discovery-synthesis`, `discovery-workshop`, `automation-scoping` | the four discovery jobs | Each job's Steps, its writing section and its DONE checklist |
| `discovery-workstream` | the discovery jobs, reviewer | The engagement and rules file, sources by id, the Run folder, conduct, claims and checks, questions; checklist Check a discovery draft |
| `process-flow-workstream` | process flow, by hand | The method (Phases 0 to 7), the Run's Steps, sections Draw a map version and Check the map; `contract.md` (folder, ids, map file, commands, json blocks); a rules template |
| `survey-analytics-workstream` | survey analytics, reviewer | The data fence, the season's jobs, Steps, sections Write the readout and Check the readout, DONE |
| `interview-synthesis` | discovery synthesis, by hand | The Read-Out and the anonymized Feedback by Topic, with `(Nx)` counts |
| `project-engagement-baseline` | discovery synthesis, by hand | Research reports, the BASELINE (section 2), the CONCEPT |
| `workshop-design` | discovery workshop, by hand | The run of show from eight exercise cards; the workshop pack and session log templates |
| `reference-process-models` | reviewer | Order to cash, procure to pay, proposal to contract, record to report, for a completeness check |
| `transcript-tools` (shared copy) | worker, main agents | `srt-transcript-collapse`, `transcript-hygiene`, section Read one transcript |
| `automation-backlog-format` (shared copy) | automation scoping | The backlog CSV, business case headings and issue note: the file contract with sales |
| `review-facts`, `review-numbers`, `review-red-team`, `review-completeness` (shared copies) | reviewer | The independent checklists |
| `orchestration-workstream`, `report-tieout`, `brand-guide`, `unslop`, `unslop-deliverable` (shared copies) | all | Conduct and return; the tie-out command; house style; plain writing |

## Commands

In `bin/`, one per script, each printing `--help`:

- `process-engineering-process-flow-prepare`: stages one engagement process into a Run folder, writing nothing outside it (the process-flow Automation's prepare step).
- `process-engineering-claim-ledger`: builds the claim ledger from the inventories and records each review (`build`, `add`, `brief`, `record`, `memo`).
- `process-engineering-process-flow-check`: whether the map is done, with every map error by step.
- `process-engineering-process-flow-render`: draws the current map version into HTML pages and a narrative.
- `process-engineering-process-flow-publish`: writes the staged folder back to the engagement and its drafts to the delivery folder, never overwriting (the finish step).
- `process-engineering-process-flow-template`, `process-engineering-swimlane-generator`: the by-hand generator and its stamp.
- Shared copies keep one unprefixed name: `srt-transcript-collapse`, `transcript-hygiene` (`transcript-tools`), `report-tieout`.

Planned but not yet written: `discovery-prepare`, `assessment-tally`, `scoping-check`, `discovery-check`, `discovery-publish`, `survey-season-check`, `survey-fence-check`.

### Settings and environment

The keys are described in [docs/settings.md](../docs/settings.md).

- `contexts_dir` (top level): where `process-engineering-process-flow-prepare` finds an engagement's Context by name.
- `[process-flow-workstream]`: `client_subfolder`, `delivery_dir`, `reference_models_dir` and `screenshot_command`, all optional. Unset, `reference_models_dir` is this plugin's `reference-process-models` skill. `process-engineering-process-flow-render` uses headless Chrome or Chromium for screenshots unless `screenshot_command` names another.
- Python 3.11 or later, with `pyyaml` and `openpyxl`, declared in each script's `# /// script` block.

## Hand-offs between jobs

A hand-off is a line in the report (the Automation's `for_owner`) or a file another job reads, never a dispatch:

- Assessment intake → discovery synthesis: the summary, once filed in `working`, is read as `A01`; the report asks to adopt the topics and to arm discovery synthesis once the interviews are done.
- Discovery synthesis → process flow: one "launch `process-flow` for engagement X, process `<slug>`" line per process the BASELINE names.
- Workshop summarize → discovery synthesis: the workshop transcript is a source the next synthesis Run picks up.
- Process flow → automation scoping: after the owner has reviewed the map ("after your review, launch `automation-scoping`").
- **Automation scoping → sales.** The backlog CSV and business cases are filed in the engagement's `working` folder in the `automation-backlog-format` contract, which sales holds a copy of; the report says "chosen items: launch the sales `bd-proposal` Automation with the backlog path". The sales README names the same contract.
- **Automation scoping → software.** Each item's issue note is written in the issue standard; the owner files the chosen ones as Portal notes, which the software issue harvest turns into GitHub issues. This plugin never touches GitHub or the Portal.

## Decisions taken in the conversion

- **Plugin name kept as `process-engineering`** (migration plan D9 proposed `process`). Decided: keep it. The rename touches every other department's links and the shared manifest while eight departments convert at once; it can follow as its own change.
- **Questions go in the report, not through `comms-confirm`.** Decided, as productivity and software do: unattended Runs never ask live, so each question is a numbered `for_owner` line with a recommendation. `comms-confirm` is no longer copied here, and the Automations drop its `confirm.py` grant.
- **`reference-process-models` stays a skill of this plugin** rather than folding into `review-completeness` (plan open question 3). Decided: `process-engineering-process-flow-prepare` keeps finding it here by its stable skill path, and the shared checklist already points to it "where the department holds it".
- **The reviewer keeps `contract.md`'s json blocks** for process-flow reviews (plan open question 2): the job section Check the map sets the return, overriding each checklist's own, so `process-engineering-claim-ledger record` reads them unchanged.
- **Scoping's chosen items reach software as issue notes the owner files** (plan open question 4). Decided: no new Portal writer; a finish-step poster is a later tool.
- **`transcript-tools` moved to `shared/skills/`** with the new section Read one transcript, so other departments copy it; its commands lost the department prefix.
- **`project-engagement-baseline` moved here from projects** (plan D10): discovery synthesis drafts the BASELINE by its section 2.
- **The worker stays on sonnet** (plan open question 6); a brief may raise the model where a transcript needs it.

## Renamed in the conversion (2026-10)

| Now | Was |
|---|---|
| `process-engineering-assessment-intake` | `assessment-intake-orchestrator` |
| `process-engineering-discovery-synthesis` | `discovery-synthesis-orchestrator` |
| `process-engineering-workshop` | `workshop-orchestrator` |
| `process-engineering-process-flow` | `process-flow-orchestrator` |
| `process-engineering-automation-scoping` | `automation-scoping-orchestrator` |
| `process-engineering-survey-analytics` | `survey-analytics-orchestrator` |
| `process-engineering-worker` on `transcript-tools`, section Read one transcript | `transcript-reader` |
| the main agent, on each job skill's writing section | `discovery-writer` |
| the main agent, on `process-flow-workstream`, section Draw a map version | `process-flow-mapper` |
| the main agent, on `survey-analytics-workstream`, section Write the readout | `survey-analytics-writer` |
| `process-engineering-reviewer` on `discovery-workstream`, section Check a discovery draft | `discovery-checker` |
| `process-engineering-reviewer` on `review-completeness` (other departments too, until they convert) | `completeness-audit` |
| `process-engineering-reviewer` on `review-facts`, `review-numbers`, `review-red-team` | `fact-check`, `numbers-reviewer`, `executive-red-team` (reporting) |
| the job skills `assessment-intake`, `discovery-synthesis`, `discovery-workshop`, `automation-scoping` | `discovery-workstream`'s four products |
| commands (`process-engineering-process-flow-check`) | script paths (`python3 .../process_flow_check.py`) |

## Depends on other departments

None at run time: what it needs from elsewhere is copied in from `shared/skills/` (`orchestration-workstream`, `transcript-tools`, `automation-backlog-format`, the four `review-*` checklists, `report-tieout`, `brand-guide`, `unslop`, `unslop-deliverable`).
