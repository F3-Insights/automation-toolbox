"""The claim ledger of one engagement process, and the record of its reviews.

    claim_ledger.py build  WORK                       inventories -> CLAIM-LEDGER.csv
    claim_ledger.py add    WORK --source ID --text T --quote Q --location L [--kind claim] [--speaker R]
    claim_ledger.py brief  WORK                       the current map's assertions and the two halves
    claim_ledger.py record WORK --kind K --from FILE  a reviewer's return, checked and kept
    claim_ledger.py memo   WORK                       VERIFICATION v<N>.md for the current map
    (each takes --format text|json)

WORK is a staged process folder (process_flow_prepare.py --out).

build: each inventories/<source id>.md is one transcript reader's return, ending with the
fenced json block the process-flow-workstream skill gives (claims, pains, wishes, numbers,
contradictions); inventories/added.json holds claims added with `add`. Every entry becomes a
ledger row with a stable id, <source>-<C|P|W|N|X><n> (T03-C12 is claim 12 of T03). Each quote
is looked up in the staged source text: quote_found is yes (verbatim, ignoring case,
punctuation and spacing), near (most of its three-word runs are there) or no. The register
records which source version each inventory was built from (ledgered_sha).

brief: writes reviews/assertions v<N>.json, every statement the current map makes that must
trace to a source, and prints the staged files each fact-check half (A and B) reads.

record: kinds factcheck-A, factcheck-B, completeness, redteam. FILE is the reviewer's return
(its last fenced json block) or a .json file. It is checked (every assertion has a verdict; a
VERIFIED or CONTRADICTED verdict quotes a source of that half; a question answered from a
source names one; every section has a letter grade) and kept as reviews/<kind> v<N>.json. A
review recorded for a map version is never replaced.

memo: cross-references the two halves and writes VERIFICATION v<N>.md (claim ledger,
corrections, caveats, omissions, open questions, source inventory); reviews/memo v<N>.json
keeps its counts.

Exit 0 when done, 1 when the input is incomplete or wrong (INCOMPLETE and the reasons are
printed; nothing is written), 2 on a bad argument.

Example:
    python3 claim_ledger.py build runs/2026-10-06/work --format json
"""

import argparse
import csv
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import _common as C

LEDGER_COLUMNS = ("id", "source", "kind", "topic", "text", "speaker", "quote", "location", "leading",
                  "basis", "quote_found")
SECTIONS = (("claims", "C", "claim"), ("pains", "P", "pain"), ("wishes", "W", "wish"),
            ("numbers", "N", "number"), ("contradictions", "X", "contradiction"))
KIND_LETTER = {kind: letter for _, letter, kind in SECTIONS}
REVIEW_KINDS = ("factcheck-A", "factcheck-B", "completeness", "redteam")
VERDICTS = {"VERIFIED": "VERIFIED", "NOT IN MY SOURCES": "NOT IN SOURCES", "NOT IN SOURCES": "NOT IN SOURCES",
            "NOT-IN-SOURCES": "NOT IN SOURCES", "CONTRADICTED": "CONTRADICTED"}
GRADE_RE = re.compile(r"^[A-F][+-]?$")
JSON_BLOCK_RE = re.compile(r"```json\s*\n(.*?)\n```", re.S)


class Incomplete(Exception):
    """The input is incomplete or wrong: exit 1, nothing written."""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def staged(work):
    p = Path(work).expanduser()
    if not C.is_staged(p):
        raise C.EngagementError(f"{p} is not a staged process folder (no {C.STAGED_MARKER}); run process_flow_prepare.py")
    return p


def last_json_block(text):
    blocks = JSON_BLOCK_RE.findall(text)
    if not blocks:
        if not text.strip().startswith("{"):
            raise Incomplete("no fenced json block in the return")
        blocks = [text.strip()]
    try:
        return json.loads(blocks[-1])
    except ValueError as exc:
        raise Incomplete(f"the return's json block does not parse: {exc}") from None


