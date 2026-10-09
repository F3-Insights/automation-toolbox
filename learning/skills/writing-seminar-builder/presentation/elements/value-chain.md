# Element: Value chain

A horizontal sequence of 4 to 6 activity blocks read left to right, each a named stage in a known end-to-end process, joined by thin gold connectors. One stage (occasionally two adjacent) is the **focal stage**: it carries a metric or annotation in gold and reads as the place where value or cost concentrates. Everything non-focal stays quiet navy, so the eye lands where the argument lives.

- **Slide type:** Value chain (Demonstrate). See [`../slide-types/_INDEX.md`](../slide-types/_INDEX.md).
- **Use it for:** mapping a recognized workflow (order to cash, lead to close, quote to install, intake to discharge) end to end and pointing at the single stage that moves the number. The chain is the terrain, the gold stage is where to act.
- **When NOT to use it:** if the slide's job is gates and decisions (HITL), use the process-flow `.lifecycle` instead. If you are scoring or comparing stages, use a comparison table or 2x2. The value chain answers *where value sits*, not *which option wins*.
- **Density:** V. **Layout:** `data-layout="value-chain"`.
- **Don't:** light more than one focal stage (two only if genuinely adjacent and part of one claim), and don't print a metric on every block. The whole point is contrast: one gold annotation against a quiet navy row.

## CSS / asset dependencies

- Styles: the `.vchain*` rules added to `deck-kit/slides.css` (new, namespaced).
- Reuses the gold CSS-arrow data-URI connector pattern from `.sf-arrow` / `.lifecycle .stage::after` (DESIGN-PRINCIPLES §5.5), the navy stage surface treatment, `.slide-head--assert`, `.foot-line`, and the `[data-build]` + `--stagger` cascade hook (§6.6).
- No icons required. No SVG: the blocks are CSS, the connector is a background data-URI on the gap, matching the lifecycle engine.

## Variants

- **4 / 5 / 6 stages.** The grid is `repeat(N, 1fr)`; the connector lives in the grid `gap`, so the row stays even at any N. Five is the comfortable default; six tightens the labels, four reads roomy.
- **Single focal vs. two adjacent focal.** Add `vchain-stage--focus` to the one stage that matters. If a claim genuinely spans two adjacent stages, mark both, but treat the connector between them as part of the focal pair (keep its arrow gold, which it already is).
- **Metric vs. annotation.** The focal stage's `.vchain-note` can hold a hard metric (`.vchain-metric` big number + a unit line) or a one-line serif annotation. Use a named benchmark and cite it (e.g. "APQC") when the figure is a benchmark, illustrative otherwise.

## Paste-ready markup (5 stages, focus on stage 4)

```html
<section class="slide" data-layout="value-chain" data-mood="paper">
  <div class="slide-pad">
    <header class="slide-head slide-head--assert">
      <h2>Cash gets stuck at invoicing, not anywhere else in the chain.</h2>
    </header>

    <div class="vchain" data-stages="5">
      <div class="vchain-row">
        <div class="vchain-stage" data-build="1" style="--stagger: 0s">
          <span class="vchain-num">01</span>
          <h4>Order intake</h4>
          <p class="vchain-desc">Quotes confirmed, PO logged</p>
        </div>
        <div class="vchain-stage" data-build="1" style="--stagger: 0.09s">
          <span class="vchain-num">02</span>
          <h4>Pick &amp; pack</h4>
          <p class="vchain-desc">Warehouse pulls the order</p>
        </div>
        <div class="vchain-stage" data-build="1" style="--stagger: 0.18s">
          <span class="vchain-num">03</span>
          <h4>Ship &amp; deliver</h4>
          <p class="vchain-desc">Carrier handoff, POD captured</p>
        </div>
        <div class="vchain-stage vchain-stage--focus" data-build="1" style="--stagger: 0.27s">
          <span class="vchain-num">04</span>
          <h4>Credit &amp; invoice</h4>
          <p class="vchain-desc">Approve terms, raise the invoice</p>
        </div>
        <div class="vchain-stage" data-build="1" style="--stagger: 0.36s">
          <span class="vchain-num">05</span>
          <h4>Collect &amp; apply</h4>
          <p class="vchain-desc">Payment received, cash applied</p>
        </div>
      </div>

      <div class="vchain-callout" data-build="2">
        <div class="vchain-metric">9 days</div>
        <p class="vchain-note">of the order-to-cash cycle sit in manual credit review and invoice prep, the single longest dwell in the chain. <span class="vchain-src">Illustrative</span></p>
      </div>
    </div>

    <p class="foot-line" data-build="2">Fix the one slow link and the whole cycle gets faster.</p>
  </div>
  <footer class="slide-chrome"><span>Demo</span><span><span class="num">07</span> / 13</span></footer>
  <aside class="notes"><span class="label">Speaker notes</span><p>...</p></aside>
</section>
```

## Animation

- **Build 1:** the five stages cascade in left to right on ONE press. Each stage carries the same `data-build="1"` and an inline `--stagger` (0.09s step for five blocks, so the row finishes in under half a second). The gold connector arrow on each stage rides in with its block, drawing the row as a left-to-right flow. The frame is the row itself, so nothing looks empty on entry.
- **Build 2:** the focal callout (metric + annotation) and the `.foot-line` fade in together, on the next press. This is the payoff beat: the chain is established, now the eye is pulled to the one stage that moves the number.

The focal stage's gold treatment is present from build 1 (so the audience sees *where* before they read *why* on build 2). Everything honors `prefers-reduced-motion` via the global `[data-build]` rule; scroll view shows all builds at once.
