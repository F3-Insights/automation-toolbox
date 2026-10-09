"""email-deliver's guards: nothing is pushed unless every one passes, and nothing is ever sent.
Also email-draft-show, whose hash the guards compare."""

import json
import re
from pathlib import Path

import pytest

import _common as c
import email_deliver as ed
import email_draft_show as eds
from reply_fixtures import NOW, ago, portal, run  # noqa: F401

SKILL = Path(__file__).resolve().parents[2]


def add_draft(portal, did="d1", **fields):
    draft = {"status": "draft", "subject": "Re: Kickoff", "content": "Hi Dana,\n\nTuesday works.\n\nCheers",
             "recipient_to": ["dana@acme.test"], "recipient_cc": [], "recipient_bcc": [], "contact_id": "c-dana",
             "email_id": "m3", "thread_id": None, "created_at": NOW.isoformat(), "delivered_at": None,
             "provider_draft_id": None}
    draft.update(fields)
    portal.drafts[did] = draft
    return draft


def write_check(tmp_path, portal, did="d1", verdict="PASS", **over):
    record = {"verdict": verdict, "draft_id": did, "content_hash": c.content_hash(portal.drafts[did]),
              "contact_id": "c-dana", "email_ref": "portal://email/m3", "checked": {"dates": "ok"}, "fixes": []}
    record.update(over)
    path = tmp_path / f"check-{did}.json"
    path.write_text(json.dumps(record))
    return path


def deliver(capsys, check, *extra, did="d1"):
    return run(ed, capsys, "--draft", did, "--check", check, "--contact", "c-dana", "--email", "portal://email/m3", *extra)


def pushes(portal):
    return [a["id"] for name, a in portal.calls if name == "draft_push"]


def codes(out):
    return {r["code"] for r in out["refusals"]}


def test_draft_show_prints_a_hash_that_moves_with_the_content(portal, capsys):
    add_draft(portal)
    code, out = run(eds, capsys, "d1")
    assert code == 0 and out["email_ref"] == "portal://email/m3"
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", out["content_hash"])
    first = out["content_hash"]
    portal.drafts["d1"]["content"] += " "
    assert run(eds, capsys, "d1")[1]["content_hash"] != first
    portal.drafts["d1"]["content"] = portal.drafts["d1"]["content"][:-1]
    portal.drafts["d1"]["recipient_to"] = ["DANA@acme.test"]
    assert run(eds, capsys, "d1")[1]["content_hash"] == first   # case in an address is not a change


def test_a_checked_draft_is_pushed_once_to_the_inbox_that_got_the_email(portal, capsys, tmp_path):
    add_draft(portal)
    check = write_check(tmp_path, portal)
    code, out = deliver(capsys, check, "--allow-recent-contact")
    assert code == 0, out
    assert out["status"] == "delivered" and out["delivered_to"] == "owner@owner.test"
    assert out["outbound_check"]["verdict"] == "ALLOW"
    assert pushes(portal) == ["d1"]
    assert json.loads((tmp_path / "delivery-intent.json").read_text())["draft_id"] == "d1"


def test_no_check_record_refuses(portal, capsys, tmp_path):
    add_draft(portal)
    code, out = deliver(capsys, tmp_path / "missing.json", "--allow-recent-contact")
    assert code == 3 and codes(out) == {"UNCHECKED"} and pushes(portal) == []


def test_a_failing_check_refuses(portal, capsys, tmp_path):
    add_draft(portal)
    code, out = deliver(capsys, write_check(tmp_path, portal, verdict="FAIL"), "--allow-recent-contact")
    assert code == 3 and "CHECK_FAILED" in codes(out) and pushes(portal) == []


def test_a_check_for_another_draft_refuses(portal, capsys, tmp_path):
    add_draft(portal)
    code, out = deliver(capsys, write_check(tmp_path, portal, draft_id="d9"), "--allow-recent-contact")
    assert code == 3 and "CHECK_MISMATCH" in codes(out)


def test_a_draft_changed_after_the_check_refuses(portal, capsys, tmp_path):
    add_draft(portal)
    check = write_check(tmp_path, portal)
    portal.drafts["d1"]["content"] += "\nPS: happy to take 10% off."
    code, out = deliver(capsys, check, "--allow-recent-contact")
    assert code == 3 and "CHANGED_SINCE_CHECK" in codes(out) and pushes(portal) == []


@pytest.mark.parametrize("fields,code", [
    ({"recipient_to": ["someone@else.test"]}, "WRONG_RECIPIENT"),
    ({"recipient_cc": ["boss@acme.test"]}, "WRONG_RECIPIENT"),
    ({"contact_id": "c-near"}, "WRONG_RECIPIENT"),
    ({"email_id": "m2"}, "WRONG_THREAD"),
    ({"email_id": None}, "WRONG_THREAD"),
], ids=["other-address", "cc", "other-contact", "other-email", "no-email"])
def test_a_draft_that_strays_from_the_pin_refuses(portal, capsys, tmp_path, fields, code):
    add_draft(portal, **fields)
    status, out = deliver(capsys, write_check(tmp_path, portal), "--allow-recent-contact")
    assert status == 3 and code in codes(out) and pushes(portal) == []


