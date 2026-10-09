"""Flowchart primitives for seminar decks.

Uses native python-pptx flowchart shapes and directional arrow shapes to
produce professional-looking flowcharts that remain editable in PowerPoint
(SmartArt is not programmable in python-pptx; this is the closest equivalent
that's still a real, native flowchart).

Two layers:

  Shape helpers (one node, one arrow):
    - add_process_node       - rounded rectangle (the standard flowchart box)
    - add_hitl_gate          - same shape, ACCENT_GREEN, for human decision points
    - add_decision_node      - diamond, for branching decisions
    - add_directed_arrow     - filled arrow shape, any direction
    - add_loopback_bar       - bottom-spanning bar + left arrowhead, for feedback loops

  High-level layouts (multi-node flows):
    - linear_flow            - one row, left-to-right
    - serpentine_flow        - multi-row snake with HITL marking and loopback
    - cycle_flow             - circular arrangement of nodes (for recursive loops)

Style tokens are imported from deckbuilder.py so palettes stay in one place.
"""

from __future__ import annotations

import math

from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

from deckbuilder import (
    NAVY, BRONZE, BRONZE_LIGHT, WHITE, GRAY, LIGHT_GRAY,
    ACCENT_GREEN, ACCENT_RED,
    TITLE_FONT, BODY_FONT,
    SLIDE_W, SLIDE_H, MARGIN,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _style_shape(shape, fill_color):
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    shape.line.fill.background()
    shape.shadow.inherit = False


def _set_text(shape, title, subtitle=None,
              title_size=12, subtitle_size=9,
              title_color=WHITE, subtitle_color=WHITE):
    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.08)
    tf.margin_right = Inches(0.08)
    tf.margin_top = Inches(0.05)
    tf.margin_bottom = Inches(0.05)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE

    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = title
    r.font.name = BODY_FONT
    r.font.size = Pt(title_size)
    r.font.bold = True
    r.font.color.rgb = title_color

    if subtitle:
        p2 = tf.add_paragraph()
        p2.alignment = PP_ALIGN.CENTER
        p2.space_before = Pt(2)
        r2 = p2.add_run()
        r2.text = subtitle
        r2.font.name = BODY_FONT
        r2.font.size = Pt(subtitle_size)
        r2.font.color.rgb = subtitle_color


# ---------------------------------------------------------------------------
# Shape helpers
# ---------------------------------------------------------------------------
def add_process_node(slide, x, y, w, h, title, subtitle=None, fill=NAVY):
    """A rounded process box. The standard flowchart node."""
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    _style_shape(shape, fill)
    _set_text(shape, title, subtitle)
    return shape


def add_hitl_gate(slide, x, y, w, h, title, subtitle=None):
    """A HITL (human-in-the-loop) decision point. Process node in ACCENT_GREEN."""
    return add_process_node(slide, x, y, w, h, title, subtitle, fill=ACCENT_GREEN)


def add_decision_node(slide, x, y, w, h, text, fill=BRONZE):
    """A diamond decision node. Use for branching decisions, not HITL gates."""
    shape = slide.shapes.add_shape(MSO_SHAPE.DIAMOND, x, y, w, h)
    _style_shape(shape, fill)
    _set_text(shape, text, title_size=11)
    return shape


def add_directed_arrow(slide, x, y, w, h, direction="right", color=BRONZE):
    """A filled directional arrow shape."""
    direction_map = {
        "right": MSO_SHAPE.RIGHT_ARROW,
        "left":  MSO_SHAPE.LEFT_ARROW,
        "up":    MSO_SHAPE.UP_ARROW,
        "down":  MSO_SHAPE.DOWN_ARROW,
    }
    shape = slide.shapes.add_shape(direction_map[direction], x, y, w, h)
    _style_shape(shape, color)
    return shape


def add_loopback_bar(slide, x_start, x_end, y_center,
                     bar_height=Inches(0.12), arrow_size=Inches(0.32),
                     color=BRONZE_LIGHT, label=None):
    """A horizontal bar with a left-pointing arrowhead, for feedback loops.

    The bar spans x_start..x_end, vertically centered on y_center.
    Optional label is placed above the bar.
    """
    arrow = slide.shapes.add_shape(
        MSO_SHAPE.LEFT_ARROW,
        x_start, y_center - arrow_size / 2,
        arrow_size, arrow_size
    )
    _style_shape(arrow, color)
    bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        x_start + arrow_size - Inches(0.02), y_center - bar_height / 2,
        x_end - x_start - arrow_size + Inches(0.02), bar_height
    )
    _style_shape(bar, color)

    if label:
        from deckbuilder import add_text
        add_text(slide, label,
                 x_start, y_center - Inches(0.45),
                 x_end - x_start, Inches(0.3),
                 size=10, italic=True, color=color, align=PP_ALIGN.CENTER)


