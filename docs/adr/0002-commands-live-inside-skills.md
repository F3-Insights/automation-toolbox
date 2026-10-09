# 0002. Commands are plain scripts inside the skill that owns them

Status: accepted, 2026-10-06. Replaces decision 2's "and later `tools/`" and the second consequence of [0001](0001-departments-and-distribution.md).

## Context

The skills and agents call about 130 commands (`trial-balance`, `task-stack-apply`, `register`). Where they started, they were modules of one Python package that share a base class, a settings reader, a Portal client and a logger, and are installed as commands on PATH. Moving that package here would need either a shared library folder, which 0001 rules out, or an install step, which a reader of one skill should not need.

## Decision

1. **A command is one plain Python file in the `scripts/` folder of the skill that owns it:** `<department>/skills/<skill>/scripts/<command>.py`, with the command's hyphens written as underscores (`trial-balance` becomes `trial_balance.py`).
2. **Each script stands on its own.** It uses the standard library and `argparse`, and a third-party package only when the job needs one (`pyyaml`, `openpyxl`, `python-pptx`, `python-docx`, `pypdf`, `pillow`). A script that needs one declares it in an inline `# /// script` block at the top, so `uv run` or `pipx run` can install it.
3. **Scripts of one skill may share one helper file,** `scripts/_common.py`, which Python finds because it sits beside them. A script never imports from another skill.
4. **Code that two skills need is copied,** kept short, rather than shared.
5. **Other skills run a command by its owning skill's name:** `python3 ~/.claude/skills/<skill>/scripts/<command>.py`, the same by-name path CONTEXT.md gives for loading a skill. Agents grant exactly that in their `tools` line.
6. **Tests sit beside the code,** in `scripts/tests/`, with invented data only.
7. **Owner facts and connection details are settings,** read from `~/.config/f3i-toolbox/settings.toml` (or the file `F3I_TOOLBOX_SETTINGS` names). Secrets come only from environment variables and are never printed.

## Consequences

- Nothing is installed and nothing goes on PATH. A skill folder copied anywhere carries everything it runs.
- Some code exists in more than one skill. Each copy is small and owned by its skill; a fix to one copy is a deliberate edit to the others.
- The original package's base class, structured-output models and logger are not carried over. Scripts print plain text or JSON and exit non-zero on failure.
