"""meeting-acknowledge: tell the Portal one recording revision is processed.

Step 9 of the meeting-scheduled-worker skill, for a recording meeting-existing reports as
`published` (an earlier attempt completed the admin task but the acknowledgment was lost).
Its one write is `complete_fellow_recording`, which sets the recording's processed_hash so
later listings leave it out.

It acknowledges only what is finished, read fresh: the transcript is still this revision,
the admin task carrying `meeting-processing:recording:<id>:<digest>` is DONE, and that task
shows the recording's note. A DONE task carrying only the older event-keyed marker is given
the exact marker first (one update_task, read back), because the Portal acknowledges against
nothing else.

`status`: acknowledged, already_acknowledged, would_acknowledge (--dry-run), or refused
with `code` NO_TASK, NOT_DONE, CHANGED, NO_NOTE, LINK_NOT_VERIFIED or ACK_NOT_VERIFIED.
Exit 0 for the first three, 3 refused, 2 could not run (an unreachable Portal defers the
recording and takes back the attempt meeting-existing counted, except in a dry run).

Example:
    python3 meeting_acknowledge.py 3f2a...-uuid --digest 0123456789abcdef
"""

from __future__ import annotations

import argparse
import sys

import _common as c

CODES, STATUSES = c.ACK_CODES, c.ACK_STATUSES


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="meeting-acknowledge", description=__doc__.split("\n\n")[0])
    p.add_argument("recording_id")
    p.add_argument("--digest", required=True, help="the transcript digest that was processed")
    p.add_argument("--state", help="state folder whose ledger an outage defers")
    p.add_argument("--dry-run", action="store_true", help="check everything, write nothing")
    a = p.parse_args(argv)
    try:
        result = c.acknowledge(c.client(), a.recording_id, a.digest, a.dry_run)
    except Exception as exc:
        reason = c.reason_of(exc, "meeting-acknowledge")
        if not a.dry_run and c.transient(exc):
            try:
                c.defer(c.state_root(a.state), a.recording_id, a.digest, f"meeting-acknowledge: {reason}")
            except Exception:  # the error below is what is reported
                pass
        return c.fail(reason)
    return c.emit(result, c.STOP if result["status"] == "refused" else c.OK)


if __name__ == "__main__":
    sys.exit(main())
