# /// script
# dependencies = ["pyyaml"]
# ///
"""Generate a new orchestrator's files from a spec, and lint an orchestrator that exists.

    orchestrator_scaffold.py generate SPEC.yaml [--root DIR] [--dry-run [--show]] [--update]
                                     [--launcher FILE --set PARAM=VALUE ...]
    orchestrator_scaffold.py lint NAME [--root DIR] [--launcher FILE] [--format text|json]

`generate` reads one YAML spec (its keys are described in the orchestrator-scaffold skill) and
writes, inside the toolbox checkout (--root, default the checkout this script sits in):

- <department>/agents/<name>.md, the orchestrator agent;
- <department>/agents/<worker>.md, one per new worker;
- <department>/skills/<skill>/SKILL.md, one per new skill;
- in the scripts/ folder of the skill that holds the work's commands (`done.skill`, default the
  first new skill): the check script `<domain>_check.py` with --precheck and --record, a stub
  per new command, and a test of the check in scripts/tests/.

The two agent kinds are filled from the skill's templates, `references/templates/orchestrator.md`
(the five stages A to E and the team) and `references/templates/sub-agent.md`, to the standard in
`references/agent-standard.md`.

The launcher's settings (schedule shipped disabled, the precheck, the form, the fixed folder
inputs, the Write and Edit rules) are printed, or written to --launcher FILE, which belongs
with the owner's private settings, never in the toolbox. Writing them needs every fixed input's
value through --set.

Every lint runs on the generated set first; one error writes nothing. A file that exists is
refused by name unless --update is given and the file still carries the scaffold's marker line.

`lint NAME` runs the same lints over an orchestrator that exists: its agent file, the agents its
team table names, the skills they load, and the launcher file when one is given.

Exit codes: 0 when it ran and found no error, 1 when a lint failed or a file was refused, 2 for a
bad spec, a bad argument or a missing file.

Example:
    python3 orchestrator_scaffold.py generate widget-review.spec.yaml --dry-run --show
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
from pathlib import Path

import yaml

DEFAULT_ROOT = Path(__file__).resolve().parents[4]
MARKER = "orchestrator-scaffold: generated"
MD_MARKER = f"<!-- {MARKER}; delete this line once the file is written by hand -->"
PY_MARKER = f"{MARKER}; delete this line once written by hand"
DESCRIPTION_LIMIT = 700
SHARED_SKILL = "orchestration-workstream"
SKILL_PATH = "~/.claude/skills/{skill}/scripts/{script}"

NAME_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)+-orchestrator$")
SLUG = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
PARAM = re.compile(r"^[a-z][a-z0-9_]*$")
WORK_RE = re.compile(r"^[A-Z][A-Z0-9]*(-[A-Z0-9]+)*$")
CRON_FIELD = re.compile(r"^[A-Za-z0-9*,/#-]+$")
MODELS = ("opus", "sonnet", "haiku", "fable")
KINDS = ("workstream", "reviewer", "keeper")
AUTHORITIES = ("dry-run-only", "propose", "trusted")
NETWORKS = ("online", "offline")
RESERVED = ("task", "contexts", "mode", "run_dir", "dry_run")
"""Launch inputs a launcher fills itself; a spec input may not take these names."""

FOLLOW_PHRASE = re.compile(r"\bfollow(?:s|ing)?\s+(?:the\s+)?[`'\"]?[a-z0-9][a-z0-9-]*[`'\"]?\s+skill\b", re.I)
INTERPRETERS = ("python", "python3", "node", "bash", "sh", "zsh", "perl", "ruby", "deno", "bun", "npx", "uv")
INTERPRETER_RULE = re.compile(
    r"^Bash\(\s*(?:" + "|".join(INTERPRETERS) + r"|python3\.\d+)(?:\s+(?:-[A-Za-z]+|run))*\s*(?::\s*\*|\*)?\s*\)$")
SHELL_COMMANDS = {"mkdir", "git", "ls", "cat", "find", "head", "tail", "wc", "diff", "sort", "test", "echo",
                  "date", "grep", "rg", "jq", "touch", "cp", "mv", "basename", "dirname", "gh"}
HOME_PATH = re.compile(r"(?:/home/|/Users/|/mnt/c/Users/)(?!<)[A-Za-z0-9._-]+")
PLACEHOLDER = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")


class SpecError(Exception):
    """The spec cannot be read or is malformed: exit 2."""


# ------------------------------------------------------------------------------- the spec

def _req(data, key, where="spec"):
    if data.get(key) in (None, "", [], {}):
        raise SpecError(f"{where}: `{key}` is required")
    return data[key]


def _words(value, where):
    if not isinstance(value, str) or not value.strip():
        raise SpecError(f"{where} must be words")
    return " ".join(value.split())


def _list(value, where):
    if value is None:
        return []
    if not isinstance(value, list):
        raise SpecError(f"{where} must be a list")
    return value


def _sentence(text):
    text = text.strip()
    return text if text.endswith((".", "!", "?")) else text + "."


def _lower_first(text):
    return text[:1].lower() + text[1:] if text[:2] != text[:2].upper() else text


def _commands(value, where):
    """prepare or finish: argv lists, or {argv, skip_on_dry_run}."""
    out = []
    for i, item in enumerate(_list(value, where), 1):
        if isinstance(item, list):
            item = {"argv": item}
        if not isinstance(item, dict) or not isinstance(item.get("argv"), list) or not item["argv"] \
                or not all(isinstance(a, str) for a in item["argv"]) or set(item) - {"argv", "skip_on_dry_run"}:
            raise SpecError(f"{where} {i}: an argv list of strings, or {{argv: [...], skip_on_dry_run: true}}")
        out.append({"argv": list(item["argv"]), "skip_on_dry_run": bool(item.get("skip_on_dry_run", False))})
    return out


def load_spec(path):
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SpecError(f"no spec at {path}") from None
    except (OSError, yaml.YAMLError) as exc:
        raise SpecError(f"{path}: {exc}") from None
    if not isinstance(raw, dict):
        raise SpecError(f"{path}: the top level must be a mapping")
    return normalise_spec(raw)


def normalise_spec(raw):
    """The spec with every default filled in, or SpecError naming what is wrong."""
    known = {"name", "domain", "department", "title", "purpose", "goal", "standard", "work", "periods", "inputs",
             "record", "workers", "skills", "tools", "done", "authority", "triggers", "prepare", "finish",
             "locks", "network", "limits", "not_for"}
    unknown = sorted(set(raw) - known)
    if unknown:
        raise SpecError(f"spec: unknown key {', '.join(unknown)}")
    s = {"name": str(_req(raw, "name"))}
    if not NAME_RE.match(s["name"]):
        raise SpecError(f"name '{s['name']}' is not kebab-case <domain>-<thing>-orchestrator")
    s["domain"] = str(_req(raw, "domain"))
    s["department"] = str(_req(raw, "department"))
    for key in ("domain", "department"):
        if not SLUG.match(s[key]):
            raise SpecError(f"{key} '{s[key]}' is not a kebab-case slug")
    s["title"] = _words(raw.get("title") or s["domain"].replace("-", " ").capitalize(), "title")
    s["purpose"] = _sentence(_words(_req(raw, "purpose"), "purpose"))
    s["goal"] = _sentence(_words(raw.get("goal") or s["purpose"], "goal"))
    s["standard"] = _sentence(_words(raw["standard"], "standard")) if raw.get("standard") else ""
    s["not_for"] = _sentence(_words(raw["not_for"], "not_for")) if raw.get("not_for") else ""
    s["work"] = str(raw.get("work") or s["domain"].upper())
    if not WORK_RE.match(s["work"]):
        raise SpecError(f"work '{s['work']}' must be capitals and hyphens (MONTH-END)")
    s["periods"] = bool(raw.get("periods", True))

    inputs = []
    for i, item in enumerate(_list(raw.get("inputs"), "inputs"), 1):
        item = {"name": item} if isinstance(item, str) else item
        if not isinstance(item, dict):
            raise SpecError(f"inputs {i}: a mapping with at least a name")
        name = str(_req(item, "name", f"inputs {i}"))
        if not PARAM.match(name):
            raise SpecError(f"inputs {i}: '{name}' is not a param name (lowercase, digits, _)")
        extra = sorted(set(item) - {"name", "label", "default", "required", "empty_means", "pattern", "description"})
        if extra:
            raise SpecError(f"inputs {name}: unknown key {', '.join(extra)}")
        if item.get("pattern") is not None:
            try:
                re.compile(str(item["pattern"]))
            except re.error as exc:
                raise SpecError(f"inputs {name}: pattern does not compile: {exc}") from None
        inputs.append({"name": name,
                       "label": _words(item.get("label") or name.replace("_", " ").capitalize(), f"inputs {name}"),
                       "default": item.get("default", ""), "required": bool(item.get("required", False)),
                       "empty_means": str(item.get("empty_means") or "not given"), "pattern": item.get("pattern"),
                       "description": _sentence(_words(item.get("description") or item.get("label") or name,
                                                       f"inputs {name}"))})
    names = [i["name"] for i in inputs]
    if len(set(names)) != len(names):
        raise SpecError("inputs: a param is named twice")
    s["inputs"] = inputs

    record = raw.get("record") or {}
    if not isinstance(record, dict):
        raise SpecError("record must be a mapping: system, folder, delivery")
    s["record"] = {"system": _words(_req(record, "system", "record"), "record system"), "folder": None,
                   "delivery": None}
    for key in ("folder", "delivery"):
        value = record.get(key)
        if value is None:
            continue
        if not isinstance(value, dict) or not PARAM.match(str(value.get("param", ""))):
            raise SpecError(f"record {key}: a mapping with a param name (and label, description)")
        if value["param"] in names:
            raise SpecError(f"record {key}: '{value['param']}' is a form input already; a folder is a fixed input")
        s["record"][key] = {"param": value["param"],
                            "label": _words(value.get("label") or value["param"].replace("_", " ").capitalize(),
                                            f"record {key} label"),
                            "description": _sentence(_words(value.get("description") or "the working folder",
                                                            f"record {key} description"))}
    fixed = [v["param"] for v in (s["record"]["folder"], s["record"]["delivery"]) if v]
    known_params = set(names) | set(fixed)

    skills = raw.get("skills") or {}
    if not isinstance(skills, dict):
        raise SpecError("skills must be a mapping: new, load")
    new_skills = []
    for i, item in enumerate(_list(skills.get("new"), "skills new"), 1):
        item = {"name": item} if isinstance(item, str) else item
        name = str(_req(item, "name", f"skills new {i}"))
        if not SLUG.match(name):
            raise SpecError(f"skills new {i}: '{name}' is not a kebab-case name")
        new_skills.append({"name": name,
                           "description": _sentence(_words(item.get("description") or f"The {name} method.",
                                                           f"skill {name} description")),
                           "workstream": bool(item.get("workstream", name.endswith("-workstream")))})
    s["skills"] = {"new": new_skills, "load": [str(x) for x in _list(skills.get("load"), "skills load")]}

    tools = raw.get("tools") or {}
    if not isinstance(tools, dict):
        raise SpecError("tools must be a mapping: existing, new")
    new_tools = []
    for i, item in enumerate(_list(tools.get("new"), "tools new"), 1):
        item = {"name": item} if isinstance(item, str) else item
        name = str(_req(item, "name", f"tools new {i}"))
        if not SLUG.match(name):
            raise SpecError(f"tools new {i}: '{name}' is not a kebab-case command")
        new_tools.append({"name": name, "description": _sentence(_words(
            item.get("description") or f"The {name} command.", f"tool {name} description"))})
    s["tools"] = {"existing": [str(x) for x in _list(tools.get("existing"), "tools existing")], "new": new_tools}

    done = raw.get("done") or {}
    if not isinstance(done, dict):
        raise SpecError("done must be a mapping: check, skill, scope, options, tests")
    check = str(done.get("check") or f"{s['domain']}-check")
    if not SLUG.match(check):
        raise SpecError(f"done check '{check}' is not a kebab-case command")
    scope = done.get("scope") or (s["record"]["folder"] or {}).get("param")
    options = [str(o) for o in _list(done.get("options"), "done options")]
    if s["periods"] and "period" not in options and "period" in names:
        options.insert(0, "period")
    for p in ([scope] if scope else []) + options:
        if p not in known_params:
            raise SpecError(f"done: '{p}' is neither an input nor the record folder")
    tests = []
    for i, item in enumerate(_list(done.get("tests"), "done tests"), 1):
        if isinstance(item, str):
            item = {"name": item.split(":")[0].strip(), "text": item.split(":", 1)[-1].strip()}
        if not isinstance(item, dict) or set(item) - {"name", "text"}:
            raise SpecError(f"done tests {i}: a mapping of name and text (a comma inside a flow mapping "
                            f"{{...}} starts a new key; write the test as a block)")
        name = str(_req(item, "name", f"done tests {i}")).lower().replace(" ", "-")
        if not SLUG.match(name):
            raise SpecError(f"done tests {i}: '{name}' is not a slug")
        tests.append({"name": name, "text": _sentence(_words(item.get("text") or name, f"done test {name}"))})
    if not tests:
        raise SpecError("done: `tests` is required, the tests of done the check computes")
    build = check not in s["tools"]["existing"]
    home = str(done.get("skill") or (new_skills[0]["name"] if new_skills else ""))
    if (build or new_tools) and not home:
        raise SpecError("done: `skill` is required to hold the check and the new commands when the spec "
                        "adds no new skill")
    s["done"] = {"check": check, "scope": scope, "options": options, "tests": tests, "build": build, "skill": home}

    workers = []
    for i, item in enumerate(_list(_req(raw, "workers"), "workers"), 1):
        if not isinstance(item, dict):
            raise SpecError(f"workers {i}: a mapping")
        if item.get("agent"):
            workers.append({"name": str(item["agent"]), "existing": True, "kind": str(item.get("kind") or "workstream"),
                            "role": _sentence(_words(item.get("role") or "See its agent file",
                                                     f"worker {item['agent']} role")),
                            "model": str(item.get("model") or "opus")})
            continue
        name = str(_req(item, "name", f"workers {i}"))
        if not SLUG.match(name):
            raise SpecError(f"workers {i}: '{name}' is not a kebab-case agent name")
        kind = str(item.get("kind") or "workstream")
        if kind not in KINDS:
            raise SpecError(f"worker {name}: kind '{kind}' is not one of {', '.join(KINDS)}")
        model = str(item.get("model") or ("sonnet" if kind == "keeper" else "opus"))
        if model not in MODELS:
            raise SpecError(f"worker {name}: model '{model}' is not one of {', '.join(MODELS)}")
        skill_list = [str(x) for x in _list(item.get("skills"), f"worker {name} skills")]
        if kind == "workstream" and SHARED_SKILL not in skill_list:
            skill_list.insert(0, SHARED_SKILL)
        workers.append({"name": name, "existing": False, "kind": kind, "model": model,
                        "role": _sentence(_words(_req(item, "role", f"worker {name}"), f"worker {name} role")),
                        "description": item.get("description"),
                        "not_for": _sentence(_words(item["not_for"], f"worker {name} not_for")) if item.get("not_for") else "",
                        "owns": _words(item["owns"], f"worker {name} owns") if item.get("owns") else "",
                        "skills": skill_list, "tools": [str(t) for t in _list(item.get("tools"), f"worker {name} tools")],
                        "color": {"workstream": "blue", "reviewer": "red", "keeper": "cyan"}[kind]})
    if len({w["name"] for w in workers}) != len(workers):
        raise SpecError("workers: an agent is named twice")
    s["workers"] = workers

    authority = raw.get("authority") or {}
    authority = {"level": authority} if isinstance(authority, str) else authority
    s["authority"] = {"level": str(authority.get("level") or "dry-run-only"),
                      "may": [_words(x, "authority may") for x in _list(authority.get("may"), "authority may")],
                      "may_not": [_words(x, "authority may_not")
                                  for x in _list(authority.get("may_not"), "authority may_not")]}
    if s["authority"]["level"] not in AUTHORITIES:
        raise SpecError(f"authority '{s['authority']['level']}' is not one of {', '.join(AUTHORITIES)}")
    triggers = raw.get("triggers") or {}
    if not isinstance(triggers, dict):
        raise SpecError("triggers must be a mapping")
    extra = sorted(set(triggers) - {"schedule", "tz", "precheck", "cadence", "events", "manual"})
    if extra:
        raise SpecError(f"triggers: unknown key {', '.join(extra)}")
    schedule = triggers.get("schedule")
    if schedule and (not isinstance(schedule, str) or len(schedule.split()) != 5
                     or not all(CRON_FIELD.match(f) for f in schedule.split())):
        raise SpecError(f"triggers: schedule '{schedule}' is not a five-field cron line")
    s["triggers"] = {"schedule": schedule, "tz": triggers.get("tz"),
                     "precheck": bool(triggers.get("precheck", bool(schedule))), "cadence": triggers.get("cadence"),
                     "events": list(triggers.get("events") or []), "manual": bool(triggers.get("manual", True))}
    s["prepare"] = _commands(raw.get("prepare"), "prepare")
    s["finish"] = _commands(raw.get("finish"), "finish")
    locks = raw.get("locks")
    locks = [str(x) for x in ([locks] if isinstance(locks, str) else _list(locks, "locks"))]
    if len(locks) > 1:
        raise SpecError("locks: name one input")
    for p in locks:
        if p not in known_params:
            raise SpecError(f"locks: '{p}' is neither an input nor the record folder")
    s["locks"] = locks
    s["network"] = str(raw.get("network") or "online")
    if s["network"] not in NETWORKS:
        raise SpecError(f"network '{s['network']}' is online or offline")
    limits = raw.get("limits") or {}
    s["limits"] = {"max_turns": int(limits.get("max_turns", 400)), "timeout_s": int(limits.get("timeout_s", 10800))}
    return s


# ------------------------------------------------------------------------------- the toolbox on disk

def script_name(command):
    return command.replace("-", "_") + ".py"


def find_script(root, command):
    """(skill, path) of the script a command names anywhere in the toolbox, or None."""
    hits = sorted(root.glob(f"*/skills/*/scripts/{script_name(command)}"))
    return (hits[0].parent.parent.name, hits[0]) if hits else None


def skill_dir(root, name):
    hits = sorted(p.parent for p in root.glob(f"*/skills/{name}/SKILL.md"))
    return hits[0] if hits else None


def skill_names(root):
    return {p.parent.name for p in root.glob("*/skills/*/SKILL.md")}


def find_agent(root, name):
    hits = sorted(root.glob(f"*/agents/{name}.md"))
    return hits[0] if hits else None


def has_marker(path):
    try:
        return MARKER in path.read_text(encoding="utf-8")
    except OSError:
        return False


def home_skill_dir(spec, root):
    """The skill folder that holds the check and the new commands."""
    name = spec["done"]["skill"]
    if name in {s["name"] for s in spec["skills"]["new"]}:
        return root / spec["department"] / "skills" / name
    found = skill_dir(root, name)
    if found is None:
        raise SpecError(f"done: skill '{name}' is neither a new skill nor a skill in the toolbox")
    return found


def command_path(spec, root, command):
    """The by-name path an agent runs a command at, or None when no script holds it."""
    generated = ([spec["done"]["check"]] if spec["done"]["build"] else []) + [t["name"] for t in spec["tools"]["new"]]
    if command in generated:
        return SKILL_PATH.format(skill=spec["done"]["skill"], script=script_name(command))
    found = find_script(root, command)
    return SKILL_PATH.format(skill=found[0], script=found[1].name) if found else None


def tool_rule(spec, root, tool):
    """A spec tool as an agent's tools entry: a command becomes the exact script rule."""
    tool = str(tool).strip()
    if not SLUG.match(tool):
        return tool
    path = command_path(spec, root, tool)
    return f"Bash(python3 {path}:*)" if path else f"Bash({tool}:*)"


