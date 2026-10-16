"""What calendar_time.py shares with the calendar steward: owner settings, the Insights Portal
client and the calendar read and its cleaning. A trimmed copy of calendar-steward-method's
_common.py; keep the functions identical to it.

The Portal endpoint and bearer come from the MCP config file the `portal_mcp_config` setting
names (server `portal_server`, default `insights-portal`). The bearer is
`INSIGHTS_PORTAL_ASSISTANT_TOKEN` when set, else the config's Authorization header with
`${VAR}` expanded from the environment. It is never printed. HTTPS only, except plain HTTP to
localhost, and a redirect is refused so the bearer goes nowhere but the configured URL.
"""

import json
import os
import re
import tomllib
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo  # noqa: F401  (calendar_time.py reads c.ZoneInfo)


class Bad(Exception):
    """A bad argument or an unreadable input: exit 2."""

class Failure(Exception):
    """The command could not do its job; the message says why."""

class PortalError(Failure):
    """The Portal refused the call or gave no usable answer."""

class PortalUnreachable(PortalError):
    """The call never got an answer (network, TLS, an HTTP status, a redirect)."""

def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data

_SECRETS = re.compile(r"(?i)(bearer\s+\S+|authorization[\"'\s:=]+(?:bearer\s+)?\S+"
                      r"|[?&](?:key|token|api_key|access_token)=[^\s&\"']+)")

def safe(text):
    """Everything on its way to the screen passes through here, so no token is ever shown."""
    return _SECRETS.sub("[redacted]", str(text))

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect: urllib would otherwise resend the bearer to the new address."""

    def redirect_request(self, *args, **kwargs):
        return None

_OPENER = urllib.request.build_opener(_NoRedirect)

def portal_endpoint(config_path=None, server=None):
    """(url, Authorization header) for the Portal, from settings and the environment. A config
    path or server name given here replaces the `portal_mcp_config` or `portal_server` setting."""
    top = settings()
    config_path = config_path or top.get("portal_mcp_config")
    server = server or top.get("portal_server") or "insights-portal"
    if not config_path:
        raise Failure("set portal_mcp_config in the owner settings to the MCP config holding the Portal")
    path = Path(str(config_path)).expanduser()
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))["mcpServers"][server]
    except (OSError, ValueError, KeyError, TypeError):
        raise Failure(f"{path} has no usable mcpServers entry named {server!r}") from None
    token = os.environ.get("INSIGHTS_PORTAL_ASSISTANT_TOKEN", "").strip()
    auth = f"Bearer {token}" if token else (cfg.get("headers") or {}).get("Authorization") or ""
    url = cfg.get("url") or ""

    def expand(value, what):
        def one(match):
            if not os.environ.get(match.group(1)):
                raise Failure(f"the Portal {what} needs {match.group(1)}, which is not set")
            return os.environ[match.group(1)]
        value = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", one, value)
        if "${" in value or "\n" in value or "\r" in value:
            raise Failure(f"the Portal {what} is malformed")
        return value

    if not url or not auth:
        raise Failure(f"the {server!r} entry in {path} needs a url and a token")
    url, auth = expand(url, "URL"), expand(auth, "token")
    parts = urlsplit(url)
    local = parts.hostname in ("localhost", "127.0.0.1", "::1")
    if not parts.hostname or parts.username or parts.password or not (
            parts.scheme == "https" or (parts.scheme == "http" and local)):
        raise Failure("the Portal URL must be HTTPS (HTTP only on localhost)")
    if not auth.startswith("Bearer ") or not auth[7:].strip():
        raise Failure("the Portal token is not a bearer token")
    return url, auth

class Portal:
    """A JSON-RPC client for the Portal's MCP server: one `call` per tool."""

    def __init__(self, url, auth, timeout=60):
        self.url, self._auth, self.timeout = url, auth, timeout
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
            if 300 <= exc.code < 400:
                raise PortalUnreachable(f"portal {tool}: HTTP {exc.code}, a redirect, refused") from None
            raise PortalUnreachable(f"portal {tool}: HTTP {exc.code}") from None
        except urllib.error.URLError as exc:
            raise PortalUnreachable(f"portal {tool}: {exc.reason}") from None
        except OSError as exc:
            raise PortalUnreachable(f"portal {tool}: {type(exc).__name__}") from None
        return unwrap(tool, raw)

    def whoami(self):
        return self.call("whoami")

def unwrap(tool, raw):
    """The tool's answer from a JSON or event-stream response, parsed when it is JSON."""
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
        except ValueError:
            return text
    return result

