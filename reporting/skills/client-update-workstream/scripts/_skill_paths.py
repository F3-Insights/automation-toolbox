"""Find another skill's file through the toolbox checkout this script lives in.

A script that runs a script of another skill used to name it as
~/.claude/skills/<skill>/scripts/<name>, a folder that goes away when the departments
become plugins. skill_file() looks instead in the checkout that holds this file
(followed through any link), in this order:

  1. this department:  <toolbox>/<department>/skills/<skill>/
  2. the shared skills: <toolbox>/shared/skills/<skill>/
  3. any department:   <toolbox>/*/skills/<skill>/ (sorted, so the answer is stable)
  4. ~/.claude/skills/<skill>/, only when none of those holds the file.

The first folder holding the file wins; when none does, the last path is returned so a
caller's "not found" message names where it looked last. Same-skill files are found
relative to __file__ directly, not through here.

The same text sits in each skill that needs it (a skill is copied whole, so it carries
its own copy); scripts/tests/test_skill_paths.py checks the copies match. Standard
library only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, Optional

HOME_SKILLS = Path("~/.claude/skills")


def toolbox_root(start: Optional[Path] = None) -> Optional[Path]:
    """The checkout holding START (default this file): the folder above <department>/skills/."""
    here = Path(start or __file__).resolve()
    for folder in here.parents:
        if folder.name == "skills" and folder.parent != folder.parent.parent:
            return folder.parent.parent
    return None


def candidates(skill: str, start: Optional[Path] = None) -> Iterator[Path]:
    """Every folder skill_file() tries for SKILL, in order, ending with ~/.claude/skills/SKILL."""
    root = toolbox_root(start)
    if root is not None:
        here = Path(start or __file__).resolve()
        own = next((p for p in here.parents if p.name == "skills"), None)
        if own is not None:
            yield own / skill
        yield root / "shared" / "skills" / skill
        for dept_skills in sorted(root.glob("*/skills")):
            if dept_skills != own:
                yield dept_skills / skill
    yield HOME_SKILLS.expanduser() / skill


def skill_file(skill: str, *parts: str, start: Optional[Path] = None) -> Path:
    """The path to PARTS (e.g. "scripts", "x.py") inside SKILL, found as the docstring says."""
    last = None
    for folder in candidates(skill, start):
        last = folder.joinpath(*parts)
        if last.exists():
            return last
    return last
