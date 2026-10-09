"""What the issue-harvest scripts share: settings, the repo map, the ledger, the markers, the
Portal and GitHub reads, and the source gathering.

The issue harvest turns what people say about the owner's software (email, Portal notes and
tasks, said-but-not-seen commitments) into GitHub issues on the right repository. Which
repositories, which sources and where they live are the owner's settings, never this code's.

SETTINGS (table [issue-harvest-workstream] in the owner settings file)

    repos_file = "<the repo map, below>"          # required, no default
    state = "<the state folder>"                   # default: <state_dir>/issue-harvest
    horizon_days = 14                              # the furthest back a Run reads
    closed_days = 30                               # "recently closed" for the dedupe snapshot
    public_denylist_files = ["<file>", ...]        # private names refused in a public repository
    private_terms = ["<term>", ...]                # refused on every repository, whole word, any case
    [issue-harvest-workstream.source_links]        # optional link template per source, {id}
    [issue-harvest-workstream.sources.portal_notes]   enabled, exclude_titles, max_fetch
    [issue-harvest-workstream.sources.portal_email]   enabled, exclude_senders, exclude_subjects
    [issue-harvest-workstream.sources.portal_tasks]   enabled
    [issue-harvest-workstream.sources.said_not_seen]  enabled, path (folder of said-not-seen-*.json)

The Portal connection is the shared `portal_mcp_config` (and `portal_server`) setting.

THE REPO MAP (YAML, JSON or TOML), a list under `repos`, each entry:

    repo: example-org/widgets      # owner/name on GitHub
    product: Widget portal         # what people call it
    public: false                  # a public repo gets the private-names scan
    harvest: true                  # may the harvest file here (the allowlist)
    labels: {bug: [bug], feature: [enhancement], always: [agent-filed]}
    title: {convention: "WID-YYYYMMDD-CODE: summary", pattern: '^WID-\\d{8}-[A-Z0-9]{3,12}: .+'}
    terms: [widget portal]         # words that tie a source item to this repo
    portal_projects: [<Portal project id>]
    reporters: [tester@example.com]

MARKERS. Every issue or comment the harvest files carries `<!-- issue-harvest:<hash> -->`, the
first 12 hex digits of the SHA-1 of the source item's key, so nothing is filed twice.

THE LEDGER. `<state>/HARVEST-LEDGER.csv`, one row per source item a Run has seen, written only by
issue_harvest_record.py. States: seen (not decided yet), filed, commented, duplicate,
not-software, asked, stuck (refused or failed on three Runs). Every state but seen is final.
`runs.jsonl` beside it holds one line per recorded Run.
"""

from __future__ import annotations

import csv
import fcntl
import io
import hashlib
import json
import os
import re
import shlex
import subprocess
import tempfile
import tomllib
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

SKILL = "issue-harvest-workstream"
HORIZON_DEFAULT = 14
CLOSED_DAYS_DEFAULT = 30
MARKER_PREFIX = "issue-harvest:"
REPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]{1,100}$")
COLUMNS = ("id", "source", "ref", "state", "repo", "issue", "url", "verified", "marker", "item_date",
           "first_seen", "last_run", "attempts", "note", "updated_at", "by")
STATES = ("seen", "filed", "commented", "duplicate", "not-software", "asked", "stuck")
FINAL = tuple(s for s in STATES if s != "seen")
WRITTEN = ("filed", "commented")
MAX_ATTEMPTS = 3
SAID_SCHEMA = "time-study/said-not-seen@1"
TEXT_MAX = 6000
BODY_SNAPSHOT = 1200
SEARCH_LIMIT = 50
SOURCES = ("portal-notes", "portal-email", "portal-tasks", "said-not-seen")
SETTING_KEYS = {"portal-notes": "portal_notes", "portal-email": "portal_email",
                "portal-tasks": "portal_tasks", "said-not-seen": "said_not_seen"}
LIST_LIMIT = 1000

