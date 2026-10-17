"""obsidian-curate-scan: the facts the vault curator works from, computed, never judged.

Reads the notes inside the curate folders (setting vault_curate_dirs) and the inbox
(vault_inbox), and lists what code can find; the curator judges the rest. Private folders are
never read. Writes nothing in the vault.

Lists, for notes inside the curate folders:
- notes: how many notes the scope holds.
- duplicate_titles: groups of notes whose titles are the same or nearly so.
- broken_links / ambiguous_links: links that resolve to no note, or to several, with the
  closest existing titles as suggestions.
- orphans: notes no other note links to.
- oversized: notes over --size-budget characters.
- frontmatter: notes with no frontmatter, or a block that never closes or has a line that is
  not `key: value` or a list item.
- misfiled: notes most of whose links (both ways) sit in another scope folder (the first
  folder level under a curate folder).
- dated_lines: status lines ("as of", "current", ...) carrying a date older than --stale-months,
  for the curator to judge stale.
Each of these lists keeps at most --per-folder items from each scope folder, so one large
folder cannot crowd out the rest; totals_by_folder gives the full counts.
- related_pairs: up to --batch pairs of notes that share the most links, to read for
  contradictions.
And for the inbox: each note with its hash and the curate notes it most likely belongs with
(by title and shared links). The inbox's "merged" folder and the curator's log are left out.

    python3 curate_scan.py --out RUN/scan.json [--size-budget 15000] [--stale-months 6] [--batch 10] [--per-folder 15]
"""

import argparse
import difflib
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import date
from itertools import combinations
from pathlib import Path

from _common import Vault, extract_links, fail, parse_frontmatter, settings

DATE_RE = re.compile(r"\b(20\d\d)-(0[1-9]|1[0-2])(?:-(0[1-9]|[12]\d|3[01]))?\b")
MERGED, LOG_NOTE = "merged", "Curator log.md"


def norm_title(stem):
    return re.sub(r"[^a-z0-9]+", " ", stem.lower()).strip()


def under(rel, folder):
    low, f = rel.lower(), folder.strip("/").lower()
    return low == f or low.startswith(f + "/")


def scope_folder(rel, curate):
    """The first folder level under the curate folder holding rel, e.g. <curate>/<sub>."""
    for c in curate:
        if under(rel, c):
            parts = rel[len(c.strip("/")) + 1:].split("/")
            return f"{c.strip('/')}/{parts[0]}" if len(parts) > 1 else c.strip("/")
    return None


def malformed(text):
    if not text.startswith("---"):
        return "missing"
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i].strip() in ("---", "...")), None)
    if end is None:
        return "never closes"
    for raw in lines[1:end]:
        s = raw.strip()
        if s and not s.startswith(("#", "- ")) and ":" not in raw and not raw.startswith((" ", "\t")):
            return f"bad line: {s[:60]}"
    return None


