"""What this skill's scripts share: owner settings and the Insights Portal client.

The Portal endpoint and bearer come from the MCP config file the `portal_mcp_config` setting
names (server `portal_server`, default `insights-portal`). The bearer is
`INSIGHTS_PORTAL_ASSISTANT_TOKEN` when set, else the config's Authorization header with
`${VAR}` expanded from the environment. It is never printed. HTTPS only, except plain HTTP to
localhost, and a redirect is refused so the bearer goes nowhere but the configured URL.
confirm_portal.py writes only the request's own task: a create, a comment and a
status, each read back.
"""

import json
import os
import re
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit


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


# --------------------------------------------------------------------------- the Portal

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect: urllib would otherwise resend the bearer to the new address."""

    def redirect_request(self, *args, **kwargs):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def portal_endpoint():
    """(url, Authorization header) for the Portal, from settings and the environment."""
    top = settings()
    config_path = top.get("portal_mcp_config")
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


def client():
    """The Portal client, built from the owner settings."""
    return Portal(*portal_endpoint())