# What may never leave in an issue: home folders and anything shaped like a secret.
TITLE_MAX = 200
BODY_MAX = 60000
SECRETS = re.compile(r"(?i)(bearer\s+\S+|authorization[\"'\s:=]+\S+|[?&](?:key|token|api_key|access_token)=[^\s&\"']+)")
PRIVATE = [
    ("a Windows user folder", re.compile(r"(?i)(/mnt/c/Users/|\b[a-z]:\\+Users\\+)")),
    ("a home-directory path", re.compile(r"(/home/[a-z_][a-z0-9_-]*/|/Users/[A-Za-z][A-Za-z0-9._-]*/)")),
    ("a secret (bearer or token in a URL)", SECRETS),
    ("a secret (token shape)", re.compile(
        r"(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|\bsk-[A-Za-z0-9_-]{20,}"
        r"|\bAKIA[0-9A-Z]{16}\b|\bxox[abprs]-[A-Za-z0-9-]{10,}"
        r"|-----BEGIN [A-Z ]*PRIVATE KEY-----|\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.)")),
    ("a secret (assignment)", re.compile(
        r"(?i)\b(password|passwd|secret|client_secret|api[_-]?key|access[_-]?token|auth[_-]?token)\b"
        r"\s*[:=]\s*[\"']?[^\s\"']{6,}")),
]


class ConfigError(Exception):
    """Settings or a repo map that cannot be used: the script exits 2."""


class GitHubError(Exception):
    """A gh command failed."""


def safe(text):
    """Anything on its way to output passes through here, so no bearer or token is printed."""
    return SECRETS.sub("[redacted]", str(text))


def err_text(exc):
    return safe(f"{type(exc).__name__}: {exc}")[:300]


# ------------------------------------------------------------------------------ settings

def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"the settings file {path} cannot be read ({type(exc).__name__})") from None
    return data.get(section, {}) if section else data


def harvest_settings():
    return settings(SKILL)


def state_root(cfg, explicit=""):
    """The state folder: --state, else the skill's `state`, else <state_dir>/issue-harvest."""
    where = explicit or cfg.get("state")
    if not where and settings().get("state_dir"):
        where = str(Path(str(settings()["state_dir"])) / "issue-harvest")
    if not where:
        raise ConfigError(f"no state folder: pass --state, or set `state` under [{SKILL}] or `state_dir`"
                          " in the settings file")
    return Path(str(where)).expanduser()


def as_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value if v is not None and str(v).strip()]


def read_map_file(path):
    """A YAML, JSON or TOML file as data."""
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            return json.loads(text)
        if path.suffix == ".toml":
            return tomllib.loads(text)
        import yaml  # only the YAML repo map needs pyyaml
        return yaml.safe_load(text)
    except Exception as exc:  # noqa: BLE001 - any unreadable map is a settings error
        raise ConfigError(f"the repo map {path} cannot be read ({type(exc).__name__})") from None


def load_repos(cfg, explicit=""):
    """The repo map, validated; every entry gets every key, so callers never guess."""
    where = (explicit or "").strip() or str(cfg.get("repos_file") or "")
    if not where:
        raise ConfigError(f"no repo map: pass --repos-file, or set `repos_file` under [{SKILL}] in the settings file")
    path = Path(where).expanduser()
    data = read_map_file(path)
    raw = data.get("repos") if isinstance(data, dict) else None
    if not isinstance(raw, list) or not raw:
        raise ConfigError(f"{path}: `repos` must be a non-empty list")
    out, seen = [], set()
    for i, r in enumerate(raw, 1):
        if not isinstance(r, dict):
            raise ConfigError(f"{path}: entry {i} is not a mapping")
        repo = str(r.get("repo") or "").strip()
        if not REPO_RE.match(repo):
            raise ConfigError(f"{path}: entry {i}: repo {repo!r} is not owner/name")
        if repo.lower() in seen:
            raise ConfigError(f"{path}: {repo} appears twice")
        seen.add(repo.lower())
        labels = r.get("labels") or {}
        if not isinstance(labels, dict):
            raise ConfigError(f"{path}: {repo}: labels must be a mapping of kind to labels")
        title = r.get("title") or {}
        if isinstance(title, str):
            title = {"convention": title}
        pattern = str(title.get("pattern") or "")
        if pattern:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ConfigError(f"{path}: {repo}: title pattern does not compile ({exc})") from None
        out.append({
            "repo": repo, "product": str(r.get("product") or repo.split("/", 1)[1]),
            "public": bool(r.get("public", False)), "harvest": bool(r.get("harvest", False)),
            "triage_owner": str(r.get("triage_owner") or "") or None,
            "labels": {str(k): as_list(v) for k, v in labels.items()},
            "title": {"convention": str(title.get("convention") or ""), "pattern": pattern},
            "terms": as_list(r.get("terms")), "portal_projects": as_list(r.get("portal_projects")),
            "reporters": [a.lower() for a in as_list(r.get("reporters"))],
            "note": str(r.get("note") or ""),
        })
    return out


