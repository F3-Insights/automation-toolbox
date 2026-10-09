# Deck Styling

The visual style for seminar decks built by this skill. F3 Insights is the default brand. To rebrand, edit this file **and** the matching constants at the top of `scripts/deckbuilder.py`; they're intentionally duplicated so the markdown stays human-readable and the Python stays executable.

This file covers two things: the visual style tokens (colors, fonts, dimensions) and the slide-type catalog (what layouts the helpers support and when each is appropriate).

---

## Visual style tokens

### Palette: F3 Insights brand

| Token | Hex | Role |
|---|---|---|
| `NAVY` | `#1E3A6E` | Primary text, title-slide hero band |
| `BRONZE` | `#A67C52` | Accent: subtitles, top chrome bar, callouts (alias: `ORANGE`) |
| `BRONZE_LIGHT` | `#B88B5E` | Secondary accent (rings, hover states) |
| `GRAY` | `#4B5563` | Muted body text, footnotes, slide-number footer |
| `LIGHT_GRAY` | `#F9FAFB` | Card and panel backgrounds |
| `BORDER_GRAY` | `#E5E7EB` | Borders, dividers |
| `CODE_BG` | `#1F2937` | Code block background (dark) |
| `CODE_FG` | `#E6EDF3` | Code block text |
| `WHITE` | `#FFFFFF` | Hero text on color bands |
| `ACCENT_RED` | `#B41E1E` | Warnings, "before" / "bad" columns |
| `ACCENT_GREEN` | `#1A7F37` | Success, "after" / "good" columns |

### Typography

| Token | Value | Used for |
|---|---|---|
| `TITLE_FONT` | `Inter` | Slide titles, hero text |
| `BODY_FONT` | `Inter` | Bullets, body text, captions |
| `CODE_FONT` | `Consolas` | Code blocks, monospace callouts |

Inter is a Google Font. If it's not installed on the rendering machine, PowerPoint falls back to Calibri or system-ui. Decks remain legible either way.

### Dimensions

| Token | Value | Notes |
|---|---|---|
| `SLIDE_W` | `13.333 in` | 16:9 widescreen |
| `SLIDE_H` | `7.5 in` | 16:9 widescreen |
| `MARGIN` | `0.6 in` | Standard left/right padding on every slide |

### Chrome conventions

Every non-title slide should call `add_chrome(slide, slide_num, total, section)` which adds:

- A `0.15 in` BRONZE accent bar at the top edge of the slide
- A section name (italic, GRAY, size 10) bottom-left
- The slide number (`N / total`) bottom-right

The title slide (Slide 1) skips chrome and uses a full-bleed color band instead.

### Title positioning

- Title text: navy, bold, 32 pt, starts at `0.45 in` from top
- Optional subtitle: bronze, italic, 18 pt, starts at `1.25 in`
- Body content: typically begins at `2.1 in` from top, leaving room for title + subtitle

---

## Slide-type catalog

Seven layouts are supported by the helpers in `deckbuilder.py`. The "Visual concept" field in your Step-3 markdown outline should map onto one of these.

| Layout | When to use | Key helpers |
|---|---|---|
| **Title slide** | Slide 1 (outcome promise). Full-bleed NAVY band, bronze accent stripe, hero title in WHITE | `add_blank_slide` + two `add_rect` bands + `add_text` for hero copy |
| **Bullet slide** | Standard teaching slide. Title + 3–5 bullets, optional sub-text under each | `slide_title` + `add_bullets` |
| **Three-column cards** | Comparisons, "three pillars," tier menus, side-by-side categories | `add_rect` × 3 (colored headers + LIGHT_GRAY bodies) + `add_text` |
| **Two-column split** | Before/after, current vs. AI-augmented, problem/solution | `slide_title` + two `add_text` blocks side-by-side; optional ACCENT_RED / ACCENT_GREEN column headers |
| **Stepped flow** | Numbered workflow or process diagram (e.g., "Inbound → Classify → Draft → Review") | Sequence of `add_rect` boxes with arrows drawn as thin rectangles + `add_text` |
| **Table layout** | Decision grids, comparison tables, criteria lists | Rows of `add_rect` (alternating LIGHT_GRAY / WHITE) + `add_text` for each cell |
| **Closing offer** | Final 1–2 slides. Horizontal cards for the tier menu (the three or four offers from `closing-offer-menu.md`) | One `add_rect` card per tier + colored headers + `add_text` for tier descriptions; bottom CTA line |

