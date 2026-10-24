"""This skill's copy of _skill_paths.py finds a sibling skill's file in the checkout it lives in."""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.modules.pop("_skill_paths", None)  # another skill's copy may be loaded in the same run
import _skill_paths  # noqa: E402


def test_finds_this_skills_own_folder_first():
    found = _skill_paths.skill_file(HERE.parent.name, "SKILL.md", start=HERE / "_skill_paths.py")
    assert found == HERE.parent / "SKILL.md"


def test_names_home_skills_last_when_nothing_holds_the_file():
    found = _skill_paths.skill_file("no-such-skill", "scripts", "x.py", start=HERE / "_skill_paths.py")
    assert found.parts[-3:] == ("no-such-skill", "scripts", "x.py")
    assert not found.exists()
