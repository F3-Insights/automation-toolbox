# Slide Formatting

The per-slide output format used in Step 3 of the workflow. Every slide in the draft deck follows this structure.

---

## Per-slide format

For each slide, produce the following sections in order:

### Slide # and title
A clear, business-outcome-led title wherever possible. The title alone, read out of context, should hint at the slide's payoff.

### Role in the arc
Label one of:
- **Outcome promise** (Slide 1 only)
- **Assumptions** (Slide 2 only)
- **Teaching** (middle slides)
- **Offer** (final 1–2 slides)

This label makes the structure visible at review time.

### Visual concept
Describe what's actually on the slide in prose. If the slide includes a flowchart, table, decision grid, or before/after comparison, **draft it inline**; don't just describe it abstractly. Examples:

- *Flowchart:* "Box A (Inbound ticket) → Box B (Classifier with 3 outputs: routine / nuanced / escalation) → Box C (Draft response) → Box D (Human review gate). Annotate the arrow from B to D with 'confidence < threshold'."
- *Table:* Provide a markdown table with sample rows.
- *Before/after:* Two columns, current state on the left, AI-augmented state on the right, 3–5 rows comparing time, error rate, cost, or whatever the seminar's outcome metric is.
- *Image suggestion:* If a stock image or icon would help, describe it ("a single overflowing inbox, viewed from above"). Otherwise omit.

If the slide is mostly text, list the headline plus 2–4 supporting bullets. Don't pack the slide; the speaker script carries the detail.

**Word budget: ≤40 words of body text per slide** (diagram labels and shape text in flowchart nodes don't count). See `visual-design.md` for full budgets by slide type, font minimums (22pt floor for body text), and the four slide-as-anchor checks every slide must pass.

### Speaker script
**60–120 seconds of natural spoken language.** Not bullet-prose. Should sound like the user on stage, not like a whitepaper or a LinkedIn post.

Rules:
- Open and close the seminar in business language; technology lives in the middle.
- Use contractions, short sentences, occasional rhetorical questions.
- Anchor abstract ideas in concrete examples or one-line stories.
- Avoid "AI can…" sentence openings. Prefer "Your team currently…" or "The problem most companies hit is…"
- Don't recite the slide. The slide is the visual anchor; the script adds the texture the slide can't carry.

### Transition
One sentence that bridges to the next slide. The transition is what the speaker says as the slide changes. It shouldn't recap, it should set up. Examples:
- "So if that's the trap, what does the alternative actually look like?"
- "Which raises the obvious question: how do you keep the human in the loop without slowing everything down?"
- "That's the principle. Here's what it looks like in practice."

### Depth note (teaching slides only)
A one-line flag on where this slide sits on the give/hold line (see `depth-boundaries.md`). If the slide is near the boundary, note what the follow-up offer is that picks up where this slide stops.

Example: *"Near the boundary. Shows the workflow shape but stops before tool configuration. Picks up in the `<Sprint>` offer."*

Omit this section on Slide 1, Slide 2, and the closing offer slide(s).

---

## Deck-level rules

**Slide count.**
- 30 minutes → 10–12 slides total
- 45 minutes → 12–14 slides total
- Slide 1 and Slide 2 are always single slides
- Closing offer is 1–2 slides
- The remainder are teaching slides

**Title voice.** Business-outcome-led wherever possible. "Cutting close cycle time in half" beats "AI in the finance function." Save technology framing for body content.

**Diagram budget.** At least one workflow diagram or architecture sketch in the teaching section. Often the most-remembered slide in the deck.

**The final test.** Before delivering the draft, check: *If an executive saw only Slide 1, the main workflow diagram, and the closing offer slide, would they already understand the business case and what to do next?* If no, the business hook is buried somewhere it shouldn't be.

---

## What the speaker script is not

- Not a transcript of every word the speaker will say
- Not a list of bullet points to read aloud
- Not a recap of the visual on the slide
- Not a whitepaper paragraph in disguise

It's a verbal performance score: the natural arc of what the speaker says while the slide is up, written in their voice, sized to the time the slide deserves.
