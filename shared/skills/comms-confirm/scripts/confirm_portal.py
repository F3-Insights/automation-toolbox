#!/usr/bin/env python3
"""confirm-portal: the Portal half of comms-confirm. JSON in on stdin, JSON out.

confirm.py beside this file runs it. Three subcommands, each reading one JSON object on stdin:

    task     find or create the request's Portal task, by its marker
    look     for open requests: the task's status and comments, and email replies
    finish   when a request is closed: comment on its task and set it DONE or CANCELLED

`task` input: {id, question, asked_of, person, contact_id, relayed, due, context, fallback,
domain, project_id, dry_run}. The task carries the marker line `confirmation-request:<id>` as
the last line of its description and as `source_reference`. Tasks in every status whose text
holds the id are read first and one carrying the marker is reused, so a re-run never makes a
second task. Every task sits on the owner's own list (owner: the token's own contact) and is
never assigned to anyone else. With a `contact_id` it is WAITING on that person; without one
(a question to the owner) it stays TODO. Every create is read back.

`look` input: {requests: [{id, task, asked_at, contact_id, subject, thread, seen}]}. A task
DONE is an answer (`task_done`), CANCELLED a withdrawal (`task_cancelled`), and a comment
newer than `asked_at` written by a person, not an agent, is an answer (`comment`). Received
mail from the contact newer than `asked_at`, on the request's thread or with its subject less
Re:/Fwd:, is an answer (`email_reply`). Evidence listed in `seen` is skipped. Read only.

`finish` input: {task_id, status, comment, id}. A task already DONE or CANCELLED is left as
it is; otherwise one comment, then the status, read back.

Nothing here sends anything or touches a draft. Prints one JSON object. Exit 0, or 2 on an
error (`{"status": "error", "reason": ...}`).

Example:
    echo '{"requests": []}' | python3 confirm_portal.py look
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone

import _common as c

TITLE_MAX = 200
MARKER_PREFIX = "confirmation-request:"
ID_RE = re.compile(r"^CR-[0-9a-f]{10}$")
UUID_RE = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
REPLY_PREFIX = re.compile(r"^\s*(?:(?:re|fw|fwd|aw|sv)\s*:\s*)+", re.I)
AGENT_LINE = re.compile(r"\(posted by .+?, an agent\)\s*\Z", re.S)
ALL_STATUSES = ["TODO", "IN_PROGRESS", "WAITING", "DONE", "CANCELLED"]
EMAIL_ROWS = 50
ANSWER_CHARS = 1000


def marker(rid):
    return f"{MARKER_PREFIX}{rid}"


def parse_time(value):
    if not value:
        return None
    try:
        out = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return out if out.tzinfo else out.astimezone()


def bare_subject(text):
    return " ".join(REPLY_PREFIX.sub("", str(text or "")).split()).casefold()


def uuid_in(value):
    m = UUID_RE.search(str(value or ""))
    return m.group(0) if m else None


def bare_id(value):
    return str(value or "").strip().rstrip("/").rsplit("/", 1)[-1]


def is_owner(role):
    out = " ".join(str(role or "").split()).casefold()
    return (out[4:] if out.startswith("the ") else out) == "owner"


# --------------------------------------------------------------------------- task

def title_for(req):
    who = str(req.get("person") or req.get("asked_of") or "").split("<")[0].strip()
    if is_owner(req.get("asked_of")) and not req.get("person"):
        who = ""
    base = str(req.get("question") or "").strip()
    title = f"Confirm with {who}: {base}" if who else f"Confirm: {base}"
    return title if len(title) <= TITLE_MAX else title[: TITLE_MAX - 3].rstrip() + "..."


def description_for(req):
    lines = [f"Question: {req.get('question')}", f"Asked of: {req.get('person') or req.get('asked_of')}"]
    if req.get("context"):
        lines.append(f"Context: {req['context']}")
    if req.get("due"):
        lines.append(f"Answer wanted by: {req['due']}")
    if req.get("fallback"):
        lines.append(f"If no answer by then: {req['fallback']}")
    who = str(req.get("person") or req.get("asked_of") or "the person").split("<")[0].strip()
    how = (f"Please put this question to {who}, then comment their answer on this task, or mark it done with "
           "the answer in a comment." if req.get("relayed") else
           "Answer by commenting on this task, or mark it done with the answer in a comment.")
    return "\n".join(lines + ["", how, marker(str(req["id"]))])


def find_task(portal, rid):
    """The task carrying this request's marker, in any status. The task search does not match
    `source_reference`, so it searches on the id and keeps the one whose description holds the marker."""
    rows, offset = {}, 0
    for _ in range(5):
        out = portal.call("list_entities", {"entity_type": "task", "limit": 50, "offset": offset,
                                            "filters": {"search": rid, "status": ALL_STATUSES}})
        if not isinstance(out, dict) or out.get("error"):
            raise c.Failure(f"the task lookup failed: {out.get('error') if isinstance(out, dict) else 'no answer'}")
        for row in out.get("items") or []:
            if isinstance(row, dict) and row.get("id"):
                rows.setdefault(str(row["id"]), row)
        if not out.get("has_more"):
            break
        offset = int(out.get("next_offset") or offset + 50)
    mark = marker(rid)
    hits = [t for t in rows.values() if str(t.get("source_reference") or "") == mark
            or mark in str(t.get("description") or "").splitlines()]
    return sorted(hits, key=lambda t: str(t.get("created_at") or ""))[0] if hits else None


def owner_contact(portal):
    who = portal.call("whoami")
    contact = ((who or {}).get("principal") or {}).get("contact_id") if isinstance(who, dict) else None
    if not uuid_in(contact):
        raise c.Failure("whoami named no contact for the owner; tasks are never created ownerless")
    return str(contact)


def ensure_task(portal, req):
    rid = str(req.get("id") or "")
    if not ID_RE.match(rid) or not str(req.get("question") or "").strip():
        raise c.Failure("task needs the request id (CR-...) and its question")
    contact = uuid_in(req.get("contact_id"))
    have = find_task(portal, rid)
    if have:
        return {"outcome": "found", "task_id": have["id"], "ref": f"portal://task/{have['id']}",
                "status": have.get("status")}
    args = {"title": title_for(req), "description": description_for(req), "source_reference": marker(rid),
            "owner_contact_id": owner_contact(portal), "due_date": req.get("due") or None, "priority": 2,
            "domain_id_or_name": req.get("domain") or None, "project_id": uuid_in(req.get("project_id"))}
    if contact:
        args.update(task_contact_id=contact, waiting_on_contact_id=contact,
                    waiting_reason="confirmation relayed through the owner" if req.get("relayed")
                    else "confirmation requested")
    args = {k: v for k, v in args.items() if v not in (None, "", [])}
    if req.get("dry_run"):
        return {"outcome": "would_create", "args": args, "then_status": "WAITING" if contact else None}
    try:
        created = portal.call("create_task", args)
        tid = uuid_in(created.get("id") or (created.get("task") or {}).get("id")) if isinstance(created, dict) else None
    except Exception as exc:  # a create that may have landed is reconciled by its marker
        tid, created = None, {"error": f"{type(exc).__name__}: {exc}"}
    if not tid:
        again = find_task(portal, rid)
        if not again:
            raise c.Failure(f"create_task made no task: {c.safe(str(created))[:200]}")
        tid = again["id"]
    if contact:
        portal.call("update_task", {"id": tid, "status": "WAITING"})
    back = portal.call("get", {"entity_type": "task", "id_or_query": tid})
    record = back.get("task", back) if isinstance(back, dict) else {}
    if str(record.get("id") or "") != tid or marker(rid) not in str(record.get("description") or ""):
        raise c.Failure(f"task {tid} was created but did not read back with its marker")
    return {"outcome": "created", "task_id": tid, "ref": f"portal://task/{tid}", "status": record.get("status")}


# --------------------------------------------------------------------------- look

def task_findings(portal, req, asked):
    tid = uuid_in(req.get("task"))
    if not tid:
        return []
    env = portal.call("get", {"entity_type": "task", "id_or_query": tid, "detail": "full"})
    if not isinstance(env, dict) or env.get("error"):
        raise c.Failure(f"task {tid} could not be read")
    record = env.get("task") if isinstance(env.get("task"), dict) else env
    status = str(record.get("status") or "").upper()
    ref = f"portal://task/{tid}"
    out = []
    people = [x for x in env.get("comments") or [] if isinstance(x, dict) and str(x.get("body") or "").strip()
              and not AGENT_LINE.search(str(x.get("body") or ""))]
    newer = [x for x in people if asked is None or (parse_time(x.get("created_at")) or asked) > asked]
    if newer:
        last = newer[-1]
        out.append({"kind": "comment", "by": last.get("author_name") or last.get("author_email") or "",
                    "text": "\n".join(str(x.get("body")).strip() for x in newer)[:ANSWER_CHARS],
                    "evidence": f"{ref} comment {last.get('created_at')}", "at": last.get("created_at")})
    if status == "DONE":
        out.append({"kind": "task_done", "by": record.get("owner_name") or "",
                    "text": "the Portal task was marked done" + (" (see its comments)" if newer else ""),
                    "evidence": f"{ref} DONE", "at": record.get("completed_at") or record.get("updated_at")})
    elif status == "CANCELLED":
        out.append({"kind": "task_cancelled", "by": "", "text": "", "evidence": f"{ref} CANCELLED",
                    "at": record.get("updated_at")})
    return out


def email_findings(portal, req, asked):
    contact = uuid_in(req.get("contact_id"))
    subject, thread = bare_subject(req.get("subject")), bare_id(req.get("thread"))
    if not contact or not (subject or thread):
        return []
    rows = portal.call("list_entities", {"entity_type": "email", "limit": EMAIL_ROWS,
                                         "filters": {"contact_id": contact, "direction": "received"}})
    if not isinstance(rows, dict) or rows.get("error"):
        raise c.Failure("the email listing failed")
    out = []
    for row in rows.get("items") or []:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        when = parse_time(row.get("received_at"))
        if asked is not None and (when is None or when <= asked):
            continue
        same_thread = bool(thread) and thread in {bare_id(row.get("thread_id")), bare_id(row.get("id"))}
        if same_thread or (bool(subject) and bare_subject(row.get("subject")) == subject):
            sender = row.get("from_name") or str(row.get("from_address") or "").strip().lower()
            out.append({"kind": "email_reply", "by": sender,
                        "text": f"replied by email: {str(row.get('snippet') or row.get('subject') or '')[:300]}",
                        "evidence": f"portal://email/{bare_id(row['id'])}", "at": row.get("received_at")})
    return sorted(out, key=lambda f: str(f.get("at") or ""))


def look(portal, data):
    findings, problems = [], []
    for req in data.get("requests") or []:
        if not isinstance(req, dict) or not ID_RE.match(str(req.get("id") or "")):
            problems.append({"id": None, "reason": "a request without a CR- id was skipped"})
            continue
        asked = parse_time(req.get("asked_at"))
        seen = {str(s).strip() for s in req.get("seen") or []}
        try:
            got = task_findings(portal, req, asked) + email_findings(portal, req, asked)
        except c.Failure as exc:
            problems.append({"id": req["id"], "reason": str(exc)})
            continue
        got = [g for g in got if g["evidence"] not in seen]
        if not got:
            continue
        # One finding per request: a cancellation wins, then a person's own words over a bare
        # status change, the newest first.
        cancelled = [g for g in got if g["kind"] == "task_cancelled"]
        words = [g for g in got if g["kind"] in ("comment", "email_reply")]
        pick = cancelled[0] if cancelled else (words[-1] if words else got[0])
        findings.append(dict(pick, id=req["id"]))
    return {"status": "ok", "findings": findings, "problems": problems,
            "looked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


# --------------------------------------------------------------------------- finish

def finish(portal, data):
    tid, status = uuid_in(data.get("task_id")), str(data.get("status") or "").upper()
    if not tid or status not in ("DONE", "CANCELLED"):
        raise c.Failure("finish needs a task_id and a status of DONE or CANCELLED")
    env = portal.call("get", {"entity_type": "task", "id_or_query": tid})
    record = env.get("task", env) if isinstance(env, dict) else {}
    if str(record.get("id") or "") != tid:
        raise c.Failure(f"task {tid} could not be read")
    if data.get("id") and marker(str(data["id"])) not in str(record.get("description") or ""):
        raise c.Failure(f"task {tid} does not carry {marker(str(data['id']))}; it is not this request's task")
    now = str(record.get("status") or "").upper()
    if now in ("DONE", "CANCELLED"):
        return {"status": "ok", "outcome": f"already {now}", "task_id": tid}
    if str(data.get("comment") or "").strip():
        portal.call("create_task_comment", {"task_id": tid, "body": str(data["comment"])[:4000]})
    portal.call("update_task", {"id": tid, "status": status})
    back = portal.call("get", {"entity_type": "task", "id_or_query": tid})
    got = str((back.get("task", back) if isinstance(back, dict) else {}).get("status") or "").upper()
    if got != status:
        raise c.Failure(f"task {tid} reads back {got or 'unknown'}, not {status}")
    return {"status": "ok", "outcome": status, "task_id": tid}


def run(name, portal, data):
    return {"task": ensure_task, "look": look, "finish": finish}[name](portal, data)


def main():
    parser = argparse.ArgumentParser(description="Find or create a confirmation task, look for answers, or "
                                                 "finish a task. One JSON object on stdin.")
    parser.add_argument("subcommand", choices=["task", "look", "finish"])
    args = parser.parse_args()
    try:
        try:
            data = json.loads(sys.stdin.read() or "{}")
        except ValueError:
            raise c.Failure("stdin is not JSON") from None
        if not isinstance(data, dict):
            raise c.Failure("stdin is not a JSON object")
        result = run(args.subcommand, c.client(), data)
    except Exception as exc:
        reason = str(exc) if isinstance(exc, c.Failure) else \
            f"confirm-portal {args.subcommand} could not complete: {type(exc).__name__}: {exc}"
        print(c.safe(json.dumps({"status": "error", "reason": reason}, indent=1)))
        sys.exit(2)
    print(c.safe(json.dumps(result, indent=1, default=str)))


if __name__ == "__main__":
    main()
