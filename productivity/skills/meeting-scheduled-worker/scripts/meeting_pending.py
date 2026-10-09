"""meeting-pending: the stored Fellow recordings still to process, oldest first.

Step 1 of the meeting-scheduled-worker skill. Reads the Portal and the local ledger; writes
nothing.

A recording is pending when it is matched to a calendar event, came through the owner's own
Fellow connection (not a principal's, `via_delegation`), and the Portal has not acknowledged
its current transcript. The ledger then keeps a recording from taking a slot it cannot use:
`skipped_known` (marked permanent for this revision), `parked` (tried --max-attempts times),
`waiting` (its admin task waits on the owner, until they comment or move it off WAITING) and
`deferred` (the last attempt failed less than --backoff-hours ago). What is left, oldest
first, is cut to --limit. Recordings with no calendar event are listed apart as `unmatched`.

Inputs: --since (else the setting [meeting-scheduled-worker] since), --limit, --state.
Prints one JSON object. Exit 0 with status `ok` or `nothing`; 3 `not_local_owner` (the
Portal hands processing elsewhere); 2 could not run. --precheck prints only `NOTHING` or
`WORK: <n> recordings to process` and exits 0.

Example:
    python3 meeting_pending.py --limit 5
"""

from __future__ import annotations

import argparse
import sys

import _common as c

PAGE, MAX_PAGES = 50, 200
STATUSES = ("ok", "nothing", "not_local_owner")


def all_meetings(portal, since: str) -> dict:
    rows, offset, seen = [], 0, set()
    owner = runs = None
    for _ in range(MAX_PAGES):
        page = portal.call("list_fellow_meetings", {"since": since, "offset": offset, "limit": PAGE})
        if not isinstance(page, dict) or not isinstance(page.get("meetings"), list):
            raise c.Stop("list_fellow_meetings returned nothing usable")
        if owner is None:
            owner, runs = page.get("owner"), page.get("active_cloud_runs")
        rows.extend(m for m in page["meetings"] if isinstance(m, dict))
        nxt = page.get("next_offset")
        if nxt is None:
            return {"owner": owner, "active_cloud_runs": runs, "meetings": rows}
        if not isinstance(nxt, int) or nxt <= offset or nxt in seen:
            raise c.Stop("list_fellow_meetings paging did not advance")
        seen.add(nxt)
        offset = nxt
    raise c.Stop(f"list_fellow_meetings still had pages after {MAX_PAGES}")


def line(m: dict, entry=None) -> dict:
    out = {"recording_id": m.get("id"), "digest": m.get("transcript_hash"),
           "calendar_event_id": m.get("calendar_event_id"), "note_id": m.get("note_id"),
           "started_at": m.get("started_at"), "match_method": m.get("match_method")}
    if entry:
        out["attempts"] = entry.get("attempts", 0)
        if entry.get("last_reason"):
            out["last_reason"] = entry["last_reason"]
    return out


def waiting_status(portal, task_id: str, email) -> tuple:
    """The admin task's status, and whether the owner has answered on it since its questions."""
    try:
        env = c.get_full(portal, "task", task_id)
    except c.Stop:
        return "UNREADABLE", False
    status = c.status_of(c.record(env, "task"))
    return status, bool(status == "WAITING" and c.answers(env, email())["answered"])


def pending(portal, root, since: str, limit: int = 5, max_attempts: int = c.MAX_ATTEMPTS,
            backoff_hours: float = c.BACKOFF_HOURS, now=None) -> dict:
    now = now or c.now_utc()
    got = all_meetings(portal, since)
    base = {"since": since, "owner": got["owner"], "active_cloud_runs": got["active_cloud_runs"], "state": str(root)}
    if got["owner"] != "local" or got["active_cloud_runs"] != 0:
        return {**base, "status": "not_local_owner", "recordings": [],
                "reason": f"the Portal hands Fellow processing to {got['owner']!r} with {got['active_cloud_runs']} "
                          "active cloud runs; local processing needs owner local and none active"}
    ledger = c.load_ledger(root)
    cached = []

    def email():  # whoami only when a waiting task needs it
        if not cached:
            cached.append(c.owner_email(portal))
        return cached[0]

    # A recording seen only through a delegation is the principal's, processed by their own worker.
    open_rows = [m for m in got["meetings"] if m.get("transcript_hash") and not m.get("via_delegation")
                 and m.get("processed_hash") != m.get("transcript_hash")]
    unmatched = [line(m) for m in open_rows if not m.get("calendar_event_id")]
    lists = {"skipped_known": [], "parked": [], "waiting": [], "deferred": []}
    eligible = []
    for m in open_rows:
        if not m.get("calendar_event_id"):
            continue
        entry = ledger.get(c.ledger_key(str(m.get("id")), str(m.get("transcript_hash"))))
        if not entry:
            eligible.append(line(m))
        elif entry.get("permanent"):
            lists["skipped_known"].append(line(m, entry))
        elif entry.get("waiting_task_id"):
            status, answered = waiting_status(portal, entry["waiting_task_id"], email)
            if status == "WAITING" and not answered:
                lists["waiting"].append({**line(m, entry), "admin_task_id": entry["waiting_task_id"]})
            else:
                eligible.append({**line(m, entry), "admin_task_status": status, "answered": answered})
        elif int(entry.get("attempts") or 0) >= max_attempts:
            lists["parked"].append(line(m, entry))
        else:
            until = c.deferred_until(entry, backoff_hours)
            if until and until > now:
                lists["deferred"].append({**line(m, entry), "until": until.isoformat()})
            else:
                eligible.append(line(m, entry))
    eligible.sort(key=lambda r: str(r.get("started_at") or ""))
    picked = eligible[:max(0, limit)]
    counts = {"open": len(open_rows), "eligible": len(eligible), "picked": len(picked),
              "unmatched": len(unmatched), **{k: len(v) for k, v in lists.items()}}
    return {**base, "status": "ok" if picked else "nothing", "limit": limit, "counts": counts,
            "recordings": picked, "remaining_after_this_run": len(eligible) - len(picked),
            "unmatched": unmatched, **lists}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="meeting-pending", description=__doc__.split("\n\n")[0])
    p.add_argument("--since", help="earliest meeting start, ISO time (default: the setting since)")
    p.add_argument("--limit", type=int, default=5, help="recordings this run takes (default 5)")
    p.add_argument("--max-attempts", type=int, default=c.MAX_ATTEMPTS)
    p.add_argument("--backoff-hours", type=float, default=c.BACKOFF_HOURS)
    p.add_argument("--state", help="state folder")
    p.add_argument("--precheck", action="store_true", help="print NOTHING or WORK: <reason> and exit")
    a = p.parse_args(argv)
    try:
        since = a.since or c.settings(c.SKILL).get("since")
        if not since:
            raise c.Stop(f"no cut-off: pass --since or set [{c.SKILL}] since (an ISO time such as 2026-01-01T00:00:00Z)")
        result = pending(c.client(), c.state_root(a.state), str(since), a.limit, a.max_attempts, a.backoff_hours)
    except Exception as exc:
        if a.precheck:
            print(c.safe(f"meeting-pending: {c.reason_of(exc, 'meeting-pending')}"), file=sys.stderr)
            return c.ERROR
        return c.fail(c.reason_of(exc, "meeting-pending"))
    if a.precheck:
        print(f"WORK: {result['counts']['eligible']} recordings to process" if result["status"] == "ok" else "NOTHING")
        return c.OK
    return c.emit(result, c.STOP if result["status"] == "not_local_owner" else c.OK)


if __name__ == "__main__":
    sys.exit(main())
