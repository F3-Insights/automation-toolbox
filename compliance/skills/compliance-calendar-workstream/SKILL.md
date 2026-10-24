---
name: compliance-calendar-workstream
description: "The compliance calendar's procedure, loaded by compliance-calendar-keeper, compliance-worker and compliance-reviewer, not for a user request; adds to orchestration-workstream. The Steps, the calendar and rules files, the item shape, lead-time arithmetic, what counts as evidence a filing or renewal was made, the occurrence states, the sections Place a batch and Check the evidence, the review and proposal shapes, and the DONE checklist. For \"what filings are due\", start compliance-calendar-keeper."
---

# Compliance calendar workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Load it, and `task-stack-workstream` for the change set, with the Skill tool if they are not loaded. What follows is only what the compliance calendar adds.

The work: no filing, renewal, registration, report or legal deadline across the owner's entities is missed. Each week every item's current occurrence is placed (filed, due, upcoming, overdue), each one due inside its lead time gets an owner task or evidence it was done, and the owner sees one short list. Filings, payments and signatures are people's acts; agents only find evidence, propose tasks and propose calendar changes.

## Steps

For `compliance-calendar-keeper`. `RUN` is the Run folder; write only there.

1. [judgment] Orient. `whoami`; read `COMPLIANCE-RULES.md`, the task-stack rules file (`rules_file`) and `COMPLIANCE-CALENDAR.yaml`. Keep only the entity's items when the Run names one. A missing or empty calendar is the owner's question: report it and stop.
   → the calendar is missing or empty: stop
2. [judgment] Split the items into batches of about fifteen, by entity. Write `RUN/plan.json`.
3. [hand-off: compliance-worker] Place each batch (section Place a batch), one worker per batch in parallel, with the batch, the horizon, today's date, the owner's contact id and both rules files' paths. Save each return as `RUN/returns/<batch>.json`.
4. [hand-off: compliance-reviewer] Check every `filed` and `not-applicable` state and every `complete` op (section Check the evidence), with the claims and their cited evidence only, never the workers' reasoning. Save its return as `RUN/returns/evidence-check.json`. A FAIL turns the item back to `due` or `overdue` and drops its op; record why in `review.json`.
5. [judgment] Write `RUN/review.json` (one row per item with its checked state), `RUN/changes.json` in the `task-stack-workstream` shape with `orchestrator` `compliance-calendar-keeper`, and `RUN/calendar-proposals.md` (each proposed calendar change with its source).
6. [judgment] Walk the DONE checklist into `RUN/done.md`, each line met or not with its evidence, and report: counts by state, the overdue and due items with their tasks, the reviewer's FAILs, the proposed calendar changes, and the questions as one numbered list the owner can answer "1) ok 2) no", overdue items first.
   → reported: done

After the session the Automation runs `task-stack-apply --run RUN --dry-run-if=<dry_run>`, the one writer of the owner's tasks. A missing calendar is the one question that stops the Run; every other question goes in the report.

## The folder

The caller names one compliance folder. It holds:

- `COMPLIANCE-RULES.md`: the owner's rules. Which entities are in scope, who owns each kind of item (a role, mapped to a person in the rules), the default lead time, where evidence of a filing is kept, what an agent may write. It wins over this skill.
- `COMPLIANCE-CALENDAR.yaml`: the items. The owner's file; agents never edit it.
- `evidence/` (optional): copies or receipts a person saved.

## The item shape

```yaml
- id: annual-report-entity-a        # stable, kebab
  item: Annual report and fee         # what must be done
  entity: Entity A                    # the label the rules use
  authority: Secretary of State       # who it is filed with
  recurrence: annual                  # annual | quarterly | monthly | once | every-N-years
  due: "2027-05-31"                   # the next due date, or a rule: "last day of anniversary month"
  lead_days: 45                       # optional; else the rules' default
  owner: controller                   # a role from the rules
  evidence_where: "mail from the authority; Legal Docs folder"   # where proof of filing lands
  last_filed: {date: "2026-05-20", evidence: "<path or portal ref>"}
  notes: ""
```

