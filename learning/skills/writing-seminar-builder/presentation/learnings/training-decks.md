# Training & Teaching Decks: Learnings

*How to build a deck whose job is to **make a smart non-expert understand something**, not to sell a conclusion. Read [_universal.md](_universal.md) first; this doc covers what's specific to teaching.*

Audience: business leaders who are intelligent but not domain experts.

---

## The job is different from consulting

Consulting drives to a recommendation. Teaching **builds understanding**, then lets the audience reach the conclusion themselves. That requires slide types consulting decks rarely use (analogy, mental model, misconception, worked example, knowledge-check) and a different pacing.

The house arc that encodes this: **Setup → Meat → Close** (see DESIGN-PRINCIPLES §1). Setup orients; the meat teaches one act-on-able idea per slide with an assertion headline + evidence + a concrete leave-behind; the close lands the real takeaway.

---

## Principles

1. **Scaffold; don't dump.** Build comprehension step by step so each slide earns the next. Sequence simple → complex; pre-teach a term before you use it in a system (Mayer "pre-training"). This manages *intrinsic* cognitive load, which is high for non-experts.

2. **Progressive disclosure.** Reveal one step/idea at a time (build animations), keeping prior steps visible but dimmed. Never a wall of text; never more than ~3 sequential parts on screen before a build. Keep the assembled end-state legible.

3. **Analogy and visual metaphor.** Introduce an abstract idea by mapping it onto something the audience already owns ("A is like B"). Construct it deliberately: pick a truly familiar source, map the correspondences, and **name where the analogy breaks**: an incomplete analogy can become the learner's only (wrong) mental model. Definition/concept slides may carry a little more text, but always anchor with a visual.

4. **Make mental models visible.** Show *how something works* structurally: inputs → process → outputs, or cause → effect chains. A 3–4 box labeled diagram beats prose for a non-expert (dual coding: one image + one phrase).

5. **Worked examples: real over abstract.** Show a complete solved instance with the reasoning, not just the answer (the "worked-example effect"); present the correct example first. When you can, make it a **real, named artifact wired to real inputs** (the `wiring-flow` element), not a generic recipe. A built system reads as practitioner experience; an abstract recipe reads as explanation. Pair any "here are N examples" list with a reusable **judgment tool** (a 2×2 or decision framework) so the audience can spot *their own* candidates, not just read yours.

6. **Misconception clearing.** Explicitly contrast what people *assume* vs. what's *actually* true. Refutation beats assertion. Powerful for AI-literacy topics. **Frame additively** (per the house voice): "easy to assume X, and also Y," never "you're wrong." De-emphasize the myth, emphasize the reality.

7. **Translate technical → business.** Replace jargon with the business outcome. Not "transformer architecture" but "how AI reads your 100 emails and surfaces the 3 that need you." Use concrete, named scenarios from the audience's world (the concreteness effect). Feynman test: explain it to a smart non-specialist with one everyday example. When a term of art is unavoidable (MCP, BAA, token), its first use gets a one-phrase plain-English translation in the same breath; never assume the room knows it, never make them ask.

8. **Retrieval and participation.** Adults learn by doing, not absorbing (andragogy). Use knowledge-check / question slides to force recall and surface confusion; give decision frameworks they can self-apply. Put the answer/ feedback next to the question (spatial contiguity), not on a later slide.

9. **Relevance-first, problem-centered.** Adults invest effort only in what's relevant. Open each section with a "why this matters to your business" hook before any concept; tie every technical point back to a P&L / team / customer stake. Design backward from "what should they *do* differently?" (action mapping), not "what's the full taxonomy?"

10. **Respect their experience; positive and additive voice.** These are accomplished executives. Anchor analogies in business experience they already have; invite them to map new ideas onto their context. Never imply they're doing something wrong (see the training folder's `CONTEXT.md`, when it has one, and the `brand-guide` skill).

11. **Earn the non-obvious (or it reads as AI-generated).** A deck that is all definition reads like a generic article: the most common failure, and exactly what a skeptical executive will name out loud. A deck can pass every mechanical check (action titles, no catchphrases, clean QA) and still feel generated because it has no point of view and nothing to *do*. Before it ships, the deck must contain at least: **(1)** one *real, concrete artifact or wired system*, not an abstract recipe; **(2)** one number or lived example from actual practice; **(3)** one non-obvious, expert insight the audience couldn't get from a blog post (the "here's what everyone gets wrong" beat); and **(4)** one personal Monday-morning action the executive can do themselves this week. Breadth of definition is the first thing to cut to make room; this is #9 (action mapping, not taxonomy) made checkable.

12. **The slide carries the value; notes are cues.** The presenter can carry a room; the deck's job is to be useful even on a silent read (DESIGN-PRINCIPLES §1A silent-read bar). The specifics live ON the slide: the number, the named example, the decision rule, the artifact. Notes are delivery cues and depth, never a rescue layer for a thin slide, and never a restatement of it. The story only the presenter can tell (a system they built, a messy situation they untangled, a real before/after) still anchors the deck, but it lands as an on-slide artifact or worked example, not as a paragraph in the notes.

13. **Friction before framework.** Introduce every framework, matrix, or lifecycle as the answer to a named, lived problem ("most companies stall at the Do phase, and here's why"), never as a free-standing taxonomy. The decks that land name the friction first (a pilot stuck on a slow yes, a gap between how many firms adopt and how few measure a return); the framework arrives as relief. Corollaries: pair every named-company win with where the same pattern breaks or stalls; frame governance as how you move faster safely (the unlock), never as a compliance checklist.

14. **Design for the room and for Monday.** Plan at least two audience- interaction beats per deck (a poll, a show of hands, a "where does your company sit?" pause), marked in the notes. A live session should interact every 10–15 minutes, and a deck with no planned beats turns the presenter into a lecturer. Any "N options" grid stars the recommended first move and says why ("start with the weekly review: repeatable, low-stakes, immediate"). The Monday-morning action is sized to Monday: doable before lunch, no budget, no team: "map one workflow with two people tomorrow," not "pilot three this quarter."

---

## Give / hold (what to teach, what to reserve)

A seminar arms the executive; it doesn't hand them a working kit.

- **Give:** principles, frameworks, mental models, decision tools, workflow shapes, named patterns, attributed stats, the "what to plan for" guidance, the Monday-morning move.
- **Hold:** templates, calculators, prompts, configs, code, per-industry baselines, specific tool stacks, implementation playbooks. Those live in the paid engagement (Intensive, Implementation).
- **Tease the technical, don't dive in.** Architecture diagrams, named patterns, benefits, failure modes: yes. Code, prompts, configs: no. A smart executive should leave able to brief their team on *what* to build and roughly *how* it flows, but still need help turning it into a working system.

---

## Teaching slide types (Explain / Demonstrate / Reframe & check)

concept-with-analogy · plain definition · named-framework figure · mental model (inputs→process→outputs) · step-by-step build · worked example · before/after · misconception (myth vs reality) · business-application translation · spectrum/ continuum · decision framework · knowledge-check · recap · relevance hook.

---

## Sources

Mayer, *Multimedia Learning* (12 principles) · Sweller, Cognitive Load Theory · Knowles, andragogy · Cathy Moore, action mapping · Paivio, dual coding · the worked-example-effect literature · Duarte / Reynolds.
