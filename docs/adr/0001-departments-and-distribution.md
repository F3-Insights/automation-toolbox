# 0001. Departments, one home per piece, and clone-and-link distribution

Status: accepted, 2026-10-06. Decision 2's `tools/` folder and the second consequence are replaced by [0002](0002-commands-live-inside-skills.md).

## Context

These agents and skills grew up inside F3 Insights' own working setup, next to client and owner material that is never published. The general-purpose pieces are worth sharing on their own. They must stay usable by an agent runtime that reads agents from one folder and skills from one folder, refers to agents by name, and passes agent text to Claude itself.

## Decision

1. **A new repository with no inherited history.** Pieces are copied in one at a time and audited for privacy, simplicity and readability on the way in.
2. **Department folders at the root,** each holding `agents/` and `skills/` (and later `tools/`). Departments are business functions a reader recognizes.
3. **No shared or common folder.** A piece used by several departments lives in the one it fits best, and the others refer to it by name. A reference document used by several skills becomes a small reference skill.
4. **Names are unique across the whole repository.** A runtime and `~/.claude/skills` see one flat list. `scripts/toolbox_check.py` enforces it.
5. **Skills refer to each other by name, never by relative path.** Relative paths break once a department is installed as a plugin.
6. **Agents sit directly in `agents/`, without subfolders,** so a plugin names an agent `finance:fpa-forecast-reviewer` and nothing longer.
7. **Clone and link is the supported install.** A link script will build one merged folder of agents and skills for Claude Code, Codex and any agent runtime. Each department is shaped so a plugin manifest can be added later without moving files.
8. **Nothing owner-specific is written into the repository.** Owner facts are settings. The private-name lists live outside the repository and the pre-commit hook reads them.

## Consequences

- Departments depend on each other by name (accounting uses reporting's `finance-reviewer`). A plugin release will declare those dependencies in each `plugin.json`.
- The Python commands cross-import heavily, so they port in a separate step once their shared library has a home.
- Maturity is a frontmatter field, never a folder, so a piece never moves to change status.
