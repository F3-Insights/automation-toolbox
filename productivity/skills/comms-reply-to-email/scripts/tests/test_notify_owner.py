"""notify-owner sends only to the token's own member and own address, never to a recipient it
is given; on --channel teams it falls back to email only when Teams refuses, on email it sends
email only, and on both it tries each channel whatever happened to the other."""

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
            if isinstance(self.mail, Exception):
                raise self.mail
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


def names(fake):
    return [n for n, _ in fake.calls]


@pytest.mark.parametrize("extra", [[], ["--dry-run"], ["--channel", "both"]])
def test_the_result_is_one_json_object_on_one_line(fake, capsys, extra):
    # Sentinel's notify.py parses the last line of stdout as the JSON answer.
    import sys
    old = sys.argv
    sys.argv = ["notify_owner", "--title", "t", *extra]
    try:
        no.main()
    except SystemExit:
        pass
    finally:
        sys.argv = old
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1 and isinstance(json.loads(lines[-1]), dict)


def test_channel_teams_is_the_default_and_sends_no_email_when_teams_works(fake, capsys):
    code, out = notify(capsys, "--channel", "teams")
    assert code == 0 and out == {"sent": True, "channel": "teams", "id": "x1"}
    assert names(fake) == ["whoami", "teams_post"]


def test_channel_email_goes_only_to_the_owners_own_address(fake, capsys):
    code, out = notify(capsys, "--channel", "email", "--bullet", "one line",
                       "--link", "https://github.com/acme/app/issues/3", "--record-ref", "portal://draft/0a1b2c3d")
    assert code == 0 and out == {"sent": True, "channel": "email", "id": "l1"}
    assert names(fake) == ["whoami", "send_agent_message"]
    args = fake.calls[-1][1]
    assert args["recipient"] == "owner@owner.test" and args["channel_kind"] == "email"
    assert args["body"] == ("Draft reply to Dana is in your Drafts\n\n- one line\n\n"
                            "Open issue #3 in acme/app: https://github.com/acme/app/issues/3\n\n"
                            "Portal record: portal://draft/0a1b2c3d")


def test_channel_email_refused_exits_nonzero_and_never_tries_teams(fake, capsys):
    fake.mail = {"success": False, "decision": "blocked", "reason": "no mailbox"}
    code, out = notify(capsys, "--channel", "email")
    assert code == 1 and out["sent"] is False and "no mailbox" in out["reason"]
    assert "teams_post" not in names(fake)


def test_channel_both_sends_the_same_content_on_both(fake, capsys):
    code, out = notify(capsys, "--channel", "both", "--bullet", "one line")
    assert code == 0 and out["sent"] is True and out["channel"] == "both" and out["id"] == "x1"
    assert out["channels"] == {"teams": {"sent": True, "id": "x1"}, "email": {"sent": True, "id": "l1"}}
    calls = dict(fake.calls)
    assert calls["teams_post"]["member_or_ref"] == "mem-1" and calls["teams_post"]["bullets"] == ["one line"]
    assert calls["send_agent_message"]["recipient"] == "owner@owner.test"
    assert "- one line" in calls["send_agent_message"]["body"]


@pytest.mark.parametrize("failing", ["teams", "email"])
def test_channel_both_one_failing_does_not_stop_the_other(fake, capsys, failing):
    if failing == "teams":
        fake.teams = RuntimeError("teams is down")
    else:
        fake.mail = {"success": False, "decision": "blocked", "reason": "no mailbox"}
    code, out = notify(capsys, "--channel", "both")
    other = "email" if failing == "teams" else "teams"
    assert code == 0 and out["sent"] is True
    assert out["channels"][failing]["sent"] is False and out["channels"][other]["sent"] is True
    assert names(fake).count("teams_post") == 1 and names(fake).count("send_agent_message") == 1


def test_channel_both_with_neither_sent_exits_nonzero_with_both_reasons(fake, capsys):
    fake.teams = {"success": False, "decision": "blocked", "reason": "no chat"}
    fake.mail = {"success": True, "decision": "sent", "simulated": True}
    code, out = notify(capsys, "--channel", "both")
    assert code == 1 and out["sent"] is False and "no chat" in out["reason"] and "simulated" in out["reason"]
    assert out["channels"]["teams"]["sent"] is False and out["channels"]["email"]["sent"] is False


def test_dry_run_both_prints_both_renderings_and_contacts_nothing(fake, capsys):
    code, out = notify(capsys, "--channel", "both", "--dry-run", "--bullet", "one line",
                       "--link", "https://example.com/x")
    assert code == 0 and out["dry_run"] is True and out["channel"] == "both" and fake.calls == []
    assert out["rendered"]["teams"].startswith("**Draft reply") and "- one line" in out["rendered"]["teams"]
    assert out["rendered"]["email"].startswith("Draft reply") and "https://example.com/x" in out["rendered"]["email"]
    assert set(out["arguments"]) == {"teams_post", "send_agent_message"}
    assert "whoami" in out["arguments"]["send_agent_message"]["recipient"]


def test_dry_run_email_prints_only_the_email(fake, capsys, monkeypatch):
    monkeypatch.setenv("NOTIFY_OWNER_MODE", "dry-run")
    code, out = notify(capsys, "--channel", "email")
    assert code == 0 and "rehearsal" in out["reason"] and set(out["rendered"]) == {"email"}
    assert fake.calls == []


def test_an_unknown_channel_is_a_bad_argument(fake, capsys):
    import sys
    old = sys.argv
    sys.argv = ["notify_owner", "--title", "t", "--channel", "slack"]
    with pytest.raises(SystemExit) as exc:
        no.main()
    sys.argv = old
    assert exc.value.code == 2 and fake.calls == []


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
