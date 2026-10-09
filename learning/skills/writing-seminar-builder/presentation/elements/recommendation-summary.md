# Element: Recommendation summary

The "answer" opener of a recommendation close. Three to five recommendation groups stack down the slide, each one a numbered, verb-led headline ("Stand up...", "Consolidate...", "Sequence...") with one or two sub-points that make the move concrete and an optional impact tag naming the payoff. The set is MECE: each group is a distinct move, and together they cover the recommendation. The governing thought lands last as a gold italic foot-line, so the audience reads the answer first, then the one sentence that ties it together.

- **Slide type:** Recommendation summary (Recommend & close). See [`../slide-types/_INDEX.md`](../slide-types/_INDEX.md).
- **Use it for:** the close of a recommendation or advisory deck, where the audience needs the two-to-five things to do, stated answer-first. The numbered headlines carry the recommendation; the sub-points say just enough; the impact tag names the so-what.
- **Density:** T. **Layout:** `data-layout="recommendation"` (centers a shorter stack with `margin-block: auto` and keeps the foot-line clear of the footer chrome ~673).
- **Don't:** run more than five groups or fewer than three (it stops being a graspable, MECE set), write label headlines instead of verb-led moves, or turn this into an owner-and-date action plan, that is the next-steps slide. No prices on the impact tag; name the outcome, not the figure.

## CSS / asset dependencies

- Styles: the `.recsum*` rules added to `deck-kit/slides.css`, plus the `[data-layout="recommendation"]` caps.
- Reuses `.slide-head--assert` (the assertion headline that states the answer) and `.foot-line` (the gold italic governing-thought close) from the existing primitives.
- The single gold accent rides the number badge and the optional impact tag; the group bodies stay quiet navy on paper. Tints use `color-mix(in srgb, var(--gold) N%, transparent)`, no hardcoded hex.
- The per-group cascade follows the `.am-link` / `.it-node` discipline: each group carries its own `opacity:0` plus a transition keyed to `var(--stagger)` that activates when the parent `.recsum` gets `.in`, so the cascade does not rely on the global `[data-build]` stagger.
- No icons required. The numbered badges are CSS counters, so adding or removing a group renumbers itself.

## Variants

- **Numbered (default).** A gold counter badge per group, the moves read as an ordered set. The count is auto-incremented, so the markup carries no hardcoded digits.
- **With impact tags.** Each group closes with a `.recsum-impact` tag naming the payoff (a named outcome, never a price). Omit the tag on groups where the move is its own justification.
- **Sub-point count.** One or two `.recsum-points` lines per group. Keep it to two at most, the depth is spoken; the slide is the map.

## Paste-ready markup

```html
<section class="slide" data-layout="recommendation" data-mood="paper">
  <div class="slide-pad">
    <header class="slide-head slide-head--assert">
      <h2>Four moves turn the pilots into a capability this year.</h2>
    </header>

    <ol class="recsum" data-build="1">
      <li class="recsum-group" style="--stagger: 0s">
        <span class="recsum-num"></span>
        <div class="recsum-body">
          <h3 class="recsum-head">Stand up a governed tool library</h3>
          <ul class="recsum-points">
            <li>One reviewed catalog of the actions AI is allowed to take.</li>
          </ul>
        </div>
        <span class="recsum-impact">Reusable across every team</span>
      </li>

      <li class="recsum-group" style="--stagger: .1s">
        <span class="recsum-num"></span>
        <div class="recsum-body">
          <h3 class="recsum-head">Consolidate the three intake paths into one</h3>
          <ul class="recsum-points">
            <li>Email, portal, and phone requests land in a single queue.</li>
            <li>One owner, one status, one place to measure cycle time.</li>
          </ul>
        </div>
        <span class="recsum-impact">Faster, traceable response</span>
      </li>

      <li class="recsum-group" style="--stagger: .2s">
        <span class="recsum-num"></span>
        <div class="recsum-body">
          <h3 class="recsum-head">Sequence the rollout by reversibility</h3>
          <ul class="recsum-points">
            <li>Start where a wrong answer is cheap to catch and undo.</li>
          </ul>
        </div>
        <span class="recsum-impact">Confidence before scale</span>
      </li>

      <li class="recsum-group" style="--stagger: .3s">
        <span class="recsum-num"></span>
        <div class="recsum-body">
          <h3 class="recsum-head">Name an accountable owner per workflow</h3>
          <ul class="recsum-points">
            <li>Every automated step has a person who can pause it.</li>
          </ul>
        </div>
        <span class="recsum-impact">Clear line of control</span>
      </li>
    </ol>

    <p class="foot-line" data-build="2">Govern the library once, and every team after this builds on it.</p>
  </div>
  <footer class="slide-chrome"><span>SECTION NAME</span><span><span class="num">12</span> / NN</span></footer>
  <aside class="notes"><span class="label">Speaker notes</span><p>...</p></aside>
</section>
```

## Animation

- **Entry:** the assertion headline (the answer) and the group frames read from slide entry, so the slide never looks empty. The badges, headlines, sub-points, and impact tags are present but the groups sit at `opacity:0`.
- **Build 1:** the groups cascade in on a single press, top to bottom, each on its own inline `--stagger` (0s, .1s, .2s, .3s). The groups carry their own `opacity:0` plus a transition keyed to `var(--stagger)` that activates when `.recsum` gets `.in`, so the cascade does not depend on the global `[data-build]` stagger (same discipline as `.am-link` and `.it-node`). One beat: "here are the moves."
- **Build 2:** the gold `.foot-line` lands the governing thought, the one sentence that ties the set together. One press.

Total: two presses, frame to recommendations to governing thought, the answer- first close of the Pyramid Principle (DESIGN-PRINCIPLES §6.2, consulting-decks learnings).
