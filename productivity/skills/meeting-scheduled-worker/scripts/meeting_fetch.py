"""meeting-fetch: one exact recording, its transcript and its meeting context, into its folder.

Step 4 of the meeting-scheduled-worker skill. Reads the Portal and writes two files into
the recording's folder: source.json (everything the analyst, checker and publisher need)
and transcript.txt (one numbered line per segment).

The checks, in code:
- Exact retrieval: the transcript is the one stored for this recording id, and its segments
  must hash to the listed digest. The event and the note must belong together.
- The note written into is the recording's own Fellow note; none is `no_note`.
- An invitation is not attendance: invitees are listed as `invited`. Speaker names match a
  contact only on an exact full name; anything else is a candidate for the analyst.
- The length cap (--cap-hours, default 3): longer is `over_cap`, marked permanent.
- Audio quality that code can see is flagged (generic labels, no speaker, one voice).
- No join links or secrets: only the event's id, title, times, organizer and company.

`status`: ok, over_cap, no_transcript, no_note, changed, mismatch. With ok,
`earlier_check` says whether an earlier plan.json with a PASS check.json still holds for
this exact plan and note, with no answers it was not made with; only then may the analysis
be skipped.

Inputs: RECORDING_ID, --digest, --cap-hours, --state, --dry-run (marks nothing permanent).
Prints one JSON summary. Exit 0 ok, 3 the others, 2 could not run (an unreachable Portal
defers the recording and takes back the attempt meeting-existing counted).

Example:
    python3 meeting_fetch.py 3f2a...-uuid --digest 0123456789abcdef
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

import _common as c

GENERIC_SPEAKER = re.compile(r"^(speaker|unknown|participant|guest)\s*[#\d]*$", re.IGNORECASE)
MAX_SPEAKERS = 15
STATUSES = ("ok", "over_cap", "no_transcript", "no_note", "changed", "mismatch")
PERMANENT = {"over_cap", "no_transcript"}
EVENT_FIELDS = ("id", "title", "start_time", "end_time", "start_local", "end_local", "organizer_email",
                "organizer_name", "company_id", "timezone")


def clock(seconds) -> str:
    try:
        s = int(float(seconds))
    except (TypeError, ValueError):
        return "--:--"
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def duration_seconds(row: dict, segments: list) -> float:
    """The longer of start-to-end and the last segment's end."""
    spans = []
    start, end = c.parse_time(row.get("started_at")), c.parse_time(row.get("ended_at"))
    if start and end:
        spans.append((end - start).total_seconds())
    ends = [float(s["end"]) for s in segments if isinstance(s.get("end"), (int, float))]
    if ends:
        spans.append(max(ends))
    return max(spans) if spans else 0.0


def quality(segments: list, invited: int) -> dict:
    speakers = Counter(str(s.get("speaker") or "").strip() for s in segments)
    flags = []
    generic = sorted(n for n in speakers if n and GENERIC_SPEAKER.match(n))
    if generic:
        flags.append("generic speaker labels: " + ", ".join(generic))
    if speakers.get(""):
        flags.append(f"{speakers['']} segments carry no speaker")
    if len([n for n in speakers if n]) == 1 and invited > 1:
        flags.append("one speaker label for a meeting with several invitees: attribution may be unreliable")
    empty = sum(1 for s in segments if not str(s.get("text") or "").strip())
    if empty:
        flags.append(f"{empty} segments have no text")
    return {"speakers": dict(speakers.most_common()), "flags": flags}


