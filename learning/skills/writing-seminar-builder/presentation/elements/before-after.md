# Element: Before / after (mirrored two-column delta)

Two mirrored columns with an IDENTICAL row structure so only the differences pop. The left column is **Today** (quiet navy header, status quo stated neutrally); the right column is **With <the change>** (the single gold accent, the same rows transformed). A shared label runs down the center spine, one row label per pair, so the eye reads across each row. Each row may carry an optional **metric-delta chip** ("3 days to 40 min") that makes the lift concrete. A serif punch line lands the takeaway last.

- **Slide type:** Before / after (Compare & decide). See [`../slide-types/before-after.md`](../slide-types/before-after.md).
- **Use it for:** making the value of a change vivid once the mechanism is understood, just ahead of the recommendation. The status quo and the future are the *same things* changed, row by row.
- **Density:** B. **Layout:** `data-layout="before-after"`.
- **Don't:** grade the status quo. "Today" describes, it never blames (house voice: positive and additive). Keep one accent: gold lives only in the with-change column and the punch line. Keep each cell to one line so the rows stay mirrored; if a cell wraps, shorten it, do not widen one side.

## CSS / asset dependencies

- Styles: the `.before-after*` rules in `deck-kit/slides.css`.
- No icons required. The metric-delta chip uses a gold CSS-background arrow data-URI in the same style as `.sf-arrow` / `.anat-arrow` (2.5px gold line, forward direction), so it needs no sprite.
- Pairs with the standard `.slide-head--assert` header and `.foot-line` if a one-line summary is wanted instead of the built-in punch.

## Variants

- **With metric deltas (default).** Each row carries a `.ba-delta` chip on the with-change side: `<from> <arrow> <to>`. Best when the change is measurable.
- **Qualitative (no chips).** Omit `.ba-delta`; the row text alone carries the contrast. Use when the lift is real but not a clean number.
- **Punch line vs. foot-line.** The built-in `.ba-punch` is the serif takeaway on build 3. If the deck standard is `.foot-line`, drop `.ba-punch` and add a `.foot-line` with `data-build="3"` instead.

## Paste-ready markup

```html
<section class="slide" data-layout="before-after" data-mood="paper">
  <div class="slide-pad">
    <header class="slide-head slide-head--assert">
      <h2>One shared inbox turns a three-day quote into a same-hour reply.</h2>
    </header>
    <div class="before-after">
      <!-- shared header row: spine label is empty, the two state headers sit either side -->
      <div class="ba-headrow">
        <span class="ba-spine-lbl"></span>
        <span class="ba-head ba-head--today">Today</span>
        <span class="ba-head ba-head--with">With a shared intake assistant</span>
      </div>

      <!-- TODAY column fills on build 1; WITH column on build 2; rows share one spine label -->
      <div class="ba-row" data-build="1" style="--stagger: 0s">
        <span class="ba-spine">First response</span>
        <span class="ba-cell ba-cell--today">Customer email waits in one rep's inbox</span>
        <span class="ba-cell ba-cell--with" data-build="2" style="--stagger: 0s">
          Acknowledged and routed the same hour
          <span class="ba-delta">3 days <i class="ba-arr"></i> 1 hr</span>
        </span>
      </div>

      <div class="ba-row" data-build="1" style="--stagger: 0.1s">
        <span class="ba-spine">Quote prep</span>
        <span class="ba-cell ba-cell--today">Rep retypes specs from the thread by hand</span>
        <span class="ba-cell ba-cell--with" data-build="2" style="--stagger: 0.1s">
          Draft quote assembled from the thread, rep reviews
          <span class="ba-delta">45 min <i class="ba-arr"></i> 5 min</span>
        </span>
      </div>

      <div class="ba-row" data-build="1" style="--stagger: 0.2s">
        <span class="ba-spine">Follow-up</span>
        <span class="ba-cell ba-cell--today">Remembered, or it slips</span>
        <span class="ba-cell ba-cell--with" data-build="2" style="--stagger: 0.2s">
          Scheduled and tracked against every open quote
          <span class="ba-delta">ad hoc <i class="ba-arr"></i> tracked</span>
        </span>
      </div>

      <div class="ba-row" data-build="1" style="--stagger: 0.3s">
        <span class="ba-spine">Where reps spend the day</span>
        <span class="ba-cell ba-cell--today">Triage and retyping</span>
        <span class="ba-cell ba-cell--with" data-build="2" style="--stagger: 0.3s">
          The deals that actually need judgment
          <span class="ba-delta">admin <i class="ba-arr"></i> selling</span>
        </span>
      </div>
    </div>

    <p class="ba-punch" data-build="3">Same team, same systems. The wait is what changes.</p>
  </div>
  <footer class="slide-chrome"><span>Demo</span><span><span class="num">07</span> / 13</span></footer>
  <aside class="notes"><span class="label">Speaker notes</span><p>...</p></aside>
</section>
```

## Animation

- **Build 0 (slide entry):** the frame is visible. The header, the head row ("Today" / "With ..."), the spine labels, and the Today cells' container are all present so the slide never looks empty. (The Today cells themselves fade in on build 1.)
- **Build 1:** the four **Today** cells cascade in left-spine-to-bottom on one press, `--stagger` stepping ~0.1s per row. Beat: "Here is how this runs today."
- **Build 2:** the four **With** cells (and their metric-delta chips) cascade in on one press, matched row-for-row to the same `--stagger` so each lands beside its Today twin. Beat: "With one change, the same rows look like this."
- **Build 3:** the serif punch line fades in. Beat: the takeaway.

Three presses total. The two columns are peers within their own set so each cascades on a single press; the punch line is a distinct beat and takes the next build. Honors `prefers-reduced-motion` via the global `[data-build]` rule; in scroll view all builds show at once.
