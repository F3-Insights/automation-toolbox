---
name: project-engagement-workstream
description: Reference loaded by project-engagement-writer and project-engagement-checker and read by the kickoff and closeout orchestrators, not for a user request; adds to orchestration-workstream. Covers the engagement's private Context and rules first, the signed SOW as the only baseline, the kickoff pack (background, rules drafts, briefs, comms drafts, folder plan, the first two weeks as proposed tasks), the closeout pack (acceptance evidence, final invoice check, lessons, a name-free method harvest, a case study draft), the DONE checklists and the claims and checks shapes.
---

# Project engagement workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Load it by name if it is not loaded. It covers the two ends of an engagement: setting it up from a signed SOW so the delivery, weekly update and discovery orchestrators can run, and closing it so nothing is owed in either direction and what was learned is kept. The lifecycle is `project-engagement-runbook`; this skill is how its first and last steps run inside a Run folder.

## The engagement

An engagement is named by its private **Context**: a YAML file, kept with the owner's engagement records and supplied by the caller, that names the engagement's folders as **Sources**. The orchestrator reads it first and these Sources by name:

| Source | Holds | Access |
|---|---|---|
| `rules` | The folder for `DELIVERY-RULES.md`, `UPDATE-RULES.md`, `DISCOVERY-RULES.md`, `ENGAGEMENT-CONTEXT.md` | read |
| `sow` | The signed SOW (a file or the folder holding it) | read only |
| `engagement`, `engagement-*` | The client folders | read only |
| `working` | The delivery working folder (`PLAN.md`, `RAID.csv`, `DELIVERY-EVIDENCE.csv`) | read only |
| `delivery` | Where finals were shared with the client | read only |
| `billing` | The firm-billing folder for this client (invoices, the billing ledger) | read only |
| `repo` | The engagement's build repository, when there is one | read only |

At kickoff most of these do not exist yet: the kickoff proposes them. A Source missing at closeout is a gap to report.

## Conduct here

- **The SOW is the only baseline.** Scope, milestones, acceptance, dates and fees come from the signed SOW and are cited by section. Nothing is filled from a proposal deck, a transcript or a reading of the work. No signed SOW: stop the kickoff and ask for it.
- **Drafts, never live files.** Rules files, the Context, the briefs and every message are drafts in the Run folder for the owner to adopt. Nothing is sent, nothing is created in the Portal or the client's folders by the session.
- **Nothing lands on a person** who has not agreed to receive agent assignments. A task for anyone but the owner is a question.
- **Generic means generic.** A method harvest names no client, person, company, product, figure or place; it reads as if written for any engagement.
- **Client consent first** for any reuse that could identify the client, a case study above all. The draft is anonymized and the consent is the owner's question.

## Kickoff (`project-engagement-kickoff-orchestrator`)

The pack, in `drafts/`:

| File | What | By |
|---|---|---|
| `BACKGROUND.md` | The client, its people by role, systems, calendar | this skill |
| `ENGAGEMENT-CONTEXT.md` | The sections `client-update-workstream` defines | this skill |
| `DELIVERY-RULES.md` | `## Scope baseline` from the SOW, cited, plus the delivery settings | `client-delivery-workstream` |
| `UPDATE-RULES.md`, `DISCOVERY-RULES.md` | Audience, cadence, variant; topics and sponsor | the update and discovery skills |
| `Kickoff Brief <date>.md` | Runbook steps 4 and 5: the setup order, the kickoff deck outline (`templates/engagement-decks.md` in this skill), the IT asks (`templates/it-access-asks.md` in this skill) | `project-engagement-runbook` |
| `Onboarding Brief <date>.md` | The two-page teammate brief | `project-engagement-onboarding` |
| `comms/` | Sponsor framing note, technical invite, all-staff announcement, interview invites (the `engagement-comms-set` skill), as files | `unslop-email` |
| `folder-plan.json` | `python3 ~/.claude/skills/project-engagement-workstream/scripts/engagement_folders.py --dry-run --format json` output | the tool |
| `context-proposal.yaml` | The private Context this engagement needs, with the Sources above | this skill |
| `changes.json` | The first two weeks as task-stack `create` ops, in the `task-stack-workstream` shape | `task-stack-workstream` |

DONE:

1. The signed SOW is read and cited; without it the kickoff stops at a question.
2. Every scope item, milestone, acceptance test, date and fee term in the drafts cites an SOW section, and nothing is in the baseline that the SOW does not say (checker).
3. Every proposed task has a verb-first title, a project or domain, a due date, and the owner as its owner; anyone else's work is a question (checker).
4. A Portal project for the engagement is a question for the owner, never an op.
5. The Context proposal marks a build repository private and names no path the owner has not given.
6. Every message is a file; none is sent or staged as a draft in a mailbox.
7. The red team, reading the kickoff brief as the client sponsor, at or above the bar.

## Closeout (`project-engagement-closeout-orchestrator`)

The pack, in `drafts/`:

| File | What |
|---|---|
| `Acceptance <date>.md` | Each SOW acceptance item: `accepted` (evidence and the owner's or client's confirmation), `delivered` (evidence, no confirmation), `missing`; the source of each |
| `Final Invoice Check <date>.csv` | `line,sow_ref,basis,amount_due,invoiced,invoice_ref,paid,difference,note`, one row per fee line or month the SOW bills |
| `Lessons <date>.md` | What happened, why, what to do next time, each with a source; the `lessons-learned` format the pre-mortem uses |
| `harvest/` | Method worth keeping, one draft per pattern in the house skill format, name-free, for the owner to move into the skills inbox |
| `Case Study <date>.md` | Problem, approach, outcome, anonymized, marked DRAFT, by `unslop-editorial` |
| `changes.json` | The engagement's open Portal tasks: `complete` on evidence, `cancel` on the rules' conditions, else a question |
| `context-closeout.md` | The proposed closing revision of `ENGAGEMENT-CONTEXT.md` |

DONE:

1. Every SOW acceptance item has a state and evidence, or a question for the owner (checker).
2. Every fee line ties: invoiced against the SOW basis, paid against the ledger, differences named (`numbers-reviewer`).
3. Every lesson cites a source (a transcript, a status memo, a RAID row, a log entry).
4. The harvest drafts hold no client, person, company or product name and no figure from the engagement (checker).
5. The case study is anonymized, marked DRAFT, and the client's consent is the owner's question.
6. Every open Portal task in the engagement's domain has an op or a question.
7. The red team, reading the case study as a prospective client, at or above the bar.

## The returns here

**The writer** (`project-engagement-writer`): the shared block, `files` the drafts written, `extra.claims` one entry per statement a checker must trace (`{"key": "delivery-rules/baseline/M2", "text": "...", "sources": ["SOW 3.2"]}`), and `extra.ops` the proposed task ops in the `task-stack-workstream` shape with `confidence`.

**The checker** (`project-engagement-checker`): the shared block with `extra.checks`, one per checklist item it was given, `{"item": "kickoff-2", "verdict": "PASS" | "FAIL", "evidence": "...", "fix": "..."}`.

## Later tools

- `engagement-pack`: resolve the Context and copy the SOW, the delivery ledgers and the billing rows into the Run folder before the session.
- `sow-extract`: the SOW's sections, milestones and fee lines as cited rows.
- `closeout-invoice-tie`: tie the SOW fee lines to the firm-billing ledger.
- `harvest-name-check`: the name guard over the harvest drafts before a person files them.
- `engagement-publish`: file the adopted drafts into the engagement's folders as new files.
- A finish step running `task-stack-apply` on `changes.json` once the owner has approved it.
