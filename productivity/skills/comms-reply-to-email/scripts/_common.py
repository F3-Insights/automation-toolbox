"""What this skill's scripts share: owner settings, the Insights Portal client, addresses and
ids, the owner's inboxes, the draft content hash, the run-folder guard and the calendar read
the context pack uses for free slots.

The Portal endpoint and bearer come from the MCP config file the `portal_mcp_config` setting
names (server `portal_server`, default `insights-portal`). The bearer is
`INSIGHTS_PORTAL_ASSISTANT_TOKEN` when set, else the config's Authorization header with
`${VAR}` expanded from the environment. It is never printed. HTTPS only, except plain HTTP to
localhost, and a redirect is refused so the bearer goes nowhere but the configured URL.

None of these scripts sends mail. The only Portal writes in this skill are `draft_push`
(email_deliver.py, into the owner's own Drafts folder) and the owner-only message of
notify_owner.py.
"""

import hashlib
import json
import os
import re
import sys
import tomllib
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

# Exit codes shared by the reply commands: go on, stop, could not run.
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


def addresses_in(values):
    """Every address in a string, a list or a dict holding `address` or `email`."""
    out = []
    if values is None:
        return out
    if isinstance(values, str):
        values = re.split(r"[,;]", values)
    if isinstance(values, dict):
        values = [values.get("address") or values.get("email") or ""]
    for value in values or []:
        if isinstance(value, dict):
            value = value.get("address") or value.get("email") or ""
        addr = bare_address(value)
        if addr and addr not in out:
            out.append(addr)
    return out


def contact_addresses(contact):
    """Every address a contact record holds, primary first. A web address filed as an email
    is not an address and is dropped by the pattern."""
    out = []
    primary = bare_address(contact.get("primary_email"))
    if primary:
        out.append(primary)
    for row in contact.get("emails") or []:
        addr = bare_address(row.get("address") if isinstance(row, dict) else row)
        if addr and addr not in out:
            out.append(addr)
    return out


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


# --------------------------------------------------------------------------- the owner

def owner(portal):
    """The owner's timezone, own addresses and inboxes (with provider), from one `whoami`."""
    who = portal.whoami()
    if not isinstance(who, dict):
        raise Failure("whoami returned nothing usable")
    principal = who.get("principal") or {}
    tz_name = str(principal.get("timezone") or "") or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:  # an unknown zone falls back to UTC, and says so
        tz, tz_name = ZoneInfo("UTC"), "UTC"
    inboxes = []
    for row in who.get("inboxes") or []:
        if isinstance(row, dict) and bare_address(row.get("address")):
            inboxes.append({"id": row.get("id"), "address": bare_address(row.get("address")),
                            "provider": str(row.get("provider") or ""), "kind": row.get("kind"),
                            "is_active": row.get("is_active")})
    addresses = [i["address"] for i in inboxes]
    primary = bare_address(principal.get("primary_email"))
    if primary and primary not in addresses:
        addresses.append(primary)
    return {"tz": tz, "timezone": tz_name, "inboxes": inboxes, "addresses": addresses,
            "contact_id": principal.get("contact_id"), "member_id": principal.get("org_member_id")}


def receiving_inbox(message, inboxes):
    """Which of the owner's inboxes a message arrived in, judged from its To and Cc.

    One match is an answer; none or several is said, never guessed.
    """
    seen = addresses_in(message.get("to_addresses")) + addresses_in(message.get("cc_addresses"))
    hits = [i for i in inboxes if i["address"] in seen]
    if len(hits) == 1:
        return {"inbox": hits[0], "basis": "the message's To or Cc names this inbox"}
    if not hits:
        return {"inbox": None, "basis": "no inbox of the owner's appears in the message's To or Cc "
                                        "(a Bcc, an alias or a list); the Portal decides at push time"}
    return {"inbox": None, "basis": "several of the owner's inboxes are on the message: "
                                    + ", ".join(i["address"] for i in hits), "candidates": hits}


def is_gmail(inbox):
    return bool(inbox) and "gmail" in str(inbox.get("provider") or "").lower()


# --------------------------------------------------------------------------- the draft

HASHED_FIELDS = ("subject", "content", "recipient_to", "recipient_cc", "recipient_bcc",
                 "email_id", "contact_id")


def content_hash(draft):
    """One hash over everything that decides what would be sent and to whom: subject, body,
    every recipient list, the email it answers and the contact. Any change after the check
    makes the check stale."""
    canon = {}
    for key in HASHED_FIELDS:
        value = draft.get(key)
        if key.startswith("recipient_"):
            value = sorted(addresses_in(value))
        elif key in ("email_id", "contact_id"):
            value = bare_id(value)
        else:
            value = "" if value is None else str(value)
        canon[key] = value
    digest = hashlib.sha256(json.dumps(canon, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return f"sha256:{digest}"


def read_draft(portal, draft_id):
    out = portal.call("get", {"entity_type": "draft", "id_or_query": bare_id(draft_id), "detail": "full"})
    if not isinstance(out, dict) or out.get("error") or not out.get("id"):
        reason = out.get("error") if isinstance(out, dict) else "no answer"
        raise Failure(f"draft {draft_id} could not be read: {reason}")
    return out


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


def skill_script(skill, name):
    """Another skill's script, by the skill's name, as an installed toolbox places it."""
    return Path.home() / ".claude" / "skills" / skill / "scripts" / name


# --------------------------------------------------------------------------- the calendar

CANCELLED_PREFIXES = ("canceled:", "cancelled:")
_CLONE = re.compile(r"(?i)\s*[\(\[]\s*clone(?:\s*\d+)?\s*[\)\]]")


class Event:
    """One calendar row: when it starts and ends, and whether it is all day or cancelled."""

    def __init__(self, row):
        self.title = str(row.get("title") or "").strip()
        self.ref = str(row.get("_ref") or "")
        self.start = parse_time(row.get("start_time"))
        self.end = parse_time(row.get("end_time"))
        self.all_day = bool(row.get("is_all_day"))
        self.cancelled = self.title.lower().startswith(CANCELLED_PREFIXES)
        self.attendees = len(row.get("attendees") or [])
        title = _CLONE.sub("", self.title).casefold()
        self.key = (str(self.start), str(self.end), " ".join(title.split()))


def deduplicate(events):
    """One event per (start, end, title without clone markers), keeping the fullest copy."""
    best, order = {}, []
    for event in events:
        seen = best.get(event.key)
        if seen is None:
            best[event.key] = event
            order.append(event.key)
        elif event.attendees > seen.attendees:
            best[event.key] = event
    return [best[k] for k in order]


def page_events(portal, since, until, page=50, max_calls=200):
    """Every calendar row in [since, until), halving a page the server will not serialise
    (a large response fails outright), down to stepping over one bad row. Returns the rows and
    how many could not be read. Reading nothing at all is an error, never an empty calendar."""
    def iso(moment):
        return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    filters = {"since": iso(since), "until": iso(until)}
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
