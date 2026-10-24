---
name: survey-analytics-workstream
description: "The client survey season job (an annual employee or culture survey), run by process-engineering-survey-analytics and checked by process-engineering-reviewer, not for a user request; adds to orchestration-workstream. Covers SURVEY-RULES.md first, the data fence (the session reads only the aggregate and structural files listed, never responses or free-text comments; client text goes only to the local models the contract allows), the season's jobs as an evidenced checklist, its Steps, the sections Write the readout and Check the readout, and the DONE checklist."
user-invocable: false
---

# Survey analytics workstream

This skill extends `orchestration-workstream`: keep its conduct. It covers one client's survey season: the same instruments each year, data that arrives in a window, a pipeline that blinds, normalizes and categorizes it, and a readout and a formal submission at the end. Get the season delivered on time with nothing lost and no client text exposed: every job tracked with evidence, every local run's counts recorded, and the readout drafted and checked so the owner reviews instead of builds.

## Inputs

- **Survey Context** (required): the engagement folder with `SURVEY-RULES.md` (read first; it wins, its `## Agent-readable` list above all) and `SEASON-<yyyy>.md`.
- **Season** (optional, yyyy). Default: the current season in the rules.
- **Job** (optional): `status` (the checklist only), `readout`, or `all`. Default: `status`.
- **Instructions** (optional): override the defaults here, never the rules file.
- **Dry run** (optional): work in the Run folder only; write nothing in the engagement folder.
- `RUN` is the working folder.

## The data fence (read first, every Run)

- **Client text never reaches a hosted model.** Survey contracts of this kind commonly forbid public AI models on client text. The session, and every agent it dispatches, is a hosted model: none opens, quotes, summarizes or classifies a response, a free-text comment or a respondent or employee record, blinded or not.
- **Only what the rules list is read.** `SURVEY-RULES.md` has an `## Agent-readable` list: structural metadata (question and response mappings, the category taxonomy), run logs and quality reports that hold counts and rates, and aggregate tables at or above the rules' minimum cell size. Anything not on the list is closed, whatever its name looks like. A file whose content turns out to hold client text is closed at once and reported. Every file opened is logged in `RUN/fence.md`; the reviewer is briefed with agent-readable files only.
- **The local pipeline does the client-text work.** Categorization and any other job on client text runs on the local models and scripts the rules name, started by a person (or, later, by the Automation's prepare step). This workstream plans, checks and reports on those runs from their counts; it never runs them on a hosted model.

## Conduct here

- **The rules file first.** `SURVEY-RULES.md` names the client by role, the instruments, the season's window and deadlines, the jobs and who runs each, the local pipeline's commands and outputs, the minimum cell size, the agent-readable list, the readout's audience and format, and the submission's recipient and format. It overrides this skill.
- **The season is a checklist.** `SEASON-<yyyy>.md` in the engagement folder lists each job with owner, due date, state (`not started`, `in progress`, `waiting`, `done`) and evidence (a run log, a quality report's counts, a file delivered).
- **Nothing leaves.** No upload to the client's platform, no submission, no message to the client. Those are the owner's or their team's steps, recorded as evidence when done.
- **Questions** (a late job, a missing export, a decision) go in the report as one numbered list with your recommendation, never asked live.

## The jobs

| Job | Done when (evidence from agent-readable files) |
|---|---|
| `exports` | Every unit's export received, response counts by unit against invited, dated |
| `blinding` | Every reported cell at or above the minimum size; the blinding log's counts |
| `categorization` | Every comment classified on the local model; schema-valid rate, screened count, client review state, upload file built |
| `readout` | The executive readout drafted from aggregate tables, every figure traced, reviewed |
| `submission` | The formal blinded submission assembled to the recipient's format, owner-approved |

## Steps

For `process-engineering-survey-analytics`.

1. [judgment] Fence. Read the rules and the agent-readable list; start `RUN/fence.md` and log every file opened from here on.
   → no rules file: stop
2. [judgment] Status. Read `SEASON-<yyyy>.md` and the local pipeline's run logs and quality reports; set each job's state and evidence and record each finished run's counts. Write the season file (dry run: `RUN/SEASON-<yyyy>.md`).
   → job `status`: step 5
   → categorization not done (the readout waits; say so): step 5
3. [judgment] Write the readout (section Write the readout).
4. [hand-off: process-engineering-reviewer] Two checks at once, with agent-readable files only: this skill's section Check the readout, with the readout, `figures.csv` and the aggregate tables it cites; `review-red-team` with only the readout, the client's sponsor as reader and one line of purpose. Save each return to `RUN/reviews/`.
   → a FAIL or a section under the bar: step 3 (max 1)
5. [judgment] Close. Walk the DONE checklist, citing evidence per item, and append to the engagement's `LOG.md` (dry run: `RUN/LOG.md`). Report: each job's state with evidence, the recorded run counts, the readout's path and the review verdicts, files closed by the fence, the DONE checklist, and the questions as one numbered list the owner can answer "1) ok 2) no".
   → reported: done

## Write the readout

Run by the main agent, from agent-readable files only. `readout/Readout <yyyy> v<n>.md`: the headline findings, the composite scores by area against last year and the benchmark the rules name, the strengths and the areas to improve, and the comment themes by category count only. Every figure carries a hidden source comment naming the aggregate table and cell (`<!-- src: <file>:<row>,<col> -->`). Plus `readout/figures.csv`: `figure, value, source_file, row, col, derivation`. A revision is `v<n+1>` and answers every finding: fixed, or why not in the report.

## Check the readout

For `process-engineering-reviewer`, given the readout, `figures.csv`, the aggregate tables it cites and the rules file's path, never the maker's reasoning. Read the rules' agent-readable list first and open nothing else. Follow `review-numbers` (re-derive every figure in `figures.csv` from the cell it cites), plus:

- **Minimum cell size.** Every figure the readout reports rests on a cell at or above the rules' minimum; a smaller cell is a FAIL whatever its value.
- **Category counts only.** A comment theme is a category and its count; any quoted or paraphrased comment is a FAIL.

Return `review-numbers`' verdict and findings, with each cell-size and quotation finding numbered among them.

## DONE (the main agent checks each item and cites its evidence)

1. No file outside the rules' agent-readable list was opened this Run (cite `RUN/fence.md`).
2. `SEASON-<yyyy>.md` has every job with a state and evidence, and every past-due job has a question or a dated next step.
3. Each finished local run's counts are recorded: comments in, classified, schema-valid, screened for review (cite the run log or quality report).
4. Every readout figure is in `figures.csv` and re-derived from the aggregate table it cites (the reviewer's PASS).
5. No reported cell is under the minimum size (the reviewer's check).
6. The red-team check, reading as the client's sponsor, finds no section below the bar without a fix applied or reported.
7. Nothing was uploaded, submitted or sent.

## Later tools

- `survey-season-check`: compute DONE items 2 and 3 from the season file and the local runs' logs; `--precheck` says WORK when a run finished or a deadline is within a week.
- `survey-fence-check`: list the files a Run opened against the agent-readable list.
- A `prepare:` step that runs the local categorization pipeline and writes only its counts.
