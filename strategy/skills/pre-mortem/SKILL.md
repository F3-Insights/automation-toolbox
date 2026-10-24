---
name: pre-mortem
description: "Run a structured pre-mortem on a strategic plan before capital or time is committed: strategy-worker surfaces the plan's stated, implied and missing assumptions and gathers sourced external evidence, the session writes the kill-shot risks and the decision brief itself, strategy-reviewer red-teams the brief, and the executive decides at two gates. Resumable from the files it has written. Use for \"pre-mortem this plan\" or \"what could kill this\" when a draft strategic plan deserves disciplined critique before commitment. Not for critiquing a finished document; use a red-team review."
---

# Pre-mortem

The session that loads this skill does the analytical work (the diagnostic framing and the brief) in its own context and delegates two jobs to `strategy-worker` (`strategy:strategy-worker` when the strategy plugin is loaded by `--plugin-dir`), each told the section to follow, and one check to `strategy-reviewer`. It runs in the owner's session, never unattended: both gates are the executive's.

## When to invoke

When the user has a strategic plan in `initiatives/<slug>/plan.md` (with `quant-inputs.yaml` alongside it) and wants disciplined critique before committing capital or time. Not for a quick sanity check (a plain chat), decisions below about $500k or shorter than 6 months, decisions where the analysis is done and the executive just needs to review, or decisions outside the categories in `context/taxonomy.md`.

## What lives where

