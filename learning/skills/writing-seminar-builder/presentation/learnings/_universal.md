# Effective Decks for Executives: Core Learnings (Universal)

*Research-backed principles for building presentations that land with intelligent but non-specialist business audiences. This is the **umbrella** doc; for the job each deck type is doing, also read its companion:*

- [training-decks.md](training-decks.md): teach a concept (build understanding)
- [consulting-decks.md](consulting-decks.md): drive to a recommendation
- [financial-data-decks.md](financial-data-decks.md): make numbers tell a defensible story

*Implementation rules for the web-seminar system (layout primitives, animation, the exact visual system) live in [DESIGN-PRINCIPLES.md](../DESIGN-PRINCIPLES.md). Brand + voice live in the `brand-guide` skill and the training folder's `CONTEXT.md` (layout in the skill's `SKILL.md`).*

---

## The foundational mindset

Executives **scan**. They process a slide in seconds and decide whether to keep paying attention. Everything below serves one goal: instant comprehension with minimal cognitive load. Design isn't about making slides pretty; it's about making the message effortless to receive. (Cognitive Load Theory: the load you add through poor presentation, "extraneous load", is the load you can directly remove through design.)

Two failure modes to avoid:
- **Too much:** dense slides packed edge-to-edge force the audience to hunt for the point.
- **Too little structure:** image-only slides with no anchoring text leave intelligent audiences guessing.

The sweet spot is **visual-first, text-supporting.**

---

## Universal principles (apply to every deck)

1. **One idea per slide.** A single clear message supported by evidence. If the audience has to decode the slide, you've lost them. (If a slide carries two ideas, split it.)

2. **Message-first titles.** The title states the *insight*, not the *topic*.
   - Weak: "Quarterly Results" / "Claude Code Skills"
   - Strong: "Revenue grew 40% on enterprise demand" / "Claude Code cuts implementation time in half" A useful forcing function: if you can't write the so-what title, the slide isn't ready and may not deserve to exist.

3. **White space is a feature, not a gap.** Leave ~15–20% of each slide intentionally empty. Generous margins signal confidence; they create hierarchy by surrounding key elements with room to breathe. A bold statistic in open space lands; the same number buried in a text block disappears.

4. **Visual hierarchy via size, contrast, and placement.** Guide the eye deliberately: titles larger than body, bold/color on the one thing that matters, predictable element positions so the deck feels organized.

5. **Restrained typography.** Two to three font families across the whole deck. Sans-serif for screen. Create contrast through *size and weight*, not by adding fonts.

6. **Disciplined color.** Limit the palette to 3–4 brand shades; use the accent only to highlight the one thing that matters, never for decoration. Always ensure strong text-to-background contrast (accessibility, and readability from the back of the room). Never carry meaning by color alone; reinforce with text, icons, and position.

7. **Consistency builds trust.** Keep layout structure consistent within a deck so the audience never has to recalibrate. The most damaging mistakes break consistency: wrong brand colors, unapproved fonts, off-brand imagery.

8. **Quality imagery only.** Custom or high-quality images that fit the brand. Generic or low-resolution stock undercuts everything else. (When a real asset isn't available, use an honest framed slot, never amateur filler.)

---

## Text vs. visuals: the balance

- The dominant visual occupies roughly **60–70%** of the slide; text **annotates** it rather than explaining separately.
- Replace paragraphs with labeled diagrams (a 3–4 box flow beats five bullets describing a process).
- When bullets are used: **3–4 maximum, each 5–8 words.** They are anchors for your spoken delivery, not complete thoughts. The real explanation is in your voice.
- Concept/definition slides are the one place to allow a little more text, but still pair with a visual.
- This is an attribute of the slide *type*, not a category. Some types are legitimately text-dense (calibration, definition, recap); most are visual-first.

---

## The cognitive backbone (why the above works)

- **Cognitive Load Theory** (Sweller): manage intrinsic load (sequence simple to complex, pre-teach terms), strip extraneous load (cut decoration and redundant words), and spend the freed capacity on germane load (analogies, examples).
- **Mayer's multimedia principles:** pair a word with a relevant visual; signal the one thing that matters; segment into learner-paced chunks; don't read on-screen text verbatim (redundancy); keep labels beside their graphic (spatial contiguity).
- **Primacy–recency:** open with the answer/relevance and close with the recap + one memorable line. (Default rule: the answer lands by ~25% of talk time; punchy send-off before the offer.)

---

## Sourcing & credibility

Every number on a slide carries a credible, named source (and year when it matters), in small muted type near the figure. Credible: named research firms (RAND, Gartner, IDC, Forrester, McKinsey), major publishers (HBR, Fortune, Bloomberg), named surveys (RSM, Gallup), peer-reviewed work, credible named authors. Not credible for a client slide: "some studies say," anonymous blog posts, un-attributed vendor marketing. External frameworks credit their originator (e.g. IndyDevDan for the four-quadrants); frameworks the presenter's own practice originated are taught as the practice's own.

## Audience calibration (setting `audience`)

Write to the audience the owner describes (setting `audience`), for example finance leaders at mid-sized companies. Use numbers and examples at the scale that audience runs, not figures from a different world. For a mid-sized company that means per-seat pricing in the tens of dollars, targeted automation in the hundreds-to-low-thousands per month, run-rate in the low tens of thousands, not $40K bills and 5,000-engineer anecdotes; for a larger or smaller audience, scale the same way. A believable example beats a dramatic one the audience discounts. Stats from a much larger scale are fine only as an explicitly flagged "extreme version of this story."

## Quick self-check before any slide ships

- Can the audience grasp the main message in a few seconds?
- Does the title state an insight, not a topic?
- Is there one idea, and only one, on this slide?
- Is ~15–20% of the slide intentionally empty?
- Two to three fonts max, strong contrast, 3–4 brand shades?
- **Cover-up test:** without the spoken notes, does the slide alone over-share the punchline? It should anchor, not give everything away.
- **Back-row test:** readable from row 6 of a 30-person room?
- **Attribution test:** does every number cite a credible source?
- **Trusted-advisor test:** would the smartest, most senior person in row 2 (for a finance audience, the CFO) feel lectured? If yes, soften.
- For **teaching:** does this slide *build* understanding, or just assert it?
- For **consulting:** does this slide advance the SCQA argument?
- For **financial data:** does one insight lead, with the detail in support?
- Is every image high-quality and on-brand? No em dashes or taglines on the slide?

---

## Sources

Minto, *The Pyramid Principle* · Zelazny, *Say It With Charts* · Tufte (data-ink) · Mayer, *Multimedia Learning* · Sweller et al. (Cognitive Load Theory) · Duarte, *slide:ology* · Reynolds, *Presentation Zen*.
