# Toolbox Maintenance

Keeps an agent toolbox healthy as it grows. A weekly toolbox audit reads the whole toolbox (every department's agents, skills and scripts) against its own design, check and lints, finds drift, unused and duplicated pieces, long descriptions, scripts off the commands-in-skills rule and private names in generic files, looks at what the automation does in the Insights Portal (runs and cost, drafts and contact pressure), makes the narrow frontmatter fixes on a review branch, and hands the owner one ranked list. A monthly skill harvest mines the owner's past Claude Code and Codex sessions for work that keeps being done by hand, and stages drafts of the skills the owner picks on a review branch. Nothing here merges, pushes or edits the live checkout.

## The plugin

This folder is a standalone Claude Code plugin named `toolbox-maintenance` (`.claude-plugin/plugin.json`), on the pattern of [ADR 0004](../docs/adr/0004-a-department-is-a-plugin.md) and [converting a department](../docs/converting-a-department.md). One short main agent per job; the procedure is in the job's skill under `## Steps`; `toolbox-maintenance-worker` does parallel or isolated slices and `toolbox-maintenance-reviewer` does every independent check. Commands are in `bin/`, written by `python3 scripts/build_bins.py toolbox-maintenance`.

```bash
claude --plugin-dir ~/coding-projects/automation-toolbox/toolbox-maintenance --agent toolbox-maintenance:toolbox-maintenance-auditor
```

From Sentinel, an Automation launches a main agent with `--plugin-dir <toolbox>/toolbox-maintenance`, which puts the commands on PATH; the overlay's `subagents:` lists `toolbox-maintenance-worker` and `toolbox-maintenance-reviewer`, and its tools are the agent's `tools:` line.

## Jobs and agents

| Agent | Job | Dispatches | Needs |
|---|---|---|---|
| `toolbox-maintenance-auditor` | Weekly toolbox audit (Automation `estate-audit`): one ranked findings list, narrow lint fixes on a branch, the owner's top tasks | `toolbox-maintenance-worker` (Judge a group of sections ×3, Audit the automation's activity, Fix within the rule), `toolbox-maintenance-reviewer` (Check findings and fixes) | setting `repo` under `[toolbox-audit-workstream]`; Insights Portal; `toolbox-maintenance-toolbox-audit-scan` and `-fix open` before, `-fix commit`, `-record` and `task-stack-apply` after |
| `toolbox-maintenance-skill-harvester` | Monthly skill harvest (Automation `skill-harvest`): candidate list from past sessions, then drafts of the owner's picks | `toolbox-maintenance-worker` (Mine one scope, Draft one pick), `toolbox-maintenance-reviewer` (Check a skill draft) | settings `[skills-extract]`, `[skill-harvest-workstream]`; `toolbox-maintenance-skill-harvest-branch` after a draft pass |
| `toolbox-maintenance-worker` | One slice a main agent hands it, following the skill section it is told to use | none | what the section needs |
| `toolbox-maintenance-reviewer` | Independent PASS or FAIL with numbered fixes, from the sources alone; edits nothing | none | what the section needs |

The two jobs stay separate: they share a repository and both stage work on a review branch, but their cadence, rules files and folders differ (the audit folder against the harvest folder), so by the toolbox's merge rule they are two jobs. The worker runs on opus: every slice here is judgment (findings, contact pressure, a draft a person may publish).

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `toolbox-audit-workstream` | The audit's Steps, the scan's sections, finding shape, ranking, the two patterns, the sections Judge a group of sections, Audit the automation's activity and Fix within the rule, the checklist Check findings and fixes, and the fix rule | `pyyaml`; setting `repo` |
| `skill-harvest-workstream` | The harvest's Steps for both passes, the sections Mine one scope and Draft one pick, the checklist Check a skill draft, the files, DONE checklists and the review-branch command | setting `repo` under `[skill-harvest-workstream]` |
| `skills-extract` | Owner-started: find repeated manual work in past sessions, map it to existing skills, draft what the owner picks | none (session folders are settings with defaults) |
| `pressure-test-method` | Red-teams one of the owner's systems per run from a rotation ledger: steelman, goal fit, external practice, ranked verdict | Insights Portal; settings `goals_doc`, `playbooks_dir`, `owner_profile`, `rotation_ledger` under `[pressure-test-method]` |
| `orchestration-workstream` | Copied from `shared/skills/`: how a worker behaves and returns | none |
| `task-stack-workstream` | Copied from `shared/skills/`: the change-set contract and `task-stack-apply`, which files the audit's owner tasks after the Run | Insights Portal |

A one-off "is the automation over-contacting people or wasting runs" is the auditor run with instructions to that effect, or the section Audit the automation's activity followed in any session.

## Commands

Each runs a script in its skill's `scripts/` folder and prints `--help`.

