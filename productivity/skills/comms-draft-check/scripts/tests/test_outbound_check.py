"""outbound-check is a safety gate, so these tests are about the ways it can be wrong. The Portal
is an in-memory fake; the clock is pinned to Monday 2030-03-04 12:00 UTC so the weekend
arithmetic can be checked by reading the dates."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import _common as c  # noqa: E402
import outbound_check as oc  # noqa: E402

MONDAY = datetime(2030, 3, 4, 12, 0, tzinfo=timezone.utc)
TO = "jordan@example.com"


class FakePortal:
    def __init__(self, drafts=(), thread=(), tz="America/Chicago", fail=None):
        self.drafts, self.thread, self.tz, self.fail = list(drafts), list(thread), tz, fail
        self.calls = []

    def call(self, tool, args=None):
        args = dict(args or {})
        self.calls.append((tool, args))
        if self.fail:
            raise self.fail
        if tool == "whoami":
            return {"principal": {"timezone": self.tz} if self.tz else {}}
        if tool == "list_entities":
            return {"items": list(self.drafts), "has_more": False}
        if tool == "get" and args["entity_type"] == "email":
            return {"thread": list(self.thread)}
        if tool == "get" and args["entity_type"] == "draft":
            row = next((d for d in self.drafts if d["id"] == args["id_or_query"]), None)
            return dict(row, email_id=row.get("_email_id")) if row else {"error": "not found"}
        return {"error": "not found"}


def draft(**fields):
    base = {"id": "d1", "status": "draft", "to": [TO], "subject": "February results", "thread_id": "abc123",
            "created_at": "2030-03-04T09:00:00Z"}
    base.update(fields)
    return base


def sent(**fields):
    base = {"id": "e1", "direction": "sent", "subject": "February results", "sent_at": "2030-03-04T08:00:00Z"}
    base.update(fields)
    return base


def check(portal, **kwargs):
    kwargs.setdefault("now", MONDAY)
    return oc.run(portal, TO, **kwargs)


def test_empty_ledger_allows():
    result = check(FakePortal())
    assert result["verdict"] == "ALLOW" and result["rule"] is None and result["checked"] == {"drafts": 0, "sent": 0}


def test_open_draft_on_the_same_thread_holds():
    result = check(FakePortal(drafts=[draft()]), thread="portal://email/abc123")
    assert result["rule"] == "OPEN_DRAFT_SAME_THREAD" and result["evidence"]["draft_ids"] == ["d1"]


def test_a_sent_draft_does_not_hold_and_unknown_status_does():
    assert check(FakePortal(drafts=[draft(status="sent", created_at="2030-02-01T09:00:00Z")]), thread="abc123",
                 per_person_days=0)["verdict"] == "ALLOW"
    assert check(FakePortal(drafts=[draft(status="marinating")]), thread="abc123")["rule"] == "OPEN_DRAFT_SAME_THREAD"


def test_no_thread_falls_back_to_recipient_and_subject():
    result = check(FakePortal(drafts=[draft(thread_id="", subject="Re: February Results")]), subject="February results")
    assert result["rule"] == "OPEN_DRAFT_SAME_THREAD" and result["evidence"]["matched_on"] == "recipient and subject"


def test_recent_contact_by_a_draft_or_a_sent_message_on_the_thread_holds():
    result = check(FakePortal(drafts=[draft(thread_id="other", created_at="2030-03-01T09:00:00Z")]), thread="abc123")
    assert result["rule"] == "RECENT_CONTACT" and result["evidence"]["dates"] == ["2030-03-01"]
    result = check(FakePortal(thread=[sent(sent_at="2030-02-28T09:00:00Z")]), thread="abc123")
    assert result["rule"] == "RECENT_CONTACT" and result["evidence"]["sent_to_recipient"] == 1
    assert check(FakePortal(thread=[sent(sent_at="2030-02-01T09:00:00Z")]), thread="abc123")["verdict"] == "ALLOW"


def test_a_friday_message_holds_a_monday_nudge_at_one_business_day():
    result = check(FakePortal(thread=[sent(sent_at="2030-03-01T15:00:00Z")]), thread="abc123", per_person_days=1)
    assert result["rule"] == "RECENT_CONTACT"


def test_daily_cap_counts_today_only_in_the_owners_timezone():
    today = [draft(id=f"d{n}", to=["else@example.com"], thread_id=f"t{n}") for n in range(10)]
    result = check(FakePortal(drafts=today), thread="abc123", daily_cap=10)
    assert result["rule"] == "DAILY_CAP" and result["evidence"]["timezone"] == "America/Chicago"
    old = [draft(id=f"d{n}", to=["else@example.com"], thread_id=f"t{n}", created_at="2030-03-01T09:00:00Z")
           for n in range(20)]
    assert check(FakePortal(drafts=old), thread="abc123", daily_cap=2)["verdict"] == "ALLOW"


def test_the_rules_are_evaluated_in_order():
    drafts = [draft(id=f"d{n}") for n in range(12)]
    assert check(FakePortal(drafts=drafts), thread="abc123", daily_cap=1)["rule"] == "OPEN_DRAFT_SAME_THREAD"


THREAD = [{"id": "m-a", "direction": "received", "received_at": "2030-02-26T22:00:00+00:00"},
          {"id": "m-b", "direction": "sent", "received_at": "2030-03-01T06:00:00+00:00"},
          {"id": "m-c", "direction": "received", "received_at": "2030-03-04T10:00:00+00:00"}]


def old_draft(**fields):
    base = {"id": "d-old", "status": "draft", "to": [TO], "thread_id": "", "_email_id": "m-a",
            "created_at": "2030-02-26T23:00:00Z"}
    base.update(fields)
    return base


def test_an_older_draft_answering_an_earlier_email_is_stale_not_a_duplicate():
    result = check(FakePortal(drafts=[old_draft()], thread=THREAD), thread="portal://email/m-c", per_person_days=0)
    assert result["rule"] == "STALE_DRAFT" and result["evidence"]["answers"] == ["m-a"]
    # The same draft asked about the email it answers is a duplicate; so is an undated one.
    assert check(FakePortal(drafts=[old_draft()], thread=THREAD), thread="m-a",
                 per_person_days=0)["rule"] == "OPEN_DRAFT_SAME_THREAD"
    assert check(FakePortal(drafts=[old_draft(created_at=None)], thread=THREAD), thread="m-c",
                 per_person_days=0)["rule"] == "OPEN_DRAFT_SAME_THREAD"


def test_the_draft_being_delivered_is_left_out_of_its_own_ledger():
    result = check(FakePortal(drafts=[draft()]), thread="abc123", exclude_draft="portal://draft/d1", per_person_days=0)
    assert result["verdict"] == "ALLOW" and result["excluded_draft"] == "d1"


def test_an_item_with_no_recipient_or_thread_still_counts_toward_the_cap():
    result = check(FakePortal(drafts=[{"id": "x", "status": "draft", "created_at": "2030-03-04T09:00:00Z"}]),
                   thread="abc123", daily_cap=1)
    assert result["rule"] == "DAILY_CAP" and any("neither a recipient" in w for w in result["warnings"])


def test_a_missing_or_unknown_timezone_falls_back_to_utc_with_a_warning():
    assert any("UTC" in w for w in check(FakePortal(tz=None))["warnings"])
    assert any("unknown timezone" in w for w in check(FakePortal(tz="Mars/Base"))["warnings"])


def test_bad_arguments_raise_rather_than_producing_a_verdict():
    with pytest.raises(c.Failure):
        oc.run(FakePortal(), "not an address")
    with pytest.raises(c.Failure):
        oc.run(FakePortal(), TO, daily_cap=0)


def test_subjects_and_recipients_normalise():
    assert oc.normalise_subject("RE: Fwd:  February   Results") == "february results"
    assert oc.emails_in([{"email": "Jordan <JORDAN@example.com>"}, "a@x.test; b@y.test"]) == \
        ["jordan@example.com", "a@x.test", "b@y.test"]


def test_explain_reports_keys_and_never_values():
    result = check(FakePortal(drafts=[draft()]), thread="zzz", per_person_days=0)
    assert "to" in result["explain"]["draft"]["keys"] and TO not in json.dumps(result["explain"])


def run_cli(monkeypatch, capsys, portal, *args):
    monkeypatch.setattr(c, "client", lambda: portal)
    monkeypatch.setattr(sys, "argv", ["outbound_check.py", "--to", TO, *args])
    with pytest.raises(SystemExit) as exc:
        oc.main()
    return exc.value.code, capsys.readouterr()


def test_cli_exit_codes_and_json(monkeypatch, capsys):
    code, out = run_cli(monkeypatch, capsys, FakePortal(), "--json")
    assert code == 0 and set(json.loads(out.out)) == {"verdict", "rule", "reason", "evidence", "checked"}
    code, out = run_cli(monkeypatch, capsys, FakePortal(drafts=[draft()]), "--thread", "abc123")
    assert code == 3 and out.out.startswith("HOLD OPEN_DRAFT_SAME_THREAD")
    code, out = run_cli(monkeypatch, capsys, FakePortal(fail=RuntimeError("down")))
    assert code == 2 and "ERROR" in out.err


def test_a_missing_setting_exits_two_without_reaching_the_portal(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "none.toml"))
    monkeypatch.setattr(sys, "argv", ["outbound_check.py", "--to", TO])
    with pytest.raises(SystemExit) as exc:
        oc.main()
    assert exc.value.code == 2 and "portal_mcp_config" in capsys.readouterr().err


def test_the_token_never_appears_in_output(monkeypatch, capsys):
    secret = "Bearer sk-live-abcdef123456"
    code, out = run_cli(monkeypatch, capsys, FakePortal(fail=RuntimeError(f"Authorization: {secret}")))
    assert code == 2 and "abcdef123456" not in out.err + out.out
