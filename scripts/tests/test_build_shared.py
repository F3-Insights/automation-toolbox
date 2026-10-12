"""build_shared.py: each shared skill copied whole into the departments the manifest lists."""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import build_shared  # noqa: E402


@pytest.fixture
def tb(tmp_path, monkeypatch):
    root = tmp_path / "toolbox"
    src = root / "shared" / "skills" / "widget-method"
    (src / "scripts" / "tests").mkdir(parents=True)
    (src / "SKILL.md").write_text("---\nname: widget-method\ndescription: Count widgets.\n---\n")
    (src / "scripts" / "count.py").write_text("print('count')\n")
    (src / "scripts" / "tests" / "test_count.py").write_text("")
    (src / "scripts" / "__pycache__").mkdir()
    (src / "scripts" / "__pycache__" / "count.cpython-312.pyc").write_bytes(b"\0")
    for dept in ("widgets", "gadgets", "sprockets"):
        (root / dept / "skills" / f"{dept}-own").mkdir(parents=True)
        (root / dept / "skills" / f"{dept}-own" / "SKILL.md").write_text("own")
    manifest(root, "widget-method: [widgets, gadgets]")
    monkeypatch.setattr(build_shared, "ROOT", root)
    return root


def manifest(root: Path, *entries: str) -> None:
    body = "".join(f"  {e}\n" for e in entries)
    (root / "shared" / "manifest.yaml").write_text(f"# which departments get which copy\nskills:\n{body}")


def build(root: Path) -> list:
    actions, problems = build_shared.plan(root)
    assert problems == []
    build_shared.apply(actions, root)
    return actions


def test_each_listed_department_gets_the_whole_skill_and_a_marker(tb):
    build(tb)
    for dept in ("widgets", "gadgets"):
        copy = tb / dept / "skills" / "widget-method"
        assert (copy / "SKILL.md").read_bytes() == (tb / "shared/skills/widget-method/SKILL.md").read_bytes()
        assert (copy / "scripts" / "count.py").is_file()
        assert (copy / "scripts" / "tests" / "test_count.py").is_file()
        assert not (copy / "scripts" / "__pycache__").exists()
        assert "source: shared/skills/widget-method" in (copy / ".shared-copy").read_text()
        assert build_shared.copy_source(copy) == "widget-method"
    assert not (tb / "sprockets" / "skills" / "widget-method").exists()


def test_rerunning_changes_nothing(tb):
    build(tb)
    assert build_shared.plan(tb) == ([], [])


def test_check_fails_when_a_copy_differs_or_is_missing(tb, capsys):
    build(tb)
    (tb / "widgets/skills/widget-method/SKILL.md").write_text("edited by hand")
    (tb / "gadgets/skills/widget-method/scripts/extra.py").write_text("")
    manifest(tb, "widget-method: [widgets, gadgets, sprockets]")
    assert build_shared.main(["--check"]) == 1
    actions, _ = build_shared.plan(tb)
    assert ("write", "widgets/skills/widget-method/SKILL.md") in actions
    assert ("remove", "gadgets/skills/widget-method/scripts/extra.py") in actions
    assert ("write", "sprockets/skills/widget-method/SKILL.md") in actions
    build_shared.apply(actions, tb)
    assert build_shared.plan(tb) == ([], [])
    assert (tb / "widgets/skills/widget-method/SKILL.md").read_text().startswith("---")


def test_an_edit_to_the_source_reaches_every_copy(tb):
    build(tb)
    (tb / "shared/skills/widget-method/scripts/count.py").write_text("print('count v2')\n")
    actions = build(tb)
    assert sorted(actions) == [("write", "gadgets/skills/widget-method/scripts/count.py"),
                               ("write", "widgets/skills/widget-method/scripts/count.py")]


def test_a_copy_no_longer_listed_is_removed_whole(tb):
    build(tb)
    manifest(tb, "widget-method: [widgets]")
    actions = build(tb)
    assert actions == [("drop", "gadgets/skills/widget-method")]
    assert not (tb / "gadgets/skills/widget-method").exists()
    assert (tb / "gadgets/skills/gadgets-own/SKILL.md").exists()


def test_a_departments_own_skill_is_never_touched(tb):
    own = tb / "gadgets" / "skills" / "widget-method"
    own.mkdir()
    (own / "SKILL.md").write_text("mine")
    actions, problems = build_shared.plan(tb)
    assert any("gadgets/skills/widget-method is the department's own skill" in p for p in problems)
    assert not any(rel.startswith("gadgets/") for _, rel in actions)
    assert build_shared.main([]) == 1  # a problem stops the whole run
    assert (own / "SKILL.md").read_text() == "mine"
    assert not (tb / "widgets/skills/widget-method").exists()


def test_manifest_problems(tb):
    (tb / "shared/skills/orphan-method").mkdir()
    (tb / "shared/skills/orphan-method/SKILL.md").write_text("x")
    manifest(tb, "widget-method: [widgets, nowhere]", "ghost-method: [widgets]")
    _, problems = build_shared.plan(tb)
    assert any("'nowhere', which is not a department folder" in p for p in problems)
    assert any("ghost-method, which has no shared/skills/ghost-method/SKILL.md" in p for p in problems)
    assert any("shared/skills/orphan-method is in no department" in p for p in problems)


def test_a_missing_source_never_drops_its_copies(tb):
    build(tb)
    manifest(tb, "widget-method: [widgets, gadgets]", "ghost-method: [widgets]")
    (tb / "shared/skills/widget-method/SKILL.md").unlink()
    actions, problems = build_shared.plan(tb)
    assert not any(kind == "drop" for kind, _ in actions)
    assert problems


def test_the_manifest_reads_flow_and_block_lists():
    got, problems = build_shared.parse_manifest(
        "skills:\n  a-skill: [one, two]  # home first\n  b-skill:\n    - three\n    - four\n")
    assert problems == []
    assert got == {"a-skill": ["one", "two"], "b-skill": ["three", "four"]}
    _, problems = build_shared.parse_manifest("other:\n  a: [x]\n")
    assert problems
