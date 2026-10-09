"""What the three task-capture scripts share: settings, the capture sources, the capture
ledger, the task marker and a small Insights Portal client.

THE SOURCES
-----------
Which sources the owner captures from, and where they are, is a setting, never code. The list
comes from `--sources FILE` (YAML, TOML or JSON), else the `sources` list in the
`[task-stack-capture]` table of the owner settings, else the file that table's `sources_file`
names. Each source:

    name      lowercase kebab; the prefix of every item key from it
    kind      said-not-seen | markdown-inbox | folder-inbox | future
    path      a folder or file (not needed for `future`)
    optional  true: a missing file is no items, not an unreadable source
    glob      folder-inbox only; default *.md and *.txt
    note      for `future`: why it is not read yet

- said-not-seen: the time study's `said-not-seen-*.json` files (schema
  `time-study/said-not-seen@1`). An item with status other than `open` is closed at the source.
- markdown-inbox: one markdown file. Every `- [ ] text` and plain `- text` bullet is an item;
  `- [x] text` is closed. A `YYYY-MM-DD` at the start of the line, or in the heading above,
  dates it. The id hashes the date and the text, so an unchanged line is the same item.
- folder-inbox: every matching file in the folder is one item, dated by its modification time.
- future: a source with no read path yet; reported, never read.

Sources are only ever read.

THE CAPTURE LEDGER
------------------
`<state>/capture/CAPTURE-LEDGER.csv`, one row per source item ever seen, written only by
task_capture_record.py. `<state>` is `--state`, else `<state_dir>/task-stack` from the
top-level `state_dir` setting, else `~/.local/state/task-stack` (the folder task-stack-apply
keeps its journal in). States: seen (not yet decided), created, exists, skipped, asked,
expired, closed, stuck. Every state but `seen` is final. `runs.jsonl` beside it has one line
per recorded Run.
"""

import csv
import fcntl
import hashlib
import io
import json
import os
import re
import sys
import tomllib
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit

SECTION = "task-stack-capture"
SAID_SCHEMA = "time-study/said-not-seen@1"
KINDS = ("said-not-seen", "markdown-inbox", "folder-inbox", "future")
NAME = re.compile(r"^[a-z][a-z0-9-]{0,40}$")
TEXT_MAX = 4000
COLUMNS = ("id", "source", "ref", "state", "task", "marker", "item_date", "first_seen", "last_run",
           "attempts", "note", "updated_at", "by")
STATES = ("seen", "created", "exists", "skipped", "asked", "expired", "closed", "stuck")
FINAL = tuple(s for s in STATES if s != "seen")
MAX_ATTEMPTS = 3
SKILL_DIR = Path(__file__).resolve().parents[1]


class Bad(Exception):
    """A bad argument, an unusable sources file or a malformed ledger: exit 2."""


def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


_SECRETS = re.compile(r"(?i)(bearer\s+\S+|authorization[\"'\s:=]+\S+)")


def safe(text):
    """Everything printed passes through here, so a bearer token is never shown."""
    return _SECRETS.sub("[redacted]", str(text))


def source_marker(source):
    """The marker task-stack-apply gives a create that captures one source item: `tsk` and 12
    hex digits of the item's key alone, so the item has one task however its title is worded."""
    return "tsk" + hashlib.sha256(f"source:{source.strip()}".encode("utf-8")).hexdigest()[:12]


def truthy_flag(value):
    """--dry-run-if from a scheduler placeholder: only an unmistakable value is accepted."""
    text = str(value or "").strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    raise Bad(f"--dry-run-if wants true or false, got {value!r}; nothing was written")


def atomic_json(path, value):
    """Write JSON through a temporary file and a rename, so a reader never sees half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def parse_day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def whole_number(value, name, default, low, high):
    """A whole-number option; blank (from a launch form) means the default."""
    text = str(value or "").strip()
    if not text:
        return default
    if not text.isdigit() or not (low <= int(text) <= high):
        raise Bad(f"--{name} wants a whole number from {low} to {high}, got {value!r}")
    return int(text)


def as_of_date(value):
    try:
        return date.fromisoformat(value.strip()) if str(value or "").strip() else date.today()
    except ValueError:
        raise Bad(f"--as-of wants YYYY-MM-DD, got {value!r}") from None


# --------------------------------------------------------------------------- the sources

def _read_structured(path):
    """A YAML, TOML or JSON file. YAML needs the pyyaml package."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".toml":
        return tomllib.loads(text)
    if path.suffix == ".json":
        return json.loads(text)
    import yaml
    return yaml.safe_load(text)


