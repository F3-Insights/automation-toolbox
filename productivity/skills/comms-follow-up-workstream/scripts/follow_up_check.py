#!/usr/bin/env python3
"""follow-up-check: is there anything for the follow-up pass to chase today?

The code precheck of the follow-up Automation, so a quiet morning costs no session. Read only
toward the Portal; writes nothing but --out. It counts four kinds of work, the same four the
waiting-on tracker's lenses look for, in the owner's own timezone (from whoami):

- waiting: an open WAITING task whose follow-up date (its due date) is today or earlier;
- delegated: an open task someone else holds (owner_contact_id set and not the owner, not
  WAITING) that is overdue or has not moved inside --stale-days (default 7);
- silent: a thread in the last --window-days (14) where the owner wrote last, to someone other
  than himself, more than --silence-days (3) business days ago;
- promises: an open task of the owner's captured from a promise (its description holds
  `Captured from: promise:`, as task-stack-apply writes a lens D create) due within
  --promise-days (2), overdue included.

--precheck prints one line, `WORK: <counts>` or `NOTHING: <why>`, and exits 0; a Portal that
cannot be read prints the reason on stderr and exits 2, so the scheduler records a failed
check rather than a quiet day. Without --precheck it prints the JSON (counts and the refs of
each item, at most 20 a kind) and exits 0, 2 on an error. --out also writes the JSON.

Example:
    python3 follow_up_check.py --precheck
    python3 follow_up_check.py --out RUN/follow-up-check.json
"""

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone

import _common as c

STALE_DAYS, SILENCE_DAYS, PROMISE_DAYS, WINDOW_DAYS, SHOWN = 7, 3, 2, 14, 20
CLOSED = {"done", "cancelled", "canceled", "completed", "archived"}
PROMISE_MARK = "captured from: promise:"


def status_of(task):
    return str(task.get("status") or "").strip().upper()


def is_open(task):
    return status_of(task).lower() not in CLOSED and not task.get("is_archived") and not task.get("deleted_at")


def due_of(task, tz):
    for key in ("due_date", "deadline"):
        day = c.local_day(task.get(key), tz)
        if day:
            return day
    return None


def thread_key(mail):
    for key in ("thread_id", "conversation_id", "thread"):
        if str(mail.get(key) or "").strip():
            return str(mail[key]).strip()
    return None


def recipients(mail):
    out = []
    for key in ("to_addresses", "cc_addresses"):
        values = mail.get(key) or []
        if isinstance(values, str):
            values = values.replace(";", ",").split(",")
        for value in values:
            address = c.bare_address(value.get("address") or value.get("email") if isinstance(value, dict) else value)
            if address and address not in out:
                out.append(address)
    return out


def ref(kind, row):
    return row.get("_ref") or f"portal://{kind}/{row.get('id')}"


