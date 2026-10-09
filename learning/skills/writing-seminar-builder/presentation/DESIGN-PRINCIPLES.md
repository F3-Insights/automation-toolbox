# Web Seminar Design Principles

Authoritative, living reference for all seminars in the training folder (layout defined in the skill's `SKILL.md`, "The training folder"). This is the single consolidated record of design + content learnings; once a principle lands here it applies to every slide in every seminar going forward. When a new decision overturns an old rule, **fix the old rule in place** so the document never contradicts itself.

Companion documents:
- The training folder's `CONTEXT.md`, when it has one: business, audience, voice
- The `brand-guide` skill: brand guide source, deck style guide, voice and tone
- [README.md](README.md): folder structure, how to preview, keyboard nav

---

## 1. Philosophy

**Story first: the overarching rule.** The deck is one narrative, not a pile of slides. Every slide must add to the story *concisely and substantially*, or it is cut. Before designing any slide, name its job in the arc. Slides fall into two kinds:
- **Setup** (title, "where you are," framing, transitions) earns its place by moving the story forward and orienting the audience. Light by design. No leave-behind obligation.
- **Meat** (the middle ~8 of 13) teaches something the audience can act on. Carries the substance: an assertion headline, evidence, and a concrete leave-behind artifact.

The slide-language codes below are *tools, applied by role*, not mandates on every slide. Use each where the slide's job calls for it.

**Story craft (how the narrative holds together).**
- **State the spine once, as a hinge.** Find the one argument the talk makes and put it at the center as a pivot. Everything before it *earns* it; everything after it *pays it off*. A spine whispered across four scattered slides reads as no spine at all.
- **Evidence must prove the assertion, not just sit near it.** The visual under an assertion headline has to make *that* claim land. If the headline says one thing and the body shows an adjacent-but-different thing, the slide has an identity crisis.
- **Clean mechanics ≠ sound structure.** A slide can have a one-line headline, no dashes, and perfect spacing and still be wrong, if its body doesn't serve its job. Fix the story before polishing the pixels.

**Editorial, not decorative.** Every visual choice carries the talk's meaning. If a graphic doesn't sharpen an idea, it's noise.

**Trusted advisor, not salesperson.** The audience is the one the owner describes (setting `audience`; see the skill's "The audience"), for example finance leaders at mid-sized companies. Whoever they are, the visual register is calm, matter-of-fact, sophisticated. Never flashy.

**Two views, one source.** Each `index.html` renders as both a **slide view** (click-driven builds, projector-ready) and a **scroll view** (long-form editorial). Authoring decisions must serve both.

**Super clean, professional.** No overlaps. No labels touching borders. No truncation. No "almost-aligned." If something looks 95% right, it's not right.

---

## 1A. Slide-language codes (apply by slide role)

Tools, not mandates. The meat slides should carry most of these; setup and transition slides stay light.

**Action titles (meat slides): the title IS the takeaway.** This is the McKinsey / Minto Pyramid Principle standard, and it is non-negotiable. Every meat-slide title is a complete, plain sentence stating the slide's *conclusion* (the "so what"), not a label for the topic, and **never a catchphrase**. An executive who reads only the titles, top to bottom, should follow the entire argument (this is the deck's *horizontal logic*). The body exists to prove the title; if an element on the slide doesn't support the title, cut it.

A strong action title is **specific, and carries weight**: it is *compelling, surprising, or a position*, and it conveys real insight, not the obvious. Craft rules (all of them):
- **State a conclusion, not a process.** ✅ "Eight high-impact cost levers, three of them free." ❌ "We analyzed the cost base."
- **Be concrete and specific.** Name the thing, the number, the stakes. Avoid vague verbs ("can be optimized," "is important").
- **Active voice, ≤ ~15 words, one line.** Lead with the subject doing the thing.
- **Say something only you would say.** If a competitor's deck could carry the same title, it's too generic.
- ❌ "What is a Tool?" → ✅ "A tool lets the AI act in your real systems, not just describe them."

**No catchphrases, anywhere, ever.** This is the hardest rule in the deck. We are not selling; we are teaching people who have deep thought and real insight to share. Punchy parallel fragments, clever wordplay, and AI-pitch cadence are banned in **titles, sub-lines, and body** alike:
- ❌ "Grab what's generic. Build what's yours."  ❌ "Stop generating. Start executing."  ❌ "Brain + hands = a worker."
- ✅ A title that says the real thing: "You can download a published Skill, or build your own."

Every line on a meat slide must carry value or meaning. If a line is only there for rhythm or polish, it is noise; delete it. Named-concept and setup slides are the exception to *action* phrasing only: a noun-phrase title is fine there (e.g. "Effective Agentic Framework", the title slide), but a catchphrase is not, even there.

**Leave-behind value (meat slides).** A meat slide should be useful to someone reading the deck *without* the talk: a concrete artifact: numbered steps, a screenshot, a named list. But the depth (judgment, nuance, war stories) stays in spoken commentary. The deck is the map, not the territory. Setup slides ("here's where you should be") carry no leave-behind.

**The silent-read bar (deck-level).** The scroll view alone, with no speaker, should function as a short editorial piece an executive would forward to a colleague. Every meat slide carries at least one of: a number that does real work, a named real example, a decision rule, an artifact. If a slide's value exists only in the speaker notes, the slide is thin. Fix the slide, don't pad the notes.

**Cognitive load (all slides).** One idea per slide. The slide never restates your spoken script verbatim; it simplifies and anchors. No multi-sentence paragraph of narrative beneath a visual.

**Visual honesty (production rule).** Build what code does well: geometric diagrams, flows, frameworks, node/connector figures. Do NOT fake photographic product screenshots or bespoke illustration. Those get a clean framed *slot* and the real asset is dropped in. If a diagram can't reach a professional bar in code, it becomes a slot too. Never ship amateur visuals to cover a gap; say so instead.

### Writing mechanics (hard rules, all slides)

- **No em dashes (U+2014), ever.** The long dash reads as AI-generated. Use a period, comma, colon, or the word "to" instead. This applies to every word visible on a slide (and speaker notes too). Re-read after writing.
- **No orphan wraps.** A concept sits on ONE row. If a bullet, label, or title wraps a single word onto a second line, reword it shorter or widen the container until it fits. A slide **title is one line** unless there is a deliberate reason. Verify in Playwright, not by eye.
- **Name things, don't article them.** Diagram labels, column headers, and comparison captions use the bare noun or a meaningful qualifier, never a weak indefinite article. ❌ "a prompt" / "a skill" → ✅ "Chat prompt" / "Skill", or a qualifier that adds information ("an ad-hoc prompt"). The article adds no meaning and reads as tentative. (Sentence-form action titles still use natural grammar; this rule is about labels and headers.)
- **Vertical balance.** Content must not cling to the top with dead space below. Center the main body block in the available height (e.g. `margin-block: auto` on the content block) unless the layout has trailing elements that fill the space.
- **The gold foot-line sits in the same place on every slide.** A trailing gold `.foot-line` (the slide's takeaway) is **centered in the band between the body's bottom edge and the footer chrome**, never tucked tight under the body on one slide and dropped to the footer on the next. The deck-kit does this with three equal auto-margin gaps (header→body, body→foot, foot→footer); on a full slide where the body leaves no slack, the line rides just under the body and still clears the chrome. Consistency of this placement across the deck is the rule, not any single slide's spacing.

---

## 1B. The idea picks the form (anti-uniformity rules)

A series where every deck runs the same grid → calibration → lifecycle sequence reads as the output of a template, no matter how clean each slide is. Layout variety is not decoration; it is the visible evidence that someone thought about *this* idea. Four rules:

- **Name the idea's shape before choosing a layout.** A tension or choice → two-column or 2×2; a sequence → flow; one decisive fact → big number; a real thing → artifact slot or screenshot; a range → spectrum; a claim → assertion + the one visual that proves it. **A card grid is the layout of last resort.** Before reaching for one, ask whether the "list" is really a disguised ranking, decision, or sequence. It usually is.
- **Pattern budget per deck.** At most ONE card grid (`.grid-6` or kin) per deck; no other layout shape appears more than twice. (Exempt: the EAF signature figure and the title/send-off chrome: those repeats are the brand thread, and they only earn that exemption because everything else varies.) A 12-slide deck should draw on roughly six or more distinct layout shapes.
- **Vary density deliberately.** Each deck gets at least one near-empty slide (one sentence or one number commanding the full stage) and at least one genuinely dense artifact slide. Uniform medium density across twelve slides is itself an AI tell.
- **Break perfect parallelism.** Peer items in a set must not share identical grammatical shape and length: six cells of "Two-Word Label
  + one balanced sentence" is the strongest machine-written signal there is. Let the set be ragged: one cell carries the number, one the named example, one the caution, one the star ("start here"). And show the true count: if there are five real things, show five. Never pad to fill a grid.

---

## 2. The Effective Agentic Framework vocabulary

The house signature framework (the framework slide early in a deck, reused across a seminar family). **Five elements:** four working parts (**Model, Prompt, Context, Tools**) bound together by the **Harness**, with **People** engaging the whole system from *outside*, through the Harness. Use these names verbatim; do not invent synonyms.

| Element | Icon (`deck-kit/icons.svg`) | Role in the figure |
|---|---|---|
| **MODEL**   | `icon-brain`          | working part (core) |
| **PROMPT**  | `icon-notebook-pen`   | working part (core) |
| **CONTEXT** | `icon-book-open-text` | working part (core) |
| **TOOLS**   | `icon-wrench`         | working part (core) |
| **HARNESS** | (ring label)          | binds the four parts into one system |
| **PEOPLE**  | `icon-users`          | external; engages the system via the Harness |

**No printed annotations.** Do not label the icons with explanatory glosses like *"the brain"* or *"your data"* on the slide. That is what the speaker *says*; printing it on the model is clutter (and reads as talking down to the audience). The mono caps label stands alone.

**Focus by `data-focus`.** Whichever element a slide is *about* lights gold; the rest stay quiet navy. In the `.eaf` figure this is a single attribute (`data-focus="tools"`) so one reusable figure serves every slide. See §7.

---

## 3. Visual primitives

### 3.1 Color

Pulled from the house brand guide (the `brand-guide` skill; F3 Insights is the worked example here), defined as CSS custom properties in `deck-kit/brand.css`.

| Token | Hex | Role |
|---|---|---|
| `--navy` | `#1E3A6E` | Primary structure: ring strokes, definition box backgrounds, send-off, body type |
| `--obsidian` | `#0F172A` | Ink for headings |
| `--gold` | `#8F6B2E` | **The single accent color.** Active/forward elements: eyebrows, forward arrows, filled "protagonist" circles, italic punchlines |
| `--gold-foil` | `#C9A24B` | Highlight tint for hero/send-off, never as a primary accent |
| `--mist` | `#7DD3FC` | Tertiary: atmospheric glows in hero blocks |
| `--muted` | `#5A6473` | **Secondary/return:** gray return arrows, body annotations, footnotes |
| `--paper` | `#F6F7F9` | Cool card / diagram background |
| `--paper-warm` | `#F3EFE7` | Warm editorial section background (scroll view) |
| `--ink` | `#0F172A` | Body text |

**One accent color per slide: gold.** Do not stack accents. Mist and gold-foil are atmosphere only.

### 3.2 Type

| Family | Use |
|---|---|
| **Hanken Grotesk** (display sans, 800 weight) | Slide titles (`h2`), big-number callouts |
| **Inter** (sans, 400/600 weight) | Body text, card labels |
| **Fraunces** (serif, 300 italic) | Editorial display moments, annotations under labels, punchlines |
| **IBM Plex Mono** (mono, 500/600 weight) | Eyebrows, chrome, labels (MODEL, TOOL, CONTEXT, FUNCTION CALL, etc.), section numbers |

**Hierarchy rule for labeled elements:** the *noun* (MODEL, TOOL, CONTEXT, LOOKUP, etc.) is the dominant label, in mono caps, navy, bold, spaced. Do **not** add an explanatory gloss underneath it (*"the brain," "your data"*). Those are spoken, not printed (see §2). Fraunces italic is reserved for genuine editorial moments (a serif sub-line), not for labeling every icon.

**Body and labels run large.** This is a room of executives, not a dense report. The deck-kit body/label scale is deliberately large; favour the larger sizes (diagram labels, focus lines, list body, card text). When a slide gets full, **tighten its spacing, never shrink the text** back below the scale. Only true hero type (titles, big-number callouts) sits above this body scale.

**Titles run large.** Small titles read as timid; size them up. Topic / named-concept titles sit at **~58px**, assertion / action-title sentences at **~38px** (they hold more words but must still command the top of the slide). The title is the loudest thing on a content slide after the hero figure.

**Emphasis word vs. connective words.** When a label combines a hero noun with connective words ("packaged as a **Skill**", "**familiar**", "becomes **a Skill**"), the hero noun is the message and must be **roughly twice the size** of the connective words, which drop to the small mono/supporting size. Don't set the whole phrase at one mid-size; the eye should land on the one word that matters.

### 3.3 Surfaces

- **Paper-colored cards** (`var(--paper)`) with a thin border are the default container for diagrams, calibrations, and grids.
- **Navy blocks** (`var(--navy)`) are for definitional moments (`.def-block`, `.call-def`, etc.): they frame the *one* sentence the audience must remember.
- **Paper-warm sections** are scroll-view only: alternating section backgrounds for editorial rhythm.

### 3.4 Icons

The Lucide-based sprite at `deck-kit/icons.svg` is the single source of icons across all seminars.

**Stroke weight:** 2 (Lucide default). All icons share the same weight, cap, and corner radius; that visual coherence is what makes the deck feel like one system.

**Sizes:**
- 24px (`.icon`): inline in chips, list items, system tags
- 48px (`.icon--lg`): inside 88px node circles (MODEL/TOOL/CONTEXT)
- 56–88px (`.icon icon--xl`): hero moments

**Adding a new icon:** copy a Lucide SVG into `deck-kit/icons.svg` as a new `<symbol id="icon-NAME">` block, matching the existing stroke attributes. Then reference with `<use href="../deck-kit/icons.svg?v=N#icon-NAME"/>` (bump the `?v=N` to bust browser cache after adding icons).

---

## 4. Layout

### 4.1 Slide canvas

- **1280 × 720** design canvas (16:9), scaled by `presenter.js` to fit the viewport. Authoring happens at this canvas size.
- `.slide-pad` padding: **56px top / 72px sides / 60px bottom**. All slide content lives inside this.

### 4.2 Slide head

**Eyebrows are gone.** The cutesy purpose-label eyebrow ("Vocabulary first," "Honest calibration," "Grounding visual · series signature") read as filler and is removed. The headline carries the meaning.

A **meat slide** opens with an assertion headline (§1A), no eyebrow:
```html
<header class="slide-head slide-head--assert">
  <h2>A tool is a function the AI calls to act in your systems.</h2>
</header>
```
- `.slide-head--assert` runs the h2 at **~38px so the full sentence fits ONE line** (§1A writing mechanics). Keep action-title headlines ≤ ~60 characters / ~15 words.
- A **setup / named-concept** slide keeps the larger topic title (`.slide-head` h2 at ~58px, e.g. "Effective Agentic Framework") and an optional one-line italic `.sub`.

### 4.3 Diagram containers

Any diagram (call diagram, lifecycle, governance stack, etc.) lives inside a paper-colored card with `border: 1px solid var(--line)`, generous padding (`18px 24px` minimum), and `position: relative` so arrows can be absolutely positioned over it.

### 4.4 Multi-column layouts

Use **CSS Grid** with `align-items: start` for any diagram that mixes call-node columns with connector columns. Top-aligning the cells means lines positioned at consistent y-offsets land at consistent positions across the row.

**The 5-column call-diagram grid** (used by the call diagram, a hub-and-spoke figure, anywhere a flow has nodes and connectors):
```css
grid-template-columns:
  minmax(140px, 1fr)        /* node 1 (e.g., MODEL)      */
  minmax(120px, 1.2fr)      /* connector 1               */
  minmax(140px, 1fr)        /* node 2 (e.g., TOOL)       */
  minmax(120px, 1.2fr)      /* connector 2               */
  minmax(140px, 1fr);       /* node 3 (e.g., CONTEXT)    */
column-gap: 8px;
```

With this grid, the outer column centers sit at **~9%** and **~91%** of the inner content width. Use those percentages for absolutely- positioned elements (return arrows, annotations) that need to align to the outer columns.

### 4.5 Connectors between nodes

A connector cell is a **fixed-height** wrapper matching the icon diameter (typically 88px), with the arrow line absolutely positioned inside. Match the line's vertical position to the icon's visual target: usually the **top** of the icons for a flow that visually loops over the heads of the row, or the **center** if the connector is the focal element.

---

## 5. Arrows

### 5.1 The single arrow system

All arrows across the deck (gold forward arrows, gray return arrows, connectors in lifecycle flows, governance inheritance arrows) follow one system:

- **2.5px line weight.** Always. Gold and gray match.
- **CSS triangle arrowhead, 13 × 10 px.** `border-left/right/top/bottom` pattern, color matching the line.
- **Color encodes direction of flow:**
  - **Gold** = forward / outbound / active
  - **Muted gray** = return / inbound / secondary
- **Animated** arrows are HTML elements (line + CSS-triangle head), not SVG: SVG paths in non-uniformly-stretched viewBoxes hit rasterizer edge cases, and HTML divs animate predictably. **Static** connectors and whole geometric figures (the EAF circle, lifecycle arrows) *may* be SVG, because the slide scales uniformly so there's no distortion. See §5.5. Rule of thumb: animate in HTML, draw static geometry in SVG.

### 5.2 Trace animation

A line traces by animating `transform: scaleX(0) → scaleX(1)`:
- `transform-origin: left center` for left-to-right traces
- `transform-origin: right center` for right-to-left traces
- Duration: **0.85s** with `cubic-bezier(.4, 0, .2, 1)`
- Arrowhead `::after` fades in with `transition: opacity .15s ease-in .7s` (so it pops just as the line arrives at its destination)

### 5.3 Label timing

The text label on an arrow (`FUNCTION CALL`, `INVOKES`, etc.) is **invisible until the line finishes tracing.** It then fades in over 0.2s. Until the line is drawn, no text: the audience watches the line move, then reads what it represents.

### 5.4 Sequential traces

When multiple arrows reveal in the same build, stagger them with `transition-delay`. For three arrows (the call-diagram pattern):

| t (s) | Event |
|---:|---|
| 0.00 | Arrow 1 line traces |
| 0.70 | Arrow 1 arrowhead pops |
| 0.85 | Arrow 1 label fades in |
| 0.90 | Arrow 2 line traces |
| 1.60 | Arrow 2 arrowhead pops |
| 1.75 | Arrow 2 label fades in |
| 1.80 | Arrow 3 line traces |
| 2.55 | Arrow 3 arrowhead pops |
| 2.65 | Arrow 3 label fades in |

Total: ~2.7s. One `→` press fires the whole sequence.

---

### 5.5 Static connector arrows (non-animated flows)

The call-diagram trace arrows (§5.1–5.4) are HTML elements because they *animate*. For **static** forward connectors in a flow (between lifecycle stages, between the anatomy decider/executor, between the shipped-flow nodes), use a small gold arrow as a CSS `background` data-URI instead. It's one declaration, scales with the uniform slide scale (no text inside, so no distortion), and fades in with its parent build:

```css
.x-arrow {
  height: 14px;
  background: no-repeat center / 42px 14px
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 42 14'%3E%3Cline x1='1' y1='7' x2='30' y2='7' stroke='%238F6B2E' stroke-width='2.5'/%3E%3Cpath d='M28 1.5 L38 7 L28 12.5 Z' fill='%238F6B2E'/%3E%3C/svg%3E");
}
```

Still gold (`%238F6B2E`) for forward flow, still 2.5px line. To center the arrow on a circle row, give it `align-self: start` and a height equal to the icon circle's diameter so its centered background lands at the circle's center.

## 6. Animation system: the `data-build` pattern

### 6.1 How builds work

Any element with `data-build="N"` is hidden (opacity 0, translateY 10px) until the slide reaches build step N. The `presenter.js` runtime adds the `.in` class to all qualifying elements when the speaker presses `→` for the Nth time.

Pressing `→` at the last build advances to the next slide. Pressing `←` walks back through builds before going to the previous slide.

### 6.2 Builds map to script beats

Every build should correspond to **one beat in the speaker's script**. Builds aren't decorative; they pace delivery.

For the canonical 4-build content slide (the call-diagram pattern):

| Build | What appears | Script beat |
|---:|---|---|
| 0 | Header + frame (navy boxes empty) | (slide entry) |
| 1 | Definition fills in | The setup sentence |
| 2 | Diagram scaffolding (icons + labels) | "Here's what's involved." |
| 3 | Connectors trace in sequence | The relationship between the elements |
| 4 | Categories / chips / punchline | The takeaway |

Some slides will need more or fewer builds, but the structure (*frame → setup → scaffolding → relationships → takeaway*) is the template.

### 6.3 Container frames are always visible

If a navy block or paper card is the **frame** for content that fades in, put `data-build` on the **inner text**, not the frame. The frame should be visible from slide entry. This keeps the slide from looking empty.

### 6.4 Reduced motion

Every animation honors `@media (prefers-reduced-motion: reduce)` by setting `transition: none`. The end-state still renders correctly; the motion is just instant.

### 6.5 Scroll view

In `body.mode-scroll`, all `data-build` elements are visible at once (`opacity: 1; transform: none`). Scroll-view animation is reveal-on-scroll only.

### 6.6 Cascade a parallel set on ONE press, never one click per box

A row of peer items the speaker introduces **as a group** (the three calibration columns, the five lifecycle stages, the six tool cards, the two offer cards) is **one beat**, so it gets **one build**, not one build per box. Give every item in the set the *same* `data-build` number and an inline `--stagger` so they flow in left-to-right on a single `→`:

```html
<div class="col" data-build="1" style="--stagger: 0s">…</div>
<div class="col" data-build="1" style="--stagger: 0.12s">…</div>
<div class="col" data-build="1" style="--stagger: 0.24s">…</div>
```

The hook is global in `deck-kit/slides.css`:

```css
[data-build] { transition-delay: var(--stagger, 0s); }
```

Stagger steps: **~0.12s** for 2–3 items, **~0.08–0.10s** for 5–6 (so a six-card grid still finishes in well under a second). A *distinct* element that earns its own beat (a summary foot-line, a strategic-shift callout, a CTA strip) takes the **next** build number. The usual effect is that a slide drops from four, five or six presses to two.

**Reserve sequential one-per-press builds for genuine sequence**: the call-diagram arrow trace (model → tool → context), where each step *is* a separate idea. Peers cascade; a true sequence steps.

### 6.7 Reveal budget: ≤ 3 presses, and reveal in the idea's own order

**Hard cap: no slide takes more than 3 presses (`→`) to fully reveal.** If a slide needs more, the builds are too granular (cascade the peers, §6.6) or the slide is carrying more than one idea (split it). Most content slides land at 2–3 builds; setup slides at 0–1.

**Reveal follows the logic of the idea, not the order elements sit in the markup.** Animation is there to *narrate*: fade things in and highlight the active one as the speaker reaches it. Two governing patterns:

- **Causal / transformation flow** (e.g. *chat prompt → packaged as a Skill → what the Skill can now do*): reveal in that causal order, one beat per stage. Show the starting state, then the thing it becomes, *then* the consequences (the expansion list), and the expansion may itself cascade one-at-a-time within its single build. Don't reveal the end-state before the thing it results from, and don't let a downstream column appear before its cause.

- **Comparison table** (two things across shared dimensions, e.g. *Chat prompt* vs *Skill* across "Where it lives / Who can run it / What happens when that person leaves / Quality over time"): the **row headers and both column headers are the frame**, visible on entry (build 0), so the audience sees the structure of the comparison first. Then **fill column 1 top-to-bottom (one press), then column 2 (one press).** The comparison lands by contrast, column against column, not cell by cell.

**Motion vocabulary is fade-in + highlight.** Default reveal is a soft fade (opacity + small translate). The active element of a build gets the gold focus treatment (`data-focus`, a gold wash, or a gold label) so the eye knows where to look. No motion for motion's sake; every reveal maps to a spoken beat (§6.2).

---

## 7. Component patterns

These reusable patterns live in `deck-kit/slides.css`. Reuse them for execution quality (spacing, arrows, cards, build behavior), but the *choice* of pattern follows the idea's shape and the pattern budget (§1B), never the path of least resistance.

| Class | Pattern |
|---|---|
| `.checklist` | Bulleted setup with checkbox markers (assumptions slide) |
| `.eaf` + `.eaf-sector--*` + `data-focus` | **Effective Agentic Framework**: the reusable signature figure (framework slide + family). See note below. (Supersedes the old boxy `.bap`.) |
| `.def-block`, `.call-def` | Navy frame for the *one* definitional sentence |
| `.call-node`, `.call-node--tool` | The icon-circle node treatment |
| `.call-connector`, `.arrow-line` | Forward gold arrow with label |
| `.call-return`, `.ret-line` | Return gray arrow with label |
| `.analogy` | Two-column comparison table |
| `.tri` (with `.col.green`, `.col.gray`, `.col.gold`) | Three-column calibration |
| `.shipped-flow` + `.sf-node` + `.sf-hub` + `.sf-cats` | AI → hub → categories connectivity flow |
| `.grid-6` | 3×2 card grid with header icons |
| `.anatomy` + `.anat-row` (reuses `.call-node`) | Mirrored two-row analogy diagram: aligned decider/executor columns |
| `.lifecycle` + `.stage` + `.gate` + `.loopback` | Horizontal process flow with gold inter-stage connector arrows + HITL gate |
| `.callout-strip` | Full-width navy strip for a strategic shift / unified message |
| `.offers`, `.cta-strip` | Offer slide with two cards + CTA |
| `.slide--title`, `.slide--sendoff` | Full-bleed navy heros |
| `.khint` | Persistent keyboard hint, fixed bottom-center on the dark stage (slide mode only) |

**The Effective Agentic Framework figure (`.eaf`).** One self-contained SVG, drawn in the thin-stroke engineering style of the brand's architecture reference deck (in the `brand-guide` skill): a thin core circle split into four quadrants (Model, Prompt, Context, Tools), wrapped by a thin **Harness ring** whose label *interrupts* the ring at top, with **People** as an external node and a refined connector arrow into the ring. Lessons that produced it:
- **Thin strokes, faint fills, not solid blocks.** A fat filled donut reads as SmartArt. 1.5px strokes + a faint `rgba(navy,.05)` wash + a subtle `rgba(gold,.15)` focus wash is the professional register.
- **Keep labels off the ring.** Pull quadrant labels well inside the core radius or they clip against the ring.
- **Focus is one attribute.** `data-focus="tools"` lights that quadrant (gold wash + gold icon/label) and the focus fades in on build 1. Change the attribute to reuse the identical figure on any element's slide.
- **Hero figures run large.** The signature visual should be a large share of the slide, not a timid centerpiece (max-height ~460, the dominant element).

**Stage chrome (slide mode).** Two persistent affordances live on the dark backdrop *outside* the 1280×720 canvas, so they never touch slide content: the **view-toggle** (top-right) and the **keyboard hint** (`.khint`, bottom-center: `← → Navigate · F Fullscreen · S Notes · V Scroll`). Both are hidden in scroll mode. The hint is one static element near the top of `<body>`; style lives in `deck-kit/slides.css`.

---

## 8. Voice & content (cross-reference)

Also in the training folder's `CONTEXT.md`, when it has one, and the `brand-guide` skill. The content rules, applied to slide design:

- **No taglines, no cleverness, no fluff.** Write for a serious (if casual) executive. Lines that try to be clever ("When AI stops talking and starts doing," "Stop generating. Start executing.," "Brain + hands = a worker") read as a sales pitch. State the real thing plainly. This is the single most important content rule. (Full action-title / no-catchphrase rule: §1A.)
- **Operator's memo, not presentation copy.** The register of on-slide text is a sharp internal briefing written by someone who has done the thing: plain declarative sentences that commit to a position ("Start with the weekly report"); concrete nouns and named instances (the Friday flash report, month-end close, NetSuite as an instance of "your ERP") instead of category nouns (workflows, stakeholders, insights); one number that does real work per meat slide. Specificity is the anti-AI signal; balanced abstraction is the AI tell. Vendor-agnostic positioning still holds: name products as *examples*, never as the recommendation.
- **Specificity dial: decision-grade, not implementation-grade.** On-slide detail is calibrated so an executive could brief their team on *what* to do and *why* (the number, the pattern, the first move, the risk to plan for) but would still need help with *how* (configs, prompts, setup steps, per-industry baselines stay in the paid engagement). "Too detailed" and "too vague" are both misses on the same dial.
- **The gold sub-line must earn its place or be cut.** The single gold italic line some slides carry (the closing punchline under the body) is *not* a slot for a catchphrase. It is only justified when it adds a real **takeaway or a useful, value-bearing statement** the slide would be poorer without. ❌ "Building the ones you trust, with the testing behind them, is where we come in." (a sales line dressed as insight) → ✅ "You can also ask AI to help you build your own Skills." (a fact the exec can act on). When in doubt, delete it: a slide with no gold line beats a slide with a weak one.
- **Allowed exceptions to the no-sell rule.** Two, and only two: (1) the **closing offer slide**: selling the engagement is its job. (2) **Honest breadcrumbs to our other seminars**, when they genuinely help the audience go deeper on something out of scope (e.g. a risk call-out pointing to the data-security seminar). These must read as helpful, never pushy.
- **No em dashes; one-line titles; no orphan wraps.** See §1A writing mechanics. (Hard rules.)
- **No prices.** Name services (the offer names from `references/closing-offer-menu.md`), never dollar amounts.
- **Positive & additive.** Never imply the audience is doing something wrong. Frame additions, not corrections.
- **Risk topics lead with the positive unlock.** Governance slides open with what becomes possible, not what fails.
- **Slides are anchors, not scripts.** Lean text; depth lives in spoken commentary and speaker notes (§1A leave-behind).
- **The close is a substantive takeaway, not a punchy slogan.** End on the real idea the exec should repeat tomorrow (e.g. "the governed tool library you build this year is the capability you run on next year"), not a two-word flourish.

---

## 9. Quality verification (must do, every slide)

1. Drive the slide in Playwright. Press `→` through **every** build.
2. Wait ≥2s for all transitions to complete.
3. Screenshot the final state.
4. Inspect for:
   - **Alignment.** Arrows connect their endpoints. Verticals center on icon columns. No 1px gaps.
   - **Typography.** No SVG text inside non-uniformly-stretched viewBoxes (it distorts). Use HTML text.
   - **Container containment.** Labels sit fully inside their containers with breathing room. Never touch borders.
   - **Bottom-edge overflow.** Content-dense slides silently overrun the footer chrome and the slide's bottom edge. Measure the last element's `bottom` in design px; it must clear the `.slide-chrome` top (~673) and the 720 edge. The fix is tightening that slide's spacing, not moving the chrome.
   - **Post-animation state.** What the audience actually sees mid-talk.

If pixel-level uncertainty: scan with PIL/Python at specific coordinates (cheaper than re-rendering and re-eyeballing).

---

## 10. Authoring checklist

Before declaring a slide done:

**Story & content**
- [ ] Named the slide's job in the arc (setup vs meat) before designing
- [ ] Title is an **action title**: a complete, specific takeaway, ≤15 words, that the body proves
- [ ] Reading the titles alone tells the whole story (horizontal logic)
- [ ] **No catchphrases** in title, sub-line, or body; every line carries value
- [ ] Gold sub-line is a real takeaway/useful fact, or it's cut
- [ ] Labels name the thing (no weak "a prompt" / "a skill" articles)
- [ ] No eyebrow; headline carries the meaning
- [ ] Meat slide carries a concrete leave-behind; depth stays in commentary
- [ ] Passes a silent read: a number, named example, decision rule, or artifact ON the slide
- [ ] No em dashes anywhere visible
- [ ] Title on ONE line; no bullet/label wraps a single orphan word

**Layout & build**
- [ ] Layout chosen from the idea's shape; pattern budget holds (≤1 card grid per deck, no shape more than twice, §1B)
- [ ] Peer sets are ragged (no perfect parallelism) and show the true count, not a padded grid
- [ ] `data-mood` + `data-layout` set
- [ ] Frame containers visible from entry; only interior fades in
- [ ] **≤ 3 presses** to fully reveal; reveal follows the idea's order (§6.7)
- [ ] Comparison tables: row + column headers on entry, then fill column by column
- [ ] Parallel sets cascade on one press (`--stagger`); true sequences step
- [ ] Content vertically balanced (no clinging to the top)
- [ ] Visuals are real (built-well diagrams) or honest framed slots, never amateur filler
- [ ] Speaker notes in `<aside class="notes">` as `<p>` blocks
- [ ] Footer chrome with section name + slide number

**Verification (Playwright, measured not eyeballed)**
- [ ] Driven through every build; final state screenshot-checked
- [ ] No bottom-edge overflow (last element clears the chrome / 720)
- [ ] Headline + bullets measured as single lines
- [ ] Scroll view still renders (no animation reliance)
