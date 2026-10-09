#!/usr/bin/env python3
"""Rebuild INDEX.md, the routing table of the owner's playbook folder.

The playbook folder has a shared ratification pipeline (`_inbox/`, `verdicts/`, `voice/`,
`policies/`, `meta/`) over one folder per business function (for example `finance/` or
`sales/`), each holding `playbooks/` (ratified), `drafts/` (not yet ratified) and
`briefs/` (context and per-client calibration). This script reads the frontmatter of
every Markdown file in those folders and writes one compact index an agent can keep in
context: ratified playbooks first, then cross-cutting policies, then drafts, then briefs.

Frontmatter fields read: `name`, `triggers` (list), `profiles` or `profile` (which agent
scopes may load it), `policy-refs` (list) and `calibration: per-client`.

Inputs: the folder as the one argument, else the setting `playbooks_dir`. Function
folders are every folder that is not part of the pipeline; the optional table
`function_labels` under [playbook-ratification] gives each a heading and its order
(for example `finance = "Finance: accounting, treasury, controls"`). An optional
`meta/INDEX-FOOTER.md` is appended as written, for pointers to rules kept elsewhere.

Writes FOLDER/INDEX.md and prints one line with the count of entries. It refuses a
folder that does not look like a playbook folder (no `_inbox/` or `meta/`, and no
INDEX.md this script wrote), so a wrong path never has its INDEX.md overwritten. Exit 0
on success, 1 when the folder is missing or refused, 2 when no folder is given or set.

Example:
  python3 playbook_index.py ~/path/to/playbooks
"""

from __future__ import annotations

import os
import re
import sys
import tomllib
from pathlib import Path

PIPELINE = {"policies", "_inbox", "verdicts", "voice", "meta"}
MARKER = "Generated from frontmatter by playbook_index.py"


def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


def frontmatter(path: Path) -> dict:
    """The simple `key: value` and `key: [a, b]` lines between the opening `---` lines."""
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        if ":" not in line or line.strip().startswith("#"):
            continue
        key, _, val = line.partition(":")
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            fm[key.strip()] = [v.strip().strip("'\"") for v in val[1:-1].split(",") if v.strip()]
        else:
            fm[key.strip()] = val.strip("'\"")
    return fm


def joined(value, sep=", ") -> str:
    return sep.join(value) if isinstance(value, list) else str(value or "")


def row(fm: dict, path: Path, root: Path) -> str:
    where = path.relative_to(root)
    if not fm:
        return f"- {path.stem} (no frontmatter) -> `{where}`"
    text = f"- **{fm.get('name', path.stem)}**"
    scopes = joined(fm.get("profiles") or fm.get("profile"), " ")
    if scopes:
        text += f" [{scopes}]"
    if fm.get("triggers"):
        text += f": {joined(fm['triggers'])}"
    extras = []
    if fm.get("policy-refs"):
        extras.append(f"refs: {joined(fm['policy-refs'])}")
    if fm.get("calibration") == "per-client":
        extras.append("load client calibration")
    if extras:
        text += f" ({'; '.join(extras)})"
    return f"{text} -> `{where}`"


def rows(folder: Path, root: Path) -> list[str]:
    if not folder.is_dir():
        return []
    return [row(frontmatter(f), f, root) for f in sorted(folder.glob("*.md"))
            if not f.name.startswith("_") and f.name != "README.md"]


def functions(root: Path, labels: dict) -> list[tuple[str, str]]:
    """Function folders, labelled ones first in the order given, the rest alphabetically."""
    on_disk = sorted(d.name for d in root.iterdir()
                     if d.is_dir() and d.name not in PIPELINE and not d.name.startswith((".", "_")))
    ordered = [n for n in labels if n in on_disk] + [n for n in on_disk if n not in labels]
    return [(n, labels.get(n, n)) for n in ordered]


def section(root, funcs, title, note, sub) -> str:
    blocks = []
    for name, label in funcs:
        found = rows(root / name / sub, root)
        if found:
            blocks.append(f"### {label}\n\n" + "\n".join(found))
    return f"## {title}\n*{note}*\n\n" + "\n\n".join(blocks) if blocks else ""


def build(root: Path, labels: dict) -> tuple[str, int]:
    funcs = functions(root, labels)
    parts = [
        section(root, funcs, "Ratified playbooks", "Apply these. Cite section numbers in outputs.", "playbooks"),
    ]
    policies = rows(root / "policies", root)
    if policies:
        parts.append("## Policies (cross-cutting, ratified)\n"
                     "*Bind every function. Playbooks point to them with policy-refs.*\n\n" + "\n".join(policies))
    parts.append(section(root, funcs, "Drafts (not ratified)",
                         "May inform proposals; never cite as authority.", "drafts"))
    parts.append(section(root, funcs, "Briefs (context and per-client calibration)",
                         "Client figures live here, never in a playbook. Never load two clients together.",
                         "briefs"))
    parts = [p for p in parts if p]
    entries = sum(p.count("\n- ") for p in parts)
    footer = root / "meta" / "INDEX-FOOTER.md"
    if footer.is_file():
        parts.append(footer.read_text(encoding="utf-8").strip())
    text = ("# Playbook index\n\n"
            "*Generated from frontmatter by playbook_index.py; do not edit by hand. Match the task "
            "against the triggers, then read the matched files and any client calibration before "
            "acting. Scope by profile. The rules live in the files, not here.*\n\n"
            + "\n\n".join(parts) + "\n")
    return text, entries


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    given = argv[0] if argv else settings().get("playbooks_dir")
    if not given:
        print("playbook_index: pass the playbook folder, or set `playbooks_dir` in the owner settings",
              file=sys.stderr)
        return 2
    root = Path(given).expanduser()
    if not root.is_dir():
        print(f"playbook_index: no folder at {root}", file=sys.stderr)
        return 1
    index = root / "INDEX.md"
    ours = index.is_file() and MARKER in index.read_text(encoding="utf-8")
    if not (ours or (root / "_inbox").is_dir() or (root / "meta").is_dir()):
        print(f"playbook_index: {root} has no _inbox/ or meta/ and no generated INDEX.md; "
              "refusing to write there", file=sys.stderr)
        return 1
    labels = settings("playbook-ratification").get("function_labels", {})
    text, entries = build(root, labels)
    (root / "INDEX.md").write_text(text, encoding="utf-8")
    print(f"wrote {root / 'INDEX.md'} ({entries} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