def test_an_older_open_draft_on_the_thread_holds_at_delivery(portal, capsys, tmp_path):
    add_draft(portal)
    add_draft(portal, "d0", email_id="m2", created_at=ago(3))   # answers an older message, predates m3
    code, out = deliver(capsys, write_check(tmp_path, portal), "--allow-recent-contact")
    assert code == 3 and out["outbound_check"]["rule"] == "STALE_DRAFT"
    assert "d0" in out["outbound_check"]["evidence"]["draft_ids"] and pushes(portal) == []


def test_the_draft_being_delivered_is_not_its_own_duplicate(portal, capsys, tmp_path):
    add_draft(portal)
    code, out = deliver(capsys, write_check(tmp_path, portal), "--allow-recent-contact", "--dry-run")
    assert code == 0 and out["status"] == "would_deliver" and out["outbound_check"]["verdict"] == "ALLOW"
    assert pushes(portal) == [] and not (tmp_path / "delivery-intent.json").exists()


def test_a_reply_already_sent_after_the_email_refuses(portal, capsys, tmp_path):
    add_draft(portal)
    portal.emails["m5"] = {"thread": "T1", "direction": "sent", "from_address": "owner@owner.test",
                           "to_addresses": ["dana@acme.test"], "received_at": ago(0, 1), "subject": "Re: Kickoff",
                           "contact_id": None, "body": "Done."}
    code, out = deliver(capsys, write_check(tmp_path, portal), "--allow-recent-contact")
    assert code == 3 and "ALREADY_REPLIED" in codes(out) and pushes(portal) == []


def test_the_cooldown_holds_unless_the_owner_asked_for_the_reply(portal, capsys, tmp_path):
    portal.emails["m1"]["received_at"] = ago(2)   # the owner wrote on the thread two days ago, before m3
    add_draft(portal)
    check = write_check(tmp_path, portal)
    code, out = deliver(capsys, check)
    assert code == 3 and out["outbound_check"]["rule"] == "RECENT_CONTACT" and pushes(portal) == []
    code, out = deliver(capsys, check, "--allow-recent-contact")
    assert code == 0 and out["status"] == "delivered" and out["recent_contact_overridden"] is True


def test_an_already_delivered_draft_refuses(portal, capsys, tmp_path):
    add_draft(portal, delivered_at=ago(0, 1), provider_draft_id="prov-0")
    code, out = deliver(capsys, write_check(tmp_path, portal), "--allow-recent-contact")
    assert code == 3 and "ALREADY_DELIVERED" in codes(out)


def test_a_gmail_inbox_gets_a_compose_link_and_no_push(portal, capsys, tmp_path):
    portal.emails["m3"]["to_addresses"] = ["owner@gmail.test"]
    add_draft(portal)
    code, out = deliver(capsys, write_check(tmp_path, portal), "--allow-recent-contact", "--dry-run")
    assert code == 0 and out["status"] == "would_handoff_link"
    assert not [n for n, _ in portal.calls if n in ("draft_push", "draft_compose_url")]
    code, out = deliver(capsys, write_check(tmp_path, portal), "--allow-recent-contact")
    assert code == 0 and out["status"] == "handoff_link" and out["compose_url"] and pushes(portal) == []


def test_a_failed_push_exits_3_after_recording_the_intent(portal, capsys, tmp_path, monkeypatch):
    add_draft(portal)
    check = write_check(tmp_path, portal)
    seen = {}

    def failing_push(a):
        seen["intent_before_push"] = (tmp_path / "delivery-intent.json").exists()
        raise RuntimeError("Outlook said no")
    monkeypatch.setattr(portal, "draft_push", failing_push)
    code, out = deliver(capsys, check, "--allow-recent-contact")
    assert code == 3 and out["status"] == "push_failed" and seen == {"intent_before_push": True}


def test_an_outbound_check_that_cannot_run_refuses(portal, capsys, tmp_path, monkeypatch):
    monkeypatch.setattr(c, "skill_script", lambda skill, name: tmp_path / "missing.py")
    add_draft(portal)
    code, out = deliver(capsys, write_check(tmp_path, portal), "--allow-recent-contact")
    assert code == 3 and "OUTBOUND_ERROR" in codes(out) and pushes(portal) == []


def test_the_check_schema_requires_what_email_deliver_requires():
    schema = json.loads((SKILL / "briefs" / "checker.schema.json").read_text())
    assert tuple(schema["required"]) == ed.CHECK_REQUIRED


ALLOWED_CALLS = {"find_contact.py": {"get", "search"}, "find_email.py": {"get", "list_entities"},
                 "email_context_pack.py": {"get", "list_entities", "email_bodies"}, "email_draft_show.py": set(),
                 "_common.py": {"get", "list_entities", "whoami"},
                 "email_deliver.py": {"get", "draft_compose_url", "draft_push"},
                 "notify_owner.py": {"teams_post", "send_agent_message"}}


@pytest.mark.parametrize("name", sorted(ALLOWED_CALLS))
def test_only_email_deliver_pushes_and_only_notify_owner_sends(name):
    source = (SKILL / "scripts" / name).read_text()
    called = set(re.findall(r"""\bcall\(\s*["'](\w+)["']""", source))
    called |= set(re.findall(r"""\bcall\(portal,\s*["'](\w+)["']""", source))
    assert called <= ALLOWED_CALLS[name], called - ALLOWED_CALLS[name]
