"""What the fleet scripts share: the owner's settings, the fleet registry, and the runner.

THE REGISTRY is the owner's YAML file listing every orchestrator: where it stands, the
Automation that starts it, who may launch it and with which params. It lives outside this
repository. Its path is the setting `registry` in the `[orchestrator-fleet]` table, or
`--registry`. fleet_registry.py's docstring gives its schema.

THE RUNNER is whatever scheduler starts Automations. These scripts never assume a particular
one; two commands in the settings describe it:

    [orchestrator-fleet]
    registry        = "~/fleet/REGISTRY.yaml"
    agents_dir      = "~/.claude/agents"            # default
    automations_dir = "~/automations"               # optional
    runs_command    = ["my-runner", "runs", "--format", "json"]
    launch_command  = ["my-runner", "launch", "{automation_path}", "--source", "agent"]
    param_args      = ["--param", "{key}={value}"]  # default
    reserved_params = ["task", "run_dir"]           # optional; dry_run is always reserved

A command is a TOML list of words, or one string split like a shell would split it. It is run
directly, never through a shell.

`runs_command` prints the runner's recent Runs as JSON: a list of runs, or
{"runs": [...], "queue": [...]}. Each run is read leniently: `id` or `run_id`; `automation`
(or `workflow`); `status`; `phase`; `started_at` (or `queued_at`, `created_at`, `at`);
`ended_at`; `accepted`; `live`; `for_owner` (a count or a list of what waits on the owner);
`params.dry_run`; and `source` (a mapping, or its JSON text, with `kind` and, for an agent's
launch, `agent`) or `source_kind`. A run with no automation name is ignored.
"""

import json
import os
import re
import shlex
import subprocess
import tomllib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

SECTION = "orchestrator-fleet"
DEFAULT_AGENTS_DIR = "~/.claude/agents"
DEFAULT_PARAM_ARGS = ["--param", "{key}={value}"]
RUNNER_TIMEOUT_S = 60

TIERS = ("A", "B", "C")
STATUSES = ("spec", "drafted", "built", "dry-run-passed", "live", "scheduled")
AUTHORITIES = ("dry-run-only", "propose", "trusted")   # lowest to highest
VALUES = ("H", "M", "L")
REQUIRED = ("name", "domain", "tier", "status", "automation", "triggers", "inputs", "record",
            "authority", "check", "outputs", "replaces", "wave", "value")
OPTIONAL = ("plan", "purpose")
TRIGGER_KEYS = ("schedule", "tz", "precheck", "cadence", "events", "manual")
NAME_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)+-orchestrator$")

TERMINAL = frozenset({"completed", "failed", "refused", "stopped", "abandoned", "cancelled", "canceled"})
QUEUED = frozenset({"queued", "pending"})
WAITING = frozenset({"waiting_on_you", "needs_owner", "awaiting_owner"})


class Bad(Exception):
    """A missing setting or an unreadable registry: one line on stderr, exit 2."""


class RunnerError(Exception):
    """The runner's command is not set, could not be run, or printed something unreadable."""


# --------------------------------------------------------------------------- settings

def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


def fleet_settings():
    return settings(SECTION)


def command_words(value):
    """A command setting as a list of words: a list as given, a string split like a shell."""
    if value is None or value == "" or value == []:
        return None
    if isinstance(value, str):
        return shlex.split(value)
    return [str(word) for word in value]


def reserved_params():
    """Param names the runner fills itself; dry_run is always among them."""
    return set(fleet_settings().get("reserved_params") or []) | {"dry_run"}


def agents_dir(override=None):
    return Path(override or fleet_settings().get("agents_dir") or DEFAULT_AGENTS_DIR).expanduser()


# --------------------------------------------------------------------------- registry