def client(config_path=None, server=None):
    """The Portal client, built from the owner settings."""
    return Portal(*portal_endpoint(config_path, server))

CANCELLED_PREFIXES = ("canceled:", "cancelled:")

_CLONE_MARKER = re.compile(r"(?i)\s*[\(\[][^\)\]]*\bclone\b[^\)\]]*[\)\]]")

_REPLY_PREFIX = re.compile(r"^\s*(re|fwd|fw|aw|antw|rv|vs)\s*(\[\d+\])?\s*:\s*", re.IGNORECASE)

def parse_time(value):
    """An ISO timestamp or date as an aware UTC datetime; one with no zone is read as UTC.
    Anything that will not parse is None, so one bad row cannot take down a period."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

def iso_z(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def normalise_title(title):
    """The comparable part of a title: clone markers, Canceled: and Re:/Fw: gone, case folded."""
    text = _CLONE_MARKER.sub("", str(title or ""))
    for prefix in CANCELLED_PREFIXES:
        if text.strip().lower().startswith(prefix):
            text = text.strip()[len(prefix):]
    while True:
        stripped = _REPLY_PREFIX.sub("", text, count=1)
        if stripped == text:
            break
        text = stripped
    return " ".join(text.split()).casefold()

def domain_of(address):
    return address.rsplit("@", 1)[-1].strip().lower() if "@" in address else ""

class Event:
    """One calendar row, read defensively. Never raises on a bad shape."""

    def __init__(self, raw):
        data = raw if isinstance(raw, dict) else {}
        self.raw = data
        self.ref = str(data.get("_ref") or "")
        self.title = str(data.get("title") or "").strip()
        self.kind = str(data.get("event_kind") or "").strip().lower()
        self.all_day = bool(data.get("is_all_day"))
        self.start = parse_time(data.get("start_time"))
        self.end = parse_time(data.get("end_time"))
        seconds = (self.end - self.start).total_seconds() if self.start and self.end else 0
        self.hours = round(seconds / 3600.0, 4) if seconds > 0 else 0.0
        self.people = [a for a in data.get("attendees") or [] if isinstance(a, dict)]
        self.attendees = []
        for entry in data.get("attendees") or []:
            address = entry if isinstance(entry, str) else next(
                (str(entry[k]) for k in ("email", "address", "email_address", "value")
                 if isinstance(entry, dict) and str(entry.get(k) or "").strip()), "")
            address = address.strip().strip("<>").lower()
            if "@" in address and address not in self.attendees:
                self.attendees.append(address)
        self.cancelled = self.title.lower().startswith(CANCELLED_PREFIXES)
        self.calendar_name = str(data.get("calendar_name") or "")
        self.key = (self.start.isoformat() if self.start else "", self.end.isoformat() if self.end else "",
                    normalise_title(self.title))

    @property
    def is_meeting(self):
        return self.kind == "meeting"

    @property
    def is_availability(self):
        return self.kind == "availability_block"

def page_events(portal, since, until, page=50, max_calls=200):
    """Every calendar row in [since, until), halving a page the server will not serialise
    (a large response fails outright rather than truncating), down to stepping over one bad
    row. Returns the rows and how many could not be read. Reading nothing at all is an error,
    never an empty calendar."""
    filters = {"since": iso_z(since), "until": iso_z(until)}
    items, offset, unreadable, total, calls = [], 0, 0, None, 0
    failure, read_any = "", False
    while calls < max_calls:
        served, size = None, page
        while calls < max_calls:
            args = {"entity_type": "calendar_event", "filters": filters, "limit": size}
            if offset:
                args["offset"] = offset
            calls += 1
            try:
                out = portal.call("list_entities", args)
            except Exception as exc:  # a page too large to serialise: try a smaller one
                failure = type(exc).__name__
                if size == 1:
                    break
                size = max(1, size // 2)
                continue
            served = out if isinstance(out, dict) else None
            break
        if served is None:
            unreadable += 1
            offset += 1
            if total is None or offset >= total:
                break
            continue
        read_any = True
        rows = [r for r in served.get("items") or [] if isinstance(r, dict)]
        if isinstance(served.get("total"), int):
            total = served["total"]
        items.extend(rows)
        if not rows:
            break
        offset += len(rows)
        if total is not None and offset >= total:
            break
        if not served.get("has_more") and size >= page:
            break
    if failure and not read_any:
        raise Failure(f"could not read any calendar rows from the Portal ({failure})")
    return items, unreadable

def merge_spans(spans):
    out = []
    for start, end in sorted(spans):
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out
