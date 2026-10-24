#!/usr/bin/env python3
"""chief-of-staff-catalogue: what every department of this toolbox can do, read live.

    catalogue.py [--query WORDS] [--department D] [--limit N] [--automations-dir DIR]
                 [--format text|json]

Reads the toolbox checkout this script sits in, never a generated file, so it cannot go
stale: every department that is a plugin (<department>/.claude-plugin/plugin.json), and in
each one

- its main agents (an agent holding the Agent tool, or dispatching the department's worker
  or reviewer), with the description and the `## Inputs` section of each, and the exact
  line that starts it as a main session;
- the skills a person starts (no `user-invocable: false`, not a shared copy, not a
  reference), with the line that opens the plugin and the slash command;
- the department's commands (its bin/ folder).

Automations come from the owner's Automation folders (`--automations-dir`, else the
setting `automations_dir` under `[orchestrator-fleet]`): each folder's sentinel.yaml names
its `agent:` and `title:`, so each main agent lists the Automations that launch it. With
no folder, the Automations are left out and the output says so.

`--query` ranks departments' agents and skills by how many of the query's words appear in
their name and description (common words ignored) and keeps the best `--limit` (default
12); with no query, everything is listed. Read-only; writes nothing. Exit 0, or 2 when the
checkout or a setting cannot be read.

Example:
    chief-of-staff-catalogue --query "month end close" --limit 5
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
from pathlib import Path

STOP = set("a an and are as at be by do for from get how i in into is it its me my of on or our "
           "run the their this to up we what when where which who why with you your".split())


def toolbox_root(start: Path | None = None) -> Path | None:
    """The checkout holding this file: the folder above <department>/skills/."""
    here = Path(start or __file__).resolve()
    for folder in here.parents:
        if folder.name == "skills" and folder.parent != folder.parent.parent:
            return folder.parent.parent
    return None


def frontmatter(text: str) -> dict:
    """The single-line keys of a Markdown file's frontmatter (name, description, tools, ...)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
        if m:
            value = m.group(2).strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            out[m.group(1)] = value
    return out


def body(text: str) -> str:
    parts = text.split("\n---", 2) if text.startswith("---") else ["", "", text]
    return parts[2] if len(parts) == 3 else text


def section(text: str, heading: str, limit: int = 700) -> str:
    """The text under `## <heading>`, folded to one paragraph and cut to `limit` characters."""
    m = re.search(rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    if not m:
        return ""
    folded = " ".join(m.group(1).split())
    return folded if len(folded) <= limit else folded[:limit - 3].rstrip() + "..."


def tools_of(meta: dict) -> list[str]:
    raw = meta.get("tools", "")
    try:
        value = json.loads(raw)
        return [str(t) for t in value] if isinstance(value, list) else []
    except ValueError:
        return [t.strip().strip("\"'") for t in raw.strip("[]").split(",") if t.strip()]


def role(name: str, dept: str, meta: dict, text: str) -> str:
    if name == f"{dept}-reviewer":
        return "reviewer"
    if name == f"{dept}-worker":
        return "worker"
    if any(t == "Agent" or t.startswith("Agent(") for t in tools_of(meta)):
        return "main"
    if re.search(rf"(?<![\w-]){re.escape(dept)}-(worker|reviewer)(?![\w-])", body(text)):
        return "main"
    return "other"


def automations(folder: Path | None) -> dict[str, list[dict]]:
    """{agent: [{automation, title}]} from each Automation folder's sentinel.yaml."""
    out: dict[str, list[dict]] = {}
    if folder is None or not folder.is_dir():
        return out
    for spec in sorted(folder.glob("*/sentinel.yaml")):
        try:
            text = spec.read_text(encoding="utf-8")
        except OSError:
            continue
        agent = re.search(r"^agent:\s*['\"]?([\w:.-]+)", text, re.M)
        if not agent:
            continue
        title = re.search(r"^title:\s*(.+)$", text, re.M)
        name = agent.group(1).split(":")[-1]
        out.setdefault(name, []).append({"automation": spec.parent.name,
                                         "title": title.group(1).strip().strip("\"'") if title else ""})
    return out


def departments(root: Path, autos: dict[str, list[dict]], only: str | None = None) -> list[dict]:
    found = []
    for manifest in sorted(root.glob("*/.claude-plugin/plugin.json")):
        dept_dir = manifest.parent.parent
        dept = dept_dir.name
        if only and dept != only:
            continue
        try:
            plugin = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            plugin = {}
        entry = {"department": dept, "description": plugin.get("description", ""),
                 "plugin_dir": str(dept_dir), "agents": [], "skills": [],
                 "commands": sorted(p.name for p in (dept_dir / "bin").glob("*") if p.is_file())}
        for path in sorted((dept_dir / "agents").glob("*.md")):
            text = path.read_text(encoding="utf-8")
            meta = frontmatter(text)
            name = meta.get("name") or path.stem
            kind = role(name, dept, meta, text)
            agent = {"name": name, "role": kind, "description": meta.get("description", "")}
            if kind == "main":
                agent["inputs"] = section(body(text), "Inputs")
                agent["start"] = f"claude --plugin-dir {dept_dir} --agent {dept}:{name}"
                agent["automations"] = autos.get(name, [])
            entry["agents"].append(agent)
        for path in sorted((dept_dir / "skills").glob("*/SKILL.md")):
            if (path.parent / ".shared-copy").is_file():
                continue
            text = path.read_text(encoding="utf-8")
            meta = frontmatter(text)
            description = meta.get("description", "")
            if (meta.get("user-invocable", "").lower() == "false" or description.startswith("Reference")
                    or "not for a user request" in description.lower()):
                continue
            name = meta.get("name") or path.parent.name
            entry["skills"].append({"name": name, "description": description,
                                    "start": f"claude --plugin-dir {dept_dir}, then /{dept}:{name}"})
        found.append(entry)
    return found


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP and len(w) > 1}