class Registry:
    def __init__(self, path, data):
        self.path, self.data = path, data
        self.entries = list(data["orchestrators"])

    def get(self, name):
        return next((e for e in self.entries if isinstance(e, dict) and e.get("name") == name), None)

    def automations_dir(self, override=None):
        """--automations-dir, else the setting, else the registry's own key; None when none is set.
        A relative path in the registry resolves against the registry's folder."""
        if override:
            return Path(override).expanduser()
        value = fleet_settings().get("automations_dir")
        if value:
            return Path(value).expanduser()
        value = self.data.get("automations_dir")
        if value:
            path = Path(str(value)).expanduser()
            return path if path.is_absolute() else self.path.parent / path
        return None

    def cap(self):
        """The registry's optional daily launch cap; None (no cap) when it names none."""
        value = self.data.get("launch_cap_per_day")
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None

    def automations(self):
        return {e.get("automation") for e in self.entries if isinstance(e, dict) and e.get("automation")}


def load_registry(explicit=None):
    """Read the registry from --registry or the `registry` setting; Bad when it cannot be read."""
    import yaml  # imported here so --help works without pyyaml

    value = explicit or fleet_settings().get("registry")
    if not value:
        raise Bad(f"setting [{SECTION}] registry is needed (or pass --registry)")
    path = Path(value).expanduser()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise Bad(f"no registry at {path}") from None
    except (OSError, yaml.YAMLError) as exc:
        raise Bad(f"{path}: {exc}") from None
    if not isinstance(data, dict) or not isinstance(data.get("orchestrators"), list):
        raise Bad(f"{path}: the top level must be a mapping with an `orchestrators:` list")
    return Registry(path, data)


def filtered(registry, domain=None, status=None):
    return [e for e in registry.entries if isinstance(e, dict)
            and (domain is None or e.get("domain") == domain)
            and (status is None or e.get("status") == status)]


def has_placeholder(command):
    return bool(re.search(r"\{[A-Za-z_][A-Za-z0-9_]*\}", command))


def table(rows, header):
    widths = [max(len(str(r[i])) for r in [header] + rows) for i in range(len(header))]
    lines = ["  ".join(str(c).ljust(w) for c, w in zip(header, widths)).rstrip()]
    lines += ["  ".join(str(c).ljust(w) for c, w in zip(r, widths)).rstrip() for r in rows]
    return "\n".join(lines)


# --------------------------------------------------------------------------- the runner's Runs

@dataclass
class Run:
    id: str
    automation: str
    status: str
    phase: str = ""
    started_at: datetime = None
    ended_at: datetime = None
    source_kind: str = None
    source_agent: str = None
    accepted: bool = None
    live: bool = None
    for_owner: int = 0
    dry_run: bool = None

    @property
    def is_waiting(self):
        return self.status in WAITING or self.status.startswith("awaiting")

    @property
    def is_queued(self):
        return self.status in QUEUED

    @property
    def is_live(self):
        if self.live is not None:
            return bool(self.live) and not self.is_queued
        return not (self.status in TERMINAL or self.is_queued or self.is_waiting)

    def local_date(self):
        return self.started_at.astimezone().date() if self.started_at else None


def parse_time(value):
    if not value or not isinstance(value, str):
        return None
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _source(row):
    """The run's source as a mapping, or its bare kind as a string."""
    source = row.get("source")
    if isinstance(source, str):
        try:
            return json.loads(source)
        except ValueError:
            return source or None
    return source


