---
name: tech-portfolio-workstream
description: Reference loaded by tech-portfolio-collector, tech-portfolio-writer and tech-portfolio-orchestrator, not for a user request; adds to orchestration-workstream. Covers a portfolio of projects owned by other people, reviewed weekly from the owners' own updates, meetings and mail; the register and the rules file; the dated status row with its source; how a slipped date is detected; the steering pack's contract; and the DONE checklist.
---

# Technology portfolio workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Load it by name if it is not loaded. What follows is only what the portfolio review adds.

The work: a client's portfolio of technology and automation projects, each with its own owner, gets a weekly status the owner can stand behind in the steering meeting. Status comes from the project owners' own words (their status decks, the steering meeting's notes and transcript, their mail), never from an agent's impression. The owner of this review is the only audience: nothing goes to a project owner except through them.

## The folder

The Context binds the portfolio folder:

- `PORTFOLIO-RULES.md`: where the register is and how its columns map, the status vocabulary the steering meeting uses, the meeting's day, where owners' updates land, the Portal domain and projects that track the portfolio, the steering pack's format, and what an agent may write. It wins over this skill.
- The register (a CSV the client keeps): one row per project. Read only.
- `{yyyy}/{yyyy-mm-dd}/`: one folder per steering date, written by the orchestrator: `status.json`, `STEERING-PACK.md`, `questions.md`, the reviews, `LOG.md`.

## The status row

One per project per week:

```json
{"project": "<register id>", "name": "...", "owner_role": "...",
 "status": "<the rules' vocabulary>", "as_of": "2026-10-02",
 "summary": "one or two sentences in the owner's own terms",
 "next_milestone": {"what": "...", "date": "2026-10-30", "baseline": "2026-10-15"},
 "slipped": true, "slip_days": 15, "blockers": ["..."],
 "adoption": "training or usage signal, or null",
 "sources": ["<path or portal ref>"], "stale": false}
```

- `as_of` is the date of the newest source, not today. A project with no source in the rules' freshness window (default 14 days) is `stale: true` and its status is carried, marked carried.
- A date slipped when the newest source's date for a milestone is later than the baseline in the register or last week's status. Each slip is a question to the owner, who relays it.
- Differences between the register and the Portal projects (a project in one only, a different status) are findings.

## The steering pack

`STEERING-PACK.md`, in the rules' format: a one-screen summary (what changed, what slipped, what needs a decision), then one block per project in register order. Every sentence carries its source ids in a hidden `<!-- src: ... -->` comment. No adjective an owner did not use.

## DONE checklist

The orchestrator checks each against the week folder; starred lines rest on the reviewers.

1. Every project in the register has a status row with `as_of` and at least one source, or is marked stale with the date of its last source.
2. Every slipped date is a question in `questions.md`, addressed to the owner.
3. Every register and Portal difference is a finding.
4. * Two `fact-check` instances over disjoint source halves found no contradicted claim left in the pack.
5. * `executive-red-team` has no unanswered blocker.
6. Nothing was sent to a project owner or written outside the week folder.

## Later tools

- `portfolio-pack`: gathers each project's sources for the window (folder files with dates, Portal notes and transcripts, mail) into `sources.json` before the session.
- `portfolio-check --precheck`: a steering date within two days and no pack for it.
- A pptx text extractor for owners' status decks.
