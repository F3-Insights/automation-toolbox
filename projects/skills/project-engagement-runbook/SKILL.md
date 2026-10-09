---
name: project-engagement-runbook
description: A default eight-step consulting engagement lifecycle (sponsor prep, discovery workshop, contract, kickoff, interviews, weekly updates, findings readout, build), each step naming its deliverable and the skill or tool that makes it. Use at the start of an engagement to lay out the plan and scaffold the folders, or mid-engagement for "what step comes next". It points to the skill that does each step (for example project-engagement-kickoff-orchestrator, interview-synthesis, comms-client-status-update) rather than doing it.
argument-hint: "[client] [workstream] [start | where-are-we | next]"
allowed-tools: Read, Glob, Grep, Write, Bash(python3 ~/.claude/skills/project-engagement-workstream/scripts/engagement_folders.py:*), mcp__insights-portal__get, mcp__insights-portal__list_entities, mcp__insights-portal__search
---

# Engagement runbook

This is a default pattern for a consulting engagement, from a first sponsor call to a findings readout and, where the firm also implements, the build. Every step, and every duration, fee, cadence, document name and folder name below, is a starting default for any consultancy: change, reorder or drop them to fit the firm and the engagement, and record the firm's own version in the client repo's `docs/RUNBOOK.md`. Every step has a deliverable and a maker. Skip a step deliberately, not by forgetting.

## The eight steps

**1. Sponsor prep.** One-to-one calls with the sponsor and their direct reports. Their ideas and complaints go into `collected-ideas.csv` (Source, Evidence, Group, Category, Item). Write the INTERNAL prep brief: room roster, idea clusters, landmines with a room-safe version of each, open items, pocket questions. If time data arrives, run the hours Pareto. Maker: a quick-capture skill for the ideas, this skill for the brief; the Pareto is a kit tool once built.

**2. Discovery workshop.** Often paid, for example at a small fixed fee, so the client has committed before the contract. Present the map of what was heard. Co-select three priorities with the room, each with an owner, a first artifact, and a date. Parking lot for the rest. State the scope boundary once, early. Maker: the discovery-workshop pack (facilitation plan, live impact/effort deck, post-workshop summary within a few business days).

**3. Contract.** A prompt thank-you note, then the workshop summary. The firm's contract set, for example a master agreement, an exhibit on software and IP where the work produces any, and a statement of work with Background, Goals, Scope, Methodology, Terms and Acceptance. Red-team the package with `executive-red-team` before it goes, and send it when the sponsor will have time to read it. Defaults worth considering, each one changeable: qualitative goals, no named client staff in the SOW, "which may include" on scope, invoicing terms stated once, a bullet that lets the timeline flex. Maker: `unslop-proposal` for the edit pass; the package templates once built.

**4. Post-signature setup.** In order: the IT or admin one-to-one first (access, auth paths, sandbox, what can be exported); the sponsor framing note (short bullets, every word load-bearing); invite the technical voices; the sponsor-issued all-staff announcement (no threatening metric words); interview invites via the coordinator (for example 60 minutes each, inside a two-week window). Scaffold the folders with `engagement-folders` (its default subfolders are From Client, Shared with Client, Transcripts, Consultant Transcripts, Weekly Report and Kick off Material; rename them to the firm's own) and, where the firm keeps one, a sibling `<firm>-<client>` repo. Maker: `comms-draft-email` for each note.

**5. Kickoff.** One deck per workstream: team, focus areas lifted from the SOW with the active one boxed, what we heard reframed positively, a decide track and a build track, short sprints (two weeks is a common default), first-sprint targets. Plus a brief on the firm's delivery method, for example Align, Set up, Specify, Build and iterate. Maker: `writing-seminar-builder` with the kickoff template once built.

**6. Interviews and synthesis.** Recorded interviews (60 minutes is a common length), with a technical member of the team present where the work will touch systems (some firms call this role a forward-deployed engineer: the engineer who works directly alongside the client's team). Collapse the transcripts, then `interview-synthesis` produces the Read-Out and the anonymized Feedback by Topic. From those: per-source research reports, a BASELINE (one page, evidence by capability, exists and lacks, ranked tensions), a CONCEPT with numbered positions, a decisions log. Maker: `srt-transcript-collapse`, `interview-synthesis`, `software-grill-with-docs` for the decisions.

**7. Cadence and readout.** `comms-client-status-update` on the cadence agreed with the client (weekly is common). Findings readout goes to sponsors before executives: recommended-then versus happening-now, findings by category as unattributed cards, external evidence, what could be automated, what is still open, conclusions in the owner's words. Mock-ups are referenced, not shown first. Maker: `comms-client-status-update`, `executive-red-team` and `fact-check` on the readout.

**8. Build** (for a firm that implements; an advisory-only engagement ends at step 7). IT asks list first (auth, schema export, sandbox, approval locks, change capture, residency), then build waves in short sprints. Every write to a client system sits behind human approval. Maker: the software skills; the register kit for open items once built.

## Folder discipline, which is half the method

`<Client> - General/` holds kickoff and workshop materials and the general transcript folder. `<Client> - YYYY-MM <Workstream>/` per workstream, each with the standard subfolders (the six `engagement-folders` creates by default, or the firm's own). **From Client** and **Shared with Client** are the two directions of the boundary; nothing shared goes anywhere else, so the question "what have they seen" always has one answer. Filenames carry the date; the date in the filename is authoritative over the file's mtime.

## Using this skill

- `start <client> <workstream>`: scaffold folders and the repo, write the step-1 prep brief skeleton, list the eight deliverables with empty checkboxes in `docs/RUNBOOK.md` in the client repo.
- `where-are-we <client>`: read the client repo's `docs/RUNBOOK.md` and the engagement folder contents (under the owner setting `engagements_dir`), tick what exists, name the current step.
- `next <client>`: the next unticked step, its deliverable, its maker, and the two or three inputs it needs that are missing.

Do not run steps; this skill orients and scaffolds. The makers named above do the work.
