"""orchestrator_scaffold.py against the worked example (Acme Components' widget review).

The example spec in the skill's references/ is generated into a made-up toolbox in a temporary
folder. The tests prove the files land in the department layout, every lint passes on them, the
generated check's own tests pass, nothing private reaches a toolbox file, and each lint fires on
the mistake it exists for.
"""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import orchestrator_scaffold as sc  # noqa: E402

EXAMPLE = HERE.parent.parent / "references" / "example-spec.yaml"
NAME = "acme-widget-review-orchestrator"
FOLDER = "/srv/acme/Widget-Review"
FILES = [
    "projects/agents/acme-widget-review-orchestrator.md",
    "projects/agents/widget-review-inspector.md",
    "projects/agents/widget-review-reviewer.md",
    "projects/agents/widget-review-keeper.md",
    "projects/skills/widget-review-workstream/SKILL.md",
    "projects/skills/widget-review-workstream/scripts/widget_review_check.py",
    "projects/skills/widget-review-workstream/scripts/widget_review_pull.py",
    "projects/skills/widget-review-workstream/scripts/tests/test_widget_review_check.py",
]


ORCHESTRATOR_SECTIONS = ["Goal", "Inputs", "Context", "Approach", "Team", "Boundaries", "Done when", "Output"]
SUB_AGENT_SECTIONS = ["Goal", "Inputs", "Context", "Approach", "Boundaries", "Done when", "Output"]
STAGES = ["A. Gather", "B. Plan & clarify", "C. Build", "D. Test & review", "E. Deliver"]


def headings(text, level):
    return [line[len(level):].strip() for line in text.splitlines() if line.startswith(level)]


def skill(root, dept, name):
    d = root / dept / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: The {name} skill.\n---\n")


@pytest.fixture
def world(tmp_path, monkeypatch):
    root = tmp_path / "toolbox"
    (root / "projects" / "agents").mkdir(parents=True)
    skill(root, "software", "orchestration-workstream")
    skill(root, "productivity", "comms-confirm")
    deny = tmp_path / "denylist.txt"
    deny.write_text("# made-up names\nGlobex\nInitech Holdings\n")
    monkeypatch.setenv("F3I_TOOLBOX_DENYLIST", str(deny))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return {"root": root, "spec": yaml.safe_load(EXAMPLE.read_text()), "tmp": tmp_path}


def run(*args):
    return subprocess.run([sys.executable, str(HERE.parent / "orchestrator_scaffold.py"), *args],
                          capture_output=True, text=True)


def generate(world, spec=None, *extra):
    path = world["tmp"] / "spec.yaml"
    path.write_text(yaml.safe_dump(spec if spec is not None else world["spec"], sort_keys=False))
    return run("generate", str(path), "--root", str(world["root"]), *extra)


def mutate(world, change, *extra):
    spec = copy.deepcopy(world["spec"])
    change(spec)
    return generate(world, spec, *extra)


def test_generate_writes_every_file_and_lints_clean(world):
    res = generate(world)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "error:" not in res.stdout
    for rel in FILES:
        assert (world["root"] / rel).is_file(), rel
    res = run("lint", NAME, "--root", str(world["root"]))
    assert res.returncode == 0, res.stdout
    assert res.stdout.startswith(f"OK: {NAME}: 0 error(s)")
    assert "widget-review-inspector" in res.stdout


def test_the_orchestrator_follows_the_design(world):
    assert generate(world).returncode == 0
    text = (world["root"] / FILES[0]).read_text()
    assert headings(text, "## ") == ORCHESTRATOR_SECTIONS
    assert headings(text, "### ") == STAGES
    for stage in text.split("### ")[1:]:
        assert "- **Goal.**" in stage and "- **Who.**" in stage and "- **Move on when**" in stage
    assert sc.split_frontmatter(text)[1].split("\n")[2].startswith("You own widget review")
    assert "never the builder's reasoning" in text and "after two failed rounds" in text
    assert "Nothing is sent or posted without a person" in text
    check = "~/.claude/skills/widget-review-workstream/scripts/widget_review_check.py"
    assert f"`python3 {check} REVIEW_FOLDER --period PERIOD --format json`" in text
    assert f'"Bash(python3 {check}:*)"' in text
    assert "`WIDGET-REVIEW-RULES.md` in the Review folder" in text
    assert "**Dry run** (optional)" in text and sc.MD_MARKER in text
    assert not sc.FOLLOW_PHRASE.search(text)
    meta, _ = sc.split_frontmatter(text)
    assert meta["name"] == NAME and len(meta["description"]) <= sc.DESCRIPTION_LIMIT
    assert "Not for one lot's verdict by hand" in meta["description"]
    worker = (world["root"] / FILES[1]).read_text()
    assert "skills: [orchestration-workstream, widget-review-workstream]" in worker
    assert "extends `orchestration-workstream`" in (world["root"] / FILES[4]).read_text()


