#!/usr/bin/env python3
"""Build one merged folder of agents and skills from this toolbox checkout.

The merged folder (default ~/.local/share/f3i-toolbox, or the folder named by the
argument or F3I_TOOLBOX_LINK_DIR) holds:

  agents/<department>/<name>.md   a file link to <toolbox>/<department>/agents/<name>.md
  skills/<skill>                  a folder link to <toolbox>/<department>/skills/<skill>

Agents are file links inside real department folders because some runtimes walk
the agents folder without following folder links. Skills are flat, so
~/.claude/skills/<skill>/SKILL.md resolves once ~/.claude/skills points here.

A shared skill (scripts/build_shared.py) has one source, shared/skills/<skill>, and a
marked copy (a .shared-copy file naming that source) in each department that uses it.
Its link goes to the source, once, however many departments hold a copy. shared/ is
not a department; its skills are linked only through their copies.

Rerunning is safe. Links into this toolbox that no longer have a source are
removed. A real file, or a link that points outside this toolbox, is never touched;
if one sits where a link should go, it is reported and the run fails. Two
departments with the same agent name, or with the same skill name when they are not
both marked copies of one shared source, fail the run before anything changes.

It does not repoint ~/.claude/skills or ~/.claude/agents; it prints the commands.

Usage:
  python3 setup/link.py [LINK_DIR]          build or update the merged folder
  python3 setup/link.py --check [LINK_DIR]  report what would change, change nothing
  python3 setup/link.py --print-paths       print the agents and skills folder paths

Exit status: 0 done (or, with --check, nothing to change); 1 with --check when
something would change; 2 on a name collision or a path held by something else.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys
from pathlib import Path

TOOLBOX = Path(__file__).resolve().parent.parent
DEFAULT_LINK_DIR = Path("~/.local/share/f3i-toolbox")


def tilde(path: Path) -> str:
    """Show a path under the home folder as ~/..., for printing."""
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def link_dir_from(arg: str | None) -> Path:
    raw = arg or os.environ.get("F3I_TOOLBOX_LINK_DIR") or str(DEFAULT_LINK_DIR)
    return Path(os.path.abspath(Path(raw).expanduser()))


SHARED_COPY = ".shared-copy"


def shared_source(toolbox: Path, copy: Path) -> Path | None:
    """The shared/skills/<skill> source a marked copy names, or None when the folder is no copy."""
    marker = copy / SHARED_COPY
    if not marker.is_file():
        return None
    for line in marker.read_text(encoding="utf-8").splitlines():
        if line.startswith("source: shared/skills/"):
            return toolbox / "shared" / "skills" / line.removeprefix("source: shared/skills/").strip()
    return toolbox / "shared" / "skills" / "?"


def skill_source(toolbox: Path, name: str, paths: list[Path]) -> Path | None:
    """The one folder skill `name` links to: the department's own skill when only one
    department has it, or the shared source when every holder is a marked copy of it."""
    shared = {shared_source(toolbox, p) for p in paths}
    if len(shared) == 1 and None not in shared:
        src = shared.pop()
        return src if src.name == name and (src / "SKILL.md").is_file() else None
    return paths[0] if len(paths) == 1 and shared == {None} else None


def sources(toolbox: Path) -> tuple[dict[Path, Path], list[str]]:
    """Map each wanted link (relative to the link folder) to its source, and list collisions."""
    wanted: dict[Path, Path] = {}
    agents: dict[str, list[Path]] = {}
    skills: dict[str, list[Path]] = {}
    for dept in sorted(p for p in toolbox.iterdir() if p.is_dir() and not p.name.startswith(".")):
        if dept.name == "shared":
            continue
        for agent in sorted((dept / "agents").glob("*.md")):
            if agent.is_file():
                agents.setdefault(agent.stem, []).append(agent)
        for skill in sorted((dept / "skills").glob("*/SKILL.md")):
            skills.setdefault(skill.parent.name, []).append(skill.parent)
    collisions = []
    for name, paths in sorted(agents.items()):
        if len(paths) > 1:
            where = ", ".join(str(p.relative_to(toolbox)) for p in paths)
            collisions.append(f"agent name '{name}' is used more than once: {where}")
        else:
            wanted[Path("agents") / paths[0].parent.parent.name / paths[0].name] = paths[0]
    for name, paths in sorted(skills.items()):
        src = skill_source(toolbox, name, paths)
        if src is not None:
            wanted[Path("skills") / name] = src
            continue
        where = ", ".join(str(p.relative_to(toolbox)) for p in paths)
        named = {shared_source(toolbox, p) for p in paths}
        if len(named) == 1 and None not in named:
            collisions.append(f"skill '{name}' is held only by copies of {next(iter(named)).relative_to(toolbox)}, "
                              f"which has no SKILL.md: {where}")
        elif any(named - {None}):
            collisions.append(f"skill name '{name}' is held by folders that are not all copies of "
                              f"shared/skills/{name}: {where}")
        else:
            collisions.append(f"skill name '{name}' is used more than once: {where}")
    return wanted, collisions


def points_into(link: Path, toolbox: Path) -> bool:
    target = Path(os.path.abspath(link.parent / os.readlink(link)))
    return target == toolbox or toolbox in target.parents


def existing_links(link_dir: Path) -> list[Path]:
    """Every link under agents/ and skills/ of the link folder, relative to it."""
    found = []
    for top in ("agents", "skills"):
        base = link_dir / top
        if not base.is_dir() or base.is_symlink():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            for name in dirnames + filenames:
                p = Path(dirpath) / name
                if p.is_symlink():
                    found.append(p.relative_to(link_dir))
    return found


def plan(link_dir: Path, toolbox: Path) -> tuple[list[tuple[str, Path, Path | None]], list[str]]:
    """Return the actions (add, replace, remove) and the problems that stop the run."""
    wanted, problems = sources(toolbox)
    if link_dir == toolbox or toolbox in link_dir.parents:
        problems.append(f"the link folder {tilde(link_dir)} is inside the toolbox")
    for top in ("agents", "skills"):
        p = link_dir / top
        if p.is_symlink() or (p.exists() and not p.is_dir()):
            problems.append(f"{tilde(p)} is not a real folder; move it aside first")
    if problems:
        return [], problems
    actions: list[tuple[str, Path, Path | None]] = []
    for rel, src in sorted(wanted.items()):
        p = link_dir / rel
        if p.is_symlink():
            if not points_into(p, toolbox):
                problems.append(f"{tilde(p)} is a link to outside the toolbox; left alone")
            elif os.readlink(p) != str(src):
                actions.append(("replace", rel, src))
        elif p.exists():
            problems.append(f"{tilde(p)} is a real file or folder; left alone")
        else:
            actions.append(("add", rel, src))
    for rel in sorted(existing_links(link_dir)):
        if rel not in wanted and points_into(link_dir / rel, toolbox):
            actions.append(("remove", rel, None))
    return actions, problems


def apply(link_dir: Path, actions) -> None:
    for kind, rel, src in actions:
        p = link_dir / rel
        if kind in ("replace", "remove"):
            p.unlink()
        if kind in ("add", "replace"):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.symlink_to(src, target_is_directory=src.is_dir())
    agents = link_dir / "agents"
    if agents.is_dir():
        for dept in agents.iterdir():
            if dept.is_dir() and not dept.is_symlink() and not any(dept.iterdir()):
                dept.rmdir()
    (link_dir / "skills").mkdir(parents=True, exist_ok=True)
    agents.mkdir(parents=True, exist_ok=True)


def repoint_commands(link_dir: Path) -> list[str]:
    stamp = datetime.date.today().strftime("%Y%m%d")
    lines = []
    for top in ("skills", "agents"):
        current = f"~/.claude/{top}"
        lines.append(f"mv {current} {current}.bak-{stamp}")
        lines.append(f"ln -s {tilde(link_dir / top)} {current}")
    return lines


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build the merged agents and skills folder.")
    parser.add_argument("link_dir", nargs="?", help="default: $F3I_TOOLBOX_LINK_DIR or ~/.local/share/f3i-toolbox")
    parser.add_argument("--check", action="store_true", help="report what would change; change nothing")
    parser.add_argument("--print-paths", action="store_true", help="print the agents and skills folder paths")
    parser.add_argument("--quiet", action="store_true",
                        help="for the git hooks: print one line only when something changed, and nothing else")
    args = parser.parse_args(argv)
    link_dir = link_dir_from(args.link_dir)

    if args.print_paths:
        print(link_dir / "agents")
        print(link_dir / "skills")
        return 0

    actions, problems = plan(link_dir, TOOLBOX)
    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    if problems:
        print("nothing changed", file=sys.stderr)
        return 2

    for kind, rel, src in ([] if args.quiet else actions):
        print(f"{'would ' if args.check else ''}{kind} {rel}" + (f" -> {tilde(src)}" if src else ""))
    wanted, _ = sources(TOOLBOX)
    n_agents = sum(1 for r in wanted if r.parts[0] == "agents")
    n_skills = len(wanted) - n_agents
    if args.check:
        print(f"{len(actions)} change(s) would be made in {tilde(link_dir)}")
        return 1 if actions else 0

    apply(link_dir, actions)
    if args.quiet:
        if actions:
            print(f"toolbox links: {len(actions)} change(s) in {tilde(link_dir)}")
        return 0
    print(f"{n_agents} agents and {n_skills} skills linked in {tilde(link_dir)} ({len(actions)} change(s))")
    print("\nTo point Claude Code at it (not done for you), run:")
    for line in repoint_commands(link_dir):
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