def _count(value):
    if isinstance(value, list):
        return len(value)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def run_from_row(row, status=None):
    automation = row.get("automation") or row.get("workflow")
    if not automation:
        return None
    started = next((t for t in (parse_time(row.get(k)) for k in ("started_at", "queued_at", "created_at", "at"))
                    if t), None)
    source = _source(row)
    kind = row.get("source_kind") or (source.get("kind") if isinstance(source, dict) else source)
    agent = source.get("agent") if isinstance(source, dict) else None
    params = row.get("params") if isinstance(row.get("params"), dict) else {}
    accepted = row.get("accepted")
    return Run(id=str(row.get("id") or row.get("run_id") or ""), automation=str(automation),
               status=str(status or row.get("status") or ""), phase=str(row.get("phase") or ""),
               started_at=started, ended_at=parse_time(row.get("ended_at")),
               source_kind=str(kind) if kind else None, source_agent=str(agent) if agent else None,
               accepted=None if accepted is None else bool(accepted),
               live=row.get("live") if isinstance(row.get("live"), bool) else None,
               for_owner=_count(row.get("for_owner")),
               dry_run=params.get("dry_run") if isinstance(params.get("dry_run"), bool) else None)


def parse_runs(text):
    """The runs in the runner's JSON, newest first. Queue rows not already listed are added as queued."""
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise RunnerError(f"runs_command did not print JSON: {exc}") from None
    if isinstance(data, dict):
        items, queue = data.get("runs") or [], data.get("queue") or []
    elif isinstance(data, list):
        items, queue = data, []
    else:
        raise RunnerError("runs_command printed neither a list nor a mapping")
    runs = [r for r in (run_from_row(row) for row in items if isinstance(row, dict)) if r]
    known = {r.id for r in runs if r.id}
    for row in queue:
        if isinstance(row, dict):
            run = run_from_row(row, status=row.get("status") or "queued")
            if run and (not run.id or run.id not in known):
                runs.append(run)
    floor = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(runs, key=lambda r: (r.started_at or floor, r.id), reverse=True)


def _call(argv, what):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=RUNNER_TIMEOUT_S, check=False)
    except FileNotFoundError:
        raise RunnerError(f"{what}: {argv[0]} not found") from None
    except subprocess.TimeoutExpired:
        raise RunnerError(f"{what}: no answer in {RUNNER_TIMEOUT_S}s") from None
    except OSError as exc:
        raise RunnerError(f"{what}: {exc}") from None


def read_runs():
    """Every Run the runner lists, newest first, from the runs_command setting."""
    argv = command_words(fleet_settings().get("runs_command"))
    if not argv:
        raise RunnerError(f"setting [{SECTION}] runs_command is needed")
    done = _call(argv, "runs_command")
    if done.returncode != 0:
        detail = (done.stderr or done.stdout).strip().splitlines()
        raise RunnerError(f"runs_command failed: {detail[0] if detail else f'exit {done.returncode}'}")
    return parse_runs(done.stdout)


def count_today(runs, automations, today, by=None):
    """Today's agent launches (only `by`'s when given). A run with no source at all counts when it
    is of a registered Automation, so the cap errs toward refusing."""
    count = 0
    for r in runs:
        if r.local_date() not in (None, today):
            continue
        if r.source_kind is None:
            count += r.automation in automations
        elif r.source_kind == "agent" and (by is None or r.source_agent in (None, by)):
            count += 1
    return count


def launch_argv(automation, automation_path, by, params):
    """The launch command with its placeholders filled, then the param words for each param.
    Bad when the setting it needs is missing."""
    s = fleet_settings()
    template = command_words(s.get("launch_command"))
    if not template:
        raise Bad(f"setting [{SECTION}] launch_command is needed")
    if any("{automation_path}" in w for w in template) and automation_path is None:
        raise Bad(f"setting [{SECTION}] automations_dir is needed: launch_command uses {{automation_path}}")
    values = {"{automation}": automation, "{automation_path}": str(automation_path or ""), "{by}": by or ""}
    argv = [fill(w, values) for w in template]
    for key, value in params.items():
        pair = {"{key}": key, "{value}": value}
        argv += [fill(w, pair) for w in (command_words(s.get("param_args")) or DEFAULT_PARAM_ARGS)]
    return argv


def fill(word, values):
    for placeholder, value in values.items():
        word = word.replace(placeholder, value)
    return word


def launch(argv):
    return _call(argv, "launch_command")


def today():
    return date.today()
