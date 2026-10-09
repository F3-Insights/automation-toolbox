# Element: Section divider

A near-empty topic-boundary slide that resets attention at the seam between two major parts of a talk. One large section title sits in the optical center of a full-bleed canvas, introduced by a small mono section number, underlined by a single short gold rule, with an optional "stop N of M" progress cue that echoes the agenda. Generous space is the point: nothing competes, the room re-orients, the next section opens clean. One gold accent: the rule plus the current progress pip.

- **Slide type:** Section divider (Orient). See [`../slide-types/section-divider.md`](../slide-types/section-divider.md).
- **Use it for:** the boundary between two major sections of a longer seminar, to reset attention before the next run of meat slides. Setup slide, no leave-behind.
- **Density:** V. **Layout:** `data-layout="divider"` (centers the block in the canvas and clears the footer chrome).
- **Don't:** write an assertion headline here (this is a setup slide, so it takes a topic title, not a full-sentence takeaway), stack a subtitle paragraph, add a second accent, or use it between adjacent slides inside one idea.

## CSS / asset dependencies

- Styles: the `.divider-block*` rules in `css_additions` (appended to `deck-kit/slides.css`), plus the global `[data-build]` fade already in `slides.css`.
- Reuses existing primitives: the full-bleed navy hero pattern of `.slide--sendoff` (`.blueprint`, centered `.slide-pad`), the `.slide-chrome` footer, and the build system. The warm variant reuses `--paper-warm` and ink tokens.
- Brand tokens only: `--navy`, `--gold`, `--gold-foil`, `--paper-warm`, `--obsidian`, `--muted`, `--grotesk`, `--mono`, and `color-mix` tints of `--navy` / `--gold`. No icons, no SVG. The title is HTML text, so it scales cleanly with the uniform slide scale.

## Variants

- **`data-mood="navy"`** (default): full-bleed navy, white title, gold rule, gold-foil section number. The calm, declarative reset that contrasts hardest with the white teaching slides on either side. Carries the optional `.blueprint` grid for atmosphere.
- **`data-mood="warm"`**: warm-paper background, obsidian title, gold rule and section number. A softer editorial pause for a reflective section seam. Identical structure; drop the `.blueprint`.
- **Progress cue (optional).** Add the `.divider-progress` row of `.divider-pip` items, one per major section, and mark the section you are entering with `.divider-pip--here`. Omit the whole row for the barest possible divider. The pip count should match the stops in your agenda.

## Paste-ready markup (navy, with progress cue)

```html
<section class="slide" data-layout="divider" data-mood="navy">
  <div class="blueprint"></div>
  <div class="slide-pad">
    <div class="divider-block">
      <p class="divider-num" data-build="1">Part Two</p>
      <h2 class="divider-title" data-build="1" style="--stagger: .1s">Putting AI to work in the close</h2>
      <div class="divider-rule" data-build="1" style="--stagger: .2s"></div>
      <ul class="divider-progress" data-build="1" style="--stagger: .3s" aria-label="Stop 2 of 4">
        <li class="divider-pip"><span class="divider-pip-dot"></span>Where AI stands today</li>
        <li class="divider-pip divider-pip--here"><span class="divider-pip-dot"></span>Putting it to work in the close</li>
        <li class="divider-pip"><span class="divider-pip-dot"></span>Governing the rollout</li>
        <li class="divider-pip"><span class="divider-pip-dot"></span>Your first ninety days</li>
      </ul>
    </div>
  </div>
  <footer class="slide-chrome"><span>Demo</span><span><span class="num">07</span> / 13</span></footer>
  <aside class="notes"><span class="label">Speaker notes</span><p>This is a breath, not a teaching slide. Let it land for a beat before you speak. We have just finished where AI stands today, so name the seam out loud: the next stretch is about putting it to work inside one real process, the monthly close. The progress row maps back to the agenda you set at the top, so the room can see we are stop two of four and roughly a third of the way through. Keep your own commentary short here, then move into the first meat slide of the section.</p></aside>
</section>
```

## Animation

- **Build 1:** the section number, the title, the gold rule, and the progress cue all fade in together on one press, cascading top to bottom via inline `--stagger` (number, then title ~0.1s behind, then rule, then the progress row). This is the single beat where the speaker names the seam. Minimal by design: one press carries the whole reset.

The full-bleed background and the footer chrome are visible from slide entry, so the slide reads as a deliberate pause rather than an empty one. In scroll mode every build is visible at once, as the global build rules already handle.
