"""The meeting-processing scripts against an in-memory Portal, with the failures that matter.

A lookup by marker reconciles an interrupted attempt, a failure is one recording's, a re-run
creates nothing twice, an unreachable Portal defers rather than parks, the owner's answers on
the admin task are applied, a human edit to the note is never written over, and a dry run
writes nothing.

`FakePortal` answers the MCP tools these scripts call with the composite shapes the Portal
returns (`get(task, full)` nests the task under `task` beside `notes` and `comments`; a note's
`associations` sit on the record; `get_fellow_recording` carries `transcript_hash` beside
`recording`). Its task search matches the description and the title only, never
`source_reference`, as the Portal's does. All names and ids are invented.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _common as c  # noqa: E402
import meeting_acknowledge as mack  # noqa: E402
import meeting_existing as mex  # noqa: E402
import meeting_fetch as mfe  # noqa: E402
import meeting_pending as mpe  # noqa: E402
import meeting_publish as mpu  # noqa: E402
import meeting_skip as msk  # noqa: E402

OWNER = "44444444-0000-4000-8000-000000000001"
SAM = "44444444-0000-4000-8000-000000000002"
DOMAIN = "55555555-0000-4000-8000-000000000001"
ACME = "66666666-0000-4000-8000-000000000001"
EXISTING_TASK = "77777777-0000-4000-8000-000000000001"
OWNER_EMAIL = "owner@example.com"
SINCE = "2026-09-01T00:00:00Z"
RELAYED = "The owner's answer, relayed by the runner:"

REC_A = "a1000000-0000-4000-8000-00000000000a"
REC_B = "a2000000-0000-4000-8000-00000000000b"
REC_C = "a3000000-0000-4000-8000-00000000000c"
EVT_A = "e1000000-0000-4000-8000-00000000000a"
EVT_B = "e2000000-0000-4000-8000-00000000000b"
NOTE_A = "b1000000-0000-4000-8000-00000000000a"
NOTE_B = "b2000000-0000-4000-8000-00000000000b"
TEMPLATE = "# Talking Points\n(The things to talk about)\n\n# Action Items\n(What came out of this meeting?)\n\n"

SEGMENTS = [
    {"start": 4.4, "end": 5.0, "speaker": "Dana Park", "text": "All right, let's start."},
    {"start": 6.0, "end": 19.0, "speaker": "Sam Ortiz", "text": "I'll send the revised forecast by Friday."},
    {"start": 20.0, "end": 30.0, "speaker": "Dana Park", "text": "Good. We also agreed to move the close to Thursday."},
]


@pytest.fixture(autouse=True)
def owner_settings(tmp_path, monkeypatch):
    """Invented owner settings, so no test reads the real settings file."""
    path = tmp_path / "settings.toml"
    path.write_text(f'[meeting-scheduled-worker]\nsince = "{SINCE}"\nrelayed_answer_head = "{RELAYED}"\n')
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(path))
    monkeypatch.delenv("MEETING_PROCESSING_STATE", raising=False)
    monkeypatch.delenv(c.DRY_RUN_ENV, raising=False)


class Result:
    def __init__(self, exit_code, output, err):
        self.exit_code, self.output, self.err = exit_code, output, err


@pytest.fixture
def cli(capsys):
    """Run one script's main with arguments; its exit code, stdout and stderr."""
    def run(module, args):
        capsys.readouterr()
        code = module.main([str(a) for a in args])
        out = capsys.readouterr()
        return Result(code, out.out, out.err)
    return run


def pending(portal, state, **kw):
    kw.setdefault("since", SINCE)
    return mpe.pending(portal, state, **kw)


class Lost(Exception):
    """A write the Portal made whose answer never came back."""


