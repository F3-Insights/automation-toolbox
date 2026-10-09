# Element: Waterfall / bridge

A bridge chart that explains a delta. A start bar anchors the left at the prior figure, floating +/- step bars cascade left to right for each driver, and an end bar anchors the right at the new figure. Positive steps take one quiet tone, negative steps another, and exactly one step, the driver that carries the message, lights gold. Every step wears a signed value label, and a thin connector tick runs from the top of each step to the foot of the next so the eye follows the running total. It is the finance "explain the change" slide.

- **Slide type:** Waterfall / bridge (Prove). See [`../slide-types/waterfall.md`](../slide-types/waterfall.md).
- **Use it for:** a revenue bridge, cost walk, or margin walk, any time the beat is "the number moved from A to B, here is why", and you want one driver to be the headline.
- **Density:** V. **Layout:** `data-layout="waterfall"` (floats the chart to the optical center and keeps the source line clear of the footer chrome).
- **Don't:** add a second accent color (one gold step only), label gridlines the audience does not need, print a price, or let the bars cling to the top with dead space below. Steps must reconcile: start plus the signed steps equals end.

## CSS / asset dependencies

- Styles: the `.wf*` rules in `css_additions` (appended to `deck-kit/slides.css`), plus the global `[data-build]` fade and `--stagger` hook already in `slides.css`.
- Reuses existing primitives: `.slide-head--assert` for the insight headline, `.slide-chrome` footer, the build/`--stagger` cascade. The bar geometry is bespoke CSS (no chart library, no Mermaid, per the financial-data learnings).
- No icons. No SVG. Bars and connector ticks are HTML/CSS, so they scale cleanly with the uniform slide scale (no viewBox text distortion).
- **Geometry:** each column is a flex track; a step bar is positioned by a `--base` (its foot, as a percentage of the plot height from the bottom) and a `--size` (its height as a percentage). Compute these once from the data: the running subtotal sets `--base`, the driver magnitude sets `--size`. The start and end bars are full-height-from-zero anchors (`--base: 0`).

## Variants

- **Standard bridge (default).** Start bar, signed driver steps, end bar. The cleanest form; use it unless the walk is long.
- **Subtotal column.** Insert a `.wf-col--total` mid-walk (e.g. "Gross margin" before operating drivers) styled like the anchors, grounded at zero, so a long walk reads in two readable acts.
- **Net-callout.** Add one muted `.wf-net` line under the chart naming the total swing ("Net: down 2.4 pts") when the end bar alone does not make the delta explicit.

## Paste-ready markup (standard bridge; gold marks the focal driver)

```html
<section class="slide" data-layout="waterfall" data-mood="paper">
  <div class="slide-pad">
    <header class="slide-head slide-head--assert">
      <h2>Gross margin fell on freight, not on pricing.</h2>
    </header>
    <div class="wf">
      <div class="wf-plot">
        <!-- start + end anchors are the frame: visible on build 1 -->
        <div class="wf-col wf-col--anchor" data-build="1" style="--base:0; --size:88%">
          <span class="wf-val">41.2%</span>
          <span class="wf-bar"></span>
          <span class="wf-label">FY24 margin</span>
        </div>
        <!-- driver steps cascade left to right on build 2 -->
        <div class="wf-col wf-col--down" data-build="2" style="--base:74%; --size:14%; --stagger:0s">
          <span class="wf-val">-1.6</span>
          <span class="wf-bar"><i class="wf-tick"></i></span>
          <span class="wf-label">Freight</span>
        </div>
        <div class="wf-col wf-col--down wf-col--focus" data-build="2" style="--base:62%; --size:12%; --stagger:.1s">
          <span class="wf-val">-1.3</span>
          <span class="wf-bar"><i class="wf-tick"></i></span>
          <span class="wf-label">Materials</span>
        </div>
        <div class="wf-col wf-col--up" data-build="2" style="--base:62%; --size:6%; --stagger:.2s">
          <span class="wf-val">+0.7</span>
          <span class="wf-bar"><i class="wf-tick"></i></span>
          <span class="wf-label">Pricing</span>
        </div>
        <div class="wf-col wf-col--up" data-build="2" style="--base:68%; --size:5%; --stagger:.3s">
          <span class="wf-val">+0.6</span>
          <span class="wf-bar"><i class="wf-tick"></i></span>
          <span class="wf-label">Mix</span>
        </div>
        <div class="wf-col wf-col--anchor" data-build="1" style="--base:0; --size:80%">
          <span class="wf-val">39.6%</span>
          <span class="wf-bar"></span>
          <span class="wf-label">FY25 margin</span>
        </div>
      </div>
      <p class="wf-net" data-build="2" style="--stagger:.4s">Net: down 1.6 pts. Input costs, not price, drove the walk.</p>
      <p class="wf-source" data-build="1">Source: FY24 to FY25 management accounts, gross margin basis. Illustrative.</p>
    </div>
  </div>
  <footer class="slide-chrome"><span>Demo</span><span><span class="num">07</span> / 13</span></footer>
  <aside class="notes"><span class="label">Speaker notes</span><p>Land the headline first: margin fell, and it was input cost, not pricing. Then walk the bridge left to right. Pause on the gold step, the materials line, that is the one to act on. Close on the net line so no one leaves thinking we cut price.</p></aside>
</section>
```

## Animation

- **Build 1:** the start and end anchor bars, the baseline axis, and the source line are the frame, visible from slide entry into this build. This is the beat where the speaker names the two endpoints ("we went from 41.2 to 39.6").
- **Build 2:** the driver steps cascade left to right on ONE press, each fading in on its own `--stagger` (~0.1s apart), with the net line trailing last. This is the explain-the-delta beat, the speaker walking each driver and pausing on the gold one. The steps carry their own opacity transition keyed to `--stagger` so the left-to-right order holds without one press per bar.

The anchors are visible from entry, so the slide never looks empty before the first press. In scroll mode every build shows at once, as the global build rules already handle.
