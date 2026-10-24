---
name: bd-pipeline
description: "The weekly BD pipeline pass, run by sales-pipeline-review, not for a user request: its Steps and DONE checklist. Reads the pipeline from the system of record, has sales-worker judge the pursuits in batches and draft one nudge per stuck pursuit, has sales-reviewer check every staged draft, and writes pipeline.json, the proposed next-step tasks and the report against the target. Adds to bd-workstream, which holds the sections. Drafts only; nothing is sent. Not for one new lead (bd-lead-intake)."
user-invocable: false
---

# The weekly pipeline pass

Start each week with no pursuit adrift: every open pursuit has a next step and a date, every stuck one has its next message drafted and checked for the owner to send, and the owner sees the pipeline against its target on one page. The sections each step names are in `bd-workstream`; read it first.

## Inputs

- `bd_rules` (required): the owner's `BD-RULES.md` in the BD Context. Read it first; it wins.
- **Pursuit** (optional): one pursuit's name or ref. Default: every open pursuit.
- **Instructions** (optional): the owner's words for this Run; they override the defaults, never the rules.
- **Dry run** (optional): do everything except stage drafts; write each draft brief to `RUN/briefs/`, and `"dry_run": true` in the change set.
- `RUN` is the working folder; write only there, by absolute path.

## Steps

1. [judgment] Orient. `whoami`; read the rules and last week's `pipeline.json` if the BD working folder holds one.
   → the rules leave the system of record unset (read both and put the choice first in the questions): step 2
2. [judgment] Read the pipeline (section Read the pipeline) and write `RUN/pipeline-source.md`.
   → no open pursuit: step 6
3. [hand-off: sales-worker] Judge the pursuits, in batches of about ten, all at once (section Judge a batch of pursuits), each with its pursuit refs, the rules file's path and today's date. A pursuit a batch cannot place gets one research pass (section Research a person and a thread, model haiku), then a question.
4. [hand-off: sales-worker] Draft one nudge per stuck pursuit with a nudge intent, all at once, model opus (section Draft a message): recipient, thread ref, intent, source refs, who to copy per the rules, `agent_slug` `sales-pipeline-review`.
   → dry run (each brief written to `RUN/briefs/` instead): step 6
5. [hand-off: sales-reviewer] Check every staged draft (section Check a staged draft), with the draft ids, the drafters' briefs and the rules file's path only.
   → FAIL: step 4 (max 1)
6. [judgment] Record and close. Write `RUN/pipeline.json` (the rows), `RUN/changes.json` (the next-step task ops, `"orchestrator": "sales-pipeline-review"`, `dry_run` as this Run is) or `RUN/pipeline.md` for a tracker; walk the DONE checklist into `RUN/done.md` with evidence per item. Report: open pursuits by stage and state against the target and last week; each stuck pursuit with its draft id and check; pursuits with no next step and why; each new lead as "launch the `bd-lead-intake` Automation for <ref>"; the questions as one numbered list the owner can answer "1) ok 2) no".
   → reported: done

A draft that fails twice is reported with the reviewer's fix and left for the owner.

## DONE

1. The pipeline was read from the system of record the rules name, dated this Run (cite the source and the count of open pursuits); or the record question is first on the owner's list.
2. Every open pursuit has a verb-first next step with a date today or later, or a question that says what is missing.
3. Every pursuit marked `stuck` has a staged draft nudge or a reason it has none (cooldown, already done, the owner's move).
4. Every staged draft passed the reviewer (section Check a staged draft), or its FAIL is reported with the fix.
5. No draft states a price, term or date the owner has not stated (the reviewer's test 4).
6. The count of open pursuits against the rules' target, and the change since last week, is in the report.
7. Every question is in the report's numbered list; every new lead is a launch line.
