"""_skill_paths.py: a script finds another skill's file through its own checkout, not ~/.claude/skills.

The helper is copied into each skill whose scripts reach another skill (a skill is copied
whole, so it carries its own copy). These tests check the copies match, that the lookup
order holds on a made-up checkout, and that every real copy finds its neighbours here.
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
COPIES = sorted(ROOT.glob("*/skills/*/scripts/_skill_paths.py"))


def load(path: Path, name: str = "skill_paths_under_test"):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_there_are_copies_and_they_match():
    assert len(COPIES) >= 10
    first = COPIES[0].read_text()
    differ = [str(p.relative_to(ROOT)) for p in COPIES if p.read_text() != first]
    assert differ == []


@pytest.mark.parametrize("copy", COPIES, ids=lambda p: p.parts[-3])
def test_each_copy_finds_a_skill_of_this_checkout(copy, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    sp = load(copy)
    assert sp.toolbox_root() == ROOT
    found = sp.skill_file("orchestration-workstream", "SKILL.md")
    assert found.is_file() and ROOT in found.parents


@pytest.fixture
def toolbox(tmp_path, monkeypatch):
    """A made-up checkout: the caller in sales, a skill held three ways, a home with skills."""
    root = tmp_path / "toolbox"
    caller = root / "sales" / "skills" / "bd-caller" / "scripts"
    caller.mkdir(parents=True)
    (caller / "_skill_paths.py").write_text(COPIES[0].read_text())
    for folder in ("sales/skills/both", "shared/skills/both", "shared/skills/shared-only",
                   "accounting/skills/shared-only", "accounting/skills/elsewhere",
                   "marketing/skills/elsewhere"):
        (root / folder / "scripts").mkdir(parents=True)
        (root / folder / "scripts" / "run.py").write_text("")
    home = tmp_path / "home"
    (home / ".claude" / "skills" / "only-at-home" / "scripts").mkdir(parents=True)
    (home / ".claude" / "skills" / "only-at-home" / "scripts" / "run.py").write_text("")
    monkeypatch.setenv("HOME", str(home))
    return root, home, load(caller / "_skill_paths.py")


def test_own_department_comes_first(toolbox):
    root, _, sp = toolbox
    assert sp.skill_file("both", "scripts", "run.py") == root / "sales/skills/both/scripts/run.py"


def test_shared_comes_before_another_department(toolbox):
    root, _, sp = toolbox
    assert sp.skill_file("shared-only", "scripts", "run.py") == root / "shared/skills/shared-only/scripts/run.py"


def test_another_department_is_found_in_a_stable_order(toolbox):
    root, _, sp = toolbox
    assert sp.skill_file("elsewhere", "scripts", "run.py") == root / "accounting/skills/elsewhere/scripts/run.py"


def test_home_skills_only_when_the_checkout_lacks_it(toolbox):
    _, home, sp = toolbox
    assert sp.skill_file("only-at-home", "scripts", "run.py") == home / ".claude/skills/only-at-home/scripts/run.py"
    # Not anywhere: the last place tried, so a "not found" message names a real path.
    assert sp.skill_file("nowhere", "scripts", "run.py") == home / ".claude/skills/nowhere/scripts/run.py"


def test_a_linked_skill_still_finds_its_checkout(toolbox):
    """Run through ~/.claude/skills/<skill> (a link), the lookup still searches the checkout."""
    root, home, _ = toolbox
    link = home / ".claude" / "skills" / "bd-caller"
    link.symlink_to(root / "sales" / "skills" / "bd-caller", target_is_directory=True)
    sp = load(link / "scripts" / "_skill_paths.py", "skill_paths_through_link")
    assert sp.toolbox_root() == root
    assert sp.skill_file("both", "scripts", "run.py") == root / "sales/skills/both/scripts/run.py"
