# Element: Executive summary (SCR / pyramid stack)

The whole argument on one page, answer-first. A governing-thought line sits at the top in a navy block (the recommendation, stated as the conclusion the deck proves), and three to five bold-lead supporting points cascade beneath it, each one summarizing a branch of the argument. One optional small figure anchors the governing thought so the headline claim has a number behind it. Reading only the top line tells a hurried executive the answer; reading the supports tells them why. Built to stand alone if the slide is forwarded without the speaker.

- **Slide type:** Executive summary (SCR) (Recommend & close). See [`../slide-types/executive-summary.md`](../slide-types/executive-summary.md).
- **Use it for:** the answer-first opener of a recommendation deck, or the closing consolidation just before next-steps. A senior audience that wants the conclusion, then the support, fast.
- **Density:** T. **Layout:** `data-layout="executive-summary"`.
- **Don't:** let the supports overlap or leave gaps (they must be MECE), bury the recommendation below the supports (it leads, pyramid-style), stack more than one figure, or frame the governing thought as a fix for what the audience does wrong. State the recommendation as a forward move (house voice: positive and additive). Keep each support lead to a short bold phrase and its clause to one or two lines so the page reads in a single pass.

## CSS / asset dependencies

- Styles: the `.exsum*` rules added to `deck-kit/slides.css` (the `[data-layout="executive-summary"]` block centers the stack in the available height and caps it above the footer chrome).
- Reuses brand tokens only: `--navy`, `--gold`, `--gold-foil`, `--paper`, `--line`, `--line-soft`, `--muted`, `--obsidian`, `--ink`, `--white`, `--serif`, `--grotesk`, `--mono`, `--sans`.
- No icons or sprite required. The optional figure is plain type in the oversized-numeral register shared with big-number and relevance-hook.
- Pairs with the `.slide-head--assert` header (this is a close / meat slide, so the headline is an assertion, one line). The governing-thought block borrows the navy definitional treatment of `.call-def`; do not redefine those classes.

## Variants

- **With anchor figure (default).** The governing-thought block carries a small `.exsum-figure` on its right (one numeral plus a one-line label) so the recommendation has a number behind it. Best when one figure summarizes the case.
- **No figure.** Drop `.exsum-figure` and let `.exsum-thought` fill the block. Use when the argument is qualitative and a single number would mislead.
- **Three to five supports.** Three supports read cleanest; five is the ceiling before the page gets dense. The grid is a single column, so supports simply stack; tighten `gap` only if five rows crowd the footer.
- **Bold-lead split.** Each support is a bold lead phrase (`.exsum-lead`, the one-glance scan line) plus a supporting clause (`.exsum-detail`). Keep the lead to a few words so the column of leads reads as the argument on its own.

## Paste-ready markup

```html
<section class="slide" data-layout="executive-summary" data-mood="paper">
  <div class="slide-pad">
    <header class="slide-head slide-head--assert">
      <h2>Stand up a governed AI back office in two quarters.</h2>
    </header>
    <div class="exsum">
      <!-- governing thought: the recommendation, stated as the conclusion -->
      <div class="exsum-govern">
        <div class="exsum-thought" data-build="1">
          <span class="exsum-govern-tag">Recommendation</span>
          <p>Run a 90-day pilot on invoice intake, then extend the same governed
            pattern across finance operations, so the team spends its hours on
            judgment, not keying.</p>
        </div>
        <div class="exsum-figure" data-build="1">
          <p class="exsum-figure-num">2,400</p>
          <p class="exsum-figure-label">finance hours a year freed at full rollout</p>
        </div>
      </div>

      <!-- supports cascade on ONE press; each is a non-build child keyed to
           the parent .exsum-supports.in, stepped by --stagger -->
      <ul class="exsum-supports" data-build="2">
        <li class="exsum-support" style="--stagger: 0s">
          <span class="exsum-lead">The work is ready.</span>
          <span class="exsum-detail">Invoice intake is high-volume, rule-bound,
            and well documented, so it is the cleanest first surface to automate.</span>
        </li>
        <li class="exsum-support" style="--stagger: 0.1s">
          <span class="exsum-lead">The pattern repeats.</span>
          <span class="exsum-detail">The same intake, review, and post loop covers
            expenses, vendor onboarding, and order entry with minor changes.</span>
        </li>
        <li class="exsum-support" style="--stagger: 0.2s">
          <span class="exsum-lead">Control stays in house.</span>
          <span class="exsum-detail">Every action runs through a human review gate
            and an audit trail your controller already signs off on.</span>
        </li>
        <li class="exsum-support" style="--stagger: 0.3s">
          <span class="exsum-lead">The payback is near term.</span>
          <span class="exsum-detail">Freed hours cover the build inside the first
            year, before any second surface comes online.</span>
        </li>
      </ul>
    </div>
  </div>
  <footer class="slide-chrome"><span>Demo</span><span><span class="num">02</span> / 13</span></footer>
  <aside class="notes"><span class="label">Speaker notes</span><p>This is the answer slide. Lead with the recommendation out loud before you touch a support: stand up a governed AI back office in two quarters, starting with invoice intake. The figure is the one number that makes it real, twenty four hundred hours a year, so let it sit a beat. Then walk the four supports top to bottom. They are MECE on purpose: the work is ready, the pattern repeats, control stays in house, the payback is near term. Each one is a section of the deck behind this page, so a reader who only sees this slide still gets the whole case. Hold the detail and the war stories for the slides that follow.</p></aside>
</section>
```

## Animation

- **Build 0 (slide entry):** the frame is visible. The header and the empty navy governing block are present so the slide never looks empty. (The recommendation text and figure fade in on build 1.)
- **Build 1:** the governing thought and its anchor figure fade in together as one beat. One press. Beat: "Here is the recommendation," said before any support.
- **Build 2:** the three to five supports cascade in top-to-bottom on one press. They are peers in one set, so they share a single build and step via inline `--stagger` (~0.1s per row). The supports are NON-build children: each `<li>` starts at `opacity: 0` with a transition keyed to `var(--stagger)` that fires when the parent `.exsum-supports` gets `.in`, rather than relying on the global `[data-build]` stagger. Beat: "And here is why," walking the column.

Two presses total. Honors `prefers-reduced-motion` (the supports drop their transition and render in place); in scroll view all builds show at once via the `body.mode-scroll` rules.
