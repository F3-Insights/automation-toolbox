# Element: Knowledge-check (question with adjacent reveal)

A retrieval slide built for participation. One large question sits at the top, two to four lettered options sit below it, and the answer plus the one-line reason it is right are revealed **on the same slide, beside the options** (spatial contiguity), never on a later slide. On the reveal the correct option lights gold and a navy why-panel appears next to the option set, so the audience reads the feedback right where they made their guess.

- **Slide type:** Knowledge-check / question (Reframe & check). See [`../slide-types/knowledge-check.md`](../slide-types/knowledge-check.md).
- **Use it for:** re-engaging the room mid-session, or locking in a concept that the next stretch of the talk depends on. One, at most two, per deck.
- **Density:** T. **Layout:** `data-layout="knowledge-check"`.
- **Don't:** defer the answer to the next slide, the whole point is that the feedback lands adjacent. Don't make the wrong options silly, plausible distractors make the retrieval real. Don't frame the reveal as a verdict on the audience: it confirms a guess, it does not grade homework. One gold accent only, on the correct option and the why-panel.

## CSS / asset dependencies

- Styles: the `.knowledge-check*` rules in `deck-kit/slides.css`, plus the `[data-layout="knowledge-check"] .knowledge-check { margin-block: auto; }` vertical-balance rule that floats the body to the optical center.
- Uses the assertion-style head (`.slide-head--assert`) so the question reads as one line. The question itself carries the meaning, so no eyebrow.
- No icons or sprite required. The correct-option check glyph is drawn as a gold CSS background data-URI (the single accent), so there is no sprite dependency.

## Variants

- **Single-question (default).** One question, a column of lettered options on the left, the reveal panel on the right. This is the markup below and the usual case.
- **Poll prompt.** Swap the lettered options for a one-line `.kc-poll` prompt ("Show of hands:") with two named camps, and keep the same right-side reveal. Use when you want a live read of the room rather than a single right answer; the reveal panel then states what the split usually looks like and what it means.

## Paste-ready markup (single-question; realistic mid-market example)

```html
<section class="slide" data-layout="knowledge-check" data-mood="paper">
  <div class="slide-pad">
    <header class="slide-head slide-head--assert">
      <h2>Where does the first hour of AI payback usually come from?</h2>
    </header>
    <div class="knowledge-check">
      <ul class="kc-options" data-build="1">
        <li class="kc-option"><span class="kc-key">A</span><span class="kc-opt-text">Replacing a core system with an AI-native platform</span></li>
        <li class="kc-option"><span class="kc-key">B</span><span class="kc-opt-text">Hiring a data science team to build a custom model</span></li>
        <li class="kc-option kc-option--correct"><span class="kc-key">C</span><span class="kc-opt-text">Pointing a capable model at the busywork already on your desk</span></li>
        <li class="kc-option"><span class="kc-key">D</span><span class="kc-opt-text">Waiting for the tools to mature another year before starting</span></li>
      </ul>
      <div class="kc-reveal" data-build="2">
        <span class="kc-reveal-label">The answer</span>
        <p class="kc-reveal-head"><b>C.</b> The fast return is in the work you already do.</p>
        <p class="kc-reveal-why">Drafting, summarizing, and routing inside today's
          inbox and CRM pays back in weeks, with no migration and no new team. The
          bigger moves come later, once that habit is in place.</p>
      </div>
    </div>
  </div>
  <footer class="slide-chrome"><span>Quick check</span><span><span class="num">08</span> / 13</span></footer>
  <aside class="notes"><span class="label">Speaker notes</span><p>Let me pause and put this back to you, because the next stretch builds on the answer. Read the four, pick one, hands up. Take a real beat here: the show of hands is the point, and the room re-engages the moment they have to commit to a guess.</p><p>Then reveal C and say why beside it: the first hour of payback is almost always the busywork already on someone's desk, drafting, summarizing, routing, not a platform swap or a new hire. Frame it as confirmation, not a grade: whoever guessed A or B was reasoning from how big capabilities used to arrive. We are going to spend the next few slides on exactly where that first hour lives in your operation.</p></aside>
</section>
```

## Animation

- **Build 1:** the question is visible from slide entry (it lives in the head); on the first press the lettered options cascade in left-to-right via the inline `--stagger` on each `.kc-option`, so the whole option set arrives on **one** press. The speaker reads the options and takes the show of hands. Nothing yet marks the correct one.
- **Build 2:** the correct option lights gold (its gold left-rule, gold key chip, and the gold check glyph appear) and the navy `.kc-reveal` why-panel fades in beside the options on the same press. The feedback lands adjacent to the guess.

The options are peers introduced as a group, so they cascade on one press; the reveal is a distinct beat and takes the next press. The block is vertically centered via `margin-block: auto` so it never clings to the top. The correct-option styling keys off the parent build reaching `.in` (not the global `--stagger`), so the highlight pops cleanly on build 2 rather than fading with the option's entrance.
