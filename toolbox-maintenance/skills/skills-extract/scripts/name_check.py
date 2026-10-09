#!/usr/bin/env python3
"""Check drafted skills for private names, paths and identifiers before anyone sees them.

Scans every text file under the given folders or files for:

- names from ``--names`` files: one name per line, or the lines under a heading that contains
  "private names" in an owner-context file;
- the ``private_terms`` a data pack carries (folder names, mailbox addresses, the login name);
- the private-name denylist the toolbox check reads, kept outside any repository: each file named
  in ``F3I_TOOLBOX_DENYLIST`` (separated by ``:``) and ``~/.config/f3i-toolbox/denylist.txt``
  when it exists. One term per line, ``#`` a comment, ``=`` before a term matches it
  case-sensitively, ``@`` names another list file to read. ``--no-denylist`` skips it;
- patterns no generic skill needs: an absolute home or user path, an email address, a run of
  seven or more digits (an account or card number), a token-shaped secret.

Names match case-insensitively on whole words, so a name is caught inside a path segment, an
``@``-handle or a ``snake_case`` identifier as well as in prose.

A file's path is checked for names too.

What matched is never printed: a hit is reported as ``file:line: kind`` so the private name, the
address or the number does not travel into a log, a Run file or a commit. A file whose own path
holds a name is shown as ``(path withheld)`` under the target it was found in.

Exit codes: 0 with ``CLEAN`` on the first line; 3 with ``HITS: N`` and one line per hit
(file:line and kind); 2 when it could not run.

Example:
    python3 name_check.py RUN/drafts --pack ~/work/pack.json --names ~/private/owner-context.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

WORD = re.compile(r"[a-z0-9]+")
PATTERNS = [
    ("home path", re.compile(r"(?:/home/|/Users/|/mnt/[a-z]/[Uu]sers/|[A-Za-z]:\\+Users\\+)[^\s/\\`'\")]+")),
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z][\w.-]*")),
    ("long number", re.compile(r"(?<![\w.-])\d{7,}(?![\w-]|\.\d)")),
    ("secret", re.compile(r"\b(?:sk|pk|ghp|gho|xox[bp])[-_][A-Za-z0-9_-]{16,}\b")),
]
# Generic placeholders a skill may show: example.com mail, the placeholder user in a path.
ALLOWED = re.compile(r"@example\.(?:com|org)\b|/home/(?:you|user|USER|<[^>]+>)\b|/Users/(?:you|user|<[^>]+>)\b")
SUFFIXES = {".md", ".txt", ".py", ".json", ".yaml", ".yml", ".toml", ".sh", ".csv", ".html"}
HEADING = re.compile(r"^#+\s*(.*)$")
DEFAULT_DENYLIST = Path("~/.config/f3i-toolbox/denylist.txt").expanduser()


def load_denylist() -> List[Tuple[str, "re.Pattern[str]"]]:
    """The toolbox check's private-name lists: F3I_TOOLBOX_DENYLIST files, then the default file."""
    paths = [Path(p).expanduser() for p in os.environ.get("F3I_TOOLBOX_DENYLIST", "").split(":") if p]
    if DEFAULT_DENYLIST.exists():
        paths.append(DEFAULT_DENYLIST)
    terms, seen = [], set()
    while paths:
        path = paths.pop(0)
        if not path.exists():
            print("note: a denylist file named in F3I_TOOLBOX_DENYLIST or an @ line was not found", file=sys.stderr)
            continue
        if path.resolve() in seen:
            continue
        seen.add(path.resolve())
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("@"):
                paths.append(Path(line[1:]).expanduser())
                continue
            exact = line.startswith("=")
            term = line[1:] if exact else line
            flags = 0 if exact else re.I
            terms.append((term, re.compile(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", flags)))
    return terms


def normalize(text: str) -> str:
    return " ".join(WORD.findall(text.lower()))


def names_from_file(path: Path) -> List[str]:
    """Lines under a "private names" heading; with no such heading, every line of a plain list."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    picked: List[str] = []
    in_section = False
    has_section = False
    for line in lines:
        head = HEADING.match(line.strip())
        if head:
            in_section = "private names" in head.group(1).lower()
            has_section = has_section or in_section
            continue
        if in_section:
            picked.append(line)
    if not has_section:
        body = [ln for ln in lines if ln.strip() and not ln.strip().startswith("#")]
        if body and all(len(ln.split()) <= 6 for ln in body):
            picked = body
        else:
            print(f"note: {path} has no 'Private names' heading and is not a plain list; "
                  "no names taken from it", file=sys.stderr)
    out = []
    for ln in picked:
        ln = re.sub(r"^\s*(?:[-*+]|\d+\.)\s*", "", ln).split("#", 1)[0].strip()
        if normalize(ln):
            out.append(ln)
    return out


def load_names(name_files: Iterable[str], packs: Iterable[str]) -> List[str]:
    names: List[str] = []
    for f in name_files:
        names += names_from_file(Path(f).expanduser())
    for p in packs:
        data = json.loads(Path(p).expanduser().read_text(encoding="utf-8"))
        names += [t for t in data.get("private_terms", []) if isinstance(t, str)]
    return sorted({normalize(n) for n in names if normalize(n)})


def files_under(targets: Iterable[str]) -> List[Path]:
    return [f for f, _ in files_with_roots(targets)]


def files_with_roots(targets: Iterable[str]) -> List[Tuple[Path, Path]]:
    """(file, the target it was found under) for every text file the targets hold."""
    out: List[Tuple[Path, Path]] = []
    for t in targets:
        path = Path(t).expanduser()
        if path.is_file():
            out.append((path, path.parent))
        elif path.is_dir():
            out += [(p, path) for p in sorted(path.rglob("*")) if p.is_file() and p.suffix.lower() in SUFFIXES
                    and "__pycache__" not in p.parts]
        else:
            raise FileNotFoundError(f"no such file or folder: {path}")
    return out


def scan_text(text: str, names: List[str], denylist=()) -> List[Tuple[int, str, str]]:
    grams = {}
    for n in names:
        grams.setdefault(len(n.split()), set()).add(n)
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        words = WORD.findall(line.lower())
        for size, wanted in grams.items():
            for j in range(len(words) - size + 1):
                gram = " ".join(words[j:j + size])
                if gram in wanted:
                    hits.append((i, "name", gram))
        for _term, rx in denylist:
            for m in rx.finditer(line):
                hits.append((i, "denylist", m.group(0)))
        clean = ALLOWED.sub("", line)
        for kind, pattern in PATTERNS:
            for m in pattern.finditer(clean):
                hits.append((i, kind, m.group(0)))
    return hits


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("targets", nargs="+", help="draft folders or files to check")
    ap.add_argument("--names", action="append", default=[], help="a names list or an owner-context file; "
                    "repeatable")
    ap.add_argument("--pack", action="append", default=[], help="a data pack whose private_terms to check "
                    "for; repeatable")
    ap.add_argument("--no-denylist", action="store_true", help="do not read the toolbox's private-name denylist files")
    args = ap.parse_args(argv)
    try:
        names = load_names(args.names, args.pack)
        denylist = [] if args.no_denylist else load_denylist()
        files = files_with_roots(args.targets)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    found = []
    for f, root in files:
        rel = str(f.relative_to(root))
        path_hits = {kind for _, kind, _ in scan_text(rel, names, denylist) if kind in ("name", "denylist")}
        shown = f"{root}/(path withheld)" if path_hits else str(f)
        found += [f"{shown}: {kind} in path" for kind in sorted(path_hits)]
        for line, kind, _what in scan_text(f.read_text(encoding="utf-8", errors="replace"), names, denylist):
            found.append(f"{shown}:{line}: {kind}")
    if not found:
        print("CLEAN")
        print(f"{len(files)} files checked against {len(names)} names, {len(denylist)} denylist terms "
              f"and {len(PATTERNS)} patterns")
        return 0
    print(f"HITS: {len(found)}")
    print("\n".join(found))
    return 3


if __name__ == "__main__":
    sys.exit(main())