def resolve_argv(spec, root, argv):
    """A launcher command with its command name replaced by the script that runs it."""
    path = command_path(spec, root, argv[0]) if SLUG.match(argv[0]) else None
    return ["python3", path] + argv[1:] if path else list(argv)


# ------------------------------------------------------------------------------- generated text

def _scalar(value):
    if value.startswith(("[", "{")):
        return value
    try:
        plain = yaml.safe_load(f"k: {value}") == {"k": value}
    except yaml.YAMLError:
        plain = False
    return value if plain else json.dumps(value)


def _frontmatter(fields):
    return "---\n" + "".join(f"{k}: {_scalar(v)}\n" for k, v in fields) + "---\n"


def _flow(items):
    return "[" + ", ".join(json.dumps(i) for i in items) + "]"


def all_params(spec):
    fixed = [v for v in (spec["record"]["folder"], spec["record"]["delivery"]) if v]
    return ([{"name": v["param"], "label": v["label"], "description": v["description"], "required": True,
              "fixed": True} for v in fixed] + [{**i, "fixed": False} for i in spec["inputs"]])


def orchestrator_tools(spec, root):
    tools = ["Read", "Glob", "Grep", "Write", "Edit", "Agent", "Skill", tool_rule(spec, root, spec["done"]["check"])]
    for name in spec["tools"]["existing"] + [t["name"] for t in spec["tools"]["new"]]:
        rule = tool_rule(spec, root, name)
        if rule not in tools:
            tools.append(rule)
    return tools + ["Bash(mkdir -p:*)"]


