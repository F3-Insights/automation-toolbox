# Element: Effective Agentic Framework (EAF) figure

The signature figure of the Getting Started family. A thin-stroke engineering diagram: four working parts (**Model · Prompt · Context · Tools**) inside a core circle, bound by a **Harness** ring, with **People** engaging from outside. Whichever element the slide is *about* lights gold (`data-focus`); the rest stay quiet navy, so one figure serves every slice.

- **Slide type:** Named-framework figure (Explain). See [`../slide-types/_INDEX.md`](../slide-types/_INDEX.md).
- **Use it for:** the slide-3 grounding visual in any Getting Started deck, or any time you introduce the whole-system mental model and want to spotlight one part.
- **Density:** V. **Layout:** `data-layout="bap"` (the bap cap keeps it clear of the footer).
- **Don't:** print explanatory glosses on the icons ("the brain", "your data"). The mono-caps label stands alone (DESIGN-PRINCIPLES §2).

## CSS / asset dependencies

- Styles: `.eaf*` rules in `deck-kit/slides.css` (plus the `[data-layout="bap"] .eaf` cap that keeps the figure + credit above the footer chrome).
- Icons: `deck-kit/icons.svg` (`icon-users`, `icon-brain`, `icon-notebook-pen`, `icon-book-open-text`, `icon-wrench`).
- The `href` below is written from a seminar at `Content/Seminars/<slug>/` inside the training folder (setting `training_dir`), three levels up to its root. Adjust if pasted elsewhere.

## Focus variants

Set `data-focus` on the `<svg>` and use the matching sector path + focus overlay:

| Focus | Quadrant | Icon | Sector path `d=` |
|---|---|---|---|
| `model` | top-left | `icon-brain` | `M620,230 L472,230 A148,148 0 0 1 620,82 Z` |
| `prompt` | top-right | `icon-notebook-pen` | `M620,230 L620,82 A148,148 0 0 1 768,230 Z` |
| `context` | bottom-left | `icon-book-open-text` | `M620,230 L472,230 A148,148 0 0 0 620,378 Z` |
| `tools` | bottom-right | `icon-wrench` | `M620,230 L768,230 A148,148 0 0 1 620,378 Z` |

`context` and `tools` are render-verified. **Verify `model`/`prompt` sector fill in Playwright on first use** (flip the sweep flag if the wrong wedge fills).

## Paste-ready markup (focus = context shown; swap per the table above)

```html
<section class="slide" data-layout="bap" data-mood="warm">
  <div class="slide-pad">
    <header class="slide-head">
      <h2>Effective Agentic Framework</h2>
      <p class="sub">A mental model of the elements that determine whether AI actually works in your business.</p>
    </header>
    <div class="eaf-wrap">
      <svg class="eaf" data-focus="context" viewBox="0 0 980 460" role="img"
           aria-label="Effective Agentic Framework. Model, Prompt, Context and Tools are the four working parts, bound by the Harness; People engage from outside. Context is highlighted.">
        <defs>
          <marker id="eaf-arr" markerWidth="8" markerHeight="8" refX="5.5" refY="3" orient="auto">
            <path d="M0,0 L6,3 L0,6 Z" fill="#1E3A6E" opacity="0.55"/>
          </marker>
        </defs>
        <use class="eaf-ico" href="../../../Resources/presentation/deck-kit/icons.svg?v=4#icon-users" x="86" y="206" width="48" height="48"/>
        <text class="eaf-people-lbl" x="110" y="278" text-anchor="middle">PEOPLE</text>
        <line class="eaf-arrow-line" x1="164" y1="230" x2="438" y2="230" marker-end="url(#eaf-arr)"/>
        <circle class="eaf-ring" cx="620" cy="230" r="178"/>
        <circle class="eaf-core" cx="620" cy="230" r="148"/>
        <!-- focus wash - swap class + d= per the focus table -->
        <path class="eaf-sector eaf-sector--context" data-build="1" d="M620,230 L472,230 A148,148 0 0 0 620,378 Z"/>
        <line class="eaf-div" x1="620" y1="82" x2="620" y2="378"/>
        <line class="eaf-div" x1="472" y1="230" x2="768" y2="230"/>
        <rect class="eaf-mask" x="556" y="47" width="128" height="24"/>
        <text class="eaf-ring-lbl" x="620" y="64" text-anchor="middle">HARNESS</text>
        <use class="eaf-ico" href="../../../Resources/presentation/deck-kit/icons.svg?v=4#icon-brain"          x="548" y="156" width="28" height="28"/>
        <text class="eaf-q-lbl" x="562" y="198" text-anchor="middle">MODEL</text>
        <use class="eaf-ico" href="../../../Resources/presentation/deck-kit/icons.svg?v=4#icon-notebook-pen"   x="664" y="156" width="28" height="28"/>
        <text class="eaf-q-lbl" x="678" y="198" text-anchor="middle">PROMPT</text>
        <use class="eaf-ico" href="../../../Resources/presentation/deck-kit/icons.svg?v=4#icon-book-open-text" x="548" y="252" width="28" height="28"/>
        <text class="eaf-q-lbl" x="562" y="294" text-anchor="middle">CONTEXT</text>
        <use class="eaf-ico" href="../../../Resources/presentation/deck-kit/icons.svg?v=4#icon-wrench"          x="664" y="252" width="28" height="28"/>
        <text class="eaf-q-lbl" x="678" y="294" text-anchor="middle">TOOLS</text>
        <!-- focus overlay: the focused element re-drawn in gold (swap icon + label + xy to match) -->
        <g class="eaf-q-focus" data-build="1">
          <use class="eaf-ico eaf-ico--focus" href="../../../Resources/presentation/deck-kit/icons.svg?v=4#icon-book-open-text" x="548" y="252" width="28" height="28"/>
          <text class="eaf-q-lbl eaf-q-lbl--focus" x="562" y="294" text-anchor="middle">CONTEXT</text>
        </g>
      </svg>
      <p class="eaf-focus-line" data-build="1">Today, we focus on Context: your Data.</p>
      <p class="eaf-credit" data-build="2">Framework adapted from IndyDevDan (@indydevdan) · Harness &amp; People framing by F3 Insights.</p>
    </div>
  </div>
  <footer class="slide-chrome"><span>SECTION NAME</span><span><span class="num">03</span> / NN</span></footer>
  <aside class="notes"><span class="label">Speaker notes</span><p>…</p></aside>
</section>
```

## Animation

- **Build 1:** the focus wash + gold icon/label fade in, and the focus line appears ("Today, we focus on …"). One press.
- **Build 2:** the attribution credit fades in.

Everything else (ring, core, four neutral labels, People, the inbound arrow) is visible from slide entry, so the figure never looks empty.
