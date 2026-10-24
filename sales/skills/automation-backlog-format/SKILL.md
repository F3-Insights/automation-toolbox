---
name: automation-backlog-format
description: "Reference loaded by the job that writes an automation backlog and the jobs that read one, not for a user request: the file contract for a ranked automation backlog (the CSV columns and how annual value is computed), the one-page business case's headings, and the issue note a chosen item becomes for a build. Process engineering's automation scoping writes it; the sales proposal reads it as discovery input; a chosen item filed as a Portal note in the issue standard reaches the software issue harvest. Not for drawing the process map the backlog rests on."
user-invocable: false
---

# Automation backlog: the file contract

One backlog per process, written into the engagement's working folder by the job that scopes it and read, unchanged, by any job that prices or builds from it. The producer and every reader hold a copy of this skill, so the shape cannot drift between them. A change to a column is a change here, in the shared source, and every copy follows.

## The files

- `Automation Backlog <process> <yyyy-mm-dd>.csv`: one row per backlog item, in rank order.
- `Automation Backlog <process> <yyyy-mm-dd>.md`: the ranking table and one business case per top item (the top five, or as many as the rules say).
- `Automation Backlog <process> <yyyy-mm-dd> issue notes.md`: one issue note per item, written ready to file once the owner chooses it.

## The CSV

Columns, in this order:

`id,process,map_step,pain,opportunity,approach,hours_per_month,hours_source,rate,rate_source,error_cost,error_source,effort_days,effort_basis,annual_value,rank,confidence,estimate`

- `id`: `AB-<n>`, stable for the life of the backlog; a re-scoped backlog keeps the ids of items that survive.
- `map_step`: the process map's step key (`02/tobe/t3`); `pain`: the claim id the item answers (`T03-P2`).
- `hours_per_month`, `rate`, `error_cost`: figures as the sources state them; each `*_source` names the claim id, row id or document that states it, or `estimate`.
- `annual_value` is `hours_per_month * 12 * rate + error_cost` and nothing else. `rank` orders by `annual_value`, ties broken by lower `effort_days`.
- `confidence`: `high` (every input stated by a source), `medium` (one input estimated), `low` (more).
- `estimate`: `yes` when any input is not stated by a source. An estimate is never presented as a figure; the input is a question for the owner.

## The business case

One page per top item, these headings in this order:

1. **The step and the pain**: the map step, in the client's words, and the pain claim it answers, quoted.
2. **What changes**: the approach in two or three plain sentences; what the people in the lane stop doing.
3. **What it is worth**: hours, rate and error cost with their sources, the annual value and its arithmetic on one line; every estimate marked.
4. **What it takes**: effort in days with its basis; the systems touched; what the client must provide.
5. **Risks and open questions**: each a question for a named role.

No firm fee, rate or price appears in a business case: they are the client's numbers. Pricing the work is the proposal's job, from the owner's own terms.

## The issue note

When the owner chooses an item for a build, it is filed as one Portal note in the issue standard the software issue harvest reads, so the harvest turns it into a well-formed issue. The scoping job writes each note ready to file; the owner files the chosen ones (or a later finish step does). Each note:

- **Title**: what is wanted, under 90 characters, naming the process step, not the client.
- `## What is wanted`: the approach, with the pain quoted from the map's claim.
- `## Expected behaviour`: what the people in the lane see when it works.
- `## Where and how to reproduce`: the map step key and the claim ids; "Not stated in the source" where the map is silent.
- `## Acceptance`: two to five checkable points.
- Nothing private: roles, never names; no client figures beyond what the build needs.

## Readers

- **A proposal** reads the CSV and business cases as discovery notes: the scope is the chosen items, written as qualitative goals; the values are the client's case, never the fee.
- **A build** starts from the filed issue note, never from the CSV.
