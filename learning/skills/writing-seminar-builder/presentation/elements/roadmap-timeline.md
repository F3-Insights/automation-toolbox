# Element: Roadmap timeline

A phased roadmap. Two to four workstream rows laid across a shared time axis (30/60/90, or Q1 to Q4), each with a duration bar spanning the periods it covers, milestone diamonds marking proof points, and faint phase bands behind the columns. One mono time header sits above the rows. The single gold bar marks the focal workstream; every other bar stays quiet navy, so the eye lands on the track the talk is about.

- **Slide type:** Roadmap / phased timeline (Demonstrate). See [`../slide-types/_INDEX.md`](../slide-types/_INDEX.md).
- **Use it for:** a sequenced plan where several workstreams run in parallel and the value is the overlap and milestone cadence (a 30/60/90 adoption plan, a quarter-by-quarter rollout, a phased capability build).
- **Don't:** use it for a single chain of stages with decision gates. That is a process flow (`.lifecycle`). A roadmap shows parallel tracks across time, not one hand-off sequence.
- **Density:** V. Keep it to 2 to 4 rows: more and the bars compress past readability. Illustrative durations only; if a figure is a real benchmark, cite the source on the bar or in the foot-line.

## CSS / asset dependencies

- Styles: the `.rtl*` rules in `css_additions` (namespaced to this element).
- Reuses existing primitives: `.slide-head--assert` (assertion headline), `.foot-line` (the italic gold close), `.callout-strip` is available if a strategic-shift line is wanted instead.
- Borrows two conventions, does not redefine them: the **gold CSS-arrow / diamond data-URI** convention from `.sf-arrow` / `.lifecycle .stage::after`, and the **per-child stagger** idiom from `.am-links` (children carry their own `opacity:0` + transition keyed to `var(--stagger)`, activated when the parent build element gets `.in`).
- The time axis is a CSS grid: a label column plus N equal period columns. Bars span periods with `grid-column: <start> / span <n>`; diamonds are positioned with `grid-column` and centered on a period boundary.

## Variants

- **Time axis:** 30/60/90 (three periods), or Q1 to Q4 (four). Set `--rtl-cols` to the number of period columns and write that many `<span>`s in the header and that many `.rtl-band` cells.
- **Focal track:** put `rtl-track--focus` on the one workstream the slide is about. Its bar fills gold; the rest stay muted navy. One gold per slide.
- **Milestone weight:** a `.rtl-ms` diamond is muted by default; add `.rtl-ms--focus` to gold-mark the single milestone that is the payoff (typically on the focal track).
- **Bands:** `.rtl-band` cells are faint by default; the current/active phase can take `.rtl-band--lit` for a slightly warmer wash.

## Paste-ready markup (3-period 30/60/90; focal = the middle track)

```html
<div class="rtl" style="--rtl-cols: 3">
  <!-- time header (visible from entry) -->
  <div class="rtl-head">
    <span class="rtl-corner"></span>
    <span>First 30 days</span>
    <span>Day 31 to 60</span>
    <span>Day 61 to 90</span>
  </div>
  <!-- phase bands (visible from entry, behind the rows) -->
  <div class="rtl-bands" aria-hidden="true">
    <span class="rtl-corner"></span>
    <span class="rtl-band"></span>
    <span class="rtl-band rtl-band--lit"></span>
    <span class="rtl-band"></span>
  </div>
  <!-- workstream rows -->
  <div class="rtl-rows" data-build="1">
    <div class="rtl-track">
      <span class="rtl-label">Foundations</span>
      <span class="rtl-bar" style="grid-column: 2 / span 1; --stagger: 0s">Access &amp; guardrails</span>
    </div>
    <div class="rtl-track rtl-track--focus">
      <span class="rtl-label">Pilot pod</span>
      <span class="rtl-bar" style="grid-column: 2 / span 2; --stagger: .1s">Live use on one workflow</span>
    </div>
    <div class="rtl-track">
      <span class="rtl-label">Scale-out</span>
      <span class="rtl-bar" style="grid-column: 3 / span 2; --stagger: .2s">Second team onboards</span>
    </div>
  </div>
  <!-- milestone diamonds (own build) -->
  <div class="rtl-miles" data-build="2" aria-hidden="true">
    <span class="rtl-corner"></span>
    <span class="rtl-ms" style="grid-column: 2; --stagger: 0s"><b>Charter signed</b></span>
    <span class="rtl-ms rtl-ms--focus" style="grid-column: 3; --stagger: .12s"><b>First win shipped</b></span>
    <span class="rtl-ms" style="grid-column: 4; --stagger: .24s"><b>Go / no-go review</b></span>
  </div>
</div>
<p class="foot-line" data-build="2">Ninety days to a proven workflow, not a finished platform.</p>
```

The diamond label sits in HTML text above the diamond glyph (the glyph is a rotated `::before` square), so no SVG text distorts under the slide scale. Diamonds anchor on a **grid-line**: `grid-column: 2` places a diamond on the boundary at the start of period 1, `grid-column: 4` on the right edge of the last period. Match the milestone to the bar event it marks.

## Animation

- **Build 0 (entry):** the mono time header, the row labels, and the faint phase bands are all visible. The frame never looks empty; only the data fades in.
- **Build 1:** the duration bars cascade left to right. Each `.rtl-bar` carries its own `opacity:0` + transition keyed to `var(--stagger)`, activated when `.rtl-rows` gets `.in` (the global `[data-build]` stagger only fires on build elements, so the bars carry their own, per the `.am-links` convention).
- **Build 2:** the milestone diamonds pop in (same per-child stagger), and the `.foot-line` close fades with them.

Honor `prefers-reduced-motion`: the end-state renders correctly, motion is instant.