class FakePortal:
    def __init__(self, owner="local", runs=0):
        self.owner, self.runs = owner, runs
        self.clock = 0
        self.recordings: dict = {}
        self.events: dict = {}
        self.notes: dict = {}
        self.tasks: dict = {}
        self.contacts = {OWNER: {"id": OWNER, "full_name": "Dana Park"},
                         SAM: {"id": SAM, "full_name": "Sam Ortiz"}}
        self.companies = {ACME: {"id": ACME, "name": "Acme Components"}}
        self.domains = {DOMAIN: {"id": DOMAIN, "name": "Clients"}}
        self.profiles = [{"slug": "deep-researcher", "is_active": True}]
        self.writes: list = []
        self.fail: dict = {}  # tool -> "lost" | "error" | "unreachable"
        self.ids = 0
        self.comments: dict = {}  # task id -> [comment]

    # ---------------------------------------------------------------- set-up

    def stamp(self) -> str:
        self.clock += 1
        return (datetime(2026, 10, 2, tzinfo=timezone.utc) + timedelta(seconds=self.clock)).isoformat()

    def new_id(self) -> str:
        self.ids += 1
        return f"99999999-0000-4000-8000-{self.ids:012d}"

    def add_recording(self, rid, eid, nid, started, segments=SEGMENTS, ended=None, note_content=TEMPLATE,
                      title="Weekly status"):
        self.recordings[rid] = {"id": rid, "calendar_event_id": eid, "note_id": nid, "started_at": started,
                                "ended_at": ended, "match_method": "ical_uid", "match_confidence": 1.0,
                                "transcript": {"speech_segments": [dict(s) for s in segments]},
                                "updated_at": self.stamp(), "processed_hash": None, "processed_at": None}
        if eid and eid not in self.events:
            self.events[eid] = {"id": eid, "title": title, "start_time": started, "end_time": started,
                                "start_local": started, "organizer_email": "owner@example.com", "company_id": None,
                                "meeting_url": "https://join.example/secret"}
        if nid and nid not in self.notes:
            self.notes[nid] = {"id": nid, "title": title, "content": note_content, "updated_at": self.stamp(),
                               "calendar_event_id": eid, "associations": [
                                   {"id": self.new_id(), "entity_type": "calendar_event", "entity_id": eid}]}

    def add_comment(self, task_id, body, email=OWNER_EMAIL, after_seconds=1):
        """A comment on a task, stamped after the real clock (the questions are stamped with it)."""
        at = (datetime.now(timezone.utc) + timedelta(seconds=after_seconds)).isoformat()
        c = {"id": self.new_id(), "author_name": "Dana Park", "author_email": email, "body": body,
             "created_at": at, "updated_at": at}
        self.comments.setdefault(task_id, []).append(c)
        return c

    def digest(self, rid) -> str:
        return c.queue_digest(self.recordings[rid]["transcript"]["speech_segments"])

    def add_task(self, **fields) -> dict:
        t = {"id": self.new_id(), "status": "TODO", "description": "", "created_at": self.stamp(),
             "updated_at": self.stamp(), "title": "", "source_reference": None, "owner_contact_id": None}
        t.update(fields)
        self.tasks[t["id"]] = t
        return t

    # ---------------------------------------------------------------- the client surface

    def whoami(self):
        return {"principal": {"contact_id": OWNER, "display_name": "Dana Park", "timezone": "America/Los_Angeles",
                              "org_member_id": "m-1", "primary_email": OWNER_EMAIL}, "inboxes": []}

    def list_entities(self, entity_type, filters=None, limit=200, max_pages=50):
        filters = filters or {}
        needle = str(filters.get("search") or "").lower()
        if entity_type == "task":
            # The Portal's task search does not match source_reference.
            rows = [t for t in self.tasks.values()
                    if needle in (str(t.get("description")) + str(t.get("title"))).lower()]
            if not filters.get("include_completed"):
                rows = [t for t in rows if t["status"] not in ("DONE", "CANCELLED")]
            return [dict(t) for t in rows]
        if entity_type == "contact":
            return [dict(c) for c in self.contacts.values() if needle in c["full_name"].lower()]
        return []

    def note_links(self, kind, uid):
        return [{"id": n["id"], "title": n["title"]} for n in self.notes.values()
                if any(a["entity_type"] == kind and a["entity_id"] == uid for a in n["associations"])]

    def call(self, tool, args=None):
        args = dict(args or {})
        mode = self.fail.pop(tool, None)
        if mode == "error":
            raise RuntimeError(f"portal {tool}: MCP tool failed")
        if mode == "unreachable":
            raise c.Unreachable(f"portal {tool}: HTTP 503")
        out = getattr(self, "t_" + tool)(args)
        if mode == "lost":
            raise Lost(f"portal {tool}: the answer was lost")
        return out

    def t_list_fellow_meetings(self, a):
        rows = sorted(self.recordings.values(), key=lambda r: r["started_at"], reverse=True)
        rows = [{"id": r["id"], "calendar_event_id": r["calendar_event_id"], "note_id": r["note_id"],
                 "started_at": r["started_at"], "match_method": r["match_method"],
                 "processed_hash": r["processed_hash"], "transcript_hash": self.digest(r["id"]),
                 "via_delegation": r.get("via_delegation", False)}
                for r in rows if r["started_at"] >= a["since"]]
        off, lim = a.get("offset") or 0, a.get("limit") or 50
        page = rows[off:off + lim]
        return {"owner": self.owner, "active_cloud_runs": self.runs, "meetings": page,
                "next_offset": off + lim if off + lim < len(rows) else None}

    def t_get_fellow_recording(self, a):
        r = self.recordings.get(a["recording_id"])
        if not r:
            return {"error": "not found"}
        siblings = [{"id": x["id"], "note_id": x["note_id"], "started_at": x["started_at"],
                     "transcript_hash": self.digest(x["id"]), "processed_hash": x["processed_hash"]}
                    for x in self.recordings.values() if x["calendar_event_id"] == r["calendar_event_id"]]
        return {"owner": self.owner, "active_cloud_runs": self.runs, "recording": json.loads(json.dumps(r)),
                "transcript_hash": self.digest(r["id"]), "recordings": siblings}

    def t_get(self, a):
        kind, uid = a["entity_type"], a["id_or_query"]
        if kind == "task":
            t = self.tasks.get(uid)
            if not t:
                return {"error": "No task found"}
            thread = [dict(c) for c in self.comments.get(uid, [])]
            return {"task": dict(t), "notes": self.note_links("task", uid), "comments": thread,
                    "comment_stats": {"total": len(thread), "returned": len(thread), "has_more": False}}
        if kind == "note":
            n = self.notes.get(uid)
            return json.loads(json.dumps(n)) if n else {"error": "No note found"}
        if kind == "calendar_event":
            e = self.events.get(uid)
            return {"event": dict(e), "attendees": [], "related_notes": [], "related_tasks": []} if e else {"error": "x"}
        table = {"contact": self.contacts, "company": self.companies, "domain": self.domains}.get(kind, {})
        rec = table.get(uid)
        return {kind: dict(rec)} if rec else {"error": f"No {kind} found matching '{uid}'"}

    def t_list_agent_profiles(self, a):
        return {"profiles": self.profiles}

    def t_create_task(self, a):
        self.writes.append(("create_task", a.get("source_reference")))
        t = self.add_task(**{k: v for k, v in a.items() if k not in ("assignees", "domain_id_or_name")},
                          domain_id=a.get("domain_id_or_name"), assignees=a.get("assignees") or [])
        return {"id": t["id"], "title": t["title"]}

    def t_update_task(self, a):
        self.writes.append(("update_task", a["id"], a.get("status")))
        t = self.tasks[a["id"]]
        t.update(a.get("fields") or {})
        if a.get("source_reference"):
            t["source_reference"] = a["source_reference"]
        if a.get("status"):
            t["status"] = a["status"]
        t["updated_at"] = self.stamp()
        return {"success": True}

    def t_update_note(self, a):
        n = self.notes[a["id"]]
        if a.get("fields"):
            self.writes.append(("update_note", a["id"]))
            if a.get("expected_updated_at") and a["expected_updated_at"] != n["updated_at"]:
                raise RuntimeError("portal update_note: version conflict")
            n.update(a["fields"])
        for assoc in a.get("add_associations") or []:
            self.writes.append(("add_association", assoc["entity_type"], assoc["entity_id"]))
            n["associations"].append({"id": self.new_id(), **assoc})
        n["updated_at"] = self.stamp()
        return {"success": True, "id": n["id"]}

    def t_complete_fellow_recording(self, a):
        self.writes.append(("complete_fellow_recording", a["recording_id"]))
        r = self.recordings[a["recording_id"]]
        t = self.tasks[a["task_id"]]
        n = self.notes[a["note_id"]]
        assert t["source_reference"] == c.admin_marker(a["recording_id"], a["transcript_digest"])
        assert t["status"] == "DONE"
        assert (a["expected_task_updated_at"], a["expected_note_updated_at"], a["expected_recording_updated_at"]) == (
            t["updated_at"], n["updated_at"], r["updated_at"])
        r["processed_hash"] = a["transcript_digest"]
        r["processed_at"] = self.stamp()
        return {"success": True}


# --------------------------------------------------------------------------- helpers

@pytest.fixture
def portal():
    p = FakePortal()
    p.add_recording(REC_A, EVT_A, NOTE_A, "2026-09-15T18:01:50+00:00", ended="2026-09-15T18:38:38+00:00")
    return p


@pytest.fixture
def state(tmp_path):
    return c.state_root(str(tmp_path / "state"))


def good_plan(p, rid=REC_A, actions=None, clarifications=None, enrichment=None, content="Summary.\n\nThe close moves to Thursday."):
    return {"recording_id": rid, "digest": p.digest(rid), "note_title": "Weekly status (2026-09-15)",
            "note_content": content,
            "summary_evidence": [{"segment": 2, "quote": "move the close to Thursday"}],
            "actions": actions if actions is not None else [
                {"title": "Send the revised forecast", "description": "Sam sends the revised forecast.",
                 "owner_contact_id": SAM, "domain_id": DOMAIN, "project_id": None, "existing_task_id": None,
                 "due_date": "2026-09-18", "disposition": "create",
                 "evidence": [{"segment": 1, "quote": "I'll send the revised forecast by Friday"}]},
                {"title": "Decide the board date", "description": "Raised, nobody took it.",
                 "owner_contact_id": None, "domain_id": None, "project_id": None, "existing_task_id": None,
                 "due_date": None, "disposition": "proposal",
                 "evidence": [{"segment": 0, "quote": "let's start"}]}],
            "clarifications": clarifications or [], "enrichment_refs": enrichment or [], "flags": []}


def prepare(p, state, rid=REC_A, plan=None, verdict="PASS"):
    """Existing, fetch, plan and a check record, as steps 3 to 7 leave a recording folder."""
    digest = p.digest(rid)
    folder = c.recording_dir(state, rid, digest)
    c.atomic_json(folder / "existing.json", mex.existing(p, rid, digest))
    fetched = mfe.fetch(p, rid, digest)
    assert fetched["status"] == "ok", fetched
    mfe.write(folder, fetched)
    plan = plan or good_plan(p, rid)
    c.atomic_json(folder / "plan.json", plan)
    check(folder, plan, verdict)
    return folder


def check(folder, plan, verdict="PASS"):
    """The checker's record for this plan against the source in the folder (step 7)."""
    source = json.loads((folder / "source.json").read_text())
    c.atomic_json(folder / "check.json", {"verdict": verdict, "recording_id": plan["recording_id"],
                                           "plan_hash": c.plan_hash(plan, source), "fixes": []})


def refetch(p, folder, rid=REC_A):
    """Step 4 of a later run: the same recording fetched again into its folder."""
    fetched = mfe.fetch(p, rid, p.digest(rid))
    mfe.write(folder, fetched)
    return mfe.earlier_check(folder, fetched)


