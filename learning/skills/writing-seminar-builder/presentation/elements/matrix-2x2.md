# Element: 2×2 matrix (matrix-2x2)

A square plot with two mono-labeled axes running low to high, four named quadrants, a handful of options plotted as small labeled dots, and the recommended quadrant subtly emphasized in gold. It makes a two-variable trade-off legible at a glance and points at where to start, without a single chartjunk gridline.

- **Slide type:** 2×2 matrix (Compare & decide). See [`../slide-types/_INDEX.md`](../slide-types/_INDEX.md).
- **Use it for:** positioning candidate options on two decision variables (effort vs payoff, risk vs reward, reach vs readiness) when a flat ranking would hide the trade-off, and you want to recommend one quadrant.
- **Density:** V. **Layout:** `data-layout="matrix"`.
- **Don't:** plot more than five or six items (labels collide); stack accents (the gold quadrant **and** its one focal dot are the single accent, every other dot stays quiet navy); invert an axis so "good" is not up-and-right.

## CSS / asset dependencies

- Styles: the `.m2*` rules added to `deck-kit/slides.css`. No icons, no SVG: the axes, quadrants and dots are pure CSS, so the figure scales with the uniform slide scale and never distorts.
- Reuses existing primitives: `.slide-head--assert` (assertion headline), `.foot-line` (the gold serif takeaway), `.slide-chrome`, and the `[data-build]` / `--stagger` cascade hook from DESIGN-PRINCIPLES §6.6.
- Brand tokens only: `--paper`, `--line`, `--line-soft`, `--navy`, `--muted`, `--ink`, `--gold`, `--mono`, `--sans`.

## Variants

- **Axis names.** Swap the two `.m2-axis-name` strings and the four `.m2-quad-lbl` strings to re-theme the grid for any trade-off. Keep both axes running **low to high** so the winning corner stays top-right.
- **Winning quadrant.** `m2-quad--win` carries the gold wash + outline. Move it to a different quadrant by putting the class (and `data-build="2"`) on that cell instead. It is almost always top-right (high payoff, low effort), but a risk/reward read may win in a different corner.
- **Focal item.** One plotted dot gets `m2-dot--focus` (gold) to name the single first move; it should sit inside the winning quadrant. All other dots stay navy.
- **Label side.** A dot whose label would run off the right edge gets `m2-dot--left` to flip the label to the left of the dot. Reorder the inner `.lbl` / `.dot` spans to match (label first for left-flipped).

## Paste-ready markup (focus = top-right "quick wins"; retheme per Variants)

```html
<section class="slide" data-layout="matrix" data-mood="paper">
  <div class="slide-pad">
    <header class="slide-head slide-head--assert">
      <h2>Start where effort is low and payoff is high.</h2>
    </header>
    <div class="m2">
      <div class="m2-grid">
        <div class="m2-quad m2-quad--tl"><span class="m2-quad-lbl">Big bets</span></div>
        <div class="m2-quad m2-quad--tr m2-quad--win" data-build="2"><span class="m2-quad-lbl">Quick wins</span></div>
        <div class="m2-quad m2-quad--bl"><span class="m2-quad-lbl">Park for now</span></div>
        <div class="m2-quad m2-quad--br"><span class="m2-quad-lbl">Fill-ins</span></div>
      </div>
      <div class="m2-axis-x"></div>
      <div class="m2-axis-y"></div>
      <span class="m2-axlbl m2-x-lo">Low</span>
      <span class="m2-axlbl m2-x-hi">High</span>
      <span class="m2-axis-name m2-x-name">Implementation effort</span>
      <span class="m2-axlbl m2-y-lo">Low</span>
      <span class="m2-axlbl m2-y-hi">High</span>
      <span class="m2-axis-name m2-y-name">Business payoff</span>

      <!-- one press: the dots cascade in left-to-right via per-child --stagger -->
      <div class="m2-plot" data-build="1">
        <span class="m2-dot m2-dot--focus" style="left:74%; top:22%; --stagger:0s"><span class="m2-pt"></span><span class="m2-ptlbl">Invoice triage</span></span>
        <span class="m2-dot" style="left:80%; top:40%; --stagger:.1s"><span class="m2-pt"></span><span class="m2-ptlbl">Support drafts</span></span>
        <span class="m2-dot m2-dot--left" style="left:24%; top:28%; --stagger:.2s"><span class="m2-ptlbl">Demand forecast</span><span class="m2-pt"></span></span>
        <span class="m2-dot" style="left:30%; top:74%; --stagger:.3s"><span class="m2-pt"></span><span class="m2-ptlbl">Custom model</span></span>
        <span class="m2-dot m2-dot--left" style="left:72%; top:78%; --stagger:.4s"><span class="m2-ptlbl">Meeting notes</span><span class="m2-pt"></span></span>
      </div>
    </div>
    <p class="foot-line" data-build="2">Pilot the top-right first: invoice triage pays back fastest.</p>
  </div>
  <footer class="slide-chrome"><span>Section name</span><span><span class="num">07</span> / 13</span></footer>
  <aside class="notes"><span class="label">Speaker notes</span><p>...</p></aside>
</section>
```

Plotting note: a dot's `left`/`top` are percentages of the square, measured from the top-left, so a high-payoff/low-effort item sits low `left`-to-mid and low `top`. Top-right (the win) is high `left`, low `top`.

## Animation

- **Entry:** the axes, the four quadrant labels, and both axis names are visible from slide entry (DESIGN-PRINCIPLES §6.3, frames never fade). The grid reads as an empty, labeled board.
- **Build 1:** the plotted dots cascade in left-to-right on **one** press. Each `.m2-dot` carries its own `opacity:0` + `transition ... var(--stagger)` that activates when the parent `.m2-plot` gets `.in` (the same real-cascade pattern as `.am-link`, not the global build hook, which only fires on `[data-build]` elements).
- **Build 2:** the winning quadrant's gold wash + outline fade in and the `.foot-line` takeaway lands. Two beats total: plot the field, then name the move.
- Honors `prefers-reduced-motion` (transitions off, end-state intact) and renders fully in `body.mode-scroll` (all dots + win visible).
