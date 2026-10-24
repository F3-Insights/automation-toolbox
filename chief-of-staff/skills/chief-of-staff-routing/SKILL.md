---
name: chief-of-staff-routing
description: How the chief-of-staff front door answers a request in a session the owner started. It finds the job or skill that serves it in the live catalogue of every department, launches a recurring job through the orchestrator fleet or gives the exact line that starts the right department's session, does in-session only what this plugin holds (research a person, an email history or a domain; a work survey; a review of a finished deliverable; one private draft), checks what comes back against its source, and reports answer first. Loaded by the chief-of-staff agent; not for the unattended cycle (chief-of-staff-cycle-runner).
---

# Routing the owner's requests

The front door owns the conversation, not the work. Since each department became its own plugin (ADR 0004), a session holds one department, so another department's skills and agents cannot run here: the front door's job is to know where each request is served and get it there fast, and to do in this session only what this plugin holds. Every answer leads with the result, then the evidence; several choices for the owner are one numbered list they can answer in one line.

## Inputs

- **The request** (required): the owner's words.
- **Standing instructions** (optional): the file the setting `owner_profile` names, read once at the start of the session and followed; never quoted back into anything shared.

## Steps

1. [judgment] Read the request. Settle what the owner wants done and by when; ask only what the request cannot answer and the catalogue cannot settle, as one numbered list.
2. [script] Run `chief-of-staff-catalogue --query "<the request's key words>"` (add `--department D` when the area is clear). It lists the best-matching main agents and owner-started skills of every department, each with its start line and the Automations that run it. With "Where requests go" below, decide which kind of answer this is.
   → served here by research or a draft: step 3
   → a finished deliverable to check: step 4
   → a recurring job with an Automation: step 5
   → an interactive skill or a main agent of another department: step 6
   → nothing in the catalogue serves it: step 6
3. [hand-off: chief-of-staff-worker] Research or draft. One worker per slice, all in one message so they run in parallel: `portal-research`, section Research a person (model haiku), Research email history (haiku) or Research a domain (sonnet), with the subject, the topic and the time frame; or `work-survey`'s gatherers and analysts, with the model its phase names; or `task-stack-produce` for one private draft from a packet you assembled. Give each only what its section needs.
   → returned: step 7
   → BLOCKED: step 1 (max 1)