def check(portal, as_of=None, stale_days=STALE_DAYS, silence_days=SILENCE_DAYS, promise_days=PROMISE_DAYS,
          window_days=WINDOW_DAYS):
    me = c.owner(portal)
    tz, mine = me["tz"], set(me["addresses"])
    owner_id = me["contact_id"]
    now = datetime.now(timezone.utc)
    today = as_of or now.astimezone(tz).date()
    found = {"waiting": [], "delegated": [], "silent": [], "promises": []}

    for task in c.list_all(portal, "task"):
        if not is_open(task):
            continue
        status, due = status_of(task), due_of(task, tz)
        holder = str(task.get("owner_contact_id") or "").lower()
        if status == "WAITING":
            if due and due <= today:
                found["waiting"].append({"ref": ref("task", task), "title": task.get("title"), "follow_up": str(due)})
            continue
        if holder and owner_id and holder != owner_id:
            moved = c.local_day(task.get("updated_at"), tz) or c.local_day(task.get("created_at"), tz)
            stale = moved is not None and (today - moved).days > stale_days
            if (due and due < today) or stale:
                found["delegated"].append({"ref": ref("task", task), "title": task.get("title"),
                                           "due": str(due or "") or None, "last_moved": str(moved or "") or None})
            continue
        if PROMISE_MARK in str(task.get("description") or "").lower() and due \
                and due <= today + timedelta(days=promise_days):
            found["promises"].append({"ref": ref("task", task), "title": task.get("title"), "due": str(due)})

    since = c.iso_z(datetime.combine(today - timedelta(days=window_days), datetime.min.time(), tz))
    threads, unthreaded = {}, 0
    for direction in ("sent", "received"):
        for mail in c.list_all(portal, "email", {"direction": direction, "since": since}):
            key = thread_key(mail)
            when = c.parse_time(mail.get("received_at") or mail.get("sent_at"))
            if not key or not when:
                unthreaded += direction == "sent"
                continue
            last = threads.get(key)
            if last is None or when > last[0]:
                threads[key] = (when, direction, mail)
    for when, direction, mail in threads.values():
        if direction != "sent":
            continue
        others = [a for a in recipients(mail) if a not in mine]
        if not others:
            continue
        quiet = c.business_days_between(when.astimezone(tz).date(), today)
        if quiet > silence_days:
            found["silent"].append({"ref": ref("email", mail), "subject": mail.get("subject"), "to": others[:3],
                                    "sent": c.iso_z(when), "business_days": quiet})

    counts = {k: len(v) for k, v in found.items()}
    return {"tool": "follow-up-check", "as_of": str(today), "timezone": me["timezone"],
            "windows": {"stale_days": stale_days, "silence_days": silence_days, "promise_days": promise_days,
                        "window_days": window_days},
            "counts": counts, "work": any(counts.values()), "unthreaded_sent": unthreaded,
            "items": {k: v[:SHOWN] for k, v in found.items()}}


def line(result):
    n = result["counts"]
    if not result["work"]:
        return (f"NOTHING: no follow-up due, no stale delegated task, no thread silent past "
                f"{result['windows']['silence_days']} business days, no promise due within "
                f"{result['windows']['promise_days']} days ({result['as_of']})")
    parts = [f"{n['waiting']} WAITING follow-ups due", f"{n['delegated']} delegated tasks stale or overdue",
             f"{n['silent']} silent threads", f"{n['promises']} promises due"]
    return "WORK: " + "; ".join(parts)


def main(argv=None, portal=None):
    p = argparse.ArgumentParser(prog="follow_up_check.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--precheck", action="store_true", help="one line, WORK: or NOTHING:, for a scheduler")
    p.add_argument("--out", default="", help="also write the JSON to this file")
    p.add_argument("--as-of", default="", help="judge as of this date (yyyy-mm-dd); blank: today in the owner's zone")
    p.add_argument("--stale-days", type=int, default=STALE_DAYS, help=f"delegated staleness, days (default {STALE_DAYS})")
    p.add_argument("--silence-days", type=int, default=SILENCE_DAYS,
                   help=f"silence window, business days (default {SILENCE_DAYS})")
    p.add_argument("--promise-days", type=int, default=PROMISE_DAYS,
                   help=f"a promise due within this many days is work (default {PROMISE_DAYS})")
    p.add_argument("--window-days", type=int, default=WINDOW_DAYS, help=f"sent mail looked at, days (default {WINDOW_DAYS})")
    p.add_argument("--config", default="", help="the MCP config holding the Portal (default: the setting)")
    a = p.parse_args(argv)
    try:
        for name in ("stale_days", "silence_days", "promise_days", "window_days"):
            if not 0 <= getattr(a, name) <= 365:
                raise c.Failure(f"--{name.replace('_', '-')} is 0 to 365")
        as_of = date.fromisoformat(a.as_of.strip()) if a.as_of.strip() else None
        result = check(portal or c.client(a.config or None), as_of, a.stale_days, a.silence_days, a.promise_days,
                       a.window_days)
        if a.out:
            out = c.guard_run_path(a.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, indent=1, default=str) + "\n", encoding="utf-8")
    except Exception as exc:  # a check that could not run is never a quiet day
        reason = str(exc) if isinstance(exc, (c.Failure, ValueError)) else f"{type(exc).__name__}: {exc}"
        if a.precheck:
            print(c.safe(f"follow-up-check: {reason}"), file=sys.stderr)
            sys.exit(c.ERROR)
        c.fail(reason)
    if a.precheck:
        print(c.safe(line(result)))
        sys.exit(c.OK)
    c.emit(result, c.OK)


if __name__ == "__main__":
    main()
