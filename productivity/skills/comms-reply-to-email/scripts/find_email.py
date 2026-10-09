#!/usr/bin/env python3
"""find-email: a contact id, to the latest email that person sent the owner.

Step 1 of comms-reply-to-email, after find_contact.py pinned the contact. It pins one exact
email ref, reads that email's thread, and says whether the owner already replied after it.
Read only.

Which email: received mail from any address the contact holds, across every inbox the token
may read. Two listings are merged, mail linked to the contact as sender and mail where the
contact is a participant; a row counts only when its sender is one of the contact's own
addresses, so a message the person was merely copied on is never taken for one they sent.
The newest wins. A message the owner sent on the thread after it is a reply.

Input: the contact id (or portal://contact/<id>). Prints one JSON object (`status` ok,
replied or none; `email`; `thread`; `other_recent_inbound`). Exit 0 when an email is pinned
and unanswered, 3 when there is none or the owner already replied after it, 2 on an error.

Example:
    python3 find_email.py portal://contact/2f0c6b1e-0000-4000-8000-000000000001
"""

import argparse

import _common as c

LOOKBACK_ROWS = 25
EPOCH = c.parse_time("1970-01-01")


def contact_card(portal, contact_id):
    out = portal.call("get", {"entity_type": "contact", "id_or_query": contact_id})
    if not isinstance(out, dict) or out.get("error"):
        reason = out.get("error") if isinstance(out, dict) else "no answer"
        raise c.Failure(f"contact {contact_id} could not be read: {reason}")
    record = out.get("contact") if isinstance(out.get("contact"), dict) else {}
    return {"id": record.get("id") or contact_id, "name": record.get("full_name") or "",
            "addresses": c.contact_addresses(out)}


def inbound_rows(portal, contact_id):
    """Received mail linked to the contact as sender or as participant, merged by id."""
    rows, scope = {}, []
    for key in ("contact_id", "participant_contact_id"):
        out = portal.call("list_entities", {"entity_type": "email", "limit": LOOKBACK_ROWS,
                                            "filters": {key: contact_id, "direction": "received"}})
        if not isinstance(out, dict):
            continue
        if out.get("error"):
            raise c.Failure(f"the email listing by {key} failed: {out['error']}")
        if out.get("inbox_scope"):
            scope.append(out["inbox_scope"])
        for row in out.get("items") or []:
            if isinstance(row, dict) and row.get("id"):
                rows.setdefault(str(row["id"]), row)
    return list(rows.values()), scope


def line(m):
    return {"id": m.get("id"), "_ref": c.email_ref(m.get("id")), "direction": m.get("direction"),
            "from_address": c.bare_address(m.get("from_address")), "received_at": m.get("received_at"),
            "received_local": m.get("received_local"), "subject": m.get("subject")}


def find(portal, contact_id):
    contact_id = c.bare_id(contact_id)
    if not contact_id:
        raise c.Failure("give a contact id")
    me = c.owner(portal)
    contact = contact_card(portal, contact_id)
    if not contact["addresses"]:
        return {"status": "none", "reason": "the contact holds no email address", "contact": contact, "email": None}
    rows, scope = inbound_rows(portal, contact_id)
    theirs = [r for r in rows if c.bare_address(r.get("from_address")) in contact["addresses"]]
    theirs.sort(key=lambda r: c.parse_time(r.get("received_at")) or EPOCH, reverse=True)
    notes = []
    if any(isinstance(s, dict) and s.get("excluded_by_inbox") for s in scope):
        notes.append("some matching mail sits in inboxes this token may not read")
    if not theirs:
        return {"status": "none", "contact": contact, "email": None, "notes": notes,
                "reason": f"no inbound email from {', '.join(contact['addresses'])} in any inbox this token may read"}

    target = theirs[0]
    eid = str(target["id"])
    thread = portal.call("get", {"entity_type": "email", "id_or_query": eid})
    if not isinstance(thread, dict) or thread.get("error"):
        raise c.Failure(f"email {eid} could not be read: "
                        f"{thread.get('error') if isinstance(thread, dict) else 'no answer'}")
    messages = [m for m in thread.get("thread") or [] if isinstance(m, dict)]
    pinned_row = next((m for m in messages if str(m.get("id")) == eid), {})
    when = c.parse_time(target.get("received_at"))
    after = [m for m in messages if str(m.get("id")) != eid and when
             and (c.parse_time(m.get("received_at")) or when) > when]
    replies = [m for m in after if str(m.get("direction") or "").lower() == "sent"]
    later_inbound = [m for m in after if str(m.get("direction") or "").lower() != "sent"]
    inbox = c.receiving_inbox(pinned_row or target, me["inboxes"])

    email = {"id": eid, "_ref": c.email_ref(eid), "subject": target.get("subject"),
             "from_address": c.bare_address(target.get("from_address")),
             "received_at": target.get("received_at"), "received_local": target.get("received_local"),
             "to_addresses": pinned_row.get("to_addresses", target.get("to_addresses")),
             "cc_addresses": pinned_row.get("cc_addresses")}
    if replies:
        status, reason = "replied", f"the owner already replied after this email ({replies[-1].get('received_at')})"
    else:
        status, reason = "ok", "the latest inbound email from this contact has no reply from the owner after it"
    if thread.get("thread_truncated"):
        notes.append(f"the thread holds {thread.get('thread_total')} messages; the newest were read")
    if not pinned_row:
        notes.append("the pinned email was not among the thread messages returned")
    return {"status": status, "reason": reason, "contact": contact, "email": email,
            "inbox": inbox["inbox"], "inbox_basis": inbox["basis"],
            "replied_after": bool(replies), "replies_after": [line(m) for m in replies],
            "later_inbound_on_thread": [line(m) for m in later_inbound],
            "thread": {"total": thread.get("thread_total"), "truncated": thread.get("thread_truncated"),
                       "messages": [line(m) for m in messages]},
            "other_recent_inbound": [line(r) for r in theirs[1:5]],
            "timezone": me["timezone"], "notes": notes}


def main():
    parser = argparse.ArgumentParser(description="The latest email this contact sent the owner and whether "
                                                 "the owner replied after it. Exit 0 pinned, 3 none or "
                                                 "replied, 2 error.")
    parser.add_argument("contact_id", help="the pinned contact id or portal://contact/<id>")
    args = parser.parse_args()
    try:
        result = find(c.client(), args.contact_id)
    except Exception as exc:
        c.fail(exc if isinstance(exc, c.Failure) else f"find-email could not complete: {type(exc).__name__}: {exc}")
    c.emit(result, c.OK if result["status"] == "ok" else c.STOP)


if __name__ == "__main__":
    main()
