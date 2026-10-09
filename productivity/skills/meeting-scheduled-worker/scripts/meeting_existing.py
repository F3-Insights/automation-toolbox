"""meeting-existing: what the Portal already holds for one recording, found by marker.

Step 3 of the meeting-scheduled-worker skill. Reads the Portal; counts an attempt in the
local ledger (not with --dry-run), so a recording that keeps failing is parked. A failure
because the Portal was unreachable counts none: the recording is deferred instead.

An interrupted earlier attempt (an admin task and nothing else, a create whose answer was
lost, a note written but never acknowledged) is recognised from the Portal itself, by the
marker each write carries, and the run carries on from there.

`stage`:
  new           no admin task carries this recording's marker; process it
  resume        the admin task is TODO or IN_PROGRESS, or WAITING with an answer from the
                owner newer than its questions; process it, reusing what exists. When the
                owner answered, their words go to REC/answers.md and an earlier plan.json and
                check.json are set aside as plan-N.json and check-N.json
  published     the admin task is DONE but the recording is not acknowledged; acknowledge it
  acknowledged  the Portal already shows this revision processed
  changed       the recording has another transcript revision now
  unmatched     the recording has no calendar event
  waiting       the admin task waits on the owner and they have not answered
  cancelled     the admin task was cancelled (marked permanent for this revision)

Inputs: RECORDING_ID, --digest, --out (a file inside the recording's folder), --state.
Prints one JSON object (also to --out). Exit 0 new, resume or published; 3 the other
stages; 2 could not run.

Example:
    python3 meeting_existing.py 3f2a...-uuid --digest 0123456789abcdef --out REC/existing.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import _common as c

GO = {"new", "resume", "published"}
STAGES = ("new", "resume", "published", "acknowledged", "changed", "unmatched", "waiting", "cancelled")


def existing(portal, recording_id: str, digest: str) -> dict:
    if not c.is_uuid(recording_id):
        raise c.Stop("give the recording id, a UUID")
    src = c.recording(portal, recording_id)
    row = src["recording"]
    event_id, current = str(row.get("calendar_event_id") or ""), str(src.get("transcript_hash") or "")
    out = {"recording_id": recording_id, "digest": digest, "current_digest": current,
           "calendar_event_id": event_id or None, "note_id": row.get("note_id"),
           "started_at": row.get("started_at"), "processed_hash": row.get("processed_hash"),
           "admin_task": None, "existing_actions": {}, "flags": [], "answered": False}
    if row.get("processed_hash") == digest:
        return {**out, "stage": "acknowledged", "reason": "the Portal already shows this revision processed"}
    if current != digest:
        return {**out, "stage": "changed", "reason": f"the recording's transcript is now revision {current}; "
                                                     "the next listing carries it"}
    if not event_id:
        return {**out, "stage": "unmatched", "reason": "the recording has no calendar event; match it in the Portal"}

    tasks = c.tasks_mentioning(portal, recording_id, event_id)
    admins = c.admin_tasks(portal, recording_id, event_id, digest, tasks)
    if len(admins) > 1:
        out["flags"].append(f"{len(admins)} admin tasks carry this recording's marker; the oldest "
                            f"({admins[0].get('id')}) is used and the others can be cancelled: "
                            + ", ".join(str(t.get("id")) for t in admins[1:]))
    segments = (row.get("transcript") or {}).get("speech_segments") or []
    if segments:
        out["full_hash"] = fhash = c.full_hash(segments)
        out["existing_actions"] = {str(i): [c.task_line(t) for t in rows]
                                   for i, rows in sorted(c.action_tasks(tasks, event_id, fhash).items())}
    if not admins:
        return {**out, "stage": "new", "reason": "no admin task carries this recording's marker"}
    admin = admins[0]
    out["admin_task"] = c.task_line(admin)
    status = c.status_of(admin)
    if status == "DONE":
        return {**out, "stage": "published",
                "reason": "the admin task is DONE but the Portal has not recorded the acknowledgment"}
    if status in ("CANCELLED", "CANCELED"):
        return {**out, "stage": "cancelled", "reason": "the admin task was cancelled"}
    asked = status == "WAITING" or (status in ("TODO", "IN_PROGRESS") and c.asked_at(admin.get("description")))
    got = c.answers(c.get_full(portal, "task", str(admin["id"])), c.owner_email(portal)) if asked else {"answered": False}
    if status == "WAITING" and not got["answered"]:
        return {**out, "stage": "waiting",
                "reason": "the admin task is WAITING; the owner has not commented on it since its questions"}
    if got["answered"]:
        out.update(answered=True, answers_text=got["text"],
                   answers_from={k: got[k] for k in ("asked_at", "comments", "new_comments", "moved", "status")})
        return {**out, "stage": "resume", "reason": "the owner answered on the admin task; analysing it again with "
                                                    "their answers"}
    return {**out, "stage": "resume",
            "reason": f"an earlier attempt left the admin task {status or 'with no status'}; carrying on from it"}


def file_answers(folder: Path, result: dict) -> None:
    """Write the owner's answers to answers.md and set an earlier plan and check aside, so the
    analyst runs again with them. A plan already made after these same answers is kept."""
    text = result.pop("answers_text", "")
    if not result.get("answered"):
        return
    path, plan = folder / "answers.md", folder / "plan.json"
    same = path.is_file() and path.read_text(encoding="utf-8") == text
    if not (same and plan.is_file() and plan.stat().st_mtime >= path.stat().st_mtime):
        result["set_aside"] = c.set_aside(folder, "plan", "check")
        path.write_text(text, encoding="utf-8")
    result["answers"] = str(path)


def note_ledger(root: Path, result: dict) -> None:
    rid, digest, stage = result["recording_id"], result["digest"], result["stage"]
    if stage in ("acknowledged", "changed", "unmatched"):
        return
    if stage == "waiting":
        c.update_ledger(root, rid, digest, waiting_task_id=result["admin_task"]["id"], reason=result["reason"])
    elif stage == "cancelled":
        c.update_ledger(root, rid, digest, permanent=True, reason=result["reason"])
    elif result.get("answered"):  # a fresh start with the owner's answers
        c.update_ledger(root, rid, digest, attempts=0, waiting_task_id=None, last_reason=None)
        c.update_ledger(root, rid, digest, attempt=True)
    else:
        c.update_ledger(root, rid, digest, attempt=True, waiting_task_id=None)


def failed_attempt(root, recording_id: str, digest: str, reason: str, transient: bool) -> None:
    """A failed lookup still counts an attempt, so it cannot hold a slot forever; a transient
    failure (the Portal unreachable) only defers the recording."""
    if root is None or not c.is_uuid(recording_id):
        return
    try:
        if transient:
            c.update_ledger(root, recording_id, digest, deferred=True, reason=c.safe("transient: " + reason)[:300])
        else:
            c.update_ledger(root, recording_id, digest, attempt=True, reason=c.safe(reason)[:300])
    except Exception:  # the ledger is a convenience; the error itself is reported anyway
        pass


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="meeting-existing", description=__doc__.split("\n\n")[0])
    p.add_argument("recording_id")
    p.add_argument("--digest", required=True, help="the transcript digest the listing gave")
    p.add_argument("--out", help="also write the result here, inside the recording's folder")
    p.add_argument("--state", help="state folder")
    p.add_argument("--dry-run", action="store_true", help="count no attempt in the ledger")
    a = p.parse_args(argv)
    root = None
    try:
        root = c.state_root(a.state)
        folder = c.recording_dir(root, a.recording_id, a.digest)
        target = c.inside(folder, a.out) if a.out else None
        result = existing(c.client(), a.recording_id, a.digest)
        result["folder"] = str(folder)
        file_answers(folder, result)
        if not a.dry_run:
            note_ledger(root, result)
        if target:
            c.atomic_json(target, result)
    except Exception as exc:
        reason = c.reason_of(exc, "meeting-existing")
        if not a.dry_run:
            failed_attempt(root, a.recording_id, a.digest, f"meeting-existing: {reason}", c.transient(exc))
        return c.fail(reason)
    return c.emit(result, c.OK if result["stage"] in GO else c.STOP)


if __name__ == "__main__":
    sys.exit(main())