def load_sources(path=""):
    """The validated source list and where it came from."""
    conf = settings(SECTION)
    where = str(path or "").strip() or str(conf.get("sources_file") or "").strip()
    if str(path or "").strip() or ("sources" not in conf and where):
        p = Path(where).expanduser()
        try:
            data = _read_structured(p)
        except Exception as exc:  # any parse error means the file cannot be used
            raise Bad(f"the sources file {p} cannot be read ({type(exc).__name__})") from None
        raw = data.get("sources") if isinstance(data, dict) else data
        origin = str(p)
    else:
        raw = conf.get("sources")
        origin = f"settings [{SECTION}]"
    if raw is None:
        raise Bad(f"no capture sources: give --sources FILE, or set `sources` or `sources_file` "
                  f"in the [{SECTION}] settings")
    if not isinstance(raw, list):
        raise Bad(f"{origin}: `sources` must be a list")
    out = []
    for i, s in enumerate(raw, 1):
        if not isinstance(s, dict):
            raise Bad(f"{origin}: source {i} is not a mapping")
        name, kind = str(s.get("name") or ""), str(s.get("kind") or "")
        if not NAME.match(name):
            raise Bad(f"{origin}: source {i}: name {name!r} is not lowercase kebab")
        if kind not in KINDS:
            raise Bad(f"{origin}: source {name}: kind {kind!r} is not one of {', '.join(KINDS)}")
        if kind != "future" and not str(s.get("path") or "").strip():
            raise Bad(f"{origin}: source {name}: path is required")
        out.append({"name": name, "kind": kind, "path": str(s.get("path") or "").strip(),
                    "optional": bool(s.get("optional", False)), "glob": s.get("glob"),
                    "note": str(s.get("note") or "")})
    names = [s["name"] for s in out]
    if len(set(names)) != len(names):
        raise Bad(f"{origin}: a source name appears twice")
    return out, origin


def _hash(*parts):
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]


def _item(source, item_id, **fields):
    key = f"{source['name']}:{item_id}"
    item = {"key": key, "source": source["name"], "kind": source["kind"], "ref": None, "date": None,
            "time": None, "text": "", "quote": None, "to": None, "by": None, "domain": None,
            "recording_id": None, "open": True}
    item.update(fields)
    item["text"] = str(item["text"] or "")[:TEXT_MAX]
    item["marker"] = source_marker(key)
    return item


def read_said_not_seen(source):
    path = Path(source["path"]).expanduser()
    files = sorted(path.glob("said-not-seen-*.json")) if path.is_dir() else [path]
    items = {}
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema") != SAID_SCHEMA:
            raise ValueError(f"{f.name} is not a {SAID_SCHEMA} file")
        window = str(data.get("window") or f.stem)
        for it in data.get("items") or []:
            if not isinstance(it, dict) or not re.fullmatch(r"[0-9a-f]{6,40}", str(it.get("id") or "")):
                continue
            text = it.get("commitment") or it.get("text") or it.get("quote") or ""
            items[str(it["id"])] = _item(
                source, str(it["id"]), ref=f"{window}#{it.get('ref') or ''}", date=it.get("date"),
                time=it.get("time"), text=text, quote=it.get("quote"), to=it.get("to"), by=it.get("by"),
                domain=it.get("domain"), recording_id=it.get("recording_id"),
                open=str(it.get("status") or "open") == "open", full_text=it.get("text"),
                why_not_seen=it.get("why_not_seen"))
    return list(items.values())


HEAD_DATE = re.compile(r"^#{1,6}\s.*?(\d{4}-\d{2}-\d{2})")
BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(?:\[( |x|X)\]\s+)?(.*\S)\s*$")
LEAD_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})\s*[:\-–]?\s*(.*)$")


def read_markdown_inbox(source):
    path = Path(source["path"]).expanduser()
    if not path.exists() and source["optional"]:
        return []
    items, heading_date = {}, None
    for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        h = HEAD_DATE.match(line)
        if h:
            heading_date = h.group(1)
            continue
        if line.lstrip().startswith("#"):
            heading_date = None
            continue
        m = BULLET.match(line)
        if not m:
            continue
        box, text = m.group(1), m.group(2).strip()
        day = heading_date
        d = LEAD_DATE.match(text)
        if d:
            day, text = d.group(1), d.group(2).strip()
        if not text:
            continue
        item_id = _hash(day or "", " ".join(text.lower().split()))
        items.setdefault(item_id, _item(source, item_id, ref=f"{path.name}:{n}", date=day, text=text,
                                        open=box not in ("x", "X")))
    return list(items.values())


