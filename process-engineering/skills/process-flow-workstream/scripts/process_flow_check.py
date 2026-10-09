# /// script
# dependencies = ["pyyaml"]
# ///
"""Whether an engagement process's map is done, computed from its folder.

    process_flow_check.py ENGAGEMENT [--process P] [--as-of yyyy-mm-dd] [--format text|json] [--precheck]

ENGAGEMENT is a staged process folder (process_flow_prepare.py --out; what a session works in),
or a Context name or path (its working folder's process-flows/<process>/ is read, and its
source folders are scanned again so a new transcript shows; this needs pyyaml). The process is
--process, else the staged folder's, else the rules file's `Default process`. Six tests, all on
the current map version N (maps/map v<N>.json):

1. sources: every transcript present, readable and not a duplicate has an inventory built into
   the ledger from the source as it is now.
2. map: the map exists and validates: every as-is step and callout cites a claim in the
   ledger, every to-be change names the pain it answers and why, no lane is orphaned, lanes are
   the rules file's `Lanes` when it lists them, the as-is shows nothing of the proposal.
3. factcheck: both halves' verdicts cover every assertion, and VERIFICATION v<N>.md lists every
   one not verified.
4. completeness: the completeness audit is recorded and listed in the memo.
5. redteam: every section graded at or above the rules file's `Red team bar` (default B-).
6. render: the as-is page (with no to-be content), the as-is and to-be page when the scope asks
   for it, the narrative, and a screenshot unless the rules file says `Screenshot: no`.

--precheck prints one line, `WORK: <reason>` or `NOTHING: <reason>`, for a scheduler. A blank
option (--process=) means not given. Exit 0 whenever it ran, whatever it found; 2 on a bad
argument or an engagement that does not resolve. Read only.

Example:
    python3 process_flow_check.py runs/2026-10-06/work --format json
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import _common as C

TESTS = ("sources", "map", "factcheck", "completeness", "redteam", "render")
GRADES = ["F", "D-", "D", "D+", "C-", "C", "C+", "B-", "B", "B+", "A-", "A", "A+"]


def grade_rank(g):
    g = (g or "").strip().upper()
    return GRADES.index(g) if g in GRADES else -1


def resolve(ref, process):
    """The folder to judge, its process, scope and rules, and the live source register."""
    if C.is_staged(ref):
        folder = Path(ref).expanduser()
        meta = C.read_json(folder / C.STAGED_MARKER, {}) or {}
        reg = C.read_json(folder / C.SOURCES_FILE, {}) or {}
        return {"folder": folder, "process": meta.get("process"), "scope": meta.get("scope") or "as-is-and-to-be",
                "rules": meta.get("rules") or {}, "sources": reg.get("sources") or [], "staged": True}
    eng = C.load_engagement(ref)
    _, parsed, _ = C.load_rules(eng["standing"])
    process = (process or C.default_process(parsed) or "").strip().lower()
    if not process:
        raise C.EngagementError("no process given and the rules file names no Default process")
    rules, _, _ = C.load_rules(eng["standing"], process)
    folder = C.process_dir(eng, process)
    reg = C.read_json(folder / C.SOURCES_FILE, {}) or {}
    known = {e.get("key") for e in reg.get("sources") or []}
    entries = C.assign_ids(C.scan_sources(eng, rules), reg)
    for e in entries:
        if e.get("present") and e.get("key") not in known:
            e["new"] = True
    return {"folder": folder, "process": process, "scope": rules.get("scope") or "as-is-and-to-be",
            "rules": rules, "sources": entries, "staged": False}


def test(met, gaps, **extra):
    return {"met": met, "gaps": gaps, **extra}


def test_sources(folder, sources):
    gaps = []
    want = [e for e in sources if e.get("kind") == "transcript" and e.get("present")
            and e.get("evidence", True) and not e.get("duplicate_of")]
    for e in want:
        name = f"{e['id']} {e.get('name', '')}".strip()
        if e.get("new"):
            gaps.append(f"{name}: new since the last session, no inventory")
        elif not (folder / "inventories" / f"{e['id']}.md").is_file():
            gaps.append(f"{name}: no inventory")
        elif e.get("ledgered_sha") != e.get("sha256"):
            gaps.append(f"{name}: the source changed after its inventory was built into the ledger"
                        if e.get("ledgered_sha") else f"{name}: inventory not built into the ledger")
    if not want:
        gaps.append("no transcripts found")
    return test(not gaps, gaps, transcripts=len(want))


def check(ref, process=None, as_of=None):
    ctx = resolve(ref, process)
    folder, scope, rules = ctx["folder"], ctx["scope"], ctx["rules"]
    tests = {"sources": test_sources(folder, ctx["sources"])}
    v, path, m = C.load_map(folder)
    reviews, slug = folder / "reviews", ctx["process"] or "process"
    if not path:
        tests.update({name: test(False, ["no map yet"]) for name in TESTS[1:]})
    else:
        scope = (m or {}).get("scope") or scope
        ledger_ids = {r["id"] for r in C.read_ledger(folder)}
        errors, warnings = C.validate(m, ledger_ids, scope, C.rule_list(rules.get("lanes"))) if m is not None \
            else ([f"{path.name} is not a JSON object"], [])
        tests["map"] = test(not errors, errors, version=v, warnings=warnings)

        items = (C.read_json(reviews / f"assertions v{v}.json", {}) or {}).get("assertions") or []
        fa, fb = C.read_json(reviews / f"factcheck-A v{v}.json"), C.read_json(reviews / f"factcheck-B v{v}.json")
        memo = C.read_json(reviews / f"memo v{v}.json")
        gaps, open_n = [], 0
        if not items:
            gaps.append(f"no assertions for map v{v} (claim-ledger brief)")
        gaps += [f"half {h} not fact-checked against map v{v}" for h, rev in (("A", fa), ("B", fb)) if not rev]
        if fa and fb and items:
            xref = C.cross_reference(fa, fb)
            uncovered = [a["key"] for a in items if a["key"] not in xref]
            if uncovered:
                gaps.append(f"{len(uncovered)} assertion(s) with no verdict: {', '.join(uncovered[:8])}")
            open_n = sum(1 for a in items if (xref.get(a["key"]) or {}).get("verdict") != "VERIFIED")
            if not memo:
                gaps.append(f"no verification memo for map v{v} (claim-ledger memo): {open_n} finding(s) not yet listed")
        tests["factcheck"] = test(not gaps, gaps, open_listed=open_n if memo else 0)

        comp = C.read_json(reviews / f"completeness v{v}.json")
        gaps = []
        if not comp:
            gaps.append(f"no completeness audit of map v{v}")
        elif not memo:
            gaps.append(f"completeness questions of map v{v} not yet listed in a verification memo")
        tests["completeness"] = test(not gaps, gaps, questions=len((comp or {}).get("questions") or []),
                                     listed=(memo or {}).get("completeness_listed", 0))

        red = C.read_json(reviews / f"redteam v{v}.json")
        bar = (rules.get("red team bar") or "B-").strip().upper()
        if not red:
            gaps = [f"the executive red team has not read the render of map v{v}"]
        else:
            gaps = [f"section {s.get('num')} graded {s.get('grade')}, under the bar {bar}"
                    for s in red.get("sections") or [] if grade_rank(s.get("grade")) < grade_rank(bar)]
        tests["redteam"] = test(not gaps, gaps, bar=bar,
                                grades={s.get("num"): s.get("grade") for s in (red or {}).get("sections") or []})

        rdir, gaps = folder / "renders", []
        asis = rdir / f"{slug} v{v} as-is.html"
        if not asis.is_file():
            gaps.append(f"no as-is render of map v{v}")
        else:
            leaks = C.as_is_leaks(asis.read_text(encoding="utf-8", errors="replace"))
            if leaks:
                gaps.append(f"the as-is render carries to-be content: {', '.join(leaks)}")
        if scope == "as-is-and-to-be" and not (rdir / f"{slug} v{v} as-is and to-be.html").is_file():
            gaps.append(f"no as-is and to-be render of map v{v}")
        if not (rdir / f"{slug} v{v} narrative.md").is_file():
            gaps.append(f"no narrative for map v{v}")
        if (rules.get("screenshot") or "yes").strip().lower() not in ("no", "false", "off"):
            png = rdir / f"{slug} v{v} as-is.png"
            if not png.is_file() or png.stat().st_size < 2000:
                gaps.append(f"no screenshot of the as-is render of map v{v}")
        tests["render"] = test(not gaps, gaps)
    met = sum(1 for t in tests.values() if t["met"])
    return {"engagement": ref, "process": ctx["process"], "folder": str(folder), "staged": ctx["staged"],
            "scope": scope, "map_version": v, "as_of": as_of or date.today().isoformat(),
            "tests": {k: tests[k] for k in TESTS}, "met": met, "of": len(TESTS), "done": met == len(TESTS)}


def precheck_line(r):
    if r["done"]:
        return f"NOTHING: map v{r['map_version']} of {r['process']} is done ({r['of']} of {r['of']} tests met)"
    open_tests = [name for name, t in r["tests"].items() if not t["met"]]
    first = r["tests"][open_tests[0]]["gaps"][:1]
    return f"WORK: {len(open_tests)} of {r['of']} tests open ({', '.join(open_tests)})" + (f"; {first[0]}" if first else "")


def as_text(r):
    out = [f"process-flow-check {r['engagement']} {r['process']}"
           + (f" map v{r['map_version']}" if r["map_version"] else " (no map yet)"),
           f"{'DONE' if r['done'] else 'NOT DONE'} ({r['met']} of {r['of']} tests met)"]
    for number, (name, t) in enumerate(r["tests"].items(), start=1):
        out.append(f"{number} {name}: {'MET' if t['met'] else 'NOT MET'}")
        out += [f"  - {gap}" for gap in t["gaps"][:20]]
        if len(t["gaps"]) > 20:
            out.append(f"  - and {len(t['gaps']) - 20} more")
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(description="Whether an engagement process's map is done, test by test.")
    p.add_argument("engagement", nargs="?", default="", help="A staged process folder, or a Context name or path")
    p.add_argument("--process", default="", help="The process slug; blank: the staged folder's or the rules file's")
    p.add_argument("--as-of", dest="as_of", default="", help="Judge as of this date (yyyy-mm-dd); blank: today")
    p.add_argument("--format", dest="fmt", choices=["text", "json"], default="text")
    p.add_argument("--precheck", action="store_true", help="One line, WORK: or NOTHING:, for a scheduler")
    a = p.parse_args(argv)
    try:
        if not a.engagement.strip():
            raise C.EngagementError("ENGAGEMENT is required: a staged process folder, or a Context")
        as_of = C.blank(a.as_of)
        if as_of:
            date.fromisoformat(as_of)
        result = check(a.engagement.strip(), C.blank(a.process), as_of)
    except (C.EngagementError, ValueError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    print(precheck_line(result) if a.precheck else json.dumps(result, indent=1) if a.fmt == "json" else as_text(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
