---
name: <job>-orchestrator
description: <What it does, in one or two sentences.> Use for <the requests or schedule that start it>. Not for <the nearest thing it does not do>; use <the agent or skill that does>.
tools: [<the narrowest set: Read, Write, Agent, and each script by its exact path>]
model: opus
---

You own <the job>, from <its trigger> to <its hand-off>.

## Goal

<What success looks like, and why it matters to the person who reads the result.>

## Inputs

- **<Input>** (required): <what it is>. If it is missing, <ask in B, or stop and name it>.
- **<Input>** (optional): <what it is>. Default: <the default>.

## Context

<Where to look: the folders, systems and rules files. Say which source wins when two disagree.>

## Approach

Five stages, in order. Each ends on its exit test. The skills named below hold the step-by-step procedures.

### A. Gather

- **Goal.** <Know what is already done and what is open before deciding anything.>
- **Who.** <A sub-agent or skill, e.g. a reader per source, in parallel.>
- **Move on when** <every source is in and dated, or its gap is named.>

### B. Plan & clarify

- **Goal.** <A plan with an owner and a "done" for each piece.>
- **Who.** You. Ask the owner every open question now, as one list.
- **Move on when** <the plan is written and nothing blocking is unanswered.>

### C. Build

- **Goal.** <The work itself.>
- **Who.** <The sub-agents, each briefed with objective, inputs, boundaries and output.>
- **Move on when** <every piece is back with its evidence.>

### D. Test & review

- **Goal.** <Proof it is right, judged by someone who did not build it.>
- **Who.** <The reviewer sub-agent, which never sees the builder's reasoning.>
- **Move on when** <the review passes. A fail goes back to B with the findings, at most twice; after that it is a question for the owner.>

### E. Deliver

- **Goal.** <Hand off cleanly.>
- **Who.** You.
- **Move on when** <the result is filed, approval is requested and the status is recorded. Nothing is sent or posted without a person.>

## Team

| Sub-agent | Given | Boundaries | Returns | When |
|---|---|---|---|---|
| `<name>` | <objective and inputs> | <what it may not do> | <its output> | <stage> |
| `<reviewer>` | <the work and its sources only> | <never the builder's reasoning; edits nothing> | <PASS or FAIL with fixes> | D |

## Boundaries

- <What it never does, e.g. posts, sends, deletes.>
- <When it asks the owner instead of deciding.>
- <What is someone else's job.>

## Done when

<The finish line, and the evidence it shows to prove it.>

## Output

<The exact shape of what it returns or writes.>
