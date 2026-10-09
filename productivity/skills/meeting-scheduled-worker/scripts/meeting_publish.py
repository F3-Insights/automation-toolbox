"""meeting-publish: write one checked meeting plan to the Portal, then acknowledge the recording.

Step 8 of the meeting-scheduled-worker skill. The writes are ordinary sourced internal
records: the recording's admin task, the action tasks the plan creates, the recording's own
meeting note (updated in place, with its links), the enrichment hand-offs, the admin task's
status, and `complete_fellow_recording`. Nothing is sent to anyone, no project is created
and no business task is completed.

FOLDER is the recording's folder: source.json (meeting-fetch), plan.json (the analyst),
check.json (the checker), and optionally existing.json and answers.md (meeting-existing).
The owner's answers are read from FOLDER/answers.md whenever it exists; --answers names
another file inside the folder only as an override.

Idempotent by marker. Before each create the item is looked up in the Portal by its marker
(admin task, action task, enrichment task); found means reused. A create whose answer is
lost is looked up again at once. The admin task is set DONE only after the note, its links
and every task read back correctly, and the recording is acknowledged only after that.

Refusals (`code`), writing nothing more for this recording: INVALID_PLAN, UNCHECKED,
CHECK_FAILED, CHANGED_SINCE_CHECK (the plan or the note it was made against changed after
the check), ANSWERS_UNAPPLIED (answers in the folder, but the plan still asks), NOT_LOCAL_OWNER
(stops the run), TRANSCRIPT_CHANGED, LINKS_CHANGED, CANCELLED, WAITING, NOTE_EDITED (the note
holds text this job did not write; when no retry cures it, `permanent` is true and the
revision is marked permanent in the ledger), MARKER_CONFLICT, MISSING_RECORD,
READBACK_MISMATCH, LINK_NOT_VERIFIED, BUSY (another publish holds the lock), DRY_RUN (the
runner set F3I_TOOLBOX_DRY_RUN=1 and --dry-run was not passed).

`status`: published, waiting (questions for the owner at the end of the admin task, which
is WAITING; the recording stays unacknowledged), published_unacknowledged, would_publish
(--dry-run: every read made, the writes listed, note-preview.md left), or refused.
Exit 0 published, waiting or would_publish; 3 refused or published_unacknowledged; 2 could
not run. Writes publish.json (publish-dry-run.json in a dry run) into the folder, and the
ledger of the state folder the folder lies in (or --state): a waiting result's admin task,
a permanent NOTE_EDITED, or a deferral when the Portal was unreachable.

Inputs: FOLDER, --answers, --agent-slug (the Portal agent that takes enrichment tasks;
default the setting enrichment_agent, else deep-researcher), --state, --dry-run.

Example:
    python3 meeting_publish.py ~/.local/state/meeting-processing/recordings/<RID>-<D> --dry-run
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import _common as c

REFUSALS = {
    "INVALID_PLAN": "the plan does not validate against the transcript",
    "UNCHECKED": "no usable check record",
    "CHECK_FAILED": "the check record is not a PASS",
    "CHANGED_SINCE_CHECK": "the plan changed after it was checked",
    "NOT_LOCAL_OWNER": "the Portal does not hand processing to this host",
    "TRANSCRIPT_CHANGED": "the transcript changed since it was fetched",
    "LINKS_CHANGED": "the recording's event or note changed since it was fetched",
    "CANCELLED": "the admin task was cancelled",
    "WAITING": "the admin task waits on the owner's answer",
    "ANSWERS_UNAPPLIED": "the owner's answers are given but the plan still lists clarifications",
    "NOTE_EDITED": "the meeting note holds an edit this job did not write; the edit is kept",
    "MARKER_CONFLICT": "a task carrying this action's marker is a different action",
    "MISSING_RECORD": "a record the plan names does not read back",
    "READBACK_MISMATCH": "a write did not read back as written",
    "LINK_NOT_VERIFIED": "a task-to-note link did not read back",
    "BUSY": "another meeting-publish holds this recording's lock",
    "DRY_RUN": "the run is a dry run and --dry-run was not passed",
}
STATUSES = ("published", "waiting", "published_unacknowledged", "would_publish", "refused")
ADMIN_PREFIX = "Process meeting: "


class Refused(Exception):
    def __init__(self, code: str, reason: str, permanent: bool = False):
        super().__init__(reason)
        self.code, self.reason, self.permanent = code, reason, permanent


def passthrough(exc: BaseException) -> None:
    """A read that failed because the Portal was unreachable is not a missing record: re-raise
    it so the recording is deferred, not refused."""
    if c.transient(exc):
        raise exc


def prior_written(folder: Path, key: str = "notes_written") -> list:
    """Fingerprints earlier publishes recorded (the note texts, the questions sections), so a
    later run tells its own text from a human edit."""
    try:
        prior = c.read_json(folder / "publish.json")
    except c.Stop:
        return []
    rows = prior.get(key) if isinstance(prior, dict) else None
    return [str(r) for r in rows if isinstance(r, str)] if isinstance(rows, list) else []


class Publisher:
    """One publish of one recording folder. Holds what was read, written and flagged."""

    def __init__(self, portal, folder: Path, dry_run=False, answers=None, agent_slug="deep-researcher"):
        self.portal, self.folder, self.dry_run, self.agent_slug = portal, folder, dry_run, agent_slug
        if answers is None and (folder / "answers.md").is_file():
            answers = c.read_answers(folder / "answers.md")
        self.answers = answers
        self.source = c.read_json(folder / "source.json")
        self.plan = c.read_json(folder / "plan.json")
        self.existing = c.read_json(folder / "existing.json") if (folder / "existing.json").is_file() else {}
        self.rid, self.digest = self.source["recording_id"], self.source["digest"]
        self.eid, self.fhash = self.source["calendar_event_id"], self.source["full_hash"]
        self.note_id = self.source["source_note"]["id"]
        self.writes, self.flags = [], []
        self.written, self.asked = prior_written(folder), prior_written(folder, "questions_written")
        self.out = {"recording_id": self.rid, "digest": self.digest, "folder": str(folder), "note_id": self.note_id,
                    "admin_task_id": None, "tasks_created": [], "tasks_reused": [], "tasks_linked": [],
                    "enrichment": [], "writes": self.writes, "flags": self.flags,
                    "notes_written": self.written, "questions_written": self.asked}

    # ---------------------------------------------------------------- gates before any write

    def check_record(self) -> None:
        errors = c.validate(self.plan, self.source, self.existing)
        if errors:
            raise Refused("INVALID_PLAN", "; ".join(errors[:5]))
        try:
            check = c.read_json(self.folder / "check.json")
        except c.Stop as exc:
            raise Refused("UNCHECKED", str(exc)) from None
        if not isinstance(check, dict) or not check.get("verdict") or not check.get("plan_hash"):
            raise Refused("UNCHECKED", "the check record lacks verdict or plan_hash")
        if str(check["verdict"]).upper() != "PASS":
            raise Refused("CHECK_FAILED", f"the check record says {check['verdict']}")
        if check.get("recording_id") not in (None, self.rid):
            raise Refused("UNCHECKED", "the check record is for another recording")
        if check["plan_hash"] != c.plan_hash(self.plan, self.source):
            raise Refused("CHANGED_SINCE_CHECK", "plan.json or the meeting note in source.json changed after "
                                                 "the check; analyse and check it again")
        if self.answers and self.plan["clarifications"]:
            raise Refused("ANSWERS_UNAPPLIED", "the owner's answers are in the folder but plan.json still lists "
                                               "clarifications; set the plan aside and run the analyst with the answers")

    def guard(self) -> None:
        """Before each write: still ours to process, the same words, the same event and note."""
        own = c.ownership(self.portal)
        if not own["local"]:
            raise Refused("NOT_LOCAL_OWNER", f"owner {own['owner']!r}, {own['active_cloud_runs']} active cloud runs")
        src = c.recording(self.portal, self.rid)
        row = src["recording"]
        segments = (row.get("transcript") or {}).get("speech_segments") or []
        if src.get("transcript_hash") != self.digest or c.full_hash(segments) != self.fhash:
            raise Refused("TRANSCRIPT_CHANGED", "the stored transcript is no longer the one analysed")
        if row.get("calendar_event_id") != self.eid or row.get("note_id") != self.note_id:
            raise Refused("LINKS_CHANGED", "the recording now points at another event or note")

    # ---------------------------------------------------------------- tasks

    def lookup(self) -> list:
        return c.tasks_mentioning(self.portal, self.rid, self.eid)

    def create_task(self, args: dict, marker: str, what: str):
        """Create one task; when the answer is lost, look the marker up before giving up."""
        if self.dry_run:
            self.writes.append({"would": "create_task", "what": what, "source_reference": marker,
                                "title": args.get("title")})
            return None
        cause = None
        try:
            created = self.portal.call("create_task", {k: v for k, v in args.items() if v is not None})
            tid = created.get("id") if isinstance(created, dict) else None
            if c.is_uuid(tid):
                self.writes.append({"did": "create_task", "what": what, "id": tid, "source_reference": marker})
                return tid
            problem = f"create_task answered without an id: {str(created)[:200]}"
        except Exception as exc:  # reconciled below by looking the marker up
            problem, cause = f"create_task failed: {type(exc).__name__}: {exc}", exc
        found = c.with_marker(self.lookup(), marker)
        if found:
            self.flags.append(f"{what}: the create answer was lost, and the Portal has the task ({found[0]['id']}); using it")
            self.writes.append({"did": "create_task", "what": what, "id": found[0]["id"], "source_reference": marker,
                                "recovered": True})
            return str(found[0]["id"])
        raise c.Stop(f"{what}: {problem}; no task carries {marker}, so the next run creates it") from cause

    def read_task(self, tid: str) -> dict:
        try:
            return c.get_full(self.portal, "task", tid)
        except c.Stop as exc:
            passthrough(exc)
            raise Refused("MISSING_RECORD", f"task {tid}: {exc}") from None

    def admin(self, tasks: list, owner_id):
        admins = c.admin_tasks(self.portal, self.rid, self.eid, self.digest, tasks)
        if len(admins) > 1:
            self.flags.append(f"{len(admins)} admin tasks carry this recording's marker; using the oldest, "
                              f"{admins[0]['id']}; the others can be cancelled: "
                              + ", ".join(str(t["id"]) for t in admins[1:]))
        if admins:
            return admins[0]
        marker = c.admin_marker(self.rid, self.digest)
        title = (ADMIN_PREFIX + str(self.source["event"].get("title") or self.eid))[:200]
        # The description carries the recording and event ids, so the lookup (a text search) finds it.
        args = {"title": title, "source_reference": marker, "owner_contact_id": owner_id, "priority": 2,
                "description": f"{marker}\nSource: portal://calendar_event/{self.eid}\nRecording: {self.rid}\n"
                               "Processed by the meeting-scheduled-worker skill: the meeting note, linked "
                               "actions and targeted enrichment are written from the original transcript, "
                               "independently checked, then this task is completed and the recording acknowledged."}
        tid = self.create_task(args, marker, "admin task")
        return {"id": tid, "status": "TODO", "source_reference": marker, "title": title} if tid else None

    # ---------------------------------------------------------------- the note

    def section_marks(self) -> tuple:
        key = f"{self.rid}:{self.digest}"
        return f"<!-- local-recording-section:{key} -->", f"<!-- /local-recording-section:{key} -->"

    def shared(self) -> bool:
        return len(self.source.get("recordings") or []) >= 2

    def own_part(self, content) -> str:
        """The text this recording owns: the whole note, or its section in a shared note."""
        content = str(content or "")
        if not self.shared():
            return content
        start, end = self.section_marks()
        if content.count(start) == 1 and content.count(end) == 1 and content.index(start) < content.index(end):
            return content[content.index(start):content.index(end) + len(end)]
        return content

    def ours(self, content) -> bool:
        """This recording's part of the note is text an earlier publish recorded writing."""
        return c.fingerprint(self.own_part(content)) in self.written

    def compose(self, lines: list) -> str:
        content = str(self.plan["note_content"]).rstrip()
        content += "\n\n## Actions and follow-up\n\n" + ("\n".join(lines) if lines else "No new accepted actions were identified.")
        if self.plan["clarifications"]:
            content += "\n\n## Clarifications needed\n\n" + "\n".join(
                "- " + c.folded(q["question"]) for q in self.plan["clarifications"])
        if self.answers:
            content += "\n\n## Clarification received\n\nThe owner's answers, filed verbatim:\n\n" + self.answers.strip()
        content += f"\n\n[Meeting and source transcript](portal://calendar_event/{self.eid})\n"
        content += c.NOTE_MARK.format(rid=self.rid, digest=self.digest) + "\n"
        if not self.shared():
            return content
        # A note several recordings share keeps the others' sections and any human text byte for byte.
        start, end = self.section_marks()
        original = str(self.source["source_note"].get("content") or "")
        block = f"{start}\n## Recording {self.source.get('started_at') or ''}\n\n{content.rstrip()}\n{end}"
        if start in original or end in original:
            if original.count(start) != 1 or original.count(end) != 1:
                raise Refused("NOTE_EDITED", "this recording's section boundaries in the note are ambiguous")
            left, rest = original.split(start, 1)
            if end not in rest:
                raise Refused("NOTE_EDITED", "this recording's section boundaries are out of order")
            return left + block + rest.split(end, 1)[1]
        return original + "\n\n" + block + "\n"

    # ---------------------------------------------------------------- the run

    def run(self) -> dict:
        self.check_record()
        self.guard()
        # Checked before anything is created, so a refusal leaves no task behind. Text this job
        # wrote after the fetch (an earlier, interrupted attempt) is not an edit.
        note = c.record(self.portal.call("get", {"entity_type": "note", "id_or_query": self.note_id,
                                                 "detail": "full"}), "note")
        fetched = self.source["source_note"]
        if (note.get("content") != fetched.get("content") or note.get("title") != fetched.get("title")) \
                and not self.ours(note.get("content")):
            raise Refused("NOTE_EDITED", "the meeting note changed after it was fetched; the edit is kept, "
                                         "nothing is written, and the next run fetches it and analyses it again")
        owner_id = c.principal(self.portal).get("contact_id")
        tasks = self.lookup()
        admin = self.admin(tasks, owner_id)
        if admin and c.status_of(admin) == "DONE":
            self.out["admin_task_id"] = admin["id"]
            self.flags.append("already published by an earlier attempt; only the acknowledgment was left")
            return self.finish("DONE")
        if admin and c.status_of(admin) in ("CANCELLED", "CANCELED"):
            raise Refused("CANCELLED", f"admin task {admin['id']} was cancelled")
        if admin and c.status_of(admin) == "WAITING" and not self.answers:
            raise Refused("WAITING", f"admin task {admin['id']} waits on the owner's answer")
        self.out["admin_task_id"] = admin["id"] if admin else None

        lines, task_ids = self.actions(tasks)
        content, title = self.compose(lines), str(self.plan["note_title"])
        already = note.get("content") == content and note.get("title") == title
        current = self.own_part(note.get("content"))
        if not already and c.NOTE_MARK.format(rid=self.rid, digest=self.digest) in current \
                and current != self.own_part(content) and not self.ours(current):
            raise Refused("NOTE_EDITED", "the meeting note carries this job's earlier text with changes this job "
                                         "did not write (none of its publishes recorded that text); the edit is "
                                         "kept and nothing more is written for this recording. No retry cures "
                                         "this, so this revision is marked permanent in the ledger and later runs "
                                         "leave it out: to have it rewritten with the edit taken in, the owner removes "
                                         "the marker line from the note and clears it with meeting-skip "
                                         f"{self.rid} --digest {self.digest} --clear", permanent=True)
        self.write_note(note, title, content, already, task_ids, admin)
        self.enrich(owner_id)
        return self.finish("WAITING" if self.plan["clarifications"] else "DONE")

    def actions(self, tasks: list) -> tuple:
        by_index = c.action_tasks(tasks, self.eid, self.fhash)
        lines, task_ids = [], []
        for i, action in enumerate(self.plan["actions"]):
            disposition = action["disposition"]
            if disposition in ("proposal", "unresolved"):
                lines.append(f"- {c.folded(action['title'])} ({disposition}). {c.folded(action.get('description'))}")
                continue
            if disposition == "link_existing":
                tid = str(action["existing_task_id"])
                self.read_task(tid)
                self.out["tasks_linked"].append(tid)
            else:
                tid = self.create_action(i, action, by_index.get(i) or [])
            if tid:
                task_ids.append(tid)
                lines.append(f"- [{c.folded(action['title'])}](portal://task/{tid})")
            else:
                lines.append(f"- {c.folded(action['title'])} (task to be created)")
        return lines, task_ids

    def create_action(self, i: int, action: dict, found: list):
        marker = c.action_marker(self.eid, self.fhash, i)
        if found:
            same = [t for t in found if c.folded(t.get("title")) == c.folded(action["title"])]
            if not same:
                raise Refused("MARKER_CONFLICT", f"task {found[0].get('id')} carries {marker} but is "
                                                 f"{found[0].get('title')!r}, not {action['title']!r}")
            if len(found) > 1:
                self.flags.append(f"{len(found)} tasks carry {marker}; using {same[0]['id']}")
            self.out["tasks_reused"].append(same[0]["id"])
            return str(same[0]["id"])
        for kind, key in (("contact", "owner_contact_id"), ("domain", "domain_id"), ("project", "project_id")):
            if action.get(key):
                try:
                    c.record(self.portal.call("get", {"entity_type": kind, "id_or_query": action[key]}), kind)
                except c.Stop as exc:
                    passthrough(exc)
                    raise Refused("MISSING_RECORD", f"action {i}: {kind} {action[key]}: {exc}") from None
        args = {"title": action["title"], "source_reference": marker, "owner_contact_id": action["owner_contact_id"],
                "domain_id_or_name": action["domain_id"], "project_id": action.get("project_id"),
                "due_date": action.get("due_date"),
                "description": f"{str(action.get('description') or '').rstrip()}\n\nMeeting: portal://calendar_event/{self.eid}\n"
                               f"Meeting note: portal://note/{self.note_id}"}
        tid = self.create_task(args, marker, f"action {i}")
        if tid is None:
            return None
        after = c.record(self.read_task(tid), "task")
        if after.get("owner_contact_id") != action["owner_contact_id"] or c.folded(after.get("title")) != c.folded(action["title"]):
            raise Refused("READBACK_MISMATCH", f"task {tid} did not read back with the planned owner and title")
        self.out["tasks_created"].append(tid)
        return tid

    def write_note(self, note: dict, title: str, content: str, already: bool, task_ids: list, admin) -> None:
        wanted = [("calendar_event", self.eid)]
        if admin and admin.get("id"):
            wanted.append(("task", admin["id"]))
        wanted += [("task", t) for t in dict.fromkeys(task_ids)]
        wanted += [("contact", a["owner_contact_id"]) for a in self.plan["actions"]
                   if a.get("owner_contact_id") and a["disposition"] in ("create", "link_existing")]
        wanted += [(ref.split("/")[2], ref.split("/")[3]) for ref in self.plan["enrichment_refs"]]
        wanted = list(dict.fromkeys(wanted))
        visible = {(a.get("entity_type"), a.get("entity_id")) for a in note.get("associations") or []}
        missing = [{"entity_type": k, "entity_id": v} for k, v in wanted if (k, v) not in visible]
        if self.dry_run:
            if not already:
                self.writes.append({"would": "update_note", "id": self.note_id, "title": title, "content_chars": len(content)})
                (self.folder / "note-preview.md").write_text(f"# {title}\n\n{content}", encoding="utf-8")
            if missing:
                self.writes.append({"would": "update_note.add_associations", "count": len(missing)})
            return
        if not already:
            self.guard()
            # Recorded before the write, so an answer lost after the Portal wrote it still leaves
            # the record: the next run knows the text as this job's, not a human edit.
            stamp = c.fingerprint(self.own_part(content))
            if stamp not in self.written:
                self.written.append(stamp)
            c.atomic_json(self.folder / "publish.json", {**self.out, "checkpoint": "writing the note"})
            self.portal.call("update_note", {"id": self.note_id, "fields": {"title": title, "content": content},
                                             "expected_updated_at": note.get("updated_at")})
            self.writes.append({"did": "update_note", "id": self.note_id})
        if missing:
            self.portal.call("update_note", {"id": self.note_id, "add_associations": missing})
            self.writes.append({"did": "update_note.add_associations", "count": len(missing)})
        after_env = c.get_full(self.portal, "note", self.note_id)
        after = c.record(after_env, "note")
        if after.get("content") != content or after.get("title") != title:
            raise Refused("READBACK_MISMATCH", "the meeting note did not read back as written")
        seen = {(a.get("entity_type"), a.get("entity_id")) for a in (after.get("associations") or after_env.get("associations") or [])}
        lost = [f"{k}/{v}" for k, v in wanted if (k, v) not in seen]
        if lost:
            raise Refused("READBACK_MISMATCH", "note links did not read back: " + ", ".join(lost[:5]))
        for tid in dict.fromkeys(task_ids + ([admin["id"]] if admin and admin.get("id") else [])):
            if not any(isinstance(n, dict) and n.get("id") == self.note_id for n in self.read_task(tid).get("notes") or []):
                raise Refused("LINK_NOT_VERIFIED", f"task {tid} does not show the meeting note")

    def enrich(self, owner_id) -> None:
        refs = list(dict.fromkeys(self.plan["enrichment_refs"]))
        if not refs:
            return
        if not self.dry_run:
            profiles = self.portal.call("list_agent_profiles", {})
            rows = profiles.get("profiles") if isinstance(profiles, dict) else None
            slugs = {p.get("slug") for p in (rows if isinstance(rows, list) else [])
                     if isinstance(p, dict) and p.get("is_active", True)}
            if self.agent_slug not in slugs:
                self.flags.append(f"no active agent profile {self.agent_slug!r}; enrichment hand-offs skipped: "
                                  + ", ".join(refs))
                return
        revision = f"Meeting evidence revision: {self.eid}:{self.fhash}"
        for ref in refs:
            kind, uid = ref.split("/")[2], ref.split("/")[3]
            try:
                full = c.record(self.portal.call("get", {"entity_type": kind, "id_or_query": uid}), kind)
            except c.Stop as exc:
                passthrough(exc)
                raise Refused("MISSING_RECORD", f"enrichment target {ref}: {exc}") from None
            marker = c.enrichment_marker(kind, uid)
            description = (f"{marker}\nIntegrate sourced durable context into canonical fields and relationships; "
                           "use topic memos for dated events. Verify destinations before completion.\n"
                           f"{revision}\nRelevant meeting: portal://calendar_event/{self.eid}\n"
                           f"Source note: portal://note/{self.note_id}")
            rows = sorted((t for t in c.tasks_mentioning(self.portal, uid)
                           if t.get("source_reference") == marker or marker in str(t.get("description") or "")),
                          key=lambda t: str(t.get("created_at") or ""))
            if len(rows) > 1:
                self.flags.append(f"{len(rows)} enrichment tasks carry {marker}; using {rows[0]['id']}")
            if rows:
                self.extend_enrichment(rows[0], revision, description, ref)
                continue
            name = full.get("full_name") or full.get("name") or uid
            tid = self.create_task({"title": f"Enrich {kind}: {name}"[:200], "description": description,
                                    "source_reference": marker, "owner_contact_id": owner_id,
                                    "assignees": [self.agent_slug], "priority": 2}, marker, f"enrichment {ref}")
            self.out["enrichment"].append({"ref": ref, "task_id": tid, "outcome": "created" if tid else "would_create"})

    def extend_enrichment(self, task: dict, revision: str, description: str, ref: str) -> None:
        """An enrichment task already exists: add this meeting's evidence, reopening it if DONE."""
        current = c.record(self.read_task(task["id"]), "task")
        if revision in str(current.get("description") or ""):
            self.out["enrichment"].append({"ref": ref, "task_id": current["id"], "outcome": "already_queued"})
            return
        reopen = c.status_of(current) == "DONE"
        if self.dry_run:
            self.writes.append({"would": "update_task", "id": current["id"], "what": f"enrichment {ref}", "reopen": reopen})
            self.out["enrichment"].append({"ref": ref, "task_id": current["id"], "outcome": "would_extend"})
            return
        args = {"id": current["id"], "fields": {"description": str(current.get("description") or "") + "\n\n" + description}}
        if reopen:
            args["status"] = "TODO"
        self.portal.call("update_task", args)
        self.writes.append({"did": "update_task", "id": current["id"], "what": f"enrichment {ref}", "reopen": reopen})
        if revision not in str(c.record(self.read_task(current["id"]), "task").get("description") or ""):
            raise Refused("READBACK_MISMATCH", f"enrichment task {current['id']} did not read back extended")
        self.out["enrichment"].append({"ref": ref, "task_id": current["id"], "outcome": "reopened" if reopen else "extended"})

    # ---------------------------------------------------------------- questions and the finish

    def question_lines(self, questions: list) -> list:
        out = []
        for n, q in enumerate(questions, 1):
            line = f"{n}. {c.folded(q.get('question'))}"
            if q.get("options"):
                line += " Options: " + "; ".join(c.folded(o) for o in q["options"]) + "."
            if q.get("recommended"):
                line += f" Recommended: {c.folded(q['recommended'])}."
            out.append(line)
        return out

    def with_questions(self, description, questions: list) -> str:
        """The admin task's description with this plan's questions as a section at its end.
        An earlier section is replaced only when it is exactly one this job wrote, keeping any
        text below it; a section the owner typed inside is kept whole and the new one follows."""
        at = c.now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
        block = c.QUESTIONS_HEAD.format(at=at) + "\n" + "\n".join(self.question_lines(questions)) + "\n\n" + c.QUESTIONS_FOOT
        before, old, after = c.split_questions(description)
        if old and c.fingerprint(old.strip()) in self.asked:
            return before.rstrip() + "\n\n" + block + after
        return str(description or "").rstrip() + "\n\n" + block

    def asks_now(self, task: dict) -> bool:
        """The admin task's last questions section lists exactly this plan's questions."""
        section = c.split_questions(task.get("description"))[1]
        return c.asked_at(task.get("description")) is not None and all(
            line in section for line in self.question_lines(self.plan.get("clarifications") or []))

    def finish(self, status: str) -> dict:
        admin_id = self.out["admin_task_id"]
        questions = (self.plan.get("clarifications") or []) if status == "WAITING" else []
        if self.dry_run:
            if admin_id is None or c.status_of(self.read_task(admin_id).get("task", {})) != status:
                self.writes.append({"would": "update_task", "what": "admin task", "status": status})
            if status == "DONE":
                self.writes.append({"would": "complete_fellow_recording", "recording_id": self.rid})
            return {**self.out, "status": "would_publish", "admin_status": status, "questions": questions}
        current = c.record(self.read_task(admin_id), "task")
        args = {"id": admin_id}
        if c.status_of(current) != status:
            args["status"] = status
        if status == "WAITING" and not self.asks_now(current):
            description = self.with_questions(current.get("description"), questions)
            args["fields"] = {"description": description}
            stamp = c.fingerprint(c.split_questions(description)[1].strip())  # recorded before the write
            if stamp not in self.asked:
                self.asked.append(stamp)
            c.atomic_json(self.folder / "publish.json", {**self.out, "checkpoint": "asking the owner"})
        if len(args) > 1:
            self.guard()
            self.portal.call("update_task", args)
            self.writes.append({"did": "update_task", "what": "admin task", "status": status,
                                "questions": len(questions) if "fields" in args else 0})
            after = c.record(self.read_task(admin_id), "task")
            if c.status_of(after) != status or (status == "WAITING" and not self.asks_now(after)):
                raise Refused("READBACK_MISMATCH", f"the admin task did not read back {status} with its questions")
        if status == "WAITING":
            return {**self.out, "status": "waiting", "admin_status": status, "questions": questions}
        result = c.acknowledge(self.portal, self.rid, self.digest)
        self.out["acknowledgment"] = result
        if result["status"] in ("acknowledged", "already_acknowledged"):
            return {**self.out, "status": "published", "admin_status": status, "acknowledged": True}
        return {**self.out, "status": "published_unacknowledged", "admin_status": status, "acknowledged": False,
                "reason": result.get("reason")}