def creates(p):
    return [w for w in p.writes if w[0] == "create_task"]


# --------------------------------------------------------------------------- markers and digests

def test_the_digest_and_the_markers():
    """The listed 16-hex digest hashes speaker and folded text."""
    segs = [{"speaker": "A", "text": "hello   world", "start": 1, "end": 2}]
    assert c.queue_digest(segs) == c.queue_digest([{"speaker": "A", "text": "hello world"}])
    assert len(c.queue_digest(segs)) == 16 and len(c.full_hash(segs)) == 64
    assert c.admin_marker(REC_A, "0123456789abcdef") == f"meeting-processing:recording:{REC_A}:0123456789abcdef"
    assert c.action_marker(EVT_A, "ab" * 32, 3) == f"local-meeting:{EVT_A}:{'ab' * 8}:3"


# --------------------------------------------------------------------------- meeting-pending

class TestPending:
    def test_oldest_first_and_cut_to_the_limit(self, portal, state):
        portal.add_recording(REC_B, EVT_B, NOTE_B, "2026-09-16T10:00:00+00:00")
        portal.add_recording(REC_C, None, None, "2026-09-14T10:00:00+00:00")
        out = pending(portal, state, limit=1)
        assert out["status"] == "ok"
        assert [r["recording_id"] for r in out["recordings"]] == [REC_A]
        assert out["remaining_after_this_run"] == 1
        assert [r["recording_id"] for r in out["unmatched"]] == [REC_C]

    def test_processed_recordings_are_left_out(self, portal, state):
        portal.recordings[REC_A]["processed_hash"] = portal.digest(REC_A)
        assert pending(portal, state)["status"] == "nothing"

    def test_a_principals_recording_seen_through_a_delegation_is_left_out(self, portal, state):
        portal.recordings[REC_A]["via_delegation"] = True
        assert pending(portal, state)["status"] == "nothing"

    def test_before_the_cut_off_is_left_out(self, portal, state):
        assert pending(portal, state, since="2026-09-20T00:00:00Z")["status"] == "nothing"

    @pytest.mark.parametrize("owner,runs", [("cloud", 0), ("local", 2)])
    def test_not_the_local_owner(self, owner, runs, state):
        p = FakePortal(owner=owner, runs=runs)
        p.add_recording(REC_A, EVT_A, NOTE_A, "2026-09-15T18:00:00+00:00")
        out = pending(p, state)
        assert out["status"] == "not_local_owner" and out["recordings"] == []

    def test_a_failing_recording_never_holds_the_queue(self, portal, state):
        """Skipped, it is deferred; tried three times, it is parked; the others go ahead."""
        portal.add_recording(REC_B, EVT_B, NOTE_B, "2026-09-16T10:00:00+00:00")
        d = portal.digest(REC_A)
        c.update_ledger(state, REC_A, d, attempt=True, reason="the checker failed twice")
        now = c.now_utc()
        out = pending(portal, state, limit=1, now=now)
        assert [r["recording_id"] for r in out["recordings"]] == [REC_B]
        assert [r["recording_id"] for r in out["deferred"]] == [REC_A]
        later = pending(portal, state, limit=1, now=now + timedelta(hours=7))
        assert [r["recording_id"] for r in later["recordings"]] == [REC_A]
        c.update_ledger(state, REC_A, d, attempt=True)
        c.update_ledger(state, REC_A, d, attempt=True)
        parked = pending(portal, state, limit=1, now=now + timedelta(hours=30))
        assert [r["recording_id"] for r in parked["parked"]] == [REC_A]
        assert [r["recording_id"] for r in parked["recordings"]] == [REC_B]

    def test_permanent_and_waiting_entries(self, portal, state):
        d = portal.digest(REC_A)
        c.update_ledger(state, REC_A, d, permanent=True, reason="over the cap")
        assert pending(portal, state)["counts"]["skipped_known"] == 1
        c.clear_ledger(state, REC_A)
        task = portal.add_task(status="WAITING")
        c.update_ledger(state, REC_A, d, waiting_task_id=task["id"], reason="waiting")
        assert pending(portal, state)["counts"]["waiting"] == 1
        task["status"] = "TODO"  # the owner answered in the Portal
        assert [r["recording_id"] for r in pending(portal, state)["recordings"]] == [REC_A]

    def test_precheck_prints_one_line(self, portal, state, monkeypatch, cli):
        monkeypatch.setattr(c, "client", lambda: portal)
        out = cli(mpe, ["--precheck", "--state", str(state)])
        assert out.exit_code == 0 and out.output.splitlines()[0] == "WORK: 1 recordings to process"
        portal.recordings[REC_A]["processed_hash"] = portal.digest(REC_A)
        out = cli(mpe, ["--precheck", "--state", str(state)])
        assert out.output.strip() == "NOTHING"

    def test_the_state_folder_is_never_inside_the_toolbox(self):
        with pytest.raises(Exception):
            c.state_root(str(c.toolbox_root() / "state"))


# --------------------------------------------------------------------------- meeting-existing

