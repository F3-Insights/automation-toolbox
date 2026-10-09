# Element: Big-number / stat

One striking figure IS the slide. A huge protagonist number sits in the optical center of the canvas, a single line of context names what it measures, and a small muted source line makes it traceable. An optional one-line supporting figure (a denominator, a prior-year baseline) can ride underneath. Nothing else competes for the eye.

- **Slide type:** Big-number / stat (Prove). See [`../slide-types/big-number.md`](../slide-types/big-number.md).
- **Use it for:** a relevance hook that sets the stake before teaching, or a single punch of evidence inside a Prove run, where one figure carries the argument and a chart would only dilute it.
- **Density:** V. **Layout:** `data-layout="bignum"` (centers the block in the available height and keeps the source line clear of the footer chrome).
- **Don't:** stack two co-equal numbers (that is before/after or a ranking bar), add a second accent color, or print the figure without a named source. One gold accent: the protagonist number.

## CSS / asset dependencies

- Styles: the `.bignum*` rules in `css_additions` (appended to `deck-kit/slides.css`), plus the global `[data-build]` fade and `--stagger` hook already in `slides.css`.
- Reuses existing primitives: `.slide-head--assert` for the takeaway headline, `.slide-chrome` footer, the build/`--stagger` cascade system.
- No icons required. No SVG. The figure is HTML text, so it scales cleanly with the uniform slide scale (no viewBox text distortion).

## Variants

- **Bare stat (default).** Headline + protagonist number + context line + source. The cleanest form; use it unless a second figure genuinely helps.
- **With supporting figure.** Add one `.bignum-support` line (e.g. "up from 21% a year earlier") between the context line and the source. Keep it to one subordinate stat in muted type. It is a footnote to the protagonist, never a rival.
- **Unit / suffix.** Wrap a trailing unit ("%", "x", "hrs") in `<span class="bignum-unit">` so it renders smaller and gold-foil tinted, letting the digits stay dominant.

## Paste-ready markup (default + supporting figure)

```html
<section class="slide" data-layout="bignum" data-mood="paper">
  <div class="slide-pad">
    <header class="slide-head slide-head--assert">
      <h2>Most mid-market finance teams now use AI weekly.</h2>
    </header>
    <div class="bignum">
      <p class="bignum-figure" data-build="1">58<span class="bignum-unit">%</span></p>
      <p class="bignum-context" data-build="1" style="--stagger: .12s">of mid-market finance teams use an AI tool at least weekly</p>
      <p class="bignum-support" data-build="2">up from 24% in the prior year</p>
      <p class="bignum-source" data-build="2">Illustrative figure. In a real deck, name the survey and year.</p>
    </div>
  </div>
  <footer class="slide-chrome"><span>Demo</span><span><span class="num">04</span> / 14</span></footer>
  <aside class="notes"><span class="label">Speaker notes</span><p>Open on the figure, then name the so-what.</p></aside>
</section>
```

## Animation

- **Build 1:** the protagonist figure and its context line cascade in together on one press (the figure leads, the context line follows ~0.12s behind via `--stagger`). This is the beat where the speaker reveals the number and says what it measures.
- **Build 2:** the supporting figure and the source line fade in together, the "for the skeptic in row two" beat that makes the number defensible.

The headline is visible from slide entry, so the slide never looks empty before the first press. Without a supporting figure, drop the `.bignum-support` line and the slide is a clean two-build reveal (figure, then source). In scroll mode every build is visible at once, as the global build rules already handle.
