# The agent file standard

Every agent in the toolbox is written to one template, so a reader finds the same thing in the same place in every file and the toolbox audit can tell when one drifts. The decision is ADR 0003 in the toolbox's `docs/adr/`. The two templates are `templates/orchestrator.md` and `templates/sub-agent.md` beside this file; `orchestrator_scaffold.py generate` fills them from a spec, and a hand-written agent starts from a copy of one, replacing each `{{slot}}`.

## Agent or skill

Make it an agent when the work needs at least one of these:

- its own focus and context window, because there is a lot to read;
- to run in parallel with other work;
- a different model from its caller;
- independence from the maker (a reviewer or checker);
- different tool access from its caller.

Otherwise it is a skill: a written procedure an agent follows. Agents hold a role and its judgment; skills hold the step-by-step procedures.

## Every agent file

Frontmatter:

- `name`, equal to the file name.
- `description`, at most 700 characters: what it does, when to use it, and when not to, naming the sibling to use instead ("Not for X; use Y").
- `tools`, the narrowest set the work needs; a script is granted by its exact path, never a bare interpreter.
- `model`.
- `color` and `skills` as the agent needs them.

Body: one opening sentence saying what the agent owns ("You own ..."; never "You are an expert ..."), then these sections in this order:

| Section | Holds |
|---|---|
| `## Goal` | What success looks like and why it matters |
| `## Inputs` | What it is handed, and what to do when something is missing |
| `## Context` | Where to look, and which source wins when two disagree |
| `## Approach` | How it works (below, by kind of agent) |
| `## Boundaries` | What it never does, when it asks or escalates, and what is not its job |
| `## Done when` | The finish line and the evidence it shows |
| `## Output` | The exact return shape |

An orchestrator adds `## Team` after `## Approach`. Other `##` sections may follow the standard ones when the agent needs them (a detailed return contract, for example), but never in place of one.

## Orchestrators

An orchestrator's name ends in `-orchestrator`. Its `## Approach` is five fixed stages, under these exact subheadings and in this order:

- `### A. Gather`
- `### B. Plan & clarify`
- `### C. Build`
- `### D. Test & review`
- `### E. Deliver`

Each stage states its **Goal**, **Who** (the skill or sub-agent that does it) and **Move on when** (the exit test). Three rules hold in every orchestrator:

- Questions to the owner are batched in B, as one list, never asked one at a time from other stages.
- D names an independent reviewer who never sees the builder's reasoning. A failed review returns to B with the findings, for a capped number of rounds; past the cap it is a question for the owner.
- E never sends or posts without a person.

The stage contents are the agent's own. A skill may hold the detailed procedure a stage runs, but the orchestrator file always says what the stage is for, who does it and when it is finished.

`## Team` lists each sub-agent with what it is given (objective, inputs, boundaries, output) and when it is dispatched. Keep it a table whose first column is the backticked agent name: the scaffold's lint and the toolbox audit find the team from it.

## Sub-agents

Every other agent is a sub-agent. Its `## Approach` holds the principles and judgment calls for its slice of the work (usually stage C, or D for a reviewer) and the skills it uses. It is not the five stages and not a step script: a run of `## Step 1`, `### 1.` headings, or a `## Steps` section as the body's structure, means the procedure belongs in a skill the sub-agent loads.

## Drift

The toolbox audit's scan reports, per agent file, a missing or out-of-order section, an orchestrator without the five stages or `## Team`, and a sub-agent written as a step script. It reports only: bringing an agent body to the template is a rewrite for a person or a reviewed change, never a lint fix.
