#!/usr/bin/env python3
"""Find duplicate and undated transcripts in a folder. Reports only; never moves or deletes.

Transcript folders collect the same meeting in several forms (a raw .srt or .vtt export, a
collapsed .txt, a pasted .md) and files whose names give no date. Reading them all counts a
meeting twice; reading an undated one cannot be cited by date. The rules:

- Files under the folder ending .txt, .md, .srt or .vtt are scanned, subfolders included.
- Two files are one meeting when their names differ only by extension (and case and
  punctuation), or when their first 400 characters of speech match once cue numbers,
  timestamps and voice tags are stripped. The copy to read is the collapsed text form
  (.txt, then .md, then .vtt, then .srt), the larger file breaking a tie.
- The date in the file name (YYYY-MM-DD, YYYYMMDD, or with _ or .) is authoritative over
  the file's modified time. A file with none is undated and cannot be cited by date.

Input: one folder. Prints a short report, or --format json with every file and its issues.
Exit 0 ok, 2 when the folder does not exist.

Example:
  python3 transcript_hygiene.py "Transcripts/" --format json
"""

import argparse
import json
import re
import sys
from pathlib import Path

DATE_RE = re.compile(r"(20\d{2})[-_.]?(\d{2})[-_.]?(\d{2})")
EXTS = {".txt", ".md", ".srt", ".vtt"}
PREFER = {".txt": 0, ".md": 1, ".vtt": 2, ".srt": 3}  # lower is read first


def name_date(name):
    m = DATE_RE.search(name)
    if not m:
        return None
    y, mo, d = m.groups()
    return f"{y}-{mo}-{d}" if 1 <= int(mo) <= 12 and 1 <= int(d) <= 31 else None


def stem_key(name):
    s = re.sub(r"\.transcript$", "", Path(name).stem.lower())
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def fingerprint(path):
    """The first 400 characters of speech, lower case, with cue numbers, timestamps and tags removed."""
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:6000]
    except OSError:
        return ""
    kept = []
    for ln in head.splitlines():
        ln = ln.strip()
        if not ln or ln.isdigit() or "-->" in ln or ln.upper() == "WEBVTT":
            continue
        ln = re.sub(r"^\[?\d{1,2}:\d{2}(:\d{2})?\]?\s*", "", ln)
        kept.append(re.sub(r"^<v\s+[^>]+>", "", ln))
        if sum(len(x) for x in kept) > 400:
            break
    return re.sub(r"\s+", " ", " ".join(kept))[:400].lower()


def scan(folder):
    items = [{"path": p, "stem": stem_key(p.name), "name_date": name_date(p.name), "fp": fingerprint(p),
              "size": p.stat().st_size, "issues": []}
             for p in sorted(folder.rglob("*"))
             if p.is_file() and p.suffix.lower() in EXTS and not p.name.startswith(".")]

    groups = {}
    for it in items:
        groups.setdefault(f"stem:{it['stem']}", []).append(it)
        if it["fp"]:
            groups.setdefault(f"fp:{it['fp'][:120]}", []).append(it)
    seen, dup_sets = set(), []
    for key, members in groups.items():
        paths = tuple(sorted(str(m["path"]) for m in members))
        if len(members) < 2 or paths in seen:
            continue
        seen.add(paths)
        by = "name" if key.startswith("stem") else "content"
        canon = min(members, key=lambda m: (PREFER.get(m["path"].suffix.lower(), 9), -m["size"]))
        others = [m for m in members if m is not canon]
        for m in others:
            m["issues"].append(f"duplicate of {canon['path'].name} ({'same name' if by == 'name' else 'same opening text'})")
        dup_sets.append({"by": by, "canonical": str(canon["path"]), "others": [str(m["path"]) for m in others]})

    for it in items:
        if not it["name_date"]:
            it["issues"].append("undated filename; cannot be cited by date")
    return {"folder": str(folder), "files": len(items), "duplicate_sets": dup_sets,
            "undated": [str(i["path"]) for i in items if not i["name_date"]],
            "items": [{"path": str(i["path"]), "name_date": i["name_date"], "size": i["size"], "issues": i["issues"]}
                      for i in items]}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Report duplicate and undated transcripts under a folder. Read only.")
    ap.add_argument("folder")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    args = ap.parse_args(argv)
    folder = Path(args.folder).expanduser()
    if not folder.is_dir():
        print(f"Not a directory: {folder}", file=sys.stderr)
        return 2
    r = scan(folder)
    if args.format == "json":
        print(json.dumps(r, indent=1))
        return 0
    print(f"{r['files']} transcript files under {r['folder']}")
    if r["duplicate_sets"]:
        print(f"\n{len(r['duplicate_sets'])} duplicate set(s); read the canonical copy, skip the others:")
        for d in r["duplicate_sets"]:
            print(f"  keep   {Path(d['canonical']).name}   (matched by {d['by']})")
            for o in d["others"]:
                print(f"  skip   {Path(o).name}")
    if r["undated"]:
        print(f"\n{len(r['undated'])} undated (no YYYY-MM-DD in the name):")
        for u in r["undated"]:
            print(f"  {Path(u).name}")
    if not r["duplicate_sets"] and not r["undated"]:
        print("Clean: no duplicates, every file dated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
