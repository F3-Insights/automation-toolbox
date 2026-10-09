"""skills-extract: the pack script and the name check, on made-up sessions.

The fixtures describe a made-up company, Acme Components, and its made-up controller. Nothing
here comes from a real transcript.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[2]


def load(name: str):
    spec = importlib.util.spec_from_file_location(f"skills_extract_{name}", SKILL / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pack_script = load("session_pack")
check_script = load("name_check")
inventory_script = load("skill_inventory")


def write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def claude_session(folder: Path, sid: str, day: str, prompts, cwd="/work/acme-close", sdk=False, tools=()):
    rows = []
    for i, text in enumerate(prompts):
        rows.append({"type": "user", "isSidechain": False, "timestamp": f"{day}T10:0{i}:00Z", "cwd": cwd,
                     "sessionId": sid, "gitBranch": "main",
                     "promptSource": "sdk" if sdk else "typed", "entrypoint": "sdk-cli" if sdk else "cli",
                     "message": {"role": "user", "content": text}})
    blocks = [{"type": "tool_use", "name": n, "input": a} for n, a in tools]
    rows.append({"type": "assistant", "isSidechain": False, "timestamp": f"{day}T10:30:00Z", "cwd": cwd,
                 "message": {"role": "assistant", "content": blocks + [{"type": "text", "text": "done"}]}})
    # Noise that is not the person typing: a tool result, a harness notice, a meta line, a sidechain.
    rows.append({"type": "user", "timestamp": f"{day}T10:31:00Z", "cwd": cwd,
                 "message": {"role": "user", "content": [{"type": "tool_result", "content": "month-end ok"}]}})
    rows.append({"type": "user", "timestamp": f"{day}T10:32:00Z", "cwd": cwd, "promptSource": "system",
                 "message": {"role": "user", "content": "<task-notification> month-end accrual run"}})
    rows.append({"type": "user", "isSidechain": True, "timestamp": f"{day}T10:33:00Z", "cwd": cwd,
                 "message": {"role": "user", "content": "sub-agent brief about the month-end close"}})
    write_jsonl(folder / f"{sid}.jsonl", rows)


@pytest.fixture
def corpus(tmp_path: Path) -> dict:
    claude = tmp_path / "claude" / "projects"
    proj = claude / "-work-acme-close"
    claude_session(proj, "c1", "2026-08-01", ["Run the month-end close for July", "post the accrual entries"],
                   tools=[("Bash", {"command": "cd /work/acme-close && python3 -m pytest -q | tail -3"}),
                          ("Bash", {"command": "python3 - <<'EOF'\nimport json\nfor x in []: pass\nEOF"}),
                          ("Edit", {"file_path": "/work/acme-close/reports/july.md"}),
                          ("Skill", {"skill": "finance-report-tieout"}),
                          ("Agent", {"subagent_type": "finance-reviewer"})])
    claude_session(proj, "c2", "2026-09-02", ["Run the month-end close for August"],
                   tools=[("Bash", {"command": "timeout 60 .venv/bin/python scripts/fetch_gl.py --period 2026-08"})])
    claude_session(proj, "c3", "2026-09-03", ["Fix the enclosed CSS in the website header",
                                              "<bash-stdout>month-end accrual output</bash-stdout>"])
    claude_session(proj, "c4", "2026-09-04", ["# Nightly: Month-end checks\nYou are running headless."], sdk=True)
    claude_session(proj, "c5", "2026-09-05", ["# Nightly: Month-end checks\nYou are running headless."], sdk=True)
    claude_session(proj / "c1" / "subagents", "agent-x", "2026-08-01", ["sub-agent month-end work"])

    codex = tmp_path / "codex" / "sessions" / "2026" / "09"
    write_jsonl(codex / "rollout-a.jsonl", [
        {"timestamp": "2026-09-10T09:00:00Z", "type": "session_meta",
         "payload": {"id": "x1", "cwd": "/work/acme-close", "originator": "codex-tui"}},
        {"timestamp": "2026-09-10T09:00:01Z", "type": "event_msg",
         "payload": {"type": "user_message", "message": "<environment_context>cwd</environment_context>"}},
        {"timestamp": "2026-09-10T09:00:02Z", "type": "event_msg",
         "payload": {"type": "user_message", "message": "Reconcile the bank accounts for August"}},
        {"timestamp": "2026-09-10T09:01:00Z", "type": "response_item",
         "payload": {"type": "function_call", "name": "exec_command",
                     "arguments": json.dumps({"cmd": "git log --oneline -5", "workdir": "/work/acme-close"})}},
        {"timestamp": "2026-09-10T09:02:00Z", "type": "response_item",
         "payload": {"type": "custom_tool_call", "name": "exec",
                     "input": 'await tools.exec_command({cmd:"rg reconcil docs"});\n'
                              "*** Begin Patch\n*** Update File: recs/bank.md\n*** End Patch"}},
    ])

    write_jsonl(codex / "rollout-old.jsonl", [
        {"timestamp": "2026-09-11T09:00:00Z", "type": "session_meta", "payload": {"id": "x3", "cwd": "/work/acme-close"}},
        {"timestamp": "2026-09-11T09:00:01Z", "type": "response_item",
         "payload": {"type": "message", "role": "user",
                     "content": [{"type": "input_text", "text": "Roll the forecast forward a month"}]}},
    ])
    write_jsonl(codex / "rollout-sub.jsonl", [
        {"timestamp": "2026-09-10T09:05:00Z", "type": "session_meta",
         "payload": {"id": "x2", "parent_thread_id": "x1", "cwd": "/work/acme-close",
                     "source": {"subagent": {"other": "reviewer"}}}},
        {"timestamp": "2026-09-10T09:05:01Z", "type": "event_msg",
         "payload": {"type": "user_message", "message": "Assess this month-end reconciliation action"}},
    ])

    export = tmp_path / "export" / "conversations.json"
    export.parent.mkdir()
    export.write_text(json.dumps([{
        "uuid": "w1", "name": "Variance commentary", "created_at": "2026-09-12T08:00:00Z",
        "chat_messages": [
            {"sender": "human", "text": "Draft the variance commentary for the board", "created_at": "2026-09-12T08:00:00Z"},
            {"sender": "assistant", "text": "Here it is", "created_at": "2026-09-12T08:01:00Z"}]}]))

    return {"tmp": tmp_path, "claude": claude, "codex": tmp_path / "codex" / "sessions", "export": export,
            "out": tmp_path / "work" / "pack.json"}


def run_pack(corpus: dict, *extra: str) -> dict:
    argv = ["--claude-dir", str(corpus["claude"]), "--codex-dir", str(corpus["codex"]),
            "--out", str(corpus["out"]), *extra]
    assert pack_script.main(argv) == 0
    return json.loads(corpus["out"].read_text())


def test_the_pack_keeps_typed_prompts_and_groups_automated_runs(corpus, capsys):
    old = run_pack(corpus, "--terms", "forecast")
    assert [(r["session"], r["prompts"]) for r in old["sessions"]] == [("x3", ["Roll the forecast forward a month"])]
    capsys.readouterr()
    pack = run_pack(corpus, "--terms", "month-end,reconcil,accrual,variance",
                    "--claude-export", str(corpus["export"]))
    first = capsys.readouterr().out.splitlines()[0]
    assert first.startswith("WORK: 4 sessions")
    ids = {s["session"] for s in pack["sessions"]}
    assert ids == {"c1", "c2", "x1", "w1"}  # not the CSS session, not the sub-agent, not the runs
    c1 = next(s for s in pack["sessions"] if s["session"] == "c1")
    assert c1["prompts"] == ["Run the month-end close for July", "post the accrual entries"]
    assert c1["origin"] == "interactive" and c1["branch"] == "main"
    assert c1["programs"] == {"python3 -m pytest": 1, "tail": 1, "python3": 1}
    assert c1["files_written"] == ["reports/july.md"]
    assert c1["skills"] == {"finance-report-tieout": 1} and c1["agents"] == {"finance-reviewer": 1}
    assert "accrual" in c1["terms_hit"] and "month-end" in c1["terms_hit"]
    c2 = next(s for s in pack["sessions"] if s["session"] == "c2")
    assert c2["programs"] == {"python fetch_gl.py": 1}
    x1 = next(s for s in pack["sessions"] if s["session"] == "x1")
    assert x1["source"] == "codex" and x1["prompts"] == ["Reconcile the bank accounts for August"]
    assert x1["programs"] == {"git log": 1, "rg": 1} and x1["files_written"] == ["recs/bank.md"]
    w1 = next(s for s in pack["sessions"] if s["session"] == "w1")
    assert w1["source"] == "claude-chat" and w1["title"] == "Variance commentary"
    assert pack["automated_matched"] == 2
    assert pack["automated_runs"][0]["runs"] == 2
    assert pack["automated_runs"][0]["signature"].startswith("# Nightly: Month-end checks")
    assert pack["summary"]["by_month"] == {"2026-08": 1, "2026-09": 3}
    assert pack["summary"]["distinct_days"] == 4
    assert {"session": "c1", "source": "claude-code", "date": "2026-08-01", "origin": "interactive",
            "skill": "finance-report-tieout", "how": "tool", "count": 1} in pack["skill_events"]
    assert pack["cwds"] == ["/work/acme-close"]
    assert "acme-close" in pack["private_terms"]


def test_a_term_matches_at_the_start_of_a_word(corpus):
    assert pack_script.hit("reconcil", "reconciliation of the bank")
    assert pack_script.hit("close", "the month-end close") and pack_script.hit("close", "/work/acme-close")
    assert not pack_script.hit("close", "fix the enclosed css")
    pack = run_pack(corpus, "--terms", "enclos")
    assert [s["session"] for s in pack["sessions"]] == ["c3"]


def test_the_window_and_the_project_filter(corpus):
    pack = run_pack(corpus, "--terms", "month-end", "--since", "2026-09-01", "--until", "2026-09-02")
    assert [s["session"] for s in pack["sessions"]] == ["c2"]
    pack = run_pack(corpus, "--project", "acme-close", "--since", "2026-09-03")
    assert {s["session"] for s in pack["sessions"]} == {"c3", "x1", "x3"}


def test_nothing_matched_says_nothing(corpus, capsys):
    run_pack(corpus, "--terms", "payroll")
    assert capsys.readouterr().out.splitlines()[0] == "NOTHING"


def test_the_pack_is_refused_inside_a_git_tree(corpus, capsys):
    repo = corpus["tmp"] / "repo"
    (repo / ".git").mkdir(parents=True)
    argv = ["--claude-dir", str(corpus["claude"]), "--terms", "close", "--out", str(repo / "pack.json")]
    assert pack_script.main(argv) == 2
    assert "git working tree" in capsys.readouterr().err
    assert not (repo / "pack.json").exists()


def test_no_terms_and_no_project_is_refused(corpus):
    assert pack_script.main(["--out", str(corpus["out"])]) == 2


def test_the_repo_section_reads_the_git_log(corpus):
    repo = corpus["tmp"] / "acme-repo"
    repo.mkdir()
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
           "GIT_AUTHOR_DATE": "2026-09-15T12:00:00Z", "GIT_COMMITTER_DATE": "2026-09-15T12:00:00Z"}
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=env)
    (repo / "README.md").write_text("# Close\n")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "Add the close checklist"], check=True, env=env)
    pack = run_pack(corpus, "--terms", "month-end", "--repo", str(repo))
    assert pack["repo"]["commits"] == 1
    assert pack["repo"]["recent"] == [{"date": "2026-09-15", "subject": "Add the close checklist"}]
    assert pack["repo"]["docs"] == ["README.md"]


# --- the name check -----------------------------------------------------------------------


def draft(folder: Path, body: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(body)
    return folder


def test_a_generic_draft_is_clean(tmp_path, capsys):
    folder = draft(tmp_path / "finance-close-run", "---\nname: finance-close-run\n---\n\nAsk the controller. "
                   "Write to `~/notes`. Mail goes to someone@example.com. Period 2026-08.\n")
    names = tmp_path / "owner.md"
    names.write_text("# Owner\n\nRuns a small practice.\n\n## Private names\n\n- Acme Components\n- Dana Reyes\n")
    assert check_script.main([str(folder), "--names", str(names)]) == 0
    assert capsys.readouterr().out.startswith("CLEAN")


def test_names_paths_and_numbers_are_flagged(tmp_path, capsys):
    folder = draft(tmp_path / "d", "Send it to dana_reyes for ACME components.\n"
                   "Open /ho" "me/dreyes/books/gl.csv and post to account 400012345.\n"
                   "Copy dana@acme-components.test on it. Use the northwind folder.\n")
    names = tmp_path / "owner.md"
    names.write_text("# Owner\n\n## Private names\n\n- Acme Components\n- Dana Reyes\n\n## Other\n\n- not a name\n")
    pack = tmp_path / "pack.json"
    pack.write_text(json.dumps({"private_terms": ["Northwind"]}))
    assert check_script.main([str(folder), "--names", str(names), "--pack", str(pack)]) == 3
    out = capsys.readouterr().out
    assert out.startswith("HITS: ")
    for needed in (":1: name", ":2: home path", ":2: long number", ":3: email", ":3: name"):
        assert needed in out, needed
    # What matched is never printed: not the name, the path, the number or the address.
    for secret in ("dana", "acme", "dreyes", "400012345", "northwind"):
        assert secret not in out.lower(), secret


def test_the_denylist_files_the_toolbox_check_reads_are_checked(tmp_path, monkeypatch, capsys):
    deny = tmp_path / "denylist.txt"
    extra = tmp_path / "more.txt"
    extra.write_text("Fabrikam\n")
    deny.write_text("# private names\n=Priya\n@" + str(extra) + "\n")
    monkeypatch.setenv("F3I_TOOLBOX_DENYLIST", str(deny))
    monkeypatch.setattr(check_script, "DEFAULT_DENYLIST", tmp_path / "absent.txt")
    folder = draft(tmp_path / "d", "Ask Priya, then file it for fabrikam. A priya-style note is fine.\n")
    assert check_script.main([str(folder)]) == 3
    out = capsys.readouterr().out
    assert out.startswith("HITS: 2") and out.count(":1: denylist") == 2
    assert "priya" not in out.lower() and "fabrikam" not in out.lower()
    assert check_script.main([str(folder), "--no-denylist"]) == 0


def test_a_private_name_in_a_file_path_is_flagged_and_the_path_withheld(tmp_path, monkeypatch, capsys):
    deny = tmp_path / "denylist.txt"
    deny.write_text("Fabrikam\n@" + str(deny) + "\n")  # a list that includes itself is read once
    monkeypatch.setenv("F3I_TOOLBOX_DENYLIST", str(deny))
    monkeypatch.setattr(check_script, "DEFAULT_DENYLIST", tmp_path / "absent.txt")
    folder = tmp_path / "drafts"
    draft(folder / "fabrikam-close", "A generic close.\n")
    assert check_script.main([str(folder)]) == 3
    out = capsys.readouterr().out
    assert "(path withheld): denylist in path" in out and "fabrikam" not in out.lower()


def test_the_session_folders_are_a_setting(tmp_path, monkeypatch):
    settings = tmp_path / "settings.toml"
    settings.write_text('[skills-extract]\nclaude_session_dirs = ["~/elsewhere/claude"]\n')
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(settings))
    assert pack_script.session_dirs("claude_session_dirs", "~/.claude/projects") == ["~/elsewhere/claude"]
    assert pack_script.session_dirs("codex_session_dirs", "~/.codex/sessions") == ["~/.codex/sessions"]


def test_a_plain_list_is_read_as_names(tmp_path):
    names = tmp_path / "names.txt"
    names.write_text("# private\nAcme Components\nDana Reyes\n")
    assert check_script.names_from_file(names) == ["Acme Components", "Dana Reyes"]


def test_this_skill_carries_no_paths_or_addresses():
    """The skill's own files pass its own pattern check (names are checked by the owner's list)."""
    hits = []
    for f in check_script.files_under([str(SKILL)]):
        if f.name == "name_check.py" or "tests" in f.parts:
            continue  # it spells out the patterns it looks for; the tests plant hits on purpose
        hits += [(f.name, h) for h in check_script.scan_text(f.read_text(), [])]
    assert hits == []


def test_programs_ignore_script_bodies():
    """A heredoc or a quoted inline script is the program's input, not commands."""
    assert pack_script.programs("python3 -c \"\nimport json\nfor x in y: print(x)\n\" | head") == ["python3", "head"]
    assert pack_script.programs("node -e 'const a = 1;\nconsole.log(a)' && npm test") == ["node", "npm test"]
    assert pack_script.programs("cat > f.md <<'EOF'\nfor the close\nEOF") == ["cat"]
    assert pack_script.programs("FOO=1 timeout 60 git -C repo status") == ["git"]