def worker_tools(spec, root, w):
    tools = ["Read", "Glob", "Grep", "Write"] + ([] if w["kind"] == "reviewer" else ["Edit"])
    for t in w["tools"]:
        rule = tool_rule(spec, root, t)
        if rule not in tools:
            tools.append(rule)
    if w["kind"] != "reviewer":
        tools.append("Bash(mkdir -p:*)")
    return tools


def orchestrator_description(spec):
    text = (f"Runs {_lower_first(spec['title'])} the way a lead runs a small team. {spec['purpose']} Reads the "
            f"working folder, works out what is done and what is open, dispatches the sub-agents and an "
            f"independent reviewer, and records every result so any session can resume. Start it as the main "
            f"session (claude --agent {spec['name']}) or through its Automation; dispatched as a sub-agent it "
            f"cannot dispatch its sub-agents.")
    return f"{text} {spec['not_for']}" if spec["not_for"] else text


def worker_description(spec, w):
    if w.get("description"):
        return _words(w["description"], f"worker {w['name']} description")
    tail = {"reviewer": "The independent reviewer. Give it the files and their sources only, never the maker's "
                        "reasoning; it returns PASS or FAIL per item with fixes and edits nothing it reviews.",
            "keeper": "It keeps the working folder (sets up a period, curates, records a learned fact with its "
                      "source), never touches the system of record and never deletes a file.",
            "workstream": "Brief it with the working folder, the period and the items assigned; it returns one "
                          "json block and writes no state."}[w["kind"]]
    not_for = w.get("not_for") or f"Not for a request on its own; start {spec['name']}."
    return f"{w['role']} Part of {spec['name']}. {tail} {not_for}"


TEMPLATES = Path(__file__).resolve().parent.parent / "references" / "templates"
SLOT = re.compile(r"\{\{([a-z_]+)\}\}")


def render(template, values):
    """A template from references/templates/ with every {{slot}} filled; a slot left over is a bug."""
    text = (TEMPLATES / template).read_text(encoding="utf-8")
    missing = sorted({m for m in SLOT.findall(text) if m not in values})
    if missing:
        raise SpecError(f"template {template}: no value for {', '.join(missing)}")
    return SLOT.sub(lambda m: values[m.group(1)], text)


def _bullets(items):
    return "\n".join(f"- {x}" for x in items)


GIVEN = {
    "workstream": ("The folder and the {unit}, its assigned rows and items, answers to its earlier questions, and the "
                   "reviewer's findings to fix"),
    "reviewer": "The work products and their sources only",
    "keeper": "The folder, the {unit} and the job: set up, curate, or record a learned fact with its source",
}
BOUNDS = {
    "workstream": "Writes no state, never edits a person's file, asks rather than guesses",
    "reviewer": "Never sees the builder's reasoning; edits nothing it reviews",
    "keeper": "Never touches the system of record, never deletes a file; a rules change is a proposal",
}
RETURNS = {
    "workstream": "A summary and the `orchestration-workstream` json block",
    "reviewer": "One review note per item, PASS or FAIL per item with fixes",
    "keeper": "A summary and the `orchestration-workstream` json block",
}
WHEN = {
    "workstream": "C, for each workstream with unblocked rows; again after a failed review",
    "reviewer": "D, for every new or changed work product; once more on `fable` for the sign-off",
    "keeper": "A, when the {unit} is not set up; E, to record a learned fact",
}


def _cell(text):
    return text.replace("|", "\\|")