# ---------------------------------------------------------------------------
# High-level layouts
# ---------------------------------------------------------------------------
def linear_flow(slide, top_y, left_x, total_w, node_h, steps,
                hitl_indices=None, arrow_gap_ratio=0.12, fill=NAVY):
    """Render `steps` in a single horizontal row with arrows between them.

    steps:         list of (title, subtitle) tuples (subtitle may be None)
    hitl_indices:  0-based indices marking HITL gates (ACCENT_GREEN)
    arrow_gap_ratio: arrow width as fraction of node width
    """
    hitl_indices = set(hitl_indices or [])
    n = len(steps)
    node_w = total_w / (n + (n - 1) * arrow_gap_ratio)
    arrow_w = arrow_gap_ratio * node_w

    nodes = []
    for i, (title, subtitle) in enumerate(steps):
        x = left_x + i * (node_w + arrow_w)
        node = (add_hitl_gate if i in hitl_indices else
                lambda s, x, y, w, h, t, st: add_process_node(s, x, y, w, h, t, st, fill=fill))(
            slide, x, top_y, node_w, node_h, title, subtitle
        )
        nodes.append(node)

    arrow_h = node_h * 0.35
    arrow_y = top_y + (node_h - arrow_h) / 2
    for i in range(n - 1):
        ax = left_x + (i + 1) * node_w + i * arrow_w
        add_directed_arrow(slide, ax, arrow_y, arrow_w, arrow_h, direction="right")

    return nodes


def serpentine_flow(slide, top_y, left_x, total_w, total_h, steps,
                    hitl_indices=None, loop_back=True, loop_label=None,
                    rows=2, arrow_gap_ratio=0.12, fill=NAVY):
    """Render `steps` as a serpentine multi-row flow.

    steps:        list of (title, subtitle) tuples
    hitl_indices: 0-based indices marking HITL gates
    rows:         number of rows in the serpentine (default 2)
    loop_back:    render a feedback loop bar from last node back to first
    loop_label:   optional caption above the loop-back bar
    """
    hitl_indices = set(hitl_indices or [])
    n = len(steps)
    cols = (n + rows - 1) // rows

    # Reserve bottom space for the loopback bar if requested
    loopback_reserve = Inches(0.55) if loop_back else Inches(0)
    flow_h = total_h - loopback_reserve
    row_h = flow_h / rows
    node_h = row_h * 0.78

    node_w = total_w / (cols + (cols - 1) * arrow_gap_ratio)
    arrow_w = arrow_gap_ratio * node_w

    nodes = []
    for i, (title, subtitle) in enumerate(steps):
        row = i // cols
        if row >= rows:
            break
        col_in_row = i % cols
        # Serpentine: even rows L→R, odd rows R→L
        col_idx = col_in_row if row % 2 == 0 else (cols - 1 - col_in_row)

        x = left_x + col_idx * (node_w + arrow_w)
        y = top_y + row * row_h + (row_h - node_h) / 2

        if i in hitl_indices:
            node_shape = add_hitl_gate(slide, x, y, node_w, node_h, title, subtitle)
        else:
            node_shape = add_process_node(slide, x, y, node_w, node_h, title, subtitle, fill=fill)
        nodes.append({"shape": node_shape, "x": x, "y": y, "row": row, "col": col_idx})

    # Draw arrows between consecutive nodes
    h_arrow_h = node_h * 0.32
    for i in range(len(nodes) - 1):
        a = nodes[i]
        b = nodes[i + 1]
        if a["row"] == b["row"]:
            # Same row: horizontal arrow between the columns
            direction = "right" if a["row"] % 2 == 0 else "left"
            x_left = min(a["x"], b["x"]) + node_w
            ay = a["y"] + (node_h - h_arrow_h) / 2
            add_directed_arrow(slide, x_left, ay, arrow_w, h_arrow_h, direction=direction)
        else:
            # Row transition: vertical down arrow on the same column
            ax = a["x"] + (node_w - arrow_w) / 2
            ay = a["y"] + node_h + Inches(0.04)
            vh = b["y"] - ay - Inches(0.04)
            if vh > 0:
                add_directed_arrow(slide, ax, ay, arrow_w, vh, direction="down")

    # Loopback: L-route around the LEFT side of the diagram, originating at
    # the last node, ending with an arrow pointing into the first node.
    if loop_back and len(nodes) > 1:
        first = nodes[0]
        last = nodes[-1]

        color = BRONZE_LIGHT
        stub_w = Inches(0.13)
        arrow_size = Inches(0.32)

        # Outer corridor - left of the diagram, fitting inside the slide margin.
        outer_x = max(Inches(0.18), first["x"] - Inches(0.4))

        # Bottom horizontal track sits just below the diagram's last row.
        track_y = last["y"] + node_h + Inches(0.18)

        # 1. Down stub from last node bottom-center to the bottom track.
        last_stub_x = last["x"] + (node_w - stub_w) / 2
        last_stub_top = last["y"] + node_h
        last_stub_h = track_y - last_stub_top
        if last_stub_h > 0:
            sh = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, last_stub_x, last_stub_top, stub_w, last_stub_h
            )
            _style_shape(sh, color)

        # 2. Horizontal segment from last's stub leftward to the outer corridor.
        bar_left = outer_x
        bar_right = last["x"] + (node_w + stub_w) / 2
        bar_w = bar_right - bar_left
        if bar_w > 0:
            sh = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, bar_left, track_y, bar_w, stub_w
            )
            _style_shape(sh, color)

        # 3. Vertical segment up the outer corridor to first node's vertical center.
        target_y = first["y"] + node_h / 2 - stub_w / 2
        vert_h = (track_y + stub_w) - target_y
        if vert_h > 0:
            sh = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, outer_x, target_y, stub_w, vert_h
            )
            _style_shape(sh, color)

        # 4. Short horizontal segment from outer corridor to just before first node,
        #    ending with a right-pointing arrow into the first node's left edge.
        arrow_x = first["x"] - arrow_size
        connector_w = arrow_x - (outer_x + stub_w)
        if connector_w > 0:
            sh = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE,
                outer_x + stub_w, target_y, connector_w, stub_w
            )
            _style_shape(sh, color)
        arrow = slide.shapes.add_shape(
            MSO_SHAPE.RIGHT_ARROW,
            arrow_x, first["y"] + node_h / 2 - arrow_size / 2,
            arrow_size, arrow_size,
        )
        _style_shape(arrow, color)

        # Optional label below the bottom horizontal segment.
        if loop_label:
            from deckbuilder import add_text as _add_text
            _add_text(
                slide, loop_label,
                outer_x + Inches(0.2), track_y + Inches(0.18),
                last["x"] + node_w - outer_x - Inches(0.4), Inches(0.3),
                size=12, italic=True, color=color,
            )

    return [n["shape"] for n in nodes]


