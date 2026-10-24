"""_skill_paths.py: another skill's file is found in this checkout, never only under ~/.claude/skills."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _skill_paths as sp  # noqa: E402

HERE = Path(sp.__file__).resolve()


def test_this_skill_and_a_shared_one_are_found_in_the_checkout():
    root = sp.toolbox_root(HERE)
    assert root is not None and (root / "productivity").is_dir()
    assert sp.skill_file("weekly-review-workstream", "SKILL.md", start=HERE) == HERE.parents[1] / "SKILL.md"
    shared = sp.skill_file("task-stack-workstream", "SKILL.md", start=HERE)
    assert shared.is_file() and root in shared.parents


def test_a_missing_file_names_the_last_place_looked():
    last = sp.skill_file("no-such-skill", "SKILL.md", start=HERE)
    assert not last.exists() and last.parts[-2:] == ("no-such-skill", "SKILL.md")