# --- the skill inventory ------------------------------------------------------------------


def skill(folder: Path, name: str, description: str, body: str = "", scripts=()) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n")
    for script in scripts:
        (folder / "scripts").mkdir(exist_ok=True)
        (folder / "scripts" / script).write_text("print('ok')\n")
    return folder


@pytest.fixture
def machine(tmp_path: Path) -> dict:
    """A made-up home folder with skills in all four kinds of place, and Acme Components sessions."""
    home = tmp_path / "home"
    toolbox = home / "toolbox" / "skills"
    skill(toolbox / "finance-close", "finance-close", "Run the month-end close.",
          "## Steps\n\n1. [script] Run `~/books-engine/run.py` for the period.\n", scripts=["fetch.py"])
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "skills").symlink_to(toolbox)
    (home / ".codex" / "skills" / ".system").mkdir(parents=True)
    (home / ".codex" / "skills" / "finance-close").symlink_to(toolbox / "finance-close")
    skill(home / ".codex" / "skills" / ".system" / "skill-maker", "skill-maker", "Make a skill.")

    plugins = home / ".claude" / "plugins"
    for sync in ("sync-1", "sync-2"):  # the same plugin synced twice, word for word
        skill(plugins / "synced" / sync / "finance" / "skills" / "variance-analysis", "variance-analysis",
              ">\n  Explain variances\n  against budget.")
    skill(plugins / "cache" / "market" / "finance" / "1.0.0" / "skills" / "journal-entry", "journal-entry", "Old.")
    skill(plugins / "cache" / "market" / "finance" / "1.2.0" / "skills" / "journal-entry", "journal-entry", "New.")
    skill(plugins / ".trash" / "123" / "finance" / "skills" / "sox-testing", "sox-testing", "Deleted.")
    skill(home / ".codex" / "plugins" / "cache" / "market" / "pages" / "0.1.0" / "skills" / "write-page",
          "write-page", "Write a page.")

    repo = home / "work" / "acme-forecast"
    (repo / ".git").mkdir(parents=True)
    skill(repo / ".claude" / "skills" / "forecast", "forecast", "Roll the Acme Components forecast.",
          "Run `.venv/bin/forecast --period P status`, then read `rules.md` and `docs/forecast.md`.\n")
    (repo / ".claude" / "skills" / "forecast" / "rules.md").write_text("Rules.\n")
    elsewhere = home / "work" / "acme-board"  # a repository no session worked in
    skill(elsewhere / ".claude" / "skills" / "board-pack", "board-pack", "Build the board pack.")

    claude = tmp_path / "claude" / "projects" / "-work-acme-forecast"
    cwd = str(repo)
    claude_session(claude, "s1", "2026-08-03",
                   ["<command-name>/forecast</command-name>", "Refresh the Acme forecast with July actuals"], cwd=cwd,
                   tools=[("Skill", {"skill": "finance-close"}), ("Skill", {"skill": "finance:variance-analysis"}),
                          ("Read", {"file_path": f"{repo}/.claude/skills/forecast/SKILL.md"})])
    claude_session(claude, "s2", "2026-09-02", ["Close August and update the forecast"], cwd=cwd,
                   tools=[("Bash", {"command": f"cat {home}/.codex/skills/finance-close/SKILL.md | head"}),
                          ("Edit", {"file_path": f"{toolbox}/finance-close/rules.md"}),
                          ("Skill", {"skill": "old-close-runner"})])
    claude_session(claude, "s3", "2026-09-04", ["# Nightly forecast check"], cwd=cwd, sdk=True,
                   tools=[("Skill", {"skill": "finance-close"})])
    codex = tmp_path / "codex" / "sessions" / "2026" / "09"
    write_jsonl(codex / "rollout-f.jsonl", [
        {"timestamp": "2026-09-05T09:00:00Z", "type": "session_meta", "payload": {"id": "x9", "cwd": cwd}},
        {"timestamp": "2026-09-05T09:00:01Z", "type": "event_msg",
         "payload": {"type": "user_message", "message": "Use $forecast to roll the Acme forecast; budget is $40k"}},
        {"timestamp": "2026-09-05T09:01:00Z", "type": "response_item",
         "payload": {"type": "function_call", "name": "exec_command",
                     "arguments": json.dumps({"cmd": "sed -n 1,80p .claude/skills/forecast/SKILL.md"})}},
    ])
    work = tmp_path / "work"
    argv = ["--claude-dir", str(tmp_path / "claude" / "projects"), "--codex-dir", str(tmp_path / "codex" / "sessions"),
            "--terms", "forecast", "--out", str(work / "pack.json")]
    assert pack_script.main(argv) == 0
    return {"home": home, "repo": repo, "elsewhere": elsewhere, "pack": work / "pack.json",
            "out": work / "skills.json", "toolbox": toolbox}


