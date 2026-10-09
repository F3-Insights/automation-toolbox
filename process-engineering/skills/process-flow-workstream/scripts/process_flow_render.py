"""Draw the current process map into HTML pages and a narrative, versioned.

    process_flow_render.py WORK [--version N] [--shot | --no-shot] [--format text|json]

WORK is a staged process folder. The map is maps/map v<N>.json (the latest, or --version), and
it is validated first: a map with errors is not drawn. It is drawn with the swim-lane generator
beside this script (swimlane_generator.py, the same engine process_flow_template.py stamps), so
a rendered map looks like a hand-built one. Into renders/:

- `<process> v<N> as-is.html`: strictly factual, no to-be content, checked for leaked markers;
- `<process> v<N> as-is and to-be.html` when the scope is as-is and to-be;
- `<process> v<N> narrative.md`: the short narrative a reader takes with the map;
- `<process> v<N> as-is.png` with --shot (the default): a screenshot of the as-is page. The
  screenshot runs the owner setting `[process-flow-workstream] screenshot_command` (a command
  line with {url}, {out}, {width} and {height} in it), else a headless Chrome or Chromium found
  on PATH. No screenshot tool is reported, not fatal.

Nothing is overwritten: a version already rendered is refused. Exit 0 rendered, 1 refused
(REFUSED and the reason printed), 2 on a bad argument.

Example:
    python3 process_flow_render.py runs/2026-10-06/work --no-shot
"""

import argparse
import html
import importlib.util
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import _common as C

GENERATOR = Path(__file__).resolve().parent / "swimlane_generator.py"
SHOT_W, SHOT_H = 1600, 1000
BADGES = {"PAIN": ("PAIN", "pain"), "DELAY": ("DELAY", "pain"), "NEW": ("NEW", "new"), "TBD": ("TBD", "tbd")}


class Refused(Exception):
    """The map cannot be drawn, or this version is already drawn: exit 1."""


