---
name: project-engagement-workstream
description: "Reference loaded by projects-engagement-kickoff and projects-engagement-closeout (and the projects-reviewer they dispatch), not for a user request; adds to orchestration-workstream. Covers the two ends of an engagement: the private Context and its Sources, the signed SOW as the only baseline, drafts never live files, nothing landing on a person, the name-free harvest, client consent, the claims and checks shapes, and the folder command. The jobs' Steps, packs and DONE checklists are in engagement-kickoff and engagement-closeout."
---

# Project engagement workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Load it by name if it is not loaded. It covers the two ends of an engagement: setting it up from a signed SOW so delivery, the weekly client update and discovery can run, and closing it so nothing is owed in either direction and what was learned is kept. The lifecycle is `project-engagement-runbook`; this skill is how its first and last steps run inside a Run folder. Each end is a job with its own skill: `engagement-kickoff` and `engagement-closeout` hold the Steps, the pack and the DONE checklist.

## The engagement

An engagement is named by its private **Context**: a YAML file, kept with the owner's engagement records and supplied by the caller, that names the engagement's folders as **Sources**. Read it first, and these Sources by name:

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
- **Drafts, never live files.** Rules files, the Context, the briefs and every message are drafts in the Run folder for the owner to adopt. Nothing is sent, nothing is created in the Portal or the client's folders by the session. Task changes are a `changes.json` the owner approves before anything applies it.
- **Read the Portal only:** the client's domain, projects and open tasks, and the owner's contact id from `whoami`.
- **Nothing lands on a person** who has not agreed to receive agent assignments. A task for anyone but the owner is a question.
- **Generic means generic.** A method harvest names no client, person, company, product, figure or place; it reads as if written for any engagement. When in doubt, leave it out.
- **Client consent first** for any reuse that could identify the client, a case study above all. The draft is anonymized and the consent is the owner's question.
- **Revisions are new files** with ` v2`; every reviewer finding is answered, fixed or with a line in `notes` saying why it stands.

## The claims and checks

The main agent keeps `RUN/claims.json` while it drafts: one entry per statement a reviewer must trace, `{"key": "delivery-rules/baseline/M2", "text": "...", "sources": ["SOW 3.2"]}`, and the proposed task ops in the `task-stack-workstream` shape with `confidence`.

The reviewer returns `extra.checks`, one per checklist item it was given: `{"item": "kickoff-2", "verdict": "PASS" | "FAIL", "evidence": "...", "fix": "..."}`. A FAIL carries the exact place and the change that would make it pass.

## The folder command

`projects-engagement-folders CLIENT --workstream NAME [--month YYYY-MM] --dry-run --format json` prints the standard folder set (and, with `--repo-root`, the working repository) it would create, under the owner setting `engagements_dir`. A session runs it only with `--dry-run`; the owner runs it for real once they adopt the plan. Folder names come from `[project-engagement-workstream]` (`general_subfolders`, `workstream_subfolders`, `repo_prefix`).

## Templates

`templates/engagement-decks.md` (the kickoff deck outline) and `templates/it-access-asks.md` (the IT asks list) in this skill's folder.