def repo_entry(repos, name):
    return next((r for r in repos if r["repo"].lower() == str(name or "").strip().lower()), None)


def whole_number(value, name, default, low, high):
    """A form value: blank means the default; otherwise a whole number in range."""
    text = str(value if value is not None else "").strip()
    if not text:
        return default
    if not text.isdigit() or not (low <= int(text) <= high):
        raise ValueError(f"--{name} wants a whole number from {low} to {high}, got {value!r}")
    return int(text)


def truthy(value):
    return str(value or "").strip().lower() in ("1", "true", "yes", "on", "y")


# ------------------------------------------------------------------------------ markers

def part_key(key, part=None):
    """The marker key of one part of a source item (`<key>#<part>`), or the item's own key."""
    part = str(part or "").strip()
    return f"{key}#{part}" if part else str(key)


def key_hash(key):
    return hashlib.sha1(str(key).encode("utf-8")).hexdigest()[:12]


def marker(key):
    return f"<!-- {MARKER_PREFIX}{key_hash(key)} -->"


def has_marker(text, key):
    return f"{MARKER_PREFIX}{key_hash(key)}" in str(text or "")


# ------------------------------------------------------------------------------ files, ledger, runs

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_time(value):
    if not value:
        return None
    text = str(value).strip()
    if len(text) == 10:
        text += "T00:00:00+00:00"
    try:
        when = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def load_json(path):
    """A JSON object from a file, or None when it is missing or not an object."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def write_new(path, data):
    """Write JSON to a file that must not exist yet: a Run's evidence is never overwritten."""
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"{path} exists; it is never overwritten")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def ledger_path(root):
    return Path(root) / "HARVEST-LEDGER.csv"


def ledger_rows(root):
    """The ledger's rows in file order (first row of an id wins); a missing file is empty."""
    path = ledger_path(root)
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8").lstrip("\ufeff")  # a leading byte-order mark is not a column
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if [c.strip() for c in reader.fieldnames or []] != list(COLUMNS):
        raise ConfigError(f"{path} does not start with the header {','.join(COLUMNS)}")
    out, seen = [], set()
    for raw in reader:
        row = {k: (v or "").strip() for k, v in raw.items() if k}
        if row.get("id") and row["id"] not in seen:
            seen.add(row["id"])
            out.append(row)
    return out


def ledger_book(root):
    return {r["id"]: r for r in ledger_rows(root)}


def ledger_upsert(root, updates):
    """Create or update rows by id (fields not given keep their value), never delete one, and
    write the file atomically. `updates` is a list of dicts that each carry `id`."""
    rows = ledger_rows(root)
    index = {r["id"]: r for r in rows}
    for u in updates:
        state = u.get("state", index.get(u["id"], {}).get("state", ""))
        if state not in STATES:
            raise ValueError(f"ledger state {state!r} is not one of {', '.join(STATES)}")
        unknown = [k for k in u if k not in COLUMNS]
        if unknown:
            raise ValueError(f"not a ledger column: {', '.join(unknown)}")
        row = index.get(u["id"])
        if row is None:
            row = {c: "" for c in COLUMNS}
            rows.append(row)
            index[u["id"]] = row
        row.update({k: "" if v is None else str(v) for k, v in u.items()})
    path = ledger_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(COLUMNS), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in COLUMNS})
    os.replace(tmp, path)


def runs(root):
    path = Path(root) / "runs.jsonl"
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def last_run(root):
    done = [r for r in runs(root) if not r.get("dry_run") and r.get("started_at")]
    return max(done, key=lambda r: str(r["started_at"])) if done else None