def norm(text):
    """Lowercase words only, curly quotes straightened: how quotes are compared."""
    text = text.lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return " ".join(re.findall(r"[a-z0-9']+", text))


def quote_found(quote, source_norm):
    q = norm(quote)
    if not q:
        return "no"
    if q in source_norm:
        return "yes"
    words = q.split()
    if len(words) < 4:
        return "no"
    runs = [" ".join(words[i:i + 3]) for i in range(len(words) - 2)]
    return "near" if sum(1 for r in runs if r in source_norm) / len(runs) >= 0.7 else "no"


def register(work):
    return C.read_json(work / C.SOURCES_FILE, {}) or {}


def source_texts(work, reg):
    out = {}
    for e in reg.get("sources") or []:
        st = e.get("staged")
        if st and Path(st).suffix in (".txt", ".md") and (work / st).is_file():
            out[e["id"]] = norm((work / st).read_text(encoding="utf-8", errors="replace"))
    return out


# --------------------------------------------------------------------------- build


def entry_text(entry, kind):
    for key in (kind, "claim", "text", "pain", "wish", "measures"):
        if entry.get(key):
            if kind == "number" and key == "measures":
                return f"{entry.get('number', '')} {entry.get('unit', '')}: {entry[key]}".strip()
            return str(entry[key])
    return ""


def inventory_rows(sid, data):
    rows, problems = [], []
    if str(data.get("source") or sid) != sid:
        problems.append(f"inventories/{sid}.md says it is for source {data.get('source')}")
    for section, letter, kind in SECTIONS:
        for i, entry in enumerate(data.get(section) or [], 1):
            if not isinstance(entry, dict):
                problems.append(f"{sid} {section} entry {i} is not an object")
                continue
            n = entry.get("n", i)
            quote = str(entry.get("quote") or entry.get("a_quote") or "")
            text = entry_text(entry, kind)
            if kind == "contradiction" and entry.get("b_quote"):
                text = f"{text} (other side: \"{entry['b_quote']}\" at {entry.get('b_location', '?')})"
            if not text or not quote:
                problems.append(f"{sid}-{letter}{n} has no text or no quote")
            leading = entry.get("leading", "")
            rows.append({"id": f"{sid}-{letter}{n}", "source": sid, "kind": kind, "topic": str(entry.get("topic") or ""),
                         "text": text, "speaker": str(entry.get("speaker") or ""), "quote": quote,
                         "location": str(entry.get("location") or entry.get("a_location") or ""),
                         "leading": leading if isinstance(leading, str) else ("yes" if leading else "no"),
                         "basis": str(entry.get("basis") or ""), "quote_found": ""})
    return rows, problems


def write_ledger(work, rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=LEDGER_COLUMNS, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in LEDGER_COLUMNS})
    tmp = work / (C.LEDGER_FILE + ".tmp")
    tmp.write_text(buf.getvalue(), encoding="utf-8")
    tmp.replace(work / C.LEDGER_FILE)