@pytest.mark.parametrize("rel", FILES[1:4])
def test_every_sub_agent_follows_the_template(world, rel):
    assert generate(world).returncode == 0
    text = (world["root"] / rel).read_text()
    meta, body = sc.split_frontmatter(text)
    assert set(meta) >= {"name", "description", "tools", "model"}
    assert "Not for a request on its own; start acme-widget-review-orchestrator." in meta["description"]
    assert headings(text, "## ") == SUB_AGENT_SECTIONS
    assert headings(text, "### ") == []
    assert body.split("\n")[2].startswith("You own ") and "You are an expert" not in body


def test_the_templates_are_the_files_the_scaffold_fills():
    for name, sections in (("orchestrator.md", ORCHESTRATOR_SECTIONS), ("sub-agent.md", SUB_AGENT_SECTIONS)):
        text = (sc.TEMPLATES / name).read_text()
        assert headings(text, "## ") == sections
    assert headings((sc.TEMPLATES / "orchestrator.md").read_text(), "### ") == STAGES
    with pytest.raises(sc.SpecError, match="no value for"):
        sc.render("sub-agent.md", {"name": "x"})


def test_a_spec_without_not_for_warns(world):
    res = mutate(world, lambda s: s.pop("not_for"))
    assert res.returncode == 0 and "warning: [not-for] spec" in res.stdout