def fresh_generator():
    """A new copy of the generator, so one render's settings never leak into the next."""
    spec = importlib.util.spec_from_file_location("swimlane_generator_render", GENERATOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def to_flow(flow, lane_index):
    """A map flow in the generator's shape."""
    nodes = [dict(id=str(n["id"]), lane=lane_index[str(n["lane"])], col=int(n["col"]), kind=n.get("kind", "step"),
                  title=str(n.get("title", "")), sub=str(n.get("sub") or ""),
                  chips=[str(s) for s in n.get("systems") or []], badge=BADGES.get(n.get("badge") or ""),
                  note=n.get("note"))
             for n in flow.get("nodes") or []]
    edges = [(str(e["from"]), str(e["to"]), e.get("style", "solid"), str(e.get("label") or ""))
             for e in flow.get("edges") or []]
    callouts = [(c.get("n"), c.get("type", "pain"), str(c.get("text", ""))) for c in flow.get("callouts") or []]
    return {"caption": str(flow.get("caption") or ""), "nodes": nodes, "edges": edges, "callouts": callouts}


def header(m, rules):
    """The page text, from the map and the rules file (Client, Prepared by, Footer)."""
    h = html.escape
    client = h(str(m.get("client") or rules.get("client") or "")).upper()
    when = h(str(m.get("date") or "")).upper()
    title = h(str(m.get("title") or m.get("process") or "Process"))
    abbrev = " &middot; ".join(f"{h(k)}: {h(str(v))}" for k, v in (m.get("abbreviations") or {}).items())
    by = m.get("prepared_by") or rules.get("prepared by")
    footer = (f"Prepared by {h(str(by))} &middot; " if by else "") + h(
        rules.get("footer") or "Working document. Friction markers reflect what the client team reported.")
    eyebrow = " &middot; ".join(x for x in (client, "{kind}", when) if x)
    return {
        "title_dual": f"{title}: as-is and to-be", "title_asis": f"{title}: as-is",
        "eyebrow_dual": eyebrow.format(kind="PROCESS FLOW"),
        "eyebrow_asis": eyebrow.format(kind="CURRENT-STATE PROCESS FLOW"),
        "h1_dual": f"{title}, <em>as-is and to-be</em>", "h1_asis": f"{title}, <em>as-is</em>",
        "sub_dual": h(str(m.get("subtitle_dual") or "Functional swim-lanes compiled from discovery sources. AS-IS as the "
                      "client team described it; TO-BE is the proposal. Working draft for validation with the client team.")),
        "sub_asis": h(str(m.get("subtitle_asis") or "Functional swim-lanes compiled from discovery sources: the current "
                      "state as the client team described it. Working draft for validation.")),
        "key_note": (abbrev + " &middot; " if abbrev else "") + "lanes are functional roles, not individuals",
        "footer": footer,
    }


def narrative(m, v, scope):
    """The short narrative, section by section, from the map's own text."""
    lanes = {str(l["id"]): l.get("label", l["id"]) for l in m.get("lanes") or []}
    out = [f"# {m.get('title') or m.get('process')}: narrative, v{v}", ""]
    if m.get("audience"):
        out += [f"For {m['audience']}. Working draft for validation; every step on the map traces to a source "
                f"in the verification memo of the same version.", ""]
    for sec in m.get("sections") or []:
        out += [f"## {sec.get('num')}. {sec.get('title')}", ""]
        if sec.get("narrative"):
            out += [str(sec["narrative"]).strip(), ""]
        asis = sec.get("asis") or {}
        steps = asis.get("nodes") or []
        if steps:
            who = sorted({lanes.get(str(n.get("lane")), "") for n in steps})
            out += [f"As-is: {len(steps)} steps across {', '.join(w for w in who if w)}.", ""]
        pains = [c for c in asis.get("callouts") or [] if c.get("type", "pain") == "pain"]
        if pains:
            out += ["Where it breaks today:", ""] + [f"- {c.get('text')}" for c in pains] + [""]
        if scope == "as-is-and-to-be" and isinstance(sec.get("tobe"), dict):
            d = sec.get("delta") or {}
            if d:
                out += [f"Today: {d.get('today', '')}. Proposed: {d.get('proposed', '')}.", ""]
            changes = [n for n in sec["tobe"].get("nodes") or [] if not n.get("same_as")]
            if changes:
                out += ["What changes and why:", ""] + [
                    f"- {n.get('title')}{' (to be designed)' if n.get('badge') == 'TBD' else ''}: {n.get('why', '')}"
                    for n in changes] + [""]
            out += [f"- Removed: step {r.get('node')}, {r.get('why', '')}" for r in sec.get("removed") or []]
            if sec.get("removed"):
                out.append("")
    return "\n".join(out).rstrip() + "\n"


def shoot(page, png):
    """Screenshot page into png; returns {ok, nonblank, error}."""
    template = C.settings(C.SKILL).get("screenshot_command")
    url = page.resolve().as_uri()
    if template:
        cmd = [part.format(url=url, out=str(png), width=SHOT_W, height=SHOT_H) for part in shlex.split(template)]
    else:
        exe = next((shutil.which(n) for n in ("chromium", "chromium-browser", "google-chrome", "chrome")
                    if shutil.which(n)), None)
        if not exe:
            return {"ok": False, "error": "no screenshot_command setting and no Chrome or Chromium on PATH"}
        cmd = [exe, "--headless", "--disable-gpu", "--hide-scrollbars", f"--window-size={SHOT_W},{SHOT_H}",
               f"--screenshot={png}", url]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "error": str(exc)}
    if not png.is_file():
        return {"ok": False, "error": (res.stderr or res.stdout).strip()[-300:] or "no image written"}
    return {"ok": True, "nonblank": png.stat().st_size >= 2000}