def build(work):
    reg = register(work)
    by_id = {e["id"]: e for e in reg.get("sources") or []}
    texts = source_texts(work, reg)
    inv_dir = work / "inventories"
    rows, problems, built = [], [], {}
    for p in sorted(inv_dir.glob("*.md")) if inv_dir.is_dir() else []:
        sid = p.stem
        if sid not in by_id:
            problems.append(f"inventories/{p.name} names no source in sources.json")
            continue
        try:
            data = last_json_block(p.read_text(encoding="utf-8", errors="replace"))
        except Incomplete as exc:
            problems.append(f"inventories/{p.name}: {exc}")
            continue
        if not isinstance(data, dict):
            problems.append(f"inventories/{p.name}: the json block is not an object")
            continue
        r, prob = inventory_rows(sid, data)
        rows += r
        problems += prob
        built[sid] = len(r)
    added = C.read_json(inv_dir / "added.json", []) or []
    for a in added:
        if a.get("source") not in by_id or not a.get("id"):
            problems.append(f"an added claim names source {a.get('source')}, not in sources.json, or has no id")
            continue
        rows.append({**{k: a.get(k, "") for k in LEDGER_COLUMNS}, "kind": a.get("kind", "claim"),
                     "leading": "no", "quote_found": ""})
    ids = [r["id"] for r in rows]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        problems.append(f"claim ids used twice: {', '.join(dupes[:10])}")
    if problems:
        raise Incomplete("; ".join(problems))
    for r in rows:
        src = texts.get(r["source"])
        r["quote_found"] = quote_found(r["quote"], src) if src is not None else "unchecked"
    write_ledger(work, rows)
    for sid, count in built.items():
        by_id[sid]["ledgered_sha"] = by_id[sid].get("sha256")
        by_id[sid]["claims"] = count
    C.write_json(work / C.SOURCES_FILE, reg)
    return {"rows": len(rows), "inventories": built, "added": len(added),
            "quote_found": {k: sum(1 for r in rows if r["quote_found"] == k) for k in ("yes", "near", "no", "unchecked")},
            "quotes_not_found": [r["id"] for r in rows if r["quote_found"] == "no"]}


def add(work, source, text, quote, location, kind, speaker):
    reg = register(work)
    if source not in {e["id"] for e in reg.get("sources") or []}:
        raise Incomplete(f"no source {source} in sources.json")
    if kind not in KIND_LETTER:
        raise Incomplete(f"kind must be one of {', '.join(KIND_LETTER)}")
    if not (text.strip() and quote.strip() and location.strip()):
        raise Incomplete("an added claim needs its text, a verbatim quote and a location")
    texts = source_texts(work, reg)
    if source in texts and quote_found(quote, texts[source]) == "no":
        raise Incomplete(f"the quote is not in source {source}; quote it verbatim")
    path = work / "inventories" / "added.json"
    added = C.read_json(path, []) or []
    for a in added:
        if a.get("source") == source and norm(a.get("quote", "")) == norm(quote):
            return {"id": a.get("id"), "added": False, "note": "already added"}
    # Hand-added claims number from 101 so they never collide with a reader's own numbering.
    prefix = f"{source}-{KIND_LETTER[kind]}"
    taken = {str(a.get("id")) for a in added} | {r["id"] for r in C.read_ledger(work)}
    n = 101
    while f"{prefix}{n}" in taken:
        n += 1
    added.append({"id": f"{prefix}{n}", "source": source, "kind": kind, "text": text.strip(), "quote": quote.strip(),
                  "location": location.strip(), "speaker": speaker.strip(), "added_at": now()})
    C.write_json(path, added)
    return {"id": f"{prefix}{n}", "added": True, "next": "run claim_ledger.py build before citing it"}


# --------------------------------------------------------------------------- brief


def current(work):
    v, path, m = C.load_map(work)
    if not path:
        raise Incomplete("no map yet (maps/map v<N>.json)")
    if m is None:
        raise Incomplete(f"{path.name} is not a JSON object")
    return v, path, m