def speaker_matches(portal, names: list, owner: dict) -> dict:
    """Exact full-name matches only. The owner's own name resolves to their contact id from
    whoami, because the Portal often holds several contacts with the owner's name."""
    out = {}
    for name in names[:MAX_SPEAKERS]:
        if not name or GENERIC_SPEAKER.match(name):
            continue
        if owner.get("name") and owner.get("contact_id") and name.casefold() == str(owner["name"]).casefold():
            out[name] = {"exact": owner["contact_id"], "candidates": [], "note": "the owner, from whoami"}
            continue
        try:
            rows = portal.list_entities("contact", {"search": name}, limit=10, max_pages=1)
        except Exception as exc:  # one failed lookup leaves that name unresolved
            out[name] = {"exact": None, "candidates": [], "note": f"lookup failed: {type(exc).__name__}"}
            continue
        exact = [r for r in rows if str(r.get("full_name") or r.get("name") or "").casefold() == name.casefold()]
        out[name] = {"exact": exact[0]["id"] if len(exact) == 1 else None,
                     "candidates": [{"id": r.get("id"), "name": r.get("full_name") or r.get("name"),
                                     "company": r.get("company_name")} for r in rows[:5]]}
    return out


def fetch(portal, recording_id: str, digest: str, cap_seconds: float = c.CAP_SECONDS) -> dict:
    src = c.recording(portal, recording_id)
    row = src["recording"]
    event_id, note_id = str(row.get("calendar_event_id") or ""), str(row.get("note_id") or "")
    segments = [s for s in ((row.get("transcript") or {}).get("speech_segments") or []) if isinstance(s, dict)]
    base = {"recording_id": recording_id, "digest": digest, "calendar_event_id": event_id or None,
            "note_id": note_id or None, "started_at": row.get("started_at"), "ended_at": row.get("ended_at")}
    if str(src.get("transcript_hash") or "") != digest:
        return {**base, "status": "changed", "reason": f"the Portal now lists revision {src.get('transcript_hash')}"}
    if not event_id:
        return {**base, "status": "mismatch", "reason": "the recording has no calendar event"}
    if not segments:
        return {**base, "status": "no_transcript", "reason": "the stored transcript has no speech segments"}
    if c.queue_digest(segments) != digest:
        return {**base, "status": "changed", "reason": "the retrieved segments do not hash to the listed digest"}
    seconds = duration_seconds(row, segments)
    base["duration_seconds"] = round(seconds)
    if seconds > cap_seconds:
        return {**base, "status": "over_cap",
                "reason": f"the recording runs {clock(seconds)}, over the {clock(cap_seconds)} cap; skipped and flagged"}
    if not note_id:
        return {**base, "status": "no_note", "reason": "the recording has no Fellow note to write into"}

    composite = portal.call("get", {"entity_type": "calendar_event", "id_or_query": event_id, "detail": "full"})
    event = c.record(composite, "event" if isinstance(composite, dict) and "event" in composite else "calendar_event")
    if event.get("id") != event_id:
        return {**base, "status": "mismatch", "reason": "the calendar event read back with another id"}
    note = c.record(portal.call("get", {"entity_type": "note", "id_or_query": note_id, "detail": "full"}), "note")
    if note.get("calendar_event_id") and note["calendar_event_id"] != event_id:
        return {**base, "status": "mismatch", "reason": "the recording's note belongs to another event"}
    siblings = [{k: r.get(k) for k in ("id", "note_id", "started_at", "transcript_hash", "processed_hash")}
                for r in src.get("recordings") or [] if isinstance(r, dict)]
    if not any(r.get("id") == recording_id and r.get("transcript_hash") == digest for r in siblings):
        siblings.append({"id": recording_id, "note_id": note_id, "started_at": row.get("started_at"),
                         "transcript_hash": digest, "processed_hash": row.get("processed_hash")})
    invited = [{"name": a.get("name") or a.get("full_name") or (a.get("contact") or {}).get("full_name"),
                "email": a.get("email"), "contact_id": a.get("contact_id") or (a.get("contact") or {}).get("id"),
                "response": a.get("response_status") or a.get("status")}
               for a in (composite.get("attendees") or []) if isinstance(a, dict)]
    q = quality(segments, len(invited))
    me = c.principal(portal)
    owner = {"contact_id": me.get("contact_id"), "timezone": me.get("timezone") or "UTC", "name": me.get("display_name")}
    return {**base, "status": "ok", "match_method": row.get("match_method"),
            "match_confidence": row.get("match_confidence"), "recording_updated_at": row.get("updated_at"),
            "full_hash": c.full_hash(segments), "segment_count": len(segments), "owner": owner,
            "event": {k: event.get(k) for k in EVENT_FIELDS},
            "invited": invited, "invited_note": "an invitation is not attendance; only the transcript shows who was there",
            "speakers": q["speakers"], "speaker_matches": speaker_matches(portal, list(q["speakers"]), owner),
            "quality_flags": q["flags"], "recordings": siblings, "shared_note": len(siblings) > 1,
            "source_note": {k: note.get(k) for k in ("id", "title", "content", "updated_at", "note_type",
                                                    "visibility", "calendar_event_id")},
            "related_notes": [{k: n.get(k) for k in ("id", "title", "note_type", "updated_at")}
                              for n in composite.get("related_notes") or [] if isinstance(n, dict)],
            "related_tasks": [c.task_line(t) for t in composite.get("related_tasks") or [] if isinstance(t, dict)],
            "segments": segments}


