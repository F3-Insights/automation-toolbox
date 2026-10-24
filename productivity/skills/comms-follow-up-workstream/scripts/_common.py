"""What the follow-up and meeting-prep commands share: owner settings, the Insights Portal
client, addresses and ids, the owner from whoami, paged listings, times and the run-folder guard.

The Portal endpoint and bearer come from the MCP config file the `portal_mcp_config` setting
names (server `portal_server`, default `insights-portal`). The bearer is
`INSIGHTS_PORTAL_ASSISTANT_TOKEN` when set, else the config's Authorization header with
`${VAR}` expanded from the environment. It is never printed. HTTPS only, except plain HTTP to
localhost, and a redirect is refused so the bearer goes nowhere but the configured URL.

Every command here only reads the Portal. The same text sits in each skill that needs it (a
skill is copied whole); comms-reply-to-email's _common.py is where it was taken from.
"""

import json
import os
import re
import sys
import tomllib
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

# Exit codes: go on, stop, could not run.
OK, STOP, ERROR = 0, 3, 2



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


def emit(payload, code):
    print(safe(json.dumps(payload, indent=1, default=str)))
    sys.exit(code)


def fail(message):
    """Print the error as JSON (callers parse stdout) and exit 2."""
    print(safe(json.dumps({"status": "error", "reason": str(message)}, indent=1)))
    sys.exit(ERROR)


# --------------------------------------------------------------------------- the Portal

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect: urllib would otherwise resend the bearer to the new address."""

    def redirect_request(self, *args, **kwargs):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def portal_endpoint(config_path=None):
    """(url, Authorization header) for the Portal, from settings and the environment. A
    config path given here replaces the `portal_mcp_config` setting."""
    top = settings()
    config_path = config_path or top.get("portal_mcp_config")
    server = top.get("portal_server") or "insights-portal"
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


def client(config_path=None):
    """The Portal client, built from the owner settings."""
    return Portal(*portal_endpoint(config_path))

# --------------------------------------------------------------------------- addresses and ids

_ADDRESS = re.compile(r"[^\s<>,;\"']+@[^\s<>,;\"']+")


def bare_address(text):
    """`Dana <dana@example.com>` becomes `dana@example.com`, lowercased."""
    found = _ADDRESS.search(str(text or ""))
    return found.group(0).strip(".<>").lower() if found else ""


def bare_id(value):
    """`portal://email/abc` and `abc` are the same id."""
    return str(value or "").strip().rstrip("/").rsplit("/", 1)[-1]


def email_ref(value):
    return f"portal://email/{bare_id(value)}" if bare_id(value) else ""


def parse_time(value):
    """An ISO timestamp as an aware UTC datetime; one without a zone is read as UTC."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
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


# --------------------------------------------------------------------------- files

def toolbox_root():
    """The repository (or, copied alone, the skill folder) these scripts live in."""
    here = Path(__file__).resolve().parent
    for folder in [here, *here.parents]:
        if (folder / ".git").exists():
            return folder
    return here.parent


def guard_run_path(path):
    """A run file never lives inside the toolbox: no state in the code."""
    target = Path(path).expanduser().resolve()
    try:
        target.relative_to(toolbox_root())
    except ValueError:
        return target
    raise Failure(f"{target} is inside the toolbox; run files live outside it")



# --------------------------------------------------------------------------- the owner and time

PUBLIC_MAIL = frozenset({"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "yahoo.com",
                         "icloud.com", "me.com", "aol.com", "proton.me", "protonmail.com"})


def domain_of(address):
    address = bare_address(address)
    return address.rsplit("@", 1)[-1] if "@" in address else ""


def owner(portal):
    """The owner's contact, timezone, own addresses and internal mail domains, from one whoami.
    An unknown zone falls back to UTC and says so in `timezone`."""
    who = portal.call("whoami")
    if not isinstance(who, dict):
        raise Failure("whoami returned nothing usable")
    principal = who.get("principal") or {}
    name = str(principal.get("timezone") or "") or "UTC"
    try:
        tz = ZoneInfo(name)
    except Exception:  # an unknown zone is UTC, said rather than guessed
        tz, name = ZoneInfo("UTC"), "UTC"
    addresses = []
    for row in who.get("inboxes") or []:
        address = bare_address(row.get("address")) if isinstance(row, dict) else ""
        if address and address not in addresses:
            addresses.append(address)
    primary = bare_address(principal.get("primary_email"))
    if primary and primary not in addresses:
        addresses.append(primary)
    internal = sorted({domain_of(a) for a in addresses} - PUBLIC_MAIL - {""})
    return {"contact_id": str(principal.get("contact_id") or "").lower() or None, "tz": tz, "timezone": name,
            "addresses": addresses, "internal_domains": internal}


def iso_z(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def local_day(value, tz):
    """The owner's local date of a timestamp, or a plain yyyy-mm-dd date as it stands."""
    text = str(value or "").strip()
    if len(text) == 10:
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
    moment = parse_time(text)
    return moment.astimezone(tz).date() if moment else None


def business_days_between(earlier, later):
    """Weekdays after `earlier` up to and including `later` (Monday to Friday)."""
    if earlier is None or later is None or later <= earlier:
        return 0
    days, day = 0, earlier
    while day < later:
        day += timedelta(days=1)
        if day.weekday() < 5:
            days += 1
    return days


def list_all(portal, entity_type, filters=None, page=200, max_pages=50):
    """Every row of one listing, following next_offset until has_more is false."""
    rows, offset = [], 0
    for _ in range(max_pages):
        args = {"entity_type": entity_type, "limit": page}
        if filters:
            args["filters"] = dict(filters)
        if offset:
            args["offset"] = offset
        out = portal.call("list_entities", args)
        if not isinstance(out, dict) or out.get("error"):
            raise PortalError(f"list_entities {entity_type} failed: "
                              f"{out.get('error') if isinstance(out, dict) else 'no answer'}")
        got = [r for r in out.get("items") or [] if isinstance(r, dict)]
        rows.extend(got)
        if not out.get("has_more") or not got:
            return rows
        offset = int(out.get("next_offset") or offset + len(got))
    raise PortalError(f"list_entities {entity_type} did not end within {max_pages} pages")
