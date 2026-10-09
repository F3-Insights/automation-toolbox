# /// script
# dependencies = ["pyyaml"]
# ///
"""Say whether a forecast vintage is done, computed from its folder rather than anyone's word.

The vintage is --vintage or the newest under vintages/. Its eleven tests:

1. extracts: both extracts exist, foot and tie, and their workbooks are unchanged since.
2. hypotheses: hypotheses.json covers every active line of every year and each year's EBITDA,
   was recorded (forecast-record) before the bridge was built, and is unchanged since.
3. bridge: bridge.json was built from the current extracts and modules, re-derives, and foots.
4. reasons: every line at or above its materiality has a driver, a kind and an evidence id
   (work/source/evidence.json) or question id (the ledger); detail amounts sum to the line.
5. flags: flags.json is current and every material flag is answered in flags-resolved.json.
6. scores: the hypotheses were scored against the current bridge.
7. summary: summary.md quotes only figures the bridge carries, never names the machinery, and
   has enough top drivers, things that would change it, and anticipated questions.
8. questions: every question in the ledger is answered, expired or withdrawn.
9. review: a reviewer's PASS is recorded against the current bridge and summary.
10. messages: no ISO week carries more batched messages than the settings allow (all vintages).
11. delivered: when the settings name deliver_to, the reviewed files were filed there.

Prints each test with its gaps (or the result with --format json). --precheck prints one line
for a scheduler: WORK: <reason> when a newer revision was issued than any vintage covers, a
vintage's workbook changed, or an open vintage has a file newer than its LOG.md; otherwise
NOTHING: <reason>. Exit 0 whenever it ran, 2 on a bad argument or a folder that is not a
Forecast folder.

Example:
    python3 forecast_check.py ~/Forecast --vintage rev3 --format json
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from _common import (ForecastError, build_bridge, close, current_vintage, file_sha, forecast_folder, ledger_rows,
                     load_modules, load_reasons, load_settings, load_vintage, read_json, resolve_path, revisions,
                     values_in_k, vintages, work_shas)

REASON_KINDS = ("business", "correction", "timing", "new-data", "mixed")
RESOLUTIONS = ("explained", "revised", "open")
SUMMARY_SECTIONS = {"anticipated questions": "min_anticipated_questions", "top drivers": "min_top_drivers",
                    "what would change it": "min_what_would_change_it"}
MONEY = re.compile(r"\$\s?(\()?\s?(-?[\d,]+(?:\.\d+)?)\s?(\))?\s?([kKmM]?)")


def result(gaps, **extra):
    return dict({"met": not gaps, "gaps": gaps}, **extra)


def test_extracts(root, meta, vdir):
    gaps = []
    for name, key in (("prior.json", "prior_workbook"), ("new.json", "new_workbook")):
        x = read_json(vdir / "work/source" / name)
        workbook = resolve_path(root, meta.get(key, ""))
        if x is None or x.get("_unreadable"):
            if key == "new_workbook" and meta.get("kind") == "rolling" and not workbook.is_file():
                gaps.append(f"the new forecast is not built: forecast-revise, then forecast-prepare --vintage {meta['vintage']}")
            else:
                gaps.append(f"{name} missing: run forecast-prepare")
            continue
        if not x.get("ok"):
            gaps.append(f"{name} does not foot or tie: {'; '.join([c['name'] for c in x.get('checks', []) if not c['ok']][:3])}")
        if not workbook.is_file():
            gaps.append(f"{workbook.name} is gone")
        elif file_sha(workbook) != x.get("sha256"):
            gaps.append(f"{workbook.name} changed since it was extracted: run forecast-prepare --vintage {meta['vintage']}")
    return result(gaps)


def test_hypotheses(vdir, modules, years, rows, bridge):
    path = vdir / "hypotheses.json"
    data = read_json(path)
    if data is None:
        return result(["hypotheses.json missing: write the hypotheses before looking at the new forecast"])
    gaps = []
    lines = data.get("lines") or {}
    missing = [f"{y}:{m['key']}" for y in years for m in modules if m.get("active", True) and f"{y}:{m['key']}" not in lines]
    if missing:
        gaps.append(f"no hypothesis for {', '.join(missing[:6])}" + (f" and {len(missing) - 6} more" if len(missing) > 6 else ""))
    for key, item in lines.items():
        if not isinstance(item, dict) or not isinstance(item.get("expected"), (int, float)):
            gaps.append(f"{key}: `expected` must be a number (EBITDA terms)")
        elif not str(item.get("rationale") or "").strip():
            gaps.append(f"{key}: no rationale")
    gaps += [f"FY{y}: no ebitda_expected" for y in years
             if not isinstance(((data.get("fy") or {}).get(y) or {}).get("ebitda_expected"), (int, float))]
    row = rows.get("hypotheses:set")
    if not row:
        gaps.append("not recorded: forecast-record --test hypotheses --item set --state written")
    else:
        if row.get("evidence") != f"sha256:{file_sha(path)}":
            gaps.append("hypotheses.json changed after it was recorded; hypotheses are never edited once written")
        if bridge and str(row.get("updated_at", "")) > str(bridge.get("built_at", "")):
            gaps.append("recorded after the bridge was built; hypotheses come before the bridge")
    return result(gaps)


def test_bridge(root, vdir, vintage, bridge, tolerance):
    if bridge is None:
        return result([f"bridge.json missing: run forecast-bridge --vintage {vintage}"])
    gaps = [f"built from an older {name}: run forecast-bridge again" for name in ("prior.json", "new.json")
            if (bridge.get("inputs") or {}).get(name) != file_sha(vdir / "work/source" / name)]
    try:
        fresh = build_bridge(root, vintage)
    except ForecastError as exc:
        return result(gaps + [str(exc)])
    if (bridge.get("inputs") or {}).get("modules") != fresh["inputs"]["modules"]:
        gaps.append("modules.yaml changed since the bridge was built: run forecast-bridge again")
    for year, walk in fresh["years"].items():
        theirs = (bridge.get("years") or {}).get(year)
        if not theirs:
            gaps.append(f"FY{year} missing from the bridge")
            continue
        stated = {l["key"]: l["amount"] for l in theirs.get("walk", [])}
        diff = [l["key"] for l in walk["walk"] if l["key"] not in stated or not close(l["amount"], stated[l["key"]], tolerance)]
        if diff:
            gaps.append(f"FY{year}: lines do not re-derive: {', '.join(diff[:5])}")
    failed = [c["name"] for c in fresh["foots"] if not c["ok"]]
    if failed:
        gaps.append("does not foot: " + "; ".join(failed[:4]))
    return result(gaps)


def test_reasons(vdir, bridge, rows, tolerance):
    if bridge is None:
        return result(["no bridge yet"])
    reasons = load_reasons(vdir)
    evidence_ids = {i.get("id") for i in (read_json(vdir / "work/source/evidence.json") or {}).get("items", [])}
    question_ids = {r["item"] for r in rows.values() if r.get("test") == "questions"}
    gaps, explained = [], 0
    for year, walk in (bridge.get("years") or {}).items():
        for line in walk.get("walk", []):
            if line["kind"] in ("start", "end"):
                continue
            key, amount = f"{year}:{line['key']}", line["amount"]
            # A restated closed month is always material; otherwise the line's own materiality.
            material = abs(amount) >= 0.005 and (line["kind"] == "restated" or abs(amount) >= float(line.get("materiality", 0.0)))
            reason = reasons.get(key)
            if not reason:
                if material:
                    gaps.append(f"{key} {amount:,.0f}: no reason")
                continue
            if not str(reason.get("driver") or "").strip():
                gaps.append(f"{key}: no driver")
            if reason.get("kind") not in REASON_KINDS:
                gaps.append(f"{key}: kind must be one of {', '.join(REASON_KINDS)}")
            if material and not (reason.get("evidence") or reason.get("questions")):
                gaps.append(f"{key} {amount:,.0f}: cites no evidence or question")
            unknown = [e for e in reason.get("evidence") or [] if e not in evidence_ids]
            unknown += [q for q in reason.get("questions") or [] if q not in question_ids]
            if unknown:
                gaps.append(f"{key}: cites ids that do not exist: {', '.join(unknown)}")
            detail = [d for d in reason.get("detail") or [] if isinstance(d.get("amount"), (int, float))]
            total = sum(d["amount"] for d in detail)
            if detail and not close(total, amount, max(tolerance, 0.5)):
                gaps.append(f"{key}: detail sums to {total:,.2f}, the line is {amount:,.2f}")
            explained += 1
    return result(gaps, explained=explained)


def test_flags(vdir, flags):
    if flags is None:
        return result(["flags.json missing: run forecast-sense-check"])
    gaps = [f"flags were built before the current {name}: run forecast-sense-check again"
            for name, rel in (("prior.json", "work/source/prior.json"), ("new.json", "work/source/new.json"),
                              ("bridge.json", "bridge.json"), ("hypotheses.json", "hypotheses.json"))
            if (flags.get("inputs") or {}).get(name) != file_sha(vdir / rel)]
    resolved = read_json(vdir / "flags-resolved.json") or {}
    unanswered = []
    for f in (f for f in flags.get("flags", []) if f["severity"] == "material"):
        answer = resolved.get(f["id"])
        kind = (answer or {}).get("resolution")
        if not answer:
            unanswered.append(f["id"])
        elif kind not in RESOLUTIONS:
            gaps.append(f"{f['id']}: resolution must be one of {', '.join(RESOLUTIONS)}")
        elif kind == "explained" and not (answer.get("evidence") or str(answer.get("text") or "").strip()):
            gaps.append(f"{f['id']}: explained without evidence or text")
        elif kind == "open" and not (answer.get("owner") and answer.get("question")):
            gaps.append(f"{f['id']}: open without an owner and a question")
    if unanswered:
        gaps.append(f"{len(unanswered)} material flag(s) unanswered: {', '.join(unanswered[:6])}")
    return result(gaps, material=flags.get("material", 0))


def test_scores(vdir):
    scores = read_json(vdir / "scores.json")
    if scores is None:
        return result(["not scored: run forecast-score"])
    return result([f"scored against an older {name}: run forecast-score again" for name in ("hypotheses.json", "bridge.json")
                   if (scores.get("inputs") or {}).get(name) != file_sha(vdir / name)])


def money_in_k(match):
    """A quoted $ figure in $k: $1,234 is 1.234, $45.0k is 45.0, $1.2m is 1200, $(15.0)k is -15.0."""
    value = float(match.group(2).replace(",", ""))
    if match.group(1) and match.group(3):
        value = -abs(value)
    unit = match.group(4).lower()
    return value * 1000.0 if unit == "m" else value if unit == "k" else value / 1000.0


def summary_sections(text):
    """Bullets or numbered lines under each `## heading`, keyed by the heading in lower case."""
    out, current = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        heading = re.match(r"^#{2,3}\s+(.*)$", line)
        if heading:
            current = heading.group(1).strip().lower().rstrip(":")
            out.setdefault(current, 0)
        elif current and re.match(r"^([-*]|\d+[.)])\s+\S", line):
            out[current] += 1
    return out


def test_summary(vdir, bridge, settings):
    path = vdir / "summary.md"
    if not path.is_file():
        return result(["summary.md missing"])
    if bridge is None:
        return result(["no bridge to tie the summary to"])
    text = path.read_text(encoding="utf-8")
    allowed, tolerance = values_in_k(bridge), float(settings["summary_k_tolerance"])
    quoted = list(MONEY.finditer(text))
    gaps = [f"{m.group(0).strip()} is not a figure the bridge carries" for m in quoted
            if not any(abs(abs(money_in_k(m)) - abs(v)) <= tolerance for v in allowed)]
    if not quoted:
        gaps.append("quotes no figures")
    gaps += [f"mentions the machinery: '{w}'" for w in settings["process_words"]
             if re.search(rf"\b{re.escape(w)}s?\b", text, re.I)]
    sections = summary_sections(text)
    for heading, setting in SUMMARY_SECTIONS.items():
        found = next((n for h, n in sections.items() if h.startswith(heading)), None)
        if found is None:
            gaps.append(f"no '## {heading.capitalize()}' section")
        elif found < int(settings[setting]):
            gaps.append(f"'{heading}' has {found}, needs {int(settings[setting])}")
    return result(gaps, quoted=len(quoted))


def test_questions(rows):
    return result([f"waiting on {r['item']} ({r.get('note') or 'no fallback stated'})" for r in rows.values()
                   if r.get("test") == "questions" and r.get("state") == "asked"])


def test_review(vdir, rows):
    row = rows.get("review:vintage")
    if not row or not row.get("review"):
        return result(["no review recorded"])
    gaps = []
    if row.get("review") != "PASS":
        gaps.append(f"review is {row.get('review')}: {row.get('note') or 'see the review file'}")
    if row.get("evidence") != work_shas(vdir):
        gaps.append("the bridge or summary changed after the review: review again")
    return result(gaps)


def test_messages(root, settings):
    """Batched messages per ISO week, counted across every vintage's ledger."""
    limit, weeks = int(settings["max_messages_per_week"]), {}
    for name in vintages(root):
        for row in ledger_rows(root / "vintages" / name, name).values():
            if row.get("test") != "messages":
                continue
            try:
                year, week, _ = date.fromisoformat(str(row.get("updated_at") or "")[:10]).isocalendar()
            except ValueError:
                continue
            weeks[f"{year}-W{week:02d}"] = weeks.get(f"{year}-W{week:02d}", 0) + 1
    return result([f"more than {limit} batched message(s) in {w}: {n}" for w, n in sorted(weeks.items()) if n > limit],
                  weeks=weeks)


