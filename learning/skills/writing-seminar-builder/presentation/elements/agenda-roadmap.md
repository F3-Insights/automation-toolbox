# Element: Agenda / roadmap

The talk's scaffold. Three to five numbered stops sit on a single horizontal path, each labelled in two to four words, connected by faint gold links so the eye reads them as one route rather than a list. It is the orienting slide right after the title, and it doubles as a returning section anchor: a variant lights the current stop gold to say "you are here" while the rest stay quiet navy. One gold accent: the active stop and the links, so the eye lands on where the talk is going.

- **Slide type:** Agenda / roadmap (Orient). See [`../slide-types/_INDEX.md`](../slide-types/_INDEX.md).
- **Use it for:** the second slide of a deck (set the route), and again at each section boundary (re-anchor with the current stop lit). It is a setup slide, so it carries no leave-behind beyond the route itself.
- **Don't:** write full sentences in the stops, run more than five stops, or light more than one stop gold. A stop is a section name in two to four words; the depth lives in the sections it points to.
- **Density:** B. **Layout:** `data-layout="agenda"`.

## CSS / asset dependencies

- Styles: the `.agenda*` rules in `css_additions` (namespaced to this element). The `[data-layout="agenda"]` block centers the path in the available height with `margin-block: auto` and keeps it above the footer chrome.
- Reuses brand tokens only: `--navy`, `--gold`, `--paper`, `--line`, `--muted`, `--obsidian`, `--ink`, `--white`, `--serif`, `--grotesk`, `--mono`, `--sans`, plus `color-mix` tints of `--gold` / `--navy`.
- Borrows two conventions, does not redefine them: the **gold CSS-arrow data-URI** convention from `.sf-arrow` / `.lifecycle .stage::after` (used here for the inter-stop links), and the **per-child stagger** idiom from `.am-links` (each `.agenda-stop` carries its own `opacity:0` + transition keyed to `var(--stagger)`, activated when the parent build element gets `.in`, because the global `[data-build]` stagger only fires on build elements).
- This is a setup slide, so the head uses the existing `.slide-head` topic-title treatment, not the `.slide-head--assert` headline.
- No sprite icons required; the stop markers are numerals, not glyphs.

## Variants

- **`data-mood="paper"`** (default): light slide, navy stops, gold links. The calm register for the opening agenda where no stop is current yet.
- **Orientation:** horizontal is the default. For a long-label route, add `agenda--vertical` to stack the stops down a vertical rail; the same markup and stagger apply, the links just run top to bottom.
- **"You are here" anchor:** add `agenda-stop--here` to the one stop the talk has reached. Its marker fills gold and a mono `agenda-here-tag` reads "YOU ARE HERE" above it; every other stop stays quiet navy. On these return appearances drop the `data-build` so the lit stop orients from slide entry with no cascade.
- **Done stops:** a stop already covered can take `agenda-stop--done` for a muted, checked marker, so a mid-talk anchor shows progress (done behind, current lit, upcoming quiet). Optional; skip it on the opening agenda.

## Paste-ready markup (horizontal, opening agenda, four stops)

```html
<div class="agenda" data-build="1">
  <ol class="agenda-path">
    <li class="agenda-stop" style="--stagger: 0s">
      <span class="agenda-num">1</span>
      <span class="agenda-label">Where AI fits today</span>
    </li>
    <li class="agenda-stop" style="--stagger: .1s">
      <span class="agenda-num">2</span>
      <span class="agenda-label">Reading your own data</span>
    </li>
    <li class="agenda-stop" style="--stagger: .2s">
      <span class="agenda-num">3</span>
      <span class="agenda-label">Letting AI act</span>
    </li>
    <li class="agenda-stop" style="--stagger: .3s">
      <span class="agenda-num">4</span>
      <span class="agenda-label">A safe first project</span>
    </li>
  </ol>
</div>
```

For the returning **"you are here"** anchor, drop the `data-build` so the lit stop orients from entry, and mark the current and done stops:

```html
<div class="agenda">
  <ol class="agenda-path">
    <li class="agenda-stop agenda-stop--done"><span class="agenda-num">1</span><span class="agenda-label">Where AI fits today</span></li>
    <li class="agenda-stop agenda-stop--here"><span class="agenda-here-tag">You are here</span><span class="agenda-num">2</span><span class="agenda-label">Reading your own data</span></li>
    <li class="agenda-stop"><span class="agenda-num">3</span><span class="agenda-label">Letting AI act</span></li>
    <li class="agenda-stop"><span class="agenda-num">4</span><span class="agenda-label">A safe first project</span></li>
  </ol>
</div>
```

The links between stops are drawn by an `::after` on each non-last stop using the gold CSS-arrow data-URI (the `.sf-arrow` convention), so there is no SVG text to distort under the slide scale and each link scales with the uniform slide scale.

## Animation

- **Build 0 (entry):** the path rail and the inter-stop links are visible, so the route reads as one shape from the start and the slide never looks empty.
- **Build 1 (opening agenda only):** the numbered stops cascade in left to right on **one press**. Each `.agenda-stop` carries its own `opacity:0` + transition keyed to `var(--stagger)`, activated when `.agenda` gets `.in` (per the `.am-links` idiom). Stagger steps at ~0.1s so a four to five stop route finishes in well under a second.
- **Returning anchor:** no build. The current stop is lit gold from entry; the re-anchor is a one-beat reset, not a rebuilt list.

Honor `prefers-reduced-motion`: the end-state renders correctly, the motion is instant. Scroll view shows every stop at once.
