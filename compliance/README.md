# Compliance & Governance

Keeps an organization's legal and governance obligations from slipping: a compliance calendar of filings, renewals and registrations placed on evidence each week, IT and AI governance worked as a control checklist (evidence per period, third-party AI tool reviews, the annual policy refresh), and a legal entity's wind-down driven step by step to dissolution. For a controller, a fractional CFO or an operations lead who owns those deadlines. Agents find evidence, prepare paper and propose tasks; people file, pay, sign and send.

## The plugin

This folder is a standalone Claude Code plugin named `compliance` (`.claude-plugin/plugin.json`), on the pattern of [ADR 0004](../docs/adr/0004-a-department-is-a-plugin.md) and the worked examples in `software/` and `productivity/`.

- **Agents**: one short main agent per job; `compliance-worker` for parallel batches and for the isolated AI tool review; `compliance-reviewer` for every independent check.
- **Skills**: each job's skill holds its `## Steps`, the sections the worker follows, the check sections the reviewer is told to use, and the DONE checklist.
- **Commands** in `bin/`, all from copied skills and unprefixed (decision D2): `task-stack-apply`, `task-stack-check`, `task-stack-queue`, `task-stack-report` (from `task-stack-workstream`) and `pdf-handle`, `excel-handle`, `powerpoint-handler` (from `office-files`). The department has no scripts of its own.

From Sentinel, an Automation launches a main agent by name with the `compliance` plugin; its overlay's `subagents:` lists `compliance-worker` and `compliance-reviewer` (only the reviewer for the wind-down). The calendar and the wind-down end with `task-stack-apply --run RUN` as the finish step, the one writer of the owner's tasks; the session never writes the Portal.

## Jobs and agents

| Agent | Job (Automation) | Dispatches | Needs |
|---|---|---|---|
| `compliance-calendar-keeper` | Compliance calendar (compliance-calendar): every item's current occurrence placed on evidence, owner tasks as a change set, calendar proposals | `compliance-worker` (Place a batch), `compliance-reviewer` (Check the evidence) | Insights Portal; `task-stack-apply` after the session |
| `compliance-it-governance` | IT governance (the it-governance Automation, one per entity): control evidence for a period, one AI tool review, or the policy-refresh gap list | `compliance-worker` (Place a batch of controls, Review an AI tool), `compliance-reviewer` (Check the control evidence, Check the tool review, Check the library's completeness and facts) | Insights Portal; web access for the worker and reviewer in tool-review mode |
| `compliance-entity-wind-down` | Entity wind-down (entity-wind-down): every step of the reference sequence placed, the next filings prepared as packets, owner tasks as a change set | `compliance-reviewer` (Check the plan's completeness, Check the plan's facts) | Insights Portal; `pdf-handle`, `excel-handle`; `task-stack-apply` after the session |
| `compliance-worker` | One slice a main agent hands it, following the section it is told to use; reads only | none | what the section needs |
| `compliance-reviewer` | Independent PASS or FAIL with numbered fixes, from the sources alone; edits nothing | none | what the section needs |

## Skills

| Skill | What it does |
|---|---|
| `compliance-calendar-workstream` | Steps, the calendar file and item shape, lead-time arithmetic, occurrence states, Place a batch, Check the evidence, the DONE checklist |
| `it-governance-workstream` | Steps for three modes, controls as checklist rows, control states, the AI tool review standard, the policy refresh, Place a batch of controls, Review an AI tool, the reviewer's checks, the DONE checklist per mode |
| `wind-down-workstream` | Steps, the reference wind-down sequence with dependencies, step states, the filing packet, Plan the wind-down, the reviewer's checks, the DONE checklist |
| copies: `orchestration-workstream`, `task-stack-workstream`, `office-files`, `evidence-check`, `review-facts`, `review-completeness` | Made by `scripts/build_shared.py` from `shared/skills/`; never edited here. `evidence-check` is compliance's own checklist, its source in `shared/skills/` |

## Across departments

- Accounting's audit support dispatches `compliance-reviewer` with the `evidence-check` checklist until accounting converts; then it copies `evidence-check` and briefs its own reviewer with it.
- A wind-down step that ends an entity's recurring filings (S9, S10, S12 done) is a proposal for the compliance calendar's rules owner, never an edit of the calendar.

## What was renamed (2026-10, the plugin conversion)

| Now | Was |
|---|---|
| `compliance-calendar-keeper` | `compliance-calendar-orchestrator`, and `compliance-calendar-tracker` as section Place a batch, run by the worker |
| `compliance-it-governance` | `it-governance-orchestrator`, `it-governance-collector` as section Place a batch of controls and `it-governance-tool-reviewer` as section Review an AI tool, both run by the worker |
| `compliance-entity-wind-down` | `wind-down-orchestrator`, and `wind-down-planner` as section Plan the wind-down, run by the main agent |
| `compliance-reviewer` | `compliance-evidence-checker` (now the `evidence-check` checklist), and the dispatches of the shared `fact-check` and `completeness-audit` agents, now the copied `review-facts` and `review-completeness` checklists |
| `compliance-worker` | new: the calendar and control batches and the tool review |

`task-stack-apply` maps `compliance-calendar-keeper` and `compliance-entity-wind-down` to the old orchestrator names, so a change set's markers match across the rename.

Decided in the conversion (the migration plan's open questions for this department):

- The AI tool review runs on `compliance-worker`, not the main session, so untrusted vendor pages never reach a session that holds Write and Portal tools; the reviewer gets WebFetch to check the review's citations.
- Copies take the whole skill, so `powerpoint-handler` comes with `office-files` though no job uses it.
- One entity-wind-down Automation serves one entity; a second entity is a second Automation with its own Context, run by the same agent.
- The calendar keeper's rule that a reviewer FAIL drops the op and records why is kept in its Steps (step 4).
- Merging the calendar and the wind-down into one agent with modes was left for later: different folders, rules and cadence.
