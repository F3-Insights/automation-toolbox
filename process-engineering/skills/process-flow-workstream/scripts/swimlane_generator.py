#!/usr/bin/env python3
"""Generic as-is / to-be swim-lane process-flow generator.

This file is a template: process_flow_template.py stamps a copy into an engagement folder,
and process_flow_render.py loads a fresh copy to draw a map file. In a stamped copy, edit
LANES and SECTIONS with the client's process, swap the brand tokens below for the client or
firm palette, and run it with python3 to write both HTML pages beside it. The method is the
process-flow-workstream skill."""

# Brand tokens — swap for the client/firm palette (keep green = decisions, red = friction only)
NAVY = "#1E3A6E"; GOLD = "#8F6B2E"; GOLDF = "#C9A24B"; GREEN = "#2F7D5E"
RED = "#B23A36"; INK = "#0F172A"; MUTED = "#5A6473"
PAPER = "#F6F7F9"; LINE = "rgba(15,23,42,.12)"

LANES = ["CUSTOMER", "SALES", "OPERATIONS", "FULFILLMENT", "VENDOR", "FINANCE"]
CUST, SALES, OPS, FUL, VEND, FIN = range(6)

LANE_H = 112; TOP = 46; LEFT = 246; COLW = 198; W = 172; H = 56; H_DEC = 78

def N(id, lane, col, kind, title, sub="", chips=None, badge=None, note=None):
    return dict(id=id, lane=lane, col=col, kind=kind, title=title, sub=sub,
                chips=chips or [], badge=badge, note=note)

PAIN = ("PAIN", "pain"); DELAY = ("DELAY", "pain"); NEW = ("NEW", "new"); TBD = ("TBD", "tbd")
CC = "PLATFORM"  # chip marking the proposed system in to-be flows

# Page text. Values are HTML (already escaped); process-flow-render sets them from a map file.
HEADER = {
    "title_dual": "Process Flow — As-Is and To-Be",
    "title_asis": "As-Is Process Flow",
    "eyebrow_dual": "CLIENT NAME &middot; PROCESS FLOW &middot; MONTH YEAR",
    "eyebrow_asis": "CLIENT NAME &middot; CURRENT-STATE PROCESS FLOW &middot; MONTH YEAR",
    "h1_dual": "Client Process, <em>as-is and to-be</em>",
    "h1_asis": "Client Process, <em>as-is</em>",
    "sub_dual": "Functional swim-lanes across the core operating processes. AS-IS compiled from discovery sources; TO-BE reflects the proposed build. Working draft for validation with the client team.",
    "sub_asis": "Functional swim-lanes across the core operating processes, compiled from discovery sources. Current state as reported by the client team; working draft for validation.",
    "key_note": "Define client abbreviations here &middot; lanes are functional roles, not individuals",
    "footer": "Prepared by F3 Insights &middot; working document. Friction markers reflect what the client team reported.",
}