### Mapping the outline to a layout

When you read each slide's "Visual concept" in the Step-3 markdown:

- "Flowchart with boxes and arrows" → **Stepped flow**
- "Markdown table comparing X to Y" → **Table layout** (or **Two-column split** if only two columns)
- "Before/after columns" → **Two-column split**
- "Three pillars" or "three pricing tiers" → **Three-column cards**
- "Bulleted list" or "headline plus 2–4 supporting bullets" → **Bullet slide**
- Slide 1 specifically → **Title slide**
- Final 1–2 slides (offer) → **Closing offer**

If the visual concept calls for something none of the layouts cover, compose it from the primitives (`add_rect`, `add_text`, `add_bullets`, `add_code`) rather than forcing it into a near-miss layout.

---

## Flowcharts: use `flowkit`, not `add_rect`

For any slide that's a process flow, workflow diagram, or step sequence (including the required Workflow Backbone Diagram from `workflow-depth.md`), use `scripts/flowkit.py`, not rectangles painted to look like flowchart boxes. Flowkit uses native python-pptx flowchart shapes (rounded rectangles, diamonds, directional arrows) that look professional and remain editable in PowerPoint.

Import alongside `deckbuilder`:

```python
from flowkit import (
    linear_flow, serpentine_flow, cycle_flow,
    add_process_node, add_hitl_gate, add_decision_node,
    add_directed_arrow, add_loopback_bar,
)
```

### High-level layout functions

| Function | Use for | Visual |
|---|---|---|
| `linear_flow(slide, top_y, left_x, total_w, node_h, steps, hitl_indices=None)` | Short L-to-R process flows (3–5 steps) | Row of rounded boxes with arrows between |
| `serpentine_flow(slide, top_y, left_x, total_w, total_h, steps, hitl_indices=None, loop_back=True, loop_label=..., rows=2)` | The Workflow Backbone Diagram. 6–10 step orchestrations with HITL gates and feedback loops | Multi-row snake with auto-routed arrows, loopback bar |
| `cycle_flow(slide, center_x, center_y, radius, steps)` | Recursive/cyclical workflows (no clear start) | Circular arrangement with directional cues |

`steps` is always a list of `(title, subtitle)` tuples. `subtitle` can be `None`. `hitl_indices` is a list of 0-based indices marking which steps are HITL gates (rendered ACCENT_GREEN).

### Shape-level helpers

When you need a custom flowchart, drop down to the shape helpers:

| Helper | Shape | Color | Use for |
|---|---|---|---|
| `add_process_node(slide, x, y, w, h, title, subtitle=None, fill=NAVY)` | `ROUNDED_RECTANGLE` | NAVY default | The standard flowchart box |
| `add_hitl_gate(slide, x, y, w, h, title, subtitle=None)` | `ROUNDED_RECTANGLE` | ACCENT_GREEN | Human-in-the-loop decision points |
| `add_decision_node(slide, x, y, w, h, text, fill=BRONZE)` | `DIAMOND` | BRONZE | Branching decisions (yes/no, escalate/proceed) |
| `add_directed_arrow(slide, x, y, w, h, direction="right", color=BRONZE)` | `RIGHT_ARROW` / `LEFT_ARROW` / `UP_ARROW` / `DOWN_ARROW` | BRONZE | Connectors between nodes |
| `add_loopback_bar(slide, x_start, x_end, y_center, label=None)` | `RECTANGLE` + `LEFT_ARROW` | BRONZE_LIGHT | Feedback loops at the bottom of a flow |

### Conventions

- HITL gates are always ACCENT_GREEN, never another color. The visual contrast against NAVY process nodes is what makes the diagram readable at a glance.
- Loopback arrows are BRONZE_LIGHT: visually present but subordinate to the main flow.
- Arrow color is BRONZE for the primary forward flow; BRONZE_LIGHT for feedback loops.
- Don't paint plain `RECTANGLE` shapes to look like flowchart boxes. Use the proper `ROUNDED_RECTANGLE` via the helpers; it reads as a real flowchart, and the audience knows it.
