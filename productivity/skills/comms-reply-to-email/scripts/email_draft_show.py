#!/usr/bin/env python3
"""email-draft-show: one Portal draft as the checker reads it, with its content hash.

Step 6 of comms-reply-to-email. The checker reads the draft through this script because the
hash it prints goes into the check record, and email_deliver.py compares it with the live
draft: a draft changed after it was checked is refused at delivery. Read only.

Input: the draft id. Prints one JSON object: subject, body, recipients, the contact and email
the draft is tied to, its status and delivery state, and `content_hash`. Exit 0, or 2 on an
error.

Example:
    python3 email_draft_show.py 7d4e2a10-0000-4000-8000-000000000002
"""

import argparse

import _common as c


def show(portal, draft_id):
    draft = c.read_draft(portal, draft_id)
    return {"draft_id": draft.get("id"), "_ref": f"portal://draft/{draft.get('id')}",
            "status": draft.get("status"), "subject": draft.get("subject"), "content": draft.get("content"),
            "recipient_to": c.addresses_in(draft.get("recipient_to")),
            "recipient_cc": c.addresses_in(draft.get("recipient_cc")),
            "recipient_bcc": c.addresses_in(draft.get("recipient_bcc")),
            "contact_id": draft.get("contact_id"), "email_ref": c.email_ref(draft.get("email_id")) or None,
            "delivered_at": draft.get("delivered_at"), "created_at": draft.get("created_at"),
            "updated_at": draft.get("updated_at"), "content_hash": c.content_hash(draft),
            "hashed_fields": list(c.HASHED_FIELDS)}


def main():
    parser = argparse.ArgumentParser(description="One Portal draft with its content hash, for the checker. Read only.")
    parser.add_argument("draft_id")
    args = parser.parse_args()
    try:
        result = show(c.client(), args.draft_id)
    except Exception as exc:
        c.fail(exc if isinstance(exc, c.Failure) else f"email-draft-show could not complete: {type(exc).__name__}: {exc}")
    c.emit(result, c.OK)


if __name__ == "__main__":
    main()
