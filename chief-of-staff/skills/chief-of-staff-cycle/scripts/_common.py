"""What the chief-of-staff cycle scripts share: the owner settings, the state folders, JSON
files and output, the Insights Portal client, the name the owner sees, the two Portal
lookups more than one script needs (the day's receipt note, the decision tasks), the doer
registry, the decider-reply parser and the message to the owner.

Settings are read from the table [chief-of-staff-cycle] first and the top level second
(`setting`). Nothing here holds state of its own, and no folder a script writes may sit inside
this skill's folder. Exit codes: 0 go on, 3 a hold or a refusal the skill branches on, 2 the
command could not run.
"""

import json
import os
import re
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

SKILL_DIR = Path(__file__).resolve().parents[1]
SKILLS_HOME = Path("~/.claude/skills").expanduser()
NOTIFY_SCRIPT = SKILLS_HOME / "comms-reply-to-email" / "scripts" / "notify_owner.py"
PRODUCE_INSTRUCTIONS = SKILLS_HOME / "task-stack-produce" / "SKILL.md"

SECTION = "chief-of-staff-cycle"
OK, STOP, ERROR = 0, 3, 2

DISPLAY_NAME_DEFAULT = "Chief of Staff"
RECEIPT_TITLE = "{name} Receipt {date}"
DECISION_PREFIX = "[{name}]"
CYCLE_MARK = "<!-- chief-of-staff:cycle:{cycle_id} -->"
DECISION_MARKER = "chief-of-staff:decision:{date}:{key}"
OWN_SKILLS = ("chief-of-staff-cycle",)
OWN_AGENTS = ("chief-of-staff-cycle-orchestrator",)
CYCLE_AGENT = "chief-of-staff-cycle-orchestrator"

_NAME_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .'&-]{0,39}$")
UUID = r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}"
FOCUS = r"[\w .,'@:/-]{0,200}"
PRODUCE_TARGET = rf"(?:task|project|meeting|email|goal):{UUID}"


class Bad(Exception):
    """The command could not run: a bad argument, a missing setting, an unreadable input or a
    Portal failure (exit 2). The message never holds a token."""


# --------------------------------------------------------------------------- settings and output

def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


def setting(key, default=None):
    """A key from [chief-of-staff-cycle], else the top level, else the default."""
    own = settings(SECTION)
    if key in own:
        return own[key]
    return settings().get(key, default)


_SECRETS = re.compile(r"(?i)(bearer\s+\S+|authorization[\"'\s:=]+\S+|[?&](?:key|token|api_key|access_token)=[^\s&\"']+)")


def safe(text):
    """Everything printed passes through here, so a bearer token is never shown."""
    return _SECRETS.sub("[redacted]", str(text))


def emit(payload, code):
    print(safe(json.dumps(payload, indent=1, default=str)))
    sys.exit(code)


def fail(message):
    print(safe(json.dumps({"status": "error", "reason": str(message)}, indent=1)))
    sys.exit(ERROR)


def flat(value, limit):
    """One line, whitespace folded, cut to `limit` characters."""
    if value is None:
        return ""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def dry_run_forced(dry):
    """A refusal when a runner marked this a dry run (F3I_TOOLBOX_DRY_RUN) and the call is not."""
    if not dry and os.environ.get("F3I_TOOLBOX_DRY_RUN", "").strip().lower() in ("1", "true", "yes", "on"):
        return "F3I_TOOLBOX_DRY_RUN is set: a write must be called with --dry-run"
    return ""


# --------------------------------------------------------------------------- folders and files

def guard(path):
    """A folder or file the scripts write never sits inside this skill's folder."""
    target = Path(path).expanduser().resolve()
    if target == SKILL_DIR or SKILL_DIR in target.parents:
        raise Bad(f"{target} is inside the skill folder; state lives outside it")
    return target


def state_root(explicit=None):
    """The cycle's state folder: --state, else [chief-of-staff-cycle] state, else
    <state_dir>/chief-of-staff."""
    value = explicit or settings(SECTION).get("state")
    if not value:
        base = settings().get("state_dir")
        if not base:
            raise Bad("setting state_dir is needed (or [chief-of-staff-cycle] state, or pass --state)")
        value = str(Path(base).expanduser() / "chief-of-staff")
    root = guard(value)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def cycle_dir(path):
    folder = guard(path)
    if not (folder / "cycle.json").exists():
        raise Bad(f"{folder} is not a cycle folder (no cycle.json)")
    return folder