All of it lives in the target repository (the company's), never in this skill:

- **Knowledge base**: `context/*.md`. Company overview, voice, taxonomy, constraints, strategic history, lessons-learned. On first run, create it from this skill's `context-examples/*.example.md` (a fictional manufacturer, Meridian, kept as a worked example) and blank the content for the real company.
- **Initiative folder**: `initiatives/<slug>/`. One folder per pre-mortem. Holds the input `plan.md`, `quant-inputs.yaml`, and the generated `gate-1-pending.md` (renamed `gate-1-approved.md` at Gate 1), `research.md` and `brief.md`.
- **Template**: `templates/pre-mortem-brief.md` in this skill (copy it into the target repo as `templates/pre-mortem-brief.md` on first run), the brief's shape.

## Steps

The workflow is resumable: at each gate the user may leave and invoke the skill again later, and step 1 finds where it stands from the files.

1. [judgment] Confirm the initiative (ask for the slug if not given) and that `initiatives/<slug>/plan.md` and `quant-inputs.yaml` exist. Then detect the state from the initiative folder.
   → plan.md or quant-inputs.yaml missing: ask
   → gate-1-pending.md exists: step 3
   → gate-1-approved.md exists and research.md does not: step 4
   → research.md exists and brief.md does not: step 5
   → brief.md exists with its Decision field empty: step 8
   → brief.md exists with its Decision filled: step 9
2. [hand-off: strategy-worker] Section Surface the assumptions, with the plan path, the quant inputs path, the knowledge base `context/` and the output path `initiatives/<slug>/gate-1-pending.md`. It does the heavy context reading, so this session does not carry the whole knowledge base.
3. [ask] Gate 1. Tell the user: "The plan's assumptions are in `initiatives/<slug>/gate-1-pending.md`. Review them. To approve and continue, rename the file to `gate-1-approved.md`. To revise the plan first, edit `plan.md`, delete the pending file, and invoke the pre-mortem again." Then stop.
   → waiting on the executive: stop
4. [hand-off: strategy-worker] Section Gather external evidence, at sonnet, with the plan path, the decision category from `context/taxonomy.md` and the output path `initiatives/<slug>/research.md`. It is the only part that needs WebSearch and WebFetch.
5. [judgment] The diagnostic framing, in this session, by section Find the kill-shot risks.
   → a quality signal fails: step 5 (max 2)
6. [judgment] Assemble `initiatives/<slug>/brief.md`, by section Write the brief, with its Decision field empty.
7. [hand-off: strategy-reviewer] `review-red-team` on `brief.md`, the executive team as reader and the purpose "should we commit, reshape or kill this", with `plan.md`, `research.md` and the knowledge base as the sources only. Make the concrete fixes it asks for in the brief once.
   → FAIL: step 6 (max 1)
8. [ask] Gate 2. Tell the user: "The brief is ready at `initiatives/<slug>/brief.md`, with revised commitment criteria. When you have decided, set its `Decision:` field (commit / reshape / kill, and one sentence of rationale) and invoke the pre-mortem again." Then stop.
   → waiting on the executive: stop
9. [judgment] Capture the lesson, by section Capture lessons learned, and tell the user the entry is logged and to come back at 90, 180 and 365 days for the outcomes.
   → logged: done

## Surface the assumptions

For a `strategy-worker` (at opus). Brief: the plan path, the quant inputs path, the knowledge base `context/`, the output path. You surface what the plan assumes; you do not analyze risks and do not make recommendations.

The goal: the executive reads the gate-1 file in 5 to 15 minutes, and at least one item makes them say "huh, I had not thought about that explicitly". If everything surfaced was already obvious, the job is not done; if there are 30 items to chase, the load-bearing ones are buried in noise.

1. **Read everything.** The plan in full, the quant inputs, every file in `context/`. The quality of the surfacing depends on knowing the company.
2. **Identify assumptions** and tag each STATED (explicitly in the plan), IMPLIED (present but not made explicit) or MISSING (the plan depends on it but does not name it), across five categories: market (competitors, customers, demand, pricing, geography); operational (execution capability, team capacity, process scaling, technology readiness); capital and timing (money flow, payback timing, capital availability, the rate environment); cultural and organizational (how people will respond, how culture scales, who drives what, change capacity); counterfactual (alternative paths implicitly rejected without being named).
3. **Push back on vagueness.** If the plan says "scale the team", ask which team, by how much, on what timeline. Quote the plan's exact phrase when flagging a stated or implied assumption; never paraphrase. Cross-reference `context/strategic-history.md`: a prior decision that contradicts a stated assumption is flagged.
4. **Write the gate-1 file** at the output path, under one page, in the voice of `context/voice.md` (plain, technical, numbers first, no marketing language). Cut to the load-bearing assumptions.

```markdown
# Gate 1: Plan Assumptions for Review

## Stated assumptions (in the plan)
- <item> (*<which section of the plan it appears in>*)

## Implied assumptions (present but not made explicit)
- <item> (*<which section implies this>*)

## Missing assumptions (the plan depends on these but doesn't name them)
- <item>

## Clarifying questions for you

Three to five questions where the plan is ambiguous or where a clarification
would meaningfully change the pre-mortem.

1. <question>

---

[ ] I have reviewed these assumptions. The plan should proceed to pre-mortem analysis.
```

Return the `orchestration-workstream` block with `workstream: "surface-the-assumptions"`, the gate-1 file in `files`, and in `notes` how many assumptions you flagged in each category and how many clarifying questions you wrote.

## Gather external evidence

For a `strategy-worker` (at sonnet). Brief: the plan path, the decision category, the output path. You provide the sourced ground; you offer no opinion on the plan and do not synthesize across findings.

The goal: a reader of `research.md` can verify every claim by clicking through, and at least one finding contradicts an assumption in the plan specifically (not "expansion is hard" but "the plan's operator wage is $3.20/hr below the latest data for the target metro"). If every finding supports the plan, the searches were not hard enough.

1. **Read the plan** and confirm the category. Note the geography, time horizon, capital scale and any named external entities (competitors, customers, suppliers, regulators).
2. **Write four to six queries specific to this plan**, for example comparable companies that opened a second facility in the target state in the last five years, regulatory differences between the origin and target state for the industry, labor market data for the target metro. Never generic ("is expansion risky").
3. **Search and fetch.** Run each query through `WebSearch`; fetch the substantive sources with `WebFetch`. Prefer primary sources (regulatory filings, company releases, industry reports), recent data (the last three years, ideally twelve months) and comparable cases. Skip generic business blogs, thought-leadership posts and vendor-sponsored content.
4. **Write `research.md`**: five to eight findings, fewer when the searches turn up little. Every claim has a URL; drop what you cannot verify. Date-stamp every fetch. Flag a contradiction with the plan neutrally ("the plan's success metric assumes X; recent comparable Y shows Z"). Plain, technical, numbers first, per `context/voice.md`.

```markdown
# External Research: <Initiative slug>

*Each finding has a sourced URL.*

## Finding 1: <Plain-language summary in one sentence>
**Source:** <URL>
**Accessed:** <YYYY-MM-DD>
**Relevance to plan:** <one sentence linking to a specific section of the plan>
**Detail:** <2 to 4 sentences of substance from the source. Direct quotes where useful.>
```

Return the `orchestration-workstream` block with `workstream: "gather-external-evidence"`, `research.md` in `files`, and in `notes` how many findings you produced and from which sources.

## Find the kill-shot risks

Read the following files yourself using the Read tool:

- `initiatives/<slug>/plan.md` (re-read if not already in context)
- `initiatives/<slug>/research.md`
- `context/strategic-history.md`
- `context/lessons-learned.md`
- `context/constraints.md`
- `context/voice.md`

Now construct the post-mortem state **internally**. From the plan, identify: the initiative name, the commitment timing, a plausible failure horizon (12 to 24 months after commit), the capital at stake, and a plausible failure-mode magnitude. Construct a narrative like:

> *"Imagine the [initiative name] was committed in [approximate commit timing]. By [commit + 18 months] the board has called it a failure. The [$X capital] is spent and the company is [specific failure outcome]. I am the analyst writing the post-mortem document explaining what happened."*

Operate from that constructed state for the rest of this section. You are no longer asking "what might go wrong?" You are asking "what DID go wrong?" with the failure already real.

Identify **3 to 5 kill-shot risks**. Each risk:

- **Specific name** (not "execution risk" but "the engineering bench is too thin to support two facilities for 18 months and the original facility loses senior judgment at exactly the moment the new one is ramping")
- **In the plan**: quote the specific line or section
- **Evidence**: citation from `research.md`, `strategic-history.md`, `constraints.md`, or `lessons-learned.md`
- **Precondition**: what has to be true for this risk to become the killing failure

Before writing the brief, **self-check against three quality signals**:

- **Specific**: every risk cites an actual line in the plan
- **Contestable**: each risk could be argued with
- **Surprising**: at least one risk should produce a "huh, I hadn't thought about that" reaction

**If any quality signal fails, redo the diagnostic in this context.** Re-construct the state more vividly. Push harder against the plan. Don't produce generic risks.

## Write the brief

Read `templates/pre-mortem-brief.md`. Reproduce its section structure exactly. Fill the sections:

- **Executive summary**: one paragraph, 3 to 5 sentences. The decision in front of the executive team in plain language. Name the recommendation if the kill-shot risks point clearly to one. Name the most important risk by short label.
- **Kill-shot risks**: verbatim from section Find the kill-shot risks. Don't soften. 3 to 5 risks, each with name, description, "in the plan" citation, evidence citation, precondition.
- **Sourced evidence**: table mapping each risk to its source. URLs and access dates from `research.md`; internal citations from `strategic-history.md`, `constraints.md`, or `lessons-learned.md`.
- **Revised commitment criteria**: derived from the kill-shot risk preconditions. Conditions for COMMIT, RESHAPE, KILL.
- **Mitigation owners**: name or role from `context/company-overview.md`. If no clear owner, write `OWNER NEEDED`.
- **Decision log entry**: placeholders for 90/180/365-day outcomes. **Leave the `Decision:` field empty**; the executive fills it at Gate 2.

Use the voice from `context/voice.md`: plain, technical, numbers first, no marketing language, no hedge words.

Write `initiatives/<slug>/brief.md`.

## Capture lessons learned

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

## Why this shape

Sub-agents are not free; each is overhead. The worker earns its place twice: heavy context reading (the six knowledge files, the plan and the quant inputs) kept out of this session, and specialized tools (WebSearch and WebFetch) only the research needs. The reviewer earns its place as an independent cold read before the executive sees the brief. The diagnostic framing and the brief are general reasoning and a template fill, so this session does them. If this session's context passes about 60% of its window during the diagnostic, or the briefs come back generic, move the diagnostic and the synthesis into worker sections too.