def orchestrator_md(spec, root):
    W = spec["work"]
    label = spec["record"]["folder"]["label"] if spec["record"]["folder"] else "Run folder"
    check = f"python3 {command_path(spec, root, spec['done']['check']) or spec['done']['check']}"
    call = " ".join([check] + ([spec["done"]["scope"].upper()] if spec["done"]["scope"] else [])
                    + [f"--{o.replace('_', '-')} {o.upper()}" for o in spec["done"]["options"]])
    unit = "period" if spec["periods"] else "Run"
    system = spec["record"]["system"]
    reviewer = next((w["name"] for w in spec["workers"] if w["kind"] == "reviewer"), None)
    keeper = next((w["name"] for w in spec["workers"] if w["kind"] == "keeper"), None)
    builders = [w["name"] for w in spec["workers"] if w["kind"] == "workstream"]
    loads = spec["skills"]["load"] + [s["name"] for s in spec["skills"]["new"]]

    extra = [("color", "green")]
    goal = [f"{spec['goal']} You orchestrate: the sub-agents do the work, an independent reviewer checks it, and "
            f"you make sure nothing is missed, nothing is done twice, and every open question reaches a person."]
    if spec["standard"]:
        goal.append(spec["standard"])
    goal.append("Success is computed, never claimed: the check under Done when decides it from the evidence.")

    inputs = []
    for p in all_params(spec):
        need = "required" if p["required"] else "optional"
        default = "" if p["fixed"] or p["required"] else f" Default: {p['empty_means']}."
        inputs.append(f"- **{p['label']}** ({need}): {_lower_first(p['description'])}{default}")
    inputs.append(f"- **Dry run** (optional): gather and plan only. Read everything, then report what is done, what "
                  f"is open, what you would dispatch and what you would ask. Dispatch nothing, ask nothing and write "
                  f"nothing in the {label}.")
    inputs += ["", "If a required input is missing or its folder does not exist, end the session with `needs_owner` "
                   "naming it. A blank optional input takes its default; say which default you used in the report."]

    context = [f"The {label} is the working folder. Its root holds the standing documents; read all of them in "
               f"stage A of every session.", "", "| File | Holds |", "|---|---|",
               f"| `{W}-RULES.md` | Authority (what an agent may and may not do in each system), thresholds, "
               f"tolerances, naming, the definition of done. |",
               f"| `{W}-PROCEDURES.md` | The standing checklist: every task, its owner, due day, done-check and "
               f"sub-agent; and the inventory the work must cover. |",
               "| `BACKGROUND.md` | The people and their roles, the calendar. |",
               f"| `SYSTEMS.md` | {system[:1].upper() + system[1:]}: how data comes out, where inputs land, and the "
               f"delivery folder when finals go elsewhere. |",
               "| `STATUS.md` | The handoff: where it stands, what is waiting, the next action. |"]
    if spec["periods"]:
        context += ["", "Each period lives in `{yyyy}/{yyyy-mm}/`:", "", "| Path | Holds |", "|---|---|",
                    "| `STATUS.md` | One row per sub-agent (not started, in progress, waiting, done), and the "
                    "Waiting on table. |",
                    "| `LOG.md` | One dated entry per dispatch and per session. |",
                    f"| `{W}-PROCEDURES-{{yyyy-mm}}.md` | This period's copy of the checklist, with each row's status "
                    f"and evidence. |",
                    "| `CONFIRMATIONS.md` | Every question asked of a person, and the answer. |",
                    f"| `{W}-EVIDENCE-{{yyyy-mm}}.csv` | One row per item of work: its state, evidence, amount and "
                    f"review. Written only through the check's `--record`. |",
                    f"| `{W}-FINDINGS-{{yyyy-mm}}.md` | What is unusual, surprising or material, for the person "
                    f"who reports on it. |",
                    "| `work/source/` | The read-only pull from the system of record, with `pulled.md`. |"]
    context += ["", "When two sources disagree:", "",
                f"- `{W}-RULES.md` wins over everything, these instructions included.",
                "- A person's file or answer wins over an agent's draft; theirs is never edited.",
                f"- The pull from {system} wins over a summary, a memory or an earlier session's note. A stale pull "
                f"is said in the report, never patched.",
                "- The check's output wins over your own reading of done."]
    context += ["", "A skill named here may not be loaded as a tool in your session. If not, read it at "
                    "`~/.claude/skills/<name>/SKILL.md` and tell each sub-agent to do the same."]
    if loads:
        context += ["", "Skills this work uses: " + ", ".join(f"`{n}`" for n in loads) + "."]

    facts = ("When the Automation launches you it has already refreshed the data: the inputs carry each prepare "
             "command's first line (`FRESH ...` or `STALE ...`), and STALE means you work from the older data and "
             "say so." if spec["prepare"] else
             "Read the date of the last pull in `work/source/pulled.md`; refresh it with the pull tool when the "
             "system has changed since, and say how old the data is.")
    gather_who = "You, with the check" + (f"; `{keeper}` sets up a {unit} that is not set up yet." if keeper else ".")
    review_who = (f"`{reviewer}`, independent of the builders: it gets the work products and their sources only, "
                  f"never the builder's reasoning, and edits nothing it reviews." if reviewer else
                  "An agent that did not make the work (`general-purpose`, briefed with the files and their sources "
                  "only, never the builder's reasoning).")
    signoff = (f" When the check shows every test met, dispatch `{reviewer}` once more, with model `fable`, for the "
               f"sign-off." if reviewer else "")
    stages = {
        "gather_goal": (f"Know where the {unit} stands before deciding anything. Read the standing documents, the "
                        f"{unit}'s `STATUS.md`, the last entries of `LOG.md`, `CONFIRMATIONS.md` and the procedures "
                        f"copy, and run the check. Each answered question is input to this session. Get the facts "
                        f"from {system}: {_lower_first(facts)}"),
        "gather_who": gather_who,
        "gather_exit": "the check has run, every answered question is noted, and you know how old the data is.",
        "plan_goal": ("List the open rows by sub-agent; mark what is blocked on a person or an input and what is "
                      "due. Plan only unblocked work, and never redo what a person already did. Collect every "
                      "question this stage finds, and any a sub-agent or the reviewer returned, and ask them as "
                      "one batch: only what the folder, earlier periods and the system cannot answer, one question "
                      "per item, through `comms-confirm`, each recorded in `CONFIRMATIONS.md` and the Waiting on "
                      "table. Then move on; the session never waits for an answer and never builds on an "
                      "assumption about a missing input."),
        "plan_who": "You; `comms-confirm` carries the questions to the owner's task list.",
        "plan_exit": ("every open row has a sub-agent, a person or a recorded question, and this round's questions "
                      "have gone out as one batch."),
        "build_goal": ("The work products for every planned row. Write a `LOG.md` line and set the sub-agent's "
                       "`STATUS.md` row to in progress before each dispatch; run independent sub-agents in "
                       "parallel. Record each json block the moment it returns, field by field: `items` with the "
                       "check's `--record`, `rows` in the procedures copy, `findings` in the findings file, "
                       "`proposals` to the keeper, and `questions` held for the next batch in B. Never batch the "
                       "records: the next session resumes from them."),
        "build_who": (", ".join(f"`{n}`" for n in builders) + ", as the team table says." if builders else
                      "The sub-agents in the team table."),
        "build_exit": "every dispatched sub-agent has returned its json block and the block is recorded.",
        "review_goal": (f"Only reviewed work counts toward done. Send every new or changed work product for review. "
                        f"A FAIL returns to B with the reviewer's findings, to be re-planned and rebuilt; after two "
                        f"failed rounds on one item it becomes a question for the owner.{signoff}"),
        "review_who": review_who,
        "review_exit": ("every new or changed work product has a PASS, or its second failure is a recorded "
                        "question; and, when the check shows every test met, the sign-off has passed."),
        "deliver_goal": (f"Leave the {unit} so any session can resume and a person can act. Update the {unit}'s "
                         f"`STATUS.md` and the root `STATUS.md` (where it stands, what waits on whom, the next "
                         f"action with its date), add anything unusual to the findings file, write the session's "
                         f"`LOG.md` entry, and run the check last. Nothing is sent or posted without a person: "
                         f"finished work stays in the folder for them, and a write to a system happens only "
                         f"through the finish step's tool."),
        "deliver_who": "You" + (f"; `{keeper}` records a learned fact in the right standing document." if keeper
                                else "."),
        "deliver_exit": "the check has run last and its result is in the report.",
    }

    rows = []
    for w in spec["workers"]:
        kind = w["kind"]
        model = w["model"] if kind != "reviewer" else f"{w['model']} per item; fable for the sign-off"
        rows.append("| " + " | ".join(_cell(x) for x in (
            f"`{w['name']}`", w["role"].rstrip("."), GIVEN[kind].format(unit=unit), BOUNDS[kind], RETURNS[kind],
            WHEN[kind].format(unit=unit), model)) + " |")
    team = ["| Sub-agent | Objective | Given | Boundaries | Returns | Dispatched | Model |",
            "|---|---|---|---|---|---|---|", *rows, "",
            "Brief a sub-agent with what its row says it is given and nothing of your own reasoning about the "
            "answer. A reply without its return block goes back once for it. Sub-agents cannot dispatch "
            "sub-agents and write no state.", "",
            "A checklist row with no sub-agent stays with its named owner; track it like any other row. For work "
            "no sub-agent owns (a one-off investigation, bulk reading), dispatch `general-purpose` with the "
            "question at hand: model `fable` for a hard judgment, `sonnet` for reading a lot, `opus` otherwise."]

    never = ["Send, post or contact anyone; a person does, from what you leave in the folder.",
             "Change a system except through the deterministic tool built for that change.",
             "Write `STATUS.md`, `LOG.md`, the procedures copy or the evidence file through anyone but yourself; "
             "you are their only writer.",
             "Edit a person's file, or read, print or write a credential.",
             "Chain commands: one command per call, with no pipes, redirects, `&&` or variables, and a skill's "
             "script by its full path."] + [_sentence(x[:1].upper() + x[1:]) for x in spec["authority"]["may_not"]]
    bounds = [f"`{W}-RULES.md` in the {label} says what an agent may do in each system; keep to it over anything "
              f"here."]
    if spec["authority"]["may"]:
        bounds += ["", "Within it, you may " + "; ".join(spec["authority"]["may"]) + "."]
    bounds += ["", "**Never**", "", _bullets(never), "", "**Ask or escalate**", "",
               _bullets(["A question goes in B's batch through `comms-confirm`; when no one is present it waits on "
                         "the owner's task list, and the session ends with the Waiting on rows the next session "
                         "needs.",
                         "A decision only the owner can make, that blocks every remaining task, ends the session "
                         "with `needs_owner`."]),
               "", "**Not your job**", "",
               _bullets(["The work itself: the sub-agents build it.",
                         "Checking your own team's work: the reviewer does.",
                         f"Changing `{W}-RULES.md`: the owner does; propose the change in the root `STATUS.md`."])]
    if spec["network"] == "offline":
        bounds += ["", "This session is offline: it has no route to the system of record. Everything the system "
                       "said is in the data prepared before you started; what you write for it is applied after "
                       "you finish, by the launcher's finish step."]

    done = [f"The work is done when every test below holds, each with its evidence in the {unit} folder:", ""]
    done += [f"{n}. **{t['name'].replace('-', ' ').capitalize()}.** {t['text']}"
             for n, t in enumerate(spec["done"]["tests"], 1)]
    done += ["", f"`{call} --format json` computes every test from the folder and the system of record, so done is "
                 f"never your opinion. Run it in A to see what is open and last in E to report where the work "
                 f"stands. `--precheck` is the scheduler's: its first line is `WORK:` or `NOTHING:`. Record an "
                 f"item with the same command and `--record TEST:ITEM --state STATE` (`--evidence`, `--review`, "
                 f"`--note` as they apply). The session's finish line is the check saying every test is met and "
                 f"the sign-off passing; otherwise it ends with what is open and why."]

    output = ["End with a report for a person, in this order:", "",
              "1. The check's result line.",
              "2. What changed this session: files written and items recorded.",
              "3. The Waiting on rows: question, asked of, since when.",
              "4. The next action and its date.",
              "5. The model each dispatch ran on.", "",
              "Then one status word on its own line: `done` (every test met and the sign-off passed), `waiting` "
              "(open items wait on people) or `needs_owner` (a decision only the owner can make blocks the rest). "
              "On a dry run the report is the plan: what is done, what is open, what you would dispatch and ask."]

    values = {"name": spec["name"], "description": _scalar(orchestrator_description(spec)),
              "tools": _flow(orchestrator_tools(spec, root)), "model": "opus",
              "frontmatter_extra": "".join(f"{k}: {v}\n" for k, v in extra), "marker": MD_MARKER,
              "owns": f"You own {_lower_first(spec['title'])}, start to finish, one {unit} at a time.",
              "goal": "\n\n".join(goal), "inputs": "\n".join(inputs), "context": "\n".join(context),
              "team": "\n".join(team), "boundaries": "\n".join(bounds), "done": "\n".join(done),
              "output": "\n".join(output), **stages}
    return render("orchestrator.md", values)


