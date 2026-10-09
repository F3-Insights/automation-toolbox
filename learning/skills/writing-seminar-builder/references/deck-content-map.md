# Deck content map, and the family template

Two planning documents written before a single slide is built. Used by `writing-seminar-builder` step 2; each deck's map sits beside its `index.html` in `Content/Seminars/<slug>/` in the training folder (setting `training_dir`).

## `_content-map.md`, one per deck

Written after the interview and before the outline is approved. It is the argument the deck makes, in a form that can be red-teamed without any visuals.

- **Spine.** One sentence: the claim the whole deck exists to land.
- **Arc.** Three or four sentences: where the audience starts, what turns, where they end.
- **(a) and (b).** For a teaching deck: (a) what the audience is assumed to know walking in, (b) what they must be able to do walking out. The red-team's contract question is "starting from (a), did this deliver (b)?"
- **Beat table.** One row per slide:

| # | Beat title | Job | Shape | Slide type |
|---|---|---|---|---|
| 1 | Title | orient | `setup` | title |
| 2 | Where we assume you are | orient | `setup` | assumption |
| 3 | The named concept | frame | `setup / named concept` | framework |
| 4 | First real thing | teach | `meat` | worked example |
| 6 | The hinge | turn | `meat (the pivot)` | contrast |
| … | | | | |
| n-1 | Monday move | act | `landing` | action |
| n | Offer or close | close | `landing` | offer |

**Job** is one of orient, frame, teach, turn, prove, act, close. **Shape** is `setup`, `meat`, or `landing`, and `meat` must carry more than half the rows or the deck is all throat-clearing. **Slide type** names an entry in this skill's `presentation/slide-types/_INDEX.md`.

Pattern-budget check before approval: no two consecutive `meat` rows with the same slide type; at most one framework slide; at least one row whose job is `prove` with a number or artifact in it.

## Family template: "Getting Started with X"

A repeatable twelve-slide shape for a series where each deck swaps one topic. Three variables per instance and nothing else changes:

1. **Variable 1, slide 3.** Which quadrant of the shared framework this topic lights up.
2. **Variable 2, slide 5.** The business analogy that makes the topic concrete for this audience.
3. **Variable 3, slide 10.** The lifecycle node names for this topic's workflow.

The twelve slides: title · where we assume you are · the framework, one quadrant lit · what X is · the analogy · what X is and isn't (the hinge) · what's already accessible · a worked example · what goes wrong · the lifecycle · Monday move · offer.

Holding the shape constant is what makes the series recognisable; changing only the three variables is what keeps each deck from being the previous one with the nouns swapped.