def assertions(m, ledger):
    """Every statement on the map that must trace to a source, with the ledger rows it cites."""
    lane = {str(l.get("id")): l.get("label", "") for l in m.get("lanes") or []}
    out = []

    def cite(ids):
        return [{"id": i, **{k: ledger[i][k] for k in ("source", "text", "quote", "location")}} if i in ledger
                else {"id": i, "missing": True} for i in ids or []]

    for sec in m.get("sections") or []:
        num = str(sec.get("num"))
        d = sec.get("delta") or {}
        if d.get("claims"):
            out.append({"key": f"{num}/delta", "kind": "delta", "section": num,
                        "text": f"Today: {d.get('today', '')}", "claims": cite(d.get("claims"))})
        for view in ("asis", "tobe"):
            flow = sec.get(view)
            if not isinstance(flow, dict):
                continue
            for n in flow.get("nodes") or []:
                if view == "asis":
                    text = f"{lane.get(str(n.get('lane')), n.get('lane'))}: {n.get('title', '')}"
                    text += f" ({n['sub']})" if n.get("sub") else ""
                    text += f" [systems: {', '.join(n['systems'])}]" if n.get("systems") else ""
                    text += f" [{n['badge']}]" if n.get("badge") else ""
                    out.append({"key": f"{num}/asis/{n.get('id')}", "kind": n.get("kind", "step"), "section": num,
                                "text": text, "claims": cite(n.get("claims"))})
                elif not n.get("same_as"):
                    out.append({"key": f"{num}/tobe/{n.get('id')}", "kind": "change", "section": num,
                                "text": f"Proposed '{n.get('title', '')}' answers: {n.get('why', '')}",
                                "claims": cite(n.get("answers"))})
            for c in flow.get("callouts") or []:
                if view == "asis" or c.get("claims"):
                    out.append({"key": f"{num}/{view}/callout/{c.get('n')}", "kind": "callout", "section": num,
                                "text": str(c.get("text", "")), "claims": cite(c.get("claims"))})
        for r in sec.get("removed") or []:
            out.append({"key": f"{num}/removed/{r.get('node')}", "kind": "removal", "section": num,
                        "text": f"Step {r.get('node')} goes because: {r.get('why', '')}", "claims": cite(r.get("answers"))})
    return out


def halves(work):
    out = {"A": [], "B": []}
    for e in register(work).get("sources") or []:
        if e.get("half") in out and e.get("staged"):
            out[e["half"]].append({"id": e["id"], "file": str(work / e["staged"]), "name": e.get("name", ""),
                                   "kind": e["kind"]})
    return out


def brief(work):
    v, _, m = current(work)
    items = assertions(m, {r["id"]: r for r in C.read_ledger(work)})
    missing = sorted({c["id"] for a in items for c in a["claims"] if c.get("missing")})
    if missing:
        raise Incomplete(f"the map cites claims not in the ledger: {', '.join(missing[:12])}; run process_flow_check.py")
    path = work / "reviews" / f"assertions v{v}.json"
    if not path.exists():
        C.write_json(path, {"map_version": v, "assertions": items})
    return {"map_version": v, "assertions_file": str(path), "assertions": len(items), "halves": halves(work)}


# --------------------------------------------------------------------------- record


def check_factcheck(data, half, items, half_ids):
    problems, keys, seen = [], {a["key"] for a in items}, set()
    for i, v in enumerate(data.get("verdicts") or [], 1):
        key = str(v.get("key") or "")
        verdict = VERDICTS.get(str(v.get("verdict") or "").upper().strip())
        if key not in keys:
            problems.append(f"verdict {i} is for '{key}', not an assertion of this map")
            continue
        if not verdict:
            problems.append(f"{key}: verdict '{v.get('verdict')}' is not VERIFIED, NOT IN MY SOURCES or CONTRADICTED")
            continue
        v["verdict"] = verdict
        seen.add(key)
        if verdict != "NOT IN SOURCES":
            if str(v.get("source") or "") not in half_ids:
                problems.append(f"{key}: a {verdict} verdict must name a source of half {half} ({', '.join(sorted(half_ids))})")
            if not str(v.get("quote") or "").strip():
                problems.append(f"{key}: a {verdict} verdict needs the quote")
    missing = sorted(keys - seen)
    if missing:
        problems.append(f"no verdict for {len(missing)} assertion(s): {', '.join(missing[:12])}")
    return problems


