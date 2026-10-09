# Element: Comparison table (Harvey balls / RAG scored grid)

A scored decision grid: **options are columns**, **criteria are rows**, and every cell holds a score, either a **Harvey ball** (five fill levels: empty, quarter, half, three-quarter, full) for judgment ratings on a shared scale, or a **RAG dot** (red, amber, green) for pass/threshold criteria. A legend names the scale. One option is the recommendation: its whole column is emphasized in gold with a "Recommended" tag, while every other column stays quiet navy, so the table does not just tabulate, it argues for the answer.

- **Slide type:** Comparison table (Compare & decide). See [`../slide-types/comparison-table.md`](../slide-types/comparison-table.md).
- **Use it for:** the option-selection beat in a recommendation, when there are three to four contenders scored on the same handful of criteria and you want the audience to reach your conclusion by reading the grid. Pairs naturally ahead of the recommendation summary.
- **Density:** B. **Layout:** `data-layout="comparison-table"`.
- **Don't:** stack accents. Gold rides only the recommended column and its tag; every other option is navy or gray. Don't overfill the grid: roughly four options by six criteria is the legible ceiling, one line per cell label. Don't invent precision: Harvey balls are deliberately five-step, not percentages. Always print the legend, and cite the scale or a named benchmark (e.g. APQC) when the scores lean on one. No prices in any cell.

## CSS / asset dependencies

- Styles: the `.ct-*` rules in `deck-kit/slides.css`. Self-contained; no sprite needed. The Harvey ball is a navy ring with a `conic-gradient` fill clipped to a circle (precise five-step fills, scales with the uniform slide scale, no chartjunk). The RAG dot reuses `--green`, `--gold-foil` (amber), and `--red`.
- Pairs with the standard `.slide-head--assert` header and an optional `.foot-line` for the one-line takeaway.
- No icons required.

## Variants

- **Harvey balls (default).** Each score cell is `<span class="ct-ball ct-b3">` where `ct-b0` through `ct-b4` set empty, quarter, half, three-quarter, full. Use for judgment ratings on a shared 0 to 4 scale (fit, effort, risk-as-rated).
- **RAG cells.** Swap the ball for `<span class="ct-rag ct-g">` (green), `ct-a` (amber), or `ct-r` (red), plus a short word so the cell is not color-only (accessibility). Use when each criterion is a clean pass / caution / fail rather than a gradient.
- **Mixed.** A grid may run Harvey-ball rows and RAG rows together: rate the gradient criteria with balls and the threshold criteria (e.g. "Meets compliance") with RAG dots. The legend then shows both keys.

## Paste-ready markup (Harvey balls; recommended column = the third option)

```html
<section class="slide" data-layout="comparison-table" data-mood="paper">
  <div class="slide-pad">
    <header class="slide-head slide-head--assert">
      <h2>The mid-tier suite scores highest where the work actually lands.</h2>
    </header>

    <div class="ct">
      <table class="ct-grid">
        <thead>
          <tr>
            <th class="ct-corner" scope="col">Criterion</th>
            <th class="ct-opt" scope="col">Build in-house</th>
            <th class="ct-opt" scope="col">Enterprise platform</th>
            <th class="ct-opt ct-rec" scope="col">
              <span class="ct-rec-tag">Recommended</span>
              Mid-tier suite
            </th>
          </tr>
        </thead>
        <tbody>
          <tr class="ct-row" data-build="2" style="--stagger: 0s">
            <th class="ct-crit" scope="row">Fit to our workflows</th>
            <td><span class="ct-ball ct-b3" role="img" aria-label="three-quarter"></span></td>
            <td><span class="ct-ball ct-b2" role="img" aria-label="half"></span></td>
            <td class="ct-rec"><span class="ct-ball ct-b4" role="img" aria-label="full"></span></td>
          </tr>
          <tr class="ct-row" data-build="2" style="--stagger: 0.09s">
            <th class="ct-crit" scope="row">Time to first value</th>
            <td><span class="ct-ball ct-b1" role="img" aria-label="quarter"></span></td>
            <td><span class="ct-ball ct-b2" role="img" aria-label="half"></span></td>
            <td class="ct-rec"><span class="ct-ball ct-b4" role="img" aria-label="full"></span></td>
          </tr>
          <tr class="ct-row" data-build="2" style="--stagger: 0.18s">
            <th class="ct-crit" scope="row">Total effort to run</th>
            <td><span class="ct-ball ct-b0" role="img" aria-label="empty"></span></td>
            <td><span class="ct-ball ct-b3" role="img" aria-label="three-quarter"></span></td>
            <td class="ct-rec"><span class="ct-ball ct-b3" role="img" aria-label="three-quarter"></span></td>
          </tr>
          <tr class="ct-row" data-build="2" style="--stagger: 0.27s">
            <th class="ct-crit" scope="row">Meets compliance</th>
            <td><span class="ct-rag ct-a">Caution</span></td>
            <td><span class="ct-rag ct-g">Meets</span></td>
            <td class="ct-rec"><span class="ct-rag ct-g">Meets</span></td>
          </tr>
          <tr class="ct-row" data-build="2" style="--stagger: 0.36s">
            <th class="ct-crit" scope="row">Vendor lock-in risk</th>
            <td><span class="ct-ball ct-b4" role="img" aria-label="full"></span></td>
            <td><span class="ct-ball ct-b1" role="img" aria-label="quarter"></span></td>
            <td class="ct-rec"><span class="ct-ball ct-b3" role="img" aria-label="three-quarter"></span></td>
          </tr>
        </tbody>
      </table>

      <div class="ct-legend" data-build="1">
        <span class="ct-legend-scale">
          <span class="ct-ball ct-b0"></span>
          <span class="ct-ball ct-b1"></span>
          <span class="ct-ball ct-b2"></span>
          <span class="ct-ball ct-b3"></span>
          <span class="ct-ball ct-b4"></span>
          <span class="ct-legend-cap">Weak to strong</span>
        </span>
        <span class="ct-legend-rag">
          <span class="ct-rag ct-g">Meets</span>
          <span class="ct-rag ct-a">Caution</span>
          <span class="ct-rag ct-r">Gap</span>
        </span>
        <span class="ct-legend-src">Scored against our intake criteria</span>
      </div>
    </div>
  </div>
  <footer class="slide-chrome"><span>Demo</span><span><span class="num">07</span> / 13</span></footer>
  <aside class="notes"><span class="label">Speaker notes</span><p>...</p></aside>
</section>
```

## Animation

- **Build 0 (slide entry):** the grid frame, the column headers (including the recommended option's name and its quiet tag), and the criteria row labels are all visible, so the slide reads as a real table from the start. The score cells are empty.
- **Build 1:** the legend fades in. Beat: "Here is the scale we used."
- **Build 2:** the score cells cascade in **row by row** on one press. Each row carries `data-build="2"` and an inline `--stagger` stepping ~0.09s, so the scores fill top to bottom in well under a second. Beat: "Here is how each option scored, criterion by criterion." (The cells fade via their own opacity transition keyed to `--stagger`, activated when the row gets `.in`, since the global build stagger only applies to the build element itself.)
- **Build 3:** the recommended column lights gold: the `.ct-rec` cells gain their gold wash and the "Recommended" tag goes solid gold. Beat: the conclusion the scores point to. Implemented by the slide-level `[data-layout].build-3` hook (presenter adds a build-count class), so no extra DOM is needed.

Three presses total. Honors `prefers-reduced-motion` via the global `[data-build]` rule and a `transition: none` on the ball fills; in scroll view all builds show at once and the recommended column is highlighted from the start.