def read_folder_inbox(source):
    path = Path(source["path"]).expanduser()
    if not path.exists() and source["optional"]:
        return []
    if not path.is_dir():
        raise ValueError(f"{path} is not a folder")
    globs = source["glob"] or ["*.md", "*.txt"]
    globs = [globs] if isinstance(globs, str) else list(globs)
    files = sorted({p for g in globs for p in path.glob(str(g)) if p.is_file() and not p.name.startswith(".")})
    out = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            continue
        day = datetime.fromtimestamp(f.stat().st_mtime).date().isoformat()
        item_id = _hash(f.name, hashlib.sha1(text.encode("utf-8")).hexdigest())
        out.append(_item(source, item_id, ref=f.name, date=day, text=text))
    return out


READERS = {"said-not-seen": read_said_not_seen, "markdown-inbox": read_markdown_inbox,
           "folder-inbox": read_folder_inbox}


def gather(sources, only=""):
    """Every item of every source (or only the one named), and one report per source. A source
    that cannot be read is reported with its error; the others are still read."""
    items, reports = [], []
    for s in sources:
        if only and s["name"] != only:
            continue
        report = {"name": s["name"], "kind": s["kind"], "path": s["path"] or None, "readable": None,
                  "error": None, "items": 0, "open": 0, "note": s["note"] or None}
        if s["kind"] == "future":
            report["note"] = s["note"] or "not reachable yet"
        else:
            try:
                got = READERS[s["kind"]](s)
            except (OSError, ValueError, UnicodeError) as exc:
                report.update(readable=False, error=f"{type(exc).__name__}: {exc}")
            else:
                report.update(readable=True, items=len(got), open=sum(1 for i in got if i["open"]))
                items += got
        reports.append(report)
    return items, reports


# --------------------------------------------------------------------------- state and ledger

def state_root(explicit=""):
    """The capture folder inside the task-stack state folder: `--state`, else
    `<state_dir>/task-stack` from the shared `state_dir` setting (the folder task_stack_apply.py uses)."""
    if str(explicit or "").strip():
        base = Path(explicit).expanduser()
    elif settings().get("state_dir"):
        base = Path(settings()["state_dir"]).expanduser() / "task-stack"
    else:
        raise Bad("setting state_dir is needed (the folder where the task stack keeps its state), or pass --state")
    return base / "capture"


def ledger_path(root):
    return root / "CAPTURE-LEDGER.csv"


def read_ledger(root):
    """The ledger's rows keyed by id (the first row of an id wins). A missing file is empty."""
    path = ledger_path(root)
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8").lstrip("\ufeff")  # drop a byte-order mark
    reader = csv.reader(io.StringIO(text, newline=""))
    header = next(reader, None)
    if header is None:
        return {}
    if [h.strip() for h in header] != list(COLUMNS):
        raise Bad(f"{path.name} does not start with the header {','.join(COLUMNS)}")
    rows = {}
    for cells in reader:
        row = {c: (v or "").strip() for c, v in zip(COLUMNS, cells)}
        if row.get("id") and row["id"] not in rows:
            rows[row["id"]] = row
    return rows


def write_ledger(root, updates):
    """Upsert rows by id: a field not given keeps its value, nothing is ever deleted, and the
    file is replaced atomically. `updates` maps id to the fields to set."""
    rows = read_ledger(root)
    for key, values in updates.items():
        if values.get("state") not in STATES:
            raise Bad(f"--state {values.get('state')!r} is not one of {', '.join(STATES)}")
        row = rows.get(key) or {c: "" for c in COLUMNS}
        row.update({k: "" if v is None else str(v) for k, v in values.items() if k in COLUMNS})
        row["id"] = key
        rows[key] = row
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(COLUMNS)
    for row in rows.values():
        writer.writerow([row.get(c, "") for c in COLUMNS])
    path = ledger_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(buffer.getvalue(), encoding="utf-8")
    if path.exists():
        os.chmod(tmp, path.stat().st_mode & 0o777)
    os.replace(tmp, path)
    return path


def last_run(root):
    """The newest Run recorded live (dry Runs do not count), or None."""
    path = root / "runs.jsonl"
    done = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and not row.get("dry_run") and row.get("started_at"):
                done.append(row)
    return max(done, key=lambda r: str(r["started_at"])) if done else None


