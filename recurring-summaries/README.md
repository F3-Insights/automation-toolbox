# Recurring Summaries

The owner's daily plan. Each weekday morning it picks the top three, fits them to free time and names conflicts and missing meeting prep; each evening it closes the day on evidence, re-dates what moved, captures the day's commitments, writes the done list and names tomorrow's three. It reads through the Insights Portal MCP server and leaves its writes in the Run folder for a finish step: nothing is sent, and no model writes to the Portal.

The nightly sweep that used to live here was retired on 2026-10-23: productivity's task keeper, project keeper and digest (the 2026-10-07 recurring-automations redesign) do its work. The task, meeting and relationship stewards in [productivity](../productivity/) cover the rest of the owner's day.

## The plugin

This folder is a standalone Claude Code plugin named `recurring-summaries` (`.claude-plugin/plugin.json`), built the way [software](../software/README.md#the-plugin) is: one short main agent, one worker and one reviewer, the know-how in the job's skill as `##` sections, and every script a named command in `bin/` (`python3 scripts/build_bins.py recurring-summaries`).

```bash
claude --plugin-dir ~/coding-projects/automation-toolbox/recurring-summaries --agent recurring-summaries:daily-planner
```

## Jobs and agents

| Agent | Automation | What it does |
|---|---|---|
| `daily-planner` | daily-plan | Morning: the top three fitted to free time, conflicts and prep, focus-block proposals. Evening: each planned item closed on evidence, re-dates and carry-overs, the day's commitments, the done list, tomorrow's three |
| `recurring-summaries-worker` | | One slice the planner hands it: one domain packet gathered into done-list candidates (section Gather one domain), on a cheap model |
| `recurring-summaries-reviewer` | | Independent PASS or FAIL on each medium-confidence completion, by `task-stack-workstream`'s Check task-stack ops; edits nothing |

The change set is signed `daily-planner`; `task-stack-apply`'s alias table maps it to the name its markers were first written under.

## Skills

| Skill | Run by | What it holds |
|---|---|---|
| `daily-plan-method` | daily-planner, worker | Steps; the pick-three rubric, fitting the day, the evening close; sections Check the plan, Gather one domain, Done today; the plan file's shape |
| `task-stack-workstream` | daily-planner, reviewer (shared copy) | Task-stack conduct, the change-set contract, checklist Check task-stack ops |
| `orchestration-workstream` | all (shared copy) | The conduct and return block |

## Commands

In `bin/`: `recurring-summaries-daily-plan-pull` (the day's read-only Portal pull, before the session), `recurring-summaries-daily-plan-publish` (the day's plan note, once per pass, by marker), `recurring-summaries-daily-plan-check` (whether the pass is done; `--offline` reads only the Run's files; `--precheck` for the scheduler). The shared copy's commands keep one unprefixed name: `task-stack-apply`, `task-stack-check`, `task-stack-queue`, `task-stack-report`. Each prints `--help`.

## The daily-plan Automation

- Precheck: `recurring-summaries-daily-plan-check --precheck --morning-at 06:30 --evening-at 18:00`.
- Prepare: `recurring-summaries-daily-plan-pull --date D --pass P --out RUN/pull.json`.
- Session: `daily-planner`, subagents `recurring-summaries-worker` and `recurring-summaries-reviewer`.
- Finish: `recurring-summaries-daily-plan-publish`, `task-stack-apply --run RUN --max-changes=20`, `recurring-summaries-daily-plan-check`.

## File contracts with other departments

- The morning's focus-block proposals land in `<state_dir>/daily-plan/<date>/morning.json` when the note is published; productivity's calendar steward reads that file (its `daily_plan_state` setting) and puts each on its approval list. Neither department dispatches the other.
- chief-of-staff's `start-session` reads the day's plan note and, with no note, runs the pull by hand.

## Decisions taken in the conversion

- The plugin keeps the folder name `recurring-summaries` (plan D9 proposed `daily`): renaming touches toolbox-wide files other departments' conversions edit at the same time, and the main agent is already called `daily-planner`, which every alias table knows. Rename at the wave-7 cleanup if the long command names grate.
- `start-session` stays in chief-of-staff (plan D10 proposed moving it here) until that department converts; it reads the plan note and the pull, a file and a command, not an agent.
- The done-list gather stays a worker slice on haiku (plan risk 1); with one or two packets the planner gathers them itself.

## Settings and environment

The keys are described in [docs/settings.md](../docs/settings.md).

- **Portal**: `portal_mcp_config` (and `portal_server`) for every command, with the bearer in `INSIGHTS_PORTAL_ASSISTANT_TOKEN` or a `${VAR}` in the MCP config.
- **State**: `state_dir`; the daily plan keeps its published copies in `<state_dir>/daily-plan`.
- **Per skill**: `[daily-plan-method] timezone`.
- **Rules files**: the owner's `TASK-STACK-RULES.md` and `DAILY-PLAN.md`, each passed in a Run's inputs.
- Python 3.11 or later; the standard library only.
