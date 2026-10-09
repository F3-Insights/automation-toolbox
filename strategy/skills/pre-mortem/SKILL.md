---
name: pre-mortem
description: Run a structured pre-mortem on a strategic initiative before capital or time is committed. Dispatches pre-mortem-investigator to surface the plan's assumptions and pre-mortem-researcher for sourced external evidence, then writes the kill-shot risks and the decision brief itself, with two gates where the executive decides. Use for "pre-mortem this plan" or "what could kill this" when a draft strategic plan deserves disciplined pre-commit critique. Not for critiquing a finished document; use the executive-red-team agent.
---

# Pre-Mortem Orchestrator

This orchestrator does the analytical work (the diagnostic framing and the brief) in its own main context and delegates only two jobs to sub-agents. The "Why this architecture" section at the bottom gives the reasoning.

## When to invoke

When the user has a strategic plan in `initiatives/<slug>/plan.md` (with `quant-inputs.yaml` alongside it) and wants disciplined critique before committing capital or time.

## What lives where

All of it lives in the target repository (the company's), never in this skill:

- **Knowledge base**: `context/*.md`. Company overview, voice, taxonomy, constraints, strategic history, lessons-learned. Read by the investigator at Step 2 and by this skill itself at Step 6. On first run, create it from this skill's `context-examples/*.example.md` (a fictional manufacturer, Meridian, kept as a worked example) and blank the content for the real company.
- **Initiative folder**: `initiatives/<slug>/`. One folder per pre-mortem run. Holds the input `plan.md`, `quant-inputs.yaml`, and the generated artifacts (`gate-1-pending.md`, `research.md`, `brief.md`).
- **Template**: `templates/pre-mortem-brief.md` in this skill (copy it into the target repo as `templates/pre-mortem-brief.md` on first run). The output shape filled by this skill at Step 7.
- **Sub-agents**: `pre-mortem-investigator` and `pre-mortem-researcher`. Diagnostic and synthesis work happens in this skill's main context, not in a sub-agent.

## The workflow

Work through these steps in order. The skill is **resumable**: at each gate the user may exit Claude Code and re-invoke later; the workflow detects state from the file system and resumes accordingly.

### Step 1: Confirm the initiative and detect workflow state

Ask the user for the initiative slug if not given. Confirm `initiatives/<slug>/plan.md` and `initiatives/<slug>/quant-inputs.yaml` both exist. If `quant-inputs.yaml` is missing, ask the user to provide it before continuing.

Then detect where in the workflow we are by looking at which files exist in the initiative folder:

- If `gate-1-pending.md` exists, the workflow is paused at Gate 1. Tell the user to review and approve; skip to Step 3.
- If `research.md` exists but `brief.md` does not, the workflow was interrupted after the researcher; skip to Step 6.
- If `brief.md` exists and its `Decision:` field is unfilled, the workflow is paused at Gate 2; skip to Step 8.
- If `brief.md` exists and `Decision:` is filled, the workflow is at lessons capture; skip to Step 9.
- Otherwise it is a fresh run; proceed to Step 2.

### Step 2: Dispatch the investigator sub-agent

Dispatch `pre-mortem-investigator` with the Agent tool. Pass it:

- The plan path: `initiatives/<slug>/plan.md`
- The quant inputs path: `initiatives/<slug>/quant-inputs.yaml`
- The knowledge base directory: `context/`
- The output path: `initiatives/<slug>/gate-1-pending.md`

The investigator reads everything and writes the gate-1 file. **This sub-agent exists because it does heavy context reading**, sparing this skill's main context from carrying the whole knowledge base.

### Step 3: Gate 1 (the executive reviews the assumptions)

When the investigator returns, tell the user:

> The investigator has surfaced the plan's assumptions in `initiatives/<slug>/gate-1-pending.md`. Review it. To approve and continue: delete the file (or rename it to `gate-1-approved.md`). To revise the plan first: edit `plan.md`, then delete the pending file, then re-invoke this skill.

Then stop. The state detection in Step 1 will resume correctly when the user comes back.

### Step 4: Dispatch the researcher sub-agent

When the pending file is gone (the user has approved), dispatch `pre-mortem-researcher` with the Agent tool. Pass it:

- The plan path: `initiatives/<slug>/plan.md`
- The decision category from `context/taxonomy.md`
- The output path: `initiatives/<slug>/research.md`

The researcher does web searches and writes 5 to 8 sourced findings to `research.md`. **This sub-agent exists because it uses specialized tools** (`WebSearch`, `WebFetch`) that this skill does not need to have.

### Step 5: (Reserved for the state machine; no action)

### Step 6: Run the diagnostic framing in this skill's main context

No sub-agent. This skill does the work itself.

Read the following files yourself using the Read tool:

- `initiatives/<slug>/plan.md` (re-read if not already in context)
- `initiatives/<slug>/research.md`
- `context/strategic-history.md`
- `context/lessons-learned.md`
- `context/constraints.md`
- `context/voice.md`

Now construct the post-mortem state **internally**. From the plan, identify: the initiative name, the commitment timing, a plausible failure horizon (12 to 24 months after commit), the capital at stake, and a plausible failure-mode magnitude. Construct a narrative like:

> *"Imagine the [initiative name] was committed in [approximate commit timing]. By [commit + 18 months] the board has called it a failure. The [$X capital] is spent and the company is [specific failure outcome]. I am the analyst writing the post-mortem document explaining what happened."*

Operate from that constructed state for the rest of this step. You are no longer asking "what might go wrong?" You are asking "what DID go wrong?" with the failure already real.

Identify **3 to 5 kill-shot risks**. Each risk:

- **Specific name** (not "execution risk" but "the engineering bench is too thin to support two facilities for 18 months and the original facility loses senior judgment at exactly the moment the new one is ramping")
- **In the plan**: quote the specific line or section
- **Evidence**: citation from `research.md`, `strategic-history.md`, `constraints.md`, or `lessons-learned.md`
- **Precondition**: what has to be true for this risk to become the killing failure

Before moving to Step 7, **self-check against three quality signals**:

- **Specific**: every risk cites an actual line in the plan
- **Contestable**: each risk could be argued with
- **Surprising**: at least one risk should produce a "huh, I hadn't thought about that" reaction

**If any quality signal fails, redo the diagnostic in this context.** Re-construct the state more vividly. Push harder against the plan. Don't produce generic risks.

### Step 7: Assemble the brief in this skill's main context

Read `templates/pre-mortem-brief.md`. Reproduce its section structure exactly. Fill the sections:

- **Executive summary**: one paragraph, 3 to 5 sentences. The decision in front of the executive team in plain language. Name the recommendation if the kill-shot risks point clearly to one. Name the most important risk by short label.
- **Kill-shot risks**: verbatim from your work in Step 6. Don't soften. 3 to 5 risks, each with name, description, "in the plan" citation, evidence citation, precondition.
- **Sourced evidence**: table mapping each risk to its source. URLs and access dates from `research.md`; internal citations from `strategic-history.md`, `constraints.md`, or `lessons-learned.md`.
- **Revised commitment criteria**: derived from the kill-shot risk preconditions. Conditions for COMMIT, RESHAPE, KILL.
- **Mitigation owners**: name or role from `context/company-overview.md`. If no clear owner, write `OWNER NEEDED`.
- **Decision log entry**: placeholders for 90/180/365-day outcomes. **Leave the `Decision:` field empty**; the executive fills it at Gate 2.

Use the voice from `context/voice.md`: plain, technical, numbers first, no marketing language, no hedge words.

Write `initiatives/<slug>/brief.md`.

### Step 8: Gate 2 (the executive decides)

Tell the user:

> The brief is ready at `initiatives/<slug>/brief.md`. Review it. The brief includes revised commitment criteria. When you've decided, set the `Decision:` field at the bottom of the brief (commit / reshape / kill + one-sentence rationale) and re-invoke this skill.

Then stop.

### Step 9: Capture lessons learned

Read the `Decision log entry` section from `initiatives/<slug>/brief.md`. Format a new entry for `context/lessons-learned.md` with today's date in `YYYY-MM-DD` format:

```markdown
## YYYY-MM-DD: <slug>
**Decision:** <commit / reshape / kill>: <rationale from brief>
**Predicted kill-shot risks:**
1. <risk 1 short name>
2. <risk 2 short name>
3. <risk 3 short name>
**Outcome at 90 days:** [pending until <date 90d from now>]
**Outcome at 180 days:** [pending until <date 180d from now>]
**Outcome at 365 days:** [pending until <date 365d from now>]
**Surprises (risks we missed):** [pending]
**Framing that would have caught it:** [pending]

---
```

Append this entry to `context/lessons-learned.md` (do not overwrite; append at the end).

Tell the user the entry has been logged and the workflow is complete. Remind them to come back at 90, 180, and 365 days to fill in the outcome and surprises fields.

## Why this architecture

The design follows three principles for when a sub-agent earns its place, and shows where none of them applies:

| Class of work | Who does it | Principle |
|---|---|---|
| Heavy context reading (6 knowledge files + plan + quant) | Investigator sub-agent | **(1) Heavy context reading**: keeps main context lean |
| External web research | Researcher sub-agent | **(2) Specialized tool use**: the only agent with `WebSearch`/`WebFetch` |
| Pre-mortem diagnostic framing | **This skill, main context** | None of the principles apply: general reasoning |
| Brief synthesis from upstream outputs | **This skill, main context** | None apply: template fill |

**The lesson:** sub-agents are not free. Each one is overhead. Build them only when one of the principles applies. When in doubt, do the work in the orchestrator's main context.

**When this breaks down:** if the orchestrator's main context starts exceeding about 60% of its window during diagnostic and synthesis, or if briefs come back generic, the principles now apply where they didn't before. At that point move the diagnostic and the synthesis into their own sub-agents.

## When NOT to use this skill

- Quick sanity checks on a decision: use a plain chat; the overhead exceeds the value
- Decisions below about $500k or shorter than 6 months
- Decisions where analysis is already done and the executive just needs to review
- Decisions outside the categories in `context/taxonomy.md`
