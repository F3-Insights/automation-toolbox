# Element: Worked example (`.worked`)

A fully solved instance with the reasoning shown. The problem statement sits at the top in a navy `.def-block` (the definitional frame), then three to four numbered reasoning steps reveal one per press, each pairing an action with a brief rationale, and the result highlights last in a gold-accented row. It is the worked-example effect made into a slide: the audience watches the method run on one believable number.

- **Slide type:** Worked example (Demonstrate). See [`../slide-types/_INDEX.md`](../slide-types/_INDEX.md).
- **Use it for:** the slide right after a framework or rule of thumb, when the executive's reaction is "show me how that plays out on a real number." One concrete, believable instance from the audience's world.
- **Density:** B. **Layout:** `data-layout="worked"`.
- **Don't:** stack more than four steps (the build drags and the column overruns the footer); don't print the deep judgment (edge cases, when the rule breaks) on the slide, that is spoken. Keep each rationale to one line.

## CSS / asset dependencies

- Styles: the `.worked*` rules in `deck-kit/slides.css`, plus the shared `.def-block` (navy problem frame) and the global `[data-build]` step pattern.
- No icons required. The step numerals are CSS-numbered mono badges, not sprite icons.
- One gold accent only: the step numerals and the result row carry it; the problem frame stays navy.

## Animation

- **Entry:** the problem statement (`.def-block`) and the empty step rail are visible from slide entry, so the slide never looks blank.
- **Builds 1 to N:** each `.worked-step` reveals on its own press. This is a *true sequence* (each step is a separate idea), so the steps step one per press rather than cascading. Give them consecutive `data-build` numbers (1, 2, 3, ...).
- **Final build:** the `.worked-result` row reveals last, on the press after the final step.
- Honors `prefers-reduced-motion` (handled globally); in scroll view every step and the result show at once.

## Paste-ready markup

```html
<section class="slide" data-layout="worked" data-mood="paper">
  <div class="slide-pad">
    <header class="slide-head slide-head--assert">
      <h2>One targeted automation can pay for itself inside a quarter.</h2>
    </header>
    <div class="worked">
      <div class="def-block worked-problem">
        <div class="big">Should we automate three-way invoice matching?</div>
        <div class="small">AP clerks match 1,400 invoices a month by hand; the team wants to know if a tool earns its keep.</div>
      </div>
      <ol class="worked-steps">
        <li class="worked-step" data-build="1">
          <span class="worked-num"></span>
          <div class="worked-body">
            <span class="worked-act">Measure the manual load.</span>
            <span class="worked-why">1,400 invoices at ~6 minutes each is 140 hours a month of clerk time.</span>
          </div>
        </li>
        <li class="worked-step" data-build="2">
          <span class="worked-num"></span>
          <div class="worked-body">
            <span class="worked-act">Estimate what the tool absorbs.</span>
            <span class="worked-why">Clean matches auto-clear; only ~20% exceptions reach a person, leaving ~28 hours.</span>
          </div>
        </li>
        <li class="worked-step" data-build="3">
          <span class="worked-num"></span>
          <div class="worked-body">
            <span class="worked-act">Value the hours returned.</span>
            <span class="worked-why">112 hours back a month is most of a full clerk's time, freed for exceptions and vendor work.</span>
          </div>
        </li>
        <li class="worked-step" data-build="4">
          <span class="worked-num"></span>
          <div class="worked-body">
            <span class="worked-act">Weigh it against the tool's cost.</span>
            <span class="worked-why">Set that recovered capacity against the tool's monthly cost; the capacity is the larger number.</span>
          </div>
        </li>
      </ol>
      <div class="worked-result" data-build="5">
        <span class="worked-result-label">Result</span>
        <span class="worked-result-text">Setup pays back within a quarter, then returns most of a clerk's month, every month after.</span>
      </div>
    </div>
  </div>
  <footer class="slide-chrome"><span>Demonstrate</span><span><span class="num">06</span> / 13</span></footer>
  <aside class="notes"><span class="label">Speaker notes</span><p>This is a worked example, so let the build do the teaching. Read the problem aloud, then step through one reveal per beat. The point is not the exact figures, it is the shape of the reasoning: measure the manual load, estimate what the tool absorbs, price the returned hours, net the run cost. Where this gets nuanced is exception handling and change management, and that is the judgment we bring in the engagement, so keep it spoken.</p></aside>
</section>
```