def root_of(folder):
    """The state folder a cycle folder sits in: <state>/cycles/<date>/<cycle>."""
    return Path(folder).parents[2]


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(value, fh, indent=1, ensure_ascii=False, default=str)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def now_utc():
    return datetime.now(timezone.utc)


def local_now():
    """The machine's local time: a cycle is dated by the clock it runs under."""
    return datetime.now().astimezone()


def check_date(value):
    if not value:
        return local_now().date().isoformat()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise Bad(f"--date must be YYYY-MM-DD, got {value!r}")
    date.fromisoformat(value)
    return value


def parse_time(value):
    if not value:
        return None
    try:
        out = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return out if out.tzinfo else out.replace(tzinfo=timezone.utc)


def find_object(text):
    """The first balanced top-level JSON object in text, strings respected."""
    depth, start, in_str, esc = 0, None, False, False
    for i, ch in enumerate(text or ""):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                return text[start:i + 1]
    return None


def load_object(text):
    raw = find_object(text or "")
    try:
        value = json.loads(raw) if raw else None
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def local_path_in(text):
    """An absolute local path in text bound for a shared surface, or None."""
    m = re.search(r"(?:(?<![\w/])~/|/home/|/mnt/[a-z]/|/Users/|[A-Za-z]:\\)[^\s)]*", text or "")
    return m.group(0) if m else None


# --------------------------------------------------------------------------- the name the owner sees

def _clean_name(value):
    text = " ".join(str(value or "").split())
    return text if _NAME_OK.match(text) else ""


def display_name():
    """The setting display_name, else "Chief of Staff". A value that would break a title or a
    prefix (brackets, a newline, over 40 characters) falls back to the default."""
    return _clean_name(setting("display_name")) or DISPLAY_NAME_DEFAULT


def known_names():
    """The display name first, then former_names: the names earlier records may carry, so a
    rename never duplicates today's receipt or an open decision."""
    former = setting("former_names")
    out = []
    for name in [display_name()] + (list(former) if isinstance(former, list) else []):
        name = _clean_name(name)
        if name and name.lower() not in (n.lower() for n in out):
            out.append(name)
    return out


def receipt_title(day, name=None):
    return RECEIPT_TITLE.format(name=name or display_name(), date=day)


def decision_prefix(name=None):
    return DECISION_PREFIX.format(name=name or display_name())


def strip_decision_prefix(title):
    text = " ".join(str(title or "").split())
    for name in known_names():
        prefix = decision_prefix(name)
        if text.lower().startswith(prefix.lower()):
            return text[len(prefix):].lstrip()
    return text


# --------------------------------------------------------------------------- the doer registry

def _pattern(text):
    """A registry args pattern: the words UUID and FOCUS stand for the shared patterns."""
    text = str(text or "")
    return text.replace("PRODUCE_TARGET", PRODUCE_TARGET).replace("UUID", UUID).replace("FOCUS", FOCUS)


def load_doers(path=None):
    """The owner's doer registry ({"doers": {name: spec}, "retired": {name: why}, "problems": [...],
    "path": ...}). The file the setting doer_registry names is the only source: with none,
    no doer may run. A malformed entry is left out and named in problems."""
    path = path or setting("doer_registry")
    out = {"doers": {}, "retired": {}, "problems": [], "path": str(path or "")}
    if not path:
        out["problems"].append("no doer registry: setting doer_registry is not set, so no doer may run")
        return out
    try:
        data = tomllib.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        out["problems"].append(f"the doer registry could not be read ({type(exc).__name__})")
        return out
    for raw in data.get("doer") or []:
        name = flat((raw or {}).get("name"), 60) if isinstance(raw, dict) else ""
        route = (raw or {}).get("route") if isinstance(raw, dict) else None
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,59}", name or ""):
            out["problems"].append(f"a doer has no valid name ({name or 'none'})")
            continue
        spec = {"route": route, "args": _pattern(raw.get("args")) if raw.get("args") is not None else None,
                "default_args": flat(raw.get("default_args"), 200), "purpose": flat(raw.get("purpose"), 300),
                "when": flat(raw.get("when"), 300)}
        if route == "produce":
            spec.update(skill="task-stack-produce", worker="chief-of-staff-producer")
            spec["args"] = spec["args"] or PRODUCE_TARGET
        elif route == "skill":
            spec.update(skill=flat(raw.get("skill"), 80), worker=flat(raw.get("worker"), 80) or "chief-of-staff-readonly-doer")
        elif route == "agent":
            spec.update(skill="", worker=flat(raw.get("agent"), 80))
        else:
            out["problems"].append(f"{name}: route must be produce, skill or agent")
            continue
        bad = [v for v in (spec.get("skill"), spec["worker"]) if v and not re.fullmatch(r"[a-z0-9][a-z0-9-]*", v)]
        if (route == "skill" and not spec["skill"]) or not spec["worker"] or bad:
            out["problems"].append(f"{name}: needs a valid skill or agent name")
            continue
        if spec["skill"] in OWN_SKILLS or spec["worker"] in OWN_AGENTS or spec["worker"].endswith("-orchestrator"):
            out["problems"].append(f"{name}: an orchestrator is launched, never dispatched as a doer")
            continue
        try:
            re.compile(spec["args"] or "")
        except re.error:
            out["problems"].append(f"{name}: its args pattern does not compile")
            continue
        out["doers"][name] = spec
    retired = data.get("retired") or {}
    if isinstance(retired, dict):
        out["retired"] = {str(k): flat(v, 300) for k, v in retired.items()}
    return out