def test_delivered(root, settings, rows):
    if not settings.get("deliver_to"):
        return result([], skipped="no deliver_to in the settings")
    row = rows.get("delivered:vintage")
    if not row:
        return result(["the reviewed bridge and summary are not filed in the delivery folder"])
    path = resolve_path(root, row.get("evidence", ""))
    return result([] if path.is_file() else [f"{path} does not exist"])


def check(folder, vintage=None):
    root = forecast_folder(folder)
    settings = load_settings(root)
    modules = load_modules(settings)
    name = vintage or current_vintage(root)
    if not name:
        return {"folder": str(root), "vintage": None, "done": False, "tests": {},
                "headline": "no vintage yet: run forecast-prepare"}
    meta = load_vintage(root, name)
    vdir = Path(meta["_dir"])
    rows = ledger_rows(vdir, name)
    bridge = read_json(vdir / "bridge.json")
    bridge = None if bridge and bridge.get("_unreadable") else bridge
    years = [str(y) for y in meta["years"]] or sorted((bridge or {}).get("years", {}))
    tolerance = float(settings["tolerance"])
    tests = {
        "extracts": test_extracts(root, meta, vdir),
        "hypotheses": test_hypotheses(vdir, modules, years, rows, bridge),
        "bridge": test_bridge(root, vdir, name, bridge, tolerance),
        "reasons": test_reasons(vdir, bridge, rows, tolerance),
        "flags": test_flags(vdir, read_json(vdir / "flags.json")),
        "scores": test_scores(vdir),
        "summary": test_summary(vdir, bridge, settings),
        "questions": test_questions(rows),
        "review": test_review(vdir, rows),
        "messages": test_messages(root, settings),
        "delivered": test_delivered(root, settings, rows),
    }
    met = sum(1 for t in tests.values() if t["met"])
    done = met == len(tests)
    return {"folder": str(root), "vintage": name, "kind": meta.get("kind"), "dir": str(vdir), "done": done,
            "tests": tests, "headline": f"vintage {name}: {'done' if done else f'{met} of {len(tests)} tests met'}"}


