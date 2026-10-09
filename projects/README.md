# Project Management

Runs client engagements and the owner's project portfolio from start to finish. Engagement kickoff and closeout turn a signed SOW into rules files, briefs and first tasks, and a finished engagement into acceptance evidence, an invoice check, lessons and a case study draft. Client delivery keeps one engagement's plan, milestones, RAID log and tasks true twice a week. The project-health pass, check-in and landscape review keep the owner's Insights Portal projects tied to goals, owners and next actions. A technology portfolio review prepares a client's steering pack. For a consultant, fractional executive or small firm running several engagements at once. Every client message is a draft; nothing is sent.

## Agents

| Agent | What it does | Needs |
|---|---|---|
| `project-engagement-kickoff-orchestrator` | Turns a signed SOW into the kickoff pack: rules files with the baseline cited, briefs, client notes, folder plan, first two weeks of tasks | Insights Portal, command `engagement-folders` |
| `project-engagement-closeout-orchestrator` | Closes an engagement: acceptance evidence, final invoice check, lessons, name-free method harvest, case study draft | Insights Portal |
| `project-engagement-writer` | Drafts the kickoff or closeout pack | Insights Portal |
| `project-engagement-checker` | Traces every baseline line to the SOW, checks assignments, acceptance and the harvest's anonymity | Insights Portal |
| `client-delivery-orchestrator` | Twice-weekly delivery pass for one engagement: plan, milestones, RAID, tasks, owner's decisions | Insights Portal, commands `delivery-check`, `delivery-record` |
| `project-delivery-planner` | Sets the plan against the SOW baseline and proposes milestone states and changes | Insights Portal |
| `project-risk-analyst` | Keeps the RAID log true from the engagement's sources | Insights Portal |
| `project-task-steward` | Reconciles the engagement's Portal tasks and proposes task ops | Insights Portal |
| `project-health-orchestrator` | Weekly pass over the owner's Portal projects: diagnosis, smallest step, one change set | Insights Portal, commands run before and after: `project-health-check`, `task-stack-check`, `task-stack-apply` |
| `project-health-diagnoser` | One diagnosis word and the unblocking ops for each of a few projects | Insights Portal |
| `tech-portfolio-orchestrator` | Weekly steering pack for a client's technology portfolio, from project owners' own updates | Insights Portal, `PORTFOLIO-RULES.md` |
| `tech-portfolio-collector` | One dated status row per project, with sources and slips | Insights Portal |
| `tech-portfolio-writer` | Writes the steering pack with a source on every sentence | none |

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `project-engagement-workstream` | The kickoff and closeout method: Context and Sources, packs, DONE checklists, return shapes; holds the deck and IT-asks templates | none |
| `project-engagement-runbook` | The eight-step engagement lifecycle, each step's deliverable and maker | command `engagement-folders`, setting `engagements_dir` |
| `project-engagement-baseline` | Research reports, then a one-page BASELINE, then a CONCEPT of numbered positions | commands `srt-transcript-collapse`, `transcript-hygiene` |
| `project-engagement-onboarding` | Two-page brief that lets a teammate join an engagement mid-stream | Insights Portal, command `register` |
| `review-register` | The review register: YAML tables of what is open, at risk, reconciled, owed and proposed, read and written by `register.py` | command `register` |
| `engagement-comms-set` | Reference: the four notes sent between signature and the first interview | none |
| `client-delivery-workstream` | The delivery method: rules first, SOW baseline never invented, milestone, change, RAID and task shapes | none |
| `project-health-diagnose` | The closed list of eight diagnoses, the smallest step, the ops, nudges and closing rules | none |
| `project-checkin` | Interactive check-in that captures the owner's status answers project by project | Insights Portal, command `project-health-check` |
| `project-landscape` | Interactive weekly portfolio review against goals, email and engagements; holds the project playbook template | Insights Portal, commands `project-scoreboard`, `calendar-time`, `goal-alignment-check` |
| `tech-portfolio-workstream` | The portfolio method: register, status row, slip detection, steering pack, DONE checklist | `PORTFOLIO-RULES.md` |

The workstream skills build on `orchestration-workstream` (software). The agents and skills also use, by name: `task-stack-workstream`, `comms-confirm`, `portal-write-safety`, `goal-auditor`, `goal-alignment-orchestrator`, `task-clarify-worker`, `task-reconcile-checker`, `waiting-on-tracker`, `comms-follow-ups`, `comms-draft-email` (productivity); `fact-check`, `executive-red-team`, `numbers-reviewer`, `client-update-workstream`, `comms-client-status-update` (reporting); `interview-synthesis` (process-engineering); `unslop-email`, `unslop-editorial`, `unslop-deliverable`, `unslop-proposal`, `marketing-case-study-orchestrator` (marketing); `writing-seminar-builder` (learning). The baseline and runbook also suggest `software-grill-with-docs` (software) for grilling a plan.

## Scripts

Each script runs by path, `python3 ~/.claude/skills/<skill>/scripts/<script>.py`, and prints `--help`. A command name used elsewhere in this README, such as `trial-balance`, is a label for the script of that name with underscores (`trial_balance.py`). Nothing is installed.

**`project-engagement-workstream`**
- `engagement_folders.py`: creates an engagement's standard folder set, and optionally its working repository.

**`client-delivery-workstream`**
- `delivery_pack.py`: gathers one engagement into the Run folder before the session, read only.
- `delivery_check.py`: whether the engagement's delivery is kept true, computed from its files.
- `delivery_record.py`: the one writer of the delivery ledgers, `DELIVERY-EVIDENCE.csv` and `RAID.csv`.
- `delivery_apply.py`: applies the session's task change set through `task_stack_apply.py`.

**`project-health-diagnose`**
- `project_health_check.py`: the state of every active Portal project and the weekly pass's worklist; `--last-run` finds the last Run.

**`project-landscape`**
- `project_scoreboard.py`: every active Portal project with the mechanical half of its priority score.

**`review-register`**
- `register.py`: reads and keeps a review register (`summary`, `list`, `render`, `add`, `close`).

The other commands named above live in productivity (`task-stack-check`, `task-stack-apply`, `task-stack-report` in `task-stack-workstream`; `calendar-time` in `calendar-steward-method`; `goal-alignment-check` in `goal-alignment-workstream`; `outbound-check` in `comms-draft-check`) and process-engineering (`srt-transcript-collapse`, `transcript-hygiene` in `transcript-tools`).

Planned and not yet built: `engagement-pack`, `sow-extract`, `closeout-invoice-tie`, `harvest-name-check`, `engagement-publish`, `portfolio-pack`, `portfolio-check`.

### Settings and environment

The keys are described in [docs/settings.md](../docs/settings.md).

- `portal_mcp_config` (and `portal_server`) for every script that reads the Portal, with the bearer in `INSIGHTS_PORTAL_ASSISTANT_TOKEN` or a `${VAR}` in the MCP config.
- `contexts_dir` for `delivery_pack.py`; `engagements_dir` (or `--root`) for `engagement_folders.py`, whose folder names `[project-engagement-workstream]` can replace (`general_subfolders`, `workstream_subfolders`, `repo_prefix`).
- `runs_dir` under `[project-health-diagnose]` for `project_health_check.py --last-run`; `owner_name` under `[review-register]` is optional.
- Python 3.11 or later, with `pyyaml` (and `pypdf`, `openpyxl` for the delivery pack), declared in each script's `# /// script` block.