def doer_skills(doers):
    """The skills whose SKILL.md is inside the improvement surface: those the registry runs."""
    return sorted({s["skill"] for s in doers.values() if s.get("skill") and s["skill"] not in OWN_SKILLS})


def check_params(raw, inputs):
    """(params, None) or ({}, why): each param one of the entry's inputs, matching its pattern."""
    if raw in (None, "", {}):
        return {}, None
    if not isinstance(raw, dict):
        return {}, "params must be an object of name to value"
    params = {}
    for key, value in raw.items():
        key = str(key)
        text = "" if value is None else (str(value).lower() if isinstance(value, bool) else str(value))
        if key == "dry_run":
            return {}, f"param '{key}' is not the decider's to set"
        if key not in inputs:
            return {}, f"param '{key}' is not one of its inputs ({', '.join(sorted(inputs)) or 'none'})"
        pattern = inputs[key]
        if pattern is not None and not re.fullmatch(str(pattern), text):
            return {}, f"param '{key}'='{flat(text, 60)}' does not match {pattern}"
        if "\n" in text or len(text) > 500:
            return {}, f"param '{key}' is not one short line"
        params[key] = text
    return params, None


# --------------------------------------------------------------------------- the Portal

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect, so the bearer token only ever goes to the configured URL."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def portal_endpoint(config=None, server=None):
    """(url, Authorization header) from the MCP config the settings name. The token is
    INSIGHTS_PORTAL_ASSISTANT_TOKEN when set, else the config's header with ${VAR} expanded.
    HTTPS only, except plain HTTP to localhost."""
    conf = settings()
    config = config or conf.get("portal_mcp_config")
    server = server or conf.get("portal_server") or "insights-portal"
    if not config:
        raise Bad("setting portal_mcp_config is needed (the MCP config holding the Portal server)")
    try:
        entry = json.loads(Path(config).expanduser().read_text())["mcpServers"][server]
    except (OSError, KeyError, TypeError, ValueError):
        raise Bad(f"the MCP config has no usable server named {server!r}") from None
    token = os.environ.get("INSIGHTS_PORTAL_ASSISTANT_TOKEN", "").strip()
    auth = f"Bearer {token}" if token else (entry.get("headers") or {}).get("Authorization", "")

    def expand(value, what):
        def one(match):
            if not os.environ.get(match.group(1)):
                raise Bad(f"the Portal {what} needs {match.group(1)}, which is not set")
            return os.environ[match.group(1)]
        value = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", one, value or "")
        if "${" in value or "\n" in value:
            raise Bad(f"the Portal {what} is malformed")
        return value

    url, auth = expand(entry.get("url", ""), "URL"), expand(auth, "token")
    parts = urlsplit(url)
    local = parts.hostname in ("localhost", "127.0.0.1", "::1")
    if not parts.hostname or not (parts.scheme == "https" or (parts.scheme == "http" and local)):
        raise Bad("the Portal URL must be HTTPS (HTTP only on localhost)")
    if not auth.startswith("Bearer ") or not auth[7:].strip():
        raise Bad("no Portal bearer token: set INSIGHTS_PORTAL_ASSISTANT_TOKEN or put one in the config")
    return url, auth


