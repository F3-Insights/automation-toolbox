# Personal

The owner's own life admin, run with the same care as the business work: a household chief of staff for one member of the household, a weekly health check-in against the owner's own goals, a weekly read of the home's own equipment against the owner's inventory, a monthly household finance review, and tax season worked like an auditor's request list. The topics are personal; nothing in these files describes a real person, home or account. Every fact (who is in the household, which accounts, which hosts, which goals) lives in the owner's private rules files, Contexts and settings outside this repository.

These run only for the owner. The owner, or a schedule the owner set, launches each orchestrator; no other orchestrator does. They write only in the private domain folder their Context names, never message anyone, and send nothing to the Insights Portal: no skill here writes to it.

## Agents

| Agent | What it does | Needs |
|---|---|---|
| `household-orchestrator` | Interviews one household member through the owner, then keeps one weekly pain point's obligations dated and sourced | none; dispatches `fact-check` (reporting) |
| `health-routine-orchestrator` | Weekly health check-in: each metric against the owner's target, with trend and the dates due in 30 days (draft) | none; dispatches `fact-check` (reporting) |
| `home-infrastructure-orchestrator` | Weekly read of the home equipment the owner's rules list, with at most one confirmed retirement proposal (draft) | none |
| `personal-finance-review-orchestrator` | Monthly one-page household review from the owner's own review engine, every figure traced | none; dispatches `numbers-reviewer` (reporting) |
| `personal-tax-season-orchestrator` | Tax documents as a checklist: what is in this year's folder and what is still owed, by whom | none; dispatches `fact-check` (reporting) and `completeness-audit` (process-engineering) |
| `household-steward` | Reads the allowed sources and proposes ledger rows, reminders and the weekly page | none |
| `health-routine-analyst` | Reads the week's data exports the rules name and drafts the check-in (draft) | the owner's exports |
| `home-infrastructure-analyst` | Runs the read-only commands the owner granted, or reads exports, and flags what needs attention (draft) | the owner's private grants |
| `home-infrastructure-checker` | Independent PASS or FAIL on the week's one retirement proposal (draft) | the owner's private grants |
| `personal-finance-review-analyst` | Answers the month's checks from the review engine's outputs and drafts the agenda | none |
| `personal-tax-season-analyst` | Builds the document checklist from last year's folder and matches this year's by form type | none |

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `personal-workstream` | Reference: privacy rules, the domain folder's shape and the return tests every personal piece shares | none |
| `household-method` | The interview, the obligations ledger, the weekly page, DONE | none |
| `health-routine-method` | Metrics against targets from the owner's exports, reminders, DONE (draft) | none |
| `home-infrastructure-method` | What to flag, one retirement a week, DONE (draft) | none |
| `personal-finance-review-method` | The month's checks from the review engine, the agenda and figure ledger, DONE | none |
| `personal-tax-season-method` | The prior-year folder as the template, matching by form type, what is still owed, DONE | none |

All extend `orchestration-workstream` (software) through `personal-workstream`.

## Drafts

`health-routine-method` and `home-infrastructure-method`, with their orchestrators and workers, are marked `maturity: draft`. They ship without commands, settings or credentials and are not yet runnable as is: the owner's rules file names the read-only commands or data exports to use, and the owner grants any command outside this repository once it is audited.

## Needs

No Insights Portal and no ERP. Each orchestrator needs a private Context naming its domain folder and rules file (`HOUSEHOLD-RULES.md`, `HEALTH-ROUTINE-RULES.md`, `HOME-INFRA-RULES.md`, `PERSONAL-FINANCE-RULES.md`, `TAX-SEASON-RULES.md`), which the owner keeps outside this repository. The finance review also needs the owner's own household review engine (a local repository that ties the banks' exports out); it is not part of this toolbox.
