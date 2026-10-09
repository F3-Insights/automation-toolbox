#!/usr/bin/env python3
"""notify-owner: tell the owner, in their own Teams chat with the Portal bot, that something
needs them.

It never takes a recipient. The Portal's `teams_post` goes to the token's own member, read
from `whoami`; a user token may post only there. Bullets are short lines with no links (the
Portal wants none in bullets, so a bullet holding a URL is refused); links go one per
paragraph in the body; --record-ref becomes the Portal's "Open in Portal" button.

When Teams refuses (`blocked`) or the tool fails, it falls back to the Portal's email path,
`send_agent_message` to the member's own primary address from `whoami`. A Portal that cannot
be reached has no fallback, since the email path goes through the same Portal.
`pending_approval` is not a refusal and is not retried by email; a `simulated` send is
reported as not sent.

The environment variable NOTIFY_OWNER_MODE switches it for a runner: `off` sends nothing,
`dry-run` rehearses, anything else (or unset) sends.

Inputs: --title, --bullet (repeatable), --link (repeatable), --record-ref, --dry-run. Prints
one JSON object `{sent, channel, id | reason}`. Exit 0 when something was sent, or when
nothing was meant to be (off, dry run); 1 when a send failed; 2 on a bad argument. A dry run
prints the rendered message and the call without reading the token or contacting the Portal.

Example:
    python3 notify_owner.py --title "Draft reply to Dana is in your Drafts" \\
        --link https://outlook.example.com/draft --record-ref portal://draft/<uuid>
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


def render(title, bullets, body_markdown):
    """The Portal's own rendering: bold title, dashed bullets, then the body."""
    parts = [f"**{title.strip()}**"] if title.strip() else []
    parts += [f"- {b.strip()}" for b in bullets if b.strip()]
    if body_markdown and body_markdown.strip():
        parts.append(body_markdown.strip())
    return "\n".join(parts)


def link_markdown(url):
    """`[Open issue #3 in org/repo](url)` for a GitHub issue or pull request, the URL otherwise."""
    m = re.search(r"github\.com/([^/]+/[^/]+)/(issues|pull)/(\d+)", url)
    if not m:
        return url
    kind = "issue" if m.group(2) == "issues" else "PR"
    return f"[Open {kind} #{m.group(3)} in {m.group(1)}]({url})"


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
            "record_ref": record_ref.strip() if record_ref else None}


def sent(result):
    return bool(result.get("success")) and result.get("decision") == "sent" and not result.get("simulated")


def why(result):
    if result.get("success") and result.get("simulated"):
        return "simulated: the Portal recorded it, but no connector transmitted it"
    return f"{result.get('decision') or 'failed'}: {result.get('reason') or 'no reason given'}"


def send(portal, message):
    """Teams first, the Portal's email path when Teams refuses. Never raises for a refusal."""
    try:
        me = portal.whoami()
    except c.PortalError as exc:
        return {"sent": False, "channel": "teams", "reason": f"Portal unreachable or refused whoami ({exc})"}
    principal = (me or {}).get("principal") or {} if isinstance(me, dict) else {}
    member = principal.get("org_member_id")
    if not member:
        return {"sent": False, "channel": "teams", "reason": "whoami returned no org_member_id for this token"}

    args = {"member_or_ref": member, "title": message["title"]}
    for key in ("bullets", "body_markdown", "record_ref"):
        if message[key]:
            args[key] = message[key]
    try:
        teams = portal.call("teams_post", args)
        teams = teams if isinstance(teams, dict) else {"raw": teams}
    except c.PortalUnreachable as exc:
        return {"sent": False, "channel": "teams",
                "reason": f"Portal unreachable ({exc}); the email fallback goes through the same Portal"}
    except c.PortalError as exc:
        teams = {"success": False, "decision": "failed", "reason": str(exc)}
    if sent(teams):
        return {"sent": True, "channel": "teams", "id": teams.get("external_message_id") or teams.get("log_id")}
    if teams.get("decision") not in ("blocked", "failed"):
        return {"sent": False, "channel": "teams", "reason": why(teams)}

    email = principal.get("primary_email")
    if not email:
        return {"sent": False, "channel": "teams",
                "reason": f"teams {why(teams)}; no email fallback: whoami returned no primary_email"}
    text = render(message["title"], message["bullets"], message["body_markdown"])
    try:
        mail = portal.call("send_agent_message", {"channel_kind": "email", "recipient": email,
                                                  "body": text, "action": "initiate"})
        mail = mail if isinstance(mail, dict) else {"raw": mail}
    except c.PortalError as exc:
        mail = {"success": False, "decision": "failed", "reason": str(exc)}
    if sent(mail):
        return {"sent": True, "channel": "email", "id": mail.get("log_id"), "teams_reason": why(teams)}
    return {"sent": False, "channel": "email", "reason": f"teams {why(teams)}; email {why(mail)}"}


def main():
    parser = argparse.ArgumentParser(description="Post one message to the owner's own Teams chat through the "
                                                 "Portal, email as the fallback.")
    parser.add_argument("--title", required=True, help="the heading, one line")
    parser.add_argument("--bullet", dest="bullets", action="append", default=[], help="a short line, no links (repeatable)")
    parser.add_argument("--link", dest="links", action="append", default=[], help="a URL (repeatable)")
    parser.add_argument("--record-ref", default=None, help="portal://<type>/<id> for an Open in Portal button")
    parser.add_argument("--dry-run", action="store_true", help="print the rendered message and the call; send nothing")
    args = parser.parse_args()
    try:
        message = build_message(args.title, args.bullets, args.links, args.record_ref)
    except c.Failure as exc:
        print(f"notify-owner: {exc}", file=sys.stderr)
        sys.exit(2)
    mode = os.environ.get("NOTIFY_OWNER_MODE", "").strip().lower()
    if mode == "off":
        print(json.dumps({"sent": False, "channel": "teams",
                          "reason": "notifications are off (NOTIFY_OWNER_MODE=off)"}, indent=1))
        return
    dry_run, reason = args.dry_run, "dry run: nothing sent"
    if mode in ("dry-run", "dryrun", "rehearsal") and not dry_run:
        dry_run, reason = True, "rehearsal: nothing sent (NOTIFY_OWNER_MODE=dry-run)"
    if dry_run:
        print(json.dumps({"sent": False, "channel": "teams", "reason": reason, "dry_run": True,
                          "rendered": render(message["title"], message["bullets"], message["body_markdown"]),
                          "arguments": {"member_or_ref": OWN_MEMBER, **message}}, indent=1))
        return
    try:
        portal = c.client()
    except c.Failure as exc:
        print(c.safe(json.dumps({"sent": False, "channel": "teams", "reason": str(exc)}, indent=1)))
        sys.exit(1)
    result = send(portal, message)
    print(c.safe(json.dumps(result, indent=1)))
    sys.exit(0 if result["sent"] else 1)


if __name__ == "__main__":
    main()
