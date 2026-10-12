"""Tests for setup/link.py, run against a fake toolbox with invented departments."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

LINK_PY = Path(__file__).resolve().parent.parent / "link.py"
LINK_SH = LINK_PY.with_name("link.sh")


def make_toolbox(root: Path) -> Path:
    tb = root / "toolbox"
    for dept, agents, skills in (
        ("widgets", ["widget-counter", "widget-checker"], ["widget-method"]),
        ("gadgets", ["gadget-orchestrator"], ["gadget-method", "gadget-tools"]),
    ):
        (tb / dept / "agents").mkdir(parents=True)
        for a in agents:
            (tb / dept / "agents" / f"{a}.md").write_text(f"---\nname: {a}\n---\n")
        for s in skills:
            (tb / dept / "skills" / s / "scripts").mkdir(parents=True)
            (tb / dept / "skills" / s / "SKILL.md").write_text(f"---\nname: {s}\n---\n")
    (tb / "setup").mkdir()
    shutil.copy(LINK_PY, tb / "setup" / "link.py")
    shutil.copy(LINK_SH, tb / "setup" / "link.sh")
    return tb


def run(tb: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    full_env = {k: v for k, v in os.environ.items() if k != "F3I_TOOLBOX_LINK_DIR"}
    full_env.update(env or {})
    return subprocess.run([sys.executable, str(tb / "setup" / "link.py"), *args],
                          capture_output=True, text=True, env=full_env)


def snapshot(d: Path) -> dict:
    out = {}
    for dirpath, dirnames, filenames in os.walk(d):
        for name in dirnames + filenames:
            p = Path(dirpath) / name
            out[str(p.relative_to(d))] = os.readlink(p) if p.is_symlink() else ("dir" if p.is_dir() else p.read_text())
    return out


@pytest.fixture
def tb(tmp_path):
    return make_toolbox(tmp_path)


@pytest.fixture
def out(tmp_path):
    return tmp_path / "merged"


def test_fresh_build(tb, out):
    r = run(tb, str(out))
    assert r.returncode == 0, r.stderr
    agent = out / "agents" / "widgets" / "widget-counter.md"
    assert agent.is_symlink() and not (out / "agents" / "widgets").is_symlink()
    assert agent.resolve() == (tb / "widgets" / "agents" / "widget-counter.md").resolve()
    skill = out / "skills" / "gadget-tools"
    assert skill.is_symlink() and (skill / "SKILL.md").is_file()
    assert (skill / "scripts").is_dir()
    assert len(list((out / "agents").rglob("*.md"))) == 3
    assert len(list((out / "skills").iterdir())) == 3
    assert "3 agents and 3 skills linked" in r.stdout
    assert "mv ~/.claude/skills ~/.claude/skills.bak-" in r.stdout
    assert "ln -s" in r.stdout


def test_rerun_is_noop(tb, out):
    run(tb, str(out))
    before = snapshot(out)
    r = run(tb, str(out))
    assert r.returncode == 0
    assert "(0 change(s))" in r.stdout
    assert snapshot(out) == before
    assert run(tb, "--check", str(out)).returncode == 0


def test_removed_source_is_unlinked(tb, out):
    run(tb, str(out))
    (tb / "gadgets" / "agents" / "gadget-orchestrator.md").unlink()
    shutil.rmtree(tb / "widgets" / "skills" / "widget-method")
    r = run(tb, str(out))
    assert r.returncode == 0, r.stderr
    assert not os.path.lexists(out / "agents" / "gadgets" / "gadget-orchestrator.md")
    assert not (out / "agents" / "gadgets").exists()  # emptied department folder goes too
    assert not os.path.lexists(out / "skills" / "widget-method")
    assert "remove skills/widget-method" in r.stdout


def test_moved_agent_is_relinked(tb, out):
    run(tb, str(out))
    shutil.move(tb / "widgets" / "agents" / "widget-checker.md", tb / "gadgets" / "agents" / "widget-checker.md")
    assert run(tb, str(out)).returncode == 0
    assert (out / "agents" / "gadgets" / "widget-checker.md").is_symlink()
    assert not os.path.lexists(out / "agents" / "widgets" / "widget-checker.md")


def test_collision_fails_and_changes_nothing(tb, out):
    run(tb, str(out))
    before = snapshot(out)
    (tb / "gadgets" / "agents" / "widget-counter.md").write_text("---\nname: widget-counter\n---\n")
    (tb / "widgets" / "skills" / "gadget-tools").mkdir()
    (tb / "widgets" / "skills" / "gadget-tools" / "SKILL.md").write_text("x")
    r = run(tb, str(out))
    assert r.returncode == 2
    assert "agent name 'widget-counter'" in r.stderr
    assert "skill name 'gadget-tools'" in r.stderr
    assert snapshot(out) == before


def share(tb: Path, skill: str, *depts: str) -> None:
    """Make `skill` a shared skill with a marked copy in each department, as build_shared.py does."""
    (tb / "shared" / "skills" / skill).mkdir(parents=True, exist_ok=True)
    (tb / "shared" / "skills" / skill / "SKILL.md").write_text(f"---\nname: {skill}\n---\n")
    for dept in depts:
        copy = tb / dept / "skills" / skill
        copy.mkdir(parents=True, exist_ok=True)
        (copy / "SKILL.md").write_text(f"---\nname: {skill}\n---\n")
        (copy / ".shared-copy").write_text(f"Generated.\nsource: shared/skills/{skill}\n")


def test_copies_of_one_shared_skill_link_its_source_once(tb, out):
    share(tb, "common-method", "widgets", "gadgets")
    r = run(tb, str(out))
    assert r.returncode == 0, r.stderr
    link = out / "skills" / "common-method"
    assert link.is_symlink()
    assert link.resolve() == (tb / "shared" / "skills" / "common-method").resolve()
    assert "3 agents and 4 skills linked" in r.stdout


def test_a_skill_moved_into_shared_is_relinked_to_its_source(tb, out):
    run(tb, str(out))
    shutil.rmtree(tb / "widgets" / "skills" / "widget-method")
    share(tb, "widget-method", "widgets", "gadgets")
    r = run(tb, str(out))
    assert r.returncode == 0, r.stderr
    assert "replace skills/widget-method" in r.stdout
    assert (out / "skills" / "widget-method").resolve() == (tb / "shared" / "skills" / "widget-method").resolve()


def test_a_copy_beside_a_different_skill_of_the_same_name_fails(tb, out):
    run(tb, str(out))
    before = snapshot(out)
    share(tb, "gadget-method", "widgets")  # gadgets has its own, unmarked gadget-method
    r = run(tb, str(out))
    assert r.returncode == 2
    assert "skill name 'gadget-method' is held by folders that are not all copies" in r.stderr
    assert snapshot(out) == before


def test_a_copy_whose_source_is_gone_fails(tb, out):
    share(tb, "common-method", "widgets", "gadgets")
    shutil.rmtree(tb / "shared")
    r = run(tb, str(out))
    assert r.returncode == 2
    assert "held only by copies of shared/skills/common-method, which has no SKILL.md" in r.stderr


def test_shared_alone_is_not_a_department(tb, out):
    share(tb, "orphan-method")  # a source with no copy is not linked
    r = run(tb, str(out))
    assert r.returncode == 0, r.stderr
    assert not os.path.lexists(out / "skills" / "orphan-method")


def test_foreign_link_and_real_file_untouched(tb, out, tmp_path):
    run(tb, str(out))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (out / "skills" / "my-own-skill").symlink_to(elsewhere, target_is_directory=True)
    (out / "agents" / "widgets" / "notes.md").write_text("mine")
    (out / "skills" / "dangling-foreign").symlink_to(tmp_path / "gone")
    r = run(tb, str(out))
    assert r.returncode == 0, r.stderr
    assert os.readlink(out / "skills" / "my-own-skill") == str(elsewhere)
    assert (out / "agents" / "widgets" / "notes.md").read_text() == "mine"
    assert os.path.lexists(out / "skills" / "dangling-foreign")


def test_real_file_where_link_belongs_fails(tb, out):
    (out / "skills" / "widget-method").mkdir(parents=True)
    r = run(tb, str(out))
    assert r.returncode == 2
    assert "real file or folder" in r.stderr
    assert not (out / "agents").exists()  # nothing was built
    assert (out / "skills" / "widget-method").is_dir() and not (out / "skills" / "widget-method").is_symlink()


def test_check_changes_nothing(tb, out):
    r = run(tb, "--check", str(out))
    assert r.returncode == 1
    assert "would add agents/widgets/widget-counter.md" in r.stdout
    assert not out.exists()
    run(tb, str(out))
    (tb / "widgets" / "agents" / "widget-counter.md").unlink()
    before = snapshot(out)
    r = run(tb, "--check", str(out))
    assert r.returncode == 1
    assert "would remove agents/widgets/widget-counter.md" in r.stdout
    assert snapshot(out) == before


def test_print_paths_and_env(tb, tmp_path):
    target = tmp_path / "from-env"
    r = run(tb, "--print-paths", env={"F3I_TOOLBOX_LINK_DIR": str(target)})
    assert r.stdout.splitlines() == [str(target / "agents"), str(target / "skills")]
    arg = tmp_path / "from-arg"
    r = run(tb, "--print-paths", str(arg), env={"F3I_TOOLBOX_LINK_DIR": str(target)})
    assert r.stdout.splitlines()[0] == str(arg / "agents")


def test_shell_wrapper(tb, out):
    r = subprocess.run(["sh", str(tb / "setup" / "link.sh"), str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert (out / "skills" / "widget-method").is_symlink()


def test_link_folder_inside_toolbox_refused(tb):
    r = run(tb, str(tb / "merged"))
    assert r.returncode == 2
    assert not (tb / "merged").exists()


def test_quiet_prints_only_when_something_changed(tb, out):
    first = run(tb, "--quiet", str(out))
    assert first.returncode == 0
    assert first.stdout.strip().startswith("toolbox links:") and "To point Claude Code" not in first.stdout
    again = run(tb, "--quiet", str(out))
    assert again.returncode == 0 and again.stdout == ""
