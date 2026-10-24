"""intacct_gl_detail.py and the credential and session code in _common.py, with no network."""

import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.pop("_common", None)  # another skill's _common may be loaded in the same run
import _common
import intacct_gl_detail as gd

NAMES = ("SAGE_INTACCT_CLIENT_ID", "SAGE_INTACCT_CLIENT_SECRET", "SAGE_INTACCT_COMPANY_ID", "SAGE_INTACCT_API_USER")


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name + "_SANDBOX", raising=False)
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "none.toml"))

    def refuse(*a, **k):
        raise AssertionError("a test tried to reach the network")
    monkeypatch.setattr(_common, "http_json", refuse)


def test_missing_credentials_name_the_variables_not_values(monkeypatch):
    monkeypatch.setenv("SAGE_INTACCT_CLIENT_SECRET", "s3cret-value")
    with pytest.raises(_common.NoCredentials) as exc:
        _common.credentials()
    assert "SAGE_INTACCT_CLIENT_ID" in str(exc.value) and "s3cret-value" not in str(exc.value)


def test_sandbox_prefers_suffixed_names_and_settings_fill_company(monkeypatch, tmp_path):
    for name in NAMES[:2]:
        monkeypatch.setenv(name, "prod")
    monkeypatch.setenv("SAGE_INTACCT_CLIENT_ID_SANDBOX", "sandbox-id")
    settings = tmp_path / "s.toml"
    settings.write_text('[erp-ledger-pull]\nintacct_company_id = "northwind-test"\nintacct_api_user = "reader"\n')
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(settings))
    assert _common.credentials("SANDBOX") == ("sandbox-id", "prod", "northwind-test", "reader")


def test_query_pages_and_ands_filters(monkeypatch):
    bodies = []

    def fake(url, method="GET", body=None, headers=None, timeout=60):
        if url.endswith("/oauth2/token"):
            return {"access_token": "t"}
        bodies.append(body)
        start = body["start"]
        page = [{"id": str(i)} for i in range(start, min(start + body["size"], 6))]
        return {"ia::result": page, "ia::meta": {"totalCount": 5}}

    monkeypatch.setattr(_common, "http_json", fake)
    monkeypatch.setattr(_common, "PAGE_SIZE", 2)
    rows, total = _common.IntacctSession("c", "s", "co", "u").query("x", ["id"], filters=[{"$eq": {}}, {"$gte": {}}])
    assert total == 5 and len(rows) == 5 and bodies[0]["filterExpression"] == "1 and 2"


def test_formats_and_totals():
    rows = [{"txnType": "debit", "txnAmount": "10"}, {"txnType": "credit", "txnAmount": "4"}, {"txnAmount": None}]
    assert gd.totals(rows) == (10.0, 4.0)
    assert gd.totals([{"x": 1}]) is None
    assert gd.as_table([], ["a"]) == "(no rows)"
    assert gd.as_csv([{"a": 1, "b": 2}], ["a"]).splitlines() == ["a", "1"]


def test_main_without_credentials_exits_two(capsys):
    assert gd.main(["--account", "6000"]) == 2
    assert "no Sage Intacct credentials" in capsys.readouterr().err


def test_main_end_to_end_with_a_fake_api(monkeypatch, capsys):
    for name in NAMES:
        monkeypatch.setenv(name, "x")

    def fake(url, method="GET", body=None, headers=None, timeout=60):
        if url.endswith("/oauth2/token"):
            return {"access_token": "t"}
        assert body["filters"][0] == {"$eq": {"glAccount.id": "6000"}}
        return {"ia::result": [{"id": "1", "txnType": "debit", "txnAmount": "12.50"}], "ia::meta": {"totalCount": 1}}

    monkeypatch.setattr(_common, "http_json", fake)
    assert gd.main(["--account", "6000", "--start", "2026-05-01", "--quiet"]) == 0
    assert "net 12.50" in capsys.readouterr().out


def test_a_redirect_is_an_error_and_never_followed(monkeypatch):
    import http.server
    import threading

    hits = []

    class Redirect(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(302)
            self.send_header("Location", "/elsewhere")
            self.end_headers()

        def log_message(self, *a):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Redirect)
    threading.Thread(target=server.handle_request, daemon=True).start()
    monkeypatch.undo()  # the real http_json, for a local server only
    try:
        with pytest.raises(_common.IntacctError) as exc:
            _common.http_json(f"http://127.0.0.1:{server.server_port}/start", timeout=5)
    finally:
        server.server_close()
    assert "(HTTP 302)" in str(exc.value) and hits == ["/start"]
