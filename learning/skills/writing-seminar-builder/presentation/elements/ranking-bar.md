# Element: Ranking (bar)

A sorted horizontal bar chart that ranks a handful of discrete items by one magnitude, descending, so the eye reads the order at a glance. Every bar is quiet navy except the one the slide is about, which carries the single gold accent; value labels sit at the bar ends. The frame (row labels and empty tracks) is present from entry and the bars fill in on one press, top to bottom.

- **Slide type:** Ranking (bar) (Prove). See [`../slide-types/ranking-bar.md`](../slide-types/ranking-bar.md).
- **Use it for:** comparing four to seven named items on a single measure where the point is which is biggest, or where a cutoff line falls (departments by hours saved, use cases by adoption, processes by cycle time).
- **Density:** V. **Layout:** `data-layout="ranking"` (centers the chart block in the available height and keeps the source line clear of the footer chrome).
- **Don't:** leave the bars unsorted (the sort *is* the message), light more than one bar gold, add gridlines or a second axis, or print a magnitude without a named source. One gold accent: the focal bar.

## CSS / asset dependencies

- Styles: the `.rank*` rules in `css_additions` (appended to `deck-kit/slides.css`), plus the global `[data-build]` fade already in `slides.css`.
- Reuses existing primitives: `.slide-head--assert` for the takeaway headline, `.slide-chrome` footer, `.foot-line` for the closing takeaway, the build/`.in` cascade system.
- No icons required. No SVG. Bars are bespoke CSS (a track plus a width-scaled fill), matching the diagram-engine rule that bar charts are built in CSS, not Mermaid. Bar widths are set per row with an inline `--pct` custom property (the fill's flex-basis), so the geometry is data, not magic numbers.

## Variants

- **Leader-focal (default).** The top (longest) bar is gold; it is the item the slide is recommending or calling out. Put `rank-bar--focal` on that row.
- **Cutoff-focal.** The gold bar is not the top one but the item that sits at a decision threshold (the lowest that still clears the bar, the one you are choosing). Move `rank-bar--focal` to that row; the sort still runs by magnitude, so gold can land anywhere in the stack.
- **Unit suffix.** Wrap a trailing unit on the value label (`<span class="rank-unit">hrs/wk</span>`) so the unit reads quieter than the digits. State the unit once in the headline or axis caption and you can drop it from the labels entirely.

## Paste-ready markup (leader-focal; swap `--focal` per the variants)

```html
<section class="slide" data-layout="ranking" data-mood="paper">
  <div class="slide-pad">
    <header class="slide-head slide-head--assert">
      <h2>Finance leads the hours AI gives back each week.</h2>
    </header>
    <div class="rank">
      <ol class="rank-bars" data-build="1">
        <li class="rank-row rank-bar--focal" style="--pct: 100%; --stagger: 0s">
          <span class="rank-label">Finance &amp; accounting</span>
          <span class="rank-track"><span class="rank-fill"></span></span>
          <span class="rank-value">9.4 <span class="rank-unit">hrs/wk</span></span>
        </li>
        <li class="rank-row" style="--pct: 81%; --stagger: .1s">
          <span class="rank-label">Customer support</span>
          <span class="rank-track"><span class="rank-fill"></span></span>
          <span class="rank-value">7.6 <span class="rank-unit">hrs/wk</span></span>
        </li>
        <li class="rank-row" style="--pct: 64%; --stagger: .2s">
          <span class="rank-label">Sales &amp; marketing</span>
          <span class="rank-track"><span class="rank-fill"></span></span>
          <span class="rank-value">6.0 <span class="rank-unit">hrs/wk</span></span>
        </li>
        <li class="rank-row" style="--pct: 45%; --stagger: .3s">
          <span class="rank-label">Operations</span>
          <span class="rank-track"><span class="rank-fill"></span></span>
          <span class="rank-value">4.2 <span class="rank-unit">hrs/wk</span></span>
        </li>
        <li class="rank-row" style="--pct: 30%; --stagger: .4s">
          <span class="rank-label">HR &amp; recruiting</span>
          <span class="rank-track"><span class="rank-fill"></span></span>
          <span class="rank-value">2.8 <span class="rank-unit">hrs/wk</span></span>
        </li>
      </ol>
      <p class="rank-source" data-build="1">Illustrative figures, per-employee weekly hours saved.</p>
      <p class="foot-line" data-build="2">Start where the hours are: finance is the fastest payback.</p>
    </div>
  </div>
  <footer class="slide-chrome"><span>Demo</span><span><span class="num">07</span> / 13</span></footer>
  <aside class="notes"><span class="label">Speaker notes</span><p>Read the order first, then the leader.</p></aside>
</section>
```

## Animation

- **Build 1:** the bars cascade in top to bottom on one press. The tracks and row labels are present from slide entry (the frame never looks empty); the fills scale from zero width and the value labels fade in, each row stepped by its own `--stagger` so the chart "draws" downward. The source line rides in on the same build. This is the beat where the speaker walks the ranking.
- **Build 2:** the focal bar resolves from quiet navy to gold and the `.foot-line` takeaway appears, the so-what beat that names why the focal item matters.

The fill and value-label cascade is keyed to `var(--stagger)` and activated when the parent `.rank-bars` gets `.in` (the global `[data-build]` `--stagger` hook only applies to build elements, so the rows carry their own per-child transition here). In scroll mode every build is visible at once and the bars render filled, as the global build rules already handle.