class Portal:
    """A small JSON-RPC client for the Portal's MCP tools."""

    def __init__(self, config=None, server=None, timeout=60):
        self.url, self._auth = portal_endpoint(config, server)
        self.timeout = timeout
        self._id = 0

    def call(self, tool, arguments=None):
        self._id += 1
        body = json.dumps({"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
                           "params": {"name": tool, "arguments": arguments or {}}}).encode()
        req = urllib.request.Request(self.url, data=body, method="POST")
        req.add_header("Authorization", self._auth)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json, text/event-stream")
        try:
            with _OPENER.open(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise Bad(f"portal {tool}: HTTP {exc.code}") from None
        except (urllib.error.URLError, OSError) as exc:
            raise Bad(f"portal {tool}: {getattr(exc, 'reason', type(exc).__name__)}") from None
        lines = [raw] if raw.lstrip().startswith("{") else [l[5:] for l in raw.splitlines() if l.startswith("data:")]
        messages = []
        for line in lines:
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if not messages:
            raise Bad(f"portal {tool}: empty response")
        out = messages[-1]
        if "error" in out:
            raise Bad(f"portal {tool}: {out['error']}")
        result = out.get("result", out)
        if isinstance(result, dict) and "content" in result:
            text = "\n".join(c.get("text", "") for c in result["content"] if c.get("type") == "text")
            if result.get("isError"):
                raise Bad(f"portal {tool}: {text[:300]}")
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        return result


def list_all(client, entity_type, filters=None, max_pages=50):
    """Every row of one entity type, following next_offset until has_more is false."""
    args = {"entity_type": entity_type, "limit": 200}
    if filters:
        args["filters"] = filters
    items, offset = [], 0
    for _ in range(max_pages):
        if offset:
            args["offset"] = offset
        out = client.call("list_entities", args)
        if not isinstance(out, dict):
            break
        items.extend(i for i in out.get("items") or [] if isinstance(i, dict))
        nxt = out.get("next_offset")
        if not out.get("has_more") or not isinstance(nxt, int) or nxt <= offset:
            break
        offset = nxt
    return items


def principal(client):
    who = client.call("whoami")
    return ((who or {}).get("principal") or {}) if isinstance(who, dict) else {}


def _title_is(value, wanted):
    return isinstance(value, str) and value.strip().lower() == wanted.strip().lower()


def find_note(client, title):
    """The note whose title is exactly `title`, or None. Matched on the record's title, never
    as a substring of the response: a not-found answer echoes the query back."""
    try:
        out = client.call("get", {"entity_type": "note", "id_or_query": title, "detail": "full"})
    except Bad:
        out = None
    if isinstance(out, dict) and not out.get("error"):
        note = out.get("note") if isinstance(out.get("note"), dict) else out
        if _title_is(note.get("title"), title) and note.get("id"):
            return note
    found = client.call("search", {"query": title, "limit": 10})
    for item in (found or {}).get("notes") or [] if isinstance(found, dict) else []:
        if isinstance(item, dict) and _title_is(item.get("title"), title) and item.get("id"):
            full = client.call("get", {"entity_type": "note", "id_or_query": item["id"], "detail": "full"})
            if isinstance(full, dict) and not full.get("error"):
                return full.get("note") if isinstance(full.get("note"), dict) else full
            return item
    return None


def find_receipt(client, day):
    """The day's receipt note under the display name, else under a former name, or None."""
    for name in known_names():
        note = find_note(client, receipt_title(day, name))
        if note:
            return note
    return None


def decision_tasks(client, include_completed=False):
    """Tasks whose title starts with a decision prefix of any known name. The listing's
    search is a substring search, so the prefix is checked again on each row."""
    out, seen = [], set()
    for name in known_names():
        prefix = decision_prefix(name).lower()
        for r in list_all(client, "task", {"search": decision_prefix(name), "include_completed": include_completed}):
            key = r.get("id") or id(r)
            if key not in seen and str(r.get("title") or "").strip().lower().startswith(prefix):
                seen.add(key)
                out.append(r)
    return out


# --------------------------------------------------------------------------- other skills' scripts

def run_script(argv, timeout=180):
    """Run one command; (exit code, stdout, stderr). Tests replace this."""
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return 124, "", f"{Path(argv[1] if len(argv) > 1 else argv[0]).name}: no answer in {timeout}s"
    except OSError as exc:
        return 127, "", f"{argv[0]}: {exc}"
    return done.returncode, done.stdout or "", done.stderr or ""


def first_line(*texts):
    for text in texts:
        for line in (text or "").splitlines():
            if line.strip():
                return line.strip()
    return ""


# --------------------------------------------------------------------------- the message to the owner

NOTIFY_CAPS = {"receipt": 1, "decision": 3, "backstop": 1}
NOTIFY_FILE = "notify.json"
NOTIFY_MAX = 300


def compose(kind, cycle, verify, base, backstop=0):
    """The message for `kind` ({"title","bullets","link","record_ref"}), {"skip": why}, or None."""
    name = display_name()
    if kind == "backstop":
        return {"title": f"{name} launch backstop {cycle.get('date')}",
                "bullets": [f"{name}: today's backstop of {backstop} orchestrator launches is reached; "
                            "no more launches today unless you start one or raise launch_backstop."],
                "link": f"{base}/tasks" if base else "", "record_ref": None}
    if verify.get("status") not in ("found", "missing"):
        return {"skip": "the Portal could not be checked, so nothing is claimed"}
    if kind == "receipt" and (verify.get("status") != "found" or not verify.get("note_id")
                              or verify.get("this_cycle_written") is not True):
        return {"skip": "no verified receipt note this cycle"}
    n = int(verify.get("decisions_created") or 0)
    if kind == "decision":
        if n < 1:
            return None
        text = f"{name}: {n} decision{'s' if n != 1 else ''} waiting: {verify.get('first_decision') or ''}"
        link = f"{base}/tasks" if base else ""
        ref = f"portal://task/{verify['decision_ids'][0]}" if verify.get("decision_ids") else None
    else:
        text = f"{name} receipt ready: {n} decision{'s' if n != 1 else ''}."
        link = f"{base}/notes/{verify['note_id']}" if base else ""
        ref = f"portal://note/{verify['note_id']}"
    title = f"{name} {'receipt' if kind == 'receipt' else 'decisions'} {cycle.get('date')}"
    text = re.sub(r"https?://\S+", "", text)  # links go in the link line, never in a bullet
    return {"title": title, "bullets": [" ".join(text.split())[:NOTIFY_MAX]], "link": link, "record_ref": ref}


def notify(folder, kind, root, dry_run=False, backstop=0):
    """Send one message to the owner within the daily caps, through comms-reply-to-email's
    notify_owner script. Never raises for a message that did not go."""
    if kind not in NOTIFY_CAPS:
        raise Bad("--kind is receipt, decision or backstop")
    cycle = read_json(Path(folder) / "cycle.json") or {}
    verify = read_json(Path(folder) / "verify.json") or {}
    dry = dry_run or bool(cycle.get("dry_run"))
    base = str(setting("portal_web_url") or "").rstrip("/")
    msg = compose(kind, cycle, verify, base, backstop)
    if msg is None:
        return {"status": "skipped", "kind": kind, "reason": "nothing to alert about"}
    if "skip" in msg:
        return {"status": "skipped", "kind": kind, "reason": msg["skip"]}
    day = local_now().date().isoformat()
    state = read_json(Path(root) / NOTIFY_FILE, default={}) or {}
    sent_today = int((state.get(kind) or {}).get(day, 0))
    if sent_today >= NOTIFY_CAPS[kind]:
        return {"status": "held", "kind": kind, "reason": f"daily cap reached ({sent_today} of {NOTIFY_CAPS[kind]})"}
    mode = os.environ.get("NOTIFY_OWNER_MODE", "").strip().lower()
    if mode == "off":
        return {"status": "skipped", "kind": kind, "reason": "notifications are off (NOTIFY_OWNER_MODE=off)"}
    argv = [sys.executable, str(NOTIFY_SCRIPT), "--title", msg["title"]]
    for bullet in msg["bullets"]:
        argv += ["--bullet", bullet]
    if msg["link"]:
        argv += ["--link", msg["link"]]
    if msg["record_ref"]:
        argv += ["--record-ref", msg["record_ref"]]
    if dry or mode in ("dry-run", "dryrun", "rehearsal"):
        return {"status": "dry_run", "kind": kind, "cap": f"{sent_today}/{NOTIFY_CAPS[kind]}",
                "title": msg["title"], "bullets": msg["bullets"]}
    code, out, err = run_script(argv, 60)
    answer = load_object(out) or {}
    if code != 0 or not answer.get("sent"):
        return {"status": "not_sent", "kind": kind, "reason": flat(answer.get("reason") or first_line(err, out)
                                                                  or f"exit {code}", 200)}
    counts = dict(state.get(kind) or {})
    counts[day] = sent_today + 1
    for stale in sorted(counts)[:-7]:
        counts.pop(stale, None)
    state[kind] = counts
    atomic_json(Path(root) / NOTIFY_FILE, state)
    return {"status": "sent", "kind": kind, "channel": answer.get("channel"), "sent_today": counts[day]}
