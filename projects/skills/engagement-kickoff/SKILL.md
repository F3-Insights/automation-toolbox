---
name: engagement-kickoff
description: "The engagement kickoff job, loaded by projects-engagement-kickoff and by the projects-reviewer it dispatches, not for a user request; extends project-engagement-workstream. Covers the Steps from a signed SOW to the kickoff pack as drafts (background, engagement context, delivery, update and discovery rules with the baseline cited, kickoff and onboarding briefs, the first client notes as files, the folder plan, the Context proposal, the first two weeks as proposed tasks), the files the other jobs read, the DONE checklist and section Check the kickoff pack. For a run, start projects-engagement-kickoff."
---

# Engagement kickoff

Load `orchestration-workstream`, `project-engagement-workstream` and `task-stack-workstream` first: the conduct, the Context and Sources and the change-set shape come from them. The goal: the day after an SOW is signed, the owner has everything the engagement needs to start, ready to adopt, with the scope baseline taken word for word from the SOW, nothing invented and nothing sent.

## Inputs

- **Engagement**: kebab-case, and its Context if one exists yet.
- **SOW**: the signed SOW's path, when the Context has no `sow` Source.
- **Instructions** (optional): they override the defaults, never a rules file.
- **Dry run**: read the SOW and say what would be drafted, proposed and asked; dispatch nothing.

## Steps

For `projects-engagement-kickoff`. Write a `RUN/LOG.md` line before each hand-off.

1. [judgment] Orient. Read the Context if it exists, the SOW, and the Portal for the client's domain and projects (`whoami`, `search`, `list_entities`).
   → no signed SOW: step 7
   → dry run: step 7
2. [judgment] Already done? A rules file, brief or Context that already exists is read and improved on as a proposal beside it, never replaced.
3. [script] `projects-engagement-folders CLIENT --workstream NAME --dry-run --format json` for the client and each SOW workstream; write its output to `RUN/drafts/folder-plan.json`.
4. [judgment] Write the kickoff pack yourself, by section Write the kickoff pack, keeping `RUN/claims.json` as you go.
5. [hand-off: projects-reviewer] Two reviewers in one message, each with the drafts and their sources only: one on section Check the kickoff pack (items 2 and 3, with the SOW, `RUN/claims.json` and the ops); one on `review-red-team` with only the kickoff brief, the client sponsor as reader and the purpose "can we start on Monday, and what do you need from me". Save each verdict to `RUN/reviews/`.
   → a FAIL or a grade under the bar: step 4 (max 1)
6. [judgment] Write `RUN/changes.json` from the checked ops in the `task-stack-workstream` shape, `"orchestrator": "projects-engagement-kickoff"`, `dry_run` as this Run is. It is not applied: the owner approves it first.
7. [judgment] Close. Walk the DONE checklist into `RUN/DONE.md`, item by item, `met`, `n/a` with a reason, or open; write `RUN/STATUS.md`; report the owner's decisions as one numbered list, each with a recommendation: the signed SOW if it is missing; create the Portal project; adopt the rules files and the Context; run the folder command; any assignment to a person other than the owner.
   → reported: done

## Write the kickoff pack

In `RUN/drafts/`:

| File | What | By |
|---|---|---|
| `BACKGROUND.md` | The client, its people by role, systems, calendar | this skill |
| `ENGAGEMENT-CONTEXT.md` | The sections in The files the other jobs read | this skill |
| `DELIVERY-RULES.md` | `## Scope baseline` from the SOW, cited, plus the delivery settings | `client-delivery-workstream` |
| `UPDATE-RULES.md`, `DISCOVERY-RULES.md` | Audience, cadence, variant; topics and sponsor | The files the other jobs read |
| `Kickoff Brief <date>.md` | Runbook steps 4 and 5: the setup order, the kickoff deck outline (`project-engagement-workstream`'s `templates/engagement-decks.md`), the IT asks (its `templates/it-access-asks.md`) | `project-engagement-runbook` |
| `Onboarding Brief <date>.md` | The two-page teammate brief | `project-engagement-onboarding` |
| `comms/` | Sponsor framing note, technical invite, all-staff announcement, interview invites, as files | `engagement-comms-set`, edited with `unslop-email` |
| `folder-plan.json` | The folder command's dry-run output | step 3 |
| `context-proposal.yaml` | The private Context this engagement needs, with the Sources in `project-engagement-workstream` | this skill |

And the first two weeks as task-stack `create` ops (verb-first title, the project or domain, a due date, the owner as owner), kept for `RUN/changes.json`.

Read the SOW first and cite it by section in every scope, milestone, acceptance, date and fee statement, and list each in `RUN/claims.json`. What the SOW does not say is a question, never a fill.

## The files the other jobs read

The kickoff drafts these for other jobs; their shapes are those jobs' contracts, kept here so the drafts fit.

- **`DELIVERY-RULES.md`** (this department's client delivery): `- Key: value` lines under `## Delivery inputs`: Portal domain, SOW (`;`-separated paths relative to the rules folder, or `missing`, or `none ...`), Lead time days (10), RAID review days (14), Session stale days (4), Lookback days (14), Assignable (Portal contact ids), Client email domains, Source folders, Never open; then a `## Scope baseline` table, one row per SOW milestone with its id, acceptance test, due date and SOW section.
- **`UPDATE-RULES.md`** (reporting's weekly client update): `- Key: value` lines under `## Update inputs`: Variant (deck or memo), Update day (default Friday), Cover email (required for a memo), Default length (weekly or full), Portal domain, Client email domains, Source folders, Never open, Recipients (`;`-separated), Engagement context (default `ENGAGEMENT-CONTEXT.md`).
- **`DISCOVERY-RULES.md`** (process engineering's discovery): `- Key: value` lines under `## Discovery inputs`: Sponsor, Topics, Interviews, Anonymize, Assessment invited, Workshop, Rates, Red team bar (default B), Never open.
- **`ENGAGEMENT-CONTEXT.md`** (read by the weekly client update and discovery every Run; agents propose revisions, never edit it): a header line `Private. Owner: <owner>. As of <yyyy-mm-dd>.`, then `## Background and goals`, `## Stakeholders` (`| Person | Role | Cares about | Gets the update |`), `## Recent politics and feedback`, `## Recent meetings`, `## Deliverables` (`| Deliverable | State | Date | Where | Source |`), `## Outstanding` (`| Item | Owner | Due | Waiting on | Source |`), `## Timeline` (`| Date | Milestone | Planned or actual | Source |`), `## Changes`. Every line carries its trace in brackets; a line no source supports is marked `(owner to confirm)`.

Once adopted, the owner arms the Automations that read them: client delivery, the client weekly update and the discovery intake for this engagement. That is a `for_owner` item, never a dispatch.

## DONE

1. The signed SOW is read and cited; without it the kickoff stops at a question.
2. Every scope item, milestone, acceptance test, date and fee term in the drafts cites an SOW section, and nothing is in the baseline that the SOW does not say (reviewer).
3. Every proposed task has a verb-first title, a project or domain, a due date, and the owner as its owner; anyone else's work is a question (reviewer).
4. A Portal project for the engagement is a question for the owner, never an op.
5. The Context proposal marks a build repository private and names no path the owner has not given.
6. Every message is a file; none is sent or staged as a draft in a mailbox.
7. The red team, reading the kickoff brief as the client sponsor, at or above the bar.

## Check the kickoff pack

For the `projects-reviewer`, given the drafts' paths, the SOW, `RUN/claims.json`, the proposed ops and the checklist items to check, never the drafter's reasoning.

- **SOW tracing (item 2).** For every claim listed and every scope, milestone, acceptance, date and fee line in the drafts, open the cited SOW section and confirm it says that. A statement with no SOW support in a baseline is a FAIL, however reasonable. A line in a baseline the claims list missed is a FAIL too.
- **Assignments (item 3).** Every proposed op's owner is the owner's contact (`whoami`) or absent; anything else must be a question. Every title starts with a verb; every op has a project or domain and a due date.

Return the `orchestration-workstream` block with `extra.checks`, one per item, as `project-engagement-workstream` gives it.
