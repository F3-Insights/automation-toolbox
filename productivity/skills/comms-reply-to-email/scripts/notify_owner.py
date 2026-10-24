#!/usr/bin/env python3
"""notify-owner: tell the owner, in their own Teams chat with the Portal bot, by email to their
own address, or both, that something needs them.

It never takes a recipient. The Portal's `teams_post` goes to the token's own member, read
from `whoami`; a user token may post only there. Email goes through the Portal's
`send_agent_message` under the agent's own mailbox (never as the owner) to the member's own
primary address from `whoami`. Bullets are short lines with no links (the Portal wants none in
bullets, so a bullet holding a URL is refused); links go one per paragraph in the body;
--record-ref becomes the Portal's "Open in Portal" button.

--channel picks the route:
- `teams` (the default): Teams first; when Teams refuses (`blocked`) or the tool fails, the
  same message by email. A Portal that cannot be reached has no fallback, since the email
  path goes through the same Portal. `pending_approval` is not a refusal and is not retried
  by email.
- `email`: the owner's own address only.
- `both`: Teams and email, each tried whatever happened to the other, with no fallback between
  them. `sent` is true when at least one went out; `channels` holds each one's outcome.
A `simulated` send is reported as not sent. The email body is plain text rendered from the same
title, bullets, links and record ref.

The environment variable NOTIFY_OWNER_MODE switches it for a runner: `off` sends nothing,
`dry-run` rehearses, anything else (or unset) sends.

Inputs: --title, --bullet (repeatable), --link (repeatable), --record-ref, --channel, --dry-run.
Prints one JSON object on one line, `{sent, channel, id | reason}`, plus `channels` for `both`.
Exit 0 when something was sent, or when nothing was meant to be (off, dry run); 1 when nothing
was sent; 2 on a bad argument. A dry run prints each channel's rendering and call without
reading the token or contacting the Portal.

Example:
    python3 notify_owner.py --title "Draft reply to Dana is in your Drafts" \\
        --link https://outlook.example.com/draft --record-ref portal://draft/<uuid> --channel both
"""

import argparse
import json
import os
import re
import sys

import _common as c

URL_RE = re.compile(r"https?://", re.I)
RECORD_REF_RE = re.compile(r"^portal://[a-z_]+/[A-Za-z0-9-]+$")
OWN_MEMBER = "(the token's own member, from whoami at send time)"
OWN_EMAIL = "(the token's own primary_email, from whoami at send time)"
CHANNELS = ("teams", "email", "both")
EMAIL_TOOL = "send_agent_message"


def render(title, bullets, body_markdown):
    """The Portal's own Teams rendering: bold title, dashed bullets, then the body."""
    parts = [f"**{title.strip()}**"] if title.strip() else []
    parts += [f"- {b.strip()}" for b in bullets if b.strip()]
    if body_markdown and body_markdown.strip():
        parts.append(body_markdown.strip())
    return "\n".join(parts)


def link_label(url):
    """`Open issue #3 in org/repo` for a GitHub issue or pull request, None otherwise."""
    m = re.search(r"github\.com/([^/]+/[^/]+)/(issues|pull)/(\d+)", url)
    if not m:
        return None
    kind = "issue" if m.group(2) == "issues" else "PR"
    return f"Open {kind} #{m.group(3)} in {m.group(1)}"


def link_markdown(url):
    """`[Open issue #3 in org/repo](url)` for a GitHub issue or pull request, the URL otherwise."""
    label = link_label(url)
    return f"[{label}]({url})" if label else url


def render_email(message):
    """Plain text for a mail client: the title, the bullets, one link per line, the record ref."""
    parts = [message["title"]]
    if message["bullets"]:
        parts.append("\n".join(f"- {b}" for b in message["bullets"]))
    links = []
    for url in message.get("links") or []:
        label = link_label(url)
        links.append(f"{label}: {url}" if label else url)
    if links:
        parts.append("\n".join(links))
    if message.get("record_ref"):
        parts.append(f"Portal record: {message['record_ref']}")
    return "\n\n".join(parts)


