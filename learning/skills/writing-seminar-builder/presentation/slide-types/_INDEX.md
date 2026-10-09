# Slide-Type Library: Index

The catalog of reusable slide *types*, organized by the **job the slide does** (its purpose). This is the selection map: given a story beat, match the beat's job to a purpose category, then pick the type whose *trigger* fits.

Variety comes from matching the right type to each beat, not from decorating. Family coherence still holds: the signature framework figure recurs, the series voice is locked (see [`../learnings/`](../learnings/)).

**How a deck gets built:** the story (per-deck `_content-map.md`) names each beat's job → pick a type here → compose it from the paste-ready markup in [`../elements/`](../elements/) → follow [`../DESIGN-PRINCIPLES.md`](../DESIGN-PRINCIPLES.md) for the visual/animation system.

**Per-type metadata** (each `slide-types/<type>.md` carries the full set): `purpose · when-to-use (trigger) · density · element(s) · animation · lineage · build-priority`.

Legend. **density:** `V` visual-dense · `T` text-dense · `B` balanced. **status:** ✅ element coded in `deck-kit/` · ◻ to build.

---

## 1 · Orient: situate the audience

| Type | When to use (trigger) | Density | Element | Status |
|---|---|---|---|---|
| Title hero | Open the deck | V | `.slide--title` | ✅ |
| Agenda / roadmap | Set the mental scaffold; returning section anchor | B | linear-flow | ✅ |
| Section divider | Mark a topic boundary; reset attention | V | divider block | ✅ |
| Relevance hook | Establish the stake before teaching ("why this matters to you") | V | big-number / statement | ✅ |
| Assumptions checklist | Qualify "where we assume you are" | T | `.checklist` | ✅ |
| Executive summary (SCR) | Whole argument on one page for a senior audience | T | summary stack | ✅ |

## 2 · Explain: make a concept understood

| Type | When to use (trigger) | Density | Element | Status |
|---|---|---|---|---|
| Plain definition | Pin one term in jargon-free language on first use | B | `.def-block` + `.two-col` | ✅ |
| Concept-with-analogy | Introduce an abstract idea via a familiar anchor | B | analogy-map | ✅ |
| Named-framework figure | Introduce the organizing mental model (e.g. EAF); recurs across the family | V | `.eaf` | ✅ |
| Mental model (inputs→process→outputs) | Show how a system works structurally | V | wiring-flow | ✅ |
| Business-application translation | Turn a technical concept into a concrete business scenario | B | `.analogy` two-col | ✅-ish |
| Spectrum / continuum | Replace a false binary with "where on the dial" | V | spectrum bar | ✅ |

## 3 · Demonstrate: show how it works / a sequence

| Type | When to use (trigger) | Density | Element | Status |
|---|---|---|---|---|
| Step-by-step build | Reveal a multi-step sequence one step at a time | B | build pattern | ✅ |
| Process flow / stage-gate | A workflow with gates/decisions (HITL) | V | `.lifecycle` (+ gate) | ✅ |
| Value chain | Map activities end-to-end to locate value/cost | V | horizontal stages | ✅ |
| Worked example | A fully solved instance with the reasoning shown | B | worked-steps | ✅ |
| Roadmap / timeline (Gantt) | Phases, workstreams, and milestones over a horizon | V | roadmap-timeline | ✅ |

## 4 · Compare & decide: frame a choice

| Type | When to use (trigger) | Density | Element | Status |
|---|---|---|---|---|
| Calibration (gives / doesn't give / larger asset) | Honest "what it is and isn't" | T | `.tri` | ✅ |
| Decision framework (when X vs Y) | A recurring judgment call; a reusable rule | B | `.tri` / 2-col | ✅-ish |
| 2×2 matrix | Position options on two decision variables | V | matrix | ✅ |
| Before / after | Make the value of a change vivid (today vs with-it) | B | mirrored 2-col | ✅ |
| Comparison table (Harvey balls / RAG) | Options × criteria, scored | B | scored grid | ✅ |
| Issue / driver tree (MECE) | Decompose a problem/metric into branches | V | tree | ✅ |

## 5 · Prove: evidence & data

| Type | When to use (trigger) | Density | Element | Status |
|---|---|---|---|---|
| Big-number / stat | One striking figure is the whole point | V | big-number | ✅ |
| Six-card grid | N parallel concrete examples, each with a win | B | `.grid-6` | ✅ |
| Trend (line / column) | Change over time | V | chart | ✅ |
| Ranking (bar) | Compare discrete items by magnitude | V | chart | ✅ |
| Composition (stacked / 100% / pie) | Part-to-whole or mix | V | chart | ✅ |
| Waterfall / bridge | Explain the delta (revenue/cost/margin walk) | V | chart | ✅ |
| Maturity / heatmap assessment | Scan many ratings; audience self-assesses | V | heatmap | ✅ |
| Connectivity flow (hub → categories) | One standard/hub reaching many things (e.g. MCP → sources) | V | `.shipped-flow` | ✅ |

## 6 · Reframe & check: correct or confirm understanding

| Type | When to use (trigger) | Density | Element | Status |
|---|---|---|---|---|
| Misconception (myth vs reality) | Confront a wrong-but-common belief, additively | B | myth-vs-reality 2-col | ✅ |
| Knowledge-check / question | Force retrieval; re-engage mid-session | T | question card | ✅ |
| Recap / summary | Consolidate 3±1 takeaways at a section/end | T | `.checklist` / `.tri` | ✅-ish |

## 7 · Recommend & close: drive action

| Type | When to use (trigger) | Density | Element | Status |
|---|---|---|---|---|
| Recommendation summary | State the main recommendations, grouped | T | grouped list | ✅ |
| Next-steps / action plan | The immediate Monday-morning moves (owner, date) | T | action table | ✅ |
| Send-off | Land one substantive takeaway (not a slogan) | V | `.slide--sendoff` | ✅ |
| Offer / CTA | Name the next step / service (no prices) | B | `.offers` + `.cta-strip` | ✅ |

---

## Which types suit which deck purpose

A deck rarely uses all seven categories evenly. Lean by purpose (see [`../learnings/`](../learnings/)):

- **Training / seminar:** heavy on Orient + Explain + Demonstrate + Reframe-and-check, closing with Recommend-and-close. The signature framework figure recurs.
- **Consulting / recommendation:** Orient (exec summary, SCQA) → Compare-and-decide + Prove → Recommend-and-close. Action titles throughout.
- **Financial / data delivery:** mostly Prove (insight-first charts) + Compare-and-decide, framed by a tight Orient and a clear recommendation.
