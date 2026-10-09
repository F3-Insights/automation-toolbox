#!/usr/bin/env python3
"""cos-watch: is anything new in the Portal worth a chief-of-staff cycle?

    cos_watch.py --since=CURSOR [--email-hours 18] [--meeting-hours 24]

The check a runtime's Monitor trigger runs on a cadence. It reads two cheap Portal views,
compares them with the cursor it was given, and prints one JSON object on stdout:

    {"items": [{"key": "overdue:<task id>", "summary": "Newly overdue: ..."}], "cursor": "c1...."}

Empty `items` means nothing to do. The script keeps no state: everything it needs to tell
what is new travels in the cursor, which the runtime saves only after it acts on the items
and passes back as `--since`. An empty `--since=` is the first run: it reports nothing and
returns the baseline cursor, so a fresh install never fires on what was already there.

What counts, in code, with no model:

- `overdue:<task id>`   a task newly overdue
- `due-today:<task id>` a task newly due today
- `vip-mail:<email id>` new VIP mail (the Portal's priority-1, unarchived), received within
  --email-hours
- `meeting:<event id>`  a meeting new to the calendar that starts within --meeting-hours
  (all-day entries are not meetings)

Not material, so never an item: routine or bulk mail, newsletters, notifications, recaps of
meetings that already happened, and a meeting already known that has simply come within 24
hours. Only additions count; something that went away is not a change.

The day's roll is not a change. On the first check of a new local day (the cursor is dated
an earlier day), tasks that became overdue or due today because the date moved are taken as
the new baseline, not reported: the morning cycle reads the day's tasks anyway. VIP mail and
new meetings are reported across the roll as usual.

Hours, the gap between cycles, the daily cap and quiet hours belong to the runtime, not here.

Reads (both read-only): `briefing` for today (tasks and VIP mail), and `briefing` for the
week (meetings, from now to seven days out; the week's ids are the meeting baseline, so a
meeting created days ahead is never reported when it comes near). Settings: the shared
`portal_mcp_config` and `portal_server`; the token in INSIGHTS_PORTAL_ASSISTANT_TOKEN or a
${VAR} in the MCP config.

Exit 0 with the JSON on stdout; exit 2 with one line on stderr when the Portal cannot be read
(or answers a section with an error) or the cursor is not one this script wrote.

Example:
    python3 cos_watch.py --since=
"""

import argparse
import base64
import binascii
import hashlib
import json
import re
import sys
from datetime import timedelta

import _common as c

CURSOR_PREFIX = "c1."
HASH_LEN = 8
SUMMARY_MAX = 160
KINDS = ("o", "t", "v", "m")  # overdue, due today, VIP mail, meetings in the week
_HASH = re.compile(rf"[0-9a-f]{{{HASH_LEN}}}")


# --------------------------------------------------------------------------- the cursor

def _h(value):
    return hashlib.sha256(str(value).encode()).hexdigest()[:HASH_LEN]


def encode_cursor(day, current):
    """`c1.` and the URL-safe base64 of {"d": day, "o": [...], "t": [...], "v": [...], "m": [...]},
    each list the sorted short hashes of that kind's ids. About 1 KB on a busy week."""
    body = {"d": day, **{k: sorted({_h(i) for i in current.get(k, ())}) for k in KINDS}}
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
    return CURSOR_PREFIX + base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(text):
    """(day, {kind: set of hashes}) from a cursor this script wrote; c.Bad for anything else."""
    if not text.startswith(CURSOR_PREFIX):
        raise c.Bad("bad cursor: not one cos_watch wrote (no c1. prefix)")
    data = text[len(CURSOR_PREFIX):]
    try:
        body = json.loads(base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode())
    except (binascii.Error, ValueError, UnicodeDecodeError):
        raise c.Bad("bad cursor: it does not decode") from None
    if not isinstance(body, dict) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(body.get("d") or "")):
        raise c.Bad("bad cursor: no date")
    current = {}
    for k in KINDS:
        values = body.get(k)
        if not isinstance(values, list) or not all(isinstance(v, str) and _HASH.fullmatch(v) for v in values):
            raise c.Bad(f"bad cursor: list {k!r} is missing or malformed")
        current[k] = set(values)
    return body["d"], current


# --------------------------------------------------------------------------- the Portal reads

def _rows(value, what):
    if not isinstance(value, list):
        raise c.Bad(f"portal briefing: {what} came back unreadable" + (
            f" ({c.flat(value.get('error'), 120)})" if isinstance(value, dict) and value.get("error") else ""))
    return [r for r in value if isinstance(r, dict) and r.get("id")]


