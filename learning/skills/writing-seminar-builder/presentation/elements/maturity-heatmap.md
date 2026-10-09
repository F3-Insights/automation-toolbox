# Element: Maturity heatmap

A capability and maturity matrix. Capability **items** run down the rows, maturity **dimensions** run across the columns, and every cell is a **Harvey ball** (a five-step fill from empty to full) that encodes the level. A legend keys the fills to named stages. One row reads as the focal "you are here" line in gold, so the grid doubles as a self-assessment mirror, the reader scans the whole pattern in one sweep and then finds themselves on it.

- **What it is:** an items x dimensions grid of graduated Harvey-ball cells with a stage legend and a single highlighted focal row. Reads at a glance, no number mining. **What it is not:** a numeric scorecard, a RAG status board, or a chart that argues one figure.
- **When to use:** the close of an AI-readiness or AI-maturity arc, when the audience must locate themselves across many capabilities at once. Fits an AI maturity seminar. See [`../slide-types/maturity-heatmap.md`](../slide-types/maturity-heatmap.md).
- **Density:** V. **Layout:** `data-layout="heatmap"` (the cap floats the matrix to optical center and keeps it above the footer chrome).
- **Don't:** light more than one row or column gold (one focal series per slide, DESIGN-PRINCIPLES section 1A and 5). Don't print a number in every cell, the ball *is* the rating. Don't add gridline chartjunk beyond the thin row rules.

## CSS / asset dependencies

- Styles: the `.mh*` rules added to `deck-kit/slides.css`, plus the `[data-layout="heatmap"]` cap that centers the matrix and floats the summary strip. Reuses `.callout-strip` for the navy "you are here" read-out and `.slide-head--assert` for the headline.
- Harvey balls are inline SVG (two circles plus a clipped half or full fill), so they scale with the uniform slide scale and never distort. No icon sprite needed.
- No external assets. All color via brand custom properties, navy for neutral fills, gold for the focal row only.

## Variants

- **Focal row vs focal column.** Default lights one **row** (`.mh-row--focus`), the "you are here" capability line. To spotlight a maturity **stage** instead, drop the row class and add `.mh-col--focus` to one header cell plus `data-focus-col` styling, the gold then marks the column most firms cluster in.
- **Harvey ball vs graduated tint.** Default is the five-step Harvey ball (`.mh-ball` with `data-level="0..4"`). For a denser read, swap to a graduated-tint swatch by adding `mh-cell--tint` and the same `data-level`, the cell background steps from `--paper` to a navy wash (gold wash on the focal row). Same data, same legend, pick by how many rows you show.
- **Row count.** Comfortable at 4 to 6 capability rows and 4 to 5 dimension columns. Past that, split into two slides rather than shrinking the balls.

## Paste-ready markup (focal row = "you are here"; five maturity stages)