# ---------------------------------------------------------------------------
# DEMO CONTENT — replace everything in SECTIONS with your client's process.
# One dict per section; each holds an "asis" and a "tobe" flow.
# Node kinds: step (rect) | dec (diamond, phrase as a question) |
#             store (cylinder) | doc (document shape)
# Naming rule: every step = imperative verb + object; the LANE is the subject.
# Numbers in callouts must trace to a source (see the process-flow-workstream skill).
# ---------------------------------------------------------------------------
SECTIONS = [
{
 "num": "01", "title": "Quote to Order (demo)",
 "headline": "Quoting is manual today; the proposal makes it a review job.",
 "delta": ("line-by-line quote entry; order status lives in spreadsheets",
           "quotes drafted automatically; one shared, visible pipeline"),
 "asis": {
  "caption": "From customer request to invoiced order. Demo content — replace with client process.",
  "nodes": [
    N("n1", CUST, 0, "doc", "Purchase request", "email, any format", ["EMAIL"], note=1),
    N("n2", SALES, 1, "step", "Create quote", "line-by-line entry", ["ERP"], PAIN, note=1),
    N("n3", SALES, 2, "dec", "Pricing approved?"),
    N("n4", CUST, 3, "step", "Sign + pay deposit", "paper process", [], PAIN, note=2),
    N("n5", OPS, 4, "step", "Convert quote to order", "", ["ERP"]),
    N("n6", OPS, 5, "store", "Order tracker", "status lives only here", ["EXCEL"], PAIN, note=3),
    N("n7", VEND, 6, "step", "Confirm availability", "email or phone"),
    N("n8", FIN, 7, "step", "Invoice customer", "", ["ERP"], DELAY),
  ],
  "edges": [
    ("n1","n2","solid",""), ("n2","n3","solid",""), ("n3","n2","dash","no: rework"),
    ("n3","n4","solid","yes"), ("n4","n5","solid",""), ("n5","n6","solid",""),
    ("n6","n7","solid",""), ("n7","n8","solid",""),
  ],
  "callouts": [
    (1, "pain", "Quote entry is fully manual; a typical quote takes N hours. (Replace with the client's sourced number.)"),
    (2, "pain", "X% of orders proceed without a signed quote or deposit. (Sourced claim goes here.)"),
    (3, "pain", "Order status exists only in a spreadsheet, invisible to the rest of the business."),
  ],
 },
 "tobe": {
  "caption": "Requests parsed automatically; people approve rather than re-type.",
  "nodes": [
    N("t1", CUST, 0, "doc", "Purchase request", "any format", ["EMAIL"]),
    N("t2", SALES, 1, "step", "Auto-draft quote", "", [CC], NEW, note=1),
    N("t3", SALES, 2, "dec", "Review needed?", "", [], NEW),
    N("t4", CUST, 3, "step", "E-sign + pay online", "", [], NEW, note=2),
    N("t5", OPS, 4, "step", "Auto-convert to order", "", ["ERP"], NEW),
    N("t6", OPS, 5, "step", "Track in shared pipeline", "", [CC], TBD),
    N("t7", FIN, 6, "step", "Invoice customer", "complete data", ["ERP"]),
  ],
  "edges": [
    ("t1","t2","solid",""), ("t2","t3","solid",""), ("t3","t4","solid","no"),
    ("t3","t4","dash","yes: after review"), ("t4","t5","solid",""),
    ("t5","t6","solid",""), ("t6","t7","solid",""),
  ],
  "callouts": [
    (1, "new", "The intake/drafting automation delivered in Sprint 1. (Describe the proposed capability.)"),
    (2, "tbd", "Payment provider per mutual design. (Mark honest unknowns TBD — clients trust diagrams that admit them.)"),
  ],
 },
},
]

# ---------------------------------------------------------------- rendering
def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def bbox(n):
    h = H_DEC if n["kind"] == "dec" else H
    x = LEFT + n["col"] * COLW
    y = TOP + n["_row"] * LANE_H + (LANE_H - h) / 2
    return x, y, W, h

def shape_svg(n):
    x, y, w, h = bbox(n)
    if n["kind"] == "dec":
        cx, cy = x + w / 2, y + h / 2
        pts = f"{cx},{y} {x+w},{cy} {cx},{y+h} {x},{cy}"
        return f'<polygon points="{pts}" fill="rgba(47,125,94,.07)" stroke="{GREEN}" stroke-width="1.6"/>'
    if n["kind"] == "store":
        ry = 8; rx = w / 2
        body = (f'M {x},{y+ry} A {rx} {ry} 0 0 1 {x+w} {y+ry} V {y+h-ry} '
                f'A {rx} {ry} 0 0 1 {x} {y+h-ry} Z')
        rim = f'<ellipse cx="{x+rx}" cy="{y+ry}" rx="{rx}" ry="{ry}" fill="none" stroke="{GOLDF}" stroke-width="1.4"/>'
        return (f'<path d="{body}" fill="rgba(201,162,75,.14)" stroke="{GOLDF}" stroke-width="1.6"/>' + rim)
    if n["kind"] == "doc":
        d = (f'M {x},{y} H {x+w} V {y+h-8} '
             f'Q {x+w*0.75},{y+h+7} {x+w/2},{y+h-8} '
             f'Q {x+w*0.25},{y+h-23} {x},{y+h-8} Z')
        return f'<path d="{d}" fill="rgba(201,162,75,.14)" stroke="{GOLDF}" stroke-width="1.6"/>'
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#fff" stroke="{NAVY}" stroke-width="1.3"/>'