def render(work, version=None, shot=True):
    meta = C.read_json(work / C.STAGED_MARKER, {}) or {}
    v, path, m = C.load_map(work, version)
    if not path:
        raise Refused("no map to render (maps/map v<N>.json)")
    if m is None:
        raise Refused(f"{path.name} is not a JSON object")
    scope = m.get("scope") or meta.get("scope") or "as-is-and-to-be"
    rules = meta.get("rules") or {}
    errors, warnings = C.validate(m, {r["id"] for r in C.read_ledger(work)}, scope, C.rule_list(rules.get("lanes")))
    if errors:
        raise Refused(f"map v{v} has {len(errors)} error(s): " + "; ".join(errors[:15]))
    slug = str(m.get("process") or meta.get("process") or "process")
    rdir = work / "renders"
    targets = {"asis": rdir / f"{slug} v{v} as-is.html", "narrative": rdir / f"{slug} v{v} narrative.md"}
    if scope == "as-is-and-to-be":
        targets["dual"] = rdir / f"{slug} v{v} as-is and to-be.html"
    if shot:
        targets["shot"] = rdir / f"{slug} v{v} as-is.png"
    taken = [p.name for p in targets.values() if p.exists()]
    if taken:
        raise Refused(f"map v{v} is already rendered ({', '.join(taken)}); write a new map version to change it")

    t = fresh_generator()
    lane_index = {str(l["id"]): i for i, l in enumerate(m["lanes"])}
    t.LANES = [str(l.get("label", l["id"])).upper() for l in m["lanes"]]
    t.HEADER = header(m, rules)
    t.CC = str(m.get("proposed_system") or "PLATFORM").upper()
    sections = []
    for sec in m["sections"]:
        d = sec.get("delta") or {}
        s = {"num": str(sec["num"]), "title": str(sec["title"]), "headline": str(sec.get("headline") or ""),
             "delta": (str(d.get("today", "")), str(d.get("proposed", ""))), "asis": to_flow(sec["asis"], lane_index)}
        s["tobe"] = to_flow(sec["tobe"], lane_index) if isinstance(sec.get("tobe"), dict) else s["asis"]
        sections.append(s)
    t.SECTIONS = sections
    t.LEGEND_ASIS, t.LEGEND = t.legend_asis(), t.legend()
    asis_html = t.build_asis_only()
    leaks = C.as_is_leaks(asis_html)
    if leaks:
        raise Refused(f"the as-is page would carry to-be content ({', '.join(leaks)}); check the as-is flows' text")
    rdir.mkdir(parents=True, exist_ok=True)
    targets["asis"].write_text(asis_html, encoding="utf-8")
    if "dual" in targets:
        targets["dual"].write_text(t.build(), encoding="utf-8")
    targets["narrative"].write_text(narrative(m, v, scope), encoding="utf-8")
    result = {"map_version": v, "scope": scope, "warnings": warnings,
              "files": [str(p) for k, p in targets.items() if k != "shot"]}
    if shot:
        result["shot"] = shoot(targets["asis"], targets["shot"])
        if targets["shot"].exists():
            result["files"].append(str(targets["shot"]))
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description="Draw the current process map into versioned HTML, a narrative and a screenshot.")
    p.add_argument("work", help="The staged process folder")
    p.add_argument("--version", type=int, default=None, help="The map version; default the latest")
    p.add_argument("--shot", action=argparse.BooleanOptionalAction, default=True, help="Screenshot the as-is page")
    p.add_argument("--format", dest="fmt", choices=["text", "json"], default="text")
    a = p.parse_args(argv)
    work = Path(a.work).expanduser()
    if not C.is_staged(work):
        print(f"ERROR {work} is not a staged process folder (no {C.STAGED_MARKER})", file=sys.stderr)
        return 2
    try:
        r = render(work, a.version, a.shot)
    except Refused as exc:
        print(f"REFUSED {exc}")
        return 1
    if a.fmt == "json":
        print(json.dumps(r, indent=1))
        return 0
    print(f"RENDERED map v{r['map_version']} ({r['scope']})")
    for f in r["files"]:
        print(f"  {f}")
    for w in r["warnings"]:
        print(f"warning: {w}")
    if "shot" in r and not r["shot"].get("ok"):
        print(f"screenshot not taken: {r['shot'].get('error')}")
    elif "shot" in r and r["shot"].get("nonblank") is False:
        print("screenshot is blank: look at the page")
    return 0


if __name__ == "__main__":
    sys.exit(main())
