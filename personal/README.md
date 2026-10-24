# Personal

The owner's own life admin, run with the same care as the business work: a household chief of staff for one member of the household, a weekly health check-in against the owner's own goals, a weekly read of the home's own equipment against the owner's inventory, a monthly household finance review, and tax season worked like an auditor's request list. The topics are personal; nothing in these files describes a real person, home or account. Every fact (who is in the household, which accounts, which hosts, which goals) lives in the owner's private rules files, Contexts and settings outside this repository.

These run only for the owner. The owner, or a schedule the owner set, launches each main agent; no other agent or job does. They write only in the private domain folder their Context names, never message anyone, and send nothing to the Insights Portal: no skill here writes to it.

## The plugin

This folder is a standalone Claude Code plugin named `personal` (`.claude-plugin/plugin.json`), on the pattern of [ADR 0004](../docs/adr/0004-a-department-is-a-plugin.md) and the worked examples in `software/` and `productivity/`. Never enable it in a work session: its skills describe the owner's private folders.

- **Agents**: one short main agent per job, and `personal-reviewer` for every independent check. There is no `personal-worker`: every job is one sequential slice the main agent does itself.
- **Skills**: each job's method skill holds its `## Steps`, the section the main agent follows, the check sections the reviewer is told to use, and the DONE checklist. `personal-workstream` holds the privacy conduct every job and the reviewer keep.
- **Commands**: `bin/report-tieout`, from the copied `report-tieout` skill, which the reviewer's numbers checklist names. The department has no scripts of its own.

From Sentinel, an Automation launches a main agent by name with the `personal` plugin, its overlay's `subagents:` lists `personal-reviewer`, and every Portal write tool is disallowed. The owner's private read-only commands (health exports, home health commands) are granted to the session in the overlay, never in this repository.

## Jobs and agents

| Agent | Job (Automation) | Dispatches | Needs |
|---|---|---|---|
| `personal-household-keeper` | Household (family-household): the interview first, then one pain point's obligations ledger and a half-page weekly page | `personal-reviewer` (household-method, Check the dates) | none |
| `personal-health-check-in` | Health check-in (health-routine), **draft**: each metric against the owner's target, with trend and the dates due in 30 days | `personal-reviewer` (health-routine-method, Check the values) | the owner's exports or private read-only grants |
| `personal-home-infrastructure-check` | Home infrastructure (home-infrastructure), **draft**: the estate from read-only commands, at most one confirmed retirement proposal | `personal-reviewer` (home-infrastructure-method, Check the retirement proposal) | the owner's private read-only grants |
| `personal-finance-review-prep` | Household finance review (personal-finance-review): the month's checks from the owner's own review engine, a one-page agenda, every figure re-derived | `personal-reviewer` (personal-finance-review-method, Check the figures) | the owner's household review engine |
| `personal-tax-season-checklist` | Tax season (personal-tax-season): the document checklist from last year's folder, matched by form type, and what is still owed | `personal-reviewer` twice (personal-tax-season-method, Check the matches and Check completeness) | none |
| `personal-reviewer` | Independent PASS or FAIL with numbered fixes, from the sources alone; read-only, and bound by the fenced folders | none | none |

## Skills

| Skill | What it does |
|---|---|
| `personal-workstream` | Reference: privacy rules, the domain folder's shape, who writes what, how the reviewer is briefed, the return's item tests |
| `household-method` | Steps, the interview, the obligations ledger, Keep the ledger, Check the dates, DONE |
| `health-routine-method` | Steps, metrics against targets from the owner's exports, Read the week, Check the values, DONE (draft) |
| `home-infrastructure-method` | Steps, what to flag, one retirement a week, Read the estate, Check the retirement proposal, DONE (draft) |
| `personal-finance-review-method` | Steps, the month's checks from the review engine, Answer the checks, Check the figures, DONE |
| `personal-tax-season-method` | Steps, the prior-year folder as the template, Build and match the checklist, Check the matches, Check completeness, DONE |
| copies: `orchestration-workstream`, `review-facts`, `review-numbers`, `review-completeness`, `report-tieout` | Made by `scripts/build_shared.py` from `shared/skills/`; never edited here |

## Drafts

`health-routine-method` and `home-infrastructure-method`, with their main agents, are marked `maturity: draft`. They ship without commands, settings or credentials and are not runnable as is: the owner's rules file names the read-only commands or data exports to use, and the owner grants any command outside this repository once it is audited. Both main agents save a copy of every source they read in the Run folder, so the reviewer judges from those copies and needs no command grant of its own.

## Needs

No Insights Portal and no ERP. Each main agent needs a private Context naming its domain folder and rules file (`HOUSEHOLD-RULES.md`, `HEALTH-ROUTINE-RULES.md`, `HOME-INFRA-RULES.md`, `PERSONAL-FINANCE-RULES.md`, `TAX-SEASON-RULES.md`), which the owner keeps outside this repository. The finance review also needs the owner's own household review engine (a local repository that ties the banks' exports out); it is not part of this toolbox.

## What was renamed (2026-10, the plugin conversion)

| Now | Was |
|---|---|
| `personal-household-keeper` | `household-orchestrator`, and `household-steward` as section Keep the ledger |
| `personal-health-check-in` | `health-routine-orchestrator`, and `health-routine-analyst` as section Read the week |
| `personal-home-infrastructure-check` | `home-infrastructure-orchestrator`, and `home-infrastructure-analyst` as section Read the estate |
| `personal-finance-review-prep` | `personal-finance-review-orchestrator`, and `personal-finance-review-analyst` as section Answer the checks |
| `personal-tax-season-checklist` | `personal-tax-season-orchestrator`, and `personal-tax-season-analyst` as section Build and match the checklist |
| `personal-reviewer` | `home-infrastructure-checker` (section Check the retirement proposal), and the dispatches of the shared `fact-check`, `numbers-reviewer` and `completeness-audit` agents, now the copied `review-facts`, `review-numbers` and `review-completeness` checklists |

Decided in the conversion (the migration plan's open questions for this department):

- One household Automation serves one household member; a second member is a second Automation with its own Context and rules file, run by the same agent.
- `maturity: draft` carries over to the two draft main agents and their skills.
- The reviewer is given the fenced list in every brief (`personal-workstream`, Briefing the reviewer), and fails a claim that cites a fenced file rather than opening it.
- The reviewer gets no private command grants: the home check's main agent saves every command output in the Run folder, and the reviewer re-reads those.
- Merging jobs (finance review with tax season; household with home and health) was left for later: the privacy fences argue against one agent reading every domain.
