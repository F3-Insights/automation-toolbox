import find_email as fe
from reply_fixtures import ago, portal, run  # noqa: F401


def test_the_latest_email_they_sent_is_pinned_not_one_they_were_copied_on(portal, capsys):
    code, out = run(fe, capsys, "c-dana")
    assert code == 0 and out["status"] == "ok"
    assert out["email"]["_ref"] == "portal://email/m3" and out["email"]["from_address"] == "dana@acme.test"
    assert out["replied_after"] is False
    assert out["inbox"]["address"] == "owner@owner.test"
    assert [m["id"] for m in out["thread"]["messages"]] == ["m1", "m2", "m3"]


def test_a_reply_by_the_owner_after_it_stops_the_run(portal, capsys):
    portal.emails["m5"] = {"thread": "T1", "direction": "sent", "from_address": "owner@owner.test",
                           "to_addresses": ["dana@acme.test"], "received_at": ago(0, 1), "subject": "Re: Kickoff",
                           "contact_id": None, "body": "Done."}
    code, out = run(fe, capsys, "portal://contact/c-dana")
    assert code == 3 and out["status"] == "replied" and [m["id"] for m in out["replies_after"]] == ["m5"]


def test_no_inbound_email(portal, capsys):
    code, out = run(fe, capsys, "c-quiet")
    assert code == 3 and out["status"] == "none" and out["email"] is None


def test_an_unknown_contact_is_an_error_not_a_none(portal, capsys):
    code, out = run(fe, capsys, "c-missing")
    assert code == 2 and out["status"] == "error"
