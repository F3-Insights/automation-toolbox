#!/usr/bin/env python3
"""Check the toolbox before anything is committed.

Two kinds of check run over every tracked or staged text file:

Privacy
  - Private names. The lists live outside the repository. Each file named in
    F3I_TOOLBOX_DENYLIST (separated by ":") is read, plus
    ~/.config/f3i-toolbox/denylist.txt when it exists. One term per line,
    "#" starts a comment, matching is whole-word and case-insensitive. A line
    starting with "=" is matched case-sensitively, for names that are also
    common words. A line starting with "@" names another list file to read.
  - Machine and account details: private and Tailscale IP addresses, Tailscale
    host names, home-directory paths, real email addresses (example.com,
    example.org and *.test are allowed), and token-shaped secrets.

Structure
  - Every agent is <department>/agents/<name>.md with frontmatter whose name
    equals the file name, and a description.
  - Every skill is <department>/skills/<name>/SKILL.md with frontmatter whose
    name equals the folder name, and a description.
  - Agent and skill names are unique across all departments.
  - No file reaches another skill by a relative "../" path; skills refer to
    each other by name.

Usage:
  python3 scripts/toolbox_check.py            check the whole working tree
  python3 scripts/toolbox_check.py PATH...    check only these files or folders

Exit status is 1 when anything fails. Each failure prints file:line and why.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEPARTMENTS = [
    "accounting", "finance", "strategy", "reporting", "projects", "process-engineering", "compliance",
    "software", "sales", "marketing", "learning", "productivity", "personal",
    "chief-of-staff", "recurring-summaries", "decision-playbooks", "toolbox-maintenance", "obsidian",
]
DEFAULT_DENYLIST = Path.home() / ".config" / "f3i-toolbox" / "denylist.txt"
TEXT_SUFFIXES = {
    ".md", ".py", ".sh", ".txt", ".json", ".yaml", ".yml", ".toml", ".csv",
    ".html", ".css", ".js", ".ts", ".ini", ".cfg", ".hujson", "",
}

PATTERNS = [
    ("private IP address", re.compile(
        r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b")),
    ("Tailscale IP address", re.compile(
        r"\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b")),
    ("Tailscale host name", re.compile(r"\b[\w-]+\.ts\.net\b")),
    ("home-directory path", re.compile(r"(?:/home/|/Users/|/mnt/c/Users/)(?!<)[A-Za-z0-9._-]+")),
    ("email address", re.compile(
        r"\b[A-Za-z0-9._%+-]+@(?!example\.(?:com|org|net)\b)(?![\w.-]*\.test\b)"
        r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("secret-shaped string", re.compile(
        r"(?:(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|xox[abp]-[A-Za-z0-9-]{10,}"
        r"|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")),
]
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
RELATIVE_SKILL_REF = re.compile(r"\.\./[\w./-]*(?:SKILL\.md|skills/)")


def load_denylist() -> list[tuple[str, re.Pattern[str]]]:
    paths = [Path(p) for p in os.environ.get("F3I_TOOLBOX_DENYLIST", "").split(":") if p]
    if DEFAULT_DENYLIST.exists():
        paths.append(DEFAULT_DENYLIST)
    terms: list[tuple[str, re.Pattern[str]]] = []
    while paths:
        path = paths.pop(0)
        if not path.exists():
            print(f"warning: denylist {path} not found", file=sys.stderr)
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("@"):
                paths.append(Path(line[1:]).expanduser())
                continue
            exact = line.startswith("=")
            term = line[1:] if exact else line
            flags = 0 if exact else re.I
            terms.append((term, re.compile(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", flags)))
    if not terms:
        print("warning: no private-name denylist loaded; names are not checked", file=sys.stderr)
    return terms


def files_to_check(args: list[str]) -> list[Path]:
    if args:
        found: list[Path] = []
        for arg in args:
            p = Path(arg).resolve()
            found.extend(sorted(x for x in p.rglob("*") if x.is_file()) if p.is_dir() else [p])
        return found
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [ROOT / line for line in out.splitlines() if line]


def unquoted_colon(path: Path) -> bool:
    """A frontmatter value with ': ' inside must be quoted, or YAML readers reject the file."""
    m = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    for line in (m.group(1).splitlines() if m else []):
        key, sep, value = line.partition(": ")
        value = value.strip()
        if sep and key in ("name", "description") and ": " in value and value[:1] not in "\"'[{>|":
            return True
    return False


def frontmatter(path: Path) -> dict[str, str]:
    m = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    if not m:
        return {}
    fields: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t", "-")):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip().strip("\"'")
    return fields


def check_privacy(files: list[Path], denylist) -> list[str]:
    failures = []
    for path in files:
        if path.suffix not in TEXT_SUFFIXES or path.name == Path(__file__).name:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        for term, rx in denylist:
            if rx.search(str(rel)):
                failures.append(f"{rel}: private name in path: {term}")
        for n, line in enumerate(text.splitlines(), 1):
            for why, rx in PATTERNS:
                if rx.search(line):
                    failures.append(f"{rel}:{n}: {why}")
            for term, rx in denylist:
                if rx.search(line):
                    failures.append(f"{rel}:{n}: private name: {term}")
            if RELATIVE_SKILL_REF.search(line):
                failures.append(f"{rel}:{n}: relative path to another skill; refer to it by name")
    return failures


def check_structure() -> list[str]:
    failures = []
    seen: dict[str, Path] = {}

    def claim(name: str, path: Path) -> None:
        if name in seen:
            failures.append(f"{path.relative_to(ROOT)}: name '{name}' already used by {seen[name].relative_to(ROOT)}")
        else:
            seen[name] = path

    for dept in DEPARTMENTS:
        for agent in sorted((ROOT / dept / "agents").glob("*.md")):
            fm = frontmatter(agent)
            if fm.get("name") != agent.stem:
                failures.append(f"{agent.relative_to(ROOT)}: frontmatter name must be '{agent.stem}'")
            if not fm.get("description"):
                failures.append(f"{agent.relative_to(ROOT)}: missing description")
            if unquoted_colon(agent):
                failures.append(f"{agent.relative_to(ROOT)}: quote the description, it contains ': '")
            claim(agent.stem, agent)
        for nested in (ROOT / dept / "agents").glob("*/**/*.md"):
            failures.append(f"{nested.relative_to(ROOT)}: agents sit directly in {dept}/agents/, no subfolders")
        for skill_dir in sorted(p for p in (ROOT / dept / "skills").glob("*") if p.is_dir()):
            skill = skill_dir / "SKILL.md"
            if not skill.exists():
                failures.append(f"{skill_dir.relative_to(ROOT)}: no SKILL.md")
                continue
            fm = frontmatter(skill)
            if fm.get("name") != skill_dir.name:
                failures.append(f"{skill.relative_to(ROOT)}: frontmatter name must be '{skill_dir.name}'")
            if not fm.get("description"):
                failures.append(f"{skill.relative_to(ROOT)}: missing description")
            if unquoted_colon(skill):
                failures.append(f"{skill.relative_to(ROOT)}: quote the description, it contains ': '")
            claim(skill_dir.name, skill)
    return failures


ALLOWED_PACKAGES = {"yaml", "openpyxl", "pptx", "docx", "pypdf", "PIL", "pytest"}


def check_scripts() -> list[str]:
    """A skill's scripts import only the standard library, the allowed packages and
    files in their own folder (tests may also import the scripts they test)."""
    failures = []
    for script in sorted(ROOT.glob("*/skills/*/scripts/**/*.py")):
        if ".venv" in script.parts or "__pycache__" in script.parts:
            continue
        local = {p.stem for p in script.parent.glob("*.py")}
        if script.parent.name == "tests":
            local |= {p.stem for p in script.parent.parent.glob("*.py")}
        try:
            tree = ast.parse(script.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            failures.append(f"{script.relative_to(ROOT)}: does not parse: {exc.msg}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            elif isinstance(node, ast.ImportFrom):
                failures.append(f"{script.relative_to(ROOT)}:{node.lineno}: relative import; import a sibling file by name")
                continue
            else:
                continue
            for name in names:
                if name not in sys.stdlib_module_names and name not in ALLOWED_PACKAGES and name not in local:
                    failures.append(f"{script.relative_to(ROOT)}:{node.lineno}: imports '{name}', which is not in its folder, the standard library or the allowed packages")
    return failures


def main(argv: list[str]) -> int:
    files = files_to_check(argv)
    failures = check_privacy(files, load_denylist())
    if not argv:
        failures += check_structure() + check_scripts()
    for failure in failures:
        print(failure)
    print(f"{len(failures)} problem(s) in {len(files)} file(s)", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
