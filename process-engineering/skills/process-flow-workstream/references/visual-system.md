# Process flow: the visual system and the generator

The house style, node vocabulary, naming rules, layout mechanics and the as-is/to-be device (Phase 3), how the generator is built and iterated (Phase 4), and the reusable subagent prompt patterns. Read it when drawing or reviewing a map. The method is `SKILL.md` in this skill.

## Phase 3: The visual system

### 3.1 Discover the house style first
Before writing any HTML, send a scout agent through prior deliverables/brand assets to extract: exact hex tokens, fonts, node treatments, legend conventions, and any explicit design rules. A typical outcome: one dark structural color, one sole accent, **a third color reserved for decision gates**, red only for friction, thin 1.3 to 1.6px strokes, mono-caps labels, bespoke inline SVG (no Mermaid or diagram libraries for deliverables). The `brand-guide` skill says how to apply a house brand.

### 3.2 Node vocabulary (standard flowchart semantics)
- **Rectangle** = process step (white fill, navy stroke)
- **Diamond** = decision, phrased as a question (green stroke/wash)
- **Cylinder** = data store (gold wash): folders, spreadsheets, databases
- **Document shape** = data input/artifact (gold wash): a requisition form, an invoice
- **System chips**: small mono-caps tags under a node (ERP, EMAIL, EXCEL…) marking every software touchpoint; in the to-be, a PLATFORM chip marks the proposed system
- **Badges** above nodes: keep the taxonomy tiny: **PAIN** and **DELAY** (red outline) for as-is friction; **NEW** (solid gold) and **TBD** (dashed gold outline) for to-be. *Eight badge species is a taxonomy, not a signal*; collapse early.
- **Numbered gold dots** on nodes → **callout cards** below the diagram
- **Dashed connectors** = exceptions/loopbacks; solid = main flow
- Always render a **legend** and a one-line abbreviation key (define the client's acronyms).

### 3.3 Naming rules (these are load-bearing)
- **Every process rectangle: imperative verb + object, with the swim lane as the implied subject.** "Confirm delivery date" in the Supplier lane means the supplier confirms. This doubles as a lane-placement test: if you can't phrase it that way, the box is in the wrong lane or isn't a step.
- Decisions are questions ("Within budget?"). Stores/documents are nouns. Automated steps get an "Auto-" verb with the executing system's chip.
- **No jargon in node titles.** Plain-word test: would a CEO squint? "PO created via API" → "Auto-create purchase order." Expand acronyms once (in the key line).
- **Nodes stay skinny; evidence goes in callouts.** Node = verb phrase + optional ≤6-word subtitle. Numbers, quotes, and explanations live in the numbered callout cards (1–2 sentences each, color-coded left border: red pain / gold new / dashed-gold TBD).

### 3.4 Layout mechanics (as implemented in the generator)
- Time flows left→right in fixed columns (`COLW`); lanes are horizontal bands (`LANE_H`).
- **Collapse unused lanes per section**: empty gray bands are the single biggest ink-waste; ~40% of canvas in the first draft.
- Fixed pixel-width SVGs (`width`/`height` attributes, not CSS stretch) so node scale is identical across sections; wide sections scroll inside their own container.
- Edge routing, three cases: forward = horizontal cubic bezier between node edge midpoints; **same-lane skip (bypass) = arc over the top** of intermediate nodes (never route behind: it reads as flow-through); backward loop = dashed dip below the lanes.
- Edge labels get a white text halo (`paint-order:stroke`) so they survive crossings.
- Callout cards: flex row, `flex:1 1 300px; max-width:480px`: fills wide screens without ballooning, wraps gracefully on narrow ones.

### 3.5 The as-is / to-be device
- Each section holds **two complete flows** with a per-section AS-IS/TO-BE toggle plus a master toggle; to-be scroller gets a gold border tint.
- **The toggle is exploration, not the argument.** The argument is the **delta strip** at the top of each section: one line of TODAY (red label, the quantified pain) → one line of PROPOSED (gold label, the outcome). Without this, comparing views is a memory test.
- To-be honesty: NEW marks genuinely proposed capability; **TBD marks scope not yet designed** (clients trust diagrams that admit unknowns); repeat only the nodes that persist.
- A "headline" line per section (italic accent) can carry the pitch; include in the dual version, **strip from the factual variant** (see Phase 6).

## Phase 4: Build as a generator, iterate visually

**Never hand-author the SVG.** Build a Python generator where all content is data:

```python
SECTIONS = [{
  "num": "01", "title": ..., "headline": ..., "delta": (today, proposed),
  "asis": {"caption": ..., "nodes": [N(id, LANE, col, kind, title, sub, chips, badge, note)],
            "edges": [(src, dst, "solid|dash", label)], "callouts": [(n, type, text)]},
  "tobe": {...},
}, ...]
```

Rendering = pure functions (`render_node`, `render_edge`, `render_flow`, `render_callouts`, `render_section`) emitting inline SVG in a standalone HTML file (Google Fonts link + one `<style>` block; no external JS/CSS dependencies). One script emits **all variants** so they can never drift.

**Iteration loop:** edit `SECTIONS` → run script → serve locally (`python3 -m http.server`; `file://` is blocked for browser tooling) → **screenshot with a headless browser and actually look at it** → fix → repeat. Layout bugs (stretched sections, lane-label collisions, edges tunneling through nodes, wrapped callouts) are caught by looking at renders, not by reading code. Programmatic checks help too (e.g., assert all callout cards share a row; grep the factual variant for leftover "TO-BE"/"PROPOSED" strings).

## Appendix A: Reusable subagent prompt patterns

- **Reader:** "Read <doc> fully. Return a structured brief covering <domains>. Preserve verbatim numbers, names, system names. Your final message is the deliverable; the parent will rely on it without reading the source."
- **Style scout:** "Explore <repo/folder> for prior diagrams. For each: format/tech, hex colors, fonts, node shapes, legend conventions, reusable CSS. Quote source snippets so the style can be reproduced exactly. Note which artifact is most recent/polished."
- **CEO critic:** persona + screenshots + the seven tests in Phase 5.1 of `SKILL.md` + "be harsh but every criticism comes with a specific, actionable fix" + per-section grades + "name the ONE change."
- **Fact-checker:** claim checklist + assigned source subset + three-verdict classification + quote-with-location requirement + "list significant omissions."
- **Completeness auditor:** standard process model + "not inefficiencies, but missing standard elements" + question-phrased output + priority tiers + "if the sources already answer it, cite instead of asking."
- **Transcript extractor (diff-shaped):** preprocessed chunk + claim checklist + open-question list + "new facts only" + timestamp/speaker/quote for everything.
