# Element: Misconception (myth vs reality)

Two stacked rows that confront a common wrong belief, additively. The top row, **Easy to assume**, states the myth in muted, quiet type. The bottom row, **What is actually true**, states the reality with the slide's single gold accent and the visual weight. The reader watches the idea expand rather than feeling corrected: the myth is framed as a reasonable assumption, never as the audience's mistake.

- **Slide type:** Misconception (Reframe & check). See [`../slide-types/misconception.md`](../slide-types/misconception.md).
- **Use it for:** the one or two hinge moments in a teaching deck where an assumption is steering decisions and the next idea cannot land until it is reframed. Refutation beats assertion.
- **Density:** B. **Layout:** `data-layout="misconception"`.
- **Don't:** phrase the myth as "you are wrong" or "your thinking is missing X." Use "easy to assume," "the common read," "the natural conclusion." The reality row adds; it never grades. One gold accent only, and it lives on the reality row.

## CSS / asset dependencies

- Styles: the `.myth-reality*` rules in `deck-kit/slides.css`, plus the `[data-layout="misconception"] .myth-reality { margin-block: auto; }` vertical balance rule that floats the two rows to the optical center.
- Uses the assertion headline (`.slide-head--assert`) like every meat slide.
- No icons required. An optional gold connector glyph between the rows is drawn as a CSS background data-URI (gold, the single accent), so no sprite dependency.

## Variants

- **Stacked (default).** Myth row over reality row, full width. Best when each side carries a sentence or two, which is the usual case. This is the markup below.
- **Side-by-side.** Add `.myth-reality--cols` to lay the two rows out as two columns instead (same inner markup). Use only when both sides are short label phrases, never when either side runs to two lines, or the columns go ragged.

## Paste-ready markup (stacked; realistic mid-market example)

```html
<section class="slide" data-layout="misconception" data-mood="paper">
  <div class="slide-pad">
    <header class="slide-head slide-head--assert">
      <h2>Adopting AI is less about new software than new wiring.</h2>
    </header>
    <div class="myth-reality">
      <div class="mr-row mr-row--myth" data-build="1">
        <span class="mr-label">Easy to assume</span>
        <p class="mr-text">Getting value from AI means buying a new platform and
          moving the work onto it, a project the size of the last ERP rollout.</p>
      </div>
      <div class="mr-bridge" data-build="2" aria-hidden="true"></div>
      <div class="mr-row mr-row--reality" data-build="2">
        <span class="mr-label">What is actually true</span>
        <p class="mr-text">Most of the early return comes from <b>connecting AI to
          the systems you already run</b>, your CRM, your inbox, your file share,
          so the wiring matters more than the purchase.</p>
      </div>
    </div>
  </div>
  <footer class="slide-chrome"><span>Where the value is</span><span><span class="num">06</span> / 13</span></footer>
  <aside class="notes"><span class="label">Speaker notes</span><p>This is the assumption I want to retire before we go further, because it sets the budget conversation off in the wrong direction. The instinct is reasonable: every big capability in the last twenty years arrived as a platform you bought and migrated onto, so AI feels like it should be the same shape. Name that read generously, it is the natural conclusion.</p><p>Then add the truth beside it. The teams seeing returns this year mostly did not replace anything. They connected a capable model to the systems already in place and let it read, draft, and route inside the work that already happens. The leverage is in the wiring, the access and the workflow, not in the line item. That reframes the first project from a twelve-month migration into a contained connection you can scope in a quarter, which is exactly where we are headed next.</p></aside>
</section>
```

## Animation

- **Build 1:** the **Easy to assume** myth row fades in. The speaker states the assumption out loud and grants that it is reasonable.
- **Build 2:** the gold bridge glyph and the **What is actually true** reality row fade in together (one press, the bridge and row share `data-build="2"`). The reality is the payoff beat.

The two rows are peers in a deliberate sequence, not a cascade, so each takes its own press: the myth has to sit alone for a moment before the reframe arrives, or the refutation loses its force. The block is vertically centered via `margin-block: auto` so it never clings to the top.
