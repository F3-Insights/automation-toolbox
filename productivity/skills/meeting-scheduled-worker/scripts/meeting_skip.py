"""meeting-skip: record why one recording was skipped, or clear it so it is tried again.

Used by the meeting-scheduled-worker skill whenever a recording is skipped for a reason no
command recorded (the analyst blocked, the check failed twice, a command could not run),
and by the owner to put a parked recording back in the queue. Writes only the local ledger
in the state folder, never the Portal.

A reason defers the recording for the backoff, and after the attempt limit it is parked.
--permanent leaves this revision out until a new transcript revision arrives; use it only
for a reason no retry cures. --clear forgets the recording (one revision with --digest,
else every revision).

Prints one JSON object. Exit 0, or 2 could not run.

Examples:
    python3 meeting_skip.py 3f2a...-uuid --digest 0123456789abcdef --reason "the checker failed twice: ..."
    python3 meeting_skip.py 3f2a...-uuid --clear
"""

from __future__ import annotations

import argparse
import sys

import _common as c


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="meeting-skip", description=__doc__.split("\n\n")[0])
    p.add_argument("recording_id")
    p.add_argument("--digest", help="the transcript revision")
    p.add_argument("--reason", help="why it was skipped, in one line")
    p.add_argument("--permanent", action="store_true", help="leave this revision out of later runs")
    p.add_argument("--clear", action="store_true", help="forget the recording so the next run tries it")
    p.add_argument("--state", help="state folder")
    a = p.parse_args(argv)
    try:
        if not c.is_uuid(a.recording_id):
            raise c.Stop("give the recording id, a UUID")
        root = c.state_root(a.state)
        if a.clear:
            return c.emit({"status": "cleared", "recording_id": a.recording_id,
                           "removed": c.clear_ledger(root, a.recording_id, a.digest)}, c.OK)
        if not a.digest or not (a.reason or "").strip():
            raise c.Stop("--digest and --reason are required unless --clear")
        entry = c.update_ledger(root, a.recording_id, a.digest, reason=c.safe(a.reason.strip())[:500],
                                **({"permanent": True} if a.permanent else {}))
    except Exception as exc:
        return c.fail(c.reason_of(exc, "meeting-skip"))
    return c.emit({"status": "recorded", "entry": entry}, c.OK)


if __name__ == "__main__":
    sys.exit(main())
