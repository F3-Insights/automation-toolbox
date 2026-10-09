---
name: survey-analytics-workstream
description: Reference loaded by survey-analytics-writer and survey-analytics-orchestrator, not for a user request; what a recurring client survey season (an annual employee or culture survey) adds to orchestration-workstream. Covers SURVEY-RULES.md first, the data fence (agents read only the aggregate and structural files listed, never responses or free-text comments; client text goes only to the local models the contract allows), the season's jobs as an evidenced checklist, the readout from aggregate tables with every figure traced, and the DONE checklist.
---

# Survey analytics workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Load that skill by name if it is not loaded. It covers one client's survey season: the same instruments each year, data that arrives in a window, a pipeline that blinds, normalizes and categorizes it, and a readout and a formal submission at the end.

## The data fence (read first, every Run)

- **Client text never reaches a hosted model.** Survey contracts of this kind commonly forbid public AI models on client text. Agents in this workstream are hosted models. They never open, quote, summarize or classify a response, a free-text comment or a respondent or employee record, blinded or not.
- **Agents read only what the rules list.** `SURVEY-RULES.md` has an `## Agent-readable` list: structural metadata (question and response mappings, the category taxonomy), run logs and quality reports that hold counts and rates, and aggregate tables at or above the rules' minimum cell size. Anything not on the list is closed, whatever its name looks like. A file whose content turns out to hold client text is closed at once and reported.
- **The local pipeline does the client-text work.** Categorization and any other job on client text runs on the local models and scripts the rules name, started by a person (or, later, by the Automation's prepare step). This workstream plans, checks and reports on those runs from their counts; it never runs them on a hosted model.

## Conduct here

- **The rules file first.** `SURVEY-RULES.md` names the client by role, the instruments, the season's window and deadlines, the jobs and who runs each, the local pipeline's commands and outputs, the minimum cell size, the agent-readable list, the readout's audience and format, and the submission's recipient and format. It overrides this skill.
- **The season is a checklist.** `SEASON-<yyyy>.md` in the engagement folder lists each job with owner, due date, state (`not started`, `in progress`, `waiting`, `done`) and evidence (a run log, a quality report's counts, a file delivered).
- **Nothing leaves.** No upload to the client's platform, no submission, no message to the client. Those are the owner's or their team's steps, recorded as evidence when done.

## The jobs

| Job | Done when (evidence from agent-readable files) |
|---|---|
| `exports` | Every unit's export received, response counts by unit against invited, dated |
| `blinding` | Every reported cell at or above the minimum size; the blinding log's counts |
| `categorization` | Every comment classified on the local model; schema-valid rate, screened count, client review state, upload file built |
| `readout` | The executive readout drafted from aggregate tables, every figure traced, reviewed |
| `submission` | The formal blinded submission assembled to the recipient's format, owner-approved |

## The readout

`readout/Readout <yyyy> v<n>.md`: the headline findings, the composite scores by area against last year and the benchmark the rules name, the strengths and the areas to improve, and the comment themes by category count only. Every figure carries a hidden source comment naming the aggregate table and cell (`<!-- src: <file>:<row>,<col> -->`). Plus `readout/figures.csv`: `figure, value, source_file, row, col, derivation`.

## The return here

The shared block with these item tests and states:

| Test | Item | States |
|---|---|---|
| `job` | a job name | `not-started`, `in-progress`, `waiting`, `done` |
| `figure` | a readout figure id | `traced`, `untraced` |
| `fence` | a file | `readable`, `closed` |

## DONE (survey-analytics-orchestrator checks each item and cites its evidence)

1. No file outside the rules' agent-readable list was opened this Run (cite the files read).
2. `SEASON-<yyyy>.md` has every job with a state and evidence, and every past-due job has a question or a dated next step.
3. Each finished local run's counts are recorded: comments in, classified, schema-valid, screened for review (cite the run log or quality report).
4. Every readout figure is in `figures.csv` and `numbers-reviewer` re-derives it from the aggregate table it cites (PASS).
5. No reported cell is under the minimum size (the reviewer's check).
6. `executive-red-team`, reading as the client's sponsor, finds no section below the bar without a fix applied or reported.
7. Nothing was uploaded, submitted or sent.

## Later tools

- `survey-season-check`: compute DONE items 2 and 3 from the season file and the local runs' logs; `--precheck` says WORK when a run finished or a deadline is within a week.
- `survey-fence-check`: list the files a Run opened against the agent-readable list.
- A `prepare:` step that runs the local categorization pipeline and writes only its counts.
