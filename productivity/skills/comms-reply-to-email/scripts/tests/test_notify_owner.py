"""notify-owner sends only to the token's own member, never to a recipient it is given, and
falls back to the member's own email only when Teams refuses."""

import json

import pytest

import _common as c
import notify_owner as no
from reply_fixtures import point_settings_at, run, serve


class FakePortal:
    def __init__(self, teams=None, mail=None, member="mem-1"):
        self.calls = []
        self.teams = teams or {"success": True, "decision": "sent", "external_message_id": "x1"}
        self.mail = mail or {"success": True, "decision": "sent", "log_id": "l1"}
        self.member = member

    def dispatch(self, name, args):
        self.calls.append((name, args))
        if name == "whoami":
            return {"principal": {"org_member_id": self.member, "primary_email": "owner@owner.test"}}
        if name == "teams_post":
            if isinstance(self.teams, Exception):
                raise self.teams
            return self.teams
        if name == "send_agent_message":
            return self.mail
        raise AssertionError(name)


@pytest.fixture
def fake(monkeypatch, tmp_path):
    holder = FakePortal()
    httpd = serve(holder)
    point_settings_at(monkeypatch, tmp_path, httpd.server_address[1])
    monkeypatch.delenv("NOTIFY_OWNER_MODE", raising=False)
    yield holder
    httpd.shutdown()
    httpd.server_close()


def notify(capsys, *args):
    return run(no, capsys, "--title", "Draft reply to Dana is in your Drafts", *args)


def test_posts_to_the_tokens_own_member(fake, capsys):
    code, out = notify(capsys, "--bullet", "one line", "--link", "https://github.com/acme/app/issues/3",
                       "--record-ref", "portal://draft/0a1b2c3d")
    assert code == 0 and out == {"sent": True, "channel": "teams", "id": "x1"}
    name, args = fake.calls[-1]
    assert name == "teams_post" and args["member_or_ref"] == "mem-1"
    assert args["bullets"] == ["one line"] and args["record_ref"] == "portal://draft/0a1b2c3d"
    assert args["body_markdown"] == "[Open issue #3 in acme/app](https://github.com/acme/app/issues/3)"
    assert [n for n, _ in fake.calls].count("send_agent_message") == 0


def test_a_blocked_post_falls_back_to_the_owners_own_email(fake, capsys):
    fake.teams = {"success": False, "decision": "blocked", "reason": "no chat"}
    code, out = notify(capsys)
    assert code == 0 and out["channel"] == "email" and out["sent"] is True
    name, args = fake.calls[-1]
    assert name == "send_agent_message" and args["recipient"] == "owner@owner.test" and args["channel_kind"] == "email"


def test_both_refused_exits_nonzero_with_both_reasons(fake, capsys):
    fake.teams = {"success": False, "decision": "blocked", "reason": "no chat"}
    fake.mail = {"success": False, "decision": "blocked", "reason": "no mailbox"}
    code, out = notify(capsys)
    assert code == 1 and out["sent"] is False and "no chat" in out["reason"] and "no mailbox" in out["reason"]


def test_pending_approval_and_simulated_are_not_sent_and_not_retried(fake, capsys):
    fake.teams = {"success": True, "decision": "pending_approval"}
    code, out = notify(capsys)
    assert code == 1 and out["sent"] is False
    fake.teams = {"success": True, "decision": "sent", "simulated": True}
    code, out = notify(capsys)
    assert code == 1 and "simulated" in out["reason"]
    assert not [n for n, _ in fake.calls if n == "send_agent_message"]


def test_whoami_without_a_member_sends_nothing(fake, capsys):
    fake.member = None
    code, out = notify(capsys)
    assert code == 1 and [n for n, _ in fake.calls] == ["whoami"]


def test_an_unreachable_portal_has_no_fallback(monkeypatch, tmp_path, capsys):
    point_settings_at(monkeypatch, tmp_path, 9)   # nothing listens on port 9
    code, out = notify(capsys)
    assert code == 1 and out["sent"] is False and "unreachable" in out["reason"].lower()


def test_a_redirect_is_refused_so_the_token_goes_nowhere_else(monkeypatch, tmp_path, capsys):
    httpd = serve(FakePortal(), redirect=True)
    point_settings_at(monkeypatch, tmp_path, httpd.server_address[1])
    try:
        code, out = notify(capsys)
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert code == 1 and "redirect" in out["reason"]


@pytest.mark.parametrize("args,message", [
    (["--bullet", "see https://example.com"], "holds a URL"),
    (["--link", "not a url"], "one http(s) URL"),
    (["--record-ref", "task 5"], "portal://"),
])
def test_bad_messages_are_refused_before_anything_is_sent(fake, capsys, args, message):
    import sys
    old = sys.argv
    sys.argv = ["notify_owner", "--title", "t", *args]
    with pytest.raises(SystemExit) as exc:
        no.main()
    sys.argv = old
    assert exc.value.code == 2 and message in capsys.readouterr().err and fake.calls == []


def test_dry_run_and_off_contact_nothing(fake, capsys, monkeypatch):
    code, out = notify(capsys, "--dry-run")
    assert code == 0 and out["dry_run"] is True and out["rendered"].startswith("**Draft reply")
    monkeypatch.setenv("NOTIFY_OWNER_MODE", "off")
    code, out = notify(capsys)
    assert code == 0 and out["sent"] is False and "off" in out["reason"]
    monkeypatch.setenv("NOTIFY_OWNER_MODE", "dry-run")
    code, out = notify(capsys)
    assert code == 0 and "rehearsal" in out["reason"]
    assert fake.calls == []


def test_env_token_beats_the_config_header_and_plain_http_is_refused(monkeypatch, tmp_path):
    config = point_settings_at(monkeypatch, tmp_path, 8080, token_env=False)
    monkeypatch.setenv("TEST_PORTAL_SECRET", "from-config")
    assert c.portal_endpoint()[1] == "Bearer from-config"
    monkeypatch.setenv("INSIGHTS_PORTAL_ASSISTANT_TOKEN", "from-env")
    assert c.portal_endpoint()[1] == "Bearer from-env"
    config.write_text(json.dumps({"mcpServers": {"insights-portal": {
        "url": "http://portal.example.com/mcp", "headers": {"Authorization": "Bearer x"}}}}))
    with pytest.raises(c.Failure, match="HTTPS"):
        c.portal_endpoint()
    monkeypatch.delenv("INSIGHTS_PORTAL_ASSISTANT_TOKEN")
    monkeypatch.delenv("TEST_PORTAL_SECRET")
    point_settings_at(monkeypatch, tmp_path, 8080, token_env=False)
    with pytest.raises(c.Failure) as exc:
        c.portal_endpoint()
    assert "TEST_PORTAL_SECRET" in str(exc.value) and "from-" not in str(exc.value)
