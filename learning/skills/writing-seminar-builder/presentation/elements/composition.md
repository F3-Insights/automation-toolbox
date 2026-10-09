# Element: Composition (100% stacked bar)

A part-to-whole chart built as a 100% stacked bar, preferred over a pie. One horizontal bar fills the width, split into CSS segments that sum to 100%, each labeled with its share. The one segment that carries the message is lit gold, the rest stay muted navy, so the eye lands on the part that matters. An optional second bar stacks below to compare the mix across two groups on a shared baseline.

- **Slide type:** Composition (stacked / 100% / pie) (Prove). See [`../slide-types/composition.md`](../slide-types/composition.md).
- **Use it for:** showing how a total splits into parts (where the spend goes, what the workflow is made of) or how a mix shifts between two groups, when one slice is the argument and a pie would scatter the comparison around a circle.
- **Density:** V. **Layout:** `data-layout="composition"` (centers the bar block in the available height and keeps the source line clear of the footer chrome).
- **Don't:** use a pie, exploded or 3-D anything, more than about five segments (slivers stop being legible), or a second accent color. One gold accent: the focal segment. Everything non-focal is muted navy. Per the data rules, every figure cites a named or clearly-illustrative source and carries no prices.

## CSS / asset dependencies

- Styles: the `.comp*` rules in `css_additions` (appended to `deck-kit/slides.css`), plus the global `[data-build]` fade and `--stagger` hook already in `slides.css`.
- Reuses existing primitives: `.slide-head--assert` for the takeaway headline, `.foot-line` for the gold italic takeaway, `.slide-chrome` footer, and the build/`--stagger` cascade system.
- No icons, no SVG. The bar is a flex row of HTML segments, so it scales cleanly with the uniform slide scale (no viewBox text distortion). Segment widths are set inline with `style="--share: NN"` and the rule reads `flex: var(--share)`, so the widths always sum to a true 100%.

## Variants

- **Single bar (default).** Headline plus one `.comp-bar` of segments plus a source line. The cleanest form: one focal segment gold, the rest muted navy, each segment labeled with its name and share. Use a `.foot-line` for the one-line takeaway.
- **Two bars (compare mix).** Add a second `.comp-row` below the first with its own `.comp-rail` label (e.g. "This year" vs "Last year", or two segments). The focal part stays gold in both bars so the eye tracks how that one share moved. Keep both bars to the same segment order so the stacks read as a comparison, not two separate charts.
- **Thin slivers.** When a focal segment is small, keep its in-bar label but let the share number ride; if it is too thin for text, move the label to a `.comp-callout` above the segment rather than cramming it inside.

## Paste-ready markup (two-bar compare; drop the second `.comp-row` for the default)

```html
<section class="slide" data-layout="composition" data-mood="paper">
  <div class="slide-pad">
    <header class="slide-head slide-head--assert">
      <h2>AI-assisted work is now a fifth of the close, up from a twentieth.</h2>
    </header>
    <div class="comp">
      <div class="comp-row" data-build="1">
        <span class="comp-rail">This close</span>
        <div class="comp-bar">
          <span class="comp-seg" style="--share: 42"><b>Manual entry</b><span class="comp-share">42%</span></span>
          <span class="comp-seg" style="--share: 30"><b>Review</b><span class="comp-share">30%</span></span>
          <span class="comp-seg comp-seg--focus" style="--share: 21"><b>AI-assisted</b><span class="comp-share">21%</span></span>
          <span class="comp-seg" style="--share: 7"><b>Other</b><span class="comp-share">7%</span></span>
        </div>
      </div>
      <div class="comp-row" data-build="1" style="--stagger: .12s">
        <span class="comp-rail">A year ago</span>
        <div class="comp-bar">
          <span class="comp-seg" style="--share: 55"><b>Manual entry</b><span class="comp-share">55%</span></span>
          <span class="comp-seg" style="--share: 33"><b>Review</b><span class="comp-share">33%</span></span>
          <span class="comp-seg comp-seg--focus" style="--share: 5"><b>AI-assisted</b><span class="comp-share">5%</span></span>
          <span class="comp-seg" style="--share: 7"><b>Other</b><span class="comp-share">7%</span></span>
        </div>
      </div>
      <p class="comp-source" data-build="1" style="--stagger: .24s">Illustrative: hours logged across the monthly close, two periods.</p>
      <p class="foot-line" data-build="2">The growing slice is where the next hour of capacity comes from.</p>
    </div>
  </div>
  <footer class="slide-chrome"><span>Demo</span><span><span class="num">07</span> / 13</span></footer>
  <aside class="notes"><span class="label">Speaker notes</span><p>Read the gold slice in both bars before anything else: AI-assisted work went from a twentieth of the close to a fifth in a year. The other parts shrank to make room. Then land the takeaway: that growing slice is where the next hour of capacity comes from.</p></aside>
</section>
```

## Animation

- **Build 1:** the bars, their labeled segments, and the source line cascade in on one press. The two `.comp-row`s carry the same `data-build="1"` with a small `--stagger` so the top bar fills, then the comparison bar, then the source, a single beat that says "here is the mix, and here it is a year ago". The bar rails and rounded track are part of the same fade, so nothing looks empty before the press.
- **Build 2:** the `.foot-line` takeaway fades in, the so-what beat where the speaker names why the gold slice matters.

The headline is visible from slide entry. For the single-bar default, drop the second `.comp-row` and the slide is the same two-build reveal (bar plus source, then takeaway). In scroll mode every build is visible at once, as the global build rules already handle.
