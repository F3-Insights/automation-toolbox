# Element: Trend line (time-series chart)

A time-series LINE chart drawn in inline SVG. The x axis is time, one focal series runs in gold, an optional comparator runs muted navy, and the one inflection point that carries the message is marked with a small callout that names cause and magnitude. Clean axes, minimal gridlines, label only what matters: the chart reads as competence, not decoration.

- **Slide type:** Trend (line) (Prove). See [`../slide-types/trend-line.md`](../slide-types/trend-line.md).
- **Use it for:** change over a continuous time axis where the slope is the point, a metric that turns after an intervention, an adoption curve that bends, a cost or cycle-time trend you want the audience to trust the path of.
- **Density:** V. **Layout:** `data-layout="trend"` (centers the chart card in the leftover height and keeps the source line clear of the footer chrome ~673).
- **Don't:** add a second accent color, draw a full gridded matrix (one faint baseline plus sparse horizontal rules is enough), plot more than one comparator, or leave the inflection unannotated. One gold accent: the focal line and its callout. Everything non-focal is muted navy or gray.

## CSS / asset dependencies

- Styles: the `.trend*` rules in `css_additions` (appended to `deck-kit/slides.css`), plus the global `[data-build]` fade, the `--stagger` hook, and the `.trace` stroke-dashoffset primitive already in `slides.css`.
- Reuses existing primitives: `.slide-head--assert` for the takeaway headline, the paper-card diagram container convention (DESIGN-PRINCIPLES §4.3), the `.trace` path-trace primitive for the focal line, `.slide-chrome` footer.
- No icons required. The chart is one inline `<svg>`. The slide scales uniformly, so static SVG geometry is safe (DESIGN-PRINCIPLES §5.1); axis and series labels are HTML overlaid on the card, not SVG text, so nothing distorts.

## Variants

- **Focal + comparator (default).** One gold focal line and one muted navy comparator (peer benchmark, prior year, or a flat target line). The eye reads the focal line against a quiet reference.
- **Focal only.** Drop the `.trend-comparator` path and its legend chip when the single series tells the whole story. The axes and inflection callout carry it.
- **Flat target line.** Use a dashed horizontal muted line as the comparator (a budget, a target DSO, an SLA) instead of a second curve.

## Paste-ready markup (focal + comparator)

```html
<section class="slide" data-layout="trend" data-mood="paper">
  <div class="slide-pad">
    <header class="slide-head slide-head--assert">
      <h2>Book-close time turned the month we automated reconciliation.</h2>
    </header>
    <figure class="trend">
      <figcaption class="trend-legend">
        <span class="trend-key trend-key--focal">Days to close, with AI assist</span>
        <span class="trend-key trend-key--comp">Peer median</span>
      </figcaption>
      <svg class="trend-chart" viewBox="0 0 1000 380" role="img"
           aria-label="Monthly days to close the books fell from 9 to 4 after reconciliation was automated in May, ending below the peer median of 6.">
        <!-- y gridlines + baseline (visible from entry) -->
        <line class="trend-grid" x1="70" y1="40"  x2="970" y2="40"/>
        <line class="trend-grid" x1="70" y1="120" x2="970" y2="120"/>
        <line class="trend-grid" x1="70" y1="200" x2="970" y2="200"/>
        <line class="trend-grid" x1="70" y1="280" x2="970" y2="280"/>
        <line class="trend-axis" x1="70" y1="40"  x2="70"  y2="320"/>
        <line class="trend-axis" x1="70" y1="320" x2="970" y2="320"/>
        <!-- comparator: peer median, muted, dashed, in from entry (build 1) -->
        <polyline class="trend-comparator" data-build="1"
          points="70,200 198,200 326,200 454,200 582,200 710,200 838,200 970,200"/>
        <!-- focal series: traces in on build 2 -->
        <svg class="trace trend-focal-wrap" data-build="2" viewBox="0 0 1000 380" x="0" y="0">
          <polyline class="trend-focal" pathLength="1"
            points="70,80 198,88 326,72 454,96 582,160 710,256 838,280 970,288"/>
        </svg>
        <!-- focal end dot + inflection dot -->
        <circle class="trend-dot trend-dot--end" data-build="2" cx="970" cy="288" r="5"/>
        <circle class="trend-dot trend-dot--infl" data-build="3" cx="582" cy="160" r="6"/>
      </svg>
      <!-- x labels (HTML, no SVG text distortion) -->
      <div class="trend-xaxis">
        <span>Jan</span><span>Feb</span><span>Mar</span><span>Apr</span>
        <span>May</span><span>Jun</span><span>Jul</span><span>Aug</span>
      </div>
      <!-- inflection callout, build 3 -->
      <div class="trend-callout" data-build="3">
        <span class="trend-callout-tag">May: reconciliation automated</span>
        <span class="trend-callout-val">9 days to 4 in three months</span>
      </div>
    </figure>
    <p class="trend-source" data-build="3">Illustrative figures; in a real deck, name the benchmark behind the peer median.</p>
  </div>
  <footer class="slide-chrome"><span>Demo</span><span><span class="num">07</span> / 13</span></footer>
  <aside class="notes"><span class="label">Speaker notes</span><p>Axes and the flat peer line are up on entry, so we open with the reference frame. Press to trace the focal line, then press to drop the inflection dot and the callout. Land the so-what: the turn is the month we automated, not a slow grind.</p></aside>
</section>
```

## Animation

- **Build 1 (entry frame):** the axes, the sparse gridlines, and the muted comparator line are visible from slide entry. The reference frame is up before any focal data, so the slide never looks empty and the audience has a baseline to read against.
- **Build 2:** the focal gold line traces in left to right via the `.trace` stroke-dashoffset primitive (0.9s, the same draw used across the deck), and its end dot fades in as the line arrives. This is the beat where the speaker walks the curve.
- **Build 3:** the inflection dot and the callout naming cause and magnitude fade in together, along with the source line. This is the so-what beat: the moment that matters, marked.

The comparator carries `data-build="1"` so it cascades with entry rather than sitting hidden. In scroll mode every build is visible at once, as the global build rules already handle; the `.trace` primitive also resolves to a fully drawn line under `prefers-reduced-motion` and in scroll view.