def worker_md(spec, root, w):
    W, kind, orch = spec["work"], w["kind"], spec["name"]
    unit = "period" if spec["periods"] else "Run"
    extra = [("color", w["color"])] + ([("skills", "[" + ", ".join(w["skills"]) + "]")] if w["skills"] else [])
    owns = {"workstream": w["owns"] or "the rows and items your brief assigns",
            "reviewer": w["owns"] or "the independent review of every work product",
            "keeper": w["owns"] or "the working folder's upkeep"}[kind]
    success = {
        "workstream": (f"Success is every assigned item finished to the standard in `{W}-RULES.md`, with evidence a "
                       f"reviewer can check, or proved already done by a person, so `{orch}` can record it line by "
                       f"line."),
        "reviewer": ("Success is a verdict per item that someone who never met the maker could defend from the "
                     "sources alone. Only reviewed work counts toward done, so a soft review lets an error through "
                     "and a vague one costs a round."),
        "keeper": ("Success is a folder any session can resume from: each period set up before its work starts, "
                   "tidy, and every learned fact in the right standing document with its source."),
    }[kind]
    given = {
        "workstream": [f"The working folder and the {unit}.", "The rows and items assigned to you.",
                       "Answers to your earlier questions, and the reviewer's findings when a review failed."],
        "reviewer": ["The work products to review and their sources (the pull, statements, people's files).",
                     "The rules file's path. Never the maker's reasoning; if a brief carries it, ignore it."],
        "keeper": [f"The working folder and the {unit}.",
                   "The job: set up a period, curate, or record a learned fact (with the fact and its source)."],
    }[kind]
    context = [f"Read `{W}-RULES.md` in the working folder first: it says what you may do and the thresholds you "
               f"work to."]
    if kind == "workstream":
        domain = [s for s in w["skills"] if s != SHARED_SKILL]
        extra_skills = f" and then {', '.join(f'`{s}`' for s in domain)}" if domain else ""
        context += [""]
        context.append(f"Load `{SHARED_SKILL}` first{extra_skills}: the conduct every workstream shares and the one "
                       f"return block. Read each at `~/.claude/skills/<name>/SKILL.md` if it is not loaded.")
    elif w["skills"]:
        context += [""]
        context.append("Read " + ", ".join(f"`{s}`" for s in w["skills"]) + " at `~/.claude/skills/<name>/SKILL.md` "
                       "if it is not loaded.")
    context += ["", "When two sources disagree, the rules file wins over any skill, a domain skill wins over "
                    f"`{SHARED_SKILL}`, and the sources themselves win over the brief's summary of them."]
    approach = {
        "workstream": ["Check every item before doing it: a person may have done it already. Record their "
                       "evidence and move on.",
                       "What good looks like in this area, item by item, and how you prove it, is the domain "
                       "skill's standard; meet it, and say where an item cannot.",
                       "An estimate, a missing input or a judgment that is not yours is a question for a named role, "
                       "never a guess."],
        "reviewer": ["Re-derive every figure and check every claim against the sources, not against the maker's "
                     "summary.",
                     "Each FAIL names the fix it needs, specific enough to act on without asking you.",
                     "Asked for the sign-off, check every test of done against the evidence file and say which "
                     "holds and which does not."],
        "keeper": ["Set up a period: the folders, the procedures copy with dates, STATUS, LOG, the findings file, "
                   "open items carried forward; never overwriting a file that exists.",
                   "Curate: links, stale questions, long logs.",
                   "Record a learned fact in the standing document it belongs in, with its source."],
    }[kind]
    if w["skills"]:
        approach.append("Skills: " + ", ".join(f"`{s}`" for s in w["skills"]) + ".")
    never = {
        "workstream": ["Write state: `STATUS.md`, `LOG.md`, the procedures copy and the evidence file are the "
                       "orchestrator's.",
                       "Edit, move or delete a person's file; write your own beside it."],
        "reviewer": ["Edit anything you review.", "Read the maker's reasoning or notes."],
        "keeper": ["Touch the system of record.", "Delete a file or overwrite one that exists."],
    }[kind] + ["Read, print or write a credential.",
               "Chain commands: one command per call, and a skill's script by its full path."]
    ask = {
        "workstream": "Return a question, with the role it is for and what it blocks, whenever the rules or the "
                      "sources do not settle an item.",
        "reviewer": "Say when the sources are not enough to judge an item; that is a FAIL with the missing source "
                    "named, never a PASS.",
        "keeper": f"A change to `{W}-RULES.md` is a proposal for the owner, never an edit.",
    }[kind]
    not_job = {"workstream": "Reviewing your own work, and any row not in your brief.",
               "reviewer": "Fixing what fails: the maker does, from your findings.",
               "keeper": "The work itself and its review."}[kind]
    done = {
        "workstream": "Every assigned item is finished with evidence, proved done by a person, or held by a "
                      "question; and the json block lists each one.",
        "reviewer": "Every item has a verdict and a review note, and every FAIL names its fix.",
        "keeper": "The job asked for is done, every file it touched is listed, and nothing was overwritten.",
    }[kind]
    output = (("Write one review note per item in the folder, then end with a short summary for a person and "
               f"exactly one fenced `json` block in the shape the `{SHARED_SKILL}` skill gives, each item's `state` "
               "PASS or FAIL and its `note` the fixes.") if kind == "reviewer" else
              ("End with a short summary for a person, then exactly one fenced `json` block in the shape the "
               f"`{SHARED_SKILL}` skill gives. Every field is present; a list may be empty."))
    values = {"name": w["name"], "description": _scalar(worker_description(spec, w)),
              "tools": _flow(worker_tools(spec, root, w)), "model": w["model"],
              "frontmatter_extra": "".join(f"{k}: {v}\n" for k, v in extra), "marker": MD_MARKER,
              "owns": f"You own {_lower_first(owns).rstrip('.')} for `{orch}`.",
              "goal": f"{w['role']} {success}", "inputs": "\n".join(
                  [_bullets(given), "", "If something you need is missing, do not fill the gap: return a question "
                                        "for the role who can supply it, with what it blocks, and work the rest."]),
              "context": "\n".join(context), "approach": _bullets(approach),
              "boundaries": "\n".join(["**Never**", "", _bullets(never), "", "**Ask or escalate**", "", f"- {ask}",
                                       "", "**Not your job**", "", f"- {not_job}"]),
              "done": done, "output": output}
    return render("sub-agent.md", values)


def skill_md(spec, sk):
    out = [_frontmatter([("name", sk["name"]), ("description", sk["description"])]), MD_MARKER, "",
           f"# {sk['name'].replace('-', ' ').capitalize()}", ""]
    if sk["workstream"]:
        out += [f"This skill extends `{SHARED_SKILL}`: keep its conduct and return its block. Read it at "
                f"`~/.claude/skills/{SHARED_SKILL}/SKILL.md` if it is not loaded. What follows is only what "
                f"{_lower_first(spec['title'])} adds.", "", "## Conduct here", "",
                f"- **Read the rules first.** `{spec['work']}-RULES.md` says what you may do and the thresholds you "
                f"work to. It overrides your own instructions.",
                "- **Already done?** How to tell, item by item, from the folder and the system of record.",
                "- **No bookkeeping.** The state you never write: STATUS.md, LOG.md, the procedures copy and the "
                "evidence file.", "", "## The return here", "",
                "The shared block, with the item tests and states the check's `--record` accepts:", "",
                "| Test | States |", "|---|---|"]
        out += [f"| `{t['name']}` | open, in-progress, waiting, done |" for t in spec["done"]["tests"]]
    else:
        out += [f"Load `{SHARED_SKILL}` first (`~/.claude/skills/{SHARED_SKILL}/SKILL.md`) for the conduct and the "
                f"return block; this skill is the method and the standard for one kind of work.", "",
                "## The standard", "", "What good looks like, the checks a professional makes.", "",
                "## The work", "", "How it is done, and which tool does what must be exact.", "",
                "## The file", "", "What it produces, where, and how it is named."]
    return "\n".join(out + [""])


