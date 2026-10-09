# Recurring Summaries

The owner's daily and nightly passes over their own work. Each night the sweep files the day's email as tasks and notes, closes the tasks the sent mail finished, names a few relationships to tend, preps the meetings of the day just starting, and writes a Daily Note; each weekday the daily plan picks the morning's three and closes the evening on evidence. Both read and write through the Insights Portal MCP server, and both leave their writes in the Run folder for a finish step to make in code: nothing is sent, and no model writes to the Portal.

The task, meeting and relationship orchestrators in [productivity](../productivity/) cover parts of the same ground on their own schedules; `nightly-sweep-workstream` says where the sweep overlaps each of them.

## Agents

| Agent | What it does | Needs |
|---|---|---|
| `nightly-sweep-orchestrator` | The nightly sweep, one date at a time, five phase workers, each plan checked by a dry run and left for the finish step | Insights Portal; commands `sweep-dates`, `sweep-emails`, `sweep-tasks`, `sweep-apply`, `sweep-note-publish`; setting `[nightly-sweep-workstream] timezone` |
| `daily-plan-orchestrator` | Morning top three fitted to free time; evening close on evidence | Insights Portal; commands `daily-plan-pull`, `daily-plan-publish`, `daily-plan-check`, `task-stack-apply` |
| `nightly-sweep-email-processor` | Phase 1: the day's email into proposed tasks, WAITING updates and notes | Insights Portal |
| `nightly-sweep-task-reconciler` | Phase 2: DONE proposals for tasks the day's sent mail or recaps finished | Insights Portal |
| `nightly-sweep-relationship-scout` | Phase 3: five relationships to tend and unanswered outreach | Insights Portal |
| `nightly-sweep-calendar-preparer` | Phase 4: prep notes for the external meetings of the day just starting | Insights Portal |
| `nightly-sweep-note-writer` | Phase 5: the date's Daily Note from the phase files | none |
| `daily-plan-planner` | Morning: picks three, fits slots, names conflicts and prep | Insights Portal |
| `daily-plan-closer` | Evening: an outcome per planned item, re-dates, tomorrow's three | Insights Portal |
| `accomplishment-gatherer` | One domain's day into candidate accomplishment bullets | Insights Portal |
| `accomplishment-synthesizer` | Picks and groups the day's done list from the candidates | none |

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `nightly-sweep-workstream` | The sweep's method: the rules every phase applies, the worker briefs, the commands, folders, ledger and markers, and where it overlaps the productivity pieces | Insights Portal; settings `[nightly-sweep-workstream]` |
| `daily-plan-method` | Pick-three rubric, fitting the day, evening close; the plan note is also the morning brief and the daily recap | Insights Portal; setting `[daily-plan-method] timezone` |
| `accomplishment-gatherer-method` | The accomplishment gatherer's procedure: strategic context first, group, weight, running themes, prime, one follow-up, five to eight bullets | none (the agent's Insights Portal reads) |
| `accomplishment-synthesizer-method` | The accomplishment synthesizer's procedure: pool and score, pick up to the cap, the header, the quality pass, the recap format | none |

## Scripts

Each script runs by path, `python3 ~/.claude/skills/<skill>/scripts/<script>.py`, and prints `--help`. A command name used in this README, such as `sweep-apply`, is a label for the script of that name with underscores (`sweep_apply.py`). Nothing is installed.

**`nightly-sweep-workstream`**
- `sweep_dates.py`: which dates a Run sweeps, oldest first, with their local-day windows; writes `dates.json` and marks the dates in progress.
- `sweep_emails.py`: every inbound and sent email of a date's local day, archived or not, into the date's folder.
- `sweep_tasks.py`: every open task, one compact row per line, into the date's folder.
- `sweep_apply.py`: makes the writes one phase proposed (phases 1, 2 and 4), each found by its marker first and read back; `--dry-run` checks a plan and writes nothing.
- `sweep_note_publish.py`: writes a date's Daily Note with a block of what the sweep really wrote, reads it back, then records the date in the ledger.

**`daily-plan-method`**
- `daily_plan_pull.py`: the day's read-only Portal pull, written before the session.
- `daily_plan_publish.py`: writes the day's plan note in the Portal, once per pass, by marker.
- `daily_plan_check.py`: whether the day's plan pass is done.

`task-stack-apply` is `task_stack_apply.py` in `task-stack-workstream` (productivity).

## Settings and environment

The keys are described in [docs/settings.md](../docs/settings.md).

- **Portal**: `portal_mcp_config` (and `portal_server`) for every script, with the bearer in `INSIGHTS_PORTAL_ASSISTANT_TOKEN` or a `${VAR}` in the MCP config.
- **State**: `state_dir`; the sweep keeps its ledger in `<state_dir>/nightly-sweep` unless `[nightly-sweep-workstream] state` names another folder, the daily plan its published copies in `<state_dir>/daily-plan`.
- **Per skill**: `[nightly-sweep-workstream] timezone`, `state`, `assistant_email`, `portal_brief_email`, `owner_names`, `firm_names`, `vip_stale_days`, `daily_note_private`; `[daily-plan-method] timezone`.
- **Rules files**: the owner's `NIGHTLY-SWEEP-RULES.md` (client and domain names for routing, the executive assistant), `TASK-STACK-RULES.md` and `DAILY-PLAN.md`, each passed in a Run's inputs.
- **Runner switch**: `F3I_TOOLBOX_DRY_RUN=1` makes the sweep's writers refuse a call without `--dry-run`.
- Python 3.11 or later; the standard library only.