```html
<section class="slide" data-layout="heatmap" data-mood="paper">
  <div class="slide-pad">
    <header class="slide-head slide-head--assert">
      <h2>Most mid-market firms sit at Developing, not Absent.</h2>
    </header>

    <div class="mh">
      <!-- Legend: keys the ball fills to named stages. Visible from entry. -->
      <div class="mh-legend" aria-hidden="true">
        <span class="mh-legend-item"><svg class="mh-ball" viewBox="0 0 22 22" data-level="0"><circle class="mh-ball-bg" cx="11" cy="11" r="9"/></svg>Absent</span>
        <span class="mh-legend-item"><svg class="mh-ball" viewBox="0 0 22 22" data-level="1"><circle class="mh-ball-bg" cx="11" cy="11" r="9"/><path class="mh-ball-fill" d="M11 2 A9 9 0 0 0 11 20 Z"/></svg>Ad hoc</span>
        <span class="mh-legend-item"><svg class="mh-ball" viewBox="0 0 22 22" data-level="2"><circle class="mh-ball-bg" cx="11" cy="11" r="9"/><path class="mh-ball-fill" d="M11 2 A9 9 0 0 0 11 20 Z"/></svg>Developing</span>
        <span class="mh-legend-item"><svg class="mh-ball" viewBox="0 0 22 22" data-level="3"><circle class="mh-ball-bg" cx="11" cy="11" r="9"/><path class="mh-ball-fill" d="M11 2 A9 9 0 0 0 11 20 Z"/></svg>Managed</span>
        <span class="mh-legend-item"><svg class="mh-ball" viewBox="0 0 22 22" data-level="4"><circle class="mh-ball-bg" cx="11" cy="11" r="9"/><path class="mh-ball-fill" d="M11 2 A9 9 0 0 0 11 20 Z"/></svg>Embedded</span>
      </div>

      <!-- Matrix: grid + labels are build 0 (visible from entry); cells cascade build 2 -->
      <div class="mh-grid">
        <!-- Header row: dimension labels -->
        <div class="mh-corner"></div>
        <div class="mh-colhead">Data</div>
        <div class="mh-colhead">Skills</div>
        <div class="mh-colhead">Governance</div>
        <div class="mh-colhead">Use cases</div>

        <!-- Row 1 -->
        <div class="mh-rowhead">Strategy</div>
        <div class="mh-cell" data-build="2" style="--stagger:0s"><svg class="mh-ball" viewBox="0 0 22 22" data-level="2"><circle class="mh-ball-bg" cx="11" cy="11" r="9"/><path class="mh-ball-fill" d="M11 2 A9 9 0 0 0 11 20 Z"/></svg></div>
        <div class="mh-cell" data-build="2" style="--stagger:0s"><svg class="mh-ball" viewBox="0 0 22 22" data-level="2"><circle class="mh-ball-bg" cx="11" cy="11" r="9"/><path class="mh-ball-fill" d="M11 2 A9 9 0 0 0 11 20 Z"/></svg></div>
        <div class="mh-cell" data-build="2" style="--stagger:0s"><svg class="mh-ball" viewBox="0 0 22 22" data-level="1"><circle class="mh-ball-bg" cx="11" cy="11" r="9"/><path class="mh-ball-fill" d="M11 2 A9 9 0 0 0 11 20 Z"/></svg></div>
        <div class="mh-cell" data-build="2" style="--stagger:0s"><svg class="mh-ball" viewBox="0 0 22 22" data-level="3"><circle class="mh-ball-bg" cx="11" cy="11" r="9"/><path class="mh-ball-fill" d="M11 2 A9 9 0 0 0 11 20 Z"/></svg></div>

        <!-- Row 2: FOCAL "you are here" -->
        <div class="mh-rowhead mh-rowhead--focus">Pilots <span class="mh-here">you are here</span></div>
        <div class="mh-cell mh-cell--focus" data-build="2" style="--stagger:.08s"><svg class="mh-ball" viewBox="0 0 22 22" data-level="2"><circle class="mh-ball-bg" cx="11" cy="11" r="9"/><path class="mh-ball-fill" d="M11 2 A9 9 0 0 0 11 20 Z"/></svg></div>
        <div class="mh-cell mh-cell--focus" data-build="2" style="--stagger:.08s"><svg class="mh-ball" viewBox="0 0 22 22" data-level="2"><circle class="mh-ball-bg" cx="11" cy="11" r="9"/><path class="mh-ball-fill" d="M11 2 A9 9 0 0 0 11 20 Z"/></svg></div>
        <div class="mh-cell mh-cell--focus" data-build="2" style="--stagger:.08s"><svg class="mh-ball" viewBox="0 0 22 22" data-level="1"><circle class="mh-ball-bg" cx="11" cy="11" r="9"/><path class="mh-ball-fill" d="M11 2 A9 9 0 0 0 11 20 Z"/></svg></div>
        <div class="mh-cell mh-cell--focus" data-build="2" style="--stagger:.08s"><svg class="mh-ball" viewBox="0 0 22 22" data-level="2"><circle class="mh-ball-bg" cx="11" cy="11" r="9"/><path class="mh-ball-fill" d="M11 2 A9 9 0 0 0 11 20 Z"/></svg></div>

        <!-- Row 3 -->
        <div class="mh-rowhead">Scaled delivery</div>
        <div class="mh-cell" data-build="2" style="--stagger:.16s"><svg class="mh-ball" viewBox="0 0 22 22" data-level="1"><circle class="mh-ball-bg" cx="11" cy="11" r="9"/><path class="mh-ball-fill" d="M11 2 A9 9 0 0 0 11 20 Z"/></svg></div>
        <div class="mh-cell" data-build="2" style="--stagger:.16s"><svg class="mh-ball" viewBox="0 0 22 22" data-level="1"><circle class="mh-ball-bg" cx="11" cy="11" r="9"/><path class="mh-ball-fill" d="M11 2 A9 9 0 0 0 11 20 Z"/></svg></div>
        <div class="mh-cell" data-build="2" style="--stagger:.16s"><svg class="mh-ball" viewBox="0 0 22 22" data-level="1"><circle class="mh-ball-bg" cx="11" cy="11" r="9"/><path class="mh-ball-fill" d="M11 2 A9 9 0 0 0 11 20 Z"/></svg></div>
        <div class="mh-cell" data-build="2" style="--stagger:.16s"><svg class="mh-ball" viewBox="0 0 22 22" data-level="2"><circle class="mh-ball-bg" cx="11" cy="11" r="9"/><path class="mh-ball-fill" d="M11 2 A9 9 0 0 0 11 20 Z"/></svg></div>

        <!-- Row 4 -->
        <div class="mh-rowhead">Risk and oversight</div>
        <div class="mh-cell" data-build="2" style="--stagger:.24s"><svg class="mh-ball" viewBox="0 0 22 22" data-level="1"><circle class="mh-ball-bg" cx="11" cy="11" r="9"/><path class="mh-ball-fill" d="M11 2 A9 9 0 0 0 11 20 Z"/></svg></div>
        <div class="mh-cell" data-build="2" style="--stagger:.24s"><svg class="mh-ball" viewBox="0 0 22 22" data-level="2"><circle class="mh-ball-bg" cx="11" cy="11" r="9"/><path class="mh-ball-fill" d="M11 2 A9 9 0 0 0 11 20 Z"/></svg></div>
        <div class="mh-cell" data-build="2" style="--stagger:.24s"><svg class="mh-ball" viewBox="0 0 22 22" data-level="1"><circle class="mh-ball-bg" cx="11" cy="11" r="9"/><path class="mh-ball-fill" d="M11 2 A9 9 0 0 0 11 20 Z"/></svg></div>
        <div class="mh-cell" data-build="2" style="--stagger:.24s"><svg class="mh-ball" viewBox="0 0 22 22" data-level="2"><circle class="mh-ball-bg" cx="11" cy="11" r="9"/><path class="mh-ball-fill" d="M11 2 A9 9 0 0 0 11 20 Z"/></svg></div>
      </div>

      <p class="mh-source">Stages and ratings illustrative.</p>
    </div>
  </div>
  <footer class="slide-chrome"><span>Demo</span><span><span class="num">07</span> / 13</span></footer>
  <aside class="notes"><span class="label">Speaker notes</span><p>...</p></aside>
</section>
```

## Animation

- **Build 0 (slide entry):** the legend, the grid frame, the column headers, and the row labels are all visible. The matrix scaffold reads immediately, it never looks empty (DESIGN-PRINCIPLES section 6.3).
- **Build 2:** every rated ball fades in, cascading row by row. All cells share `data-build="2"`; each row carries a larger `--stagger` (0s, .08s, .16s, .24s) so the fills sweep top to bottom on a **single** press, the speaker says "here is the pattern" once and the whole grid populates. The focal row's gold tint and the "you are here" tag ride in with their cells.

Note: builds skip from the entry state straight to 2 so the cell reveal maps to the single "now read the pattern" beat; there is no intermediate build 1. Reduced motion renders the populated grid instantly.
