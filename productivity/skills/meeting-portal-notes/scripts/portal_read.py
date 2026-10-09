"""Read the Portal with one named read tool and save the answer as a dated receipt.

    python3 scripts/portal_read.py TOOL --args ARGS.json --output RECEIPT.json

The Portal endpoint comes from the owner settings (~/.config/f3i-toolbox/settings.toml, or the
file F3I_TOOLBOX_SETTINGS names): `portal_mcp_config` names an MCP config file and
`portal_server` the server in it (default insights-portal). The bearer token is
INSIGHTS_PORTAL_ASSISTANT_TOKEN, else the config's Authorization header, where ${VAR} is read
from the environment. Only HTTPS is used (plain HTTP only to localhost), redirects are refused,
only read tools are allowed, and the endpoint and token are never printed. Exit 0 saved, 1 the
read failed, 2 bad arguments.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tomllib
import urllib.error
import urllib.request
from urllib.parse import urlsplit

TOKEN_ENV = 'INSIGHTS_PORTAL_ASSISTANT_TOKEN'
READ_TOOLS = {'get', 'search', 'list_entities', 'dereference', 'hierarchy', 'meeting_prep', 'email_bodies'}


def unwrap(raw):
    try:
        envelopes = [json.loads(raw)]
    except ValueError:
        envelopes = []
        for event in raw.replace('\r\n', '\n').split('\n\n'):
            data = '\n'.join(line[5:].lstrip() for line in event.splitlines() if line.startswith('data:'))
            if data:
                envelopes.append(json.loads(data))
    for envelope in envelopes:
        if envelope.get('error'):
            raise ValueError('MCP request failed')
        result = envelope.get('result')
        if not isinstance(result, dict):
            continue
        if result.get('isError'):
            raise ValueError('MCP tool failed')
        if result.get('structuredContent') is not None:
            return result['structuredContent']
        content = result.get('content') or []
        texts = [item['text'] for item in content if item.get('type') == 'text']
        if len(texts) == 1:
            try:
                return json.loads(texts[0])
            except ValueError:
                return texts[0]
        return content
    raise ValueError('No tool result')


class Stop(Exception):
    """A setting or the configuration is missing or unsafe. The message names no secret."""


def settings():
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get('F3I_TOOLBOX_SETTINGS', '~/.config/f3i-toolbox/settings.toml')).expanduser()
    try:
        return tomllib.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect, so the bearer token is never sent to another address."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def endpoint():
    """(url, Authorization header) from the MCP config the setting `portal_mcp_config` names."""
    owner = settings()
    cfg_path = owner.get('portal_mcp_config')
    server = owner.get('portal_server') or 'insights-portal'
    if not cfg_path:
        raise Stop('the setting portal_mcp_config (the MCP config file holding the Portal server) is needed')
    try:
        cfg = json.loads(Path(cfg_path).expanduser().read_text(encoding='utf-8'))['mcpServers'][server]
    except (OSError, KeyError, TypeError, ValueError):
        raise Stop(f'the file portal_mcp_config names has no usable mcpServers entry {server!r}') from None
    token = os.environ.get(TOKEN_ENV, '').strip()
    auth = f'Bearer {token}' if token else str((cfg.get('headers') or {}).get('Authorization') or '')
    url = str(cfg.get('url') or '')

    def expand(value, what):
        def one(m):
            if not os.environ.get(m.group(1)):
                raise Stop(f'the Portal {what} needs {m.group(1)}, which is not set')
            return os.environ[m.group(1)]
        value = re.sub(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}', one, value)
        if '${' in value or '\n' in value or '\r' in value:
            raise Stop(f'the Portal {what} is malformed')
        return value

    if not url or not auth:
        raise Stop(f'no Portal URL or token: set {TOKEN_ENV} or give the config an Authorization header')
    url, auth = expand(url, 'URL'), expand(auth, 'token')
    parts = urlsplit(url)
    local = parts.hostname in ('localhost', '127.0.0.1', '::1')
    if not parts.hostname or parts.username or parts.password or not (
            parts.scheme == 'https' or (parts.scheme == 'http' and local)):
        raise Stop('the Portal URL must be HTTPS (plain HTTP only to localhost)')
    if not auth.startswith('Bearer ') or not auth[7:].strip():
        raise Stop('the Portal token is not a bearer token')
    return url, auth


def request(url, auth, body, timeout=45):
    """POST one JSON-RPC body; the raw response text. A redirect is refused, never followed."""
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method='POST', headers={
        'Authorization': auth, 'Content-Type': 'application/json',
        'Accept': 'application/json, text/event-stream'})
    try:
        with OPENER.open(req, timeout=timeout) as response:
            return response.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as exc:
        raise Stop(f'the Portal answered HTTP {exc.code}'
                   + (' (a redirect, refused)' if 300 <= exc.code < 400 else '')) from None


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('tool', choices=sorted(READ_TOOLS))
    parser.add_argument('--args', type=Path, required=True, help='JSON argument file')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        arguments = json.loads(args.args.read_text())
        if not isinstance(arguments, dict):
            raise ValueError('Arguments must be an object')
        body = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                'params': {'name': args.tool, 'arguments': arguments}}
        result = unwrap(request(*endpoint(), body, timeout=45))
        receipt = {'fetched_at': datetime.now(timezone.utc).isoformat(),
                   'tool': args.tool, 'arguments': arguments, 'result': result}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(receipt, stream, indent=2, ensure_ascii=False)
        print(f'Saved read receipt: {args.output}')
    except Stop as exc:
        print(f'Portal read failed: {exc}; no output overwritten.', file=sys.stderr)
        return 1
    except Exception as exc:
        # Never print configured endpoints, auth headers or response bodies in failures.
        print(f'Portal read failed ({type(exc).__name__}); no output overwritten.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
