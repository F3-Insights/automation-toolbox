---
name: client-delivery-workstream
description: Reference loaded after orchestration-workstream by the planner, task steward and risk analyst of client-delivery-orchestrator, not for a user request. Covers DELIVERY-RULES.md first, the SOW baseline never invented, the pack's sources by id, and the milestone, plan change, RAID and task shapes the orchestrator records with delivery-record and writes into the task change set. Read it when writing or changing one of those agents.
---

# Working on client delivery

This skill extends `orchestration-workstream`: keep its conduct and return its block. Load it by name if it is not loaded. What follows is only what client delivery adds.

Client delivery keeps one engagement's delivery true: the plan against the SOW, milestones and their acceptance, the RAID log, the engagement's Portal tasks. The facts were gathered before the session (`delivery-pack`); you judge them and return proposals; the orchestrator records them, and nothing else writes.

## Conduct here

- **The rules first.** `DELIVERY-RULES.md` (its path is `rules_file` in `pack.json`) holds the scope baseline, the thresholds, who may be assigned work and what never to open. It wins over this skill and over your brief.
- **The baseline is the owner's.** The `## Scope baseline` table comes from the signed SOW, in the owner's hand. Never fill a missing baseline from a deck, a transcript or your own reading of the work: a milestone the engagement committed to without a SOW goes in the plan with no Baseline due and with the Source where it was committed. A missing SOW is the owner's question, and the orchestrator already asks it.
- **Sources by id.** `pack.json` lists every source with its id (`S004`), role (`sow`, `folder`, `portal`, `repo`), date and path; `sources/S004.md` holds the text of the SOW, each Portal item and the repo log. Cite a source by its id, or by a Portal ref (`portal://note/<uuid>`) or a file path when it is not in the pack. Every claim you return carries one.
- **Already done?** A milestone a person already delivered, a risk already in `RAID.csv`, a task already open: say so and cite it; never propose it again.
- **Read only.** You never call a Portal write tool and never write a file. You return; the orchestrator records.
- **Never open** a file the rules' Never open list matches, even when a path leads to one.
- **Dates** are `yyyy-mm-dd`. A client date is one the client was told (a steering deck, a status memo, a meeting with the client): moving it is the owner's decision.

## The return here

The shared block. `items`, `rows` and `files` may stay empty; the domain fields go in `extra`.

**The planner** (`project-delivery-planner`):

```json
"extra": {
  "plan": {
    "milestones": [{"id": "M2", "milestone": "Margin dashboard", "owner": "build lead",
                    "baseline due": "2026-11-13", "planned due": "2026-11-13", "client date": "yes",
                    "acceptance": "The CFO uses it in the November review", "source": "S001 section 3"}],
    "next_two_weeks": [{"what": "Review the costing model with the controller", "who": "owner",
                        "when": "2026-10-08", "milestone": "M1", "source": "S012"}],
    "late": [{"milestone": "M1", "why": "The controller was out; the review moved", "source": "S014"}]
  },
  "milestones": [{"id": "M1", "state": "in-progress", "evidence": "portal://note/<uuid>",
                  "source": "S014", "note": "Model drafted; review booked for 10-08"}],
  "changes": [{"id": "C1", "milestone": "M1", "to": "2026-10-23", "client_date": true,
               "reason": "The controller is out until 10-20", "source": "S014"}]
}
```

- `plan.milestones` is the whole Milestones table as it should stand, one row per milestone, every baseline Id included. When you propose moving a client date, keep `planned due` at the current date: the move is a `changes` row until the owner approves it.
- `milestones` states: planned, in-progress, at-risk, delivered (needs `evidence`), accepted (needs `evidence` and the owner's confirmation as `source`; otherwise propose delivered).
- `changes`: a planned date that moves, with the new date, the reason and its source.

**The risk analyst** (`project-risk-analyst`):

```json
"extra": {"raid": [{"id": "R2", "type": "risk", "title": "Controller away in October",
                    "owner": "owner", "review_by": "2026-10-19", "state": "open", "severity": "medium",
                    "source": "S014", "mitigation": "Book the review before the 9th", "note": ""}]}
```

- `type`: risk, assumption, issue or dependency. `id` only for a row already in `RAID.csv` (the record tool numbers new ones). `owner` is a role or a name the engagement uses; the engagement's owner is "owner". `state`: open or closed (a closed row's `note` says why).

**The task steward** (`project-task-steward`): the ops in `extra.ops`, each exactly as `task-stack-workstream` says (`task-stack-apply`'s change-set ops, with `evidence`, `reason` and `confidence`). Here, in addition:

- Only tasks in `pack.json` `tasks.items` (the engagement's open tasks), and creates in one of `pack.json` `projects`.
- An owner other than the owner's own contact (`owner_contact` in `pack.json`) or the rules' Assignable ids is never set on a create or an edit: return it as a question ("Assign
  <task> to <person>?"), and the first such question for a person also asks whether they
  agree to receive agent assignments.
- A task listed in `tasks.gaps` (no owner, or the owner's with no due date) gets an edit or a question.
