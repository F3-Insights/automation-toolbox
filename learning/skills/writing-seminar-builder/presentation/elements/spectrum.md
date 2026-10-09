# Element: Spectrum / continuum (.spectrum)

A horizontal axis bar that replaces a false binary with a graded range. Two labeled poles anchor the ends, a faint navy-to-gold gradient runs the length, and 2 to 4 named positions sit at their real points along the bar. An optional gold "you are here" marker lands the personal read. The bar and poles are quiet navy structure; the single gold accent rides the you-are-here marker (or, if there is no you-are-here, the one focal position), so the eye reads the placement itself.

- **Slide type:** Spectrum / continuum (Explain). See [`../slide-types/_INDEX.md`](../slide-types/_INDEX.md).
- **Use it for:** any beat where the audience is stuck in an either/or that is really a continuum (manual to autonomous, narrow to general, cautious to aggressive) and you want to place concrete positions and locate the audience.
- **Density:** V. **Layout:** `data-layout="spectrum"` (the cap floats the body to the optical center so the bar clears the footer chrome at ~673).
- **Don't:** crowd more than four positions onto one bar, or stack a second gold accent. The poles stay navy; gold is the you-are-here read alone.

## CSS / asset dependencies

- Styles: `.spectrum*` rules in `deck-kit/slides.css` (plus the `[data-layout="spectrum"] .spectrum` cap for vertical balance).
- No icons required. The you-are-here arrow and the takeaway use the gold CSS data-URI / `.foot-line` conventions already in the kit.
- Positions are placed by an inline `left:` percentage on each `.spectrum-mark` and each pole sits at the 0% / 100% ends. Markers alternate above / below the bar via `.spectrum-mark--up` / `.spectrum-mark--down` so labels never collide.

## Variants

- **2 to 4 positions.** Set `data-count` on `.spectrum` only if you want the kit to validate; placement is driven by each mark's inline `left:` percentage, so any count reads correctly. Alternate `--up` / `--down` for breathing room.
- **You-are-here vs focal position.** Default: a gold `.spectrum-here` marker pinned at an inline `left:`, fading in on build 2. If there is no audience read, drop `.spectrum-here` and give the one focal `.spectrum-mark` the `.spectrum-mark--focus` class instead (it then carries the single gold accent).
- **Takeaway line.** The closing `.foot-line` (existing primitive) states the reframe ("it is a dial, not a switch") and rides build 2 with the you-are-here.

## Paste-ready markup

```html
<section class="slide" data-layout="spectrum" data-mood="cool">
  <div class="slide-pad">
    <header class="slide-head slide-head--assert">
      <h2>Autonomy is a dial you turn up, not a switch you flip.</h2>
    </header>
    <div class="spectrum">
      <!-- the bar + poles: visible from entry (the frame) -->
      <div class="spectrum-track">
        <div class="spectrum-bar"></div>
        <span class="spectrum-pole spectrum-pole--lo">
          <span class="spectrum-pole-lbl">Human does it all</span>
          <span class="spectrum-pole-sub">Manual, every step</span>
        </span>
        <span class="spectrum-pole spectrum-pole--hi">
          <span class="spectrum-pole-lbl">AI runs unattended</span>
          <span class="spectrum-pole-sub">Fully autonomous</span>
        </span>

        <!-- 2 to 4 named positions: cascade on ONE press (build 1) -->
        <div class="spectrum-mark spectrum-mark--up" data-build="1" style="--stagger:0s; left:24%">
          <span class="spectrum-mark-name">Assist</span>
          <span class="spectrum-mark-desc">AI drafts, a person decides</span>
        </div>
        <div class="spectrum-mark spectrum-mark--down" data-build="1" style="--stagger:.12s; left:50%">
          <span class="spectrum-mark-name">Review</span>
          <span class="spectrum-mark-desc">AI acts, a person approves</span>
        </div>
        <div class="spectrum-mark spectrum-mark--up" data-build="1" style="--stagger:.24s; left:76%">
          <span class="spectrum-mark-name">Supervise</span>
          <span class="spectrum-mark-desc">AI runs, a person spot-checks</span>
        </div>

        <!-- you-are-here: the one gold accent, lands on build 2 -->
        <div class="spectrum-here" data-build="2" style="left:22%">
          <span class="spectrum-here-lbl">Most teams start here</span>
        </div>
      </div>
    </div>
    <p class="foot-line" data-build="2">Pick the notch that fits the risk, then turn it up as trust grows.</p>
  </div>
  <footer class="slide-chrome"><span>Demo</span><span><span class="num">06</span> / 13</span></footer>
  <aside class="notes"><span class="label">Speaker notes</span><p>…</p></aside>
</section>
```

## Animation

- **Entry (build 0):** the bar, the gradient, and both poles are visible. The frame never looks empty.
- **Build 1:** the 2 to 4 named positions cascade in left to right on ONE press via their inline `--stagger`. Each `.spectrum-mark` carries `opacity:0` and a transition keyed to `var(--stagger)` that activates when it gets `.in` (it is a build element, so the global hook fires), drawing the tick down to the bar and fading the label.
- **Build 2:** the gold `.spectrum-here` marker rises into place and the takeaway `.foot-line` fades in together, one press, landing the personal read and the reframe.