def test_the_generated_check_test_passes_and_the_stub_refuses(world):
    assert generate(world).returncode == 0
    tests = world["root"] / FILES[-1]
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(tests)],
                          capture_output=True, text=True, timeout=120, cwd=world["tmp"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "7 passed" in proc.stdout
    assert '"--period=",' in tests.read_text() and '"--as-of=",' in tests.read_text()


def test_the_launcher_ships_disabled_and_stays_out_of_the_toolbox(world):
    launcher = world["tmp"] / "private" / "widget-review.yaml"
    res = generate(world, None, "--launcher", str(launcher), "--set", f"review_folder={FOLDER}")
    assert res.returncode == 0, res.stdout + res.stderr
    side = yaml.safe_load(launcher.read_text())
    script = "~/.claude/skills/widget-review-workstream/scripts/widget_review_check.py"
    assert side["agent"] == NAME and side["enabled"] is False and side["schedule"] == "30 7 * * 1-5"
    assert side["precheck"] == ["python3", script, FOLDER, "--precheck"]
    assert side["prepare"][0]["argv"][2:] == ["{review_folder}", "--period={period}"]
    assert side["inputs"] == {"review_folder": FOLDER}
    assert f"Write(/{FOLDER}/**)" in side["allowed-tools"]
    assert side["form"]["params"] == {"period": "", "instructions": "", "dry_run": False}
    for rel in FILES:
        assert FOLDER not in (world["root"] / rel).read_text(), rel
    res = run("lint", NAME, "--root", str(world["root"]), "--launcher", str(launcher), "--format", "json")
    assert json.loads(res.stdout)["ok"] is True


def test_the_launcher_needs_every_fixed_value(world):
    res = generate(world, None, "--launcher", str(world["tmp"] / "l.yaml"))
    assert res.returncode == 2 and "--set review_folder" in res.stderr


def test_dry_run_prints_every_file_and_writes_nothing(world):
    res = generate(world, None, "--dry-run")
    assert res.returncode == 0, res.stdout
    for rel in FILES:
        assert str(world["root"] / rel) in res.stdout
        assert not (world["root"] / rel).exists()
    assert "OK: dry run; nothing written" in res.stdout
    assert "<review_folder>" in res.stdout   # the launcher, printed, with the folder left to fill
    assert "      | ## Goal" in generate(world, None, "--dry-run", "--show").stdout


def test_an_existing_file_is_refused_and_update_needs_the_marker(world):
    assert generate(world).returncode == 0
    res = generate(world)
    assert res.returncode == 1 and f"refused: {world['root'] / FILES[0]} exists" in res.stdout
    assert generate(world, None, "--update").returncode == 0
    path = world["root"] / FILES[0]
    hand = path.read_text().replace(sc.MD_MARKER + "\n", "") + "\nWritten by hand.\n"
    path.write_text(hand)
    res = generate(world, None, "--update")
    assert res.returncode == 1 and "carries no scaffold marker" in res.stdout
    assert path.read_text() == hand


def test_a_command_another_skill_holds_is_refused(world):
    other = world["root"] / "projects" / "skills" / "elsewhere" / "scripts"
    other.mkdir(parents=True)
    (other / "widget_review_check.py").write_text("")
    res = generate(world)
    assert res.returncode == 1 and "widget-review-check already exists" in res.stdout


LINT_CASES = {
    "description": lambda s: s["workers"][0].update(description="Inspects lots. " * 60),
    "follow-phrase": lambda s: s.update(goal="Follow the comms-confirm skill and review every lot."),
    "interpreter": lambda s: s["workers"][0]["tools"].append("Bash(python3:*)"),
    "reserved": lambda s: s["inputs"].append({"name": "mode", "label": "Mode"}),
    "names": lambda s: s.update(purpose="Review the widget returns Globex sends each period."),
    "home-path": lambda s: s.update(standard="The rules are in " + "/ho" + "me/someone/rules.md."),
    "skills": lambda s: s["workers"][0]["skills"].append("no-such-skill"),
    "commands": lambda s: s["workers"][0]["tools"].append("no-such-command"),
    "precheck": lambda s: s["done"].update(scope="period", options=[]),
}


@pytest.mark.parametrize("lint_name", sorted(LINT_CASES))
def test_each_lint_fires_and_nothing_is_written(world, lint_name):
    res = mutate(world, LINT_CASES[lint_name])
    assert res.returncode == 1, res.stdout + res.stderr
    assert f"error: [{lint_name}]" in res.stdout, res.stdout
    assert "nothing written" in res.stdout
    assert not (world["root"] / FILES[0]).exists()


def test_a_missing_prepare_command_and_skill_are_named(world):
    res = mutate(world, lambda s: s.update(prepare=[["widget-review-fetch", "{review_folder}"]]))
    assert res.returncode == 1 and "'widget-review-fetch' is no script" in res.stdout
    res = mutate(world, lambda s: s["skills"]["load"].append("no-such-skill"))
    assert res.returncode == 1 and "'no-such-skill' is no skill" in res.stdout


@pytest.mark.parametrize("rule,flagged", [
    ("Bash(python3:*)", True), ("Bash(python3 -m:*)", True), ("Bash(uv run:*)", True), ("Bash(python3.12:*)", True),
    ("Bash(python3 ~/.claude/skills/comms-confirm/scripts/confirm.py:*)", False), ("Read", False),
])
def test_the_interpreter_rule(rule, flagged):
    assert bool(sc.INTERPRETER_RULE.match(rule)) is flagged


def test_a_bad_spec_is_exit_2(world):
    res = mutate(world, lambda s: s.pop("name"))
    assert res.returncode == 2 and "`name` is required" in res.stderr
    res = mutate(world, lambda s: s.update(name="widget-review"))
    assert res.returncode == 2 and "-orchestrator" in res.stderr
    bad = world["tmp"] / "flow.yaml"
    bad.write_text(EXAMPLE.read_text().replace(
        "    - name: lots\n      text: Every returned lot of the period has a verdict, reviewed and recorded.",
        "    - {name: lots, text: Every returned lot has a verdict, reviewed and recorded.}"))
    res = run("generate", str(bad), "--root", str(world["root"]))
    assert res.returncode == 2 and "write the test as a block" in res.stderr


def test_lint_an_unknown_orchestrator_is_exit_2(world):
    res = run("lint", "acme-nothing-orchestrator", "--root", str(world["root"]))
    assert res.returncode == 2 and "no agent acme-nothing-orchestrator.md" in res.stderr
