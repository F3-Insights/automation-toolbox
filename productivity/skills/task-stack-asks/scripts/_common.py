"""What the two task-asks scripts share: settings, the domain file's scope, the cursor and a
small read-only Insights Portal client.

THE DOMAIN FILE
---------------
A markdown reference file holding one domain's facts. Its first fenced ```yaml block is the
scope this command reads:

    vip:              # who is a VIP in this domain: a current relationship to the company
      - {company: "Northwind Traders", roles: [founder, board_member], titles: ["chief executive"]}
    mail:
      inboxes: [dana@northwind.test]          # mail in these inboxes is in scope
      correspondent_domains: [northwind.test] # mail with these correspondents, from any inbox
    ignore:
      senders: ["*@notify.northwind.test"]   # glob patterns on the sender's address

A contact is a VIP when any of its current relationships to the company has a type in `roles`
or a title holding any of `titles` (case-insensitive). Every key is optional.

THE CURSOR
----------
`<state_dir>/task-asks/<domain-slug>.json`: `since` (the newest instant every item up to which
is decided) and `decided` (the keys dated at or after `since` - OVERLAP already decided, with
their dates). The queue reads from `since` - OVERLAP, so mail stamped earlier but synced later
is still read, and drops what `decided` holds. Written only by task_asks_record.py.
"""

import fnmatch
import json
import os
import re
import sys
import tomllib
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

SKILL_DIR = Path(__file__).resolve().parents[1]
YAML_BLOCK = re.compile(r"^```ya?ml[ \t]*\n(.*?)^```", re.M | re.S)
OVERLAP = timedelta(days=2)  # how far before the cursor each Run reads again, for late-synced mail


class Bad(Exception):
    """A bad argument, an unusable domain file or Run folder: exit 2."""


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


def parse_time(value):
    """An aware UTC datetime from an ISO string (a bare date is midnight UTC), else None."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-") or "domain"


def truthy_flag(value):
    """--dry-run-if from a scheduler placeholder: only an unmistakable value is accepted."""
    text = str(value or "").strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    raise Bad(f"--dry-run-if wants true or false, got {value!r}; nothing was written")


# --------------------------------------------------------------------------- the domain file

def _strings(value, where):
    if value in (None, ""):
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise Bad(f"{where} is a list of strings")
    return [v.strip() for v in value if v.strip()]


def load_scope(path):
    """The domain file's scope: vip rules, inboxes, correspondent domains, ignored senders."""
    p = Path(path).expanduser()
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise Bad(f"the domain file {p} cannot be read ({type(exc).__name__})") from None
    m = YAML_BLOCK.search(text)
    if not m:
        raise Bad(f"the domain file {p} has no ```yaml block")
    import yaml
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        raise Bad(f"the domain file {p}: its yaml block does not parse") from None
    if not isinstance(data, dict):
        raise Bad(f"the domain file {p}: its yaml block is not a mapping")
    vips = []
    for i, rule in enumerate(data.get("vip") or [], 1):
        if not isinstance(rule, dict) or not str(rule.get("company") or "").strip():
            raise Bad(f"the domain file {p}: vip {i} needs a company")
        vips.append({"company": str(rule["company"]).strip(),
                     "roles": [r.lower() for r in _strings(rule.get("roles"), f"vip {i} roles")],
                     "titles": [t.lower() for t in _strings(rule.get("titles"), f"vip {i} titles")]})
    mail = data.get("mail") or {}
    ignore = data.get("ignore") or {}
    if not isinstance(mail, dict) or not isinstance(ignore, dict):
        raise Bad(f"the domain file {p}: mail and ignore are mappings")
    return {"vip": vips,
            "inboxes": [a.lower() for a in _strings(mail.get("inboxes"), "mail.inboxes")],
            "correspondent_domains": [d.lower().lstrip("@") for d in
                                      _strings(mail.get("correspondent_domains"), "mail.correspondent_domains")],
            "ignore_senders": [s.lower() for s in _strings(ignore.get("senders"), "ignore.senders")]}


def ignored(address, patterns):
    return any(fnmatch.fnmatchcase(str(address or "").lower(), pat) for pat in patterns)


def vip_match(rel, rule):
    """Does one current relationship make its contact a VIP under one rule?"""
    if rel.get("is_current") is False:
        return False
    kind = str(rel.get("relationship_type") or "").lower()
    title = str(rel.get("title") or "").lower()
    return kind in rule["roles"] or any(t in title for t in rule["titles"])


# --------------------------------------------------------------------------- the cursor

def cursor_path(domain, explicit=""):
    if str(explicit or "").strip():
        base = Path(explicit).expanduser()
    elif settings().get("state_dir"):
        base = Path(settings()["state_dir"]).expanduser()
    else:
        raise Bad("setting state_dir is needed (the folder where the toolbox keeps its state), or pass --state")
    return base / "task-asks" / f"{slug(domain)}.json"


def read_cursor(path):
    """{"since": iso or None, "decided": {key: date}}; a missing file is the first run."""
    if not path.is_file():
        return {"since": None, "decided": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise Bad(f"the cursor {path} is not JSON; fix or remove it") from None
    decided = data.get("decided") or {}
    return {"since": data.get("since"), "decided": decided if isinstance(decided, dict) else {}}


def write_cursor(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def guard_run_path(path):
    """A Run folder never lives inside this skill's own folder."""
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
