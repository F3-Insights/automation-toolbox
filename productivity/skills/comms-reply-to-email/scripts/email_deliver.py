#!/usr/bin/env python3
"""email-deliver: put one checked reply draft into the owner's Outlook Drafts folder.

Step 7 of comms-reply-to-email. It never sends: the Portal's `draft_push` puts the draft in
the owner's own Drafts folder, threaded under the email it answers, and the owner reads it
and presses Send. The guard rails live here, in code. It refuses, and pushes nothing, when:

- UNCHECKED, CHECK_FAILED, CHECK_MISMATCH: the check record is missing, malformed, not a PASS,
  or for another draft, contact or email;
- CHANGED_SINCE_CHECK: the draft's content hash differs from the one the checker recorded;
- NOT_A_PENDING_DRAFT, ALREADY_DELIVERED: the draft is sent, deleted or already in Outlook;
- WRONG_THREAD: the draft does not answer the pinned email;
- WRONG_RECIPIENT: the draft is not for the pinned contact, is addressed to anyone who is not
  one of that contact's addresses, carries a Cc or Bcc (a pushed reply applies neither), or
  the pinned email was not sent by the contact (Outlook addresses a reply to the sender);
- ALREADY_REPLIED: the owner sent a message on the thread after the pinned email;
- OUTBOUND_HOLD, OUTBOUND_ERROR: outbound-check (comms-draft-check), re-run here with this
  draft left out of the ledger, holds or could not run. RECENT_CONTACT refuses unless
  --allow-recent-contact (the owner asked for this reply), and the result records the override.

An email that arrived in a Gmail inbox cannot take a push: the draft stays in the Portal and a
compose link is returned (`status: handoff_link`). Before the push it writes
delivery-intent.json beside the check record, so a push that lands before a crash leaves a
trace.

Inputs: --draft, --check (the checker's JSON record), --contact, --email, and optionally
--allow-recent-contact, --dry-run and --config (an MCP config in place of the setting).
Prints one JSON object. Exit 0 delivered, handoff_link or would_deliver (dry run), 3 refused
or push_failed, 2 on an error.

Example:
    python3 email_deliver.py --draft D --check RUN/check.json --contact C --email portal://email/E
"""

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import _common as c

CHECK_REQUIRED = ("verdict", "draft_id", "content_hash", "contact_id", "email_ref")
CLOSED = {"sent", "deleted", "discarded", "cancelled", "canceled"}
EXIT = {"delivered": c.OK, "handoff_link": c.OK, "would_deliver": c.OK, "would_handoff_link": c.OK,
        "refused": c.STOP, "push_failed": c.STOP}


