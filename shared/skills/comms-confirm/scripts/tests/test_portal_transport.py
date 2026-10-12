"""The Portal client's transport guards: a redirect is refused before the bearer is resent,
plain HTTP is refused except to localhost, and the token never reaches the screen."""

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import _common as c  # noqa: E402

TOKEN = "s3cret-portal-token"
AT = "@"  # credentials in a URL, built so the text holds no address


def serve(handler):
    httpd = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def use_portal(tmp_path, monkeypatch, url):
    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps({"mcpServers": {"insights-portal": {
        "url": url, "headers": {"Authorization": "Bearer ${TEST_PORTAL_TOKEN}"}}}}))
    settings = tmp_path / "settings.toml"
    settings.write_text(f'portal_mcp_config = "{cfg}"\n')
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(settings))
    monkeypatch.delenv("INSIGHTS_PORTAL_ASSISTANT_TOKEN", raising=False)
    monkeypatch.setenv("TEST_PORTAL_TOKEN", TOKEN)


def test_a_redirect_is_refused_and_the_token_goes_nowhere_else(tmp_path, monkeypatch):
    seen = []

    class Elsewhere(BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append(self.headers.get("Authorization"))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"result": {}}')

        def log_message(self, *args):
            pass

    other = serve(Elsewhere)

    class Redirect(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(307)
            self.send_header("Location", f"http://127.0.0.1:{other.server_address[1]}/mcp")
            self.end_headers()

        def log_message(self, *args):
            pass

    first = serve(Redirect)
    try:
        use_portal(tmp_path, monkeypatch, f"http://localhost:{first.server_address[1]}/mcp")
        with pytest.raises(Exception) as exc:
            CLIENT().call("whoami")
        assert "redirect" in str(exc.value) and TOKEN not in str(exc.value)
        assert seen == []
    finally:
        for httpd in (first, other):
            httpd.shutdown()
            httpd.server_close()


@pytest.mark.parametrize("url", ["http://portal.example.com/mcp", "https://user:pw" + AT + "portal.example.com/mcp",
                                 "https://:pw" + AT + "portal.example.com/mcp"])
def test_plain_http_and_credentials_in_the_url_are_refused(tmp_path, monkeypatch, url):
    use_portal(tmp_path, monkeypatch, url)
    with pytest.raises(Exception) as exc:
        ENDPOINT()
    assert "HTTPS" in str(exc.value) and TOKEN not in str(exc.value)


def test_localhost_may_use_plain_http(tmp_path, monkeypatch):
    use_portal(tmp_path, monkeypatch, "http://localhost:8080/mcp")
    assert ENDPOINT() == ("http://localhost:8080/mcp", f"Bearer {TOKEN}")


def test_the_token_is_redacted_from_anything_printed():
    for text in (f"Authorization: Bearer {TOKEN}", f'{{"authorization": "{TOKEN}"}}', f"https://x/?token={TOKEN}"):
        assert TOKEN not in c.safe(text)


CLIENT, ENDPOINT = c.client, c.portal_endpoint
