# Element: System wiring flow (wiring-flow)

A left-to-right "small system" diagram: a column of source nodes feeds a gold core that carries its own numbered steps, which feeds a result node, with gold connectors between the zones and mono stage labels across the top. It renders a real, multi-step artifact (a Skill, a pipeline, an automation) as architecture the audience can read at a glance, in the thin-stroke house idiom of a system architecture diagram, but in pure HTML/CSS, so it scales with the uniform slide scale and never distorts.

- **Slide type:** Mental model / inputs→process→outputs (Demonstrate). See [`../slide-types/_INDEX.md`](../slide-types/_INDEX.md) §3.
- **Use it for:** showing how one concrete system is wired (what it reads, what it does step by step, what it produces) when a bullet list would hide the structure and you want it to feel built, not explained.
- **Density:** V. **Layout:** `data-layout="wiring"`.
- **Don't:** stack more than ~3 source nodes or ~5 core steps (the row gets tall and the connectors lose their center); draw true many-to-one converging lines (the single gold arrow per zone reads as the flow; keep it); use it for an abstract sequence with no real inputs/outputs (that's a Worked example or a Step-by-step build); let the core step list exceed the source column height by much, or the columns stop reading as peers.

## CSS / asset dependencies

- Styles: the `.wiring` / `.w-*` rules in `deck-kit/slides.css`. Pure CSS + the Lucide sprite for node icons; no SVG coordinates to hand-place.
- Node icons from `deck-kit/icons.svg` (e.g. `#icon-mail`, `#icon-trending-up`, `#icon-file-text`, `#icon-notebook-pen`, `#icon-calendar`).
- The gold connector reuses the `.lifecycle` / `.sf-arrow` arrow data-URI.
- Reuses `.slide-head--assert`, `.foot-line`, the `[data-build]` / `--stagger` cascade, and brand tokens only (`--navy`, `--gold`, `--ink`, `--muted`, `--line`, `--line-soft`, `--mono`, `--grotesk`, `--sans`).

## Variants

- **Source count.** One to three `.w-node` cards in the left `.w-body`. A `.w-node--file` is dashed: the house convention for "your own file / config" vs a solid node for a live service or connection.
- **Core steps.** The `.w-skill` core is gold; its `<ol>` is the multi-step body. Swap `.ws-tag` (the file/kind label) and `.ws-name` (the artifact name). Bold the load-bearing word in each step with `<b>` (renders gold).
- **EAF call-back (optional).** Tag nodes with `.wn-tag` (Context / Tool, mono, quiet) and the core with `.wn-tag--prompt` (gold) to map the system back onto the Effective Agentic Framework, then add an `.eaf-ref` line above the takeaway that points Context/Tools to their sibling seminars. This is how a Skills deck can tie a mid-deck slide back to the EAF opener.
- **Result node.** A single `.w-out` (also a `.w-node`) with a short bulleted payoff. Keep it free of chips; it's the deliverable, not a category.

## Paste-ready markup (a Skills deck's "Weekly Review", with the EAF call-back)

```html
<section class="slide" data-layout="wiring" data-mood="paper">
  <div class="slide-pad">
    <header class="slide-head slide-head--assert"><h2>Real but simple Skill architecture: the &ldquo;Weekly Review&rdquo;</h2></header>
    <div class="wiring">
      <div class="w-col w-col--in">
        <span class="w-stage-lbl">What it reads</span>
        <div class="w-body">
          <div class="w-node">
            <div class="wn-head"><svg class="icon" aria-hidden="true"><use href="../../../Resources/presentation/deck-kit/icons.svg#icon-mail"/></svg><span class="wn-name">Your inbox</span><span class="wn-tag">Tool</span></div>
            <p class="wn-role">This week's mail, read-only</p>
          </div>
          <div class="w-node w-node--file">
            <div class="wn-head"><svg class="icon" aria-hidden="true"><use href="../../../Resources/presentation/deck-kit/icons.svg#icon-trending-up"/></svg><span class="wn-name"><span class="f">goals.md</span></span><span class="wn-tag">Context</span></div>
            <p class="wn-role">Your priorities, in your words</p>
          </div>
          <div class="w-node w-node--file">
            <div class="wn-head"><svg class="icon" aria-hidden="true"><use href="../../../Resources/presentation/deck-kit/icons.svg#icon-file-text"/></svg><span class="wn-name"><span class="f">review-template.md</span></span><span class="wn-tag">Context</span></div>
            <p class="wn-role">How you want the brief laid out</p>
          </div>
        </div>
      </div>
      <div class="w-arrow" data-build="1" aria-hidden="true"></div>
      <div class="w-col w-col--skill">
        <span class="w-stage-lbl">The Skill · four steps</span>
        <div class="w-body">
        <div class="w-skill" data-build="1">
          <span class="ws-tag">SKILL.md</span>
          <div class="ws-name"><span>weekly-review</span><span class="wn-tag wn-tag--prompt">Prompt · today's focus</span></div>
          <ol>
            <li>Pull this week's <b>important</b> email</li>
            <li>Weigh each item against your <b>goals</b></li>
            <li>Flag what needs your <b>reply or a decision</b></li>
            <li>Lay it out in your <b>template</b></li>
          </ol>
        </div>
        </div>
      </div>
      <div class="w-arrow" data-build="2" aria-hidden="true"></div>
      <div class="w-col w-col--out">
        <span class="w-stage-lbl">What you get</span>
        <div class="w-body">
        <div class="w-out w-node" data-build="2">
          <div class="wn-head"><svg class="icon" aria-hidden="true"><use href="../../../Resources/presentation/deck-kit/icons.svg#icon-calendar"/></svg><span class="wo-name">Your Monday review</span></div>
          <ul>
            <li>Top priorities for the week</li>
            <li>Threads waiting on your reply</li>
            <li>Where you're slipping against your goals</li>
          </ul>
        </div>
        </div>
      </div>
    </div>
    <p class="eaf-ref" data-build="3">Back to the framework we opened with: your files are <b>Context</b>; reaching your inbox and emailing the brief back are <b>Tools</b>, and each gets its own seminar (<em>Getting Started with Data</em>, <em>Getting Started with Tools</em>). Today we stay on the Skill itself: the <b>Prompt</b>.</p>
    <p class="foot-line" data-build="3" style="--stagger: .1s">Three ordinary files in; the same trusted brief out, every Monday.</p>
  </div>
  <footer class="slide-chrome"><span>Section name</span><span><span class="num">10</span> / 16</span></footer>
  <aside class="notes"><span class="label">Speaker notes</span><p>...</p></aside>
</section>
```

Structure note: each `.w-col` holds a top `.w-stage-lbl` (always visible, pinned to a shared top row) and a `.w-body` that vertically centers its card(s). That is what keeps the three stage labels on one baseline while the short result card stays centered against the tall core, and what lets the connectors land on the cards' shared center line. Drop the `.eaf-ref` line and the `.wn-tag` chips for a plain system diagram with no framework call-back.

## Animation

- **Entry:** the three stage labels and the source nodes are visible (frames never fade, DESIGN-PRINCIPLES §6.3). The board reads as "here are the inputs."
- **Build 1:** the first gold connector and the Skill core (with its numbered steps) appear: the system starts reading.
- **Build 2:** the second connector and the result node appear: the output.
- **Build 3:** the framework call-back line and the gold takeaway land together (the takeaway carries a small `--stagger` so it follows the reference).
- Three presses total, revealed in the system's own left-to-right order. Honors `prefers-reduced-motion` and renders fully in `body.mode-scroll` (`.w-arrow`, the `[data-build]` cards, and the lines all resolve to visible).