def build_message(title, bullets, links, record_ref):
    title = title.strip()
    if not title or "\n" in title:
        raise c.Failure("--title is one non-empty line")
    clean = []
    for b in (b.strip() for b in bullets):
        if not b:
            continue
        if "\n" in b:
            raise c.Failure("a --bullet is one line")
        if URL_RE.search(b):
            raise c.Failure("a --bullet holds a URL; the Portal wants none in bullets, so pass it as --link")
        clean.append(b)
    for link in links:
        if not re.match(r"^https?://\S+$", link.strip()):
            raise c.Failure(f"--link must be one http(s) URL, got {link!r}")
    if record_ref is not None and not RECORD_REF_RE.match(record_ref.strip()):
        raise c.Failure("--record-ref must look like portal://<type>/<id>")
    # Teams folds single newlines, so each link is its own paragraph.
    body = "\n\n".join(link_markdown(l.strip()) for l in links) or None
    return {"title": title, "bullets": clean, "body_markdown": body,
            "record_ref": record_ref.strip() if record_ref else None,
            "links": [l.strip() for l in links]}


def teams_arguments(member, message):
    args = {"member_or_ref": member, "title": message["title"]}
    for key in ("bullets", "body_markdown", "record_ref"):
        if message[key]:
            args[key] = message[key]
    return args


def email_arguments(address, message):
    return {"channel_kind": "email", "recipient": address, "body": render_email(message), "action": "initiate"}


def sent(result):
    return bool(result.get("success")) and result.get("decision") == "sent" and not result.get("simulated")


def why(result):
    if result.get("success") and result.get("simulated"):
        return "simulated: the Portal recorded it, but no connector transmitted it"
    return f"{result.get('decision') or 'failed'}: {result.get('reason') or 'no reason given'}"


def post_teams(portal, member, message):
    """One Teams post to the member: (outcome, the Portal's answer, or None when unreachable)."""
    if not member:
        return {"sent": False, "reason": "whoami returned no org_member_id for this token"}, {}
    try:
        answer = portal.call("teams_post", teams_arguments(member, message))
        answer = answer if isinstance(answer, dict) else {"raw": answer}
    except c.PortalUnreachable as exc:
        return {"sent": False, "reason": f"Portal unreachable ({exc})"}, None
    except c.PortalError as exc:
        answer = {"success": False, "decision": "failed", "reason": str(exc)}
    if sent(answer):
        return {"sent": True, "id": answer.get("external_message_id") or answer.get("log_id")}, answer
    return {"sent": False, "reason": why(answer)}, answer


def send_email(portal, address, message):
    """One email to the member's own primary address: the outcome."""
    if not address:
        return {"sent": False, "reason": "whoami returned no primary_email for this token"}
    try:
        answer = portal.call(EMAIL_TOOL, email_arguments(address, message))
        answer = answer if isinstance(answer, dict) else {"raw": answer}
    except c.PortalUnreachable as exc:
        return {"sent": False, "reason": f"Portal unreachable ({exc})"}
    except c.PortalError as exc:
        answer = {"success": False, "decision": "failed", "reason": str(exc)}
    if sent(answer):
        return {"sent": True, "id": answer.get("log_id")}
    return {"sent": False, "reason": why(answer)}