def read_portal(client):
    """Today's tasks and VIP mail, the week's meetings, and the owner's local date. A section
    the Portal could not build fails the read: treated as empty, its ids would leave the
    cursor and come back later looking new."""
    today = client.call("briefing", {"scope": "today", "sections": ["tasks", "emails"]})
    if not isinstance(today, dict):
        raise c.Bad("portal briefing: no usable answer for today")
    tasks = today.get("tasks")
    if not isinstance(tasks, dict):
        raise c.Bad("portal briefing: no tasks section")
    for key in ("overdue_error", "due_in_window_error"):
        if tasks.get(key):
            raise c.Bad(f"portal briefing: {key.replace('_error', '')} failed ({c.flat(tasks[key], 120)})")
    emails = today.get("emails")
    if not isinstance(emails, dict) or emails.get("error"):
        raise c.Bad("portal briefing: the VIP mail section failed"
                    + (f" ({c.flat(emails.get('error'), 120)})" if isinstance(emails, dict) else ""))
    window = today.get("window") if isinstance(today.get("window"), dict) else {}
    day = str(window.get("label") or str(window.get("start_local") or "")[:10])
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise c.Bad("portal briefing: no local date in its window")
    week = client.call("briefing", {"scope": "week", "sections": ["meetings"]})
    if not isinstance(week, dict):
        raise c.Bad("portal briefing: no usable answer for the week")
    return {"day": day,
            "overdue": _rows(tasks.get("overdue", []), "overdue tasks"),
            "due_today": _rows(tasks.get("due_in_window", []), "tasks due today"),
            "vip": _rows(emails.get("vip_recent", []), "VIP mail"),
            "meetings": _rows(week.get("meetings", []), "meetings")}


# --------------------------------------------------------------------------- what is material

def _line(*parts):
    return c.flat(" ".join(p for p in parts if p), SUMMARY_MAX)


def watch(client, since, now=None, email_hours=18, meeting_hours=24):
    """The items that are new and material since the cursor, and the cursor to save."""
    now = now or c.now_utc()
    prior = decode_cursor(since) if since else None
    read = read_portal(client)
    current = {"o": [r["id"] for r in read["overdue"]], "t": [r["id"] for r in read["due_today"]],
           "v": [r["id"] for r in read["vip"]], "m": [r["id"] for r in read["meetings"]]}
    cursor = encode_cursor(read["day"], current)
    if prior is None:
        return {"items": [], "cursor": cursor}
    prior_day, seen = prior
    new_day = prior_day != read["day"]

    def new(kind, row):
        return _h(row["id"]) not in seen[kind]

    items = []
    if not new_day:
        items += [{"key": f"overdue:{r['id']}", "summary": _line("Newly overdue:", str(r.get("title") or "(untitled)"))}
                  for r in read["overdue"] if new("o", r)]
        items += [{"key": f"due-today:{r['id']}", "summary": _line("Due today:", str(r.get("title") or "(untitled)"))}
                  for r in read["due_today"] if new("t", r)]
    cutoff = now - timedelta(hours=email_hours)
    for r in read["vip"]:
        got = c.parse_time(r.get("received_at"))
        if new("v", r) and (got is None or got >= cutoff):
            sender = str(r.get("from_name") or r.get("from_address") or "").strip()
            items.append({"key": f"vip-mail:{r['id']}",
                          "summary": _line("VIP mail" + (f" from {sender}:" if sender else ":"),
                                           str(r.get("subject") or "(no subject)"))})
    until = now + timedelta(hours=meeting_hours)
    for r in read["meetings"]:
        start = c.parse_time(r.get("start_time"))
        if r.get("is_all_day") or start is None or not (now <= start <= until) or not new("m", r):
            continue
        at = str(r.get("start_local") or "")[11:16] or start.strftime("%H:%MZ")
        items.append({"key": f"meeting:{r['id']}",
                      "summary": _line(f"New meeting at {at}:", str(r.get("title") or "(untitled)"))})
    return {"items": items, "cursor": cursor}


def main(argv=None):
    p = argparse.ArgumentParser(description="The chief of staff's Monitor check. One JSON object out.")
    p.add_argument("--since", default="", help="The cursor from the last check; empty the first time")
    p.add_argument("--email-hours", type=int, default=18, help="VIP mail older than this is not new (default 18)")
    p.add_argument("--meeting-hours", type=int, default=24,
                   help="A new meeting counts when it starts within this many hours (default 24)")
    args = p.parse_args(argv)
    try:
        if args.email_hours < 1 or args.meeting_hours < 1:
            raise c.Bad("--email-hours and --meeting-hours must be at least 1")
        since = args.since.strip()
        if since:
            decode_cursor(since)  # a bad cursor fails before the Portal is reached
        out = watch(c.Portal(), since, email_hours=args.email_hours,
                    meeting_hours=args.meeting_hours)
    except c.Bad as exc:
        print(c.safe(f"cos_watch: {c.flat(str(exc), 300)}"), file=sys.stderr)
        sys.exit(c.ERROR)
    print(c.safe(json.dumps(out, ensure_ascii=False, separators=(",", ":"))))
    sys.exit(c.OK)


if __name__ == "__main__":
    main()
