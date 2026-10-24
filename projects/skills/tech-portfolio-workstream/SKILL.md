---
name: tech-portfolio-workstream
description: "The technology portfolio review, loaded by projects-tech-portfolio and by the projects-worker and projects-reviewer it dispatches, not for a user request; adds to orchestration-workstream. Covers a portfolio of projects owned by other people, reviewed weekly from the owners' own updates, meetings and mail; the register and the rules file; the Steps; the sections Collect a batch, Write the steering pack and Check the pack; the dated status row and slip detection; and the DONE checklist. For the weekly pack, start projects-tech-portfolio."
---

# Technology portfolio workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Load it by name if it is not loaded. What follows is only what the portfolio review adds.

The work: a client's portfolio of technology and automation projects, each with its own owner, gets a weekly status the owner can stand behind in the steering meeting. Status comes from the project owners' own words (their status decks, the steering meeting's notes and transcript, their mail), never from an agent's impression. The owner of this review is the only audience: nothing goes to a project owner except through them.

## The folder

The Context binds the portfolio folder:

- `PORTFOLIO-RULES.md`: where the register is and how its columns map, the status vocabulary the steering meeting uses, the meeting's day, where owners' updates land, the Portal domain and projects that track the portfolio, the steering pack's format, and what an agent may write. It wins over this skill.
- The register (a CSV the client keeps): one row per project. Read only.
- `{yyyy}/{yyyy-mm-dd}/`: one folder per steering date, written by the main agent: `status.json`, `STEERING-PACK.md`, `questions.md`, the reviews, `LOG.md`.

## Inputs

- **Steering date** (default: the next one the rules name).
- **Window days** (default 7, or since the last pack).
- **Projects** (optional): only these register ids.
- **Instructions** (optional): the owner's words for this Run.
- **Dry run**: do everything, writing only under `RUN/`.

## Steps

For `projects-tech-portfolio`.

1. [judgment] Orient. Read `PORTFOLIO-RULES.md`, the register, and last week's `status.json`, `questions.md` and `STEERING-PACK.md`. Read the Portal domain's projects once (`hierarchy`). Split the projects into batches of about five and write `RUN/plan.json`: each batch's projects, their Portal project ids and last week's rows.
2. [hand-off: projects-worker] One worker per batch, in parallel, on section Collect a batch, with its projects, last week's rows, the window and the rules file's path. Save each return to `RUN/returns/<batch>.json` as it arrives.
3. [judgment] Assemble `status.json` from the rows. List each slip as a question in `questions.md`, addressed to the owner, and each register-to-Portal difference as a finding.
4. [judgment] Write the steering pack yourself, by section Write the steering pack.
5. [hand-off: projects-reviewer] Three reviewers in one message, each with the pack and its sources only: two on `review-facts`, each given a disjoint half of the sources (split by project), and one on `review-red-team` with the pack only, the steering committee as reader and the purpose "a steering committee's weekly portfolio review". Save each verdict to the week folder's reviews.
   → a contradicted claim or a red-team blocker: step 4 (max 1)
6. [judgment] Write the week folder (`status.json`, `STEERING-PACK.md`, `questions.md`, the reviews, `LOG.md`; under `RUN/` on a dry run). Walk the DONE checklist into `RUN/done.md` with a citation per line, and report: the pack's path, what changed this week, the slips as one numbered question list, stale projects, register differences, review findings left open, and the DONE result.
   → reported: done

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

## Collect a batch

For a `projects-worker` given one batch. Read `PORTFOLIO-RULES.md` first. Read only; write nothing. For each project:

1. Read the newest sources in the window: the owner's update files in the folder, the Portal project and its notes, the steering meeting's notes or transcript, mail about it (`email_bodies` only for the ones that decide it).
2. Write the status row in the shape above, in the owner's terms and the rules' vocabulary, `as_of` the newest source's date, every source cited.
3. Compare each milestone date with the baseline and last week's row; mark slips.
4. Nothing new in the window: carry last week's row, `stale` per the rules.

Return the `orchestration-workstream` block with `workstream: "collect-a-batch"`, the rows in `extra.rows`, one `items` row per project (`test` `status`, `state` the status), slips as `questions` `of: owner`, and register or Portal differences as `findings`.

## Write the steering pack

The main agent does this itself, from `status.json` and last week's pack only, in the rules' format.

1. Lead with one screen: what changed since last week, what slipped and by how much, what needs a decision and from whom.
2. Then one block per project in register order, from its status row only, in the owner's terms. Mark carried and stale rows as such.
3. Put `<!-- src: ... -->` after every sentence with the row's source ids. Invent nothing; a gap is a gap. No adjective an owner did not use.
4. On a revision, answer every finding: fixed, or why not, in `LOG.md`.

## Check the pack

The reviewer's checklists are `review-facts` (the pack's claims against its assigned half of the sources; a sentence's `src` comment says which sources it rests on) and `review-red-team` (the pack read cold by the steering committee). In addition, for the facts reviewers: a status word outside the rules' vocabulary, or a slip in the pack that is not in `questions.md`, is a finding.

## DONE

The main agent checks each against the week folder; starred lines rest on the reviewer.

1. Every project in the register has a status row with `as_of` and at least one source, or is marked stale with the date of its last source.
2. Every slipped date is a question in `questions.md`, addressed to the owner.
3. Every register and Portal difference is a finding.
4. * Two `review-facts` reviewers over disjoint source halves found no contradicted claim left in the pack.
5. * The `review-red-team` reviewer has no unanswered blocker.
6. Nothing was sent to a project owner or written outside the week folder.

## Later tools

- `portfolio-pack`: gathers each project's sources for the window (folder files with dates, Portal notes and transcripts, mail) into `sources.json` before the session.
- `portfolio-check --precheck`: a steering date within two days and no pack for it.
- A pptx text extractor for owners' status decks.
