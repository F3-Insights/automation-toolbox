# 0003. Agent files follow one template

Status: accepted, 2026-10-07; amended 2026-10-11 for plugin departments (below).

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

## Amendment, 2026-10-11: one template per role in a plugin department

**What changed.** A department that is a plugin (its folder holds `.claude-plugin/plugin.json`, [0004](0004-a-department-is-a-plugin.md)) still writes every agent to one template, but the templates are the plugin pattern's three, drawn from the software department's six agents and kept in the toolbox's `templates/`:

1. **A main agent per job** (`templates/main-agent.md`): an opening sentence, `## Goal`, `## Inputs`, `## How to work`, `## Done`, `## Never`, with `skills:` and `tools:` (including `Skill`) in the frontmatter, about 40 lines. It is named for what it does, not `-orchestrator`, and is recognised by what it does: it holds the `Agent` tool or dispatches its department's worker or reviewer. Its procedure is the `## Steps` section of its job's skill, in the format Sentinel draws (`N. [script|judgment|hand-off: agent|ask] text`, branch lines `→ condition: step N|stop|ask|done (max N)`), not the five stages; the former specialists' instructions are `##` sections of that skill.
2. **One `<department>-reviewer`** (`templates/reviewer.md`): read-only (no Write, Edit or bare Bash), judges from the sources alone against the checklist section its brief names, and returns PASS or FAIL with numbered fixes.
3. **At most one `<department>-worker`** (`templates/worker.md`): does one slice following the section its brief names and returns that section's block; it cannot dispatch.

A step hands off only to the department's own worker or reviewer, and no `skills:` entry or `Agent(...)` grant names another department's piece. Decision 2's five stages and `## Team`, and decision 3's sub-agent template, apply only to departments that are not yet plugins; decision 5's templates in the `orchestrator-scaffold` skill are that older pattern's.

**Why.** The software department's conversion showed the five stages and the specialists cost more context than they returned: most specialist steps were done better by the main agent following a skill section, and the only reasons left to dispatch are independence (the reviewer) and parallel or isolated work (the worker). Keeping "one template" while changing what it is lets the audit go on telling an agent that has drifted from one that was never shaped.

**Consequences.** Both patterns stand side by side until the last department converts. The toolbox audit judges each department by the one it is on (decision 6 still holds: it reports drift and never fixes it), so a converted department is checked against the plugin pattern instead of being flagged against the old one, and an unconverted one is judged as before. How to convert a department is `docs/converting-a-department.md`.
