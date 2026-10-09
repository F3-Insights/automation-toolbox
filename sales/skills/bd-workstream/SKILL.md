---
name: bd-workstream
description: Reference loaded by bd-pipeline-orchestrator, bd-lead-intake-orchestrator and bd-pursuit-analyst, not for a user request; what business development work adds to orchestration-workstream. Covers BD-RULES.md first, the pipeline read from the system of record the rules name (Portal BD domain or an action tracker file), the pursuit row (stage, owner, a dated verb-first next step, last touch, evidence), when a pursuit is stuck and earns a drafted nudge, the lead brief and fit score against the services list, outreach as staged drafts checked by comms-draft-checker, and both DONE checklists.
---

# BD workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Load that skill first if it is not loaded. Research is the research agents' (`person-researcher`, `domain-researcher`, `email-researcher`); drafting in the owner's voice is `email-drafter`'s; the check of a staged draft is `comms-draft-checker`'s. This skill adds what BD needs: a pipeline where every pursuit has a dated next step, and a lead answered fast with a brief, a fit score and a reply draft.

## Conduct here

- **The rules file first.** `BD-RULES.md` (its path comes from the Run's BD Context) names the system of record, the pipeline target, the services list and positioning documents, the voice sources, who is copied on BD mail, the stuck threshold and the cooldown. It overrides this skill.
- **One system of record.** The rules say `System of record: portal` (pursuits are projects in the BD domain, the next step a dated task) or `tracker` (an action-tracker file, one row per pursuit). Read the pipeline only from there. Anything else (a brain dump, a mail thread, an old tracker) is a source to compare and cite, never the record. If the rules leave it unset, read both, report the differences, and make the choice the first question to the owner.
- **Nothing is sent.** Every message to a prospect, referrer or partner is a Portal draft made by `email-drafter` and passed by `comms-draft-checker`. Nothing is pushed to Outlook, posted, scheduled or forwarded. The owner sends.
- **Price and terms are the owner's.** No draft states a price, rate, discount, scope, start date or availability the owner has not already stated in the record. Where the next step needs one, it is a question to the owner with a recommendation.
- **Pursuits, not relationships.** Only pursuits and leads get nudges here. General keeping in touch belongs to the relationship-tending workflow (`crm-relationship-tending-orchestrator`); a contact in its cooldown is left alone.
- **Already done?** Before proposing a next step or a nudge, look for what the owner already did: a sent mail, a meeting held or booked, a call logged, a proposal sent. Record it as evidence.

## The pursuit row

One row per open pursuit, in `pipeline.json` (`extra.pursuits` from the analyst):

`pursuit, ref, stage, owner, next_step, next_date, last_touch, last_touch_ref, state, nudge, evidence, note`

- `ref` is the record's id: `portal://project/<id>`, or the tracker file and row.
- `stage` is one of `lead`, `qualifying`, `proposal`, `negotiating`, `won`, `lost`, `parked`.
- `next_step` starts with a verb and names who does what ("Send the revised scope to the CFO"); `next_date` is yyyy-mm-dd, today or later.
- `state` is `moving` (touched inside the stuck threshold), `stuck` (no touch past the threshold, or the last word is theirs and unanswered), `waiting` (we wrote last and the follow-up date is not here yet), or `closed` (won, lost or parked on evidence).
- `nudge` is empty, or the intent of one message: to whom, what it asks, why now, the source refs.

A proposed next-step task in the Portal is a `task-stack-apply` op in the change-set shape of `task-stack-workstream` (`create` or `edit`, the pursuit's project, a verb-first title, a due date). With a tracker, the proposed rows go in `pipeline.md` for the owner to copy; the tracker file is never edited.

## The lead brief

One page per inbound lead, `leads/<lead>.md`: who they are (person and company, from the researchers, every fact with its ref), how they came (referral, site form, mail), what they asked for in their words, the fit score, the questions to settle on the first call, and the reply intent.

**Fit score.** Score the lead 0 to 3 against the services list and positioning document the rules name, one point each for: the need is a service the owner sells; the buyer is the kind the positioning names; the size and timing are plausible from the record. Write each point as met, not met or unknown with its source. A lead at 0 or 1 gets a polite decline or referral intent; 2 or 3 gets a reply proposing a call. The owner approves the rubric in the rules; until they have, the score is advisory and says so.

## The return here

The shared block with these item tests and states, the rows in `extra.pursuits`, the proposed task ops in `extra.ops`, and each nudge or reply intent in `extra.nudges`:

| Test | Item | States |
|---|---|---|
| `next-step` | a pursuit | `dated`, `missing`, `past-due`, `closed` |
| `nudge` | a pursuit | `due`, `not-due`, `cooldown`, `already-done` |
| `fit` | a lead | `0`, `1`, `2`, `3`, `unknown` |

`questions` go to `owner` with `why` and `blocks` (the pursuit or lead ref).

## DONE: the weekly pipeline (bd-pipeline-orchestrator checks each item and cites its evidence)

1. The pipeline was read from the system of record the rules name, dated this Run (cite the source and the count of open pursuits); or the record question is first on the owner's list.
2. Every open pursuit has a verb-first next step with a date today or later, or a question to the owner that says what is missing.
3. Every pursuit marked `stuck` has a staged draft nudge or a reason it has none (cooldown, already done, the owner's move).
4. Every staged draft passed `comms-draft-checker`, or its FAIL is reported with the fix.
5. No draft states a price, term or date the owner has not stated (the checker's test 4).
6. The count of open pursuits against the rules' target, and the change since last week, is in the report.
7. Every question is on the owner's list (comms-confirm) or in the report's numbered list.

## DONE: one lead (bd-lead-intake-orchestrator checks each item and cites its evidence)

1. The lead is pinned: a Portal contact (or the inbound email) by id, not a name alone.
2. The brief exists, every fact in it carries a ref, and nothing in it is invented.
3. The fit score has each point marked with its source, or `unknown`.
4. One reply draft is staged in the lead's thread and passed `comms-draft-checker`, or the report says why none was drafted.
5. A pursuit is proposed in the system of record (a project and a dated next-step task, or a tracker row) at stage `lead`, unless the owner already made one.

## Later tools

- `bd-pipeline-pull`: read the pipeline from the Portal BD domain or the tracker file into one dated `pipeline.json` before the session starts, so it starts from data.
- `bd-pipeline-check`: compute DONE items 1, 2 and 6 from `pipeline.json`; `--precheck` says WORK when a pursuit has no dated next step or a prospect replied since the last Run.
- A step after the session that applies the proposed next-step tasks through `task-stack-apply`, once a dry run has been read.
