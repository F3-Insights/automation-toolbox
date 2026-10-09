---
name: brand-guide
description: "Reference loaded by other skills, not for a user request: how to apply a house brand (palette, type, voice and tone, deck rules) to any branded output, with the F3 Insights brand as the worked example. Load it before building a deck, a post, a landing page or any other branded piece."
user-invocable: false
---

# Brand guide

A house brand is four things: a small palette with a role for each color, one or two typefaces, a written voice, and a few layout rules for decks. This skill says how to apply each one. The owner's own brand values replace the worked example wherever the caller or the rules file supplies them; without them, use the example in `worked-example.md`.

## Files here

- `voice-and-tone.md`: the written voice for branded copy, its rules, the adversarial to additive substitution table, the anti-patterns and the tone test.
- `worked-example.md`: the F3 Insights palette and type, as a filled-in example of the shape a house brand takes.

## Palette

- Keep the palette small: one dominant color, one accent, one muted text color, and white.
- Give every color a role (headers, accent, body text, background) and use it only in that role.
- The accent is scarce. One or two accent elements per slide or screen; overuse cheapens it.
- No other colors unless data semantics need them (red for failure, green for success). A third brand color is a decision for the owner, not something a builder introduces.
- Define colors once, as named tokens (CSS custom properties or a constants block), and reference the names. Hard-coded hex values scattered through a build drift apart.

## Type

- One family for body and headings, one monospace for code.
- Fonts must be installed wherever the file renders. A PowerPoint file opened on a machine without the font substitutes another and may break the layout; an HTML deck should load the font itself or fall back to a named system font.

## Decks

- One idea per slide.
- Message titles: the title states the point the slide proves, not its topic.
- White space is part of the layout; do not fill it.
- Keep text density low and balance text against a visual. If a slide needs a paragraph, it is a document, not a slide.
- The detailed HTML deck system (layout primitives, slide types, reusable elements) lives in the `writing-seminar-builder` skill (learning department).

## Voice

Read `voice-and-tone.md` before writing branded copy. The `unslop` skill and its sub-skills are the editing pass; this voice sits on top of them for anything that carries the brand.
