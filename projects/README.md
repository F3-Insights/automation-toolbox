# Project Management

Runs client engagements and the owner's project portfolio from start to finish. Engagement kickoff and closeout turn a signed SOW into rules files, briefs and first tasks, and a finished engagement into acceptance evidence, an invoice check, lessons and a case study draft. Client delivery keeps one engagement's plan, milestones, RAID log and tasks true twice a week. The weekly project-health pass, the check-in and the landscape review keep the owner's Insights Portal projects tied to goals, owners and next actions. A technology portfolio review prepares a client's steering pack. For a consultant, fractional executive or small firm running several engagements at once. Every client message is a draft; nothing is sent.

## The plugin

This folder is a standalone Claude Code plugin named `projects` (`.claude-plugin/plugin.json`), built the way [software](../software/README.md#the-plugin) and [productivity](../productivity/README.md) are: one short main agent per job, one `projects-worker` and one `projects-reviewer` for dispatched work, the know-how in the jobs' skills as `##` sections with `## Steps`, and every script a named command in `bin/` (`python3 scripts/build_bins.py projects`). A main agent's first instruction is to load its skills with the Skill tool.

```bash
claude --plugin-dir ~/coding-projects/automation-toolbox/projects --agent projects:projects-client-delivery
```

From Sentinel, an Automation launches a main agent by name; the overlay's `subagents:` lists `projects-worker` and `projects-reviewer`, and prepare, precheck and finish run the named commands below.

## Jobs and agents

| Agent | Automation | What it does | Was |
|---|---|---|---|
| `projects-client-delivery` | client-delivery (one per engagement) | Twice-weekly delivery session for one engagement: plan against the SOW, milestones, RAID, tasks, the owner's questions | `client-delivery-orchestrator`, with the planner, risk analyst and task steward |
| `projects-engagement-kickoff` | engagement-kickoff | Turns a signed SOW into the kickoff pack: rules files with the baseline cited, briefs, client notes, folder plan, first two weeks of tasks | `project-engagement-kickoff-orchestrator`, with the writer |
| `projects-engagement-closeout` | engagement-closeout | Closes an engagement: acceptance evidence, final invoice check, lessons, name-free method harvest, case study draft | `project-engagement-closeout-orchestrator`, with the writer |
| `projects-health-review` | project-health | Weekly pass over the owner's Portal projects: diagnosis, smallest step, buckets drained, one change set | `project-health-orchestrator`, with the diagnoser |
| `projects-tech-portfolio` | tech-portfolio-review (one per client) | Weekly steering pack for a client's technology portfolio, from project owners' own updates | `tech-portfolio-orchestrator`, with the collector and writer |
| `projects-worker` | | One slice a main agent hands it (the RAID log, the task reconcile, a diagnosis batch, the bucket drain, the waiting-on scan, a portfolio batch, the standalone goal audit), following the named section | the specialists above that ran in parallel |
| `projects-reviewer` | | Independent PASS or FAIL against the named checklist section; edits nothing | `project-engagement-checker`, and the shared checker, red team, fact-check and numbers reviewer |

The two client-delivery Automations (one per engagement) share `projects-client-delivery`: the same job on a different Context. Change sets are signed `projects-client-delivery`, `projects-engagement-kickoff`, `projects-engagement-closeout` and `projects-health-review`; `task-stack-apply` maps each to its old orchestrator name so markers stay stable.

## Skills

| Skill | Run by | What it holds |
|---|---|---|
| `client-delivery-workstream` | projects-client-delivery | Steps; sections Plan the engagement, Keep the RAID log, Reconcile the tasks, Check the delivery status; the milestone, change, RAID and question shapes |
| `engagement-kickoff` | projects-engagement-kickoff | Steps; section Write the kickoff pack, the files other jobs read, DONE, Check the kickoff pack |
| `engagement-closeout` | projects-engagement-closeout | Steps; section Write the closeout pack, DONE, Check the closeout pack |
| `project-engagement-workstream` | kickoff and closeout | The Context and Sources, conduct, the claims and checks shapes, the folder command; the deck and IT-asks templates |
| `project-health-diagnose` | projects-health-review | Steps; the eight diagnoses; sections Diagnose a batch, Drain a bucket, What the stalled projects wait on; `diagnoses.json` |
| `tech-portfolio-workstream` | projects-tech-portfolio | Steps; the status row; sections Collect a batch, Write the steering pack, Check the pack; DONE |
| `project-engagement-runbook` | the owner, kickoff | The eight-step engagement lifecycle, each step's deliverable and maker |
| `project-engagement-onboarding` | the owner, kickoff | Two-page brief that lets a teammate join an engagement mid-stream |
| `engagement-comms-set` | kickoff | Reference: the four notes sent between signature and the first interview |
| `project-engagement-baseline` | the owner | Research reports, then a one-page BASELINE, then a CONCEPT of numbered positions |
| `review-register` | the owner, onboarding | The review register's YAML tables, read and written by `projects-register` |
| `project-checkin` | the owner | Interactive check-in from the last project-health Run's diagnoses |
| `project-landscape` | the owner | Interactive weekly portfolio review against goals, email and engagements, with the goal audit; holds the project playbook template |
| `project-status-update` | the owner | Interactive: one status line in, the project's status note updated and the task changes it states made (new tasks through `task-stack-apply`). Moved here from chief-of-staff on 2026-10-24 |
| `orchestration-workstream`, `task-stack-workstream`, `portal-write-safety`, `goal-audit`, `review-facts`, `review-numbers`, `review-red-team`, `report-tieout`, `unslop`, `unslop-deliverable`, `unslop-editorial`, `unslop-email`, `unslop-proposal` | shared copies | Worker conduct; the change set and Check task-stack ops; the goal audit; the reviewer checklists; plain writing |

## Commands

In `bin/`, one per script: `projects-delivery-pack`, `-delivery-check`, `-delivery-record`, `-delivery-apply` (client delivery); `projects-engagement-folders` (always `--dry-run` in a session); `projects-health-check` (was `project_health_check.py`); `projects-scoreboard` (was `project_scoreboard.py`); `projects-register`. The shared copies' commands keep one unprefixed name: `task-stack-apply`, `task-stack-check`, `task-stack-queue`, `task-stack-report`, `report-tieout`. Each prints `--help`.

Interactive skills name other plugins' commands where those plugins are on: `project-landscape` uses productivity's `productivity-calendar-time` and strategy's `strategy-goal-alignment-check`; `project-engagement-baseline` uses process engineering's `srt-transcript-collapse` and `transcript-hygiene`.

## Contracts with other departments

- **Reporting's report-collect.** `projects-delivery-pack` runs `report_collect.py` from reporting's `report-weekly` skill, found inside this toolbox checkout (`_skill_paths`, never `~/.claude/skills`), and reads its evidence ledger (`evidence-ledger/1`) for the window's Portal meetings, notes and mail. The client-delivery Automation therefore needs the reporting department in the same checkout. A shared `portal-collect` source copied into both is the later fix.
- **`RUN/diagnoses.json`** from the project-health Run is read by productivity's weekly review and by `project-checkin`, found by Run folder, not by agent name.
- **The rules files the kickoff drafts** (`DELIVERY-RULES.md`, reporting's `UPDATE-RULES.md` and `ENGAGEMENT-CONTEXT.md`, process engineering's `DISCOVERY-RULES.md`) are file contracts; `engagement-kickoff` lists the shapes it writes.
- **Hand-offs** are `for_owner` items, never dispatches: once the kickoff pack is adopted, arm client delivery, the client weekly update and the discovery intake for the engagement; once the client consents, launch marketing's case-study Automation on the closeout's draft; amounts owed go to the firm's billing run.

## Decisions taken in the conversion (2026-10-23)

- decided: `comms-confirm` is no longer copied in. Owner questions are recorded in the engagement's `CONFIRMATIONS.md` (client delivery) or the Run's report and `for_owner` items, never as live Portal tasks from the session, as in productivity.
- decided: `project-health`, `project-checkin` and `project-landscape` stay in projects for now (plan open question 1); `project-landscape` runs the copied `goal-audit` through `projects-worker`.
- decided: `project-engagement-baseline` stays here until process engineering takes it in (plan D10); moving it is one folder.
- decided: the bucket drain and the waiting-on scan are sections of `project-health-diagnose` rather than copies of productivity's `task-stack-clarify` and `waiting-on-tracker-method`, which are not shared skills.
- decided: the `engagement-context` shared skill the plan proposes is not created here; the kickoff skill carries the section list as a file contract until reporting extracts it.

## Settings and environment

The keys are described in [docs/settings.md](../docs/settings.md).

- `portal_mcp_config` (and `portal_server`) for every command that reads the Portal, with the bearer in `INSIGHTS_PORTAL_ASSISTANT_TOKEN` or a `${VAR}` in the MCP config.
- `contexts_dir` for `projects-delivery-pack`; `engagements_dir` (or `--root`) for `projects-engagement-folders`, whose folder names `[project-engagement-workstream]` can replace (`general_subfolders`, `workstream_subfolders`, `repo_prefix`).
- `runs_dir` under `[project-health-diagnose]` for `projects-health-check --last-run`; `owner_name` under `[review-register]` is optional.
- Python 3.11 or later, with `pyyaml` (and `pypdf`, `openpyxl` for the delivery pack), declared in each script's `# /// script` block.

Planned and not yet built: `engagement-pack`, `sow-extract`, `closeout-invoice-tie`, `harvest-name-check`, `engagement-publish`, `portfolio-pack`, `portfolio-check`.