@contextmanager
def locked(root):
    """Hold the capture lock, so two records never interleave."""
    root.mkdir(parents=True, exist_ok=True)
    with (root / "record.lock").open("a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def guard_run_path(path):
    """A Run folder never lives inside this skill's own folder: no state beside the code."""
    target = Path(path).expanduser().resolve()
    if target == SKILL_DIR or SKILL_DIR in target.parents:
        raise Bad(f"{target} is inside the skill folder; Run folders live outside it")
    return target


# --------------------------------------------------------------------------- the Portal

class PortalError(Exception):
    """The Portal could not be reached or refused a call."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect, so the bearer token only ever goes to the configured URL."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def portal_endpoint(config=None, server=None):
    """(url, Authorization header) from the MCP config the `portal_mcp_config` setting names.
    The token is INSIGHTS_PORTAL_ASSISTANT_TOKEN when set, else the config's Authorization
    header with ${VAR} expanded from the environment. HTTPS only, except HTTP to localhost."""
    conf = settings()
    config = config or conf.get("portal_mcp_config")
    server = server or conf.get("portal_server") or "insights-portal"
    if not config:
        raise PortalError("setting portal_mcp_config is needed (the MCP config holding the Portal server)")
    try:
        entry = json.loads(Path(config).expanduser().read_text())["mcpServers"][server]
    except (OSError, KeyError, TypeError, ValueError):
        raise PortalError(f"the MCP config has no usable server named {server!r}") from None
    token = os.environ.get("INSIGHTS_PORTAL_ASSISTANT_TOKEN", "").strip()
    auth = f"Bearer {token}" if token else (entry.get("headers") or {}).get("Authorization", "")

    def expand(value, what):
        def one(match):
            if not os.environ.get(match.group(1)):
                raise PortalError(f"the Portal {what} needs {match.group(1)}, which is not set")
            return os.environ[match.group(1)]
        value = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", one, value or "")
        if "${" in value or "\n" in value:
            raise PortalError(f"the Portal {what} is malformed")
        return value

    url, auth = expand(entry.get("url", ""), "URL"), expand(auth, "token")
    parts = urlsplit(url)
    local = parts.hostname in ("localhost", "127.0.0.1", "::1")
    if not parts.hostname or not (parts.scheme == "https" or (parts.scheme == "http" and local)):
        raise PortalError("the Portal URL must be HTTPS (HTTP only on localhost)")
    if not auth.startswith("Bearer ") or not auth[7:].strip():
        raise PortalError("no Portal bearer token: set INSIGHTS_PORTAL_ASSISTANT_TOKEN or put one in the config")
    return url, auth


class Portal:
    """A small JSON-RPC client for the Portal's MCP tools, read only here: `call` for whoami,
    `list_all` for every page of list_entities."""

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
            raise PortalError(f"portal {tool}: HTTP {exc.code}") from None
        except (urllib.error.URLError, OSError) as exc:
            raise PortalError(f"portal {tool}: {getattr(exc, 'reason', type(exc).__name__)}") from None
        messages = []
        for line in ([raw] if raw.lstrip().startswith("{") else
                     [l[5:] for l in raw.splitlines() if l.startswith("data:")]):
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if not messages:
            raise PortalError(f"portal {tool}: empty response")
        out = messages[-1]
        if "error" in out:
            raise PortalError(f"portal {tool}: {out['error']}")
        result = out.get("result", out)
        if isinstance(result, dict) and "content" in result:
            text = "\n".join(c.get("text", "") for c in result["content"] if c.get("type") == "text")
            if result.get("isError"):
                raise PortalError(f"portal {tool}: {text[:300]}")
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        return result

    def list_all(self, entity_type, filters=None, max_pages=50):
        """Every item of one entity type, following next_offset until has_more is false."""
        args = {"entity_type": entity_type, "limit": 200}
        if filters:
            args["filters"] = filters
        items, offset = [], 0
        for _ in range(max_pages):
            if offset:
                args["offset"] = offset
            out = self.call("list_entities", args)
            if not isinstance(out, dict):
                break
            items.extend(i for i in out.get("items") or [] if isinstance(i, dict))
            nxt = out.get("next_offset")
            if not out.get("has_more") or not isinstance(nxt, int) or nxt <= offset:
                break
            offset = nxt
        return items


def fail(message, code=2):
    """One line on stderr and a non-zero exit."""
    print(safe(f"ERROR {message}"), file=sys.stderr)
    sys.exit(code)
