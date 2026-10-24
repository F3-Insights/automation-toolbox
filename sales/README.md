# Sales & Business Development

Keeps a consultant's or small firm's pipeline moving and answers new leads fast. A weekly pass gives every open pursuit a dated next step and drafts the nudge for each stuck one; a lead pass turns an inbound enquiry into a one-page brief, a fit score and a reply draft the same day; a proposal pass drafts a short proposal or statement of work from the owner's own precedent and audits the contract documents for tracked changes, broken references and contradictions. Every message is a draft; nothing is sent. Each owner keeps a `BD-RULES.md` (system of record, pipeline target, services list, stuck threshold and cooldown, proposal house style and reference documents), passed in the Run's BD Context; it is an owner input, not part of this repository.

## The plugin

This folder is a standalone Claude Code plugin named `sales` (`.claude-plugin/plugin.json`), built the way [software](../software/README.md#the-plugin) is: one short main agent per job, one `sales-worker` and one `sales-reviewer` for dispatched work, the know-how in the jobs' skills as `##` sections, and every script a named command in `bin/` (`python3 scripts/build_bins.py sales`). A main agent's first instruction is to load its skills with the Skill tool.

```bash
claude --plugin-dir ~/coding-projects/automation-toolbox/sales --agent sales:sales-pipeline-review
```

From Sentinel, an Automation launches a main agent by name; the overlay's `subagents:` lists `sales-worker` and `sales-reviewer` for the pipeline, the reviewer alone for lead intake and proposals.

## Jobs and agents

| Agent | Automation | What it does | Dispatches |
|---|---|---|---|
| `sales-pipeline-review` | bd-pipeline | Weekly pass: a dated next step per pursuit, checked nudge drafts for stuck ones, the pipeline against target, new leads as launch lines | worker: pursuit batches, nudge drafts, research; reviewer: each draft |
| `sales-lead-intake` | bd-lead-intake | One inbound lead: research, lead brief with fit score, checked reply draft, proposed pursuit | reviewer: the reply draft |
| `sales-proposal-writer` | bd-proposal | One proposal or SOW drafted from the owner's precedent and its contract documents audited; an audit-only pass on any agreements | reviewer: contract audit, facts, red team; the audit again on the revision |
| `sales-worker` | | One slice of the pipeline pass, following the named `bd-workstream` section | none |
| `sales-reviewer` | | Independent PASS or FAIL against the named checklist section; edits nothing | none |

## Skills

| Skill | Run by | What it holds |
|---|---|---|
| `bd-pipeline`, `bd-lead-intake` | the pipeline pass, lead intake | Each job's Steps and DONE checklist |
| `bd-workstream` | both BD jobs, worker, reviewer | Rules first, one system of record, the pursuit row, the lead brief and fit score; sections Read the pipeline, Judge a batch of pursuits, Research a person and a thread, Write the lead brief, Draft a message; checklist Check a staged draft |
| `bd-proposal-workstream` | proposal writer, reviewer | Steps; section Draft the proposal; checklist Audit the contract documents; DONE |
| `automation-backlog-format` (shared copy) | proposal writer | The automation backlog's CSV and business cases: the file contract with process-engineering |
| `review-facts`, `review-red-team` (shared copies) | reviewer | The proposal's client facts and its read as the buyer |
| `task-stack-workstream` (shared copy) | pipeline, lead intake | The change-set shape for proposed next-step tasks and pursuits |
| `office-files` (shared copy) | proposal writer, reviewer | `pdf-handle` (and `excel-handle`, `powerpoint-handler`) |
| `orchestration-workstream`, `unslop`, `unslop-email`, `unslop-proposal` (shared copies) | all | Conduct and return; plain writing for mail and contracts |

## Commands

In `bin/`, each a shared copy's command with one unprefixed name: `pdf-handle` (a PDF's text and comments page by page; needs `pypdf`), `excel-handle`, `powerpoint-handler`, and `task-stack-apply`, `task-stack-check`, `task-stack-queue`, `task-stack-report`. Proposed next-step tasks wait in `RUN/changes.json`; applying them is `task-stack-apply` after a session, once a dry run has been read (no Automation runs it yet), and needs `portal_mcp_config` and the Portal bearer (`INSIGHTS_PORTAL_ASSISTANT_TOKEN`). Planned and not yet built: `bd-pipeline-pull`, `bd-pipeline-check`, `docx-redlines`, `contract-xref-check`. Each command prints `--help`.