@contextmanager
def locked(root):
    """One recorder at a time on a state folder."""
    Path(root).mkdir(parents=True, exist_ok=True)
    with (Path(root) / "record.lock").open("a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


# ------------------------------------------------------------------------------ GitHub through gh

def gh(*args, input=None, timeout=300):
    """Run gh (or the program the GH environment variable names); returns (code, stdout, stderr)."""
    argv = shlex.split(os.environ.get("GH", "").strip() or "gh") + [str(a) for a in args]
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, input=input)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", f"could not run {argv[0]}: {exc}"
    return out.returncode, out.stdout or "", out.stderr or ""


def gh_ok(what, *args, input=None):
    code, out, err = gh(*args, input=input)
    if code != 0:
        tail = " ".join((err or out or "").strip().splitlines()[-3:]) or f"exit {code}"
        raise GitHubError(f"{what} failed: {tail}")
    return out


def gh_json(what, *args):
    text = gh_ok(what, *args).strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError as exc:
        raise GitHubError(f"{what} returned something other than JSON: {exc}") from None


def label_names(items):
    return sorted(str(i.get("name") if isinstance(i, dict) else i) for i in items or [] if i)


class Repo:
    """What the harvest reads of one repository, read once per Run."""

    def __init__(self, name):
        self.name = name
        self._issues = None
        self._labels = None

    def issues(self):
        if self._issues is None:
            rows = gh_json("gh issue list", "issue", "list", "-R", self.name, "--state", "all", "--limit",
                           str(LIST_LIMIT), "--json", "number,title,body,state,url") or []
            if len(rows) >= LIST_LIMIT:
                raise GitHubError(f"{self.name} has {LIST_LIMIT} or more issues; cannot establish marker coverage")
            self._issues = [r for r in rows if isinstance(r, dict)]
        return self._issues

    def labels(self):
        if self._labels is None:
            rows = gh_json("gh label list", "label", "list", "-R", self.name, "--limit", "200", "--json", "name") or []
            self._labels = [str(r.get("name")) for r in rows if isinstance(r, dict)]
        return self._labels

    def with_marker(self, key):
        return next((i for i in self.issues() if has_marker(i.get("body"), key)), None)

    def open_titled(self, title):
        t = " ".join(title.split()).lower()
        return next((i for i in self.issues() if str(i.get("state") or "").upper() == "OPEN"
                     and " ".join(str(i.get("title") or "").split()).lower() == t), None)

    def view(self, number):
        return gh_json("gh issue view", "issue", "view", str(number), "-R", self.name, "--json",
                       "number,title,body,state,url,labels,comments") or {}


# ------------------------------------------------------------------------------ the Portal (read only)