CHECK_TEMPLATE = '''"""`__CMD__`: whether __TITLE__ is done, computed from its evidence file.

__MARKER__

Inputs: SCOPE, __SCOPE_WORDS__; __OPTION_WORDS__--as-of yyyy-mm-dd; --format text|json; --precheck.
Each test of done is met when the evidence file (`__EVIDENCE__`) has at least one row for it and
every row for it is `done` with a PASS review. --precheck prints one line for a scheduler,
`WORK: <reason>` or `NOTHING: <reason>`. An option left blank on a launch form (`--period=`)
means not given.

--record TEST:ITEM with --state, --evidence, --amount, --review, --review-file, --note writes one
evidence row: fields not given keep their value, no row is ever deleted, and a change to the
state, evidence or amount without a new review clears the review.

SCAFFOLD: the generated skeleton. Replace each test with the domain's own computation from the
folder and the system of record, keep the result's shape, and delete this paragraph.

Exit 0 whenever it ran, whatever it found; 2 on a bad argument or a missing scope.

Example:
    python3 __SCRIPT__ ~/work/folder --format json
"""

import argparse
import csv
import io
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

COLUMNS = ("id", "test", "item", "state", "evidence", "amount", "review", "review_file", "note", "updated_at", "by")
STATES = ("open", "in-progress", "waiting", "done")
WORK_FIELDS = ("state", "evidence", "amount")
TESTS = __TESTS__
OPTIONS = __OPTIONS__
WORK = "__WORK__"
PERIODS = __PERIODS__


class Bad(Exception):
    """A bad argument or a missing scope: exit 2."""


def evidence_path(scope, period):
    """The period's evidence file (the latest period when none is given), or the root one."""
    if not PERIODS:
        return scope / f"{WORK}-EVIDENCE.csv"
    if not period:
        months = sorted(p for p in scope.glob("[0-9][0-9][0-9][0-9]/[0-9][0-9][0-9][0-9]-[0-9][0-9]") if p.is_dir())
        if not months:
            return None
        period = months[-1].name
    return scope / period[:4] / period / f"{WORK}-EVIDENCE-{period}.csv"


def read_rows(path):
    if path is None or not path.is_file():
        return []
    text = path.read_text(encoding="utf-8").lstrip("\\ufeff")   # a byte-order mark is not part of the header
    return list(csv.DictReader(io.StringIO(text, newline="")))


def record(path, test, item, by="", **fields):
    """Upsert the row <test>:<item>; fields not given keep their recorded value."""
    if test not in TESTS:
        raise Bad(f"test '{test}' is not one of {', '.join(TESTS)}")
    if fields.get("state") is not None and fields["state"] not in STATES:
        raise Bad(f"state '{fields['state']}' is not one of {', '.join(STATES)}")
    rows = read_rows(path)
    key = f"{test}:{item}"
    row = next((r for r in rows if r.get("id") == key), None)
    if row is None:
        row = {c: "" for c in COLUMNS}
        row.update(id=key, test=test, item=item)
        rows.append(row)
    given = {k: v for k, v in fields.items() if v is not None}
    if any(k in WORK_FIELDS and v != row.get(k, "") for k, v in given.items()) and "review" not in given:
        row["review"], row["review_file"] = "", ""   # a review never outlives the work it passed
    row.update(given)
    row["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    row["by"] = by or row.get("by", "")
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=COLUMNS, extrasaction="ignore", lineterminator="\\n")
    writer.writeheader()
    writer.writerows(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    tmp.write_text(out.getvalue(), encoding="utf-8")
    os.replace(tmp, path)
    return row


def check(scope, period=None, as_of=None, **options):
    root = Path(scope).expanduser()
    if not root.is_dir():
        raise Bad(f"no folder {root}")
    path = evidence_path(root, period)
    rows = read_rows(path)
    tests = {}
    for name in TESTS:
        mine = [r for r in rows if r.get("test") == name]
        gaps = [f"{r['item']}: {r.get('state') or 'no state'}" + ("" if r.get("review") == "PASS" else ", not reviewed")
                for r in mine if not (r.get("state") == "done" and r.get("review") == "PASS")]
        if not mine:
            gaps.append("no evidence rows yet")
        tests[name] = {"met": not gaps, "rows": len(mine), "gaps": gaps}
    met = sum(1 for t in tests.values() if t["met"])
    return {"scope": str(root), "period": period, "evidence": str(path) if path else None,
            "as_of": as_of or date.today().isoformat(), "options": options,
            "tests": tests, "met": met, "of": len(TESTS), "done": met == len(TESTS)}


def precheck_line(result):
    if result["done"]:
        return f"NOTHING: every test of done met ({result['of']} of {result['of']})"
    open_tests = [name for name, t in result["tests"].items() if not t["met"]]
    return f"WORK: {len(open_tests)} of {result['of']} tests of done open ({', '.join(open_tests)})"


def render(result):
    out = [f"__CMD__ {result['scope']}" + (f" {result['period']}" if result.get("period") else ""),
           f"{'DONE' if result['done'] else 'NOT DONE'} ({result['met']} of {result['of']} tests met)"]
    for number, (name, test) in enumerate(result["tests"].items(), start=1):
        out.append(f"{number} {name}: {'MET' if test['met'] else 'NOT MET'} ({test['rows']} row(s))")
        out += [f"  - {gap}" for gap in test["gaps"]]
    return "\\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="__CMD__", description="Whether __TITLE__ is done, test by test.")
    parser.add_argument("scope", nargs="?", default="", help="__SCOPE_WORDS__")
    for option in OPTIONS:
        parser.add_argument("--" + option.replace("_", "-"), dest=option, default="", help="blank: not given")
    parser.add_argument("--as-of", default="", help="judge as of this date (yyyy-mm-dd); blank: today")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--precheck", action="store_true", help="one line, WORK: or NOTHING:, for a scheduler")
    parser.add_argument("--record", metavar="TEST:ITEM", help="write one evidence row instead of checking")
    for field in ("state", "evidence", "amount", "review", "review-file", "note", "by"):
        parser.add_argument("--" + field, default=None)
    args = parser.parse_args(argv)
    given = {o: (getattr(args, o) or "").strip() or None for o in OPTIONS}
    as_of = (args.as_of or "").strip() or None
    try:
        if not args.scope.strip():
            raise Bad("SCOPE is required: __SCOPE_WORDS__")
        if as_of:
            date.fromisoformat(as_of)
        if args.record:
            test, _, item = args.record.partition(":")
            if not item:
                raise Bad("--record takes TEST:ITEM")
            if PERIODS and not given.get("period"):
                raise Bad("--record needs --period")
            path = evidence_path(Path(args.scope).expanduser(), given.get("period"))
            row = record(path, test, item, by=args.by or "", state=args.state, evidence=args.evidence,
                         amount=args.amount, review=args.review, review_file=args.review_file, note=args.note)
            print(json.dumps(row, indent=1) if args.format == "json" else f"recorded {row['id']}: {row['state']}")
            return 0
        result = check(args.scope, as_of=as_of, **given)
    except (Bad, ValueError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    if args.precheck:
        print(precheck_line(result))
    elif args.format == "json":
        print(json.dumps(result, indent=1))
    else:
        print(render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def check_py(spec):
    scope = spec["done"]["scope"]
    scope_words = (next(p["description"].rstrip(".") for p in all_params(spec) if p["name"] == scope).lower()
                   if scope else "the working folder")
    options = spec["done"]["options"]
    option_words = "".join(f"--{o.replace('_', '-')} ({o}); " for o in options)
    evidence = (f"{{yyyy}}/{{yyyy-mm}}/{spec['work']}-EVIDENCE-{{yyyy-mm}}.csv" if spec["periods"]
                else f"{spec['work']}-EVIDENCE.csv")
    text = CHECK_TEMPLATE
    for token, value in (("__CMD__", spec["done"]["check"]), ("__TITLE__", _lower_first(spec["title"])),
                         ("__MARKER__", PY_MARKER), ("__SCOPE_WORDS__", scope_words),
                         ("__OPTION_WORDS__", option_words), ("__EVIDENCE__", evidence),
                         ("__SCRIPT__", script_name(spec["done"]["check"])),
                         ("__TESTS__", "(" + ", ".join(json.dumps(t["name"]) for t in spec["done"]["tests"]) + ",)"),
                         ("__OPTIONS__", "(" + "".join(json.dumps(o) + ", " for o in options) + ")"),
                         ("__WORK__", spec["work"]), ("__PERIODS__", str(spec["periods"]))):
        text = text.replace(token, value)
    return text


STUB_TEMPLATE = '''"""`__CMD__`: __DESCRIPTION__

__MARKER__

SCAFFOLD: a stub. Build the command here: its settings from the working folder, read-only toward
a system of record unless it is the one controlled writer, never overwriting, `--format json`
for agents. Until then it refuses with exit 2.

Example:
    python3 __SCRIPT__ --help
"""

