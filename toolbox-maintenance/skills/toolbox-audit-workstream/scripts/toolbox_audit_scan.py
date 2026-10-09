# /// script
# dependencies = ["pyyaml"]
# ///
"""Read the agent toolbox before the toolbox audit's session and write what code can find to scan.json.

Read-only. It reads one toolbox checkout (--root, else the `repo` setting under
[toolbox-audit-workstream]) laid out by department, `<department>/agents/<name>.md` and
`<department>/skills/<name>/SKILL.md` with each command a script in the owning skill's `scripts/`
folder. It runs the toolbox's own `scripts/toolbox_check.py` for privacy and structure rather than
repeating it, and the orchestrator-scaffold lint for each orchestrator when that skill is present.

Each finding is an item with a stable `key` (so the findings ledger can tell a new finding from
one still open), a `section`, a `kind`, a `level` (error, warning or info), `where` and `text`:

- check: what the toolbox check reports about structure (names, frontmatter, relative paths).
- guards: the toolbox check's privacy hits, one item per file and kind, file only; a private name
  is never copied into the scan. Any denylisted name elsewhere in the scan (a file path, a
  lint's text) is replaced by "(withheld)" before the scan is printed or written.
- lint: frontmatter that does not parse; descriptions over 700 characters; the scaffold lint of
  each `-orchestrator` agent; and, per agent file, drift from the agent file standard (ADR 0003,
  warnings, report only): a missing or out-of-order section (`template-sections`), an
  orchestrator without `## Team` (`template-team`) or without the five stages A to E under
  `## Approach`, each with its Goal, Who and Move on when (`template-stages`), and a sub-agent
  whose body is a step script (`template-steps`: a `## Steps` heading, or two or more headings
  such as `## Step 1` or `### 1.`).
- drift: a script path or a `skills:` entry naming something that does not exist; a department
  the toolbox check does not cover; a department README out of step with its folder; an
  environment variable or a settings table a script reads that docs/settings.md does not describe.
- scripts: departures from ADR 0002 (a code file outside a skill's scripts folder, a hyphen in a
  script's name, no docstring, a package used without its `# /// script` block, imports from
  outside its folder, no test, `--help` failing under plain python3).
- unused (info): agents, skills and scripts no other file names. Department READMEs do not count
  as a mention, since they list everything.
- duplicates (info): agent or skill pairs whose descriptions share most of their words.

It also writes `teams` (each orchestrator's agents and the skills they load), `template` (per
department, its agents and how many drift from the standard), `counts` and
`sections` (each section's ok flag and error). The first line printed is `FRESH: <counts>`, or
`STALE: <sections that could not be read>; ...`. Exit 0 when it ran; 2 on a bad argument.

Example:
    python3 toolbox_audit_scan.py --root ~/src/automation-toolbox --out RUN/scan.json
"""

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import _common as c

THIRD_PARTY = {"yaml", "openpyxl", "pptx", "docx", "pypdf", "PIL"}
STOPWORDS = set("""the and for with from that this into each what when where which their them then than
over only every one its is are was were has have had not nor but any all own same other more most
about after before under while also does done used uses use run runs agent agents skill skills tool tools
owner call calls brief briefs returns return writes write reads read nothing never""".split())
DUP_THRESHOLD = 0.5
# Scripts the scan runs must leave no bytecode caches behind in the toolbox it reads.
QUIET_ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
DUP_MAX = 40
SCRIPT_REF = re.compile(r"~/\.claude/skills/([A-Za-z0-9_.-]+)/scripts/([A-Za-z0-9_./-]+\.(?:py|sh))")
ENV_READ = re.compile(r"""os\.(?:environ\.get|getenv)\(\s*["']([A-Z][A-Z0-9_]+)["']|os\.environ\[\s*["']([A-Z][A-Z0-9_]+)["']\s*\]""")
SETTINGS_TABLE = re.compile(r"""\bsettings\(\s*["']([a-z0-9-]+)["']""")
CHECK_LINE = re.compile(r"^(?P<file>[^:]+?)(?::(?P<line>\d+))?: (?P<why>.+)$")
STRUCTURE = ("frontmatter name", "missing description", "already used by", "no SKILL.md", "no subfolders",
             "relative path to another skill", "quote the description")