def check_completeness(data, source_ids):
    qs = data.get("questions") or []
    problems = [] if qs else ["no questions; a completeness audit always returns its questions"]
    for i, q in enumerate(qs, 1):
        if not str(q.get("question") or "").strip():
            problems.append(f"question {i} has no text")
        ans = q.get("answered_by")
        if ans:
            if not isinstance(ans, dict) or str(ans.get("source") or "") not in source_ids:
                problems.append(f"question {i} is answered by a source not in sources.json")
            elif not str(ans.get("quote") or "").strip():
                problems.append(f"question {i} is answered without a quote")
    return problems


def check_redteam(data, m):
    problems, graded = [], set()
    nums = {str(s.get("num")) for s in m.get("sections") or []}
    for s in data.get("sections") or []:
        num, grade = str(s.get("num") or ""), str(s.get("grade") or "").strip().upper()
        if num not in nums:
            problems.append(f"section '{num}' is not a section of the map")
            continue
        if not GRADE_RE.match(grade):
            problems.append(f"section {num} grade '{s.get('grade')}' is not a letter grade")
        s["grade"] = grade
        graded.add(num)
        problems += [f"section {num}: a criticism with no fix"
                     for c in s.get("criticisms") or [] if not str(c.get("fix") or "").strip()]
    if nums - graded:
        problems.append(f"no grade for section(s) {', '.join(sorted(nums - graded))}")
    return problems


def record(work, kind, source):
    if kind not in REVIEW_KINDS:
        raise C.EngagementError(f"--kind must be one of {', '.join(REVIEW_KINDS)}")
    v, path, m = current(work)
    out = work / "reviews" / f"{kind} v{v}.json"
    if out.exists():
        raise Incomplete(f"{out.name} is already recorded; a new review needs a new map version")
    text = source.read_text(encoding="utf-8", errors="replace")
    data = json.loads(text) if source.suffix == ".json" else last_json_block(text)
    if not isinstance(data, dict):
        raise Incomplete("the return's json block is not an object")
    meta = {"kind": kind, "map_version": v, "map_sha256": C.sha256_file(path), "recorded_at": now(), "from": source.name}
    if kind.startswith("factcheck"):
        afile = work / "reviews" / f"assertions v{v}.json"
        if not afile.is_file():
            raise Incomplete(f"no reviews/assertions v{v}.json: run claim_ledger.py brief first")
        items = (C.read_json(afile, {}) or {}).get("assertions") or []
        meta["half"] = kind[-1]
        problems = check_factcheck(data, kind[-1], items, {s["id"] for s in halves(work)[kind[-1]]})
    elif kind == "completeness":
        problems = check_completeness(data, {e["id"] for e in register(work).get("sources") or []})
    else:
        problems = check_redteam(data, m)
        renders = sorted((work / "renders").glob(f"* v{v} *.html")) if (work / "renders").is_dir() else []
        if not renders:
            problems.append(f"no render of map v{v}: the red team reads the render")
        meta["renders"] = {p.name: C.sha256_file(p) for p in renders}
    if problems:
        raise Incomplete("; ".join(problems))
    C.write_json(out, {**meta, **data})
    summary = {"recorded": str(out)}
    if kind.startswith("factcheck"):
        summary["verdicts"] = {k: sum(1 for x in data["verdicts"] if x["verdict"] == k)
                               for k in ("VERIFIED", "NOT IN SOURCES", "CONTRADICTED")}
    elif kind == "completeness":
        summary["questions"] = len(data["questions"])
        summary["answered_from_sources"] = sum(1 for q in data["questions"] if q.get("answered_by"))
    else:
        summary["grades"] = {s["num"]: s["grade"] for s in data["sections"]}
    return summary


# --------------------------------------------------------------------------- memo


def cell(text):
    return str(text or "").replace("|", "/").replace("\n", " ").strip()


