# Element: Relevance hook

An Orient element that establishes the business stake before any teaching begins. One sharp, full-sentence statement of a pain or opportunity sits on the left, anchored on the right by a single striking, attributed number. The statement leads; the number is evidence for it, not the point itself. One gold accent: the figure.

- **Slide type:** Relevance hook (Orient). See [`../slide-types/_INDEX.md`](../slide-types/_INDEX.md).
- **Use it for:** the first slide of a section, answering "why this matters to you" before you teach a concept. Setup slide, no leave-behind.
- **Density:** V. **Layout:** `data-layout="relevance"`.
- **Don't:** stack two stats, lead with the number, or frame the stake as something the audience is doing wrong. State one opportunity plainly and attribute the figure (DESIGN-PRINCIPLES §8, _universal sourcing rule).

## CSS / asset dependencies

- Styles: the `.relevance*` rules added to `deck-kit/slides.css` (the `[data-layout="relevance"]` block centers the body in the available height and caps it above the footer chrome).
- Reuses brand tokens only: `--navy`, `--gold`, `--paper`, `--line`, `--muted`, `--obsidian`, `--ink`, `--serif`, `--grotesk`, `--mono`, `--sans`.
- No icons required. The slide head uses the existing `.slide-head` topic-title treatment (this is a setup slide, not a meat slide, so it takes a topic title rather than an assertion headline).

## Variants

- **`data-mood="paper"`** (default): light slide, navy statement, gold figure. The calm register for most section openers.
- **`data-mood="warm"`**: warm-paper background for an editorial section opener. Identical structure.
- The `.relevance-figure` may carry a prefix or suffix unit (`$`, `%`, `hrs`, `×`) in `.relevance-unit` so the numeral stays dominant and the unit reads as support.

## Paste-ready markup

```html
<section class="slide" data-layout="relevance" data-mood="paper">
  <div class="slide-pad">
    <header class="slide-head">
      <h2>Why this matters to your back office</h2>
    </header>
    <div class="relevance">
      <div class="relevance-stake" data-build="1">
        <p class="relevance-statement">Every invoice your team keys by hand is a place
          AI can take the first pass, and free a person for the exceptions that actually
          need judgment.</p>
        <p class="relevance-context">For a 40-person finance and operations team, that is
          the difference between chasing paperwork and closing the month early.</p>
      </div>
      <div class="relevance-stat" data-build="2">
        <p class="relevance-figure"><span class="relevance-unit relevance-unit--pre">$</span>16<span class="relevance-unit">/invoice</span></p>
        <p class="relevance-figure-label">average fully-loaded cost to process one invoice manually</p>
        <p class="relevance-source">Illustrative figure; cite your benchmark</p>
      </div>
    </div>
  </div>
  <footer class="slide-chrome"><span>Demo</span><span><span class="num">04</span> / 14</span></footer>
  <aside class="notes"><span class="label">Speaker notes</span><p>Open the section on the stake, not the technology. Name a real number first, let it sit, then connect it to their P and L: thousands of invoices a year, sixteen dollars each, and most of that is a person doing rote keying. The point is not to cut the team, it is to point the team at the exceptions. Hold the how for the next slides.</p></aside>
</section>
```

## Animation

- **Build 1:** the stake statement plus its one-line context fade in. One press. This is the beat the speaker opens on.
- **Build 2:** the figure, its label, and the source fade in together as one beat (the numeral and its caption are one idea, so they cascade on a single press, not one per line).

The header and the empty layout frame are visible from slide entry, so the slide never looks empty. Scroll view shows both builds at once.
