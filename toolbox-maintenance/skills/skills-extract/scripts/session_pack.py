#!/usr/bin/env python3
"""Condense coding-agent sessions on one topic into a data pack.

Reads Claude Code transcripts, Codex session logs and, optionally, a claude.ai data export,
keeps the sessions that match the search terms or the project filter inside the window, and
writes one JSON pack: per session, the prompts the person typed, the programs it ran, the
files it wrote, the skills and sub-agents it used; across sessions, counts by month, project,
program, file and skill. It also records every sign that a skill was used (a Skill tool call,
a slash command, a read of a SKILL.md, a ``$skill`` mention in Codex, an edit inside a skill's
folder), which ``skill_inventory.py`` matches against the skills on the machine. Optionally adds
a repository's git log, so the model reads one pack instead of raw transcripts.

The pack holds private material. It is written only outside any git working tree.

Where the sessions are is a setting: ``claude_session_dirs`` and ``codex_session_dirs`` (lists of
folders) under ``[skills-extract]`` in the owner's settings file, defaulting to Claude Code's and
Codex's own folders (``~/.claude/projects``, ``~/.codex/sessions``). ``--claude-dir`` and
``--codex-dir`` override them.

Standard library only. Exit codes: 0 with ``WORK: ...`` or ``NOTHING`` on the first line of
stdout, 2 when it could not run (bad argument, unreadable source, refused output path).

Example:
    python3 session_pack.py --terms "reconcil,accrual,month-end" --since 90d --out ~/work/pack.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tomllib
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional

PROMPT_CHARS = 600
PROMPTS_PER_SESSION = 15
FILES_PER_SESSION = 30
PROGRAMS_PER_SESSION = 15
TOP = 40

# Messages a harness injects on the person's side of the conversation; none was typed.
NOT_TYPED = ("<task-notification>", "<local-command", "<command-", "Caveat:", "<system-reminder>",
             "This session is being continued", "Another Claude session", "[Request interrupted",
             "Base directory for this skill", "<environment_context>", "<user_instructions>",
             "<turn_aborted>", "# AGENTS.md instructions", "<permissions instructions>", "<bash-stdout>",
             "<bash-stderr>", "<bash-input>")
SLASH = re.compile(r"<command-name>/?([\w:.-]+)</command-name>")
CODEX_CMD = re.compile(r"""\bcmd\s*:\s*("(?:[^"\\]|\\.)*")""")
PATCH_FILE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.MULTILINE)
SKILL_FILE = re.compile(r"""[^\s'"`;|&<>(){}=]*/SKILL\.md\b""")
SKILL_FOLDER = re.compile(r"^(.*/skills/(?:\.system/)?[^/]+)/")
MENTION = re.compile(r"(?<![\w$])\$([a-z][a-z0-9-]*(?::[a-z0-9-]+)?)\b")
HEREDOC = re.compile(r"<<-?\s*['\"]?\w+")
QUOTED = re.compile(r"\"(?:[^\"\\\\]|\\\\.)*\"|'[^']*'", re.DOTALL)
PROGRAM = re.compile(r"^[\w.+-]+$")
SHELL_WORDS = {"cd", "echo", "true", "false", "export", "set", "then", "else", "elif", "fi", "do", "done", "for",
               "while", "if", "case", "esac", "in", "local", "return", "exit", "printf", "read", "test", "source"}
WRAPPERS = {"sudo", "env", "time", "nohup", "timeout", "xargs", "exec"}
SUBCOMMAND = {"git", "gh", "npm", "npx", "uv", "pip", "docker", "cargo", "make", "claude", "codex"}
CWD_STOP = {"home", "mnt", "users", "user", "coding", "projects", "onedrive", "documents",
            "desktop", "downloads", "general", "company", "shared documents", "workspace", "runs", "src", "docs",
            "files", "work", "worktrees", "repos", "claude", "codex", "skills", "agents", "scratchpad"}


class Refused(Exception):
    pass


def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


