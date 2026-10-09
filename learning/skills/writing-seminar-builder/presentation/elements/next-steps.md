# Element: Next-steps / action plan

The Monday-morning close. A compact table of the immediate moves, **Action** in the first column, **Owner** and **Timing** in the next two, one row per move. Every action is concrete and assignable: a verb-led action, a named owner, a timing the room can hold each other to. The single gold accent rides the first action, the one that has to happen first, so the eye lands on the true starting move; every other row stays quiet navy. A 30/60/90 three-column variant tells the same story as near, mid, and far horizons when that frame reads cleaner than a list of owners.

- **Slide type:** Next-steps / action plan (Recommend & close). See [`../slide-types/next-steps.md`](../slide-types/next-steps.md).
- **Use it for:** the closing beat of a recommendation, after the audience has accepted the argument and needs the assignable actions, with owners and timing, to leave the room and act.
- **Don't:** turn it into a project plan. Four or five rows is the ceiling, one line per cell. Don't put a price in the Timing column or anywhere else: name the next step or service, never a dollar amount. Don't stack accents: gold rides only the first action; the rest stay navy.
- **Density:** T. **Layout:** `data-layout="next-steps"`.

## CSS / asset dependencies

- Styles: the `.ns-*` rules in `css_additions` (namespaced to this element). Self-contained; no sprite, no icons required.
- Reuses existing primitives without redefining them: `.slide-head--assert` (the assertion headline), `.foot-line` (the italic gold one-line close).
- Borrows one convention: the **per-child `--stagger` idiom** from `.am-links` / `.rtl-bar`. Each row carries its own `opacity:0` plus a transition keyed to `var(--stagger)`, activated when the parent build element gets `.in`, since the global `[data-build]` stagger only fires on the build element itself.
- The table is a CSS grid: the action table is three columns (action, owner, timing); the 30/60/90 variant is three equal columns over a shared header.

## Variants

- **Action table (default).** `data-layout="next-steps"` with `.ns-table`. Rows are `.ns-row`; the focal first move takes `.ns-row--focus` (gold left rule and a quiet "Start here" tag). Owner and Timing sit in mono caps so the assignments scan fast.
- **30/60/90 columns.** Swap `.ns-table` for `.ns-cols`: three equal columns under a mono time header (First 30 days, Day 31 to 60, Day 61 to 90), each holding two or three short action lines. Put `.ns-col--focus` on the first horizon. Use this when the story is a sequence of horizons rather than a list of owners.
- **Owner styling.** A person or role goes in `.ns-owner`; if a move is shared, write the lead owner, not a committee. Keep it one line.

## Paste-ready markup (action table; focal = the first move)

```html
<div class="ns-table">
  <div class="ns-thead" aria-hidden="true">
    <span>Action</span>
    <span>Owner</span>
    <span>Timing</span>
  </div>
  <div class="ns-rows" data-build="1">
    <div class="ns-row ns-row--focus" style="--stagger: 0s">
      <span class="ns-tag">Start here</span>
      <span class="ns-action">Name one workflow for the first pilot</span>
      <span class="ns-owner">COO</span>
      <span class="ns-when">This week</span>
    </div>
    <div class="ns-row" style="--stagger: .1s">
      <span class="ns-action">Pull together the data the pilot will touch</span>
      <span class="ns-owner">Head of Ops</span>
      <span class="ns-when">Days 1 to 10</span>
    </div>
    <div class="ns-row" style="--stagger: .2s">
      <span class="ns-action">Set the guardrails and access for the pilot pod</span>
      <span class="ns-owner">IT lead</span>
      <span class="ns-when">Days 1 to 14</span>
    </div>
    <div class="ns-row" style="--stagger: .3s">
      <span class="ns-action">Run a readiness assessment alongside</span>
      <span class="ns-owner">Outside advisor</span>
      <span class="ns-when">Days 7 to 21</span>
    </div>
    <div class="ns-row" style="--stagger: .4s">
      <span class="ns-action">Review the first result, decide go or hold</span>
      <span class="ns-owner">Leadership</span>
      <span class="ns-when">Day 30</span>
    </div>
  </div>
</div>
<p class="foot-line" data-build="2">One owned action this week beats a perfect plan next quarter.</p>
```

Each cell label sits in plain HTML text, so nothing distorts under the slide scale. The "Start here" tag is a `::` free inline span on the focal row only, the single gold mark on the slide.

## Animation

- **Build 0 (entry):** the column header (Action, Owner, Timing) and the table frame are visible. The frame never looks empty; only the moves fade in.
- **Build 1:** the action rows cascade top to bottom on **one press**. Each `.ns-row` carries its own `opacity:0` plus a transition keyed to `var(--stagger)`, activated when `.ns-rows` gets `.in` (the global `[data-build]` stagger fires only on the build element, so the rows carry their own, per the `.am-links` / `.rtl-bar` convention). Steps of ~0.1s keep a five-row table finishing in well under a second. Beat: "Here is who does what, and by when."
- **Build 2:** the `.foot-line` close fades in. Beat: the one line the room should repeat tomorrow.

Honors `prefers-reduced-motion`: the end-state renders correctly, the motion is instant. In scroll view every row and the close are visible at once.