def render_node(n):
    x, y, w, h = bbox(n)
    cx, cy = x + w / 2, y + h / 2
    s = [shape_svg(n)]
    ty = cy - 3 if n["sub"] else cy + 4
    s.append(f'<text x="{cx}" y="{ty}" text-anchor="middle" class="n-name">{esc(n["title"])}</text>')
    if n["sub"]:
        s.append(f'<text x="{cx}" y="{cy+12}" text-anchor="middle" class="n-role">{esc(n["sub"])}</text>')
    if n["chips"]:
        chw = [len(c) * 6.2 + 12 for c in n["chips"]]
        total = sum(chw) + 6 * (len(chw) - 1)
        bx = cx - total / 2
        for c, wd in zip(n["chips"], chw):
            s.append(f'<rect x="{bx:.1f}" y="{y+h-6}" width="{wd:.1f}" height="15" rx="3" fill="#fff" stroke="{NAVY}" stroke-width="0.9"/>')
            s.append(f'<text x="{bx+wd/2:.1f}" y="{y+h+5.5}" text-anchor="middle" class="chip">{esc(c)}</text>')
            bx += wd + 6
    if n["badge"]:
        text, style = n["badge"]
        bw = len(text) * 6.6 + 14
        bx0, by0 = cx - bw / 2, y - 9
        if style == "new":
            s.append(f'<rect x="{bx0:.1f}" y="{by0}" width="{bw:.1f}" height="16" rx="3" fill="{GOLD}"/>')
            s.append(f'<text x="{cx}" y="{y+3}" text-anchor="middle" class="badge" fill="#fff">{esc(text)}</text>')
        else:
            color = RED if style == "pain" else GOLD
            dash = ' stroke-dasharray="3 2"' if style == "tbd" else ""
            s.append(f'<rect x="{bx0:.1f}" y="{by0}" width="{bw:.1f}" height="16" rx="3" fill="#fff" stroke="{color}" stroke-width="1"{dash}/>')
            s.append(f'<text x="{cx}" y="{y+3}" text-anchor="middle" class="badge" fill="{color}">{esc(text)}</text>')
    if n["note"]:
        nx, ny = x + w - 4, y + 2
        s.append(f'<circle cx="{nx}" cy="{ny}" r="8.5" fill="{GOLD}"/>')
        s.append(f'<text x="{nx}" y="{ny+3.5}" text-anchor="middle" class="note-n">{n["note"]}</text>')
    return "\n".join(s)

def render_edge(e, nmap):
    src, dst, style, label = e
    a, b = nmap[src], nmap[dst]
    ax, ay, aw, ah = bbox(a); bx, by, bw, bh = bbox(b)
    acy, bcy = ay + ah / 2, by + bh / 2
    if a["_row"] == b["_row"] and bx > ax + COLW * 1.5:
        sx, sy = ax + aw / 2, ay
        tx, ty = bx + bw / 2, by
        lift = min(sy, ty) - 30
        d = f"M {sx},{sy} C {sx},{lift} {tx},{lift} {tx},{ty}"
        lx, ly = (sx + tx) / 2, lift + 3
    elif bx > ax:
        sx, sy, tx, ty = ax + aw, acy, bx, bcy
        c1x, c2x = sx + (tx - sx) * 0.45, tx - (tx - sx) * 0.45
        d = f"M {sx},{sy} C {c1x},{sy} {c2x},{ty} {tx},{ty}"
        lx, ly = (sx + tx) / 2, (sy + ty) / 2 - 7
    else:
        sx, sy = ax + aw / 2, ay + ah
        tx, ty = bx + bw / 2, by + bh
        dip = max(sy, ty) + 32
        d = f"M {sx},{sy} C {sx},{dip} {tx},{dip} {tx},{ty}"
        lx, ly = (sx + tx) / 2, dip - 5
    dash = ' stroke-dasharray="5 4" opacity="0.45"' if style == "dash" else ' opacity="0.55"'
    out = [f'<path d="{d}" fill="none" stroke="{NAVY}" stroke-width="1.2" marker-end="url(#arr)"{dash}/>']
    if label:
        out.append(f'<text x="{lx:.0f}" y="{ly:.0f}" text-anchor="middle" class="e-lbl">{esc(label)}</text>')
    return "\n".join(out)