def run_inventory(machine: dict, *extra: str) -> dict:
    argv = ["--pack", str(machine["pack"]), "--out", str(machine["out"]), "--home", str(machine["home"]), *extra]
    assert inventory_script.main(argv) == 0
    data = json.loads(machine["out"].read_text())
    return {"data": data, "by": {s["invoke"]: s for s in data["skills"]}}


def test_the_inventory_finds_skills_in_every_kind_of_place(machine, capsys):
    result = run_inventory(machine)
    by = result["by"]
    assert capsys.readouterr().out.startswith("SKILLS: 6 skills")
    assert set(by) == {"finance-close", "skill-maker", "finance:variance-analysis", "finance:journal-entry",
                       "pages:write-page", "forecast"}  # no trash, no unworked repository
    close = by["finance-close"]
    assert close["kinds"] == ["user", "codex"] and len(close["locations"]) == 2  # one skill, two ways in
    assert close["has_steps"] and close["scripts"] == ["fetch.py"]
    assert close["points_outside"] == ["~/books-engine/run.py"]
    assert by["skill-maker"]["kinds"] == ["codex"]
    variance = by["finance:variance-analysis"]
    assert variance["kinds"] == ["plugin"] and len(variance["locations"]) == 2
    assert variance["description"] == "Explain variances against budget."
    assert [Path(p).parent.parent.name for p in by["finance:journal-entry"]["locations"]] == ["1.2.0"]
    assert by["finance:journal-entry"]["description"] == "New."
    assert by["forecast"]["kinds"] == ["project"]
    assert by["forecast"]["points_outside"] == [".venv/bin/forecast", "docs/forecast.md"]  # bound to its repo
    assert not any("sox" in s["invoke"] for s in result["data"]["skills"])


