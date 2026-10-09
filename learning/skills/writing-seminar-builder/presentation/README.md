# presentation/: the deck-building system

Everything used to build seminar decks in HTML (F3 Insights is the worked example of a house brand). The seminars themselves live in the training folder, whose layout (including the copy of this folder that decks link to) is defined once in the skill's `SKILL.md`, "The training folder".

```
presentation/
├── DESIGN-PRINCIPLES.md   ← the visual + animation system (the authority; read first)
├── learnings/             ← deck strategy by purpose
│   ├── _universal.md         (the umbrella: applies to every deck)
│   ├── training-decks.md     (teach a concept)
│   ├── consulting-decks.md   (drive to a recommendation)
│   └── financial-data-decks.md (make numbers defensible)
├── slide-types/           ← the ~35-type catalog: when to use each   [in progress]
├── elements/              ← cut-and-paste reusable visuals/flows      [in progress]
└── deck-kit/              ← the rendering toolkit
    ├── brand.css   ← tokens (color, type, surfaces) + primitives
    ├── slides.css  ← slide-view layout (1280×720, JS-scaled)
    ├── scroll.css  ← scroll-view editorial layout
    ├── presenter.js ← navigation, presenter window, view toggle
    └── icons.svg   ← the Lucide-based sprite (single source of icons)
```

Brand tokens come from the house brand guide in the `brand-guide` skill; if the brand guide changes, update `deck-kit/brand.css` to match.

## Preview a seminar locally

```sh
# from the training folder's root
python3 -m http.server 8765 --bind 127.0.0.1
```

Then open the seminar's folder under that root, for example `http://127.0.0.1:8765/Content/Seminars/<slug>/`.

## Two views, one source

Each `index.html` renders both ways; switch with the top-right button, the `V` key, or the URL:

| URL | View |
|---|---|
| `…/<slug>/?view=slides` (default) | One slide at a time, presenter-ready |
| `…/<slug>/?view=scroll` | Long-form editorial page, async-readable |
| `…/<slug>/?view=slides#5` | Slide deck opened to slide 5 |

Slide-view keys: `→ ↓ Space PageDown` next · `← ↑ PageUp` prev · `Home/End` first/last · `F` fullscreen · `S` presenter window · `V` toggle view.

## Authoring a new deck

1. Read `DESIGN-PRINCIPLES.md` and the relevant `learnings/` doc.
2. Compose from `slide-types/` (which slide to use when) and `elements/` (the paste-ready markup), pulling layout primitives from `deck-kit/`.
3. Keep the per-deck story in a `_content-map.md` beside the `index.html`.
4. Verify every animated change in Playwright (drive all builds, screenshot the final state) per DESIGN-PRINCIPLES §9.

If a genuinely new pattern is needed, add it to `deck-kit/` + document it in `elements/` so the next deck can reuse it.
