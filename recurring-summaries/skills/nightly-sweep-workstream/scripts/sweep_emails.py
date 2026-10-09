"""sweep-emails: every email of one local day, inbound and sent, into the date's folder.

Read only toward the Portal. For one date it writes one file; with --run it writes
RUN/<date>/emails.json for every date in RUN/dates.json, so the Automation's prepare step is
one command.

The window is the date's local day (sweep_dates prints it; given only the date, this computes
it the same way). The listing passes `since` and `until`, and the rows are filtered again on
`received_at`, since inclusive and until exclusive, so a message is in exactly one day. Every
page is read.

Archived mail is never filtered out: many people archive mail as they read it, so an archived
email is one the owner has seen, not one with nothing to do. Each row keeps `is_archived` so the
counts show how much archived mail was read.

Mail from the owner's executive assistant (--assistant, default the setting
[nightly-sweep-workstream] assistant_email) is flagged `from_assistant` and listed first: it is
never noise. The Portal's own generated Brief (--portal-brief, default portal_brief_email) is
flagged `portal_brief`; its items already exist in the Portal. Without a setting, nothing is
flagged.

Prints one JSON object (a summary; the rows are in the file). Exit 0 (`ok`, or `empty` for a day
with no mail), 3 when one date of a --run failed (the others are written), 2 on an error.

Examples:
    python3 sweep_emails.py 2030-03-06 --out RUN/2030-03-06/emails.json
    python3 sweep_emails.py --run RUN
"""

import argparse
import re
from pathlib import Path

import _common as c

PAGE = 200
FIELDS = ("id", "subject", "from_address", "from_name", "to_addresses", "cc_addresses", "received_at",
          "received_local", "is_archived", "contact_id", "recipient_contact_ids", "priority", "summary")
_ADDRESS = re.compile(r"[^\s<>,;\"']+@[^\s<>,;\"']+")


def bare_address(text):
    found = _ADDRESS.search(str(text or ""))
    return found.group(0).strip(".<>").lower() if found else ""


def list_window(client, window, direction, max_pages=c.MAX_EMAIL_PAGES):
    """Every email of one direction in the window. The filter never carries is_archived."""
    filters = {"since": window["since"], "until": window["until"], "direction": direction}
    rows, offset, pages, overflow, outside, total = {}, 0, 0, False, 0, None
    while True:
        out = client.call("list_entities", {"entity_type": "email", "filters": dict(filters),
                                            "limit": PAGE, "offset": offset})
        if not isinstance(out, dict) or out.get("error"):
            reason = out.get("error") if isinstance(out, dict) else "no answer"
            raise c.Stop(f"the {direction} email listing failed: {reason}")
        pages += 1
        total = out.get("total", total)
        for row in out.get("items") or []:
            if not isinstance(row, dict) or not row.get("id"):
                continue
            if not c.in_window(row.get("received_at"), window):
                outside += 1
                continue
            rows.setdefault(str(row["id"]), {k: row.get(k) for k in FIELDS if k in row})
        if not out.get("has_more"):
            break
        if pages >= max_pages:
            overflow = True
            break
        nxt = out.get("next_offset")
        if not isinstance(nxt, int) or nxt <= offset:
            break  # a server that stops paginating cannot spin this loop
        offset = nxt
    return {"rows": list(rows.values()), "pages": pages, "overflow": overflow, "outside_window": outside,
            "total": total}