def memo(work):
    v, _, m = current(work)
    reviews = work / "reviews"
    fa, fb = C.read_json(reviews / f"factcheck-A v{v}.json"), C.read_json(reviews / f"factcheck-B v{v}.json")
    comp = C.read_json(reviews / f"completeness v{v}.json")
    missing = [n for n, r in (("factcheck-A", fa), ("factcheck-B", fb), ("completeness", comp)) if not r]
    if missing:
        raise Incomplete(f"not recorded for map v{v}: {', '.join(missing)}")
    out = work / f"VERIFICATION v{v}.md"
    if out.exists():
        raise Incomplete(f"{out.name} exists; the memo of a map version is written once")
    items = (C.read_json(reviews / f"assertions v{v}.json", {}) or {}).get("assertions") or []
    ledger = {r["id"]: r for r in C.read_ledger(work)}
    sources = register(work).get("sources") or []
    names = {e["id"]: e.get("name", "") for e in sources}
    kinds = {e["id"]: e.get("kind") for e in sources}
    xref = C.cross_reference(fa, fb)
    lines = [f"# {m.get('title') or work.name}: verification and open questions, v{v}", "",
             f"Map v{v}, {len(items)} statements checked by two fact-checkers over disjoint halves of the sources. "
             "Working document; nothing here has been shown to the client.", "",
             "## 1. Claim ledger", "", "| Key | Statement on the map | Verdict | Source |", "|---|---|---|---|"]
    open_items, counts = [], {"VERIFIED": 0, "NOT IN SOURCES": 0, "CONTRADICTED": 0}
    for a in items:
        x = xref.get(a["key"], {"verdict": "NOT IN SOURCES", "evidence": []})
        counts[x["verdict"]] += 1
        if x["evidence"]:
            ev = x["evidence"][0]
            src = f"**{ev.get('source')} {cell(names.get(ev.get('source')))} [{cell(ev.get('location'))}]:** \"{cell(ev.get('quote'))}\""
        else:
            src = "; ".join(f"cited {c['id']}: \"{cell(c['quote'])}\"" for c in a["claims"] if not c.get("missing")) or "no source"
        lines.append(f"| {a['key']} | {cell(a['text'])} | {x['verdict']} | {src} |")
        if x["verdict"] != "VERIFIED":
            note = "; ".join(cell(e.get("note") or e.get("quote")) for e in x["evidence"]) if x["evidence"] else \
                "neither fact-checker found it in their half of the sources"
            open_items.append((f"Confirm: {cell(a['text'])}", f"{x['verdict']}: {note}"))
    lines += ["", f"VERIFIED {counts['VERIFIED']}, NOT IN SOURCES {counts['NOT IN SOURCES']}, CONTRADICTED {counts['CONTRADICTED']}.", "",
              f"## 2. Corrections since v{v - 1}" if v > 1 else "## 2. Corrections", ""]
    lines += [f"- {cell(c)}" for c in m.get("changes") or []] or ["- None: the first version."]
    lines += ["", "## 3. Caveats", ""]
    caveats = []
    for cid in sorted({c["id"] for a in items for c in a["claims"] if not c.get("missing")}):
        r = ledger.get(cid) or {}
        why = []
        if str(r.get("leading", "")).lower().startswith("yes"):
            why.append("answered a leading question")
        if r.get("basis") == "estimated":
            why.append("an estimate, not a measured figure")
        if r.get("quote_found") == "no":
            why.append("its quote was not found verbatim in the source")
        if kinds.get(r.get("source")) == "background":
            why.append("rests on a background document, not a first-person source")
        if why:
            caveats.append(f"- {cid} ({cell(r.get('text'))}): {', '.join(why)}.")
    lines += caveats or ["- None."]
    lines += ["", "## 4. Facts the sources hold that the map does not show", ""]
    om = [o for rev in (fa, fb) for o in rev.get("omissions") or []]
    lines += [f"- {cell(o.get('fact'))} ({o.get('source', '?')} {cell(o.get('location'))}: \"{cell(o.get('quote'))}\")"
              for o in om] or ["- None reported."]
    lines += ["", "## 5. Open questions", "", "| # | Question, ready to ask | Why it matters | Who can answer | Already answered? |",
              "|---|---|---|---|---|"]
    n = 0
    for q, why in open_items:
        n += 1
        lines.append(f"| {n} | {q} | {why} | the process owner | no |")
    listed = 0
    for q in comp.get("questions") or []:
        n += 1
        ans = q.get("answered_by")
        if ans:
            done = f"**yes, see {ans.get('source')} [{cell(ans.get('location'))}]:** \"{cell(ans.get('quote'))}\""
        else:
            done, listed = "no", listed + 1
        lines.append(f"| {n} | {cell(q.get('question'))} | {cell(q.get('why'))} | {cell(q.get('who')) or 'the process owner'} | {done} |")
    lines += ["", "## 6. Source inventory", "", "| Id | Source | Type | Half | Read |", "|---|---|---|---|---|"]
    for e in sources:
        state = ("not read: same meeting as " + e["duplicate_of"] if e.get("duplicate_of") else
                 "gone from the folder" if not e.get("present") else
                 "yes" if e.get("staged") else f"no ({e.get('note')})")
        lines.append(f"| {e['id']} | {cell(e.get('name'))} | {e['kind']} | {e.get('half', '-')} | {state} |")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary = {"memo": str(out), "map_version": v, "verdicts": counts, "open_from_factcheck": len(open_items),
               "completeness_questions": len(comp.get("questions") or []), "completeness_listed": listed,
               "omissions": len(om), "caveats": len(caveats), "written_at": now()}
    C.write_json(reviews / f"memo v{v}.json", summary)
    return summary