def precheck(folder):
    root = forecast_folder(folder)
    settings = load_settings(root)
    names = vintages(root)
    covered = {str(resolve_path(root, load_vintage(root, n).get("new_workbook", ""))) for n in names}
    try:
        issued = revisions(settings)
    except (ForecastError, OSError) as exc:   # an unreachable delivery folder is a soft problem here
        issued = []
        if not names:
            return f"NOTHING: no vintage, and the revisions folder cannot be read ({exc})"
    if issued and str(issued[-1]) not in covered:
        return f"WORK: {issued[-1].name} has been issued and no vintage covers it"
    if not names:
        return "NOTHING: no vintage and no issued revision"
    latest = check(root, names[-1])
    if any("changed since it was extracted" in g for g in latest["tests"]["extracts"]["gaps"]):
        return f"WORK: a workbook of vintage {names[-1]} changed since it was extracted"
    if latest["done"]:
        return f"NOTHING: vintage {names[-1]} is done"
    vdir = Path(latest["dir"])
    since = (vdir / "LOG.md").stat().st_mtime if (vdir / "LOG.md").is_file() else 0.0
    newer = [p for p in vdir.rglob("*") if p.is_file() and p.name not in ("LOG.md", "STATUS.md")
             and p.stat().st_mtime > since]
    if newer:
        return f"WORK: vintage {names[-1]} is open and {len(newer)} file(s) changed since its last session"
    waiting = latest["tests"]["questions"]["gaps"]
    return f"NOTHING: vintage {names[-1]} is open, " + (waiting[0] if waiting else "nothing changed since its last session")


def render(outcome):
    lines = [outcome["headline"]]
    for name, test in outcome.get("tests", {}).items():
        lines.append(f"  [{'x' if test['met'] else ' '}] {name}")
        lines += [f"      - {gap}" for gap in test["gaps"][:6]]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Whether a forecast vintage is done, computed from its folder.")
    parser.add_argument("folder", nargs="?", default="", help="the Forecast folder")
    parser.add_argument("--vintage", default="", help="the vintage; blank: the newest")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--precheck", action="store_true", help="one line, WORK: or NOTHING:, for a scheduler")
    args = parser.parse_args(argv)
    if not args.folder:
        print("forecast-check: name the Forecast folder", file=sys.stderr)
        return 2
    try:
        if args.precheck:
            print(precheck(args.folder))
            return 0
        outcome = check(args.folder, args.vintage.strip() or None)
    except ForecastError as exc:
        print(f"forecast-check: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(outcome, indent=1) if args.format == "json" else render(outcome))
    return 0


if __name__ == "__main__":
    sys.exit(main())
