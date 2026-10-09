# Workflow Depth: The Operationalization Lens

Every seminar's teaching content has to cross from *"here's a technique"* into *"here's how the technique becomes a working operation in a real company."* Surface-level seminars feel like LinkedIn carousels. Operationalized seminars feel like working sessions an executive forwards to their head of strategy.

This file is the lens that pushes Step 3 toward the second register. Read it before drafting the middle slides.

---

## Two requirements, every seminar

### 1. The Workflow Backbone Diagram (required centerpiece)

Every seminar must include a centerpiece slide that draws the technique as a **6–10 step orchestration diagram**. This is the most-remembered slide in the deck: the one an executive sketches on a whiteboard, the one a team lead uses to brief implementers, the one a returning attendee references weeks later.

The diagram is **not abstract**. It shows specific stages, with specific artifacts flowing between them, with specific human and AI roles, and with feedback loops where they exist. The loop has to be visible; this is not a one-shot pipeline.

**The standard orchestration moves** (use the ones that apply to the technique; rarely all):

1. **Context establishment**: assembling company context, structured documents, history, constraints into something the AI can reason from. A local file structure, a Claude Project, a Skill, or a populated GPT.
2. **Quantitative assumption injection**: putting the numbers in (targets, thresholds, budgets, comparison baselines, success criteria).
3. **Agentic interrogation**: an investigator agent quizzes the user (or team) to surface unstated assumptions and clarify scope *before any output is generated*. Pushes back on vagueness.
4. **HITL gate, expanded-understanding confirmation**: a human reviews and signs off on the expanded plan before the workflow proceeds.
5. **Orchestrator step**: the main technique runs. In this series, often a framing technique (pre-mortem, devil's advocate, red-team) or a structured analysis pattern.
6. **Sub-agent specialization**: research, diagnostic, simulation, or verification sub-agents run in their own loops with their own context and stopping criteria, feeding back to the orchestrator.
7. **Standard output template injection**: the synthesis is forced into the company's standard deliverable format (board memo, investment case, strategic plan template) so the artifact is usable on arrival.
8. **Synthesis**: conclusions and recommendations drawn from the sub-agent outputs and orchestrator results.
9. **Deliverable / executive presentation**: the artifact handed to a human decision-maker (one-pager, deck, briefing, decision log).
10. **Lessons-learned feedback loop**: outcomes and learnings captured back into a shared agentic library so the loop refines over time.

**Minimum:** six steps, including at least one HITL gate and at least one feedback loop. Anything less is a pipeline, not an operation.

### 2. Coverage of the five recurring questions

The seminar as a whole must address all five. Some slides may cover more than one; one slide may zoom in on a single question.

| # | Question | What good coverage looks like |
|---|---|---|
| 1 | **Company data & context**: how does the audience's real business context enter the workflow? | Pasting into chat is the floor. Projects, Skills, structured context files, and document repositories are the mature pattern. Name where context lives, how it's maintained, and who owns it. |
| 2 | **Human-in-the-loop decision points**: where do humans gate the workflow? | Name the gates explicitly. State what's actually being decided at each one. Workflows without HITL gates are experiments, not executive operations. |
| 3 | **Specialized sub-agent loops**: where do sub-tasks peel off into their own agents? | Sub-agents are how seminars move from single-shot prompting into actual systems. Each sub-agent has its own context, tools, and stopping criteria. Show what gets specialized and why. |
| 4 | **Deliverables, artifacts, tool calls**: what does the workflow produce, in what format, using what tools? | A workflow that doesn't end in a recognizable artifact doesn't land for executives. Name the deliverable. Show the template shape. |
| 5 | **Recursive improvement**: how does the loop get better over time? | Lessons-learned libraries, prompt iteration, feedback capture, versioned templates. Without this, the seminar teaches a one-off. With it, it teaches a practice. |

---

## Per-slide depth check

Before locking each teaching slide in Step 3, ask:

- **Substance test.** Does this slide contain real analysis, or just a headline plus restated bullets? If the bullets restate the headline, push the slide deeper or merge it with its neighbor.
- **Operational test.** Does the slide either show a stage of the workflow backbone, or address at least one of the five recurring questions, or teach a principle that informs both? If none of those, what is this slide doing in an executive seminar?
- **Inference test.** Would a senior executive read the slide title and the diagram and *already know what the slide is going to say*? If yes, the slide is too thin. Add the specific analysis, the named tradeoff, the contrarian observation, the operational consequence: whatever forces the audience to actually read it.

If a slide fails any test, the fix is almost always **deepen** (add the operationalization detail, the specific company-context consideration, the HITL implication, the sub-agent opportunity), not **add another slide**. Density of insight per slide is what makes a seminar feel substantive.

---

## Slide-count guidance with depth treatment

Default seminar lengths are 25–30 minutes, not 45. Depth comes from substance per slide, not slide count. See `narrative-arc.md` for the pacing math.

- **25 minutes** → 10–12 slides
- **30 minutes** → 12–13 slides
- **45 minutes** → 14–16 slides (only when the topic genuinely needs the air)

Standard composition for a 30-min deck with depth treatment (12 slides):

| Count | Role |
|---|---|
| 1 | Outcome promise (Slide 1) |
| 1 | Assumptions (Slide 2) |
| 1 | Problem + cause, collapsed (Slide 3) |
| 1 | The reframe / answer (Slide 4); the answer lands here, within ~25% of the talk |
| 1 | Demonstration of the answer (Slide 5) |
| 1 | **Workflow backbone diagram (centerpiece, Slide 6)** |
| 3 | Five recurring questions, combined across slides (Slides 7–9) |
| 1 | Three patterns + decision matrix collapsed (Slide 10) |
| 1 | Punchy send-off (Slide 11); see `narrative-arc.md` |
| 1 | Offer + CTA combined (Slide 12) |

The five recurring questions don't each need their own slide. A typical pairing:

- Context (Q1) + HITL (Q2) → one slide
- Sub-agents (Q3) + Artifacts (Q4) → one slide
- Recursive improvement (Q5) → one slide (this is the meta point, gets to stand alone)

If you land at 17 slides for a 30-min talk, you're padding. Collapse adjacent slides serving the same arc beat. If you can't fit the substance into 12 slides, the seminar may be two seminars.

---

## How this preserves the give-vs-hold line

The workflow backbone diagram and the five-question coverage **deepen the seminar without crossing into paid territory.** See `depth-boundaries.md` for the line.

- ✓ **GIVE:** the shape of the operationalization: what stages exist, what each stage does, where the HITL gates are, what kinds of sub-agents specialize, what artifacts flow.
- ✗ **HOLD:** the actual file structures, agent configurations, prompt strings, template documents, integration plumbing, and lessons-learned schema. The paid workshop builds those calibrated to the client's business.

A senior executive should leave able to brief their team on *what to build* and *roughly how it flows*. They should still need help to actually construct the file structures, configure the agents, write the templates, and wire the loops.