# --------------------------------------------------------------------------- command line


def main(argv=None):
    p = argparse.ArgumentParser(description="The claim ledger of one engagement process, and the record of its reviews.")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, help_text in (("build", "Build CLAIM-LEDGER.csv from inventories/*.md and inventories/added.json"),
                            ("add", "Add one claim by hand (a background document's sentence); then run build"),
                            ("brief", "Write the current map's assertions and print the two fact-check halves"),
                            ("record", "Check a reviewer's return and keep it for the current map version"),
                            ("memo", "Write VERIFICATION v<N>.md for the current map")):
        s = sub.add_parser(name, help=help_text, description=help_text)
        s.add_argument("work", help="The staged process folder")
        s.add_argument("--format", dest="fmt", choices=["text", "json"], default="text")
        if name == "add":
            s.add_argument("--source", required=True, help="The source id (B03, T02)")
            s.add_argument("--text", required=True, help="The claim, one plain sentence")
            s.add_argument("--quote", required=True, help="Verbatim, at most 25 words")
            s.add_argument("--location", required=True, help="Page, slide, cell, timestamp or line")
            s.add_argument("--kind", default="claim", help="claim, pain, wish, number or contradiction")
            s.add_argument("--speaker", default="", help="The role, when the source has one")
        if name == "record":
            s.add_argument("--kind", required=True, help=", ".join(REVIEW_KINDS))
            s.add_argument("--from", dest="source", required=True, help="The reviewer's return, saved to a file")
    a = p.parse_args(argv)
    try:
        work = staged(a.work)
        if a.cmd == "build":
            result = build(work)
        elif a.cmd == "add":
            result = add(work, a.source, a.text, a.quote, a.location, a.kind, a.speaker)
        elif a.cmd == "brief":
            result = brief(work)
        elif a.cmd == "record":
            src = Path(a.source).expanduser()
            if not src.is_file():
                raise C.EngagementError(f"no file {src}")
            result = record(work, a.kind, src)
        else:
            result = memo(work)
    except C.EngagementError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    except Incomplete as exc:
        print(f"INCOMPLETE {exc}")
        return 1
    print(json.dumps(result, indent=1) if a.fmt == "json" else
          "\n".join(f"{k}: {json.dumps(v) if isinstance(v, (dict, list)) else v}" for k, v in result.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