class TestExisting:
    def test_a_recording_with_nothing_written_is_new(self, portal):
        """An earlier create failed and nothing exists. The lookup says go, never hold."""
        out = mex.existing(portal, REC_A, portal.digest(REC_A))
        assert out["stage"] == "new" and out["admin_task"] is None

    @pytest.mark.parametrize("status,stage", [("TODO", "resume"), ("IN_PROGRESS", "resume"), ("DONE", "published"),
                                              ("WAITING", "waiting"), ("CANCELLED", "cancelled")])
    def test_the_admin_task_decides(self, portal, status, stage):
        d = portal.digest(REC_A)
        portal.add_task(source_reference=c.admin_marker(REC_A, d), status=status,
                        description=c.admin_marker(REC_A, d))
        assert mex.existing(portal, REC_A, d)["stage"] == stage

    def waiting_task(self, portal):
        d = portal.digest(REC_A)
        asked = (c.now_utc() - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return portal.add_task(source_reference=c.admin_marker(REC_A, d), status="WAITING",
                               description=c.admin_marker(REC_A, d) + "\n\n" + c.QUESTIONS_HEAD.format(at=asked)
                               + "\n1. Who owns the board date?")

    def test_a_comment_from_owner_resumes_a_waiting_task(self, portal):
        task = self.waiting_task(portal)
        d = portal.digest(REC_A)
        assert mex.existing(portal, REC_A, d)["stage"] == "waiting"
        portal.add_comment(task["id"], "Working on it.\n\n(posted by weekly-reporter, an agent)")
        portal.add_comment(task["id"], "1) Sam", email="someone.else@example.com")
        portal.add_comment(task["id"], "Old answer", after_seconds=-3600)  # before the questions
        assert mex.existing(portal, REC_A, d)["stage"] == "waiting"  # not the owner's, or not new
        portal.add_comment(task["id"], "1) Sam owns it")
        out = mex.existing(portal, REC_A, d)
        assert out["stage"] == "resume" and out["answered"] is True
        assert "1) Sam owns it" in out["answers_text"] and "weekly-reporter" not in out["answers_text"]

    def test_moving_a_waiting_task_to_todo_resumes_it_with_its_description(self, portal):
        task = self.waiting_task(portal)
        task["status"] = "TODO"
        task["description"] += "\nAnswer: Sam."
        out = mex.existing(portal, REC_A, portal.digest(REC_A))
        assert out["stage"] == "resume" and out["answered"] is True and "Answer: Sam." in out["answers_text"]

    def test_duplicate_admin_tasks_are_flagged_not_fatal(self, portal):
        d = portal.digest(REC_A)
        first = portal.add_task(source_reference=c.admin_marker(REC_A, d), description=c.admin_marker(REC_A, d))
        portal.add_task(source_reference=c.admin_marker(REC_A, d), description=c.admin_marker(REC_A, d))
        out = mex.existing(portal, REC_A, d)
        assert out["stage"] == "resume" and out["admin_task"]["id"] == first["id"] and out["flags"]

    def test_acknowledged_and_changed(self, portal):
        d = portal.digest(REC_A)
        assert mex.existing(portal, REC_A, "0" * 16)["stage"] == "changed"
        portal.recordings[REC_A]["processed_hash"] = d
        assert mex.existing(portal, REC_A, d)["stage"] == "acknowledged"

    def test_earlier_action_tasks_are_listed_by_index(self, portal):
        fhash = c.full_hash(SEGMENTS)
        t = portal.add_task(source_reference=c.action_marker(EVT_A, fhash, 0), title="Send the revised forecast",
                            description=f"Meeting: portal://calendar_event/{EVT_A}")
        out = mex.existing(portal, REC_A, portal.digest(REC_A))
        assert out["existing_actions"]["0"][0]["id"] == t["id"]

    def test_a_failed_lookup_still_counts_an_attempt(self, portal, state, monkeypatch, cli):
        monkeypatch.setattr(c, "client", lambda: portal)
        portal.fail["get_fellow_recording"] = "error"
        d = portal.digest(REC_A)
        out = cli(mex, [REC_A, "--digest", d, "--state", str(state)])
        assert out.exit_code == 2
        assert c.load_ledger(state)[c.ledger_key(REC_A, d)]["attempts"] == 1

    def test_an_unreachable_portal_defers_without_counting_an_attempt(self, portal, state, monkeypatch, cli):
        monkeypatch.setattr(c, "client", lambda: portal)
        d = portal.digest(REC_A)
        for _ in range(c.MAX_ATTEMPTS + 1):
            portal.fail["get_fellow_recording"] = "unreachable"
            out = cli(mex, [REC_A, "--digest", d, "--state", str(state)])
            assert out.exit_code == 2
        entry = c.load_ledger(state)[c.ledger_key(REC_A, d)]
        assert entry["attempts"] == 0 and entry["deferred_at"] and "HTTP 503" in entry["last_reason"]
        listed = pending(portal, state)
        assert [r["recording_id"] for r in listed["deferred"]] == [REC_A] and listed["parked"] == []
        later = pending(portal, state, now=c.now_utc() + timedelta(hours=7))
        assert [r["recording_id"] for r in later["recordings"]] == [REC_A]

    def test_out_must_be_inside_the_recording_folder(self, portal, state, tmp_path, monkeypatch, cli):
        monkeypatch.setattr(c, "client", lambda: portal)
        d = portal.digest(REC_A)
        for bad in (str(tmp_path / "elsewhere.json"), str(c.recording_dir(state, REC_A, d) / ".." / "x.json")):
            out = cli(mex, [REC_A, "--digest", d, "--state", str(state), "--out", bad])
            assert out.exit_code == 2 and "outside the recording folder" in out.output
            assert not Path(bad).exists()
        good = c.recording_dir(state, REC_A, d) / "existing.json"
        out = cli(mex, [REC_A, "--digest", d, "--state", str(state), "--out", str(good)])
        assert out.exit_code == 0 and json.loads(good.read_text())["stage"] == "new"

    def test_a_dry_run_counts_nothing_and_writes_nothing(self, portal, state, monkeypatch, cli):
        monkeypatch.setattr(c, "client", lambda: portal)
        d = portal.digest(REC_A)
        out = cli(mex, [REC_A, "--digest", d, "--state", str(state), "--dry-run"])
        assert out.exit_code == 0 and json.loads(out.output)["stage"] == "new"
        portal.fail["get_fellow_recording"] = "error"
        out = cli(mex, [REC_A, "--digest", d, "--state", str(state), "--dry-run"])
        assert out.exit_code == 2
        assert c.load_ledger(state) == {} and portal.writes == []


# --------------------------------------------------------------------------- meeting-fetch

class TestFetch:
    def test_exact_recording_into_the_folder(self, portal, state):
        d = portal.digest(REC_A)
        out = mfe.fetch(portal, REC_A, d)
        assert out["status"] == "ok" and out["segment_count"] == 3
        assert "meeting_url" not in out["event"]  # no join secrets to the model
        assert out["speaker_matches"]["Dana Park"]["exact"] == OWNER
        assert out["speaker_matches"]["Sam Ortiz"]["exact"] == SAM
        files = mfe.write(c.recording_dir(state, REC_A, d), out)
        lines = Path(files["transcript"]).read_text().splitlines()
        assert "[1] 00:06 Sam Ortiz: I'll send the revised forecast by Friday." in lines

    def test_over_the_cap_is_skipped(self, portal):
        portal.recordings[REC_A]["ended_at"] = "2026-09-15T21:30:00+00:00"
        out = mfe.fetch(portal, REC_A, portal.digest(REC_A))
        assert out["status"] == "over_cap"

    def test_no_note_and_changed(self, portal):
        d = portal.digest(REC_A)
        assert mfe.fetch(portal, REC_A, "f" * 16)["status"] == "changed"
        portal.recordings[REC_A]["note_id"] = None
        assert mfe.fetch(portal, REC_A, d)["status"] == "no_note"

    def test_generic_labels_are_flagged(self):
        q = mfe.quality([{"speaker": "Speaker 2", "text": "x"}, {"speaker": "", "text": "y"}], invited=3)
        assert any("generic speaker labels" in f for f in q["flags"])
        assert any("no speaker" in f for f in q["flags"])

    def test_over_cap_is_marked_permanent(self, portal, state, monkeypatch, cli):
        monkeypatch.setattr(c, "client", lambda: portal)
        portal.recordings[REC_A]["ended_at"] = "2026-09-15T22:30:00+00:00"
        d = portal.digest(REC_A)
        out = cli(mfe, [REC_A, "--digest", d, "--state", str(state)])
        assert out.exit_code == 3 and json.loads(out.output)["status"] == "over_cap"
        assert c.load_ledger(state)[c.ledger_key(REC_A, d)]["permanent"] is True

    def test_a_dry_run_marks_nothing_and_writes_nothing(self, portal, state, monkeypatch, cli):
        monkeypatch.setattr(c, "client", lambda: portal)
        d = portal.digest(REC_A)
        out = cli(mfe, [REC_A, "--digest", d, "--state", str(state), "--dry-run"])
        assert out.exit_code == 0 and json.loads(out.output)["earlier_check"] is False
        portal.recordings[REC_A]["ended_at"] = "2026-09-15T22:30:00+00:00"
        out = cli(mfe, [REC_A, "--digest", d, "--state", str(state), "--dry-run"])
        assert out.exit_code == 3 and json.loads(out.output)["status"] == "over_cap"
        assert c.load_ledger(state) == {} and portal.writes == []

    def test_an_earlier_check_holds_only_for_the_same_note(self, portal, state):
        folder = prepare(portal, state)
        assert refetch(portal, folder) is True
        portal.notes[NOTE_A]["content"] += "\nThe owner's own line."
        portal.notes[NOTE_A]["updated_at"] = portal.stamp()
        assert refetch(portal, folder) is False


# --------------------------------------------------------------------------- meeting-validate

class TestValidate:
    def source(self, portal):
        return mfe.fetch(portal, REC_A, portal.digest(REC_A))

    def test_a_good_plan(self, portal):
        assert c.validate(good_plan(portal), self.source(portal)) == []

    def test_a_quote_not_in_its_segment(self, portal):
        plan = good_plan(portal)
        plan["actions"][0]["evidence"] = [{"segment": 0, "quote": "I'll send the revised forecast"}]
        assert any("quote not found in segment 0" in e for e in c.validate(plan, self.source(portal)))

    def test_a_new_task_needs_owner_and_domain(self, portal):
        plan = good_plan(portal)
        plan["actions"][0]["owner_contact_id"] = None
        assert any("verified owner and domain" in e for e in c.validate(plan, self.source(portal)))

    def test_reserved_strings_and_bad_clarifications(self, portal):
        plan = good_plan(portal, content="x <!-- local-recording-section:abc -->", clarifications=["a bare string"])
        errors = c.validate(plan, self.source(portal))
        assert any("reserved" in e for e in errors) and any("clarification 0" in e for e in errors)

    def test_an_earlier_task_must_be_kept_at_its_index(self, portal):
        existing = {"existing_actions": {"0": [{"id": EXISTING_TASK, "title": "Something else"}]}}
        errors = c.validate(good_plan(portal), self.source(portal), existing)
        assert any("an earlier attempt created task" in e for e in errors)
        plan = good_plan(portal)
        plan["actions"][1].update(disposition="link_existing", existing_task_id=EXISTING_TASK)
        assert c.validate(plan, self.source(portal), existing) == []


# --------------------------------------------------------------------------- meeting-publish

class TestPublish:
    def test_publishes_then_acknowledges(self, portal, state):
        folder = prepare(portal, state)
        out = mpu.publish(portal, folder)
        assert out["status"] == "published" and out["acknowledged"] is True
        admin = portal.tasks[out["admin_task_id"]]
        assert admin["status"] == "DONE" and admin["source_reference"] == c.admin_marker(REC_A, portal.digest(REC_A))
        assert admin.get("assignees") == []  # the job's record, nobody's queue
        [action] = [portal.tasks[t] for t in out["tasks_created"]]
        assert action["owner_contact_id"] == SAM and action["due_date"] == "2026-09-18"
        note = portal.notes[NOTE_A]
        assert note["title"] == "Weekly status (2026-09-15)"
        assert f"](portal://task/{action['id']})" in note["content"]
        assert "Decide the board date (proposal)" in note["content"]
        assert c.NOTE_MARK.format(rid=REC_A, digest=portal.digest(REC_A)) in note["content"]
        assert portal.recordings[REC_A]["processed_hash"] == portal.digest(REC_A)
        order = [w[0] for w in portal.writes]
        assert order.index("update_note") < order.index("update_task") < order.index("complete_fellow_recording")

    def test_a_second_run_creates_nothing(self, portal, state):
        folder = prepare(portal, state)
        mpu.publish(portal, folder)
        portal.recordings[REC_A]["processed_hash"] = None  # the acknowledgment answer was lost
        before = len(creates(portal))
        again = mpu.publish(portal, folder)
        assert again["status"] == "published" and len(creates(portal)) == before

    def test_a_dry_run_writes_nothing(self, portal, state):
        folder = prepare(portal, state)
        out = mpu.publish(portal, folder, dry_run=True)
        assert out["status"] == "would_publish" and portal.writes == []
        kinds = [w.get("would") for w in out["writes"]]
        assert kinds.count("create_task") == 2 and "update_note" in kinds and "complete_fellow_recording" in kinds
        assert (folder / "note-preview.md").is_file() and (folder / "publish-dry-run.json").is_file()

    def test_a_failed_admin_create_is_reconciled_next_run(self, portal, state):
        """The admin create fails outright: this recording stops with an error, the next
        attempt's lookup finds nothing and creates it once. No intent file, no hold."""
        folder = prepare(portal, state)
        portal.fail["create_task"] = "error"
        with pytest.raises(c.Stop, match="the next run creates it"):
            mpu.publish(portal, folder)
        assert creates(portal) == []
        out = mpu.publish(portal, folder)
        assert out["status"] == "published"
        markers = [w[1] for w in creates(portal)]
        assert markers.count(c.admin_marker(REC_A, portal.digest(REC_A))) == 1

    def test_a_lost_create_answer_is_found_by_marker(self, portal, state):
        folder = prepare(portal, state)
        portal.fail["create_task"] = "lost"
        out = mpu.publish(portal, folder)
        assert out["status"] == "published"
        assert len(creates(portal)) == 2 and any("answer was lost" in f for f in out["flags"])

    def test_an_interrupted_attempt_resumes_without_duplicates(self, portal, state):
        """The run died after the admin task and the action task were created."""
        folder = prepare(portal, state)
        portal.fail["update_note"] = "error"
        with pytest.raises(RuntimeError):
            mpu.publish(portal, folder)
        assert len(creates(portal)) == 2
        folder = prepare(portal, state)  # the next run: existing, fetch, the same plan
        out = mpu.publish(portal, folder)
        assert out["status"] == "published" and len(creates(portal)) == 2 and out["tasks_reused"]

    def test_one_recording_failing_leaves_the_next_untouched(self, portal, state):
        portal.add_recording(REC_B, EVT_B, NOTE_B, "2026-09-16T10:00:00+00:00")
        a = prepare(portal, state, REC_A)
        b = prepare(portal, state, REC_B, plan=good_plan(portal, REC_B, actions=[]))
        portal.notes[NOTE_A]["content"] += "\nA human added this."  # makes A refuse
        assert mpu.publish(portal, a)["code"] == "NOTE_EDITED"
        assert creates(portal) == [] and portal.writes == []  # refused before any task was created
        assert mpu.publish(portal, b)["status"] == "published"
        assert "A human added this." in portal.notes[NOTE_A]["content"]

    def test_refuses_an_unchecked_or_changed_plan(self, portal, state):
        folder = prepare(portal, state, verdict="FAIL")
        assert mpu.publish(portal, folder)["code"] == "CHECK_FAILED"
        folder = prepare(portal, state)
        plan = json.loads((folder / "plan.json").read_text())
        plan["note_content"] += " Edited after the check."
        c.atomic_json(folder / "plan.json", plan)
        assert mpu.publish(portal, folder)["code"] == "CHANGED_SINCE_CHECK"
        assert portal.writes == []

    def test_refuses_when_processing_moves_to_the_cloud(self, portal, state):
        folder = prepare(portal, state)
        portal.owner = "cloud"
        out = mpu.publish(portal, folder)
        assert out["code"] == "NOT_LOCAL_OWNER" and portal.writes == []

    def test_refuses_a_changed_transcript(self, portal, state):
        folder = prepare(portal, state)
        portal.recordings[REC_A]["transcript"]["speech_segments"][0]["text"] = "Something else."
        assert mpu.publish(portal, folder)["code"] == "TRANSCRIPT_CHANGED"

    def test_a_task_carrying_the_marker_for_another_action_is_a_conflict(self, portal, state):
        folder = prepare(portal, state)
        portal.add_task(source_reference=c.action_marker(EVT_A, c.full_hash(SEGMENTS), 0), title="Unrelated",
                        description=f"portal://calendar_event/{EVT_A}")
        assert mpu.publish(portal, folder)["code"] == "MARKER_CONFLICT"

    def test_questions_leave_it_waiting_and_unacknowledged(self, portal, state):
        plan = good_plan(portal, clarifications=[{"question": "Who owns the board date?", "options": ["Dana", "Sam"]}])
        folder = prepare(portal, state, plan=plan)
        out = mpu.publish(portal, folder)
        assert out["status"] == "waiting" and out["questions"][0]["question"] == "Who owns the board date?"
        assert portal.tasks[out["admin_task_id"]]["status"] == "WAITING"
        assert portal.recordings[REC_A]["processed_hash"] is None
        assert "## Clarifications needed" in portal.notes[NOTE_A]["content"]
        assert len(out["tasks_created"]) == 1  # the unblocked action is already written
        admin = portal.tasks[out["admin_task_id"]]
        assert c.asked_at(admin["description"]) is not None  # the questions sit on the admin task
        assert "1. Who owns the board date? Options: Dana; Sam." in admin["description"]
        assert admin["description"].startswith(c.admin_marker(REC_A, portal.digest(REC_A)))
        assert mpu.publish(portal, folder)["code"] == "WAITING"

    def test_owner_answers_on_the_admin_task_and_the_next_run_applies_them(self, portal, state, monkeypatch, cli):
        """The skill's own path: run 1 leaves the questions on the WAITING admin task; the owner
        comments; run 2's meeting-existing files his comment as answers.md and sets the old plan
        aside; meeting-fetch says the earlier check no longer holds; the analyst runs again with
        the answers; meeting-publish writes the new plan and completes the recording."""
        monkeypatch.setattr(c, "client", lambda: portal)
        d = portal.digest(REC_A)
        asking = good_plan(portal, clarifications=[{"question": "Who owns the board date?"}])
        folder = prepare(portal, state, plan=asking)
        first = mpu.publish(portal, folder)
        assert first["status"] == "waiting"
        args = [REC_A, "--digest", d, "--state", str(state), "--out", str(folder / "existing.json")]
        out = cli(mex, args)  # run 2, before the owner answers
        assert out.exit_code == 3 and json.loads(out.output)["stage"] == "waiting"
        assert pending(portal, state)["counts"]["waiting"] == 1

        portal.add_comment(first["admin_task_id"], "1) Sam owns the board date")
        assert [r["recording_id"] for r in pending(portal, state)["recordings"]] == [REC_A]
        out = cli(mex, args)  # run 3: step 3
        found = json.loads(out.output)
        assert out.exit_code == 0 and found["stage"] == "resume" and found["answered"] is True
        assert found["set_aside"] == ["plan-1.json", "check-1.json"]
        assert "1) Sam owns the board date" in (folder / "answers.md").read_text()
        assert not (folder / "plan.json").exists()
        assert refetch(portal, folder) is False  # step 4: no shortcut, the analyst runs

        # The old plan, still asking, is refused even when checked again against the fresh note.
        c.atomic_json(folder / "plan.json", asking)
        check(folder, asking)
        answers = (folder / "answers.md").read_text()
        assert mpu.publish(portal, folder, answers=answers)["code"] == "ANSWERS_UNAPPLIED"

        answered = good_plan(portal)  # step 5: the analyst, given answers.md
        answered["note_content"] += "\n\nThe board date is Sam's (the owner, after the meeting)."
        c.atomic_json(folder / "plan.json", answered)
        check(folder, answered)
        out = mpu.publish(portal, folder, answers=answers)
        assert out["status"] == "published" and out["acknowledged"] is True
        note = portal.notes[NOTE_A]["content"]
        assert "## Clarification received" in note and "1) Sam owns the board date" in note
        assert "## Clarifications needed" not in note
        assert portal.tasks[first["admin_task_id"]]["status"] == "DONE"
        assert len(creates(portal)) == 2  # the admin task and the one action, each once

    def test_a_note_edited_before_publish_is_never_overwritten_by_the_old_plan(self, portal, state):
        """Run 1 refuses NOTE_EDITED; run 2 refetches, and the old plan,
        checked against the note before the edit, must not be written over it."""
        folder = prepare(portal, state)
        portal.notes[NOTE_A]["content"] += "\nThe owner's own line."
        portal.notes[NOTE_A]["updated_at"] = portal.stamp()
        assert mpu.publish(portal, folder)["code"] == "NOTE_EDITED"
        assert portal.writes == []
        c.atomic_json(folder / "existing.json", mex.existing(portal, REC_A, portal.digest(REC_A)))  # run 2
        assert refetch(portal, folder) is False
        assert mpu.publish(portal, folder)["code"] == "CHANGED_SINCE_CHECK"
        assert portal.writes == [] and portal.notes[NOTE_A]["content"].endswith("The owner's own line.")
        assert c.load_ledger(state) == {}  # cured by fetching again, so never marked permanent

    def test_a_note_edited_after_this_job_wrote_it_is_kept(self, portal, state):
        """Run 1 writes the note but setting the admin task DONE fails;
        the owner edits the note; run 2 refetches and analyses again, and its plan is refused
        rather than written over his edit."""
        folder = prepare(portal, state)
        portal.fail["update_task"] = "error"
        with pytest.raises(RuntimeError):
            mpu.publish(portal, folder)
        assert json.loads((folder / "publish.json").read_text())["notes_written"]  # recorded before the write
        assert c.NOTE_MARK.format(rid=REC_A, digest=portal.digest(REC_A)) in portal.notes[NOTE_A]["content"]
        portal.notes[NOTE_A]["content"] += "\nThe owner's correction."
        portal.notes[NOTE_A]["updated_at"] = portal.stamp()
        before = list(portal.writes)
        assert refetch(portal, folder) is False
        assert mpu.publish(portal, folder)["code"] == "CHANGED_SINCE_CHECK"
        plan = good_plan(portal, content="Summary, analysed again.\n\nThe close moves to Thursday.")
        c.atomic_json(folder / "plan.json", plan)
        check(folder, plan)
        out = mpu.publish(portal, folder)
        assert out["code"] == "NOTE_EDITED" and "removes the marker line" in out["reason"]
        assert out["permanent"] is True and "marked permanent" in out["reason"] and "--clear" in out["reason"]
        assert c.load_ledger(state)[c.ledger_key(REC_A, portal.digest(REC_A))]["permanent"] is True
        assert pending(portal, state)["counts"]["skipped_known"] == 1  # no slot spent on it again
        assert portal.notes[NOTE_A]["content"].endswith("The owner's correction.")
        assert [w for w in portal.writes[len(before):] if w[0] != "create_task"] == []
        assert len(creates(portal)) == 2  # nothing created twice

    def test_a_rerun_over_its_own_note_is_not_an_edit(self, portal, state):
        """The control for (b): with no human edit, run 2 analyses again and finishes."""
        folder = prepare(portal, state)
        portal.fail["update_task"] = "error"
        with pytest.raises(RuntimeError):
            mpu.publish(portal, folder)
        assert refetch(portal, folder) is False
        plan = good_plan(portal, content="Summary, analysed again.\n\nThe close moves to Thursday.")
        c.atomic_json(folder / "plan.json", plan)
        check(folder, plan)
        out = mpu.publish(portal, folder)
        assert out["status"] == "published" and "analysed again" in portal.notes[NOTE_A]["content"]

    def test_answers_must_be_inside_the_folder_and_short(self, portal, state, tmp_path, monkeypatch, cli):
        monkeypatch.setattr(c, "client", lambda: portal)
        folder = prepare(portal, state)
        outside = tmp_path / "answers.md"
        outside.write_text("1) Sam")
        out = cli(mpu, [str(folder), "--answers", str(outside), "--dry-run"])
        assert out.exit_code == 2 and "outside the recording folder" in out.output
        (folder / "answers.md").write_text("x" * (c.MAX_ANSWERS_CHARS + 1))
        out = cli(mpu, [str(folder), "--answers", str(folder / "answers.md"), "--dry-run"])
        assert out.exit_code == 2 and "characters" in out.output
        assert portal.writes == []

    def test_every_created_task_is_found_by_its_lookup(self, portal, state):
        """The live task search ignores source_reference, so each create must put the id its
        lookup searches for into the description (common.tasks_mentioning)."""
        made = []
        create = portal.t_create_task
        portal.t_create_task = lambda a: (made.append(a), create(a))[1]
        plan = good_plan(portal, enrichment=[f"portal://contact/{SAM}", f"portal://company/{ACME}"])
        assert mpu.publish(portal, prepare(portal, state, plan=plan))["status"] == "published"
        assert len(made) == 4
        for args in made:
            ref = args["source_reference"]
            needles = [ref.rsplit(":", 1)[1]] if ref.startswith("context-enrichment:") else [REC_A, EVT_A]
            assert any(n in args["description"] for n in needles), ref
            assert c.with_marker(c.tasks_mentioning(portal, *needles), ref), ref

    def test_a_malformed_profile_listing_skips_enrichment(self, portal, state):
        portal.t_list_agent_profiles = lambda a: ["not", "a", "dict"]
        out = mpu.publish(portal, prepare(portal, state, plan=good_plan(portal, enrichment=[f"portal://contact/{SAM}"])))
        assert out["status"] == "published" and any("enrichment hand-offs skipped" in f for f in out["flags"])

    def test_a_link_to_an_existing_task(self, portal, state):
        task = portal.add_task(title="Board pack", status="TODO")
        plan = good_plan(portal)
        plan["actions"][1].update(disposition="link_existing", existing_task_id=task["id"])
        out = mpu.publish(portal, prepare(portal, state, plan=plan))
        assert out["tasks_linked"] == [task["id"]] and portal.tasks[task["id"]]["status"] == "TODO"

    def test_enrichment_is_created_then_extended(self, portal, state):
        plan = good_plan(portal, enrichment=[f"portal://contact/{SAM}"])
        out = mpu.publish(portal, prepare(portal, state, plan=plan))
        [e] = out["enrichment"]
        made = portal.tasks[e["task_id"]]
        assert e["outcome"] == "created" and made["assignees"] == ["deep-researcher"]
        assert made["source_reference"] == c.enrichment_marker("contact", SAM)
        made["status"] = "DONE"
        portal.add_recording(REC_B, EVT_B, NOTE_B, "2026-09-16T10:00:00+00:00",
                             segments=SEGMENTS + [{"speaker": "Sam Ortiz", "text": "One more thing."}])
        plan_b = good_plan(portal, REC_B, enrichment=[f"portal://contact/{SAM}"])
        out_b = mpu.publish(portal, prepare(portal, state, REC_B, plan=plan_b))
        assert out_b["enrichment"][0]["outcome"] == "reopened" and made["status"] == "TODO"

    def test_a_shared_note_keeps_the_other_recordings_section(self, portal, state):
        portal.add_recording(REC_B, EVT_A, NOTE_A, "2026-09-15T19:00:00+00:00",
                             segments=SEGMENTS + [{"speaker": "Dana Park", "text": "Second part."}])
        out_a = mpu.publish(portal, prepare(portal, state, REC_A))
        assert out_a["status"] == "published"
        first = portal.notes[NOTE_A]["content"]
        assert f"<!-- local-recording-section:{REC_A}:" in first
        plan_b = good_plan(portal, REC_B, actions=[], content="The second recording.")
        out_b = mpu.publish(portal, prepare(portal, state, REC_B, plan=plan_b))
        assert out_b["status"] == "published"
        both = portal.notes[NOTE_A]["content"]
        assert both.startswith(first.rstrip("\n")) and "The second recording." in both

    def test_the_cli_exit_codes(self, portal, state, monkeypatch, cli):
        monkeypatch.setattr(c, "client", lambda: portal)
        folder = prepare(portal, state, verdict="FAIL")
        out = cli(mpu, [str(folder)])
        assert out.exit_code == 3 and json.loads(out.output)["code"] == "CHECK_FAILED"
        folder = prepare(portal, state)
        out = cli(mpu, [str(folder), "--dry-run"])
        assert out.exit_code == 0 and json.loads(out.output)["status"] == "would_publish"


# --------------------------------------------------------------------------- meeting-acknowledge

class TestAcknowledge:
    def test_refuses_without_a_done_admin_task(self, portal):
        d = portal.digest(REC_A)
        assert c.acknowledge(portal, REC_A, d)["code"] == "NO_TASK"
        portal.add_task(source_reference=c.admin_marker(REC_A, d), status="TODO", description=c.admin_marker(REC_A, d))
        assert c.acknowledge(portal, REC_A, d)["code"] == "NOT_DONE"

    def test_a_published_recording_is_acknowledged_once(self, portal, state):
        folder = prepare(portal, state)
        mpu.publish(portal, folder)
        d = portal.digest(REC_A)
        assert c.acknowledge(portal, REC_A, d)["status"] == "already_acknowledged"
        portal.recordings[REC_A]["processed_hash"] = None
        assert c.acknowledge(portal, REC_A, d, dry_run=True)["status"] == "would_acknowledge"
        assert c.acknowledge(portal, REC_A, d)["status"] == "acknowledged"

    def test_refuses_newer_words(self, portal):
        assert c.acknowledge(portal, REC_A, "0" * 16)["code"] == "CHANGED"

    def test_the_older_marker_is_accepted_and_made_exact(self, portal):
        d = portal.digest(REC_A)
        legacy = c.legacy_marker(EVT_A, d)
        task = portal.add_task(source_reference=legacy, status="DONE", description=f"{legacy}\nSource: {EVT_A}")
        portal.notes[NOTE_A]["associations"].append({"id": portal.new_id(), "entity_type": "task",
                                                      "entity_id": task["id"]})
        dry = c.acknowledge(portal, REC_A, d, dry_run=True)
        assert dry["status"] == "would_acknowledge" and dry["would_remark"]["task_id"] == task["id"]
        assert portal.writes == []
        out = c.acknowledge(portal, REC_A, d)
        assert out["status"] == "acknowledged" and out["remarked"] == task["id"]
        assert task["source_reference"] == c.admin_marker(REC_A, d)


# --------------------------------------------------------------------------- meeting-skip

def test_skip_records_and_clears(portal, state, cli):
    d = portal.digest(REC_A)
    out = cli(msk, [REC_A, "--digest", d, "--reason", "analyst blocked", "--state", str(state)])
    assert out.exit_code == 0 and json.loads(out.output)["entry"]["last_reason"] == "analyst blocked"
    out = cli(msk, [REC_A, "--clear", "--state", str(state)])
    assert json.loads(out.output)["removed"] == [c.ledger_key(REC_A, d)]
    assert c.load_ledger(state) == {}


# --------------------------------------------------------------------------- second review

def asking(portal, question="Who owns the board date?"):
    return good_plan(portal, clarifications=[{"question": question}])


def test_answers_in_the_folder_apply_without_the_flag(portal, state, monkeypatch, cli):
    """The orchestrator omits --answers. The owner typed their answer under the questions
    and moved the task to TODO. The old plan is refused instead of putting the same question
    back to WAITING, the answered plan publishes with his answer, and his text survives."""
    monkeypatch.setattr(c, "client", lambda: portal)
    d = portal.digest(REC_A)
    plan = asking(portal)
    folder = prepare(portal, state, plan=plan)
    first = mpu.publish(portal, folder)
    assert first["status"] == "waiting"
    admin = portal.tasks[first["admin_task_id"]]
    admin["description"] += "\nAnswer: Sam owns the board date."
    admin["status"] = "TODO"
    out = cli(mex, [REC_A, "--digest", d, "--state", str(state),
                                        "--out", str(folder / "existing.json")])
    assert out.exit_code == 0 and json.loads(out.output)["answered"] is True
    assert "Answer: Sam owns the board date." in (folder / "answers.md").read_text()

    refetch(portal, folder)
    c.atomic_json(folder / "plan.json", plan)  # the old plan, checked again, no flag given
    check(folder, plan)
    assert mpu.publish(portal, folder)["code"] == "ANSWERS_UNAPPLIED"
    assert admin["status"] == "TODO"  # not WAITING again on the same question

    answered = good_plan(portal)
    c.atomic_json(folder / "plan.json", answered)
    check(folder, answered)
    out = cli(mpu, [str(folder)])
    assert out.exit_code == 0 and json.loads(out.output)["status"] == "published"
    note = portal.notes[NOTE_A]["content"]
    assert "## Clarification received" in note and "Answer: Sam owns the board date." in note
    assert admin["status"] == "DONE" and admin["description"].endswith("Answer: Sam owns the board date.")


def test_asking_again_keeps_what_owner_typed(portal, state):
    """A later round that asks something else replaces only a questions section this
    job wrote, keeps text below it, and keeps a section the owner typed inside whole."""
    folder = prepare(portal, state, plan=asking(portal, "First question?"))
    first = mpu.publish(portal, folder)
    admin = portal.tasks[first["admin_task_id"]]
    admin["description"] += "\nThe owner: the board date is Sam's."
    admin["status"] = "TODO"  # an interrupted round; no answers filed

    second = asking(portal, "Second question?")
    c.atomic_json(folder / "plan.json", second)
    check(folder, second)
    assert mpu.publish(portal, folder)["status"] == "waiting"
    text = admin["description"]
    assert "1. Second question?" in text and "First question?" not in text
    assert text.endswith("The owner: the board date is Sam's.")
    assert text.index("Second question?") < text.index("The owner: the board date")
    assert text.count("Questions for the owner") == 1

    admin["description"] = text.replace("1. Second question?", "1. Second question? Sam, I think.")
    admin["status"] = "TODO"
    third = asking(portal, "Third question?")
    c.atomic_json(folder / "plan.json", third)
    check(folder, third)
    assert mpu.publish(portal, folder)["status"] == "waiting"
    text = admin["description"]
    assert "Second question? Sam, I think." in text and "The owner: the board date is Sam's." in text
    assert text.rstrip().endswith(c.QUESTIONS_FOOT) and "1. Third question?" in text
    assert c.asked_at(text) is not None and text.count("Questions for the owner") == 2


def test_an_unreachable_portal_after_step_3_takes_the_attempt_back(portal, state, monkeypatch, cli):
    """Meeting-existing counts the attempt at step 3; an outage at fetch, publish or
    acknowledge defers the recording and takes it back, so an outage never parks it."""
    monkeypatch.setattr(c, "client", lambda: portal)
    d = portal.digest(REC_A)
    key = c.ledger_key(REC_A, d)
    exist = [REC_A, "--digest", d, "--state", str(state)]
    for _ in range(c.MAX_ATTEMPTS + 1):
        assert cli(mex, exist).exit_code == 0
        assert c.load_ledger(state)[key]["attempts"] == 1
        portal.fail["get_fellow_recording"] = "unreachable"
        out = cli(mfe, [REC_A, "--digest", d, "--state", str(state)])
        assert out.exit_code == 2
        entry = c.load_ledger(state)[key]
        assert entry["attempts"] == 0 and entry["deferred_at"] and "HTTP 503" in entry["last_reason"]

    folder = prepare(portal, state)
    for _ in range(c.MAX_ATTEMPTS + 1):
        assert cli(mex, exist).exit_code == 0
        portal.fail["update_note"] = "unreachable"
        out = cli(mpu, [str(folder)])
        assert out.exit_code == 2
        entry = c.load_ledger(state)[key]
        assert entry["attempts"] == 0 and "meeting-publish" in entry["last_reason"]

    assert cli(mex, exist).exit_code == 0
    portal.fail["get_fellow_recording"] = "unreachable"
    out = cli(mack, [REC_A, "--digest", d, "--state", str(state)])
    assert out.exit_code == 2 and c.load_ledger(state)[key]["attempts"] == 0

    listed = pending(portal, state)
    assert [r["recording_id"] for r in listed["deferred"]] == [REC_A] and listed["parked"] == []
    portal.fail["get_fellow_recording"] = "unreachable"  # a dry run touches no ledger
    before = c.load_ledger(state)
    assert cli(mfe, [REC_A, "--digest", d, "--state", str(state), "--dry-run"]).exit_code == 2
    assert c.load_ledger(state) == before


def test_a_waiting_publish_is_not_listed_again_until_owner_answers(portal, state, tmp_path, monkeypatch, cli):
    """A waiting result records its admin task in the ledger (not in a dry run, and
    in the --state folder when one is given), so the next run spends no slot on it."""
    monkeypatch.setattr(c, "client", lambda: portal)
    folder = prepare(portal, state, plan=asking(portal))
    assert mpu.publish(portal, folder, dry_run=True)["status"] == "would_publish"
    assert c.load_ledger(state) == {}
    other = c.state_root(str(tmp_path / "other"))
    out = cli(mpu, [str(folder), "--state", str(other)])
    result = json.loads(out.output)
    assert out.exit_code == 0 and result["status"] == "waiting"
    assert c.load_ledger(state) == {}
    entry = c.load_ledger(other)[c.ledger_key(REC_A, portal.digest(REC_A))]
    assert entry["waiting_task_id"] == result["admin_task_id"]
    listed = pending(portal, other)
    assert listed["recordings"] == [] and listed["counts"]["waiting"] == 1
    portal.add_comment(result["admin_task_id"], "1) Sam")
    assert [r["recording_id"] for r in pending(portal, other)["recordings"]] == [REC_A]


def test_an_agent_label_with_parentheses_is_not_owner(portal):
    """"(posted by Claude (Opus), an agent)" is an agent's comment, not an answer."""
    assert c.AGENT_LINE.search("Done.\n\n(posted by Claude (Opus), an agent)")
    assert c.AGENT_LINE.search("Done.\n(posted by weekly-reporter, an agent)\n")
    assert not c.AGENT_LINE.search("I asked (posted by Claude, an agent) to stop. Sam owns it.")
    task = TestExisting().waiting_task(portal)
    d = portal.digest(REC_A)
    portal.add_comment(task["id"], "Working on it.\n\n(posted by Claude (Opus), an agent)")
    assert mex.existing(portal, REC_A, d)["stage"] == "waiting"
    portal.add_comment(task["id"], "1) Sam owns it")
    out = mex.existing(portal, REC_A, d)
    assert out["stage"] == "resume" and "Claude (Opus)" not in out["answers_text"]


def test_an_answer_relayed_by_the_runner_is_the_owners(portal):
    """A runner posts the owner's typed answer with an agent token; its first line (the setting
    relayed_answer_head) says whose words it carries."""
    task = TestExisting().waiting_task(portal)
    d = portal.digest(REC_A)
    portal.add_comment(task["id"], "Sam owns it.\n\n(posted by Claude Assistant, an agent)")
    assert mex.existing(portal, REC_A, d)["stage"] == "waiting"
    portal.add_comment(task["id"], f"{RELAYED}\n\n1. Who owns the board date?\nAnswer: Sam\n\n"
                                   "\n\n(posted by Claude Assistant, an agent)")
    out = mex.existing(portal, REC_A, d)
    assert out["stage"] == "resume" and out["answered"] is True
    assert "Answer: Sam" in out["answers_text"] and "Sam owns it." not in out["answers_text"]
    portal.add_comment(task["id"], f"{RELAYED}\n\nJordan", email="someone.else@example.com")
    assert "Jordan" not in mex.existing(portal, REC_A, d)["answers_text"]  # only the owner's member


def test_a_held_lock_skips_the_recording_not_the_run(portal, state, monkeypatch, cli):
    """A lock held past the wait refuses that recording (BUSY, exit 3) and leaves
    the holder's publish.json alone; a held ledger lock is an error for that command only."""
    import fcntl
    monkeypatch.setattr(c, "client", lambda: portal)
    monkeypatch.setattr(c, "LOCK_WAIT_SECONDS", 0.2)
    folder = prepare(portal, state)
    with (folder / "publish.lock").open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        out = mpu.publish(portal, folder)
        assert out["status"] == "refused" and out["code"] == "BUSY" and "held by another command" in out["reason"]
        held_out = cli(mpu, [str(folder)])
        assert held_out.exit_code == 3 and json.loads(held_out.output)["code"] == "BUSY"
        assert portal.writes == [] and not (folder / "publish.json").exists()
    with (state / "ledger.lock").open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        with pytest.raises(c.Busy):
            c.update_ledger(state, REC_A, portal.digest(REC_A), reason="x")
        skip = cli(msk, [REC_A, "--digest", portal.digest(REC_A), "--reason", "x",
                                             "--state", str(state)])
        assert skip.exit_code == 2 and "held by another command" in skip.output
    assert mpu.publish(portal, folder)["status"] == "published"