def render_flow(flow):
    nodes, edges = flow["nodes"], flow["edges"]
    nmap = {n["id"]: n for n in nodes}
    used = sorted({n["lane"] for n in nodes})
    rowmap = {lane: i for i, lane in enumerate(used)}
    for n in nodes:
        n["_row"] = rowmap[n["lane"]]
    maxcol = max(n["col"] for n in nodes)
    width = LEFT + (maxcol + 1) * COLW + 30
    height = TOP + len(used) * LANE_H + 46
    parts = [f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']
    parts.append(f'<defs><marker id="arr" markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto">'
                 f'<path d="M0,0 L6,3 L0,6 Z" fill="{NAVY}" opacity="0.6"/></marker></defs>')
    for lane in used:
        i = rowmap[lane]
        y = TOP + i * LANE_H
        if i % 2 == 0:
            parts.append(f'<rect x="0" y="{y}" width="{width}" height="{LANE_H}" fill="{PAPER}" opacity="0.55"/>')
        parts.append(f'<line x1="0" y1="{y}" x2="{width}" y2="{y}" stroke="{LINE}" stroke-width="1"/>')
        parts.append(f'<text x="16" y="{y + LANE_H/2 + 3}" class="lane-lbl">{esc(LANES[lane])}</text>')
    parts.append(f'<line x1="0" y1="{TOP + len(used)*LANE_H}" x2="{width}" y2="{TOP + len(used)*LANE_H}" stroke="{LINE}" stroke-width="1"/>')
    parts.append(f'<line x1="{LEFT-18}" y1="{TOP}" x2="{LEFT-18}" y2="{TOP + len(used)*LANE_H}" stroke="{LINE}" stroke-width="1"/>')
    for e in edges:
        parts.append(render_edge(e, nmap))
    for n in nodes:
        parts.append(render_node(n))
    parts.append("</svg>")
    return "\n".join(parts)

def render_callouts(callouts):
    if not callouts:
        return ""
    cards = []
    for num, style, text in callouts:
        cards.append(f'<div class="co {style}"><span class="co-n">{num}</span><p>{esc(text)}</p></div>')
    return f'<div class="callouts">{"".join(cards)}</div>'

def render_section(sec):
    asis = f'<div class="view asis"><div class="scroller">{render_flow(sec["asis"])}</div>{render_callouts(sec["asis"]["callouts"])}</div>'
    tobe = f'<div class="view tobe"><div class="scroller">{render_flow(sec["tobe"])}</div>{render_callouts(sec["tobe"]["callouts"])}</div>'
    today, proposed = sec["delta"]
    return f"""
<section class="flow" data-view="asis" id="sec{sec['num']}">
  <div class="sec-head">
    <div>
      <div class="eyebrow">SECTION {sec['num']}</div>
      <h2>{esc(sec['title'])}</h2>
      <p class="headline">{esc(sec['headline'])}</p>
    </div>
    <div class="toggle" role="tablist">
      <button class="t-asis" onclick="setView(this,'asis')">AS-IS</button>
      <button class="t-tobe" onclick="setView(this,'tobe')">TO-BE</button>
    </div>
  </div>
  <div class="delta">
    <div class="d-cell today"><span>TODAY</span><p>{esc(today)}</p></div>
    <div class="d-arrow">&#8594;</div>
    <div class="d-cell proposed"><span>PROPOSED</span><p>{esc(proposed)}</p></div>
  </div>
  <p class="caption asis-cap">{esc(sec['asis']['caption'])}</p>
  <p class="caption tobe-cap">{esc(sec['tobe']['caption'])}</p>
  {asis}
  {tobe}
</section>"""

def legend_asis():
    KEY_NOTE = HEADER["key_note"]
    return f"""
<div class="legend">
  <div class="lg"><span class="sw"></span>Process step</div>
  <div class="lg"><svg width="26" height="18"><polygon points="13,1 25,9 13,17 1,9" fill="rgba(47,125,94,.07)" stroke="{GREEN}" stroke-width="1.4"/></svg>Decision</div>
  <div class="lg"><svg width="24" height="18"><path d="M 2,5 A 10 3.5 0 0 1 22,5 V 13 A 10 3.5 0 0 1 2,13 Z" fill="rgba(201,162,75,.14)" stroke="{GOLDF}" stroke-width="1.3"/><ellipse cx="12" cy="5" rx="10" ry="3.5" fill="none" stroke="{GOLDF}" stroke-width="1.2"/></svg>Data store</div>
  <div class="lg"><svg width="24" height="18"><path d="M 2,1 H 22 V 13 Q 17,19 12,13 Q 7,7 2,13 Z" fill="rgba(201,162,75,.14)" stroke="{GOLDF}" stroke-width="1.3"/></svg>Document / input</div>
  <div class="lg"><span class="tag">ERP</span>System used</div>
  <div class="lg"><span class="tag pain">PAIN</span><span class="tag pain">DELAY</span>Friction marker</div>
  <div class="lg"><span class="co-n demo">1</span>See callout below</div>
  <div class="lg"><svg width="40" height="10"><line x1="0" y1="5" x2="40" y2="5" stroke="{NAVY}" stroke-width="1.2" stroke-dasharray="5 4" opacity="0.6"/></svg>Exception / loopback</div>
</div>
<p class="key-note">{KEY_NOTE}</p>"""

def legend():
    KEY_NOTE = HEADER["key_note"]
    return f"""
<div class="legend">
  <div class="lg"><span class="sw"></span>Process step</div>
  <div class="lg"><svg width="26" height="18"><polygon points="13,1 25,9 13,17 1,9" fill="rgba(47,125,94,.07)" stroke="{GREEN}" stroke-width="1.4"/></svg>Decision</div>
  <div class="lg"><svg width="24" height="18"><path d="M 2,5 A 10 3.5 0 0 1 22,5 V 13 A 10 3.5 0 0 1 2,13 Z" fill="rgba(201,162,75,.14)" stroke="{GOLDF}" stroke-width="1.3"/><ellipse cx="12" cy="5" rx="10" ry="3.5" fill="none" stroke="{GOLDF}" stroke-width="1.2"/></svg>Data store</div>
  <div class="lg"><svg width="24" height="18"><path d="M 2,1 H 22 V 13 Q 17,19 12,13 Q 7,7 2,13 Z" fill="rgba(201,162,75,.14)" stroke="{GOLDF}" stroke-width="1.3"/></svg>Document / input</div>
  <div class="lg"><span class="tag">ERP</span>System used</div>
  <div class="lg"><span class="tag">PLATFORM</span>Proposed platform</div>
  <div class="lg"><span class="tag pain">PAIN</span><span class="tag pain">DELAY</span>Friction (as-is)</div>
  <div class="lg"><span class="tag newf">NEW</span>Proposed (to-be)</div>
  <div class="lg"><span class="tag tbd">TBD</span>Scope to refine</div>
  <div class="lg"><span class="co-n demo">1</span>See callout below</div>
  <div class="lg"><svg width="40" height="10"><line x1="0" y1="5" x2="40" y2="5" stroke="{NAVY}" stroke-width="1.2" stroke-dasharray="5 4" opacity="0.6"/></svg>Exception / loopback</div>
</div>
<p class="key-note">{KEY_NOTE}</p>"""

LEGEND_ASIS = legend_asis()
LEGEND = legend()

def render_section_asis(sec):
    return f"""
<section class="flow" data-view="asis" id="sec{sec['num']}">
  <div class="sec-head">
    <div>
      <div class="eyebrow">SECTION {sec['num']}</div>
      <h2>{esc(sec['title'])}</h2>
    </div>
  </div>
  <p class="caption">{esc(sec['asis']['caption'])}</p>
  <div class="view asis"><div class="scroller">{render_flow(sec['asis'])}</div>{render_callouts(sec['asis']['callouts'])}</div>
</section>"""

def build_asis_only():
    sections = "\n".join(render_section_asis(s) for s in SECTIONS)
    css = build().split("<style>")[1].split("</style>")[0]  # shared stylesheet; unused to-be rules are harmless
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{HEADER["title_asis"]}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,wght@1,600&family=Hanken+Grotesk:wght@700;800&family=IBM+Plex+Mono:wght@500&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>{css}</style></head><body>
<header>
  <div class="eyebrow">{HEADER["eyebrow_asis"]}</div>
  <h1>{HEADER["h1_asis"]}</h1>
  <p class="sub">{HEADER["sub_asis"]}</p>
  {legend_asis()}
</header>
{sections}
<footer>{HEADER["footer"]}</footer>
</body></html>"""

def build_sections():
    return "\n".join(render_section(s) for s in SECTIONS)

def build():
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{HEADER["title_dual"]}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,wght@1,600&family=Hanken+Grotesk:wght@700;800&family=IBM+Plex+Mono:wght@500&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{{--navy:{NAVY};--gold:{GOLD};--gold-foil:{GOLDF};--green:{GREEN};--red:{RED};
--ink:{INK};--muted:{MUTED};--paper:{PAPER};--line:{LINE}}}
*{{box-sizing:border-box;margin:0}}
body{{font-family:'Inter',sans-serif;color:var(--ink);background:#fff;padding:48px 56px 72px}}
header{{max-width:1180px;margin-bottom:10px}}
.eyebrow{{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.22em;color:var(--gold);margin-bottom:10px}}
h1{{font-family:'Hanken Grotesk',sans-serif;font-weight:800;font-size:40px;letter-spacing:-.01em}}
h1 em{{font-family:'Fraunces',serif;font-style:italic;font-weight:600;color:var(--gold)}}
.sub{{color:var(--muted);font-size:15px;margin-top:8px;max-width:860px}}
.master{{display:flex;align-items:center;gap:14px;margin-top:18px}}
.master span{{font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.18em;color:var(--muted)}}
.toggle{{display:inline-flex;border:1px solid var(--navy);border-radius:6px;overflow:hidden}}
.toggle button{{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;padding:7px 16px;border:0;background:#fff;color:var(--navy);cursor:pointer}}
.flow[data-view=asis] .t-asis, .flow[data-view=tobe] .t-tobe,
body[data-mview=asis] .m-asis, body[data-mview=tobe] .m-tobe{{background:var(--navy);color:#fff}}
.legend{{display:flex;gap:20px;flex-wrap:wrap;align-items:center;margin:18px 0 4px;padding:13px 18px;background:var(--paper);border:1px solid var(--line);border-radius:8px}}
.lg{{display:flex;align-items:center;gap:7px;font-size:12.5px;color:var(--muted)}}
.sw{{width:20px;height:14px;border-radius:3px;border:1.3px solid var(--navy);background:#fff;display:inline-block}}
.tag{{font-family:'IBM Plex Mono',monospace;font-size:8.5px;letter-spacing:.08em;border:1px solid var(--navy);border-radius:3px;padding:2px 6px;color:var(--navy)}}
.tag.pain{{border-color:var(--red);color:var(--red)}}
.tag.newf{{border-color:var(--gold);background:var(--gold);color:#fff}}
.tag.tbd{{border-color:var(--gold);color:var(--gold);border-style:dashed}}
.key-note{{font-size:11.5px;color:var(--muted);margin:6px 2px 0}}
section.flow{{margin-top:44px}}
.sec-head{{display:flex;justify-content:space-between;align-items:flex-end;gap:24px;max-width:1180px}}
h2{{font-family:'Hanken Grotesk',sans-serif;font-weight:800;font-size:24px;margin-top:6px}}
.headline{{font-family:'Fraunces',serif;font-style:italic;font-size:15.5px;color:var(--gold);margin-top:5px}}
.delta{{display:flex;align-items:stretch;gap:0;margin:12px 0 10px;max-width:1180px;border:1px solid var(--line);border-radius:8px;overflow:hidden}}
.d-cell{{flex:1;padding:10px 16px}}
.d-cell span{{font-family:'IBM Plex Mono',monospace;font-size:9.5px;letter-spacing:.18em;display:block;margin-bottom:3px}}
.d-cell p{{font-size:13px;line-height:1.4}}
.d-cell.today{{background:var(--paper)}}
.d-cell.today span{{color:var(--red)}}
.d-cell.proposed{{background:rgba(201,162,75,.09)}}
.d-cell.proposed span{{color:var(--gold)}}
.d-arrow{{display:flex;align-items:center;padding:0 10px;color:var(--gold);font-size:20px;background:rgba(201,162,75,.09)}}
.caption{{color:var(--muted);font-size:13px;margin:2px 0 10px;max-width:860px}}
.flow[data-view=asis] .tobe, .flow[data-view=asis] .tobe-cap{{display:none}}
.flow[data-view=tobe] .asis, .flow[data-view=tobe] .asis-cap{{display:none}}
.scroller{{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:#fff;padding:10px 6px}}
.flow[data-view=tobe] .scroller{{border-color:rgba(143,107,46,.45)}}
.callouts{{display:flex;flex-wrap:wrap;gap:12px;margin-top:12px}}
.co{{display:flex;gap:10px;padding:12px 14px;background:var(--paper);border:1px solid var(--line);border-left:3px solid var(--red);border-radius:6px;flex:1 1 300px;max-width:480px}}
.co.new{{border-left-color:var(--gold)}}
.co.tbd{{border-left-color:var(--gold);border-left-style:dashed}}
.co p{{font-size:12.5px;color:var(--ink);line-height:1.45}}
.co-n{{flex:none;width:19px;height:19px;border-radius:50%;background:var(--gold);color:#fff;font-family:'IBM Plex Mono',monospace;font-size:11px;display:inline-flex;align-items:center;justify-content:center}}
.co-n.demo{{width:17px;height:17px;font-size:10px}}
.lane-lbl{{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.16em;fill:var(--gold)}}
.n-name{{font-family:'Hanken Grotesk',sans-serif;font-weight:700;font-size:12.5px;fill:var(--ink)}}
.n-role{{font-family:'Inter',sans-serif;font-size:9.5px;fill:var(--muted)}}
.chip{{font-family:'IBM Plex Mono',monospace;font-size:8px;letter-spacing:.06em;fill:var(--navy)}}
.badge{{font-family:'IBM Plex Mono',monospace;font-size:8.5px;letter-spacing:.1em}}
.note-n{{font-family:'IBM Plex Mono',monospace;font-size:10px;fill:#fff}}
.e-lbl{{font-family:'IBM Plex Mono',monospace;font-size:8.5px;letter-spacing:.06em;fill:var(--muted);paint-order:stroke;stroke:#fff;stroke-width:3px;stroke-linejoin:round}}
footer{{margin-top:40px;color:var(--muted);font-size:12px;max-width:900px}}
</style></head><body data-mview="">
<header>
  <div class="eyebrow">{HEADER["eyebrow_dual"]}</div>
  <h1>{HEADER["h1_dual"]}</h1>
  <p class="sub">{HEADER["sub_dual"]}</p>
  <div class="master"><span>ALL SECTIONS</span>
    <div class="toggle"><button class="m-asis" onclick="setAll('asis')">AS-IS</button><button class="m-tobe" onclick="setAll('tobe')">TO-BE</button></div>
  </div>
  {legend()}
</header>
{build_sections()}
<footer>{HEADER["footer"]}</footer>
<script>
function setView(btn, v){{ btn.closest('.flow').dataset.view = v; document.body.dataset.mview=''; }}
function setAll(v){{ document.querySelectorAll('.flow').forEach(s => s.dataset.view = v); document.body.dataset.mview=v; }}
setAll('asis');
</script>
</body></html>"""

if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path as _Path
    here = _Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Render this process map as two HTML files (full, and as-is only). A stamped copy writes beside itself; the master copy in the toolbox needs --out.")
    parser.add_argument("--out", help="folder to write the two HTML files into (default: beside this file)")
    args = parser.parse_args()
    # The master copy sits beside process_flow_template.py; never write example files into the toolbox.
    if args.out is None and (here / "process_flow_template.py").exists():
        print("this is the toolbox's master copy: pass --out, or stamp a copy with process_flow_template.py", file=sys.stderr)
        sys.exit(2)
    folder = _Path(args.out).expanduser() if args.out else here
    folder.mkdir(parents=True, exist_ok=True)
    for name, html in (("example-process-flow.html", build()), ("example-process-flow-asis-only.html", build_asis_only())):
        target = folder / name
        target.write_text(html)
        print("written", target)
