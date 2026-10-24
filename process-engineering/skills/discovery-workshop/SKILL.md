---
name: discovery-workshop
description: "The discovery workshop job, run by process-engineering-workshop in mode prepare or summarize, not for a user request: its Steps, the sections Write the workshop pack and Write the workshop summary, and both DONE checklists. Prepare builds the run of show, exercise cards and pre-read by workshop-design, with the time box and pre-read checked and the pre-read red-teamed as a participant; summarize turns the workshop transcripts and artefacts into a fact-checked summary of priorities with owners, artefacts and dates, decisions and the parking lot. Adds to discovery-workstream. Not for a training seminar; by hand, use workshop-design."
user-invocable: false
---

# Discovery workshop

Before the workshop, the facilitator has a timed run of show whose last output is the artefact the workshop exists to produce, the cards for each exercise and a pre-read the room can act on. After it, the client has a summary within three business days: the priorities chosen, each with an owner, a first artefact and a date, the decisions and the parking lot, each traced to what was said or made in the room. This skill adds to `discovery-workstream`; read it first.

## Inputs

- **Engagement** (required): the name of its private Context.
- **Mode** (required): `prepare` or `summarize`.
- **Workshop** (optional): its date or name. Default: the rules' `Workshop` setting.
- **Instructions** (optional): the owner's words for this Run; they override the defaults, never `DISCOVERY-RULES.md`.
- **Dry run** (optional): say what you would draft and dispatch; dispatch nothing and write only `STATUS.md`.

## Steps

1. [judgment] Orient. Read the Context, `DISCOVERY-RULES.md`, `ENGAGEMENT-CONTEXT.md` and the `working` Source for an earlier pack or summary of this workshop.
   → no goal, date, time box or room in `Workshop` and the instructions (the gap goes in the report): stop
   → dry run: step 8
   → mode summarize: step 4
2. [judgment] Write the workshop pack (section Write the workshop pack), with `drafts/claims.json` for its facts.
3. [hand-off: process-engineering-reviewer] Two checks at once, with the sources only: `discovery-workstream`, section Check a discovery draft, prepare items 2 and 4, with the pack and the rules file's path; `review-red-team` with only the pre-read, a participant as reader, one line of purpose and the rules' bar. Save each return to `reviews/`.
   → a FAIL or a grade under the bar: step 2 (max 1)
   → passed: step 8
4. [script] Register the workshop's transcripts and artefacts in `sources.json` with halves; collapse each subtitle export with `srt-transcript-collapse <file> --out <RUN>/sources`.
5. [hand-off: process-engineering-worker] Read. One worker per workshop transcript, all in one message, each told to follow `transcript-tools`, section Read one transcript, with its file, `Source id`, the rules' `Topics` and the transcript json block from `process-flow-workstream`'s `contract.md`. Save each return to `inventories/<id>.md`.
   → a return without its json block: step 5 (max 1)
6. [judgment] Write the workshop summary (section Write the workshop summary), with `drafts/claims.json`.
7. [hand-off: process-engineering-reviewer] Review, all in one message: `review-facts` on half A's sources only and on half B's only, each with `drafts/claims.json`; `discovery-workstream`, section Check a discovery draft, summarize item 2, with the summary, the inventories and the artefacts. Save each return to `reviews/`.
   → a CONTRADICTED verdict or a FAIL: step 6 (max 1)
8. [judgment] Close. Write `DONE.md` for the mode's checklist with evidence, `STATUS.md` and `LOG.md`. Report: for prepare, the run of show's total against the time box and the red-team grade; for summarize, the priorities with owners and dates, the parking lot count, the DONE items open, and the hand-off "the next `discovery-synthesis` Run picks up the workshop transcript as a source". Questions (a priority with no owner, a date nobody said) go as one numbered list with your recommendation.
   → reported: done

## Write the workshop pack

By `workshop-design` (its Steps and rules) and the templates it holds (`references/workshop-exercise-cards.md`, `references/discovery-workshop-pack.md`), from the rules' `Workshop` setting:

- `drafts/Workshop Run of Show <date>.md`: the timed table (time, exercise, output, who leads, materials), the facilitator notes per exercise and the materials list.
- `drafts/Workshop Pre-Read <date>.md`: what the room should know and bring, under 120 words in the ask, with no threatening metric words and nothing the rules mark confidential.
- `drafts/Workshop Cards <date>.md`: each exercise's card, adapted from the template, never a new invention.

The last row's output is the artefact the `Workshop` goal names. A card whose people are not in the room is named, with the pre-read or pre-interview that substitutes.

## Write the workshop summary

`drafts/Workshop Summary <date>.md`, from the inventories and the artefacts: the priorities chosen, each with an owner, a first artefact and a date; the decisions; the parking lot; the scope boundary as stated in the room. Every priority, owner, date and decision cites a claim id or an artefact id. An owner or date nobody said is not written: it is a question.

## DONE: prepare

1. The last row's output is the goal artefact `Workshop` names.
2. The durations, transitions and breaks add up to the time box (checker).
3. Every exercise is a card from the template, adapted, not a new invention; the people each card needs are in the room.
4. The pre-read holds nothing the rules mark confidential and names no one's feedback (checker).
5. The red-team check, reading the pre-read as a participant, at or above the bar.

## DONE: summarize

1. Every workshop transcript and artefact is in `sources.json` and every transcript has an inventory.
2. Every priority, owner, date and decision cites a transcript location or artefact (checker).
3. Both facts halves recorded; no CONTRADICTED left.
4. The summary is dated within three business days of the workshop, or the delay is named.
5. The hand-off to discovery synthesis is named in the report.
