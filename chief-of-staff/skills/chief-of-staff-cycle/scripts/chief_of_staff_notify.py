#!/usr/bin/env python3
"""chief-of-staff-notify: the cycle's messages to the owner, a link and a count, never a briefing.

    chief_of_staff_notify.py CYCLE_DIR --kind receipt|decision [--dry-run]

- receipt: "your receipt is ready", once a day, and only when verify.json found the note in
  the Portal holding this cycle's own marker (this_cycle_written).
- decision: "N decisions waiting", at most three a day, and only when the Portal's own record
  (verify.json: decision tasks created since the cycle started) shows the cycle raised one.
- (The backstop message, once a day, is sent by chief_of_staff_fleet.py launch.)

One recipient, the token's own member, through comms-reply-to-email's notify_owner.py (the
Portal's Teams post, email as the fallback); the text is cut to 300 characters. The link
needs the setting portal_web_url (the Portal's web address); without it the message carries
only the Open in Portal button. The caps are counted per kind per local day in notify.json in
the state folder, and only a message that was sent counts. NOTIFY_OWNER_MODE=off sends
nothing and =dry-run rehearses. A dry run sends nothing and counts nothing.

Results: sent, held (cap reached), skipped (nothing to say, or no verified receipt),
not_sent (refused or unreachable), dry_run. Always exit 0 unless it could not run (2): a
message that did not go never fails a cycle.

Example:
    python3 chief_of_staff_notify.py ~/state/chief-of-staff/cycles/2030-03-04/061500 --kind receipt
"""

import argparse

import _common as c


def main(argv=None):
    p = argparse.ArgumentParser(description="Send the receipt link or the decision count to the owner, within the caps.")
    p.add_argument("cycle_dir")
    p.add_argument("--kind", required=True, choices=("receipt", "decision"))
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    try:
        folder = c.cycle_dir(args.cycle_dir)
        out = c.notify(folder, args.kind, c.root_of(folder), dry_run=args.dry_run)
    except c.Bad as exc:
        c.fail(str(exc))
    out["dry_run"] = out.get("status") == "dry_run"
    c.emit(out, c.OK)


if __name__ == "__main__":
    main()