def send(portal, message, channel="teams"):
    """Send on the chosen channel. Never raises for a refusal. The recipient is always the
    token's own member or its own primary address, both from whoami."""
    try:
        me = portal.whoami()
    except c.PortalError as exc:
        return {"sent": False, "channel": channel, "reason": f"Portal unreachable or refused whoami ({exc})"}
    principal = (me or {}).get("principal") or {} if isinstance(me, dict) else {}
    member, address = principal.get("org_member_id"), principal.get("primary_email")

    if channel == "email":
        return {"channel": "email", **send_email(portal, address, message)}

    if channel == "both":
        teams, _ = post_teams(portal, member, message)
        mail = send_email(portal, address, message)
        out = {"sent": teams["sent"] or mail["sent"], "channel": "both",
               "channels": {"teams": teams, "email": mail}}
        first = teams if teams["sent"] else mail if mail["sent"] else None
        if first:
            out["id"] = first["id"]
        else:
            out["reason"] = f"teams {teams['reason']}; email {mail['reason']}"
        return out

    if not member:
        return {"sent": False, "channel": "teams", "reason": "whoami returned no org_member_id for this token"}
    teams, answer = post_teams(portal, member, message)
    if teams["sent"]:
        return {"sent": True, "channel": "teams", "id": teams["id"]}
    if answer is None:
        return {"sent": False, "channel": "teams",
                "reason": f"{teams['reason']}; the email fallback goes through the same Portal"}
    if answer.get("decision") not in ("blocked", "failed"):
        return {"sent": False, "channel": "teams", "reason": teams["reason"]}
    if not address:
        return {"sent": False, "channel": "teams",
                "reason": f"teams {teams['reason']}; no email fallback: whoami returned no primary_email"}
    mail = send_email(portal, address, message)
    if mail["sent"]:
        return {"sent": True, "channel": "email", "id": mail["id"], "teams_reason": teams["reason"]}
    return {"sent": False, "channel": "email", "reason": f"teams {teams['reason']}; email {mail['reason']}"}


def dry_run_result(message, channel, reason):
    """What would go out on each channel and the calls that would carry it; no Portal contact."""
    out = {"sent": False, "channel": channel, "reason": reason, "dry_run": True}
    if channel == "teams":
        # The shape callers already read, plus the body the email fallback would carry.
        out["rendered"] = render(message["title"], message["bullets"], message["body_markdown"])
        out["arguments"] = {"member_or_ref": OWN_MEMBER, **{k: v for k, v in message.items() if k != "links"}}
        out["email_fallback"] = render_email(message)
        return out
    rendered, calls = {}, {}
    if channel == "both":
        rendered["teams"] = render(message["title"], message["bullets"], message["body_markdown"])
        calls["teams_post"] = teams_arguments(OWN_MEMBER, message)
    rendered["email"] = render_email(message)
    calls[EMAIL_TOOL] = email_arguments(OWN_EMAIL, message)
    out["rendered"], out["arguments"] = rendered, calls
    return out


def emit(result):
    """The result as one JSON object on one line, the last line printed."""
    print(c.safe(json.dumps(result)))


def main():
    parser = argparse.ArgumentParser(description="Tell the owner through the Portal: their own Teams chat (email "
                                                 "as the fallback), their own email address, or both.")
    parser.add_argument("--title", required=True, help="the heading, one line")
    parser.add_argument("--bullet", dest="bullets", action="append", default=[], help="a short line, no links (repeatable)")
    parser.add_argument("--link", dest="links", action="append", default=[], help="a URL (repeatable)")
    parser.add_argument("--record-ref", default=None, help="portal://<type>/<id> for an Open in Portal button")
    parser.add_argument("--channel", choices=CHANNELS, default="teams",
                        help="teams (default, email as the fallback), email (own address only), or both")
    parser.add_argument("--dry-run", action="store_true", help="print the rendered message and the call; send nothing")
    args = parser.parse_args()
    try:
        message = build_message(args.title, args.bullets, args.links, args.record_ref)
    except c.Failure as exc:
        print(f"notify-owner: {exc}", file=sys.stderr)
        sys.exit(2)
    mode = os.environ.get("NOTIFY_OWNER_MODE", "").strip().lower()
    if mode == "off":
        emit({"sent": False, "channel": args.channel, "reason": "notifications are off (NOTIFY_OWNER_MODE=off)"})
        return
    dry_run, reason = args.dry_run, "dry run: nothing sent"
    if mode in ("dry-run", "dryrun", "rehearsal") and not dry_run:
        dry_run, reason = True, "rehearsal: nothing sent (NOTIFY_OWNER_MODE=dry-run)"
    if dry_run:
        emit(dry_run_result(message, args.channel, reason))
        return
    try:
        portal = c.client()
    except c.Failure as exc:
        emit({"sent": False, "channel": args.channel, "reason": str(exc)})
        sys.exit(1)
    result = send(portal, message, args.channel)
    emit(result)
    sys.exit(0 if result["sent"] else 1)


if __name__ == "__main__":
    main()
