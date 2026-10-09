---
name: compliance-calendar-workstream
description: Reference loaded by compliance-calendar-tracker and compliance-calendar-orchestrator, not for a user request; adds to orchestration-workstream. Covers the calendar file and its rules file, the item shape, lead-time arithmetic, what counts as evidence a filing or renewal was made, the states an item's current occurrence can take, the review and proposal shapes, and the DONE checklist. For "what filings are due", start compliance-calendar-orchestrator.
---

# Compliance calendar workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Load that skill if it is not loaded. What follows is only what the compliance calendar adds.

The work: no filing, renewal, registration, report or legal deadline across the owner's entities is missed. Each week every item's current occurrence is placed (filed, due, upcoming, overdue), each one due inside its lead time gets an owner task or evidence it was done, and the owner sees one short list. Filings, payments and signatures are people's acts; agents only find evidence, propose tasks and propose calendar changes.

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

## What the tracker returns

The `orchestration-workstream` block, with:
- `items`: one row per calendar item: `test` `occurrence`, `item` the id, `state`, `evidence`, `note` (the due date and lead time used).
- `extra.ops`: task-stack-apply ops (`task-stack-workstream` shape) for each `due` or `overdue` item with no open task: a `create` titled verb-first ("File the Entity A annual report with the Secretary of State"), due on the due date less five working days, owner from the rules; a `complete` for an open task whose item is `filed`, with the evidence.
- `proposals`: changes to `COMPLIANCE-CALENDAR.yaml`, each with its source: the next `due` and `last_filed` for a filed item, a new item found in the record (a notice from an authority, a renewal letter), a correction.
- `questions`: overdue items first, then unknown dates, each `of: owner`.

## DONE checklist

The orchestrator checks each against evidence it can cite before it reports, and has `compliance-evidence-checker` confirm the starred ones.

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
- `task-stack-apply` after the session, to make `RUN/changes.json`.