class Portal:
    """A small JSON-RPC client for the Insights Portal MCP. Read calls only; never follows a redirect."""

    def __init__(self, url, auth, timeout=60):
        self.url, self._auth, self.timeout, self._id = url, auth, timeout, 0

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
            raise RuntimeError(f"portal {tool}: HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"portal {tool}: {type(exc).__name__}") from None
        messages = []
        if raw.lstrip().startswith("{"):
            messages.append(json.loads(raw))
        else:
            for line in raw.splitlines():
                if line.startswith("data:"):
                    try:
                        messages.append(json.loads(line[5:].strip()))
                    except ValueError:
                        continue
        if not messages:
            raise RuntimeError(f"portal {tool}: empty response")
        out = messages[-1]
        if "error" in out:
            raise RuntimeError(f"portal {tool}: {safe(out['error'])[:200]}")
        result = out.get("result", out)
        if isinstance(result, dict) and "content" in result:
            text = "\n".join(c.get("text", "") for c in result["content"] if c.get("type") == "text")
            if result.get("isError"):
                raise RuntimeError(f"portal {tool}: {safe(text)[:300]}")
            try:
                return json.loads(text)
            except ValueError:
                return text
        return result

    def list_entities(self, entity_type, filters=None, max_pages=50):
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


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # refused, so the bearer is never sent anywhere else


_OPENER = urllib.request.build_opener(_NoRedirect)


def portal_client():
    """The Portal client from the `portal_mcp_config` setting; the bearer from
    INSIGHTS_PORTAL_ASSISTANT_TOKEN, else the config's Authorization header with ${VAR} expanded."""
    shared = settings()
    config = str(shared.get("portal_mcp_config") or "")
    if not config:
        raise ConfigError("the Portal needs the setting `portal_mcp_config` (the MCP config file)")
    server = str(shared.get("portal_server") or "insights-portal")
    try:
        cfg = json.loads(Path(config).expanduser().read_text(encoding="utf-8"))["mcpServers"][server]
    except (OSError, ValueError, KeyError, TypeError):
        raise ConfigError(f"the Portal config has no usable mcpServers entry named {server!r}") from None
    token = os.environ.get("INSIGHTS_PORTAL_ASSISTANT_TOKEN", "").strip()
    auth = f"Bearer {token}" if token else str((cfg.get("headers") or {}).get("Authorization") or "")
    url = str(cfg.get("url") or "")

    def expand(value, what):
        def one(m):
            if not os.environ.get(m.group(1)):
                raise ConfigError(f"the Portal {what} needs {m.group(1)}, which is not set")
            return os.environ[m.group(1)]
        return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", one, value)

    url, auth = expand(url, "URL"), expand(auth, "token")
    parts = urlsplit(url)
    local = parts.hostname in ("localhost", "127.0.0.1", "::1")
    if not parts.hostname or not (parts.scheme == "https" or (parts.scheme == "http" and local)):
        raise ConfigError("the Portal URL must be HTTPS (HTTP only on localhost)")
    if not auth.startswith("Bearer ") or not auth[7:].strip():
        raise ConfigError("no Portal bearer token: set INSIGHTS_PORTAL_ASSISTANT_TOKEN or put one in the config")
    return Portal(url, auth)


def open_client():
    """(client, None), or (None, why) when the Portal cannot be set up; never a crash."""
    try:
        return portal_client(), None
    except Exception as exc:  # noqa: BLE001 - reported as unreadable sources
        return None, err_text(exc)


# ------------------------------------------------------------------------------ gathering source items

def term_re(term):
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(term.strip()) + r"(?![A-Za-z0-9])", re.IGNORECASE)


def match_repos(item, repos):
    """Which repositories a source item is about, and why: a hint, never a decision."""
    text = " ".join(str(item.get(k) or "") for k in ("title", "text"))
    links = " ".join(str(x) for x in item.get("links") or [])
    sender = str(item.get("from") or "").lower()
    hints = []
    for r in repos:
        why = [f"term: {t}" for t in r["terms"] if t.strip() and term_re(t).search(text)]
        why += [f"project: {p}" for p in r["portal_projects"] if p and p in links]
        if sender and any(a and a in sender for a in r["reporters"]):
            why.append("reporter")
        why += [f"search: {t}" for t in item.get("search_terms") or [] if t in r["terms"]]
        if why:
            hints.append({"repo": r["repo"], "why": sorted(set(why))})
    return hints


def excluded(value, patterns):
    return any(re.search(p, value or "", re.IGNORECASE) for p in patterns)


def in_window(value, since, until):
    when = parse_time(value)
    return when is not None and since <= when < until


def new_item(source, ident, **fields):
    key = f"{source}:{ident}"
    item = {"key": key, "source": source, "ref": None, "date": None, "time": None, "title": "",
            "text": "", "from": None, "links": [], "search_terms": []}
    item.update(fields)
    item["text"] = str(item.get("text") or "")[:TEXT_MAX]
    item["marker"] = marker(key)
    return item


