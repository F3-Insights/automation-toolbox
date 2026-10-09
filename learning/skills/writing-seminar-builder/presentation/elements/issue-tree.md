# Element: Issue / driver tree (MECE)

A left-to-right MECE decomposition. A root claim or metric sits on the left and branches, through thin connector lines, into two to four child nodes on the right that are mutually exclusive and collectively exhaustive: each child is a distinct piece, and together they fully account for the root. An optional second level drills one child into its own sub-parts. The parent always reads as the sum or summary of its children, so the eye can verify the logic top to bottom.

- **Slide type:** Issue / driver tree (Compare & decide). See [`../slide-types/_INDEX.md`](../slide-types/_INDEX.md).
- **Use it for:** opening up a single metric, problem, or claim into its parts so the audience sees the structure and the one branch worth acting on. The root states what is under examination; the children are the MECE breakdown.
- **Density:** V/B. **Layout:** `data-layout="issue-tree"` (caps the figure clear of the footer chrome and centers a shorter tree with `margin-block: auto`).
- **Don't:** stack more than four first-level children or go past one extra level, and don't let the children overlap (a list of grievances is not a tree) or leave a gap (then it is not collectively exhaustive). Contributions are illustrative or named-benchmark figures, never live client financials.

## CSS / asset dependencies

- Styles: the `.it-*` rules added to `deck-kit/slides.css`, plus the `[data-layout="issue-tree"]` cap.
- Connectors are **inline SVG** (static geometry, uniform slide scale, no text inside, so no rasterizer distortion per DESIGN-PRINCIPLES §5.5). The line weight matches the deck arrow system at 2px to 2.5px in `var(--navy)`.
- Reuses `.slide-head--assert` (assertion headline) and `.foot-line` (the gold italic "so what" line) from the existing primitives.
- No icons required. The focal accent is the gold root node; everything downstream is quiet navy.

## Variants

- **Two to four children (default).** One level: root to children. Adjust `--it-rows` (the child count) so the connector fan and node column stay centered on the root.
- **Two-level drill.** Give one child a `.it-children--sub` group to its right and a second connector fan. Keep the rest of the first level flat so the eye knows which branch was opened.
- **Driver tree (with contributions).** Each child carries an illustrative `.it-share` (e.g. a percentage or a named-benchmark figure with its source). The shares should sum to the root, reinforcing MECE.

## Paste-ready markup

```html
<section class="slide" data-layout="issue-tree" data-mood="paper">
  <div class="slide-pad">
    <header class="slide-head slide-head--assert">
      <h2>Three pieces explain the nine weeks; one carries the most.</h2>
    </header>

    <div class="it-tree" style="--it-rows: 3">
      <!-- ROOT: the claim under examination (gold focal) -->
      <div class="it-root" data-build="1">
        <span class="it-root-tag">Time to onboard a new client</span>
        <span class="it-root-val">9 weeks</span>
        <span class="it-root-note">Average, last 20 engagements</span>
      </div>

      <!-- CONNECTOR FAN: root to three children, static SVG -->
      <svg class="it-links" viewBox="0 0 120 300" preserveAspectRatio="none"
           data-build="2" aria-hidden="true">
        <path class="it-link" d="M0,150 C60,150 60,40 120,40"/>
        <path class="it-link" d="M0,150 C60,150 60,150 120,150"/>
        <path class="it-link" d="M0,150 C60,150 60,260 120,260"/>
      </svg>

      <!-- CHILDREN: MECE parts, cascade on the build-2 press -->
      <div class="it-children" data-build="2">
        <div class="it-node" style="--stagger: 0s">
          <span class="it-node-name">Data and access setup</span>
          <span class="it-node-desc">Provisioning, permissions, system handshakes</span>
          <span class="it-share">4 wks</span>
        </div>
        <div class="it-node" style="--stagger: .12s">
          <span class="it-node-name">Discovery and scoping</span>
          <span class="it-node-desc">Interviews, current-state mapping, sign-off</span>
          <span class="it-share">3 wks</span>
        </div>
        <div class="it-node" style="--stagger: .24s">
          <span class="it-node-name">Build and handover</span>
          <span class="it-node-desc">Configuration, review, training</span>
          <span class="it-share">2 wks</span>
        </div>
      </div>
    </div>

    <p class="foot-line" data-build="3">Access setup is the longest piece, so it is the first place to look.</p>
  </div>
  <footer class="slide-chrome"><span>SECTION NAME</span><span><span class="num">07</span> / NN</span></footer>
  <aside class="notes"><span class="label">Speaker notes</span><p>...</p></aside>
</section>
```

## Animation

- **Entry:** the assertion headline is visible. The tree frame (root box outline, child boxes empty, the column gutter) reads from slide entry so the slide never looks empty.
- **Build 1:** the root node fills in, lighting gold. One press. This anchors the claim being decomposed.
- **Build 2:** the connector fan and the children reveal on a single press. The three children cascade left-figure-to-bottom with their inline `--stagger` (0s, .12s, .24s), and the SVG connector paths trace in over the same beat. The children carry their own `opacity:0` plus a transition keyed to `var(--stagger)` that activates when `.it-children` gets `.in`, so the cascade does not depend on the global `[data-build]` stagger (same discipline as `.am-link`).
- **Build 3:** the gold `.foot-line` lands the "so what", naming the branch to act on. One press.

Total: three presses, frame to root to branches to takeaway, matching the frame to setup to relationships to takeaway template in DESIGN-PRINCIPLES §6.2.