def cycle_flow(slide, center_x, center_y, radius, steps, fill=NAVY,
               node_w=Inches(1.8), node_h=Inches(0.7)):
    """Render `steps` arranged in a circle, with arrows between consecutive nodes.

    Use for recursive/cyclical workflows where there is no clear start or end.
    Each node is a rounded process box.

    steps: list of (title, subtitle) tuples
    """
    n = len(steps)
    nodes = []
    for i, (title, subtitle) in enumerate(steps):
        # Place at evenly spaced angles, starting at top (-90°)
        angle = -math.pi / 2 + 2 * math.pi * i / n
        cx = center_x + radius * math.cos(angle)
        cy = center_y + radius * math.sin(angle)
        x = cx - node_w / 2
        y = cy - node_h / 2
        node = add_process_node(slide, x, y, node_w, node_h, title, subtitle, fill=fill)
        nodes.append((node, cx, cy))
    # Connecting arrows (curved lines aren't well-supported, so use short straight
    # directional arrows between adjacent centers - directional cue rather than exact link)
    arrow_size = Inches(0.3)
    for i in range(n):
        a_cx, a_cy = nodes[i][1], nodes[i][2]
        b_cx, b_cy = nodes[(i + 1) % n][1], nodes[(i + 1) % n][2]
        # Midpoint between the two nodes, shifted slightly inward
        mx = (a_cx + b_cx) / 2
        my = (a_cy + b_cy) / 2
        # Compute direction: cardinal based on dominant axis
        dx = b_cx - a_cx
        dy = b_cy - a_cy
        if abs(dx) > abs(dy):
            direction = "right" if dx > 0 else "left"
        else:
            direction = "down" if dy > 0 else "up"
        add_directed_arrow(slide,
                           mx - arrow_size / 2, my - arrow_size / 2,
                           arrow_size, arrow_size,
                           direction=direction)
    return [n[0] for n in nodes]
