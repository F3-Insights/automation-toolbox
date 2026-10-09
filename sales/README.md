# Sales & Business Development

Keeps a consultant's or small firm's pipeline moving and answers new leads fast. A weekly pass gives every open pursuit a dated next step and drafts the nudge for each stuck one; a lead pass turns an inbound enquiry into a one-page brief, a fit score and a reply draft the same day; a proposal pass drafts a short proposal or statement of work from the owner's own precedent and audits the contract documents for tracked changes, broken references and contradictions. Every message is a draft; nothing is sent. Each owner keeps a `BD-RULES.md` (system of record, pipeline target, services list, stuck threshold, proposal house style and reference documents), passed in the Run's BD Context; it is an owner input, not part of this repository.

## Agents

| Agent | What it does | Needs |
|---|---|---|
| `bd-pipeline-orchestrator` | Weekly pipeline pass: a dated next step per pursuit, checked nudge drafts for stuck ones, pipeline against target | Insights Portal (or a tracker file), `BD-RULES.md` |
| `bd-lead-intake-orchestrator` | Answers one inbound lead: research, lead brief with fit score, checked reply draft, proposed pursuit | Insights Portal, `BD-RULES.md` |
| `bd-proposal-orchestrator` | Drafts one proposal or SOW and audits the contract documents; audit-only pass on any agreements | `BD-RULES.md`, command `pdf-handle` |
| `bd-pursuit-analyst` | Judges each pursuit's stage, state and next step; writes the lead brief and fit score | Insights Portal |
| `bd-proposal-drafter` | Writes a short first draft in the house style with price and terms as placeholders | command `pdf-handle` |
| `bd-contract-auditor` | Independent audit of tracked changes, cross-references and contradictions across documents | command `pdf-handle` |

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `bd-workstream` | The BD method: system of record, pursuit row, stuck rule, lead brief and fit score, DONE checklists | `BD-RULES.md` |
| `bd-proposal-workstream` | The proposal and contract-audit method: newest copy first, house precedent, short drafts, audit rows, DONE checklist | `BD-RULES.md` |

Both skills build on `orchestration-workstream` (software). The agents also use, by name: `person-researcher`, `email-researcher`, `domain-researcher`, `email-drafter`, `comms-draft-checker`, `comms-confirm`, `task-stack-workstream` (productivity); `fact-check`, `executive-red-team` (reporting); `unslop-proposal` (marketing).

## Scripts

This department holds no scripts. Its agents run two from productivity, by path: `python3 ~/.claude/skills/office-files/scripts/pdf_handle.py --operation text --pdf-path FILE` (`bd-proposal-drafter`, `bd-contract-auditor`; it prints each page's text, then any comments) and `task_stack_apply.py` in `task-stack-workstream`, which applies the proposed next-step tasks after a Run and needs `portal_mcp_config` and the Portal bearer (`INSIGHTS_PORTAL_ASSISTANT_TOKEN`). `pdf_handle.py` needs `pypdf`. Planned and not yet built: `bd-pipeline-pull`, `bd-pipeline-check`, `docx-redlines`, `contract-xref-check`.