## Hand-offs

- **From process-engineering.** Automation scoping files its backlog in the engagement's working folder in the `automation-backlog-format` contract, which both plugins hold a copy of, and its report says "chosen items: launch `bd-proposal` with the backlog path". `sales-proposal-writer` reads that backlog as discovery notes: the chosen items are the scope, written as qualitative goals; the values are the client's case, never the fee. The process-engineering README names the same contract.
- **Pipeline → lead intake.** A new lead the pipeline pass finds is a launch line in its report, never a dispatch.

## Decisions taken in the conversion

- **The research, drafting and draft-check know-how is sales' own** (`bd-workstream` sections), condensed from productivity's `portal-research`, `email-drafter-method` and `comms-draft-check` (plan risk 1). Decided: those three are productivity's skills, not shared ones, and moving them to `shared/skills/` changes productivity's commands; once they are shared, sales should copy them and drop its sections.
- **The cooldown is checked by the reviewer** (Check a staged draft, test 2) from the Portal's drafts and touches, with the days in `BD-RULES.md`. The code gate (productivity's `outbound-check`) comes with that copy.
- **No `comms-confirm`** (plan open question 4): questions go in the report as one numbered list, the Automation's `for_owner`, as productivity's do.
- **Drafting in the owner's voice runs at opus.** The worker is sonnet by default; the pipeline's draft step names model opus, and lead intake drafts in the opus main session.
- **Lead intake has no worker:** one lead, two small research reads, done by the main agent.
- **Agent names** follow the plan and `task-stack-apply`'s rename map (`sales-pipeline-review`, `sales-lead-intake`), so change sets signed by either the old or the new name keep their markers; the job skills are `bd-pipeline` and `bd-lead-intake` because a skill may not share an agent's name.

## Renamed in the conversion (2026-10)

| Now | Was |
|---|---|
| `sales-pipeline-review` | `bd-pipeline-orchestrator` |
| `sales-lead-intake` | `bd-lead-intake-orchestrator` |
| `sales-proposal-writer` | `bd-proposal-orchestrator` |
| `sales-worker` on `bd-workstream`, section Judge a batch of pursuits | `bd-pursuit-analyst` (pursuits) |
| the main agent, on `bd-workstream`, section Write the lead brief | `bd-pursuit-analyst` (a lead) |
| the main agent, on `bd-proposal-workstream`, section Draft the proposal | `bd-proposal-drafter` |
| `sales-reviewer` on `bd-proposal-workstream`, section Audit the contract documents | `bd-contract-auditor` |
| `sales-worker` or the main agent, on `bd-workstream`, section Draft a message | `productivity-worker` on `email-drafter-method` |
| `sales-reviewer` on `bd-workstream`, section Check a staged draft | `productivity-reviewer` on `comms-draft-check` |
| the main agent or `sales-worker`, on `bd-workstream`, sections Read the pipeline and Research a person and a thread | `productivity-worker` on `portal-research` |
| `sales-reviewer` on `review-facts`, `review-red-team` | `fact-check`, `executive-red-team` (reporting) |
| the job skills `bd-pipeline`, `bd-lead-intake` | `bd-workstream`'s two DONE lists |

## Depends on other departments

None at run time: what it needs from elsewhere is copied in from `shared/skills/`. It reads and writes through the Insights Portal MCP server (drafts only).