def transcript_text(result: dict) -> str:
    event = result["event"]
    head = [f"# Transcript of recording {result['recording_id']} (revision {result['digest']})",
            f"# Meeting: {event.get('title')} at {event.get('start_local') or event.get('start_time')}",
            "# One line per segment: [index] start Speaker: text. Cite the index and quote the words exactly.", ""]
    body = [f"[{i}] {clock(s.get('start'))} {str(s.get('speaker') or '(no speaker)').strip()}: {c.folded(s.get('text'))}"
            for i, s in enumerate(result["segments"])]
    return "\n".join(head + body) + "\n"


def earlier_check(folder: Path, source: dict) -> bool:
    """A PASS check from an earlier attempt still holds for this exact plan and this source."""
    try:
        plan, check = c.read_json(folder / "plan.json"), c.read_json(folder / "check.json")
    except c.Stop:
        return False
    if not isinstance(plan, dict) or not isinstance(check, dict):
        return False
    if str(check.get("verdict") or "").upper() != "PASS" or check.get("plan_hash") != c.plan_hash(plan, source):
        return False
    return not ((folder / "answers.md").is_file() and plan.get("clarifications"))


def write(folder: Path, result: dict) -> dict:
    c.atomic_json(folder / "source.json", result)
    (folder / "transcript.txt").write_text(transcript_text(result), encoding="utf-8")
    return {"source": str(folder / "source.json"), "transcript": str(folder / "transcript.txt")}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="meeting-fetch", description=__doc__.split("\n\n")[0])
    p.add_argument("recording_id")
    p.add_argument("--digest", required=True, help="the transcript digest the listing gave")
    p.add_argument("--cap-hours", type=float, default=c.CAP_SECONDS / 3600, help="length cap (default 3)")
    p.add_argument("--state", help="state folder")
    p.add_argument("--dry-run", action="store_true", help="mark nothing in the ledger")
    a = p.parse_args(argv)
    root = None
    try:
        root = c.state_root(a.state)
        folder = c.recording_dir(root, a.recording_id, a.digest)
        result = fetch(c.client(), a.recording_id, a.digest, a.cap_hours * 3600)
        summary = {k: v for k, v in result.items() if k not in ("segments", "source_note", "speaker_matches",
                                                                  "related_notes", "related_tasks", "invited")}
        summary["folder"] = str(folder)
        if result["status"] == "ok":
            summary["files"] = write(folder, result)
            summary["source_note_chars"] = len(str(result["source_note"].get("content") or ""))
            summary["earlier_check"] = earlier_check(folder, result)
        elif result["status"] in PERMANENT and not a.dry_run:
            c.update_ledger(root, a.recording_id, a.digest, permanent=True, reason=result["reason"])
    except Exception as exc:
        reason = c.reason_of(exc, "meeting-fetch")
        if not a.dry_run and c.transient(exc):
            c.defer(root, a.recording_id, a.digest, f"meeting-fetch: {reason}")
        return c.fail(reason)
    return c.emit(summary, c.OK if result["status"] == "ok" else c.STOP)


if __name__ == "__main__":
    sys.exit(main())
