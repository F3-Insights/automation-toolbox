# 0003. Agent files follow one template

Status: accepted, 2026-10-07.

## Context

The toolbox's 198 agents were written over many months by different sessions, and their bodies show it. The same content sits under `## Return`, `## Returns`, `## The return` and `## What you return`; 59 of the 67 orchestrators run a numbered `## Steps`, `## Each session` or `## The session` script, each with its own steps, and the rest describe their work in prose; some sub-agents are written as `Step 1` to `Step 6` procedures. A reader has to learn each file before trusting it, and the toolbox audit cannot tell an agent that has drifted from one that was never shaped. ICM's "stage contract" (Inputs, Process, Outputs per worker, in `TOOLBOX-DESIGN-SUGGESTIONS.md`) pointed the same way.

## Decision

1. **Every agent file has the same frontmatter and sections.** Frontmatter `name`, `description` (what it does, when to use it, when not, naming the sibling to use instead), `tools` (the narrowest set) and `model`. The body opens with one sentence saying what the agent owns, never "You are an expert", then `## Goal`, `## Inputs`, `## Context`, `## Approach`, `## Boundaries`, `## Done when`, `## Output`, in that order.
2. **An orchestrator's Approach is five fixed stages:** `### A. Gather`, `### B. Plan & clarify`, `### C. Build`, `### D. Test & review`, `### E. Deliver`, each stating its Goal, Who (the skill or sub-agent that does it) and "Move on when" (its exit test). Questions to the owner are batched in B. D names an independent reviewer who never sees the builder's reasoning, and a failed review returns to B with the findings for a capped number of rounds. E never sends or posts without a person. A `## Team` section after Approach lists each sub-agent, what it is given (objective, inputs, boundaries, output) and when it is dispatched.
3. **Every other agent is a sub-agent.** Its Approach is the principles and judgment calls for its slice (usually C, or D for a reviewer) and the skills it uses: not the five stages, not a step script.
4. **Agent or skill.** A piece is an agent when it needs its own context window, to run in parallel, a different model, independence from the maker, or different tool access. Otherwise it is a skill, a written procedure an agent follows. The stage contents are the agent's own; skills hold the step-by-step procedures.
5. **The templates live in the `orchestrator-scaffold` skill** (`references/templates/orchestrator.md`, `references/templates/sub-agent.md`, with the standard in `references/agent-standard.md`), and the scaffold generates from them.
6. **The toolbox audit reports drift and never fixes it.** Its scan flags, per agent file, a missing or out-of-order section, an orchestrator without the five stages or `## Team`, and a sub-agent written as a step script. Rewriting an agent body is a reviewed change, outside the audit's fix rule.

## Consequences

- Every existing agent is flagged on the first scan (198 of 198 on 2026-10-07): the standard is new, and no agent was written to it. They are brought to it department by department, each with an independent review, as other work touches them.
- ICM's stage contract is settled by this record: Inputs, Approach and Output cover its Inputs, Process and Outputs.
- Orchestrators that followed the scaffold's earlier eight-step session shape (orient, facts, plan, dispatch, review, findings, questions, close) keep that content; it moves into the five stages.
