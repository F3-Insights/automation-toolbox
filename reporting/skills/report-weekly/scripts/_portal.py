"""A small JSON-RPC client for the Insights Portal MCP server, read calls and the work order's
task mirror only.

Where the Portal is: the MCP config file the setting `portal_mcp_config` names, server entry
`portal_server` (default `insights-portal`). The bearer is `INSIGHTS_PORTAL_ASSISTANT_TOKEN`
when that is set, else the config's Authorization header with any `${VAR}` filled from the
environment. HTTPS only, except plain HTTP to localhost. A redirect is never followed, so the
bearer only ever goes to the configured address. Nothing here prints the bearer.
"""

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from _common import Fail, settings


def endpoint():
    """(url, Authorization header) from the owner's settings and environment."""
    shared = settings()
    config = str(shared.get("portal_mcp_config") or "").strip()
    server = str(shared.get("portal_server") or "insights-portal").strip()
    if not config:
        raise Fail("the setting portal_mcp_config is not set: name the MCP config file that "
                   "holds the Insights Portal server in ~/.config/f3i-toolbox/settings.toml")
    path = Path(config).expanduser()
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))["mcpServers"][server]
    except (OSError, ValueError, KeyError, TypeError):
        raise Fail(f"{path} has no usable mcpServers entry named {server!r}") from None
    token = os.environ.get("INSIGHTS_PORTAL_ASSISTANT_TOKEN", "").strip()
    auth = f"Bearer {token}" if token else str((entry.get("headers") or {}).get("Authorization") or "")
    url = str(entry.get("url") or "")

    def expand(value, what):
        def one(match):
            if not os.environ.get(match.group(1)):
                raise Fail(f"the Portal {what} needs {match.group(1)}, which is not set")
            return os.environ[match.group(1)]
        value = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", one, value)
        if "${" in value or "\n" in value:
            raise Fail(f"the Portal {what} is malformed")
        return value

    if not url or not auth:
        raise Fail(f"the {server!r} entry in {path} gives no URL or no token")
    url, auth = expand(url, "URL"), expand(auth, "token")
    parts = urlsplit(url)
    local = parts.hostname in ("localhost", "127.0.0.1", "::1")
    if not parts.hostname or not (parts.scheme == "https" or (parts.scheme == "http" and local)):
        raise Fail("the Portal URL must be HTTPS (plain HTTP only to localhost)")
    if not auth.startswith("Bearer ") or not auth[7:].strip():
        raise Fail("the Portal token is not a bearer token")
    return url, auth


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


class Portal:
    """One connection. `call(tool, arguments)` returns the tool's parsed result."""

    def __init__(self, url=None, auth=None, timeout=60):
        if url is None:
            url, auth = endpoint()
        self.url, self._auth, self.timeout, self._id = url, auth, timeout, 0
        self.calls = 0

    def call(self, tool, arguments=None):
        self._id += 1
        self.calls += 1
        body = json.dumps({"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
                           "params": {"name": tool, "arguments": arguments or {}}}).encode()
        request = urllib.request.Request(self.url, data=body, method="POST")
        request.add_header("Authorization", self._auth)
        request.add_header("Content-Type", "application/json")
        request.add_header("Accept", "application/json, text/event-stream")
        try:
            with OPENER.open(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise Fail(f"portal {tool}: HTTP {exc.code}"
                       + (", a redirect, refused" if 300 <= exc.code < 400 else "")) from None
        except (urllib.error.URLError, OSError) as exc:
            raise Fail(f"portal {tool}: {getattr(exc, 'reason', type(exc).__name__)}") from None
        try:
            return self.read(tool, raw)
        except (ValueError, TypeError, AttributeError, KeyError) as exc:
            # A malformed answer is a failed call, never a crash that loses the caller's work.
            raise Fail(f"portal {tool}: an unreadable response ({type(exc).__name__})") from None

    @staticmethod
    def read(tool, raw):
        """The tool's result out of a JSON or event-stream response body."""
        messages = [json.loads(raw)] if raw.lstrip().startswith("{") else []
        for line in raw.splitlines():
            if line.startswith("data:"):
                try:
                    messages.append(json.loads(line[5:].strip()))
                except ValueError:
                    pass
        if not messages:
            raise Fail(f"portal {tool}: empty response")
        out = messages[-1]
        if "error" in out:
            raise Fail(f"portal {tool}: {str(out['error'])[:300]}")
        result = out.get("result", out)
        if isinstance(result, dict) and "content" in result:
            text = "\n".join(c.get("text", "") for c in result["content"] if c.get("type") == "text")
            if result.get("isError"):
                raise Fail(f"portal {tool}: {text[:300]}")
            try:
                return json.loads(text)
            except ValueError:
                return text
        return result

    def safe_call(self, tool, arguments=None):
        """One call whose failure is a gap in the read rather than the end of the run."""
        try:
            return self.call(tool, arguments)
        except Fail:
            return None

    def page(self, entity_type, filters=None, max_calls=400):
        """Every row of one entity type. A page the server refuses to serialise is retried
        smaller, down to one row, and a row that never serialises is stepped over and counted.
        Returns (rows, rows that could not be read)."""
        rows, offset, unreadable, total, calls = [], 0, 0, None, 0
        while calls < max_calls:
            served = None
            for size in (200, 50, 10, 1):
                args = {"entity_type": entity_type, "limit": size}
                if filters:
                    args["filters"] = dict(filters)
                if offset:
                    args["offset"] = offset
                calls += 1
                out = self.safe_call("list_entities", args)
                if isinstance(out, dict):
                    served = (out, size)
                    break
            if served is None:
                if calls <= 4 and not rows:
                    raise Fail(f"could not read any {entity_type} rows from the Portal")
                unreadable += 1
                offset += 1
                if total is None or offset >= total:
                    break
                continue
            out, size = served
            got = [r for r in out.get("items") or [] if isinstance(r, dict)]
            total = out["total"] if isinstance(out.get("total"), int) else total
            rows += got
            offset += len(got)
            if not got or (total is not None and offset >= total) or (size == 200 and not out.get("has_more")):
                break
        return rows, unreadable