## Placing an occurrence

For each item compute the current occurrence's due date (the `due` field, or the rule applied to today), then its state:

| State | When |
|---|---|
| `filed` | Evidence of this occurrence exists: a confirmation, a receipt, a filed copy, the authority's acknowledgement, dated inside the occurrence window (after the prior due date) |
| `due` | Inside its lead time, not yet due, no evidence |
| `overdue` | Past due, no evidence |
| `upcoming` | Outside its lead time |
| `unknown-date` | The due date cannot be computed from the file (a rule that needs a fact the file lacks) |
| `not-applicable` | The rules or the record say it no longer applies (an entity dissolved, a policy cancelled); needs a source |

Evidence is a document that did the act, never one that talks about it. A reminder email, a calendar hold, a task marked done without an attachment, or a draft is not evidence. Cite it by path or by `portal://<kind>/<id>`.

## Place a batch

For `compliance-worker`, given one batch of items, the horizon, today's date, the owner's contact id and the two rules files' paths. Read the rules files first. You read only; you write nothing. For each item:

1. Compute the current occurrence's due date and lead time; say which rule you used.
2. Look for evidence where the item's `evidence_where` and the rules point: the folder, then the Portal (`search` for the authority and the entity; `email_bodies` for a confirmation).
3. Place it (section Placing an occurrence), and look for an open task that already covers it (`list_entities` task, `search`).
4. Propose a `create` or `complete` op only as below; never one for a task that already exists.
5. Propose a calendar change where the record shows the item moved, ended or is new.

Return the `orchestration-workstream` block with `workstream: "compliance-calendar"`; every item in the batch appears in `items`:
- `items`: one row per calendar item: `test` `occurrence`, `item` the id, `state`, `evidence`, `note` (the due date and lead time used).
- `extra.ops`: task-stack-apply ops (`task-stack-workstream` shape) for each `due` or `overdue` item with no open task: a `create` titled verb-first ("File the Entity A annual report with the Secretary of State"), due on the due date less five working days, owner from the rules; a `complete` for an open task whose item is `filed`, with the evidence.
- `proposals`: changes to `COMPLIANCE-CALENDAR.yaml`, each with its source: the next `due` and `last_filed` for a filed item, a new item found in the record (a notice from an authority, a renewal letter), a correction.
- `questions`: overdue items first, then unknown dates, each `of: owner`.

## Check the evidence

For `compliance-reviewer`, with `evidence-check` as the checklist (load it), given the claims (each `filed` or `not-applicable` state and each `complete` op, with its id and the evidence it cites) and the rules file's path, never the workers' reasoning. The bar is section Placing an occurrence above:

- A `filed` claim passes only on a document that did the act, dated inside the occurrence window (after the prior due date), for the item's entity and authority.
- A `not-applicable` claim passes only on a source that says the item no longer applies (a dissolution, a cancellation), not on silence.
- A `complete` op passes only when its evidence also places the item `filed`.

Return the `evidence-check` return block.

## DONE checklist

The main agent checks each against evidence it can cite before it reports; the reviewer confirms the starred ones (section Check the evidence).

1. Every item in the calendar has a state for its current occurrence in `RUN/review.json`.
2. Every item due within the rules' horizon (default 30 days) or its own lead time has evidence of filing, an open owner task (cited), or a `create` op in `RUN/changes.json`.
3. * Every `filed` state cites evidence dated inside the occurrence window.
4. * Every `complete` op and every `not-applicable` state rests on a source.
5. Every overdue item is the first question in the owner's list.
6. Every proposed calendar change names its source.
7. Nothing was filed, paid, signed or sent, and the calendar file is unchanged.

## Later tools

- `compliance-check --precheck`: the due-date and lead-time arithmetic, printing WORK when anything is inside its lead time; also the computed occurrences for the session.
- `compliance-record`: writes a checked `filed` occurrence to an evidence log beside the calendar, never to the calendar itself.
