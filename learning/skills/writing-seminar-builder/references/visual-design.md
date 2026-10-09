# Visual Design

How slides actually look. The structural counterpart is `narrative-arc.md` (where slides sit in the story) and `slide-formatting.md` (the per-slide markdown format). This file is about what's on the slide visually, and what isn't.

---

## The core principle

**A slide is a visual anchor for what the speaker says, not a script for the audience to read.**

If the audience can read the slide and get all the substance, the speaker isn't adding value, and the audience will read the slide instead of listening to the speaker. Every word on the slide either earns its place by being a *visual hook* (a phrase, a number, a label, a callout) or it belongs in the speaker notes.

The substance lives in the notes pane. The slide lives on stage.

This is the principle behind Garr Reynolds' *Presentation Zen*, Nancy Duarte's slide vs. slidedoc distinction, and Guy Kawasaki's 10/20/30 rule. We're adopting the *spirit* of those: less text, bigger fonts, visuals first.

---

## Word budget per slide

**Target: ≤40 words of body text per slide.** Diagram labels and shape text inside flowchart nodes don't count against this budget; they're visual elements. Bullets and prose blocks do count.

| Slide type | Body-text budget |
|---|---|
| Title slide | ≤15 words (title + subtitle) |
| Assumptions slide | ≤60 words (it's denser by design: 4 short bullets) |
| Hook / answer / expansion slides | ≤40 words |
| Demo / before-after slides | ≤30 words per column |
| Workflow backbone diagram | ≤20 words outside the diagram itself |
| Punchy send-off | ≤15 words |
| Offer cards | ≤30 words per card |
| CTA | ≤10 words |

If a slide is over budget, the fix is **cut text**, not shrink font. The speaker script in the notes pane absorbs whatever you cut.

---

## Font size minimums

| Element | Minimum size | Typical size |
|---|---|---|
| Slide title | 28pt | 32–36pt |
| Slide subtitle | 18pt | 20–22pt |
| Body text / bullets | **22pt** | 22–26pt |
| Bullet sub-text | 16pt | 16–18pt |
| Diagram labels (inside shapes) | 11pt | 11–13pt |
| Callouts / quotes | 18pt | 18–22pt |
| Captions / footnotes | 12pt | 12–14pt |

**22pt is the floor for body text on a projected seminar slide.** Below that, the back row can't read it. If body text won't fit at 22pt, you have too much text. Cut it, don't shrink it.

(These are smaller than Kawasaki's strict 30pt minimum because seminar decks often have side-by-side comparisons and dense diagrams that need a bit more room. But 22pt is the hard floor; titles and primary callouts should still be 28pt+.)

---

## Visual-first preference

When in doubt, **draw it.** A slide with a clean diagram + three labeled phrases beats a slide with five bullets every time. Reach for these visual patterns before reaching for bullets:

| Pattern | Use for | Helper |
|---|---|---|
| Flowchart / process diagram | Workflows, sequences, the backbone diagram | `flowkit.serpentine_flow` / `linear_flow` |
| Before/after comparison | Demonstrating the change | Two-column with `add_text` |
| Big number + label | A single stat that anchors a point | Large `add_text` size=72+ |
| Side-by-side cards | Three options, three principles, three patterns | Three-column cards via `add_rect` + `add_text` |
| Maturity ladder | Tiers of capability | Stacked `add_rect` with tier labels |
| Decision matrix | Mapping decision types to patterns | Table via `add_rect` rows |
| Single quote / principle | The punchy send-off | Large centered `add_text` |

If the visual concept on a slide is "a list of bullets," ask whether the underlying idea could be shown as one of the patterns above instead.

---

## Anti-patterns (what not to do)

| Anti-pattern | Why it fails | Fix |
|---|---|---|
| Full sentences in bullets | Audience reads instead of listening | Cut to phrases (3–5 words) |
| Paragraphs of body text on a slide | The slide becomes the talk; the speaker becomes redundant | Move the prose to speaker notes; keep 2–3 anchor phrases on the slide |
| 6+ bullets on one slide | Audience can't track them; speaker rushes | Two slides, or convert to a visual (table, comparison, diagram) |
| Body text below 18pt | Back of the room can't read it | Cut text until it fits at 22pt |
| Italic body text for emphasis | Italic at small sizes is hard to read | Use color or bold instead |
| Both header and subheader text on the same line as bullet content | Visual hierarchy collapses | Stack head over sub-text, indent the sub |
| Tables denser than 5 rows × 4 cols | Audience can't scan | Split or convert to two slides |
| Generic stock imagery as decoration | Doesn't anchor anything; looks like a sales deck | Replace with a real diagram or omit |

---

## Slide-as-anchor check (run before locking each slide)

Before finalizing each slide, ask:

1. **The cover-up test.** If you covered the speaker notes and just showed the slide, would the audience get the punchline? *They should not.* If yes, your slide is doing the speaker's job; move text to notes.
2. **The 5-second test.** Look at the slide for 5 seconds and look away. What do you remember? *That memory is what the slide is teaching.* If what you remember is "lots of bullets," the slide isn't teaching anything specific.
3. **The back-row test.** Imagine the slide projected to a 30-person conference room. Can someone in row 6 read the body text? If not, fonts are too small or there's too much text.
4. **The visual-first test.** Could this slide be a diagram, table, or comparison instead of bullets? If yes, switch.

If a slide fails any of the four tests, fix it before declaring the deck done. Use the visual verification loop in Step 4 (render previews, look at the PNGs) to catch what slipped through.