def rank(found: list[dict], query: str, limit: int) -> list[dict]:
    """The best `limit` main agents and skills for the query, each with its department."""
    want = words(query)
    rows = []
    for dept in found:
        items = [dict(a, kind="agent") for a in dept["agents"] if a["role"] == "main"]
        items += [dict(s, kind="skill") for s in dept["skills"]]
        for item in items:
            name_hits = len(want & words(item["name"].replace("-", " ")))
            hits = len(want & words(item["name"].replace("-", " ") + " " + item["description"]))
            if hits:
                rows.append((hits + name_hits, item["kind"] == "agent", dict(item, department=dept["department"])))
    rows.sort(key=lambda r: (-r[0], not r[1], r[2]["department"], r[2]["name"]))
    return [r[2] for r in rows[:limit]]


def settings() -> dict:
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def first_sentence(text: str, limit: int = 220) -> str:
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    out = m.group(1) if m else text
    return out if len(out) <= limit else out[:limit - 3] + "..."


def as_text(found: list[dict], ranked: list[dict] | None, autos_note: str) -> str:
    lines = []
    if ranked is not None:
        for item in ranked:
            autos = ", ".join(a["automation"] for a in item.get("automations") or [])
            lines.append(f"{item['department']} | {item['kind']} | {item['name']}"
                         + (f" | Automations: {autos}" if autos else "")
                         + f"\n  {first_sentence(item['description'])}\n  start: {item['start']}")
    else:
        for dept in found:
            lines.append(f"## {dept['department']}: {first_sentence(dept['description'])}")
            for a in dept["agents"]:
                if a["role"] == "main":
                    autos = ", ".join(x["automation"] for x in a["automations"])
                    lines.append(f"- agent {a['name']}" + (f" (Automations: {autos})" if autos else "")
                                 + f": {first_sentence(a['description'])}")
            for s in dept["skills"]:
                lines.append(f"- skill {s['name']}: {first_sentence(s['description'])}")
    if autos_note:
        lines.append(autos_note)
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="What every department can do, read live from this toolbox checkout.")
    p.add_argument("--query", default=None, help="Rank agents and skills by these words")
    p.add_argument("--department", default=None, help="Only this department")
    p.add_argument("--limit", type=int, default=12)
    p.add_argument("--automations-dir", default=None, help="The owner's Automation folders (default: the setting)")
    p.add_argument("--format", choices=("text", "json"), default="text")
    args = p.parse_args(argv)
    root = toolbox_root()
    if root is None:
        print("chief-of-staff-catalogue: not inside a toolbox checkout", file=sys.stderr)
        return 2
    try:
        folder = args.automations_dir or (settings().get("orchestrator-fleet") or {}).get("automations_dir")
    except (OSError, ValueError) as exc:
        print(f"chief-of-staff-catalogue: the settings could not be read ({type(exc).__name__})", file=sys.stderr)
        return 2
    autos_dir = Path(folder).expanduser() if folder else None
    autos = automations(autos_dir)
    note = "" if autos_dir and autos_dir.is_dir() else \
        "Automations: not listed (no automations_dir under [orchestrator-fleet], or it is missing)."
    found = departments(root, autos, args.department)
    ranked = rank(found, args.query, max(1, args.limit)) if args.query else None
    if args.format == "json":
        print(json.dumps({"toolbox": str(root), "automations_dir": str(autos_dir or ""),
                          "results": ranked} if ranked is not None else
                         {"toolbox": str(root), "automations_dir": str(autos_dir or ""), "departments": found},
                         indent=1))
    else:
        print(as_text(found, ranked, note))
    return 0


if __name__ == "__main__":
    sys.exit(main())