def short_hash(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


def item(section, kind, level, where, text, key=None, evidence=None):
    return {"key": key or f"{section}:{kind}:{where}:{short_hash(text)}", "section": section, "kind": kind,
            "level": level, "where": where, "text": text, "evidence": evidence or []}


class Toolbox:
    """Where everything is, read once."""

    def __init__(self, root):
        self.root = root
        self.departments = sorted(p.name for p in root.iterdir()
                                  if p.is_dir() and not p.name.startswith(".") and ((p / "agents").is_dir() or (p / "skills").is_dir()))
        self.agents = {p.stem: p for d in self.departments for p in sorted((root / d / "agents").glob("*.md"))}
        self.skills = {p.name: p for d in self.departments for p in sorted((root / d / "skills").glob("*")) if p.is_dir()}
        self.scripts = sorted(p for d in self.departments for p in (root / d / "skills").glob("*/scripts/*")
                              if p.is_file() and p.suffix in (".py", ".sh") and p.name != "_common.py")
        self.texts = {}
        for d in self.departments:
            for p in (root / d).rglob("*"):
                if p.is_file() and p.suffix in (".md", ".py", ".sh", ".yaml", ".yml", ".json", ".toml") and "__pycache__" not in p.parts:
                    try:
                        self.texts[p] = p.read_text(encoding="utf-8")
                    except (OSError, UnicodeDecodeError):
                        continue
        for extra in ("CONTEXT.md", "docs/settings.md"):
            p = root / extra
            if p.is_file():
                self.texts[p] = p.read_text(encoding="utf-8")

    def rel(self, path):
        try:
            return str(Path(path).relative_to(self.root))
        except ValueError:
            return str(path)

    def meta(self, path):
        return c.parse_frontmatter(path.read_text(encoding="utf-8"))

    def orchestrators(self):
        return [n for n in self.agents if n.endswith("-orchestrator")]


# --- check and guards: the toolbox's own check ---------------------------------------------

def check_items(tb):
    script = tb.root / "scripts" / "toolbox_check.py"
    if not script.is_file():
        raise RuntimeError("scripts/toolbox_check.py not found in the toolbox")
    done = subprocess.run([sys.executable, str(script)], cwd=str(tb.root), capture_output=True, text=True, timeout=600, env=QUIET_ENV)
    grouped = {}
    out = []
    for line in done.stdout.splitlines():
        m = CHECK_LINE.match(line.strip())
        if not m:
            continue
        where, why = m.group("file"), m.group("why")
        if why.startswith("private name"):
            kind = "private-name-in-path" if "in path" in why else "private-name"
            grouped.setdefault((where, kind), []).append(m.group("line") or "")
        elif any(s in why for s in STRUCTURE):
            out.append(item("check", "structure", "error", where, why, evidence=["scripts/toolbox_check.py"]))
        elif "imports" in why or "relative import" in why or "does not parse" in why:
            out.append(item("scripts", "imports", "error", where, why, evidence=["scripts/toolbox_check.py"]))
        else:
            grouped.setdefault((where, re.sub(r"[^a-z]+", "-", why.lower()).strip("-")), []).append(m.group("line") or "")
    for (where, kind), lines in sorted(grouped.items()):
        what = "a private name from the denylist" if kind.startswith("private-name") else kind.replace("-", " ")
        out.append(item("guards", kind, "error", where,
                        f"{len(lines)} hit(s) of {what} (the toolbox check names the lines; the name is not copied here)",
                        key=f"guards:{kind}:{where}", evidence=[f"lines {', '.join(x for x in lines if x) or 'path'}"]))
    if done.returncode not in (0, 1):
        raise RuntimeError(f"toolbox_check.py exited {done.returncode}: {done.stderr.strip()[:200]}")
    return out


# --- lint ---------------------------------------------------------------------------------

def lint_items(tb):
    out = []
    for kind, paths in (("agent", tb.agents.values()), ("skill", [p / "SKILL.md" for p in tb.skills.values()])):
        for path in paths:
            if not path.is_file():
                continue
            where = tb.rel(path)
            meta, why = tb.meta(path)
            if meta is None:
                out.append(item("lint", "frontmatter", "error", where, why, key=f"lint:frontmatter:{where}"))
                continue
            desc = c.one_line(meta.get("description"))
            if len(desc) > c.DESCRIPTION_LIMIT:
                out.append(item("lint", "description", "error" if kind == "agent" else "warning", where,
                                f"description is {len(desc)} characters, over {c.DESCRIPTION_LIMIT}",
                                key=f"lint:description:{where}"))
    scaffold = next(iter(tb.root.glob("*/skills/orchestrator-scaffold/scripts/orchestrator_scaffold.py")), None)
    if scaffold is None:
        out.append(item("lint", "scaffold", "info", "orchestrator-scaffold",
                        "the orchestrator-scaffold skill is not in this toolbox; orchestrators were not linted against the design",
                        key="lint:scaffold:missing"))
        return out
    for name in tb.orchestrators():
        done = subprocess.run([sys.executable, str(scaffold), "lint", name, "--root", str(tb.root), "--format", "json"],
                              capture_output=True, text=True, timeout=120, env=QUIET_ENV)
        try:
            result = json.loads(done.stdout)
        except ValueError:
            out.append(item("lint", "scaffold", "warning", tb.rel(tb.agents[name]),
                            f"orchestrator-scaffold lint could not read it: {(done.stderr or done.stdout).strip()[:200]}"))
            continue
        for f in result.get("findings") or []:
            if f.get("lint") in ("description", "names"):
                continue  # the description length is above; private names are the guards section
            out.append(item("lint", str(f.get("lint") or "scaffold"), str(f.get("level") or "warning"),
                            str(f.get("where") or name), str(f.get("text") or ""), evidence=[f"orchestrator-scaffold lint {name}"]))
    return out


# --- the agent file standard (ADR 0003) -----------------------------------------------------

SECTIONS = ("Goal", "Inputs", "Context", "Approach", "Boundaries", "Done when", "Output")
ORCHESTRATOR_SECTIONS = ("Goal", "Inputs", "Context", "Approach", "Team", "Boundaries", "Done when", "Output")
STAGES = ("A. Gather", "B. Plan & clarify", "C. Build", "D. Test & review", "E. Deliver")
STAGE_PARTS = (("Goal", r"\*\*\s*Goal\b"), ("Who", r"\*\*\s*Who\b"), ("Move on when", r"\*\*\s*Move on when\b"))
HEADING = re.compile(r"^(#{2,3})\s+(.+?)\s*#*\s*$")
STEPS_HEADING = re.compile(r"^(?:the\s+)?steps?$", re.I)
NUMBERED_HEADING = re.compile(r"^(?:step\s+\d+\b|\d+[.)](?:\s|$))", re.I)


def headings(body):
    """[(level, title, the text under it)] for the ## and ### headings outside fenced code."""
    out, fence = [], False
    for line in body.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        m = None if fence else HEADING.match(line)
        if m:
            out.append([len(m.group(1)), m.group(2).strip(), ""])
        elif out:
            out[-1][2] += line + "\n"
    return [tuple(h) for h in out]


def template_problems(name, text):
    """[(kind, text)]: where one agent file departs from the agent file standard. Report only."""
    hs = headings(c.split_text(text)[1])
    top = [title for level, title, _ in hs if level == 2]
    orchestrator = name.endswith("-orchestrator")
    want = ORCHESTRATOR_SECTIONS if orchestrator else SECTIONS
    problems = []
    missing = [s for s in SECTIONS if s not in top]
    seen = list(dict.fromkeys(t for t in top if t in want))
    expected = [s for s in want if s in seen]
    parts = []
    if missing:
        parts.append("missing " + ", ".join(f"## {s}" for s in missing))
    if seen != expected:
        parts.append("out of order (" + ", ".join(seen) + "; the standard is " + ", ".join(expected) + ")")
    if parts:
        problems.append(("template-sections", "; ".join(parts)))
    if orchestrator:
        if "Team" not in top:
            problems.append(("template-team", "an orchestrator with no ## Team section"))
        stages, inside = [], False
        for level, title, under in hs:
            if level == 2:
                inside = title == "Approach"
            elif inside:
                stages.append((title, under))
        titles = [title for title, _ in stages]
        if "Approach" not in top:
            problems.append(("template-stages", "no ## Approach, so none of the five stages A to E"))
        elif [s for s in titles if s in STAGES] != list(STAGES):
            absent = [s for s in STAGES if s not in titles]
            what = ("missing " + ", ".join(f"### {s}" for s in absent)) if absent else \
                "the stages are out of order"
            problems.append(("template-stages", f"## Approach does not hold the five stages: {what}"))
        else:
            thin = [f"{title} (no {', '.join(p for p, rx in STAGE_PARTS if not re.search(rx, under))})"
                    for title, under in stages if title in STAGES
                    and not all(re.search(rx, under) for _, rx in STAGE_PARTS)]
            if thin:
                problems.append(("template-stages", "a stage without its Goal, Who and Move on when: " + "; ".join(thin)))
    else:
        steps = [title for _, title, _ in hs if STEPS_HEADING.match(title)]
        numbered = [title for _, title, _ in hs if NUMBERED_HEADING.match(title)]
        if steps or len(numbered) >= 2:
            shown = (steps + numbered)[:4]
            problems.append(("template-steps", "a sub-agent written as a step script (" +
                             ", ".join(f'"{s}"' for s in shown) + "); its procedure belongs in a skill it loads"))
    return problems


def template_items(tb):
    out = []
    for name, path in tb.agents.items():
        where = tb.rel(path)
        for kind, text in template_problems(name, path.read_text(encoding="utf-8")):
            out.append(item("lint", kind, "warning", where, text, key=f"lint:{kind}:{where}",
                            evidence=["agent-standard.md in the orchestrator-scaffold skill"]))
    return out


def template_summary(tb, items):
    """Per department: how many agents it has and how many drift from the standard."""
    flagged = {i["where"] for i in items if i["section"] == "lint" and i["kind"].startswith("template-")}
    summary = {}
    for name, path in tb.agents.items():
        dept = Path(tb.rel(path)).parts[0]
        row = summary.setdefault(dept, {"agents": 0, "flagged": 0})
        row["agents"] += 1
        row["flagged"] += tb.rel(path) in flagged
    return dict(sorted(summary.items()))


# --- drift --------------------------------------------------------------------------------

def checked_departments(root):
    """The DEPARTMENTS list the toolbox check walks, read from its source."""
    tree = ast.parse((root / "scripts" / "toolbox_check.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "DEPARTMENTS" for t in node.targets):
            return set(ast.literal_eval(node.value))
    return set()


def owning_skill(tb, path):
    parts = Path(tb.rel(path)).parts
    return parts[2] if len(parts) > 3 and parts[1] == "skills" else None


def drift_items(tb):
    out = []
    for path, text in tb.texts.items():
        if "tests" in Path(tb.rel(path)).parts:
            continue  # test fixtures name made-up skills and scripts on purpose
        for m in SCRIPT_REF.finditer(text):
            skill, script = m.group(1), m.group(2)
            target = tb.skills.get(skill)
            if target is None:
                out.append(item("drift", "script-ref", "error", tb.rel(path),
                                f"names the script {script} of the skill {skill}, which this toolbox does not have",
                                key=f"drift:script-ref:{tb.rel(path)}:{skill}/{script}"))
            elif not (target / "scripts" / script).is_file():
                out.append(item("drift", "script-ref", "error", tb.rel(path),
                                f"names {skill}/scripts/{script}, which does not exist",
                                key=f"drift:script-ref:{tb.rel(path)}:{skill}/{script}"))
    for name, path in tb.agents.items():
        meta, _ = tb.meta(path)
        skills = (meta or {}).get("skills") or []
        for s in skills if isinstance(skills, list) else [skills]:
            if str(s) not in tb.skills:
                out.append(item("drift", "skills", "error", tb.rel(path), f"loads the skill {s}, which this toolbox does not have",
                                key=f"drift:skills:{name}:{s}"))
    covered = checked_departments(tb.root)
    for d in tb.departments:
        if d not in covered:
            out.append(item("drift", "department", "error", d,
                            f"the department {d} is not in the toolbox check's DEPARTMENTS, so its structure is never checked",
                            key=f"drift:department:{d}"))
        readme = tb.root / d / "README.md"
        if not readme.is_file():
            out.append(item("drift", "readme", "warning", d, "the department has no README.md", key=f"drift:readme:{d}"))
            continue
        text = readme.read_text(encoding="utf-8")
        named = set()
        for line in text.splitlines():
            if line.startswith("|") and not set(line) <= set("|- :"):
                named |= set(re.findall(r"`([a-z0-9-]+)`", line.strip().strip("|").split("|")[0]))
        own = {n for n, p in tb.agents.items() if Path(tb.rel(p)).parts[0] == d} | \
              {n for n, p in tb.skills.items() if Path(tb.rel(p)).parts[0] == d}
        for n in sorted(own - named):
            out.append(item("drift", "readme", "warning", f"{d}/README.md", f"{n} is in the department but not in its README tables",
                            key=f"drift:readme-missing:{d}:{n}"))
        for n in sorted(named - set(tb.agents) - set(tb.skills)):
            if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)+", n):
                out.append(item("drift", "readme", "warning", f"{d}/README.md",
                                f"the README lists {n}, which no department has as an agent or skill",
                                key=f"drift:readme-stale:{d}:{n}"))
    settings_doc = (tb.root / "docs" / "settings.md")
    doc = settings_doc.read_text(encoding="utf-8") if settings_doc.is_file() else ""
    for path in tb.scripts:
        if path.suffix != ".py" or "tests" in path.parts:
            continue
        text = tb.texts.get(path, "")
        common = path.parent / "_common.py"
        text_all = text + (tb.texts.get(common, "") if common.is_file() else "")
        for m in ENV_READ.finditer(text):
            var = m.group(1) or m.group(2)
            if f"`{var}`" not in doc and var not in ("HOME", "PATH", "USER"):
                out.append(item("drift", "env", "warning", tb.rel(path),
                                f"reads the environment variable {var}, which docs/settings.md does not describe",
                                key=f"drift:env:{tb.rel(path)}:{var}"))
        for table in set(SETTINGS_TABLE.findall(text_all)):
            if f"[{table}]" not in doc:
                out.append(item("drift", "settings", "warning", tb.rel(path),
                                f"reads the settings table [{table}], which docs/settings.md does not describe",
                                key=f"drift:settings:{tb.rel(path)}:{table}"))
    return out


# --- scripts (ADR 0002) --------------------------------------------------------------------

def third_party(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names & THIRD_PARTY


def script_items(tb, run_help=True):
    out = []
    for d in tb.departments:
        for p in (tb.root / d).rglob("*"):
            if p.is_file() and p.suffix in (".py", ".sh") and "__pycache__" not in p.parts:
                parts = Path(tb.rel(p)).parts
                if not (len(parts) >= 5 and parts[1] == "skills" and parts[3] == "scripts"):
                    out.append(item("scripts", "placement", "warning", tb.rel(p),
                                    "a code file outside any skill's scripts/ folder (ADR 0002: a command lives in the skill that owns it)",
                                    key=f"scripts:placement:{tb.rel(p)}"))
    for path in tb.scripts:
        if path.suffix != ".py" or "tests" in path.parts:
            continue
        where = tb.rel(path)
        text = tb.texts.get(path, "")
        if "-" in path.stem:
            out.append(item("scripts", "name", "warning", where, "a hyphen in the script's name; ADR 0002 writes commands with underscores",
                            key=f"scripts:name:{where}"))
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue  # the toolbox check reports it
        if not ast.get_docstring(tree):
            out.append(item("scripts", "docstring", "warning", where, "no docstring saying what it does, its inputs and an example",
                            key=f"scripts:docstring:{where}"))
        packages = third_party(tree)
        common = path.parent / "_common.py"
        if common.is_file() and re.search(r"^\s*import _common|^\s*from _common", text, re.M):
            try:
                packages |= third_party(ast.parse(tb.texts.get(common, "")))
            except SyntaxError:
                pass
        if packages and "# /// script" not in text:
            out.append(item("scripts", "dependencies", "warning", where,
                            f"uses {', '.join(sorted(packages))} with no `# /// script` dependencies block",
                            key=f"scripts:dependencies:{where}"))
        tests = "".join(tb.texts.get(t, "") for t in sorted((path.parent / "tests").glob("*.py")))
        if path.stem not in tests:
            out.append(item("scripts", "tests", "warning", where, "no test in the skill's scripts/tests names this script",
                            key=f"scripts:tests:{where}"))
        if run_help and not packages:
            try:
                done = subprocess.run(["python3", str(path), "--help"], capture_output=True, text=True, timeout=30,
                                      cwd=str(path.parent), env=QUIET_ENV)
                failed = done.returncode != 0
                why = (done.stderr or done.stdout).strip().splitlines()[-1:] or [""]
            except subprocess.TimeoutExpired:
                failed, why = True, ["timed out after 30 seconds"]
            if failed:
                out.append(item("scripts", "help", "error", where, f"`python3 {path.name} --help` fails: {why[0][:160]}",
                                key=f"scripts:help:{where}"))
    return out


# --- unused and duplicates -----------------------------------------------------------------

def mentioned(tb, name, own):
    rx = re.compile(rf"(?<![A-Za-z0-9_-]){re.escape(name)}(?![A-Za-z0-9_-])")
    return any(name in text and not own(p) and p.name != "README.md" and rx.search(text) for p, text in tb.texts.items())


def unused_items(tb):
    out = []
    for name, path in tb.agents.items():
        if not mentioned(tb, name, lambda p, me=path: p == me):
            out.append(item("unused", "agent", "info", tb.rel(path), f"no other file names the agent {name}",
                            key=f"unused:agent:{name}"))
    for name, folder in tb.skills.items():
        if not mentioned(tb, name, lambda p, f=folder: p.is_relative_to(f)):
            out.append(item("unused", "skill", "info", tb.rel(folder),
                            f"no agent or other skill names the skill {name}; only a person can invoke it",
                            key=f"unused:skill:{name}"))
    for path in tb.scripts:
        if "tests" in path.parts:
            continue
        tests = path.parent / "tests"
        names = {path.name, path.stem.replace("_", "-")}
        if not any(mentioned(tb, n, lambda p, me=path, t=tests: p == me or p.is_relative_to(t)) for n in names):
            out.append(item("unused", "script", "info", tb.rel(path), f"no agent, skill or other script names {path.name}",
                            key=f"unused:script:{tb.rel(path)}"))
    return out


def words(text):
    return {w for w in re.findall(r"[a-z][a-z-]{3,}", text.lower()) if w not in STOPWORDS}


def duplicate_items(tb):
    described = []
    for name, path in tb.agents.items():
        described.append(("agent", name, words(str((tb.meta(path)[0] or {}).get("description") or ""))))
    for name, folder in tb.skills.items():
        if (folder / "SKILL.md").is_file():
            described.append(("skill", name, words(str((tb.meta(folder / "SKILL.md")[0] or {}).get("description") or ""))))
    pairs = []
    for i, (ka, a, wa) in enumerate(described):
        for kb, b, wb in described[i + 1:]:
            if ka != kb or len(wa) < 6 or len(wb) < 6:
                continue
            score = len(wa & wb) / len(wa | wb)
            if score >= DUP_THRESHOLD:
                pairs.append((score, ka, *sorted((a, b))))
    pairs.sort(reverse=True)
    return [dict(item("duplicates", kind, "info", f"{a} / {b}", f"the {kind}s {a} and {b} share {score:.0%} of their descriptions' words",
                      key=f"duplicates:{kind}:{a}:{b}"), similarity=round(score, 2)) for score, kind, a, b in pairs[:DUP_MAX]]


def teams(tb):
    """Each orchestrator's agents (backticked names in its tables) and the skills each loads."""
    result = {}
    for name in tb.orchestrators():
        body = c.split_text(tb.agents[name].read_text(encoding="utf-8"))[1]
        members = []
        for line in body.splitlines():
            if line.startswith("|") and not set(line) <= set("|- :"):
                for n in re.findall(r"`([a-z0-9-]+)`", line.strip().strip("|").split("|")[0]):
                    if n in tb.agents and n not in members and n != name:
                        members.append(n)
        result[name] = {"agent_file": tb.rel(tb.agents[name]),
                        "workers": [{"agent": m, "skills": (tb.meta(tb.agents[m])[0] or {}).get("skills") or []} for m in members]}
    return result


def scan(root, run_help=True):
    tb = Toolbox(root)
    items, sections = {}, {}

    def section(name, fn):
        try:
            got = fn()
            sections[name] = {"ok": True}
            return got
        except Exception as exc:  # a section that fails is reported, never fatal
            sections[name] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]}
            return []

    for name, fn in (("check", lambda: check_items(tb)), ("lint", lambda: lint_items(tb) + template_items(tb)),
                     ("drift", lambda: drift_items(tb)),
                     ("scripts", lambda: script_items(tb, run_help)), ("unused", lambda: unused_items(tb)),
                     ("duplicates", lambda: duplicate_items(tb))):
        for it in section(name, fn) or []:
            items.setdefault(it["key"], it)
    team = section("teams", lambda: teams(tb)) or {}
    order = {lvl: i for i, lvl in enumerate(c.LEVELS)}
    listed = sorted(items.values(), key=lambda i: (order.get(i["level"], 9), i["section"], i["key"]))
    counts = {"departments": len(tb.departments), "agents": len(tb.agents), "orchestrators": len(tb.orchestrators()),
              "skills": len(tb.skills), "scripts": len([p for p in tb.scripts if "tests" not in p.parts]),
              "error": sum(1 for i in listed if i["level"] == "error"),
              "warning": sum(1 for i in listed if i["level"] == "warning"),
              "info": sum(1 for i in listed if i["level"] == "info")}
    result = {"tool": "toolbox-audit-scan", "version": 1, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "counts": counts, "sections": sections, "teams": team, "template": template_summary(tb, listed),
              "items": listed}
    # A denylisted name anywhere (a file path, a lint's text, a section's error) is replaced by
    # "(withheld)" before anything is printed or stored. Only `root`, the checkout the analysts
    # open, is kept as given: it is the owner's own path and the Run folder is private.
    return {**c.scrub(result, c.load_denylist()), "root": str(root)}


def headline(result):
    counts = result["counts"]
    text = (f"{counts['departments']} departments, {counts['agents']} agents ({counts['orchestrators']} orchestrators), "
            f"{counts['skills']} skills, {counts['scripts']} scripts; {counts['error']} error(s), "
            f"{counts['warning']} warning(s), {counts['info']} info")
    stale = [k for k, v in result["sections"].items() if not v.get("ok")]
    return f"STALE: {', '.join(stale)}; {text}" if stale else f"FRESH: {text}"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Scan an agent toolbox for the toolbox audit; writes scan.json.")
    ap.add_argument("--root", help="the toolbox checkout (default: the `repo` setting under [toolbox-audit-workstream])")
    ap.add_argument("--out", help="where to write scan.json (default: print the items only)")
    ap.add_argument("--no-help", action="store_true", help="skip running each script's --help")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args(argv)
    try:
        root = c.toolbox_repo(args.root)
    except c.AuditError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    result = scan(root, run_help=not args.no_help)
    if args.out:
        out = Path(args.out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        c.write_json(out, result)
    if args.format == "json":
        print(json.dumps(result, indent=1))
        return 0
    print(headline(result))
    for it in result["items"]:
        if it["level"] != "info":
            print(f"  {it['level']}: [{it['section']}/{it['kind']}] {it['where']}: {it['text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