def load_check(path):
    p = Path(path).expanduser()
    if not p.is_file():
        raise ValueError(f"no check record at {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        raise ValueError(f"the check record at {p} is not JSON") from None
    if not isinstance(data, dict):
        raise ValueError("the check record is not a JSON object")
    missing = [k for k in CHECK_REQUIRED if not data.get(k)]
    if missing:
        raise ValueError(f"the check record lacks {', '.join(missing)}")
    return data


def outbound_gate(address, thread, exclude_draft, per_person_days=None):
    """Run outbound-check from comms-draft-check and return its JSON verdict. Exit 0 is ALLOW
    and 3 is HOLD, both with JSON; anything else is a check that did not run."""
    argv = ["python3", str(c.skill_script("comms-draft-check", "outbound_check.py")), "--to", address,
            "--thread", thread, "--exclude-draft", exclude_draft, "--json"]
    if per_person_days is not None:
        argv += ["--per-person-days", str(per_person_days)]
    done = subprocess.run(argv, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL)
    if done.returncode not in (0, 3):
        raise c.Failure(f"outbound-check exited {done.returncode}")
    return json.loads(done.stdout)


def write_intent(check_path, draft_id, **extra):
    """delivery-intent.json beside the check record, written before the push."""
    path = Path(check_path).expanduser().parent / "delivery-intent.json"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({"draft_id": draft_id, "started_at": datetime.now(timezone.utc).isoformat(
        timespec="seconds"), **extra}, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def deliver(portal, draft_id, check_path, contact_id, email, allow_recent_contact=False, dry_run=False,
            gate=outbound_gate):
    draft_id, contact_id, email_id = c.bare_id(draft_id), c.bare_id(contact_id), c.bare_id(email)
    if not (draft_id and contact_id and email_id):
        raise c.Failure("--draft, --contact and --email are all required")
    out = {"status": "refused", "draft_id": draft_id, "contact_id": contact_id,
           "email_ref": c.email_ref(email_id), "refusals": []}
    refusals = out["refusals"]

    def refuse(code, reason):
        refusals.append({"code": code, "reason": reason})

    # 1. The check record is a PASS for exactly this draft, contact and email.
    try:
        check = load_check(check_path)
    except ValueError as exc:
        refuse("UNCHECKED", str(exc))
        return out
    if str(check["verdict"]).upper() != "PASS":
        refuse("CHECK_FAILED", f"the check record says {check['verdict']}, not PASS")
    if c.bare_id(check["draft_id"]) != draft_id:
        refuse("CHECK_MISMATCH", "the check record is for another draft")
    if c.bare_id(check["contact_id"]) != contact_id or c.bare_id(check["email_ref"]) != email_id:
        refuse("CHECK_MISMATCH", "the check record is for another contact or email")
    if refusals:
        return out

    # 2. The draft as it is now: still pending, and unchanged since the check.
    draft = c.read_draft(portal, draft_id)
    status = str(draft.get("status") or "").lower()
    if status in CLOSED or draft.get("deleted_at"):
        refuse("NOT_A_PENDING_DRAFT", f"the draft is {status or 'deleted'}")
    if draft.get("delivered_at") or draft.get("provider_draft_id"):
        refuse("ALREADY_DELIVERED", "the draft is already in the Outlook Drafts folder")
    out["content_hash"] = c.content_hash(draft)
    if out["content_hash"] != check["content_hash"]:
        refuse("CHANGED_SINCE_CHECK", "the draft changed after it was checked; check it again")

    # 3. Addressed to the pinned contact only, answering the pinned email.
    if c.bare_id(draft.get("email_id")) != email_id:
        refuse("WRONG_THREAD", "the draft does not answer the pinned email" if draft.get("email_id")
               else "the draft answers no email, so it would be pushed as a new message")
    if c.bare_id(draft.get("contact_id")) != contact_id:
        refuse("WRONG_RECIPIENT", "the draft is not tied to the pinned contact")
    card = portal.call("get", {"entity_type": "contact", "id_or_query": contact_id})
    allowed = c.contact_addresses(card) if isinstance(card, dict) and not card.get("error") else []
    if not allowed:
        refuse("WRONG_RECIPIENT", "the pinned contact's addresses could not be read")
    to = c.addresses_in(draft.get("recipient_to"))
    stray = [a for a in to if a not in allowed]
    if not to or stray:
        refuse("WRONG_RECIPIENT", "the draft is addressed to someone other than the pinned contact: "
                                  f"{', '.join(stray) or 'no recipient'}")
    if c.addresses_in(draft.get("recipient_cc")) or c.addresses_in(draft.get("recipient_bcc")):
        refuse("WRONG_RECIPIENT", "the draft carries a Cc or Bcc, which a pushed reply does not apply")
    thread = portal.call("get", {"entity_type": "email", "id_or_query": email_id})
    messages = [m for m in thread.get("thread") or [] if isinstance(m, dict)] if isinstance(thread, dict) else []
    pinned = next((m for m in messages if c.bare_id(m.get("id")) == email_id), None)
    if pinned is None:
        refuse("WRONG_THREAD", "the pinned email could not be read")
    else:
        if c.bare_address(pinned.get("from_address")) not in allowed:
            refuse("WRONG_RECIPIENT", "the pinned email was not sent by the pinned contact, "
                                      "and Outlook addresses a reply to the sender")
        when = c.parse_time(pinned.get("received_at"))
        later_sent = [m for m in messages if str(m.get("direction") or "").lower() == "sent"
                      and when and (c.parse_time(m.get("received_at")) or when) > when]
        if later_sent:
            refuse("ALREADY_REPLIED", "the owner sent a message on this thread after the pinned email "
                                      f"({later_sent[-1].get('received_at')})")

    # 4. outbound-check, with this draft left out of its own ledger.
    address = to[0] if to else (allowed[0] if allowed else "")
    overridden = False
    try:
        verdict = gate(address, c.email_ref(email_id), draft_id)
        if verdict["verdict"] == "HOLD" and verdict["rule"] == "RECENT_CONTACT" and allow_recent_contact:
            overridden = True
            verdict = gate(address, c.email_ref(email_id), draft_id, per_person_days=0)
        out["outbound_check"] = {k: verdict.get(k) for k in ("verdict", "rule", "reason", "evidence")}
        if verdict["verdict"] != "ALLOW":
            refuse("OUTBOUND_HOLD", f"outbound-check holds: {verdict['rule']}, {verdict['reason']}")
    except Exception as exc:  # a gate that could not run has not been satisfied
        refuse("OUTBOUND_ERROR", f"outbound-check could not run: {type(exc).__name__}")
    out["recent_contact_overridden"] = overridden
    if refusals:
        return out

    # 5. Where it goes, then the push.
    inbox = c.receiving_inbox(pinned or {}, c.owner(portal)["inboxes"])
    out["inbox_basis"] = inbox["basis"]
    target = inbox["inbox"]
    if dry_run:
        # Before the Gmail branch: building a compose link is itself a handoff the Portal records.
        out.update(status="would_handoff_link" if c.is_gmail(target) else "would_deliver",
                   delivered_to=target["address"] if target else None)
        return out
    if c.is_gmail(target):
        link = portal.call("draft_compose_url", {"id": draft_id, "target": "gmail"})
        out.update(status="handoff_link", delivered_to=None,
                   reason=f"the email arrived in the Gmail inbox {target['address']}; the Portal cannot deliver "
                          "into Gmail, so the draft stays in the Portal",
                   compose_url=link.get("url") if isinstance(link, dict) else None)
        return out
    write_intent(check_path, draft_id, contact_id=contact_id, email_ref=c.email_ref(email_id))
    try:
        pushed = portal.call("draft_push", {"id": draft_id})
    except c.PortalError as exc:
        out.update(status="push_failed", reason=str(exc), note="the draft is unharmed and still in the Portal under its id")
        return out
    pushed = pushed if isinstance(pushed, dict) else {}
    out.update(status="delivered",
               delivered_to=target["address"] if target else "the Outlook inbox that received the email",
               web_link=pushed.get("web_link"), provider_draft_id=pushed.get("provider_draft_id"),
               warning=pushed.get("warning"))
    return out


def main():
    parser = argparse.ArgumentParser(description="Put one checked reply draft into the owner's Outlook Drafts "
                                                 "folder. Never sends. Exit 0 delivered, 3 refused, 2 error.")
    parser.add_argument("--draft", required=True, help="the Portal draft id")
    parser.add_argument("--check", required=True, help="the check record the checker returned (JSON file)")
    parser.add_argument("--contact", required=True, help="the pinned contact id")
    parser.add_argument("--email", required=True, help="the pinned email ref or id")
    parser.add_argument("--allow-recent-contact", action="store_true",
                        help="the owner asked for this reply: a RECENT_CONTACT hold does not refuse it")
    parser.add_argument("--dry-run", action="store_true", help="run every check, push nothing")
    parser.add_argument("--config", default="", help="the MCP config holding the Portal (default: the setting)")
    args = parser.parse_args()
    try:
        result = deliver(c.client(args.config or None), args.draft, args.check, args.contact, args.email,
                         args.allow_recent_contact, args.dry_run)
    except Exception as exc:
        c.fail(exc if isinstance(exc, c.Failure) else f"email-deliver could not complete: {type(exc).__name__}: {exc}")
    c.emit(result, EXIT.get(result["status"], c.ERROR))


if __name__ == "__main__":
    main()