def scan(v, curate, inbox, size_budget=15000, stale_months=6, batch=10, per_folder=15, today=None):
    today = today or date.today()
    in_scope = [n for n in v.notes if any(under(n["rel"], c) for c in curate)]
    in_inbox = [n for n in v.notes if inbox and under(n["rel"], inbox)
                and not under(n["rel"], f"{inbox}/{MERGED}") and n["rel"] != f"{inbox.strip('/')}/{LOG_NOTE}"]
    texts = {n["rel"]: n["path"].read_text(encoding="utf-8", errors="replace") for n in in_scope + in_inbox}
    links = {rel: extract_links(t) for rel, t in texts.items()}
    scope_rels = {n["rel"] for n in in_scope}

    by_path, by_stem = {}, {}
    for n in v.notes:
        by_path.setdefault(n["rel"].removesuffix(".md").lower(), []).append(n)
        by_stem.setdefault(n["stem"].lower(), []).append(n)

    def resolve(target):  # as Vault.resolve: an exact path first, then the file name
        cleaned = target.strip().removesuffix(".md").lower()
        return by_path.get(cleaned) or by_stem.get(Path(cleaned).name, [])

    resolved, back = {}, {}
    for src in v.notes:  # backlinks from anywhere readable, so a note linked from outside is no orphan
        targets = links.get(src["rel"]) or v.links_of(src)
        for t in targets:
            hits = resolve(t)
            if src["rel"] in texts:
                resolved.setdefault(src["rel"], []).append((t, hits))
            for h in hits:
                if h["rel"] != src["rel"]:
                    back.setdefault(h["rel"], set()).add(src["rel"])
    all_stems = sorted({n["stem"] for n in v.notes})

    def describe(n):
        return {"rel": n["rel"], "sha256": hashlib.sha256(n["path"].read_bytes()).hexdigest(),
                "chars": len(texts[n["rel"]])}

    groups, sm = {}, difflib.SequenceMatcher()  # one group per title, near-matches joined to it
    for i, a in enumerate(in_scope):
        ta = norm_title(a["stem"])
        sm.set_seq2(ta)
        for b in in_scope[i + 1:]:
            tb = norm_title(b["stem"])
            sm.set_seq1(tb)
            if ta and (ta == tb or (sm.real_quick_ratio() >= 0.9 and sm.quick_ratio() >= 0.9 and sm.ratio() >= 0.9)):
                key = next((k for k, g in groups.items() if a["rel"] in g or b["rel"] in g), a["rel"])
                groups.setdefault(key, []).extend(r for r in (a["rel"], b["rel"]) if r not in groups.get(key, []))
    dupes = [{"notes": g, "same_title": len({norm_title(Path(r).stem) for r in g}) == 1} for g in groups.values()]

    broken, ambiguous = [], []
    for n in in_scope:
        for t, hits in resolved.get(n["rel"], []):
            if not hits:
                broken.append({"note": n["rel"], "target": t,
                               "suggest": difflib.get_close_matches(Path(t).name, all_stems, n=3, cutoff=0.6)})
            elif len(hits) > 1:
                ambiguous.append({"note": n["rel"], "target": t, "candidates": [h["rel"] for h in hits]})

    misfiled = []
    for n in in_scope:
        home = scope_folder(n["rel"], curate)
        neighbours = {h["rel"] for _, hits in resolved.get(n["rel"], []) for h in hits} | back.get(n["rel"], set())
        votes = Counter(scope_folder(r, curate) for r in neighbours if r in scope_rels and r != n["rel"])
        if votes:
            best, count = votes.most_common(1)[0]
            total = sum(votes.values())
            if best != home and count >= 2 and count * 2 > total:
                misfiled.append({"note": n["rel"], "in": home, "links_point_to": best, "votes": f"{count}/{total}"})

    cutoff = (today.year * 12 + today.month) - stale_months
    dated = []
    for n in in_scope:
        for i, line in enumerate(texts[n["rel"]].splitlines(), 1):
            m = DATE_RE.search(line)
            if m and int(m.group(1)) * 12 + int(m.group(2)) <= cutoff and re.search(
                    r"\b(as of|status|currently|current|now|today|latest|update[sd]?)\b", line, re.I):
                dated.append({"note": n["rel"], "line": i, "text": line.strip()[:200]})

    link_sets = {n["rel"]: {h["rel"] for _, hits in resolved.get(n["rel"], []) for h in hits} for n in in_scope}
    pairs = []
    for a, b in combinations(in_scope, 2):
        shared = len(link_sets[a["rel"]] & link_sets[b["rel"]])
        if shared >= 2 or (b["rel"] in link_sets[a["rel"]] and a["rel"] in link_sets[b["rel"]]):
            pairs.append({"notes": [a["rel"], b["rel"]], "shared_links": shared})
    pairs.sort(key=lambda p: -p["shared_links"])

    inbox_out = []
    for n in in_inbox:
        mine = {h["rel"] for _, hits in resolved.get(n["rel"], []) for h in hits}
        scored = []
        for s in in_scope:
            score = difflib.SequenceMatcher(None, norm_title(n["stem"]), norm_title(s["stem"])).ratio()
            score += 0.2 * len(mine & (link_sets[s["rel"]] | {s["rel"]}))
            scored.append((round(score, 2), s["rel"]))
        scored.sort(reverse=True)
        inbox_out.append({**describe(n), "candidates": [{"rel": r, "score": sc} for sc, r in scored[:5] if sc >= 0.4]})

    fm = [{"note": n["rel"], "problem": p} for n in in_scope if (p := malformed(texts[n["rel"]]))]
    lists = {
        "duplicate_titles": dupes,
        "broken_links": broken,
        "ambiguous_links": ambiguous,
        "orphans": [{"note": n["rel"]} for n in in_scope if not back.get(n["rel"])],
        "oversized": [{"note": n["rel"], "chars": len(texts[n["rel"]])} for n in in_scope
                      if len(texts[n["rel"]]) > size_budget],
        "frontmatter": fm,
        "misfiled": misfiled,
        "dated_lines": dated,
    }
    totals = {}
    for name, items in lists.items():  # at most per_folder items from each scope folder, so one big folder cannot crowd out the rest
        kept, per = [], Counter()
        for item in items:
            folder = scope_folder(item.get("note") or item["notes"][0], curate)
            per[folder] += 1
            if per[folder] <= per_folder:
                kept.append(item)
        totals[name] = dict(per)
        lists[name] = kept
    return {"vault": str(v.root), "curate_dirs": curate, "inbox": inbox, "today": today.isoformat(),
            "notes": len(in_scope), **lists, "totals_by_folder": totals,
            "related_pairs": pairs[:batch], "inbox_notes": inbox_out}


def main(argv=None):
    ap = argparse.ArgumentParser(description="The vault curator's computed lists; writes nothing in the vault.")
    ap.add_argument("--vault", help="vault root (default: setting vault_dir)")
    ap.add_argument("--out", help="write the JSON here as well as printing a summary")
    ap.add_argument("--size-budget", type=int, default=15000, help="characters a note may hold (default 15000)")
    ap.add_argument("--stale-months", type=int, default=6, help="a dated status older than this is listed")
    ap.add_argument("--batch", type=int, default=10, help="related pairs to read for contradictions")
    ap.add_argument("--per-folder", type=int, default=15, help="items per scope folder in each list (default 15)")
    args = ap.parse_args(argv)
    conf = settings()
    curate = [str(d).strip().replace("\\", "/").strip("/") for d in conf.get("vault_curate_dirs") or []]
    if not curate:
        fail("No curate scope: set vault_curate_dirs (folders inside the vault) in the owner's settings.", 2)
    v = Vault(args.vault)
    inbox = (conf.get("vault_inbox") or "").strip("/")
    result = scan(v, curate, inbox, args.size_budget, args.stale_months, args.batch, args.per_folder)
    if args.out:
        out = Path(args.out).expanduser().resolve()
        if out.is_relative_to(v.root):
            fail("The scan is written outside the vault; give an --out path in the Run folder.", 2)
        out.write_text(json.dumps(result, indent=1), encoding="utf-8")
        counts = {k: sum(val.values()) for k, val in result["totals_by_folder"].items()}
        counts.update(notes=result["notes"], inbox_notes=len(result["inbox_notes"]))
        print(json.dumps({"out": str(out), "counts": counts}, indent=1))
    else:
        print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
