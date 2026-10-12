"""build_bins.py: one wrapper per script in a plugin department's bin/, kept in step."""
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import build_bins  # noqa: E402


@pytest.fixture
def dept(tmp_path, monkeypatch):
    root = tmp_path / "toolbox"
    scripts = root / "widgets" / "skills" / "widget-count" / "scripts"
    (scripts / "tests").mkdir(parents=True)
    (scripts / "count_widgets.py").write_text("import sys\nprint('counted', *sys.argv[1:])\n")
    (scripts / "widgets_report.py").write_text("print('report')\n")
    (scripts / "_common.py").write_text("")
    (scripts / "probe.sh").write_text("echo probed \"$@\"\n")
    (scripts / "loop.template.sh").write_text("")
    (scripts / "tests" / "test_count_widgets.py").write_text("")
    monkeypatch.setattr(build_bins, "ROOT", root)
    return root / "widgets"


def test_names_follow_the_rule():
    assert build_bins.command_name("software", Path("repo_status.py")) == "software-repo-status"
    assert build_bins.command_name("software", Path("software_x.py")) == "software-x"
    assert build_bins.command_name("software", Path("detect-db-type.sh")) == "software-detect-db-type"


def test_every_script_but_helpers_templates_and_tests_gets_a_wrapper(dept):
    actions, problems = build_bins.plan(dept)
    assert problems == []
    assert sorted(n for _, n in actions) == ["widgets-count-widgets", "widgets-probe", "widgets-report"]


def test_a_wrapper_runs_its_script_even_through_a_link(dept, tmp_path):
    want, _ = build_bins.wanted(dept)
    build_bins.apply(dept, build_bins.plan(dept)[0], want)
    link = tmp_path / "elsewhere" / "cw"
    link.parent.mkdir()
    link.symlink_to(dept / "bin" / "widgets-count-widgets")
    out = subprocess.run([str(link), "a", "b c"], capture_output=True, text=True, check=True).stdout
    assert out.strip() == "counted a b c"
    out = subprocess.run([str(dept / "bin" / "widgets-probe"), "x"], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "probed x"


def test_rerunning_changes_nothing_and_stale_wrappers_go(dept):
    want, _ = build_bins.wanted(dept)
    build_bins.apply(dept, build_bins.plan(dept)[0], want)
    assert build_bins.plan(dept) == ([], [])
    (dept / "skills" / "widget-count" / "scripts" / "widgets_report.py").unlink()
    assert build_bins.plan(dept) == ([("remove", "widgets-report")], [])


def test_a_hand_written_file_in_bin_is_reported_never_touched(dept):
    (dept / "bin").mkdir()
    (dept / "bin" / "widgets-probe").write_text("#!/bin/sh\necho mine\n")
    (dept / "bin" / "notes.txt").write_text("hello")
    actions, problems = build_bins.plan(dept)
    assert ("write", "widgets-probe") not in actions
    assert any("widgets-probe was not written by build_bins.py" in p for p in problems)
    assert any("notes.txt runs no script" in p for p in problems)


def share_copy(dept_dir: Path, skill: str, script: str) -> None:
    """A marked copy of a shared skill in the department, as build_shared.py writes it."""
    scripts = dept_dir / "skills" / skill / "scripts"
    scripts.mkdir(parents=True)
    (scripts / script).write_text("print('shared')\n")
    (dept_dir / "skills" / skill / ".shared-copy").write_text(f"source: shared/skills/{skill}\n")


def test_a_shared_copy_keeps_one_unprefixed_name(dept):
    assert build_bins.command_name("accounting", Path("task_stack_apply.py"), shared=True) == "task-stack-apply"
    share_copy(dept, "stack-workstream", "task_stack_apply.py")
    actions, problems = build_bins.plan(dept)
    assert problems == []
    assert ("write", "task-stack-apply") in actions
    assert ("write", "widgets-task-stack-apply") not in actions
    want, _ = build_bins.wanted(dept)
    assert "skills/stack-workstream/scripts/task_stack_apply.py" in want["task-stack-apply"]


def test_the_same_copy_gets_the_same_wrapper_in_every_department(dept):
    other = dept.parent / "gadgets"
    for d in (dept, other):
        share_copy(d, "stack-workstream", "task_stack_apply.py")
    assert build_bins.wanted(dept)[0]["task-stack-apply"] == build_bins.wanted(other)[0]["task-stack-apply"]


def test_a_copy_command_that_clashes_with_the_departments_own_is_an_error(dept):
    share_copy(dept, "stack-workstream", "widgets_report.py")  # widgets-report, like the department's own
    _, problems = build_bins.plan(dept)
    assert any(p.startswith("widgets-report: both") and "shared copy" in p for p in problems)
    assert build_bins.main(["--check", "widgets"]) == 1