def read_notes(client, cfg, since, until, full=True):
    """Notes in the window, each read in full unless `full` is false (the precheck's cheap pass)."""
    patterns = as_list(cfg.get("exclude_titles"))
    cap = int(cfg.get("max_fetch") or 300)
    out = []
    for row in client.list_entities("note", {"since": since.isoformat()}):
        if not row.get("id") or excluded(str(row.get("title") or ""), patterns):
            continue
        when = row.get("updated_at") or row.get("created_at")
        if not in_window(when, since, until):
            continue
        content, links = str(row.get("content_preview") or ""), []
        if full and len(out) < cap:
            got = client.call("get", {"entity_type": "note", "id_or_query": row["id"], "detail": "full"})
            if isinstance(got, dict) and isinstance(got.get("note"), dict):
                got = got["note"]
            if isinstance(got, dict):
                content = str(got.get("content") or content)
                links = [json.dumps(got.get("associations"), default=str), str(got.get("calendar_event_id") or "")]
        out.append(new_item("portal-notes", str(row["id"]), ref=f"portal://note/{row['id']}", date=str(when)[:10],
                            time=when, title=str(row.get("title") or ""), text=content, links=links))
    return out


def read_email(client, cfg, since, until):
    """Inbound and sent mail in the window, each with its body where the Portal has one."""
    senders, subjects = as_list(cfg.get("exclude_senders")), as_list(cfg.get("exclude_subjects"))
    out = []
    for direction in ("received", "sent"):
        rows = client.list_entities("email", {"since": since.isoformat(), "until": until.isoformat(),
                                              "direction": direction})
        for row in rows:
            if not row.get("id") or not in_window(row.get("received_at"), since, until):
                continue
            sender = str(row.get("from_address") or "").lower()
            if direction == "received" and excluded(sender, senders):
                continue
            if excluded(str(row.get("subject") or ""), subjects):
                continue
            out.append(new_item("portal-email", str(row["id"]), ref=f"portal://email/{row['id']}",
                                date=str(row.get("received_local") or row.get("received_at") or "")[:10],
                                time=row.get("received_at"), title=str(row.get("subject") or ""),
                                text=str(row.get("summary") or ""), direction=direction,
                                to=[str(a).lower() for a in row.get("to_addresses") or []],
                                links=[str(row.get("contact_id") or "")], **{"from": sender}))
    # The listing's summary is often empty: take each body from email_bodies, 50 ids a call.
    ids = [i["key"].split(":", 1)[1] for i in out]
    found = {}
    for start in range(0, len(ids), 50):
        try:
            got = client.call("email_bodies", {"ids": ids[start:start + 50]})
        except Exception:  # noqa: BLE001 - a body that cannot be read leaves the summary
            continue
        for row in (got.get("items") or []) if isinstance(got, dict) else []:
            if isinstance(row, dict) and row.get("found") and str(row.get("body") or "").strip():
                found[str(row.get("id"))] = str(row["body"])
    for item, ident in zip(out, ids):
        if ident in found:
            item["text"], item["text_source"] = found[ident][:TEXT_MAX], "body"
        else:
            item["text_source"] = "summary" if item.get("text") else "none"
    return out


def search_hits(client, repos):
    """Note and email ids the Portal's full-text search finds for each repo term."""
    hits = {}
    for term in sorted({t for r in repos for t in r["terms"] if t.strip()}):
        out = client.call("search", {"query": f'"{term}"' if " " in term else term, "limit": SEARCH_LIMIT})
        if not isinstance(out, dict):
            continue
        for kind in ("notes", "emails"):
            for row in out.get(kind) or []:
                if isinstance(row, dict) and row.get("id"):
                    hits.setdefault(f"{kind}:{row['id']}", []).append(term)
    return hits


def read_tasks(client, repos, since, until):
    out = {}
    for r in repos:
        for project in r["portal_projects"]:
            for row in client.list_entities("task", {"project_id": project, "include_completed": True}):
                if not row.get("id") or not in_window(row.get("created_at"), since, until):
                    continue
                item = new_item("portal-tasks", str(row["id"]), ref=f"portal://task/{row['id']}",
                                date=str(row.get("created_at") or "")[:10], time=row.get("created_at"),
                                title=str(row.get("title") or ""), text=str(row.get("description") or ""),
                                status=row.get("status"), links=[project])
                out.setdefault(item["key"], item)
    return list(out.values())