def test_the_inventory_counts_loads_from_the_sessions(machine):
    by = run_inventory(machine)["by"]
    close = by["finance-close"]["use"]
    assert close["sessions"] == 3 and close["typed_sessions"] == 2 and close["automated_sessions"] == 1
    assert close["by_how"] == {"tool": 2, "read": 1}  # the read came through the Codex symlink
    assert close["first"] == "2026-08-03" and close["last"] == "2026-09-04"
    assert close["shared_name_sessions"] == 0
    assert close["edit_sessions"] == 1 and close["edit_dates"] == ["2026-09-02"]  # maintenance, not use
    forecast = by["forecast"]["use"]
    assert forecast["sessions"] == 2 and forecast["by_how"] == {"slash": 1, "read": 2, "mention": 1}
    assert forecast["dates"] == ["2026-08-03", "2026-09-05"]
    assert by["finance:variance-analysis"]["use"]["sessions"] == 1
    assert by["pages:write-page"]["use"]["sessions"] == 0
    unmatched = run_inventory(machine)["data"]["unmatched"]
    assert [(u["skill"], u["loads"], u["dates"]) for u in unmatched] == [("old-close-runner", 1, ["2026-09-02"])]


def test_a_named_folder_adds_its_project_skills(machine):
    by = run_inventory(machine, "--project-dir", str(machine["elsewhere"]))["by"]
    assert by["board-pack"]["kinds"] == ["project"] and by["board-pack"]["use"]["sessions"] == 0
    by = run_inventory(machine, "--projects-root", str(machine["home"] / "work"))["by"]
    assert "board-pack" in by and by["forecast"]["use"]["sessions"] == 2


