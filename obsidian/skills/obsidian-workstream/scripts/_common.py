"""What the vault scripts share: the owner's settings, the vault index, frontmatter and links.

Settings (top level of the owner's settings file, all shared by the obsidian skills):
  vault_dir           the vault's root folder; no default, the scripts stop without it
  vault_inbox         the folder inside the vault that agents may write new notes into
  vault_private_dirs  folders inside the vault that are never indexed, read or written
  vault_rules         the owner's VAULT-RULES.md (note kinds, frontmatter keys, prefixes)

The index skips Obsidian's own folders, the trash and every private folder, so a note in
one of them is never found, read, linked or proposed for anything. A symlink counts by where
it really points: one that leads outside the vault or into a private folder is skipped too.
"""

import difflib
import os
import re
import sys
import tomllib
from pathlib import Path

ALWAYS_SKIPPED = {".obsidian", ".trash", ".git", ".stfolder", "node_modules"}

# [[Target]], [[Target|Alias]], [[Target#Heading]], ![[Embed]]: group 1 is the target alone.
WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:#[^\]\|]*)?(?:\|[^\]]*)?\]\]")


def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


def fail(message, code=1):
    print(message, file=sys.stderr)
    sys.exit(code)


class Vault:
    """An indexed vault. The folder scan happens once, on first use."""

    def __init__(self, root=None):
        conf = settings()
        root = root or conf.get("vault_dir")
        if not root:
            fail("No vault configured: set vault_dir in the owner's settings or pass --vault.", 2)
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            fail(f"Vault not found at {self.root}.", 2)
        self.private = [self._private_rel(p) for p in conf.get("vault_private_dirs", [])]
        self._notes = None
        self._links = None

    def _private_rel(self, entry):
        """A private folder as a lower-case path from the vault root, however the owner wrote it.

        "Journal", "Journal/", "./Journal", "Journal\\Daily" and an absolute path inside the vault
        all work. "." makes the whole vault private.
        """
        text = str(entry).strip().replace("\\", "/")
        path = Path(text).expanduser()
        if path.is_absolute():
            resolved = path.resolve()
            text = resolved.relative_to(self.root).as_posix() if resolved.is_relative_to(self.root) else ""
        return os.path.normpath(text or "/nonexistent-outside-vault").replace("\\", "/").strip("/").lower() or "."

    def is_private(self, rel):
        low = rel.lower()
        return any(p == "." or low == p or low.startswith(p + "/") for p in self.private)

    def readable(self, path):
        """True when a file may be read: its real location (symlinks followed) is inside the vault,
        outside every private folder and outside Obsidian's own folders and the trash."""
        real = path.resolve()
        if not real.is_relative_to(self.root):
            return False
        rel = real.relative_to(self.root).as_posix()
        return not (set(Path(rel).parts) & ALWAYS_SKIPPED or self.is_private(rel))

    @property
    def notes(self):
        """Every readable note as a dict: rel (path from the root), stem, folder, path."""
        if self._notes is None:
            found = []
            for path in self.root.rglob("*.md"):
                rel = path.relative_to(self.root).as_posix()
                if set(Path(rel).parts) & ALWAYS_SKIPPED or self.is_private(rel) or not self.readable(path):
                    continue
                folder = Path(rel).parent.as_posix()
                found.append({"rel": rel, "stem": path.stem, "folder": "" if folder == "." else folder, "path": path})
            self._notes = sorted(found, key=lambda n: n["rel"])
        return self._notes

    def read(self, note):
        """(frontmatter, body) of a note; a bad byte is replaced, never fatal."""
        return parse_frontmatter(note["path"].read_text(encoding="utf-8", errors="replace"))

    def links_of(self, note):
        if self._links is None:
            self._links = {n["rel"]: extract_links(n["path"].read_text(encoding="utf-8", errors="replace")) for n in self.notes}
        return self._links.get(note["rel"], [])

    def resolve(self, target):
        """The notes a wikilink target points at: an exact path first, then the file name."""
        cleaned = target.strip().removesuffix(".md")
        by_path = [n for n in self.notes if n["rel"].removesuffix(".md") == cleaned]
        if by_path:
            return by_path
        stem = Path(cleaned).name.lower()
        return [n for n in self.notes if n["stem"].lower() == stem]

    def find(self, query, limit=10):
        """(note, why) pairs, best first: exact title, title prefix, title contains, path, fuzzy."""
        q = query.strip().lower()
        if not q:
            return []
        tiers = {"exact title": [], "title prefix": [], "title contains": [], "path contains": []}
        for n in self.notes:
            stem = n["stem"].lower()
            if stem == q:
                tiers["exact title"].append(n)
            elif stem.startswith(q):
                tiers["title prefix"].append(n)
            elif q in stem:
                tiers["title contains"].append(n)
            elif q in n["rel"].lower():
                tiers["path contains"].append(n)
        ranked = [(n, why) for why, group in tiers.items() for n in group]
        if len(ranked) < limit:
            seen = {n["rel"] for n, _ in ranked}
            for stem in difflib.get_close_matches(q, [n["stem"].lower() for n in self.notes], n=limit, cutoff=0.7):
                for n in self.notes:
                    if n["stem"].lower() == stem and n["rel"] not in seen:
                        ranked.append((n, "fuzzy title"))
                        seen.add(n["rel"])
        return ranked[:limit]

    def resolve_one(self, query):
        """Exactly one note for a query, or stop and list the candidates."""
        matches = self.find(query, limit=6)
        if not matches:
            fail(f"No note matches {query!r}.")
        if len(matches) > 1 and matches[0][1] != "exact title":
            listing = "\n".join(f"  {n['rel']}  ({why})" for n, why in matches)
            fail(f"{query!r} is ambiguous. Candidates:\n{listing}")
        return matches[0][0]

    def backlinks(self, note):
        """Notes whose links resolve to this note."""
        hits = []
        for other in self.notes:
            if other["rel"] != note["rel"] and any(
                    any(c["rel"] == note["rel"] for c in self.resolve(t)) for t in self.links_of(other)):
                hits.append(other)
        return hits


def parse_frontmatter(text):
    """Split leading YAML frontmatter from the body: flat values, [a, b] lists and - item lists.

    A nested mapping comes back as its raw text rather than a wrong guess.
    """
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i].strip() in ("---", "...")), None)
    if end is None:
        return {}, text
    meta, key = {}, None
    for raw in lines[1:end]:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and key is not None:
            item = stripped[2:].strip().strip("\"'")
            current = meta.get(key)
            meta[key] = (current if isinstance(current, list) else ([current] if current else [])) + [item]
            continue
        if ":" not in raw:
            continue
        key, _, value = raw.partition(":")
        key, value = key.strip(), value.strip()
        if value.startswith("[") and value.endswith("]"):
            meta[key] = [v.strip().strip("\"'") for v in value[1:-1].split(",") if v.strip()]
        else:
            meta[key] = [] if value == "" else value.strip("\"'")
    return meta, "\n".join(lines[end + 1:])


def extract_links(text):
    """Wikilink targets in order of first appearance."""
    seen = {}
    for match in WIKILINK_RE.finditer(text):
        target = match.group(1).strip()
        if target:
            seen.setdefault(target, None)
    return list(seen)
