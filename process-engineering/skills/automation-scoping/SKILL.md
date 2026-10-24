---
name: automation-scoping
description: "The automation scoping job, run by process-engineering-automation-scoping, not for a user request: its Steps, the section Write the backlog and its DONE checklist. Turns one process's reviewed to-be map into a ranked automation backlog with a business case per top item, in the automation-backlog-format contract: every item tied to the map step it changes and the pain it answers, hours, rates and error cost from stated inputs only, estimates flagged. process-engineering-reviewer recomputes every value and rank, finds pains with no item, traces each item and reads the cases as the sponsor. Adds to discovery-workstream. Not for drawing the map (process-flow-workstream)."
user-invocable: false
---

# Automation scoping

The sponsor gets a ranked list of what to automate in one process and why, in money and hours the client's own people stated, with every item traceable to the map step it changes and the pain it answers. Where an input is a guess the backlog says so and asks. The backlog feeds the proposal and the build, through the files `automation-backlog-format` defines. This skill adds to `discovery-workstream`; read it first.

## Inputs

- **Engagement** (required): the name of its private Context.
- **Process** (required): the process slug; its map is `process-flows/<process>/maps/` in the `process-flows` Source.
- **Instructions** (optional): the owner's words for this Run; they override the defaults, never `DISCOVERY-RULES.md`.
- **Dry run** (optional): say which map version, ledger and assessment you would use and what you would dispatch; dispatch nothing and write only `STATUS.md`.

## Steps

1. [judgment] Orient. Read the Context, `DISCOVERY-RULES.md`, and the process's newest map version with its `CLAIM-LEDGER.csv` and verification memo; read an assessment summary from `working` when one is filed.
   → no rules file: stop
   → no to-be map (the report names "launch `process-flow` for this process first"): stop
2. [judgment] Register the map (`M01`), the ledger, the assessment and any client pricing input in `sources.json`.
   → dry run: step 5
3. [judgment] Write the backlog (section Write the backlog): the CSV, the business cases and the issue notes, in `automation-backlog-format`'s shape, with `drafts/claims.json`.
4. [hand-off: process-engineering-reviewer] Review, all in one message, each with the sources only: `review-numbers` with the CSV, the business cases and the inputs they cite (re-derive every `annual_value` and the ranking); `review-completeness` with the backlog and the map's pain list as the reference model (a pain with no item and no reason is a finding); `discovery-workstream`, section Check a discovery draft, item 1, with the CSV, the map and the ledger; `review-red-team` with only the business cases, the `Sponsor` as reader, one line of purpose and the rules' bar. Save each return to `reviews/`.
   → a wrong value, an untraced item, an unexplained pain or a grade under the bar: step 3 (max 1)
5. [judgment] Close. Write `DONE.md` item by item, `STATUS.md` and `LOG.md`. Report: items by rank with annual value and confidence, how many rest on estimates, pains left without an item and why, and as one numbered list each rate or volume marked `estimate` (with your recommendation) plus the hand-offs: "chosen items: launch the sales `bd-proposal` Automation with the backlog path as discovery notes" and "for a build: file each chosen item's issue note as a Portal note, which the software issue harvest turns into an issue".
   → reported: done

## Write the backlog

From the to-be map (`maps/map v<N>.json` and its `CLAIM-LEDGER.csv`) and, when present, the assessment summary, in the shapes `automation-backlog-format` gives:

- `drafts/Automation Backlog <process> <date>.csv`: one row per to-be change worth automating, each citing its `map_step` and `pain`; hours, rates and error costs only as a source states them, the source named, else the row is `estimate` and the input a question. `annual_value` is computed by the format's formula and nothing else.
- `drafts/Automation Backlog <process> <date>.md`: the ranking table and one business case per top item under the format's headings.
- `drafts/Automation Backlog <process> <date> issue notes.md`: one issue note per item in the format's issue standard, ready to file once chosen.

Rates follow the rules' `Rates` setting: no firm rate prices a client hour unless the setting says so. A map error is a finding for the process flow, never a change to the map.

## DONE

Copy into `DONE.md` and mark each item `met`, `open` or `n/a` with a reason, citing the file, line or review that proves it. Items marked (checker) rest on the reviewer's PASS.

1. Every item cites a to-be map step and the pain claim it answers (checker).
2. Every hour, rate and error cost names its source, or the row is marked `estimate` and the input is a question.
3. Every `annual_value` and the ranking recompute from the stated inputs (`review-numbers`).
4. Every pain on the map with no backlog item has a one-line reason (`review-completeness`).
5. Rates follow the rules' `Rates` setting; no firm rate prices a client hour unless it says so.
6. The red-team check, reading the business cases as the `Sponsor`, at or above the bar.
7. Every item has an issue note in the issue standard.