import argparse
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(prog="__CMD__", description="__DESCRIPTION__")
    parser.add_argument("args", nargs="*")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.parse_args(argv)
    print("ERROR __CMD__ is not built yet (an orchestrator-scaffold stub)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
'''


def stub_py(tool):
    return (STUB_TEMPLATE.replace("__CMD__", tool["name"]).replace("__DESCRIPTION__", tool["description"])
            .replace("__MARKER__", PY_MARKER).replace("__SCRIPT__", script_name(tool["name"])))


def test_py(spec):
    check, first = script_name(spec["done"]["check"]), spec["done"]["tests"][0]["name"]
    blank = " ".join(f'"--{o.replace("_", "-")}=",' for o in spec["done"]["options"])
    period_args = '"--period", "2026-09", ' if spec["periods"] else ""
    stubs = "".join(
        f'\n\ndef test_{t["name"].replace("-", "_")}_is_a_stub_that_refuses_until_built():\n'
        f'    res = subprocess.run([sys.executable, str(HERE.parent / "{script_name(t["name"])}")],\n'
        f'                         capture_output=True, text=True)\n'
        f'    assert res.returncode == 2 and "not built" in res.stderr\n'
        for t in spec["tools"]["new"])
    return f'''"""`{spec["done"]["check"]}` against a made-up company (Acme Components).

{PY_MARKER}

SCAFFOLD: the generated skeleton. Add the domain's tests of done as the check grows.
"""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECK = HERE.parent / "{check}"
sys.path.insert(0, str(HERE.parent))
import {check[:-3]} as chk  # noqa: E402

TESTS = list(chk.TESTS)


def run(*args):
    return subprocess.run([sys.executable, str(CHECK), *args], capture_output=True, text=True)


def record(folder, test, item, review="PASS"):
    res = run(str(folder), "--record", f"{{test}}:{{item}}", {period_args}"--state", "done",
              "--evidence", f"{{item}}.md", "--review", review)
    assert res.returncode == 0, res.stderr


def test_precheck_says_work_when_nothing_is_recorded(tmp_path):
    res = run(str(tmp_path), "--precheck")
    assert res.returncode == 0, res.stderr
    assert res.stdout.startswith("WORK: ")


def test_precheck_says_nothing_when_every_test_is_met(tmp_path):
    for test in TESTS:
        record(tmp_path, test, "acme-1")
    res = run(str(tmp_path), "--precheck")
    assert res.returncode == 0, res.stderr
    assert res.stdout.startswith("NOTHING: ")


def test_an_unreviewed_row_does_not_count(tmp_path):
    for test in TESTS:
        record(tmp_path, test, "acme-1")
    record(tmp_path, "{first}", "acme-2", review="")
    result = json.loads(run(str(tmp_path), "--format", "json").stdout)
    assert result["done"] is False and result["tests"]["{first}"]["met"] is False


def test_json_reports_every_test(tmp_path):
    record(tmp_path, "{first}", "acme-1")
    result = json.loads(run(str(tmp_path), "--format", "json").stdout)
    assert list(result["tests"]) == TESTS and result["tests"]["{first}"]["met"] is True


def test_a_missing_scope_is_exit_2(tmp_path):
    assert run().returncode == 2
    assert run(str(tmp_path / "nowhere")).returncode == 2
    assert run(str(tmp_path), "--as-of", "someday").returncode == 2


def test_a_blank_option_from_the_launch_form_means_not_given(tmp_path):
    res = run(str(tmp_path), {blank} "--as-of=", "--precheck")
    assert res.returncode == 0, res.stderr
    assert res.stdout.startswith(("WORK: ", "NOTHING: "))
{stubs}'''


# ------------------------------------------------------------------------------- the launcher

def _abs_rule(tool, path):
    path = path.rstrip("/")
    return f"{tool}(/{path}/**)" if path.startswith("/") else f"{tool}({path}/**)"


def launcher(spec, root, values):
    """The launcher's settings as data. Fixed inputs without a value show as <param>."""
    fixed_params = [v["param"] for v in (spec["record"]["folder"], spec["record"]["delivery"]) if v]
    fixed = {p: values.get(p, f"<{p}>") for p in fixed_params}
    out = {"title": spec["title"], "agent": spec["name"]}
    trig = spec["triggers"]
    if trig["schedule"]:
        out["schedule"] = trig["schedule"]
        if trig["tz"]:
            out["tz"] = trig["tz"]
        out["enabled"] = False
        if trig["precheck"]:
            scope = spec["done"]["scope"]
            argv = resolve_argv(spec, root, [spec["done"]["check"]])
            if scope:
                argv.append(fixed.get(scope, "{" + scope + "}"))
            out["precheck"] = argv + ["--precheck"]
    if spec["prepare"]:
        out["prepare"] = [{**c, "argv": resolve_argv(spec, root, c["argv"])} for c in spec["prepare"]]
    if spec["finish"]:
        out["finish"] = [{**c, "argv": resolve_argv(spec, root, c["argv"])} for c in spec["finish"]]
    if fixed:
        out["inputs"] = fixed
    own = set(orchestrator_tools(spec, root))
    rules = [_abs_rule(t, v) for v in fixed.values() for t in ("Write", "Edit")]
    for w in spec["workers"]:
        for rule in (worker_tools(spec, root, w) if not w["existing"] else []):
            if rule.startswith("Bash(") and rule not in own and rule not in rules:
                rules.append(rule)
    if rules:
        out["allowed-tools"] = rules
    if spec["locks"]:
        out["concurrency"] = {"key": spec["locks"][0]}
    out["network"] = spec["network"]
    out["limits"] = dict(spec["limits"])
    out["form"] = {"params": {**{i["name"]: i["default"] for i in spec["inputs"]}, "dry_run": False},
                   "labels": {**{i["name"]: i["label"] for i in spec["inputs"]}, "dry_run": "Dry run"},
                   "empty_means": {i["name"]: i["empty_means"] for i in spec["inputs"] if not i["required"]}}
    return out


def launcher_yaml(spec, root, values):
    head = (f"# {MARKER}; delete this line once the file is written by hand\n"
            f"# The launcher settings for {spec['name']}: owner-specific values live here, never in the toolbox.\n")
    if spec["triggers"]["schedule"]:
        head += "# The schedule ships disabled until one live period has run.\n"
    return head + yaml.safe_dump(launcher(spec, root, values), sort_keys=False, allow_unicode=True, width=100)


# ------------------------------------------------------------------------------- lints

def split_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    parts = text.split("\n---", 1)
    if len(parts) < 2:
        return {}, text
    try:
        meta = yaml.safe_load(parts[0][3:]) or {}
    except yaml.YAMLError:
        meta = {}
    return (meta if isinstance(meta, dict) else {}), parts[1].split("\n", 1)[-1]


def as_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [v.strip() for v in re.split(r"[,\n]", value.strip("[] ")) if v.strip()]
    return [str(v) for v in value]


def rule_argv(rule):
    """The words of a `Bash(...)` rule before its wildcard, or None for a non-Bash rule."""
    m = re.match(r"^Bash\((.*)\)$", rule.strip())
    if not m:
        return None
    inner = re.sub(r"\s*(?::\s*\*|\*)\s*$", "", m.group(1)).strip()
    try:
        return shlex.split(inner) if inner else None
    except ValueError:
        return inner.split()


def load_denylist():
    """Private names, from the same lists the toolbox check reads (one term per line)."""
    paths = [Path(p) for p in os.environ.get("F3I_TOOLBOX_DENYLIST", "").split(":") if p]
    default = Path("~/.config/f3i-toolbox/denylist.txt").expanduser()
    if default.exists():
        paths.append(default)
    terms = []
    while paths:
        path = paths.pop(0)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("@"):
                paths.append(Path(line[1:]).expanduser())
                continue
            term = line[1:] if line.startswith("=") else line
            terms.append(re.compile(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])",
                                    0 if line.startswith("=") else re.I))
    return terms


def lint(root, orchestrator, agents, texts, skills, scripts, launch=None, launch_where="launcher"):
    """Findings as (level, lint, where, text). agents: name -> (where, text); texts: toolbox
    files to screen for private names and home paths; scripts: generated script paths."""
    out = []

    def err(name, where, text):
        out.append(("error", name, where, text))

    def command_problem(argv):
        first = argv[0]
        if first in SHELL_COMMANDS:
            return None
        if first in INTERPRETERS or re.match(r"^python3\.\d+$", first):
            m = re.search(r"\.claude/skills/([^/]+)/(.+)$", argv[1]) if len(argv) > 1 else None
            if m and f"{m.group(1)}/{m.group(2)}" not in scripts:
                home = skill_dir(root, m.group(1))
                if home is None or not (home / m.group(2)).is_file():
                    return f"{argv[1]}: no such script in the {m.group(1)} skill"
            return None
        if "/" in first or find_script(root, first):
            return None
        return f"'{first}' is no script in any skill's scripts/ folder"

    if not NAME_RE.match(orchestrator):
        err("name", orchestrator, "an orchestrator is kebab-case <domain>-<thing>-orchestrator")
    rules = []
    for name, (where, text) in agents.items():
        meta, _ = split_frontmatter(text)
        if meta.get("name") != name or Path(where).stem != name:
            err("name", where, f"frontmatter name '{meta.get('name')}' must equal the file name '{Path(where).stem}'")
        desc = " ".join(str(meta.get("description") or "").split())
        if not desc:
            err("description", where, "no description")
        elif len(desc) > DESCRIPTION_LIMIT:
            err("description", where, f"description is {len(desc)} characters, over {DESCRIPTION_LIMIT}")
        if name == orchestrator:
            hit = FOLLOW_PHRASE.search(text)
            if hit:
                err("follow-phrase", where, f"'{hit.group(0)}': say 'read it' or 'as the skill says'")
        for skill in as_list(meta.get("skills")):
            if skill not in skills:
                err("skills", where, f"skills: names '{skill}', and no <department>/skills/{skill}/SKILL.md exists")
        rules += [(where, r) for r in as_list(meta.get("tools"))]
    if launch:
        rules += [(launch_where, r) for r in as_list(launch.get("allowed-tools"))]
        for key in (launch.get("inputs") or {}):
            if key in RESERVED:
                err("reserved", launch_where, f"input '{key}' is a name the launcher fills itself")
        for key in ((launch.get("form") or {}).get("params") or {}):
            if key in RESERVED and key != "dry_run":
                err("reserved", launch_where, f"form param '{key}' is a name the launcher fills itself")
        for key in ("prepare", "finish"):
            for i, item in enumerate(launch.get(key) or [], 1):
                argv = item.get("argv") if isinstance(item, dict) else item
                problem = command_problem([str(a) for a in argv]) if argv else None
                if problem:
                    err("commands", launch_where, f"{key} {i}: {problem}")
        pre = launch.get("precheck")
        if pre:
            pre = [str(a) for a in (pre if isinstance(pre, list) else shlex.split(str(pre)))]
            problem = command_problem(pre)
            if problem:
                err("commands", launch_where, f"precheck: {problem}")
            if any(PLACEHOLDER.search(a) for a in pre):
                err("precheck", launch_where, "a precheck runs before any launch, so no {placeholder} in it is "
                                              "filled; write the value")
    for where, rule in rules:
        if INTERPRETER_RULE.match(rule.strip()):
            err("interpreter", where, f"{rule}: grant the exact script "
                                      f"(Bash(python3 ~/.claude/skills/<skill>/scripts/<x>.py:*))")
            continue
        argv = rule_argv(rule)
        problem = command_problem(argv) if argv else None
        if problem:
            err("commands", where, f"{rule}: {problem}")
    denylist = load_denylist()
    if not denylist:
        out.append(("warning", "names", "denylist", "no private-name denylist loaded; names not checked"))
    for where, text in texts.items():
        if any(rx.search(text) for rx in denylist):
            err("names", where, "a private name from the denylist; keep it in the launcher settings")
        m = HOME_PATH.search(text)
        if m:
            err("home-path", where, "an absolute home path; use ~ or a folder input")
    return out


def finding_line(f):
    return f"{f[0]}: [{f[1]}] {f[2]}: {f[3]}"


# ------------------------------------------------------------------------------- generate and lint

def build_plan(spec, root, update):
    """[(path, text, action)] and the refusals."""
    dept = root / spec["department"]
    files = [(dept / "agents" / f"{spec['name']}.md", orchestrator_md(spec, root))]
    files += [(dept / "agents" / f"{w['name']}.md", worker_md(spec, root, w)) for w in spec["workers"]
              if not w["existing"]]
    files += [(dept / "skills" / sk["name"] / "SKILL.md", skill_md(spec, sk)) for sk in spec["skills"]["new"]]
    if spec["done"]["build"] or spec["tools"]["new"]:
        scripts = home_skill_dir(spec, root) / "scripts"
        if spec["done"]["build"]:
            files.append((scripts / script_name(spec["done"]["check"]), check_py(spec)))
            files.append((scripts / "tests" / ("test_" + script_name(spec["done"]["check"])), test_py(spec)))
        files += [(scripts / script_name(t["name"]), stub_py(t)) for t in spec["tools"]["new"]]
    plan, refusals = [], []
    for path, text in files:
        action = "create"
        if path.exists():
            if update and has_marker(path):
                action = "update"
            else:
                refusals.append(f"{path} exists" + (" and carries no scaffold marker" if update else ""))
        elif path.suffix == ".py" and path.parent.name != "tests":
            taken = find_script(root, path.stem.replace("_", "-"))
            if taken:
                refusals.append(f"{path.stem.replace('_', '-')} already exists as {taken[1]}")
        plan.append((path, text, action))
    return plan, refusals


def generate(args):
    root = Path(args.root).expanduser().resolve()
    spec = load_spec(args.spec)
    if not (root / spec["department"]).is_dir():
        raise SpecError(f"{root} has no department folder {spec['department']}/ (is --root the toolbox?)")
    values = {}
    for item in args.set or []:
        key, sep, value = item.partition("=")
        if not sep or not value:
            raise SpecError(f"--set {item}: write PARAM=VALUE")
        values[key] = value
    fixed = [v["param"] for v in (spec["record"]["folder"], spec["record"]["delivery"]) if v]
    if args.launcher and set(fixed) - set(values):
        raise SpecError(f"--launcher needs a value for every fixed input: --set {sorted(set(fixed) - set(values))[0]}=...")
    plan, refusals = build_plan(spec, root, args.update)
    launch_text = launcher_yaml(spec, root, values)
    agents = {p.stem: (str(p.relative_to(root)), t) for p, t, _ in plan if p.parent.name == "agents"}
    for w in spec["workers"]:
        if w["existing"]:
            path = find_agent(root, w["name"])
            agents[w["name"]] = ((str(path.relative_to(root)), path.read_text(encoding="utf-8")) if path else
                                 (f"?/agents/{w['name']}.md", "---\nname: missing\n---\n"))
    skills = skill_names(root) | {s["name"] for s in spec["skills"]["new"]}
    scripts = {f"{spec['done']['skill']}/scripts/{p.name}" for p, _, _ in plan if p.suffix == ".py"}
    texts = {str(p.relative_to(root)): t for p, t, _ in plan}
    launch = yaml.safe_load(launch_text)
    findings = lint(root, spec["name"], agents, texts, skills, scripts, launch,
                    str(args.launcher) if args.launcher else "launcher")
    if any(i["name"] == "dry_run" for i in spec["inputs"]):
        findings.append(("error", "reserved", "spec inputs", "'dry_run' is added to every launch form already"))
    for name in spec["skills"]["load"]:
        if name not in skills:
            findings.append(("error", "skills", "spec skills.load", f"'{name}' is no skill in the toolbox"))
    if not spec["not_for"]:
        findings.append(("warning", "not-for", "spec", "no `not_for`: the description names no sibling to use "
                                                       "instead (\"Not for X; use Y.\")"))
    errors = [f for f in findings if f[0] == "error"]
    if args.launcher:
        path = Path(args.launcher).expanduser()
        action = "create"
        if path.exists():
            if args.update and has_marker(path):
                action = "update"
            else:
                refusals.append(f"{path} exists" + (" and carries no scaffold marker" if args.update else ""))
        plan.append((path, launch_text, action))

    print(f"{spec['name']}: {len(plan)} file(s); {'would write' if args.dry_run else 'writes'}:")
    for path, text, action in plan:
        print(f"  {action:<6} {path}")
        if args.dry_run and args.show:
            print("\n".join("      | " + ln for ln in text.splitlines()))
    if not args.launcher:
        print("\nThe launcher settings, for the owner's private settings (or pass --launcher FILE --set ...):\n")
        print(launch_text)
    for f in findings:
        print(finding_line(f))
    for r in refusals:
        print(f"refused: {r}")
    if errors or refusals:
        print(f"FAIL: {len(errors)} lint error(s), {len(refusals)} refusal(s); nothing written")
        return 1
    if args.dry_run:
        print("OK: dry run; nothing written")
        return 0
    for path, text, _ in plan:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(f"OK: {len(plan)} file(s) written. Next: write each file goal-first and delete its marker, build each "
          f"stub, run the generated test, and review the launcher settings.")
    return 0


def team_from_table(body, root):
    """Backticked agent names in the first column of a markdown table."""
    names = []
    for line in body.splitlines():
        if line.startswith("|") and not set(line) <= set("|- "):
            for n in re.findall(r"`([a-z0-9-]+)`", line.strip().strip("|").split("|")[0]):
                if find_agent(root, n) and n not in names:
                    names.append(n)
    return names


def lint_existing(args):
    root = Path(args.root).expanduser().resolve()
    path = find_agent(root, args.name)
    if path is None:
        raise SpecError(f"no agent {args.name}.md under {root}/*/agents")
    text = path.read_text(encoding="utf-8")
    agents = {args.name: (str(path.relative_to(root)), text)}
    for member in team_from_table(split_frontmatter(text)[1], root):
        if member != args.name:
            p = find_agent(root, member)
            agents[member] = (str(p.relative_to(root)), p.read_text(encoding="utf-8"))
    texts = {}
    for where, member_text in agents.values():
        texts[where] = member_text
        for skill in as_list(split_frontmatter(member_text)[0].get("skills")):
            d = skill_dir(root, skill)
            if d:
                texts[str((d / "SKILL.md").relative_to(root))] = (d / "SKILL.md").read_text(encoding="utf-8")
    launch = None
    if args.launcher:
        try:
            launch = yaml.safe_load(Path(args.launcher).expanduser().read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise SpecError(f"launcher {args.launcher}: {exc}") from None
        if launch.get("agent") and launch["agent"] != args.name:
            raise SpecError(f"launcher {args.launcher} is for {launch['agent']}, not {args.name}")
    findings = lint(root, args.name, agents, texts, skill_names(root), set(), launch, str(args.launcher or ""))
    errors = [f for f in findings if f[0] == "error"]
    if args.format == "json":
        print(json.dumps({"name": args.name, "ok": not errors, "agents": sorted(agents),
                          "findings": [dict(zip(("level", "lint", "where", "text"), f)) for f in findings]}, indent=1))
    else:
        print(f"{'FAIL' if errors else 'OK'}: {args.name}: {len(errors)} error(s), "
              f"{len(findings) - len(errors)} warning(s); agents {', '.join(sorted(agents))}")
        for f in findings:
            print("  " + finding_line(f))
    return 1 if errors else 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="orchestrator-scaffold",
                                     description="Generate an orchestrator from a spec, and lint orchestrators.")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="write the orchestrator SPEC describes")
    gen.add_argument("spec")
    gen.add_argument("--dry-run", action="store_true", help="print every file it would write; write nothing")
    gen.add_argument("--show", action="store_true", help="with --dry-run, print each file's text too")
    gen.add_argument("--update", action="store_true", help="replace files that still carry the scaffold's marker")
    gen.add_argument("--launcher", help="write the launcher settings to this file (outside the toolbox)")
    gen.add_argument("--set", action="append", metavar="PARAM=VALUE", help="a fixed input's value, for --launcher")
    chk = sub.add_parser("lint", help="lint the orchestrator NAME as it exists")
    chk.add_argument("name")
    chk.add_argument("--launcher", help="its launcher settings file, linted too")
    chk.add_argument("--format", choices=["text", "json"], default="text")
    for p in (gen, chk):
        p.add_argument("--root", default=str(DEFAULT_ROOT), help="the toolbox checkout (default: this one)")
    args = parser.parse_args(argv)
    try:
        return generate(args) if args.command == "generate" else lint_existing(args)
    except SpecError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