def test_a_skill_read_from_another_repository_brings_that_repository_in(machine):
    other = machine["home"] / "work" / "acme-runner"
    skill(other / ".claude" / "skills" / "close-engine", "close-engine", "Run the close engine.")
    claude = machine["pack"].parent.parent / "claude" / "projects" / "-work-acme-forecast"
    claude_session(claude, "s4", "2026-09-20", ["Run the forecast close engine"], cwd=str(machine["repo"]),
                   tools=[("Read", {"file_path": f"{other}/.claude/skills/close-engine/SKILL.md"}),
                          ("Bash", {"command": "for f in skills/*/SKILL.md; do head -3 $f; done; cat $d/SKILL.md"})])
    argv = ["--claude-dir", str(machine["pack"].parent.parent / "claude" / "projects"), "--codex-dir",
            str(machine["pack"].parent.parent / "codex" / "sessions"), "--terms", "forecast",
            "--out", str(machine["pack"])]
    assert pack_script.main(argv) == 0
    result = run_inventory(machine)
    assert result["by"]["close-engine"]["use"]["sessions"] == 1
    assert all("*" not in u["skill"] and "$" not in u["skill"] for u in result["data"]["unmatched"])


def test_one_name_with_different_text_stays_two_skills(machine):
    skill(machine["repo"] / ".claude" / "skills" / "finance-close", "finance-close", "A local fork of the close.")
    skills = run_inventory(machine)["data"]["skills"]
    forks = [s for s in skills if s["invoke"] == "finance-close"]
    assert sorted(s["kinds"][0] for s in forks) == ["project", "user"]
    user = next(s for s in forks if s["kinds"][0] == "user")["use"]
    fork = next(s for s in forks if s["kinds"][0] == "project")["use"]
    # The Skill tool calls name both; the read came by the user copy's own path.
    assert user["sessions"] == 3 and user["shared_name_sessions"] == 2
    assert fork["sessions"] == 2 and fork["shared_name_sessions"] == 2


def test_the_inventory_refuses_a_git_tree_and_a_missing_pack(machine, tmp_path, capsys):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    assert inventory_script.main(["--pack", str(machine["pack"]), "--out", str(repo / "skills.json")]) == 2
    assert inventory_script.main(["--pack", str(tmp_path / "none.json"), "--out", str(machine["out"])]) == 2
    assert "git working tree" in capsys.readouterr().err