4. [hand-off: chief-of-staff-reviewer] Check a finished deliverable. The reviewer on the checklist that fits (`review-red-team` for a deck, memo or report read as its audience; `review-facts` for claims against their sources, two reviewers over disjoint halves; `review-numbers` for a package's figures, with `report-tieout`; `review-completeness` for a map or checklist against a reference model), given the artifact and its sources only, never the author's reasoning or what you hope it finds.
   → returned: step 7
5. [script] Launch through the fleet by `orchestrator-fleet`'s "Launching one for a person": `chief-of-staff-fleet-registry list --format json`, then `chief-of-staff-fleet-status --format json`, then `chief-of-staff-fleet-launch NAME --authority trusted --params k=v ...` (add `--dry-run` unless the entry is live or the owner said live). A Run already live or queued is the answer to "start it"; a `spec` entry is not built yet, so say so and give the start line instead.
   → queued, live or refused: step 7
6. [judgment] Hand it over: give the exact start line from the catalogue (`claude --plugin-dir <toolbox>/<department> --agent <department>:<agent>` for a main agent; the plugin and `/<department>:<skill>` for a skill), what to say there, and, for a job with an Automation, that "Run once" in Sentinel starts it too. Never try to run another department's skill here. When nothing serves the request, say so plainly and name the nearest job.
   → handed over: done
7. [judgment] Check what came back against its source before you report it: read the file the worker named, read the record back from the Portal, recompute a figure, or read the fleet's queue line. Where evidence is missing, say what is missing instead of supplying it, and name any risk you see. Report answer first; the owner's decisions as one numbered list.
   → reported: done

## Where requests go

The catalogue is the live list; this is the shape of it, so a request lands in the right department even when its words do not match. Department names are the plugin folders.

| When the owner asks for | Where | Notes |
|---|---|---|
| Who is this person, what have we said to them, where does this area stand | here: `chief-of-staff-worker` on `portal-research` | Person and email history at haiku, a domain at sonnet; a domain brief recommends follow-on passes, which you dispatch |
| A finished deliverable checked before it goes | here: `chief-of-staff-reviewer` on a `review-*` checklist | Artifact and sources only |
| Where a working life's hours go, deeply, once | here: `work-survey` (owner-started), its gatherers and analysts as `chief-of-staff-worker` slices | A recurring time study is productivity's `time-study` |
| What the automation did today, what waits on me from it | here: the fleet's status and today's `<display name> Receipt` note | The unattended cycle is `chief-of-staff-cycle-runner`, its own Automation |
| A recurring job run now ("run the weekly review", "start the task reconciliation") | the fleet: step 5 | The registry is the list; read it, never memory |
| Email: a reply, a batch of replies, a new email, chasing what I am owed | productivity: `comms-reply-to-email`, `comms-inbox-replies`, `comms-draft-email`, `comms-follow-ups`; unattended, `email-replier`, `comms-steward` | Drafts only; nothing is sent |
| A meeting prepared, logged, written up or followed up | productivity: `meeting-prep`, `meeting-log`, `meeting-followup`, `meeting-portal-notes`, `meeting-summary`; a whole day or the Fellow queue, `meeting-steward` | |
| Something captured, a call logged, a contact updated | productivity: `quick-capture`, `comms-log-call`, `crm-contact-update` | |
| My task list cleaned up, the weekly review, the calendar, where my time went | productivity: `task-steward`, `gtd-weekly-review`, `calendar-steward`, `time-study` | |
| The day started, or wrapped | recurring-summaries: `start-session`; the plan itself, `daily-planner` | |
| A project's status line, a check-in, the portfolio against the goals | projects: `project-status-update`, `project-checkin`, `project-landscape`; the weekly pass, `projects-health-review` | |
| An engagement kicked off, delivered, closed out | projects: `projects-engagement-kickoff`, `projects-client-delivery`, `projects-engagement-closeout`, `project-engagement-runbook` | |
| Interviews synthesized, a process mapped, a workshop, automation scoped | process-engineering: `interview-synthesis`, `process-engineering-process-flow`, `workshop-design`, `process-engineering-automation-scoping` | |
| The weekly leadership report, a board package, a client update or status memo | reporting: `weekly-reporter` (with the executive) or `reporting-weekly-report`, `reporting-board-package`, `reporting-client-update`, `comms-client-status-update` | |
| The month-end close, an entry, a reconciliation, billing, collections, 1099s | accounting: `accounting-month-end-close`, `month-end-journal-entry`, `month-end-reconciliation`, `accounting-firm-billing`, `accounting-collections-review`, `accounting-vendor-1099` | A person uploads every entry |
| A forecast, a budget, cash, a one-off analysis | finance: `finance-forecast`, `finance-budget`, `finance-cash-forecast`, `finance-analysis` | |
| Pipeline, a new lead, a proposal or SOW | sales: `sales-pipeline-review`, `sales-lead-intake`, `sales-proposal-writer` | |
| Goals against the work, a plan stress-tested | strategy: `strategy-goal-alignment`, `pre-mortem` | |
| GitHub issues built into pull requests, a release, a bug, the architecture | software: `software-developer`, `software-release-prep`, `software-diagnose-bugs`, `software-improve-architecture`, `software-grill-with-docs` | |
| Filings and renewals, an entity wound down, AI tool governance | compliance: `compliance-calendar-keeper`, `compliance-entity-wind-down`, `compliance-it-governance` | |
| A seminar, a learning community session; a post or case study | learning: `learning-seminar-builder`, `learning-community-host`; marketing: `marketing-post-writer`, `marketing-case-study-writer` | |
| How I decide, written down | decision-playbooks: `decision-playbooks-curator`, `playbook-ratification` | |
| Household, health, home, personal money and taxes | personal: its five agents | Private; nothing to the Portal |
| The toolbox itself audited, new skills harvested | toolbox-maintenance: `toolbox-maintenance-auditor`, `toolbox-maintenance-skill-harvester` | |
| Writing cleaned up | here: `unslop`'s five principles; an audience-specific edit is the `unslop-*` skill of the department that owns the text | |

## What needs the owner's go-ahead

Work that stays inside the owner's own records and can be undone (a local file, a research brief, a private draft, a dry-run launch) proceeds without asking, unless the standing instructions say otherwise. Ask first for anything another person would see or that cannot easily be reversed: a live launch of an entry not yet `live`, sending, deploying, pushing, a migration, deleting, money, or someone else's private data. A clear go-ahead in this conversation covers the step it was given for.

## Fan-out

- Independent workers go out in one message, so they run in parallel: five people to research is five dispatches in one turn.
- A worker cannot dispatch and cannot ask the owner. If it comes back blocked, answer it and dispatch again; never have it guess.
- Never dispatch a main agent as a sub-agent: it must be the main session of its own Run to dispatch its own workers. That is what launching and handing over are for.
- The reviewer gets the artifact and its sources, never the author's reasoning, the outline or the verdict you expect.

## Done when

The owner has the answer or the next action, each claim in it checked against its source (or named as unchecked), with any decisions of theirs as one numbered list.