def session_dirs(key: str, default: str) -> List[str]:
    """A list of session folders from the [skills-extract] settings, else the tool's own default."""
    value = settings("skills-extract").get(key)
    if isinstance(value, str):
        value = [value]
    return [str(v) for v in value] if value else [default]


# --- small helpers ------------------------------------------------------------------------


def parse_when(text: Optional[str], end: bool = False) -> Optional[datetime]:
    """``YYYY-MM-DD``, an ISO timestamp, or ``Nd`` (days ago). An end date covers its whole day."""
    if not text:
        return None
    m = re.fullmatch(r"(\d+)d", text.strip())
    if m:
        return datetime.now(timezone.utc) - timedelta(days=int(m.group(1)))
    try:
        when = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise Refused(f"not a date: {text!r} (use YYYY-MM-DD, an ISO time, or Nd)") from exc
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    if end and re.fullmatch(r"\d{4}-\d{2}-\d{2}", text.strip()):
        when += timedelta(days=1)
    return when


def ts(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def iso(when: Optional[datetime]) -> Optional[str]:
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if when else None


def jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                yield row


def hit(term: str, text: str) -> bool:
    """A term matches at the start of a word: ``reconcil`` finds "reconciliation", ``close`` not "enclosed"."""
    return re.search(r"(?<![a-z0-9])" + re.escape(term), text) is not None


def clip(text: str, n: int = PROMPT_CHARS) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def typed(text: str) -> bool:
    stripped = text.lstrip()
    return bool(stripped) and not stripped.startswith(NOT_TYPED)


def programs(command: str) -> List[str]:
    """The programs a shell command runs: ``cd x && python3 -m pytest -q`` -> ``python3 -m pytest``."""
    out = []
    heredoc = HEREDOC.search(command)
    if heredoc:  # the body is a script or a document, not commands
        end = command.find("\n", heredoc.end())
        command = command if end < 0 else command[:end]
    command = QUOTED.sub("''", command)  # a quoted script (python -c "...") is one argument
    for segment in re.split(r"&&|\|\||;|\||\n", command):
        words = segment.strip().split()
        while words and (words[0] in WRAPPERS or re.fullmatch(r"\w+=\S*|\d+[smh]?", words[0])):
            words = words[1:]
        if not words or words[0] in SHELL_WORDS:
            continue
        name = words[0].rsplit("/", 1)[-1]
        if not PROGRAM.match(name) or name.startswith("-") or name.isdigit():
            continue
        if name.startswith("python") and len(words) > 2 and words[1] == "-m":
            name = f"{name} -m {words[2]}"
        elif name.startswith("python") and len(words) > 1 and words[1].endswith(".py"):
            name = f"{name} {words[1].rsplit('/', 1)[-1]}"
        elif name in SUBCOMMAND and len(words) > 1 and not words[1].startswith("-"):
            name = f"{name} {words[1]}"
        out.append(name)
    return out


def relative(path: str, cwd: Optional[str]) -> str:
    if cwd and path.startswith(cwd.rstrip("/") + "/"):
        return path[len(cwd.rstrip("/")) + 1:]
    return path


class Session:
    def __init__(self, source: str, sid: str, path: Path):
        self.source, self.id, self.path = source, sid, str(path)
        self.cwd: Optional[str] = None
        self.branch: Optional[str] = None
        self.start: Optional[datetime] = None
        self.end: Optional[datetime] = None
        self.origin = "interactive"
        self.title: Optional[str] = None
        self.prompts: List[str] = []
        self.runner_prompt: Optional[str] = None
        self.programs: Counter = Counter()
        self.written: Counter = Counter()
        self.read: Counter = Counter()
        self.skills: Counter = Counter()
        self.agents: Counter = Counter()
        self.mcp: Counter = Counter()
        self.skill_use: Counter = Counter()  # (skill name or SKILL.md folder, how) -> count

    def seen(self, when: Optional[datetime]) -> None:
        if when:
            self.start = when if not self.start or when < self.start else self.start
            self.end = when if not self.end or when > self.end else self.end

    def haystack(self) -> str:
        parts = [self.cwd or "", self.title or "", self.runner_prompt or "", *self.prompts, *self.written,
                 *self.programs, *self.skills, *self.agents]
        return "\n".join(parts).lower()

    def record(self, terms: List[str]) -> Dict[str, Any]:
        hay = self.haystack()
        hits = sorted({t for t in terms if hit(t, hay)})
        prompt_hits = [p for p in self.prompts if any(hit(t, p.lower()) for t in terms)] if terms else []
        keep = self.prompts[:1] + [p for p in prompt_hits if p not in self.prompts[:1]]
        keep += [p for p in self.prompts if p not in keep]
        return {
            "source": self.source, "session": self.id, "origin": self.origin,
            "start": iso(self.start), "end": iso(self.end),
            "minutes": round((self.end - self.start).total_seconds() / 60) if self.start and self.end else None,
            "cwd": self.cwd, "branch": self.branch, "title": self.title,
            "terms_hit": hits, "prompts_typed": len(self.prompts), "prompts_matching": len(prompt_hits),
            "prompts": [clip(p) for p in keep[:PROMPTS_PER_SESSION]],
            "runner_prompt": clip(self.runner_prompt) if self.runner_prompt else None,
            "programs": dict(self.programs.most_common(PROGRAMS_PER_SESSION)),
            "files_written": [relative(p, self.cwd) for p, _ in self.written.most_common(FILES_PER_SESSION)],
            "files_read": len(self.read),
            "skills": dict(self.skills), "agents": dict(self.agents),
            "mcp_tools": dict(self.mcp.most_common(10)),
            "skill_use": self.skill_rows(),
            "transcript": self.path,
        }

    def skill_rows(self) -> List[Dict[str, Any]]:
        return [{"skill": k, "how": how, "count": n} for (k, how), n in sorted(self.skill_use.items())]

    def absolute(self, path: str) -> str:
        path = os.path.expanduser(path.strip())
        if not path.startswith("/") and self.cwd:
            path = os.path.join(self.cwd, path)
        return os.path.normpath(path)

    def skill_files(self, text: str, how: str) -> None:
        """A SKILL.md named in a command or read: record its folder, made absolute."""
        for raw in SKILL_FILE.findall(text):
            folder = os.path.dirname(self.absolute(raw))
            if re.fullmatch(r"[\w.:-]+", os.path.basename(folder)) and not re.search(r"[$*?{]", folder):
                # a glob or a shell variable names no one skill
                self.skill_use[(folder, how)] += 1

    def skill_edit(self, path: str) -> None:
        m = SKILL_FOLDER.match(self.absolute(path) + "/")
        if m and not m.group(1).endswith("/skills"):
            self.skill_use[(m.group(1), "edit")] += 1


# --- readers --------------------------------------------------------------------------------


def read_claude(path: Path) -> Optional[Session]:
    s = Session("claude-code", path.stem, path)
    for row in jsonl(path):
        if row.get("isSidechain"):
            continue
        s.seen(ts(row.get("timestamp")))
        s.cwd = s.cwd or row.get("cwd")
        s.branch = s.branch or row.get("gitBranch")
        if row.get("type") == "summary" and row.get("summary") and not s.title:
            s.title = row["summary"]
        if str(row.get("entrypoint", "")).startswith("sdk") or row.get("promptSource") == "sdk":
            s.origin = "automated"
        message = row.get("message") or {}
        content = message.get("content")
        if row.get("type") == "user" and not row.get("isMeta") and row.get("promptSource") != "system":
            texts = [content] if isinstance(content, str) else [
                c.get("text", "") for c in content or [] if isinstance(c, dict) and c.get("type") == "text"]
            for text in texts:
                for name in SLASH.findall(text):
                    s.skills["/" + name] += 1
                    s.skill_use[(name, "slash")] += 1
                if not typed(text):
                    continue
                if s.origin == "automated" or row.get("promptSource") == "sdk":
                    s.runner_prompt = s.runner_prompt or text
                else:
                    s.prompts.append(text)
        if row.get("type") == "assistant" and isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool(s, block.get("name", ""), block.get("input") or {})
    if s.origin == "automated" and s.prompts:
        s.origin = "mixed"
    return s if s.start else None


def tool(s: Session, name: str, args: Dict[str, Any]) -> None:
    if name == "Bash":
        command = str(args.get("command", ""))
        for p in programs(command):
            s.programs[p] += 1
        s.skill_files(command, "read")
    elif name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        path = args.get("file_path") or args.get("notebook_path")
        if path:
            s.written[str(path)] += 1
            s.skill_edit(str(path))
    elif name == "Read":
        if args.get("file_path"):
            s.read[str(args["file_path"])] += 1
            s.skill_files(str(args["file_path"]), "read")
    elif name == "Skill":
        if args.get("skill"):
            s.skills[str(args["skill"])] += 1
            s.skill_use[(str(args["skill"]), "tool")] += 1
    elif name in ("Agent", "Task"):
        s.agents[str(args.get("subagent_type") or "general-purpose")] += 1
    elif name.startswith("mcp__"):
        s.mcp[name] += 1


def read_codex(path: Path) -> Optional[Session]:
    s = Session("codex", path.stem, path)
    items: List[str] = []  # older logs carry the prompt only as a response item
    for row in jsonl(path):
        s.seen(ts(row.get("timestamp")))
        kind = row.get("type")
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        if kind == "session_meta":
            source = payload.get("source")
            if payload.get("parent_thread_id") or (isinstance(source, dict) and "subagent" in source):
                return None  # a sub-agent's thread (a reviewer, a worker), like Claude Code's sidechains
            s.id = payload.get("id") or s.id
            s.cwd = s.cwd or payload.get("cwd")
            if "exec" in str(payload.get("originator", "")) or payload.get("source") == "exec":
                s.origin = "automated"
            git = payload.get("git") or {}
            s.branch = s.branch or (git.get("branch") if isinstance(git, dict) else None)
        elif kind == "turn_context":
            s.cwd = s.cwd or payload.get("cwd")
        elif kind == "event_msg" and payload.get("type") == "user_message":
            text = str(payload.get("message", ""))
            if typed(text):
                for name in MENTION.findall(text):
                    s.skill_use[(name, "mention")] += 1
                if s.origin == "automated":
                    s.runner_prompt = s.runner_prompt or text
                else:
                    s.prompts.append(text)
        elif kind == "response_item" and payload.get("type") == "message" and payload.get("role") == "user":
            for c in payload.get("content") or []:
                if isinstance(c, dict) and c.get("type") == "input_text" and typed(str(c.get("text", ""))):
                    items.append(str(c["text"]))
        elif kind == "response_item" and payload.get("type") == "function_call":
            try:
                args = json.loads(payload.get("arguments") or "{}")
            except ValueError:
                args = {}
            command = args.get("cmd") or args.get("command") or ""
            if isinstance(command, list):
                command = " ".join(map(str, command))
            for p in programs(str(command)):
                s.programs[p] += 1
            s.skill_files(str(command), "read")
            for f in PATCH_FILE.findall(str(args.get("input", ""))):
                s.written[f.strip()] += 1
                s.skill_edit(f)
        elif kind == "response_item" and payload.get("type") == "custom_tool_call":
            body = str(payload.get("input", ""))
            for raw in CODEX_CMD.findall(body):
                try:
                    command = json.loads(raw)
                except ValueError:
                    continue
                for p in programs(command):
                    s.programs[p] += 1
                s.skill_files(str(command), "read")
            for f in PATCH_FILE.findall(body):
                s.written[f.strip()] += 1
                s.skill_edit(f)
    if not s.prompts and not s.runner_prompt and items:
        if s.origin == "automated":
            s.runner_prompt = items[0]
        else:
            s.prompts = items
    if s.origin == "automated" and s.prompts:
        s.origin = "mixed"
    return s if s.start else None


def read_export(path: Path) -> Iterator[Session]:
    """A claude.ai data export's ``conversations.json``: chats from the web and desktop apps."""
    data = json.loads(path.read_text(encoding="utf-8"))
    for conv in data if isinstance(data, list) else []:
        s = Session("claude-chat", str(conv.get("uuid", "")), path)
        s.title = conv.get("name") or None
        for msg in conv.get("chat_messages") or []:
            s.seen(ts(msg.get("created_at")))
            if msg.get("sender") == "human":
                text = msg.get("text") or " ".join(
                    c.get("text", "") for c in msg.get("content") or [] if isinstance(c, dict))
                if typed(text):
                    s.prompts.append(text)
        s.seen(ts(conv.get("created_at")))
        if s.start:
            yield s


# --- gathering ------------------------------------------------------------------------------


def claude_files(root: Path, projects: List[str], since: Optional[datetime]) -> Iterable[Path]:
    if not root.is_dir():
        return []
    out = []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir():
            continue
        if projects and not any(p in folder.name.lower() for p in projects):
            continue
        for f in folder.glob("*.jsonl"):  # top level only: subagents/ holds sidechains
            if since and datetime.fromtimestamp(f.stat().st_mtime, timezone.utc) < since:
                continue
            out.append(f)
    return out


def codex_files(root: Path, since: Optional[datetime]) -> Iterable[Path]:
    if not root.is_dir():
        return []
    return [f for f in sorted(root.rglob("*.jsonl"))
            if not since or datetime.fromtimestamp(f.stat().st_mtime, timezone.utc) >= since]


def project_slug(name: str) -> str:
    """How Claude Code names a project folder after a path: every non-alphanumeric becomes '-'."""
    return re.sub(r"[^a-z0-9]", "-", name.lower())


def in_window(s: Session, since: Optional[datetime], until: Optional[datetime]) -> bool:
    if since and s.end and s.end < since:
        return False
    if until and s.start and s.start >= until:
        return False
    return True


def matches(s: Session, terms: List[str], projects: List[str]) -> bool:
    if projects and not any(p in (s.cwd or "").lower() or p in project_slug(s.cwd or "") for p in projects):
        return False
    if not terms:
        return True
    hay = s.haystack()
    return any(hit(t, hay) for t in terms)


def score(rec: Dict[str, Any]) -> tuple:
    return (len(rec["terms_hit"]), rec["prompts_matching"], rec["prompts_typed"], rec["start"] or "")


def git_section(repo: Path, since: Optional[datetime], until: Optional[datetime]) -> Dict[str, Any]:
    cmd = ["git", "-C", str(repo), "log", "--no-merges", "--date=short", "--format=%ad%x09%s"]
    if since:
        cmd.append(f"--since={iso(since)}")
    if until:
        cmd.append(f"--until={iso(until)}")
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        return {"path": str(repo), "error": f"git log failed: {exc}"}
    commits = [dict(zip(("date", "subject"), line.split("\t", 1))) for line in out.splitlines() if "\t" in line]
    docs = sorted(str(p.relative_to(repo)) for pattern in ("*.md", "docs/**/*.md")
                  for p in repo.glob(pattern) if ".git" not in p.parts)
    return {"path": str(repo), "commits": len(commits),
            "by_month": dict(sorted(Counter(c["date"][:7] for c in commits).items())),
            "recent": commits[:200], "docs": docs[:200]}


def skill_events(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Every sign of skill use in every matched session, typed or automated, for the inventory."""
    out = []
    for r in records:
        for use in r.get("skill_use", []):
            out.append({"session": r["session"], "source": r["source"], "date": (r["start"] or "")[:10],
                        "origin": r["origin"], **use})
    return out


def private_terms(sessions: List[Dict[str, Any]], repo: Optional[Dict[str, Any]]) -> List[str]:
    """Folder names, mailbox addresses and the login name the evidence carries, for the name check."""
    terms = set()
    home = Path.home()
    terms.add(home.name)
    for rec in sessions:
        cwd = rec.get("cwd") or ""
        if not cwd or cwd.startswith(("/tmp", "/var", "/private")):
            continue
        for part in Path(cwd).parts:
            for piece in re.split(r"\s+-\s+", part):
                key = " ".join(re.findall(r"[a-z0-9]+", piece.lower()))
                if len(key) < 3 or key in CWD_STOP or re.search(r"\d{6}", key):
                    continue
                terms.add(piece.strip())
        for p in rec.get("prompts", []):
            terms.update(re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", p))
    if repo and repo.get("path"):
        terms.add(Path(repo["path"]).name)
    return sorted(terms, key=str.lower)


def automation_groups(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Runs a scheduler or runner started, grouped by the opening of their prompt: work already automated."""
    groups: Dict[str, Dict[str, Any]] = {}
    for r in runs:
        opening = (r.get("runner_prompt") or "(no prompt)").split(". ")[0]
        key = re.sub(r"\d", "#", clip(opening, 90))
        g = groups.setdefault(key, {"signature": key, "runs": 0, "first": r["start"], "last": r["start"],
                                    "terms_hit": Counter(), "projects": Counter(), "programs": Counter()})
        g["runs"] += 1
        g["first"] = min(g["first"] or "", r["start"] or "") or None
        g["last"] = max(g["last"] or "", r["start"] or "") or None
        g["terms_hit"].update(r["terms_hit"])
        g["projects"][r["cwd"] or "(none)"] += 1
        g["programs"].update(r["programs"].keys())
    out = []
    for g in sorted(groups.values(), key=lambda g: -g["runs"]):
        out.append({**g, "terms_hit": [t for t, _ in g["terms_hit"].most_common(8)],
                    "projects": [p for p, _ in g["projects"].most_common(3)],
                    "programs": [p for p, _ in g["programs"].most_common(6)]})
    return out[:TOP * 2]


def inside_git_tree(path: Path) -> Optional[Path]:
    for parent in [path, *path.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def build(args: argparse.Namespace) -> Dict[str, Any]:
    since = parse_when(args.since)
    until = parse_when(args.until, end=True)
    terms = sorted({t.strip().lower() for chunk in args.terms for t in chunk.split(",") if t.strip()})
    projects = sorted({p.strip().lower() for chunk in args.project for p in chunk.split(",") if p.strip()})
    if not terms and not projects:
        raise Refused("give --terms, --project, or both")
    slugs = sorted({project_slug(p) for p in projects})

    scanned = Counter()
    kept: List[Dict[str, Any]] = []
    automated = Counter()
    for root in args.claude_dir:
        for f in claude_files(Path(root).expanduser(), slugs, since):
            scanned["claude-code"] += 1
            s = read_claude(f)
            if s and in_window(s, since, until) and matches(s, terms, projects):
                kept.append(s.record(terms))
    for root in args.codex_dir:
        for f in codex_files(Path(root).expanduser(), since):
            scanned["codex"] += 1
            s = read_codex(f)
            if s and in_window(s, since, until) and matches(s, terms, projects):
                kept.append(s.record(terms))
    for export in args.claude_export:
        path = Path(export).expanduser()
        if not path.is_file():
            raise Refused(f"no such export file: {path}")
        for s in read_export(path):
            scanned["claude-chat"] += 1
            if in_window(s, since, until) and matches(s, terms, projects):
                kept.append(s.record(terms))

    events = skill_events(kept)
    cwds = sorted({r["cwd"] for r in kept if r.get("cwd")})
    for rec in kept:
        automated[rec["origin"]] += 1
    runs = [r for r in kept if r["origin"] == "automated"]
    kept = [r for r in kept if r["origin"] != "automated"]
    kept.sort(key=score, reverse=True)
    total = len(kept)
    kept = kept[: args.max_sessions]

    def tally(key: str) -> Dict[str, int]:
        c: Counter = Counter()
        for rec in kept:
            value = rec[key]
            if isinstance(value, dict):
                c.update({k: 1 for k in value})  # sessions using it, not calls
            else:
                c.update(set(value))
        return dict(c.most_common(TOP))

    repo = git_section(Path(args.repo).expanduser(), since, until) if args.repo else None
    pack = {
        "generated_at": iso(datetime.now(timezone.utc)),
        "query": {"terms": terms, "projects": projects, "since": iso(since), "until": iso(until),
                  "max_sessions": args.max_sessions},
        "scanned": dict(scanned),
        "matched": total,
        "automated_matched": len(runs),
        "kept": len(kept),
        "summary": {
            "by_origin": dict(automated),
            "by_month": dict(sorted(Counter((r["start"] or "")[:7] for r in kept).items())),
            "by_project": dict(Counter(r["cwd"] or "(none)" for r in kept).most_common(TOP)),
            "by_term": {t: sum(1 for r in kept if t in r["terms_hit"]) for t in terms},
            "programs": tally("programs"),
            "skills": tally("skills"),
            "agents": tally("agents"),
            "files_written": tally("files_written"),
            "distinct_days": len({(r["start"] or "")[:10] for r in kept}),
        },
        "sessions": kept,
        "automated_runs": automation_groups(runs),
        "repo": repo,
        "cwds": cwds,
        "skill_events": events,
    }
    pack["private_terms"] = private_terms(kept, repo)
    return pack


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--terms", action="append", default=[], help="comma-separated search terms, matched "
                    "case-insensitively at the start of a word in prompts, folder, files, programs and skills; "
                    "repeatable")
    ap.add_argument("--project", action="append", default=[], help="keep only sessions whose working folder "
                    "contains this text (a repo or folder name); repeatable")
    ap.add_argument("--since", help="YYYY-MM-DD, ISO time, or Nd for N days ago")
    ap.add_argument("--until", help="YYYY-MM-DD (inclusive) or ISO time")
    ap.add_argument("--claude-dir", action="append", default=None, help="Claude Code projects folder "
                    "(default: the claude_session_dirs setting, else ~/.claude/projects); repeatable")
    ap.add_argument("--codex-dir", action="append", default=None, help="Codex sessions folder "
                    "(default: the codex_session_dirs setting, else ~/.codex/sessions); repeatable")
    ap.add_argument("--claude-export", action="append", default=[], help="a claude.ai export's "
                    "conversations.json, for desktop and web chats; repeatable")
    ap.add_argument("--repo", help="a git repository whose log and docs go in the pack")
    ap.add_argument("--max-sessions", type=int, default=400)
    ap.add_argument("--out", required=True, help="where to write the pack (outside any git working tree)")
    args = ap.parse_args(argv)
    if args.claude_dir is None:
        args.claude_dir = session_dirs("claude_session_dirs", "~/.claude/projects")
    if args.codex_dir is None:
        args.codex_dir = session_dirs("codex_session_dirs", "~/.codex/sessions")
    try:
        out = Path(args.out).expanduser().resolve()
        tree = inside_git_tree(out.parent)
        if tree:
            raise Refused(f"refusing to write the pack inside a git working tree ({tree}); "
                          "the pack holds private transcript content")
        pack = build(args)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(pack, indent=1, ensure_ascii=False), encoding="utf-8")
    except Refused as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not pack["matched"] and not pack["automated_matched"]:
        print("NOTHING")
        print(f"scanned {json.dumps(pack['scanned'])}; no session matched")
        return 0
    s = pack["summary"]
    print(f"WORK: {pack['matched']} sessions with typed prompts matched, {pack['kept']} kept, on "
          f"{s['distinct_days']} days; {pack['automated_matched']} automated runs in "
          f"{len(pack['automated_runs'])} groups")
    print(f"origin {json.dumps(s['by_origin'])}; months {json.dumps(s['by_month'])}")
    print(f"pack {out} ({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