def collect(client, day, window, assistant=None, portal_brief=None, max_pages=c.MAX_EMAIL_PAGES):
    assistant = (c.address_setting("assistant_email") if assistant is None else assistant).strip().lower()
    portal_brief = (c.address_setting("portal_brief_email") if portal_brief is None else portal_brief).strip().lower()
    inbound = list_window(client, window, "received", max_pages)
    sent = list_window(client, window, "sent", max_pages)
    for row in inbound["rows"]:
        sender = bare_address(row.get("from_address"))
        row["_ref"] = c.email_ref(row.get("id"))
        row["from_assistant"] = bool(assistant) and sender == assistant
        row["portal_brief"] = bool(portal_brief) and sender == portal_brief
    for row in sent["rows"]:
        row["_ref"] = c.email_ref(row.get("id"))
    # The assistant's mail first, then the day in order of arrival.
    inbound["rows"].sort(key=lambda r: (not r["from_assistant"], str(r.get("received_at") or "")))
    sent["rows"].sort(key=lambda r: str(r.get("received_at") or ""))
    errors = [f"the {name} listing stopped after {part['pages']} pages; more mail exists in the window"
              for name, part in (("inbound", inbound), ("sent", sent)) if part["overflow"]]
    return {
        "date": day, "window": window,
        "counts": {"inbound": len(inbound["rows"]), "sent": len(sent["rows"]),
                   "archived": sum(1 for r in inbound["rows"] if r.get("is_archived")),
                   "from_assistant": sum(1 for r in inbound["rows"] if r["from_assistant"]),
                   "portal_brief": sum(1 for r in inbound["rows"] if r["portal_brief"]),
                   "outside_window_dropped": inbound["outside_window"] + sent["outside_window"]},
        "assistant": assistant, "errors": errors,
        "inbound": inbound["rows"], "sent": sent["rows"],
    }


def one_date(client, day, window, target, assistant, portal_brief):
    result = collect(client, day, window, assistant, portal_brief)
    c.atomic_json(target, result)
    empty = not result["inbound"] and not result["sent"]
    return {"status": "empty" if empty else "ok", "date": day, "window": result["window"],
            "counts": result["counts"], "errors": result["errors"], "out": str(target)}


def main(argv=None, client=None):
    ap = argparse.ArgumentParser(description="Every inbound and sent email of one local day, archived or not. "
                                             "Exit 0 ok or empty, 3 a --run date failed, 2 error.")
    ap.add_argument("day", nargs="?", help="the date, YYYY-MM-DD (or use --run)")
    ap.add_argument("--out", help="where to write the rows, with DAY")
    ap.add_argument("--run", help="the run folder: every date in its dates.json")
    ap.add_argument("--since", help="window start, a UTC instant (default: the local day's midnight)")
    ap.add_argument("--until", help="window end, exclusive (default: the next local midnight)")
    ap.add_argument("--tz", help="the owner's IANA timezone (default: the settings)")
    ap.add_argument("--assistant", help="the executive assistant's address (default: the settings)")
    ap.add_argument("--portal-brief", help="the sender of the Portal's own Brief (default: the settings)")
    args = ap.parse_args(argv)
    out = {}

    def body():
        if bool(args.run) == bool(args.day):
            raise c.Stop("give DAY --out PATH, or --run RUN, not both")
        portal = client or c.Portal()
        if args.run:
            if args.since or args.until or args.out:
                raise c.Stop("--run takes each date's window from dates.json; drop --since, --until and --out")
            run = c.guard_run_path(args.run)
            dates = []
            for row in c.run_date_rows(run):
                day = row["date"]
                try:
                    window = row.get("email_window") or c.local_day(c.parse_date(day), c.zone(c.timezone_name(args.tz)))
                    window = {k: window[k] for k in ("since", "until")}
                    dates.append(one_date(portal, day, window, c.out_path(Path(run) / day / "emails.json"),
                                          args.assistant, args.portal_brief))
                except Exception as exc:  # noqa: BLE001 - one date failing is that date's result
                    dates.append({"status": "error", "date": day, "reason": c.safe(f"{type(exc).__name__}: {exc}")})
            failed = any(d["status"] == "error" for d in dates)
            out.update({"status": "partial" if failed else "ok", "run": str(run), "dates": dates})
            return
        c.parse_date(args.day)
        if not args.out:
            raise c.Stop("--out is required with DAY")
        if bool(args.since) != bool(args.until):
            raise c.Stop("give both --since and --until, or neither")
        if args.since:
            s, u = c.parse_time(args.since), c.parse_time(args.until)
            if not s or not u or s >= u:
                raise c.Stop("--since and --until must be ISO instants with since before until")
            window = {"since": c.utc_iso(s), "until": c.utc_iso(u)}
        else:
            w = c.local_day(c.parse_date(args.day), c.zone(c.timezone_name(args.tz)))
            window = {"since": w["since"], "until": w["until"]}
        target = c.out_path(args.out)
        out.update(one_date(portal, args.day, window, target, args.assistant, args.portal_brief))

    c.run_main(body, "sweep_emails")
    c.emit(out, c.STOP if out.get("status") == "partial" else c.OK)


if __name__ == "__main__":
    main()
