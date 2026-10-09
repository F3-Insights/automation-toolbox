#!/usr/bin/env python3
"""List every skill the owner already has and how often the matched sessions used each one.

Finds skills in four kinds of place:

- user: the Claude Code skills folder in the home folder;
- codex: Codex's skills folders (its own and the shared agents folder), system skills included;
- plugin: installed plugins, synced and cached, for Claude Code and Codex; only the newest
  cached version of a plugin counts, and a plugin's trash is never read;
- project: the skills folders inside each repository the pack's sessions worked in or loaded a
  skill from, any repository or folder given with ``--project-dir``, and every repository
  directly under a ``--projects-root`` folder.

A skill reached from several places (a symlink, a synced copy, a worktree's copy with the same
text) is one entry with every location listed. Two skills with one name and different text stay
two entries: that is an overlap worth knowing.

For each skill: name, how it is invoked, description, kinds, locations, whether it has a
``## Steps`` section, its size, its scripts, the paths outside its own folder it points at (a
sign it depends on one machine's repositories), and its use in the pack's matched sessions
(``skill_events``): Skill tool calls, slash commands, reads of its SKILL.md, ``$skill`` mentions,
with sessions, dates, and typed versus automated. Edits inside its folder are counted apart: they
are maintenance, not use. Loads of a name no skill on the machine carries (renamed or removed)
are listed as ``unmatched``.

Standard library only. Exit codes: 0 with ``SKILLS: ...`` on the first line of stdout, 2 when it
could not run (no pack, a refused output path).

Example:
    python3 skill_inventory.py --pack ~/work/pack.json --skills-dir ~/src/toolbox/finance/skills --out ~/work/skills.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

DESC_CHARS = 400
DATES_KEPT = 30
SESSIONS_KEPT = 15
PROJECT_SKILL_DIRS = (".claude/skills", ".agents/skills", ".codex/skills")
VERSION = re.compile(r"^v?\d+(?:\.\d+)*(?:[-+.][\w.]+)?$")
OUTSIDE = re.compile(r"""(?:~|/(?:home|Users|mnt|opt|srv|var/lib))/[^\s`'"()<>\]\[,;]+""")
RELATIVE = re.compile(r"`(\.?[\w.-]+(?:/[\w.-]+)+/?)[`\s]")


class Refused(Exception):
    pass


# --- reading one skill ----------------------------------------------------------------------


def frontmatter(text: str) -> Dict[str, str]:
    """The ``name`` and ``description`` of a SKILL.md, folded YAML blocks and quotes included."""
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    out: Dict[str, str] = {}
    if not m:
        return out
    lines = m.group(1).splitlines()
    i = 0
    while i < len(lines):
        key = re.match(r"^([\w-]+):\s*(.*)$", lines[i])
        i += 1
        if not key:
            continue
        value = key.group(2).strip()
        if value in (">", "|", ">-", "|-", ""):
            block = []
            while i < len(lines) and (lines[i].startswith((" ", "\t")) or not lines[i].strip()):
                block.append(lines[i].strip())
                i += 1
            value = " ".join(b for b in block if b)
        out[key.group(1)] = value.strip().strip("\"'")
    return out


def clip(text: str, n: int = DESC_CHARS) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def plugin_name(skills_dir: Path) -> str:
    root = skills_dir.parent
    for meta in (root / ".claude-plugin" / "plugin.json", root / ".codex-plugin" / "plugin.json"):
        try:
            name = json.loads(meta.read_text(encoding="utf-8")).get("name")
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(name, str) and name:
            return name
    return root.parent.name if VERSION.match(root.name) else root.name


def read_skill(skill_md: Path, kind: str, plugin: Optional[str]) -> Dict[str, Any]:
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    meta = frontmatter(text)
    folder = skill_md.parent
    name = meta.get("name") or folder.name
    real = os.path.realpath(folder)
    outside = []
    for ref in OUTSIDE.findall(text):
        ref = ref.rstrip(".:")
        full = os.path.realpath(os.path.expanduser(ref))
        if not full.startswith(real + os.sep) and ref not in outside:
            outside.append(ref)
    for ref in RELATIVE.findall(text):  # a relative path the skill's own folder does not hold
        if not (folder / ref).exists() and ref not in outside:
            outside.append(ref)
    scripts = folder / "scripts"
    return {
        "name": name,
        "invoke": f"{plugin}:{name}" if plugin else name,
        "folder": folder.name,
        "plugin": plugin,
        "description": clip(meta.get("description", "")),
        "kinds": [kind],
        "locations": [str(folder)],
        "real": [real],
        "has_steps": bool(re.search(r"^## Steps\b", text, re.MULTILINE)),
        "words": len(text.split()),
        "scripts": sorted(p.name for p in scripts.iterdir() if p.is_file()) if scripts.is_dir() else [],
        "points_outside": outside[:8],
        "_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


# --- finding skills -------------------------------------------------------------------------


def trash(path: Path) -> bool:
    return any(part.lower().lstrip(".").startswith("trash") for part in path.parts)


def skill_files(skills_dir: Path) -> List[Path]:
    """``<dir>/<skill>/SKILL.md`` and Codex's ``<dir>/.system/<skill>/SKILL.md``."""
    if not skills_dir.is_dir() or trash(skills_dir):
        return []
    found = sorted(skills_dir.glob("*/SKILL.md")) + sorted(skills_dir.glob(".system/*/SKILL.md"))
    return [f for f in found if f.is_file()]


def plugin_skill_dirs(root: Path, depth: int = 5) -> List[Path]:
    """Every ``skills`` folder of a plugin under ``root``, the newest cached version only, no trash."""
    if not root.is_dir():
        return []
    found: List[Path] = []
    for here, dirs, _ in os.walk(root, followlinks=False):
        path = Path(here)
        dirs[:] = [d for d in dirs if not trash(Path(d)) and d != "node_modules"]
        if len(path.relative_to(root).parts) >= depth:
            dirs[:] = []
        if path.name == "skills" and path != root:
            found.append(path)
            dirs[:] = []
    newest: Dict[Path, Tuple[Tuple, Path]] = {}
    keep = []
    for d in found:
        version = d.parent.name
        if VERSION.match(version):
            key = tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.\-+]", version.lstrip("v")))
            group = d.parent.parent
            if group not in newest or key > newest[group][0]:
                newest[group] = (key, d)
        else:
            keep.append(d)
    return sorted(keep + [d for _, d in newest.values()])


def git_root(path: Path) -> Optional[Path]:
    for parent in [path, *path.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def event_projects(events: Iterable[Dict[str, Any]]) -> List[Path]:
    """The repositories whose project skills a session read or edited."""
    out = set()
    for e in events:
        target = str(e.get("skill", ""))
        for sub in PROJECT_SKILL_DIRS:
            marker = "/" + sub + "/"
            if target.startswith("/") and marker in target:
                out.add(Path(target.split(marker, 1)[0]))
    return sorted(out)


def locations(home: Path, project_dirs: Iterable[Path], extra: Iterable[Path]) -> List[Tuple[str, Path, Optional[bool]]]:
    """(kind, skills folder, is a plugin folder) for every place a skill can live."""
    out: List[Tuple[str, Path, Optional[bool]]] = [("user", home / ".claude" / "skills", False)]
    out += [("codex", home / ".codex" / "skills", False), ("codex", home / ".agents" / "skills", False)]
    for root in (home / ".claude" / "plugins" / "synced", home / ".claude" / "plugins" / "cache",
                 home / ".codex" / "plugins" / "cache"):
        out += [("plugin", d, True) for d in plugin_skill_dirs(root)]
    seen = set()
    for p in project_dirs:
        for base in filter(None, {p, git_root(p)}):
            for sub in PROJECT_SKILL_DIRS:
                d = base / sub
                if d.is_dir() and d not in seen and d.parent.parent != home:
                    seen.add(d)
                    out.append(("project", d, False))
    out += [("given", Path(e), False) for e in extra]
    return out


def inventory(places: List[Tuple[str, Path, Optional[bool]]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    merged: Dict[Tuple[str, str], Dict[str, Any]] = {}
    scanned = []
    for kind, folder, is_plugin in places:
        files = skill_files(folder)
        scanned.append({"kind": kind, "path": str(folder), "skills": len(files)})
        plugin = plugin_name(folder) if is_plugin else None
        for f in files:
            try:
                skill = read_skill(f, kind, plugin)
            except OSError:
                continue
            key = (skill["invoke"], skill["_hash"])
            same = merged.get(key)
            if same is None:
                merged[key] = skill
                continue
            for field in ("kinds", "locations", "real"):
                for value in skill[field]:
                    if value not in same[field]:
                        same[field].append(value)
    return list(merged.values()), scanned


# --- matching use to skills -----------------------------------------------------------------


def match(event: Dict[str, Any], skills: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:
    """The skills an event names, and whether the match is exact (a path, or one skill by name)."""
    target = str(event.get("skill", ""))
    if target.startswith("/") and event.get("how") in ("read", "edit"):
        real = os.path.realpath(target)
        hits = [s for s in skills if real in s["real"] or target in s["locations"]]
        if hits:
            return hits, True
        target = os.path.basename(target.rstrip("/"))
    target = target.lstrip("/")
    exact = [s for s in skills if target == s["invoke"]]
    hits = exact or [s for s in skills if target in (s["name"], s["folder"])]
    return hits, len(hits) == 1


def attach_use(skills: List[Dict[str, Any]], events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    use: Dict[int, Dict[str, Any]] = defaultdict(lambda: {"how": Counter(), "sessions": {}, "edits": {},
                                                          "shared": set()})
    unmatched: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for e in events:
        hits, exact = match(e, skills)
        if not hits:
            if e.get("how") in ("tool", "read"):
                u = unmatched.setdefault((e["skill"], e["how"]), {"skill": e["skill"], "how": e["how"],
                                                                  "loads": 0, "dates": set()})
                u["loads"] += e.get("count", 1)
                u["dates"].add(e.get("date"))
            continue
        for s in hits:
            u = use[id(s)]
            if e.get("how") == "edit":
                u["edits"][e["session"]] = e.get("date")
                continue
            u["how"][e["how"]] += e.get("count", 1)
            u["sessions"][e["session"]] = (e.get("date"), e.get("origin"))
            if not exact:
                u["shared"].add(e["session"])
    for s in skills:
        u = use.get(id(s))
        sessions = u["sessions"] if u else {}
        dates = sorted({d for d, _ in sessions.values() if d})
        s["use"] = {
            "sessions": len(sessions),
            "loads": sum(u["how"].values()) if u else 0,
            "by_how": dict(u["how"]) if u else {},
            "typed_sessions": sum(1 for _, o in sessions.values() if o != "automated"),
            "automated_sessions": sum(1 for _, o in sessions.values() if o == "automated"),
            "first": dates[0] if dates else None,
            "last": dates[-1] if dates else None,
            "dates": dates[-DATES_KEPT:],
            "session_ids": sorted(sessions, key=lambda k: sessions[k][0] or "")[-SESSIONS_KEPT:],
            "shared_name_sessions": len(u["shared"]) if u else 0,
            "edit_sessions": len(u["edits"]) if u else 0,
            "edit_dates": sorted({d for d in u["edits"].values() if d})[-DATES_KEPT:] if u else [],
        }
        s.pop("_hash", None)
        s.pop("real", None)
    return [{**u, "dates": sorted(d for d in u["dates"] if d)}
            for u in sorted(unmatched.values(), key=lambda u: -u["loads"])]


def inside_git_tree(path: Path) -> Optional[Path]:
    return git_root(path)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pack", required=True, help="the pack session_pack.py wrote")
    ap.add_argument("--out", required=True, help="where to write the inventory (outside any git working tree)")
    ap.add_argument("--project-dir", action="append", default=[], help="a repository or folder whose "
                    "project skills to include, beyond those the pack's sessions worked in; repeatable")
    ap.add_argument("--projects-root", action="append", default=[], help="a folder of repositories; the "
                    "project skills of every repository directly under it are included; repeatable")
    ap.add_argument("--skills-dir", action="append", default=[], help="any other skills folder; repeatable")
    ap.add_argument("--home", default=str(Path.home()), help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    try:
        out = Path(args.out).expanduser().resolve()
        tree = inside_git_tree(out.parent)
        if tree:
            raise Refused(f"refusing to write the inventory inside a git working tree ({tree})")
        pack_path = Path(args.pack).expanduser()
        if not pack_path.is_file():
            raise Refused(f"no such pack: {pack_path}")
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
        projects = [Path(c) for c in pack.get("cwds", [])]
        if (pack.get("repo") or {}).get("path"):
            projects.append(Path(pack["repo"]["path"]))
        projects += event_projects(pack.get("skill_events", []))
        projects += [Path(p).expanduser() for p in args.project_dir]
        for root in args.projects_root:
            root = Path(root).expanduser()
            if not root.is_dir():
                raise Refused(f"no such folder: {root}")
            projects += sorted(d for d in root.iterdir() if d.is_dir())
        places = locations(Path(args.home).expanduser(), [p for p in projects if p.is_dir()],
                           [Path(p).expanduser() for p in args.skills_dir])
        skills, scanned = inventory(places)
        unmatched = attach_use(skills, pack.get("skill_events", []))
        skills.sort(key=lambda s: (-s["use"]["sessions"], -s["use"]["loads"], s["invoke"]))
        result = {"pack": str(pack_path), "pack_generated_at": pack.get("generated_at"),
                  "query": pack.get("query"), "locations": [p for p in scanned if p["skills"]],
                  "skills": skills, "unmatched": unmatched}
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    except (Refused, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    used = [s for s in skills if s["use"]["sessions"]]
    kinds = Counter(k for s in skills for k in s["kinds"])
    print(f"SKILLS: {len(skills)} skills in {len(result['locations'])} folders; {len(used)} used in the "
          f"matched sessions, {len(skills) - len(used)} never; {len(unmatched)} unmatched names")
    print(f"kinds {json.dumps(dict(sorted(kinds.items())))}")
    print(f"inventory {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
