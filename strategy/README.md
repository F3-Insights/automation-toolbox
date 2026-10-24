# Strategy

Keeps the owner's goals honest against what actually happens. Once a month the goal alignment sets the owner's goals against their projects and against where the time went (from productivity's time study), finds the gaps (goals with no project, projects with no goal, goals starved of time, time serving nothing), pre-fills the review of the owner's strategic goals document, and puts one numbered approval list to the owner. Nothing is written to the Portal until the owner approves. Before a strategic plan is committed to, a pre-mortem stress-tests it in two gates: the assumptions it rests on, then how it fails.

The strategic goals document and the review cadence are the owner's; they are named by settings (`[goal-alignment-workstream]` in [docs/settings.md](../docs/settings.md)), never written here.

## The plugin

This folder is a standalone Claude Code plugin named `strategy` (`.claude-plugin/plugin.json`), built the way [software](../software/README.md#the-plugin) and [productivity](../productivity/README.md) are: one short main agent per job, one `strategy-worker` and one `strategy-reviewer`, the know-how in the skills as `##` sections with `## Steps`, and every script a named command in `bin/` (`python3 scripts/build_bins.py strategy`).

```bash
claude --plugin-dir ~/coding-projects/automation-toolbox/strategy --agent strategy:strategy-goal-alignment
```

## Jobs and agents

| Agent | Automation | What it does | Was |
|---|---|---|---|
| `strategy-goal-alignment` | goal-alignment | Monthly check of goals against projects and time, as one approval list; quarterly, the review pre-filled | `goal-alignment-orchestrator`, with `goal-auditor` and `goal-alignment-strategy` |
| `strategy-worker` | | One slice: the goal audit of a group of domains, a plan's assumptions (`gate-1-pending.md`) or the web evidence (`research.md`) | `pre-mortem-investigator`, `pre-mortem-researcher`, and `goal-auditor` for a large portfolio |
| `strategy-reviewer` | | Independent PASS or FAIL on the pre-mortem brief before Gate 2 (`review-red-team`); edits nothing | new: the plan's suggested cold read of the brief |

The pre-mortem is a skill the owner runs in their own session, not an Automation and not a main agent: its two gates are the executive's, so it never runs unattended. It dispatches `strategy-worker` and `strategy-reviewer` itself.

## Skills

| Skill | Run by | What it holds |
|---|---|---|
| `goal-alignment-workstream` | strategy-goal-alignment | Steps (pack and approve passes); sections Audit goals against work, Pulse the strategic goals; the item contract |
| `pre-mortem` | the owner | Steps with two gates; sections Surface the assumptions and Gather external evidence (worker), Find the kill-shot risks, Write the brief, Capture lessons learned; the fictional worked company and the brief template |
| `goal-audit`, `orchestration-workstream`, `task-stack-workstream`, `review-red-team` | shared copies | The seven findings and closed action list (also run standalone by projects' `project-landscape`); worker conduct; the change set; the red-team checklist |

`pre-mortem-investigator-method` and `pre-mortem-researcher-method` were merged into `pre-mortem` as its two worker sections.

## Commands

In `bin/`, one per script of `goal-alignment-workstream`: `strategy-goal-alignment-gather` (before the session: the month's facts and the pass), `strategy-goal-alignment-pack` (in it: checks `review.json` and renders the note), `strategy-goal-alignment-check` (whether the month is done; the precheck), `strategy-goal-alignment-changes` (after it: the owner's answers as one change set) and `strategy-goal-alignment-publish` (files the note and the approval task). The shared copy's commands keep one unprefixed name: `task-stack-apply`, `task-stack-check`, `task-stack-queue`, `task-stack-report`.

## Contracts with other departments

- **The time study's tables** (productivity's `report-time-study`) are read by `strategy-goal-alignment-gather` from the `time_study_home` setting: a file contract.
- **The `lessons-learned` entry format** the pre-mortem appends to is the one projects' engagement closeout writes its lessons in.
- Change sets are signed `strategy-goal-alignment`; `task-stack-apply` maps it to the old orchestrator name so markers stay stable.

## Decisions taken in the conversion (2026-10-23)

- decided: the pre-mortem stays a skill with `## Steps` and no main agent (plan open question 2): it has no Automation and both gates are the owner's.
- decided: the pre-mortem's resume state is detected in step 1 from the files; Gate 1 is approved by renaming `gate-1-pending.md` to `gate-1-approved.md`, so a fresh run and an approved one are told apart.
- decided: `goal-auditor`'s two modes are split: its findings and closed action list, and its standalone walk of the Portal, are the shared skill `goal-audit` (copied into projects for `project-landscape`); the alignment mode is section Audit goals against work, run by the main agent, or by the worker per group of domains for a large portfolio.
- decided: the department has a reviewer for the pre-mortem brief's cold read (the plan's optional check); the goal alignment keeps no reviewer step, since `strategy-goal-alignment-pack` validates the note and the owner approves every op.

## Settings and environment

The keys are described in [docs/settings.md](../docs/settings.md): `state_dir`, `portal_mcp_config`, and `[goal-alignment-workstream] rules_file`, `alignment_project` or `alignment_domain`, `time_study_home`. Python 3.11 or later, standard library and `pyyaml`, declared in each script's `# /// script` block.
