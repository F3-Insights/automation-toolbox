# Element: Concept-with-analogy (analogy-map)

A two-panel mapping that explains an abstract or technical concept by laying it beside a familiar one. The **left panel is the SOURCE** the audience already owns (an everyday situation from their working life); the **right panel is the TARGET** (the new concept). Each panel carries an icon, a label, and two or three short trait chips. **Correspondence connectors** join each source trait to its matching target trait, so the eye reads the mapping one row at a time. A single muted caption underneath **names where the analogy breaks**, so the room does not leave with an over-extended, and therefore wrong, mental model.

- **Slide type:** Concept-with-analogy (Explain). See [`../slide-types/concept-with-analogy.md`](../slide-types/concept-with-analogy.md).
- **Use it for:** the first time an abstract idea (context window, retrieval, an agent, fine-tuning) enters the room and a plain definition would land as jargon.
- **Density:** B. **Layout:** `data-layout="analogy-map"`.
- **Don't:** stack more than three trait rows (the mapping stops being legible), and never ship without the breaks-caption (`presentation/learnings/training-decks.md` §3: an unbounded analogy becomes the learner's only, wrong model). One gold accent: the connectors plus the target icon. The source panel stays quiet navy.

## CSS / asset dependencies

- Styles: the `.analogy-map*` rules added to `deck-kit/slides.css`.
- Icons: `deck-kit/icons.svg` (any two `icon-*` symbols; the markup below uses `icon-users` for the familiar source and `icon-brain` for the target).
- Reuses existing primitives: `.slide-head--assert`, the icon-circle treatment pattern (mirrors `.call-node .icon-wrap`), and the muted-mono caption voice.
- The `href` below is written from a seminar at `Content/Seminars/<slug>/` inside the training folder (setting `training_dir`), three levels up to its root. Adjust if pasted elsewhere.

## Variants

- **Icon choice** is free: pick the two `icon-*` symbols that best read as the source and the target. Keep both at the same node size for visual parity.
- **Two or three trait rows.** Two rows reads cleaner; three is the ceiling. The connector count follows the row count automatically (one `.am-link` per row).
- **Mood:** `paper` or `warm`. The breaks-caption sits in `--paper-warm` on a `paper` slide for a soft editorial close; flip if the slide mood is `warm`.

## Paste-ready markup

```html
<section class="slide" data-layout="analogy-map" data-mood="paper">
  <div class="slide-pad">
    <header class="slide-head slide-head--assert">
      <h2>An agent starts every task with the memory of a brand-new hire.</h2>
    </header>
    <div class="analogy-map">
      <!-- SOURCE: the familiar anchor (build 1) -->
      <div class="am-panel am-panel--source" data-build="1">
        <span class="am-role">Familiar</span>
        <div class="am-node">
          <span class="am-icon"><svg class="icon icon--lg"><use href="../../../Resources/presentation/deck-kit/icons.svg?v=4#icon-users"/></svg></span>
          <span class="am-label">A new hire's first morning</span>
        </div>
        <ul class="am-traits">
          <li>Knows the role, not your accounts</li>
          <li>Reads only what you hand them</li>
          <li>Forgets the day once they go home</li>
        </ul>
      </div>

      <!-- the mapping: one connector per trait row (build 2) -->
      <div class="am-links" data-build="2">
        <span class="am-link" style="--stagger: 0s"></span>
        <span class="am-link" style="--stagger: .12s"></span>
        <span class="am-link" style="--stagger: .24s"></span>
      </div>

      <!-- TARGET: the new concept (build 2) -->
      <div class="am-panel am-panel--target" data-build="2">
        <span class="am-role">The agent</span>
        <div class="am-node">
          <span class="am-icon"><svg class="icon icon--lg"><use href="../../../Resources/presentation/deck-kit/icons.svg?v=4#icon-brain"/></svg></span>
          <span class="am-label">An AI agent on a task</span>
        </div>
        <ul class="am-traits">
          <li>Trained on the world, blank on your data</li>
          <li>Sees only the context you load in</li>
          <li>Starts fresh when the session ends</li>
        </ul>
      </div>
    </div>
    <p class="am-breaks" data-build="3">Where it breaks: a new hire learns and remembers from week to week. The agent does not, unless you build the memory in.</p>
  </div>
  <footer class="slide-chrome"><span>SECTION NAME</span><span><span class="num">05</span> / NN</span></footer>
  <aside class="notes"><span class="label">Speaker notes</span><p>…</p></aside>
</section>
```

## Animation

- **Build 1:** the SOURCE panel fades in. The speaker introduces the familiar anchor on its own, so the room settles into something they already know.
- **Build 2:** the TARGET panel and the three correspondence connectors cascade in together on ONE press (peers, staggered via `--stagger`), reading left to right so each connector lands on its trait row. This is the mapping beat.
- **Build 3:** the breaks-caption fades in. The honest close: "here is where the analogy stops being true."

Three presses, three script beats. The two panels are frames, so their headers and icons are visible from slide entry; only the trait rows and connectors stage in. Honors `prefers-reduced-motion` via the global rule.