| Command | Script | What it does |
|---|---|---|
| `toolbox-maintenance-toolbox-audit-scan` | `toolbox-audit-workstream/scripts/toolbox_audit_scan.py` | Reads the toolbox before the session, reusing `scripts/toolbox_check.py` and the scaffold lint, judges each department by the pattern it is on, checks copies against their sources, and writes `scan.json` |
| `toolbox-maintenance-toolbox-audit-fix` | `toolbox-audit-workstream/scripts/toolbox_audit_fix.py` | `open` makes the Run's worktree on a `toolbox-audit/fixes-<date>` branch, `verify` checks the diff against the fix rule, `commit` commits it only after the reviewer's PASS and the toolbox check; never the live checkout, never merges or pushes |
| `toolbox-maintenance-toolbox-audit-check` | `toolbox-audit-workstream/scripts/toolbox_audit_check.py` | Whether an audit is due (`--precheck`) and whether a Run's audit is done (`--run`) |
| `toolbox-maintenance-toolbox-audit-record` | `toolbox-audit-workstream/scripts/toolbox_audit_record.py` | The Run's REPORT.md, the findings ledger, `runs.jsonl` and the task change set, signed `toolbox-maintenance-auditor` |
| `toolbox-maintenance-session-pack` | `skills-extract/scripts/session_pack.py` | Condenses past sessions on one topic into a private data pack |
| `toolbox-maintenance-skill-inventory` | `skills-extract/scripts/skill_inventory.py` | Lists every skill already installed (a toolbox checkout's plugin departments included) and how often the sessions used it |
| `toolbox-maintenance-name-check` | `skills-extract/scripts/name_check.py` | Flags private names, paths and numbers in drafts and their file paths, including the toolbox's external denylist; reports file, line and kind, never what matched |
| `toolbox-maintenance-skill-harvest-branch` | `skill-harvest-workstream/scripts/skill_harvest_branch.py` | Stages passed drafts on a `skill-harvest/<date>` branch through a worktree in the Run folder, after the name check and the toolbox check; never the live checkout, never merges or pushes |
| `task-stack-apply`, `task-stack-check`, `task-stack-queue`, `task-stack-report` | `task-stack-workstream/scripts/` (copied) | The shared task-stack commands; the audit's finish step uses `task-stack-apply` |

The scripts keep their file names, so the audit's commands carry `toolbox-audit` after the department prefix; other builders and the toolbox check still run the scan by its path.

## Settings and environment

The keys are described in [docs/settings.md](../docs/settings.md).

- `[toolbox-audit-workstream] repo`: the toolbox checkout the audit scans and cuts its fix branch from (or `--repo`, `--root`). The Run folder must sit outside that checkout.
- `[skill-harvest-workstream] repo`: the toolbox checkout the harvest's review branch is cut from (or `--repo`).
- `[skills-extract] claude_session_dirs`, `codex_session_dirs` and `toolbox_dirs`: folders holding past sessions (default `~/.claude/projects` and `~/.codex/sessions`) and toolbox checkouts whose skills the inventory reads.
- `F3I_TOOLBOX_DENYLIST` and `~/.config/f3i-toolbox/denylist.txt`: the private-name lists, kept outside any repository, read by the name check and the audit's fix rule as well as the toolbox check.
- The audit's rules (`TOOLBOX-AUDIT-RULES.md`) and the harvest's rules (`SKILL-HARVEST-RULES.md`) live in the owner's audit and harvest folders, never here.

Needs Claude Code, `git` for the fix and review branches, the Insights Portal MCP server for the activity audit and the task finish step, and `pyyaml` for the audit scripts.

## What was renamed (2026-10-23)

The department became a plugin. Neither job had run unattended, so there is no alias period; the task-stack writer's `RENAMED_AGENTS` keeps `toolbox-maintenance-auditor` mapped to `toolbox-audit-orchestrator` for its markers.

| Now | Was |
|---|---|
| `toolbox-maintenance-auditor` | `toolbox-audit-orchestrator` |
| `toolbox-maintenance-skill-harvester` | `skill-harvest-orchestrator` |
| `toolbox-audit-workstream`, section Judge a group of sections, by `toolbox-maintenance-worker` | `toolbox-audit-analyst` |
| `toolbox-audit-workstream`, section Audit the automation's activity, by `toolbox-maintenance-worker` | `activity-auditor` |
| `toolbox-audit-workstream`, section Fix within the rule, by `toolbox-maintenance-worker` | `toolbox-audit-fixer` |
| `toolbox-audit-workstream`, checklist Check findings and fixes, by `toolbox-maintenance-reviewer` (on fable for a description it judges close) | `toolbox-audit-checker` |
| `skill-harvest-workstream`, sections Mine one scope and Draft one pick, by `toolbox-maintenance-worker` | `skill-harvest-worker` |
| `skill-harvest-workstream`, checklist Check a skill draft, by `toolbox-maintenance-reviewer` | `skill-harvest-checker` |
| the commands above | `python3 <skill>/scripts/<x>.py` |

Decided in the conversion, following the migration plan:

- decided: the scripts keep their file names, so the audit's commands are `toolbox-maintenance-toolbox-audit-*` rather than the plan's `toolbox-maintenance-audit-*`; renaming the scan would break every department's check that runs it by path.
- decided: harvest drafts are written to `RUN/drafting/` and copied to `RUN/drafts/` only after the reviewer passes them, because the branch command stages everything in `RUN/drafts/` and no agent holds a delete.
- decided: skill harvest stays a separate job from the audit (the plan's merge candidate), and chief-of-staff's improvement step stays with chief-of-staff.
