---
name: bd-lead-intake
description: "One inbound lead answered the day it arrives, run by sales-lead-intake, not for a user request: its Steps and DONE checklist. Pins the lead, researches the person and the thread, writes the one-page lead brief with a fit score, stages the reply draft and has sales-reviewer check it, and proposes the pursuit. Adds to bd-workstream, which holds the sections. Drafts only; nothing is sent. Not for the weekly pipeline pass (bd-pipeline)."
user-invocable: false
---

# One inbound lead

A new lead never waits on the owner's research. Within the day, the owner has a one-page brief on who they are and what they want, a fit score the owner can disagree with in one line, a reply draft in the thread ready to send, and the pursuit proposed in the pipeline. The sections each step names are in `bd-workstream`; read it first.

## Inputs

- `bd_rules` (required): the owner's `BD-RULES.md`, with the services list and positioning documents it names. Read it first; it wins.
- **Lead** (required): a `portal://contact/<id>` or `portal://email/<id>`; a name alone is resolved to one of these first.
- **Instructions** (optional): the owner's words for this Run; they override the defaults, never the rules.
- **Dry run** (optional): brief and score; write the draft brief to `RUN/briefs/` and stage nothing.

## Steps

1. [judgment] Pin. `whoami`; resolve the lead to one contact or email by id; look for an existing pursuit (the BD domain's projects, or the tracker) and any open draft to them.
   → the lead resolves to none or several (the question goes in the report): stop
   → already answered, or already a pursuit (say which, with its ref): stop
2. [judgment] Research the person and the inbound thread yourself (section Research a person and a thread), topic the inbound ask.
3. [judgment] Write the lead brief with its fit score (section Write the lead brief).
4. [judgment] Draft the reply yourself (section Draft a message), with the thread ref, the reply intent from the brief, who to copy per the rules, `agent_slug` `sales-lead-intake`.
   → dry run (the brief written to `RUN/briefs/` instead): step 6
   → BLOCKED (the question goes in the report): step 6
5. [hand-off: sales-reviewer] Check the draft (section Check a staged draft), with the draft id, the draft brief and the rules file's path only.
   → FAIL: step 4 (max 1)
6. [judgment] Propose the pursuit in `RUN/changes.json` (a `comment` op proposing the project on the lead's first task and a dated first next step, `"orchestrator": "sales-lead-intake"`), or a row in `RUN/pipeline.md` for a tracker. Walk the DONE checklist into `RUN/done.md` with evidence. Report: the lead and how it came, the fit score with each point, the brief's path, the draft id and its check, the proposed pursuit, and the questions as one numbered list.
   → reported: done

## DONE

1. The lead is pinned: a Portal contact (or the inbound email) by id, not a name alone.
2. The brief exists, every fact in it carries a ref, and nothing in it is invented.
3. The fit score has each point marked with its source, or `unknown`.
4. One reply draft is staged in the lead's thread and passed the reviewer, or the report says why none was drafted.
5. A pursuit is proposed in the system of record (a dated next step and the project proposal, or a tracker row) at stage `lead`, unless the owner already made one.
