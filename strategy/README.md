# Strategy

Keeps the owner's goals honest against what actually happens. Once a month the goal alignment pass sets the owner's goals against their projects and against where the time went (from the time study in productivity), finds the gaps (goals with no project, projects with no goal, goals starved of time, time serving nothing), pre-fills the review of the owner's strategic goals document, and puts one numbered approval list to the owner. Nothing is written to the Portal until the owner approves. Before a strategic plan is committed to, a pre-mortem stress-tests it in two gates: the assumptions it rests on, then how it fails.

The strategic goals document and the review cadence are the owner's; they are named by settings (`[goal-alignment-workstream]` in [docs/settings.md](../docs/settings.md)), never written here.

## Agents

| Agent | What it does | Needs |
|---|---|---|
| `goal-alignment-orchestrator` | Monthly check of goals against projects and time, as one approval list | Insights Portal, commands `goal-alignment-gather`, `goal-alignment-pack`, `goal-alignment-check` |
| `goal-auditor` | Finds where goals, projects and time have come apart | Insights Portal, optional commands `project-scoreboard`, `calendar-time` |
| `goal-alignment-strategy` | Status pulse and goal mapping from the owner's strategic goals document | Insights Portal |
| `pre-mortem-investigator` | Surfaces a plan's stated, implied and missing assumptions for Gate 1 | none |
| `pre-mortem-researcher` | Gathers sourced external evidence on the plan | web search |

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `goal-alignment-workstream` | Goal alignment questions and item contract | Insights Portal |
| `pre-mortem` | Two-gate pre-mortem on a strategic plan, with a fictional worked company and the brief template | none |
| `pre-mortem-investigator-method` | The investigator's procedure: read the plan and knowledge base, tag assumptions in five categories, write the gate-1 file | none |
| `pre-mortem-researcher-method` | The researcher's procedure: plan-specific queries, primary and recent sources, write research.md | web search |

## Scripts

**`goal-alignment-workstream`**
- `goal_alignment_gather.py`: reads the month's facts before the session and picks the pass.
- `goal_alignment_pack.py`: checks the session's review and renders the alignment note.
- `goal_alignment_check.py`: whether the month's goal alignment is done.
- `goal_alignment_changes.py`: turns the owner's answers into one task change set.
- `goal_alignment_publish.py`: files the alignment note and the approval task after the session.

Task changes go through `task-stack-apply` in `task-stack-workstream` (productivity), and the hours come from `report-time-study` (productivity).
