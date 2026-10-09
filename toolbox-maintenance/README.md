# Toolbox Maintenance

Keeps an agent toolbox healthy as it grows. A weekly toolbox audit reads the whole toolbox (every department's agents, skills and scripts) against its own design, check and lints, finds drift, unused and duplicated pieces, long descriptions, scripts off the commands-in-skills rule and private names in generic files, makes the narrow frontmatter fixes on a review branch, and hands the owner one ranked list. An activity auditor looks at what the automation does in the Insights Portal (runs, cost, drafts and contact pressure). A monthly skill harvest mines the owner's past Claude Code and Codex sessions for work that keeps being done by hand, and stages drafts of the skills the owner picks on a review branch. Nothing here merges, pushes or edits the live checkout.

## Agents

| Agent | What it does | Needs |
|---|---|---|
| `toolbox-audit-orchestrator` | Weekly audit of the toolbox itself: one ranked findings list, narrow lint fixes on a branch | setting `repo` under `[toolbox-audit-workstream]` |
| `toolbox-audit-analyst` | Judges the scan's findings and each orchestrator's fit to the design | none |
| `toolbox-audit-fixer` | Makes only the fixes the fix rule allows, in the Run's worktree | none |
| `toolbox-audit-checker` | Independent PASS or FAIL on every finding and fix | none |
| `activity-auditor` | Audits the automation's own activity: runs and cost, drafts and contact pressure, duplicate and idle work | Insights Portal; a run logs folder (optional) |
| `skill-harvest-orchestrator` | Monthly harvest: candidate list from past sessions, then drafts of the owner's picks | settings `[skills-extract]`, `[skill-harvest-workstream]` |
| `skill-harvest-worker` | Mines one scope with skills-extract, or drafts one picked skill | none |
| `skill-harvest-checker` | Independent check of one draft: format, privacy, coverage | none |

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `toolbox-audit-workstream` | The audit's sections, finding shape, ranking, fix rule, and its four scripts (reference for the workers) | `pyyaml`; setting `repo` |
| `skills-extract` | Owner-started: find repeated manual work in past sessions, map it to existing skills, draft what the owner picks | none (session folders are settings with defaults) |
| `skill-harvest-workstream` | The monthly harvest loop, inbox review, DONE checklists and the review-branch script (reference for the workers) | setting `repo` under `[skill-harvest-workstream]` |

Used by name from other departments: `orchestration-workstream` and `orchestrator-scaffold` (software), `task-stack-apply` in `task-stack-workstream` (productivity), which files the audit's owner tasks after the Run.

## Scripts

Each script runs by path, `python3 ~/.claude/skills/<skill>/scripts/<script>.py`, and prints `--help`. Nothing is installed.

**`toolbox-audit-workstream`** (Python 3.11 with `pyyaml`)
- `toolbox_audit_scan.py`: reads the toolbox before the session, reusing its `scripts/toolbox_check.py` and the scaffold lint, reports each agent file that drifts from the agent file standard (ADR 0003), and writes `scan.json`.
- `toolbox_audit_fix.py`: `open` makes the Run's worktree on a `toolbox-audit/fixes-<date>` branch, `verify` checks the diff against the fix rule, `commit` commits it there only after the checker's PASS and the toolbox check; never touches the live checkout, never merges or pushes.
- `toolbox_audit_check.py`: whether an audit is due (`--precheck`) and whether a Run's audit is done (`--run`).
- `toolbox_audit_record.py`: the Run's REPORT.md, the findings ledger, `runs.jsonl` and the task change set.

**`skills-extract`** (standard library)
- `session_pack.py`: condenses past sessions on one topic into a private data pack.
- `skill_inventory.py`: lists every skill already installed and how often the sessions used it.
- `name_check.py`: flags private names, paths and numbers in drafts and their file paths, including the toolbox's external denylist; it reports file, line and kind, never what matched.

**`skill-harvest-workstream`** (standard library)
- `skill_harvest_branch.py`: stages checked drafts on a `skill-harvest/<date>` branch of the toolbox through a worktree in the Run folder, after the name check and the toolbox check pass; never touches the live checkout, never merges or pushes.

## Settings and environment

The keys are described in [docs/settings.md](../docs/settings.md).

- `[toolbox-audit-workstream] repo`: the toolbox checkout the audit scans and cuts its fix branch from (or `--repo`, `--root`). The Run folder must sit outside that checkout.
- `[skill-harvest-workstream] repo`: the toolbox checkout the harvest's review branch is cut from (or `--repo`).
- `[skills-extract] claude_session_dirs` and `codex_session_dirs`: lists of folders holding past sessions; default `~/.claude/projects` and `~/.codex/sessions`.
- `F3I_TOOLBOX_DENYLIST` and `~/.config/f3i-toolbox/denylist.txt`: the private-name lists, kept outside any repository, read by `name_check.py` and the audit's fix rule as well as the toolbox check.
- The audit's rules (`TOOLBOX-AUDIT-RULES.md`) and the harvest's rules (`SKILL-HARVEST-RULES.md`) live in the owner's audit and harvest folders, never here.

## Needs

Claude Code; `git` for the fix and review branches; the Insights Portal MCP server for `activity-auditor`; `pyyaml` for the audit scripts.
