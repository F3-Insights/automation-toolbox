"""Propose the housekeeping a vault gardener would do, and do none of it.

Three lists, computed from the vault's files and links, never from a model:
- Loose notes: notes at the vault's root, each with a proposed folder, the folder that
  holds most of the notes it links to and the notes linking to it. A note whose links reach
  no folder is listed as "unfiled", never guessed. At most --limit are proposed.
- Thin map notes: notes whose name ends in --moc-suffix (a "map of content") and whose body
  carries the --placeholder marker or is under 200 characters, with the existing notes that
  link to it or share its tags, because a stub is filled only from what the vault holds.
  At most 5.
- Dead checkboxes: notes with unticked "- [ ]" items not modified in --stale-months.

Private folders (setting vault_private_dirs) are never read, and a note or folder given with
--skip is never proposed to move or to receive a note. The script writes nothing:
--as-script prints "mv -n" lines (which never overwrite) for the owner to read and run.

Input: optionally --vault (else the setting vault_dir), --limit, --stale-months,
--moc-suffix, --placeholder, --skip (repeatable), --format text|json, --as-script.

    python3 ~/.claude/skills/obsidian-vault-garden/scripts/vault_garden.py --format json
"""

import argparse
import json
import re
import shlex
import time
from collections import Counter

from _common import Vault

CHECKBOX_RE = re.compile(r"^\s*[-*]\s+\[ \]\s+\S", re.MULTILINE)
MONTH = 30.4 * 86400


def tag_list(meta):
    tags = meta.get("tags")
    return [str(t).lower() for t in (tags if isinstance(tags, list) else [tags] if tags else [])]


def skipped(rel, skip):
    """True when a note or folder is one the owner's rules say the gardener never touches."""
    low = rel.lower().removesuffix(".md")
    return any(low == s or low.startswith(s + "/") for s in skip)


def garden(v, limit=15, stale_months=12, moc_suffix="MOC", placeholder="[placeholder]", skip=()):
    skip = [s.strip("/").lower().removesuffix(".md") for s in skip]
    notes = v.notes
    backlinks = {}  # note rel -> notes linking to it, built in one pass
    for src in notes:
        for target in v.links_of(src):
            for hit in v.resolve(target):
                if hit["rel"] != src["rel"]:
                    backlinks.setdefault(hit["rel"], {})[src["rel"]] = src
    back = {rel: list(d.values()) for rel, d in backlinks.items()}

    loose = []
    for n in notes:
        if n["folder"] or skipped(n["rel"], skip):
            continue
        votes = Counter(hit["folder"] for t in v.links_of(n) for hit in v.resolve(t) if hit["folder"])
        votes.update(src["folder"] for src in back.get(n["rel"], []) if src["folder"])
        for folder in [f for f in votes if skipped(f, skip)]:
            del votes[folder]
        folder = votes.most_common(1)[0][0] if votes else "unfiled"
        loose.append({"note": n["rel"], "proposed_folder": folder, "backlinks": len(back.get(n["rel"], []))})
    loose.sort(key=lambda r: (r["proposed_folder"] == "unfiled", -r["backlinks"], r["note"]))

    stubs = []
    for n in notes:
        if not n["stem"].lower().endswith(moc_suffix.lower()):
            continue
        meta, body = v.read(n)
        text = body.strip()
        if placeholder.lower() not in text.lower() and len(text) >= 200:
            continue
        fill = [b["rel"] for b in back.get(n["rel"], [])]
        tags = set(tag_list(meta))
        if tags:
            for other in notes:
                if len(fill) >= 12:
                    break
                if other["rel"] != n["rel"] and other["rel"] not in fill and tags & set(tag_list(v.read(other)[0])):
                    fill.append(other["rel"])
        stubs.append({"note": n["rel"], "chars": len(text), "fill_from": fill[:12]})
        if len(stubs) >= 5:
            break

    now = time.time()
    dead = []
    for n in notes:
        try:
            mtime = n["path"].stat().st_mtime
        except OSError:
            continue
        if mtime > now - stale_months * MONTH:
            continue
        count = len(CHECKBOX_RE.findall(v.read(n)[1]))
        if count:
            dead.append({"note": n["rel"], "open_checkboxes": count, "months_untouched": round((now - mtime) / MONTH, 1)})
    dead.sort(key=lambda r: -r["months_untouched"])
    return {"vault": str(v.root), "notes": len(notes), "loose_root_notes": len(loose), "proposals": loose[:limit],
            "placeholder_mocs": stubs, "dead_checkboxes": dead}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Propose vault housekeeping; writes nothing.")
    ap.add_argument("--vault", help="vault root (default: setting vault_dir)")
    ap.add_argument("--limit", type=int, default=15, help="loose notes to propose (default 15)")
    ap.add_argument("--stale-months", type=int, default=12)
    ap.add_argument("--moc-suffix", default="MOC", help='name ending of a map-of-content note (default "MOC")')
    ap.add_argument("--placeholder", default="[placeholder]", help="marker of an unfinished stub")
    ap.add_argument("--skip", action="append", default=[], help="a note or folder never moved or moved into (repeatable)")
    ap.add_argument("--as-script", action="store_true", help="print mv -n lines for the proposed filings only")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args(argv)

    r = garden(Vault(args.vault), args.limit, args.stale_months, args.moc_suffix, args.placeholder, args.skip)
    if args.as_script:
        print("#!/usr/bin/env bash\n# vault garden proposal: read every line before running\nset -euo pipefail")
        print("cd " + shlex.quote(r["vault"]))
        for p in r["proposals"]:
            if p["proposed_folder"] != "unfiled":
                print(f"mv -n {shlex.quote(p['note'])} {shlex.quote(p['proposed_folder'] + '/')}")
        return 0
    if args.format == "json":
        print(json.dumps(r, indent=1))
        return 0
    print(f"{r['notes']} notes, {r['loose_root_notes']} loose at the root")
    print(f"\nFile these ({len(r['proposals'])} of {r['loose_root_notes']}):")
    for p in r["proposals"]:
        print(f"  {p['note']:56} -> {p['proposed_folder']}  ({p['backlinks']} backlinks)")
    print(f"\nThin map notes ({len(r['placeholder_mocs'])}):")
    for s in r["placeholder_mocs"]:
        print(f"  {s['note']}  ({s['chars']} chars)")
        for f in s["fill_from"][:6]:
            print(f"      fill from {f}")
    print(f"\nDead checkboxes ({len(r['dead_checkboxes'])} notes):")
    for d in r["dead_checkboxes"][:20]:
        print(f"  {d['note']:56} {d['open_checkboxes']:3} open, {d['months_untouched']} months untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