def note_ledger(root, result: dict) -> None:
    """A waiting result records the admin task it waits on; a refusal no retry cures marks the
    revision permanent. A ledger that cannot be written is flagged, never an error."""
    if root is None:
        return
    rid, digest = result["recording_id"], result["digest"]
    try:
        if result["status"] == "waiting" and result.get("admin_task_id"):
            c.update_ledger(root, rid, digest, waiting_task_id=result["admin_task_id"],
                            reason="waiting on the owner's answer on the admin task")
        elif result["status"] == "refused" and result.get("permanent"):
            c.update_ledger(root, rid, digest, permanent=True, reason=c.safe(result["reason"])[:500])
    except Exception as exc:  # the Portal holds the truth; the ledger only saves slots
        result.setdefault("flags", []).append(f"the ledger was not updated: {type(exc).__name__}: {exc}")


def publish(portal, folder: Path, dry_run=False, answers=None, agent_slug="deep-researcher", root=None) -> dict:
    """Publish one recording folder. `root` is the state folder whose ledger records a waiting
    result or a permanent refusal; by default the one the folder lies in."""
    refusal = c.dry_run_refusal(dry_run)
    if refusal:
        rid, digest = c.folder_ids(folder)
        return {"recording_id": rid, "digest": digest, "folder": str(folder), "status": "refused",
                "code": "DRY_RUN", "reason": refusal}
    try:
        with c.locked(folder / "publish.lock"):
            pub = Publisher(portal, folder, dry_run, answers, agent_slug)
            try:
                result = pub.run()
            except Refused as exc:
                result = {**pub.out, "status": "refused", "code": exc.code, "reason": exc.reason}
                if exc.permanent:
                    result["permanent"] = True
            result["finished_at"] = datetime.now().astimezone().isoformat()
            result["notes_written"], result["questions_written"] = pub.written, pub.asked
            c.atomic_json(folder / ("publish-dry-run.json" if dry_run else "publish.json"), result)
    except c.Busy as exc:  # the holder owns publish.json; nothing is read or written here
        rid, digest = c.folder_ids(folder)
        return {"recording_id": rid, "digest": digest, "folder": str(folder), "status": "refused",
                "code": "BUSY", "reason": str(exc)}
    if not dry_run:
        note_ledger(root if root is not None else c.state_of(folder), result)
    return result


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="meeting-publish", description=__doc__.split("\n\n")[0])
    p.add_argument("folder", help="the recording's folder")
    p.add_argument("--answers", help="another file of the owner's answers inside the folder (overrides answers.md)")
    p.add_argument("--agent-slug", help="the Portal agent that takes enrichment tasks")
    p.add_argument("--state", help="state folder whose ledger this writes (default: the one FOLDER is in)")
    p.add_argument("--dry-run", action="store_true", help="make every read, write nothing, list the writes")
    a = p.parse_args(argv)
    path = root = None
    try:
        path = c.outside_toolbox(a.folder)
        root = c.state_root(a.state) if a.state else c.state_of(path)
        answers = c.read_answers(c.inside(path, a.answers)) if a.answers else None
        slug = a.agent_slug or c.settings(c.SKILL).get("enrichment_agent") or "deep-researcher"
        result = publish(c.client(), path, a.dry_run, answers, slug, root)
    except Exception as exc:
        reason = c.reason_of(exc, "meeting-publish")
        if path is not None and not a.dry_run and c.transient(exc):
            c.defer(root, *c.folder_ids(path), f"meeting-publish: {reason}")
        return c.fail(reason)
    return c.emit(result, c.OK if result["status"] in ("published", "waiting", "would_publish") else c.STOP)


if __name__ == "__main__":
    sys.exit(main())
