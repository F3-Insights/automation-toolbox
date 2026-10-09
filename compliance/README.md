# Compliance & Governance

Keeps an organization's legal and governance obligations from slipping: a compliance calendar of filings, renewals and registrations placed on evidence each week, IT and AI governance worked as a control checklist (evidence per period, third-party AI tool reviews, the annual policy refresh), and a legal entity's wind-down driven step by step to dissolution. For a controller, a fractional CFO or an operations lead who owns those deadlines. Agents find evidence, prepare paper and propose tasks; people file, pay, sign and send.

## Agents

| Agent | What it does | Needs |
|---|---|---|
| `compliance-calendar-orchestrator` | Weekly pass over the compliance calendar: places every item's current occurrence, has filed claims checked, proposes owner tasks and calendar changes | Insights Portal; command `task-stack-apply` (after the session) |
| `it-governance-orchestrator` | Runs IT and AI governance in three modes: control evidence for a period, one AI tool review, or the policy-refresh gap list | Insights Portal |
| `wind-down-orchestrator` | Drives one entity's wind-down: places every step of the reference sequence, prepares filing packets, proposes owner tasks | Insights Portal; command `task-stack-apply` (after the session) |
| `compliance-calendar-tracker` | Places one batch of calendar items on evidence and proposes task ops and calendar changes | Insights Portal |
| `compliance-evidence-checker` | Independent PASS or FAIL on evidence claims for the calendar, IT governance and audit support | Insights Portal |
| `it-governance-collector` | Places one batch of approved, effective controls for a period on artifacts | Insights Portal |
| `it-governance-tool-reviewer` | Reviews one third-party AI tool's published terms against the data-privacy policy and proposes a verdict | web access |
| `wind-down-planner` | Places each wind-down step on evidence, orders what is next, prepares field-by-field filing packets | commands `pdf-handle`, `excel-handle` |

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `compliance-calendar-workstream` | The calendar file and item shape, lead-time arithmetic, what counts as evidence of filing, occurrence states, the DONE checklist | none |
| `it-governance-workstream` | Controls worked as checklist rows, evidence only against approved and effective controls, the AI tool review standard, the policy refresh, the DONE checklist per mode | none |
| `wind-down-workstream` | The reference wind-down sequence with dependencies, step states, the filing packet, legal judgments routed to counsel, the DONE checklist | none |

All three extend `orchestration-workstream` (software). The calendar and wind-down pieces also use `task-stack-workstream` (productivity). The IT-governance and wind-down orchestrators dispatch `completeness-audit` (process-engineering) and `fact-check` (reporting). `compliance-evidence-checker` also serves `audit-support-workstream` (accounting).

## Scripts

This department holds no scripts. Its pieces run three from productivity, by path: `task_stack_apply.py` in `task-stack-workstream` (the calendar and wind-down change sets, after the session; it needs `portal_mcp_config`, `state_dir` and the Portal bearer in `INSIGHTS_PORTAL_ASSISTANT_TOKEN`), and `pdf_handle.py` and `excel_handle.py` in `office-files` (`wind-down-planner`; `pypdf` and `openpyxl`). The skills' "Later tools" sections name planned commands (`compliance-check`, `compliance-record`, `governance-check`, `governance-record`, `wind-down-check`, `state-filing-lookup`) that do not exist yet and are not needed to run.