def read_said(cfg, since, until):
    """Open said-but-not-seen commitments (time-study/said-not-seen@1 files) dated in the window."""
    path = str(cfg.get("path") or "").strip()
    if not path:
        raise ValueError("said_not_seen.path is not set")
    folder = Path(path).expanduser()
    if not folder.exists():
        raise ValueError(f"{path} does not exist")
    files = sorted(folder.glob("said-not-seen-*.json")) if folder.is_dir() else [folder]
    latest = {}   # id: (window, item); a later file's copy of an item replaces an earlier one's
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema") != SAID_SCHEMA:
            raise ValueError(f"{f.name} is not a {SAID_SCHEMA} file")
        window = str(data.get("window") or f.stem)
        for it in data.get("items") or []:
            ident = str(it.get("id") or "") if isinstance(it, dict) else ""
            if re.fullmatch(r"[0-9a-f]{6,40}", ident):
                latest[ident] = (window, it)
    items = []
    for ident, (window, it) in latest.items():
        day = parse_time(it.get("date"))
        # Closed in its latest copy, or dated outside the window: not a candidate.
        if str(it.get("status") or "open") != "open" or day is None or not (since.date() <= day.date() <= until.date()):
            continue
        text = it.get("commitment") or it.get("text") or it.get("quote") or ""
        items.append(new_item(
            "said-not-seen", ident, ref=f"{window}#{it.get('ref') or ''}", date=it.get("date"),
            time=f"{it.get('date')}T{it.get('time') or '00:00:00'}", title=str(text)[:200],
            text="\n".join(str(x) for x in (text, it.get("quote"), it.get("text"), it.get("why_not_seen")) if x),
            to=it.get("to"), by=it.get("by"), domain=it.get("domain"), recording_id=it.get("recording_id")))
    return items


def gather(client, cfg, repos, since, until, full=True):
    """Every candidate source item in the window, and one report per source."""
    sources = cfg.get("sources") or {}
    items, reports, hits = [], [], {}
    wants_search = any((sources.get(SETTING_KEYS[s]) or {}).get("enabled", True)
                       for s in ("portal-notes", "portal-email"))
    if client is not None and wants_search:
        try:
            hits = search_hits(client, repos)
        except Exception as exc:  # noqa: BLE001 - a failed search narrows the match; reported
            reports.append({"name": "portal-search", "readable": False, "error": err_text(exc),
                            "listed": 0, "candidates": 0})
    readers = {
        "portal-notes": lambda c: read_notes(client, c, since, until, full),
        "portal-email": lambda c: read_email(client, c, since, until),
        "portal-tasks": lambda c: read_tasks(client, repos, since, until),
        "said-not-seen": lambda c: read_said(c, since, until),
    }
    for name in SOURCES:
        scfg = sources.get(SETTING_KEYS[name])
        if scfg is None and name == "said-not-seen":
            continue
        scfg = scfg or {}
        if not scfg.get("enabled", True):
            continue
        report = {"name": name, "readable": None, "error": None, "listed": 0, "candidates": 0}
        reports.append(report)
        if name.startswith("portal-") and client is None:
            report.update(readable=False, error="the Portal could not be reached")
            continue
        try:
            got = readers[name](scfg)
        except Exception as exc:  # noqa: BLE001 - one unreadable source never stops the others
            report.update(readable=False, error=err_text(exc))
            continue
        report.update(readable=True, listed=len(got))
        kind = {"portal-notes": "notes", "portal-email": "emails"}.get(name)
        for item in got:
            if kind:
                item["search_terms"] = sorted(set(hits.get(f"{kind}:{item['key'].split(':', 1)[1]}", [])))
            item["repo_hints"] = match_repos(item, repos)
            if item["repo_hints"]:
                items.append(item)
                report["candidates"] += 1
    for name, scfg in sources.items():
        if name not in SETTING_KEYS.values() and isinstance(scfg, dict):
            reports.append({"name": name, "readable": None, "error": None, "listed": 0, "candidates": 0,
                            "note": str(scfg.get("note") or "not reachable yet")})
    return items, reports


def window(root, days, now):
    """From the last live Run's start, never further back than `days`; a first Run reads `days`."""
    floor = now - timedelta(days=days)
    last = last_run(root)
    start = parse_time(last.get("started_at")) if last else None
    since = max(start, floor) if start else floor
    return {"since": since, "until": now, "first_run": last is None,
            "last_run": last.get("started_at") if last else None}
