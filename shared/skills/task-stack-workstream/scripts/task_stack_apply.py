#!/usr/bin/env python3
"""task-stack-apply: the one writer of the owner's task stack in the Insights Portal.

Every task-stack orchestrator proposes its writes as a change set (RUN/changes.json) and this
script makes them after the session, each once, under the task-stack rules. A dry run writes
nothing, a re-run writes nothing twice, and every write is logged so it can be undone.

  python3 task_stack_apply.py --run RUN                 RUN/changes.json; results to RUN/apply.json
  python3 task_stack_apply.py --run RUN --dry-run       what it would do, to RUN/apply-dry-run.json
  python3 task_stack_apply.py --run RUN --dry-run-if=true   a scheduler's placeholder; true means dry
  python3 task_stack_apply.py CHANGES.json --log undo.jsonl --out applied.json
  python3 task_stack_apply.py --undo RUN/undo.jsonl [--op OP_ID] [--dry-run]

THE CHANGE SET
  {"tool": "task-stack-changes", "version": 1, "orchestrator": "task-reconcile-orchestrator",
   "dry_run": false,
   "ops": [
    {"id": "c1", "op": "complete", "task": "portal://task/<uuid>", "evidence": "portal://email/<uuid>",
     "reason": "Sent the signed SOW"},
    {"id": "e1", "op": "edit", "task": "<uuid>", "set": {"due_date": "2030-10-15"}, "reason": "..."},
    {"id": "m1", "op": "merge", "task": "<the duplicate>", "into": "<the older task>", "reason": "..."},
    {"id": "x1", "op": "cancel", "task": "<uuid>", "reason": "Stale since June, no goal"},
    {"id": "n1", "op": "create", "title": "Send the board pack", "project": "<uuid>", "due_date": "...",
     "reason": "...", "source": "<source>:<item id>"},
    {"id": "k1", "op": "comment", "task": "<uuid>", "body": "...", "reason": "..."},
    {"id": "p1", "op": "project_edit", "project": "portal://project/<uuid>", "set": {"goal_id": "<uuid>"}},
    {"id": "p2", "op": "project_close", "project": "<uuid>", "status": "CANCELLED", "reason": "..."},
    {"id": "g1", "op": "goal_edit", "goal": "portal://goal/<uuid>", "set": {"priority": "P2"}, "reason": "..."},
    {"id": "g2", "op": "goal_close", "goal": "<uuid>", "status": "CANCELLED", "reason": "..."}],
   "questions": [{"ask": "...", "task": "portal://task/<uuid>", "why": "..."}], "notes": []}

Every op has a unique `id`, its `op`, a `reason`, and `by` (the producing agent; the set's
`orchestrator` when absent). `evidence` is portal://<email|note|calendar_event|task|project|
goal|document>/<uuid> (read before it is relied on: it must exist, and an event must have
started) or an https:// link to a commit or pull request.

THE RULES (an op that fails one is refused whole, with a code; the other ops go on)
- Nothing is ever deleted. Undoing a create cancels the task.
- complete: the task is open; evidence is required and goes into the completion comment.
- edit: only EDITABLE fields; status only TODO, IN_PROGRESS or WAITING. A task left WAITING has
  a due date (its follow-up date) and a task moved to WAITING names who it waits on. A new
  title starts with a verb. A new project_id is an open project, in the op's domain_id when it
  sets one, and inside --domain.
- merge: both tasks open with the same owner; `into` (kept) is the older one. The kept task
  gets a comment carrying the duplicate's text and any MERGE_FILL field it lacks; the
  duplicate is completed with "Duplicate of <ref>".
- cancel: with evidence, or without only when the task has had no update for
  --stale-cancel-days (60) and links to no goal. A cancel by task-reconcile-orchestrator
  carries "check": "PASS" from its checker or is refused UNCHECKED.
- create: a verb-first title, an owner (the op's, else the token's own contact), a project
  or a domain whose catch-all project takes it, and no open task in that project already is
  it. A create with `source` is marked by that key alone, so the item gets one task.
- project_edit / project_close: only PROJECT_EDITABLE fields and open statuses; a close to
  CANCELLED or COMPLETED (COMPLETED needs evidence) once no open task is left. Without
  evidence, CANCELLED only with no goal and no activity for --stale-close-days (90). A
  catch-all project is never edited or closed.
- goal_edit / goal_close: priority P1-P4, horizon, title, dates, open status (DEFERRED parks
  it); a close to ACHIEVED (needs evidence), CANCELLED or MISSED while no active project or
  sub-goal still serves it, unless an earlier op in the same set closed or relinked it.
- Only the owner's own (or unowned) tasks, projects and goals move. Work is assigned only to
  the owner or a contact in the setting [task-stack-workstream] assignable_contacts.
- --domain limits every op to one domain; --max-changes caps the writes, the rest deferred.

HAND EDITS: a field changed by anyone else in the last --hand-edit-days (7) is never
overwritten. The journal (<state>/writes.jsonl) holds each record's updated_at and tracked
values after this script wrote it; a later change it did not make is a hand edit. Each write
is found first by its marker (`tsk` + 12 hex digits of the op's content), sent against the
version just read, and read back. Every write appends a line to the undo log.

Settings: portal_mcp_config (and portal_server); state_dir, or --state (the journal and lock
live in <state_dir>/task-stack); [task-stack-workstream] assignable_contacts and lead_words.

Prints one JSON object. Exit 0 when every op was applied, unchanged, refused or deferred for
a stated reason; 3 when a write failed (partial) or the whole set was refused; 2 when it
could not run.
"""

import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import _common as c

TOOL, VERSION = "task-stack-changes", 1
CHECKED_CANCELS = ("task-reconcile-orchestrator",)
PROJECT_OPS = ("project_edit", "project_close")
GOAL_OPS = ("goal_edit", "goal_close")
OPS = ("complete", "edit", "merge", "cancel", "create", "comment") + PROJECT_OPS + GOAL_OPS
OPEN = ("TODO", "IN_PROGRESS", "WAITING")
ALL_STATUSES = ["TODO", "IN_PROGRESS", "WAITING", "DONE", "CANCELLED"]
EDIT_STATUSES = ("TODO", "IN_PROGRESS", "WAITING")
# What `edit` may set: never description (an agent adds by comment, never rewrites the owner's text).
EDITABLE = ("title", "status", "project_id", "domain_id", "goal_id", "due_date", "deadline", "start_date",
            "priority", "owner_contact_id", "waiting_on_contact_id", "waiting_reason")
DATE_FIELDS = ("due_date", "deadline", "start_date")
ID_FIELDS = ("project_id", "domain_id", "goal_id", "owner_contact_id", "waiting_on_contact_id", "assignee_contact_id")
MERGE_FILL = ("project_id", "goal_id", "due_date", "deadline")
TRACKED = EDITABLE + ("description",)
PROJECT_EDITABLE = ("status", "goal_id", "assignee_contact_id", "priority", "due_date", "deadline", "start_date")
PROJECT_OPEN_STATUSES = ("NOT_STARTED", "PLANNING", "IN_PROGRESS", "ON_HOLD")
PROJECT_CLOSE_STATUSES = ("CANCELLED", "COMPLETED")
PROJECT_TRACKED = PROJECT_EDITABLE + ("is_archived",)
GOAL_EDITABLE = ("status", "priority", "horizon", "title", "due_date", "deadline")
GOAL_OPEN_STATUSES = ("NOT_STARTED", "IN_PROGRESS", "DEFERRED")
GOAL_CLOSE_STATUSES = ("ACHIEVED", "CANCELLED", "MISSED")
GOAL_TRACKED = GOAL_EDITABLE + ("is_archived", "assignee_contact_id")
CLOSED_GOAL = ("ACHIEVED", "MISSED", "CANCELLED", "ARCHIVED", "COMPLETED", "DONE")
HORIZONS = ("VISION", "ANNUAL", "QUARTERLY", "MONTHLY")
HAND_EDIT_DAYS, STALE_CLOSE_DAYS, STALE_CANCEL_DAYS, MAX_CHANGES = 7, 90, 60, 50
COMMENT_MAX, TITLE_MAX = 4000, 200
DUP_THRESHOLD = 0.85

HEX_ID = r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}"
UUID = re.compile(rf"^{HEX_ID}$")
TASK_REF = re.compile(rf"^(?:portal://task/)?({HEX_ID})$")
PROJECT_REF = re.compile(rf"^(?:portal://project/)?({HEX_ID})$")
GOAL_REF = re.compile(rf"^(?:portal://goal/)?({HEX_ID})$")
PORTAL_REF = re.compile(rf"^portal://(email|note|calendar_event|task|project|goal|document)/({HEX_ID})$")
LINK_REF = re.compile(r"^https://\S+$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
OP_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")
AGENT = re.compile(r"^[a-z0-9][a-z0-9-]{1,80}$")
SOURCE_KEY = re.compile(r"^[a-z][a-z0-9-]{0,40}:[A-Za-z0-9][A-Za-z0-9_.:-]{0,80}$")
PRIORITY = re.compile(r"^[Pp]?([1-4])$")


class Refused(Exception):
    """One op (or the whole set) a rule stops. Nothing is written."""

    def __init__(self, code, reason):
        super().__init__(reason)
        self.code, self.reason = code, reason


# --------------------------------------------------------------------------- small helpers

def _id(pattern, ref):
    m = pattern.match(str(ref or "").strip())
    return m.group(1).lower() if m else None


def task_id(ref):
    return _id(TASK_REF, ref)


def project_id(ref):
    return _id(PROJECT_REF, ref)


def goal_id(ref):
    return _id(GOAL_REF, ref)


def tref(tid):
    return f"portal://task/{tid}"


def norm(field, value):
    """A field's value as compared: dates YYYY-MM-DD, priority 1-4, ids and statuses in one
    case, horizon upper case, empty as None."""
    if value in (None, "", []):
        return None
    if field in DATE_FIELDS:
        return str(value)[:10]
    if field == "priority":
        m = PRIORITY.fullmatch(str(value).strip())
        return int(m.group(1)) if m else str(value)
    if field in ID_FIELDS:
        return str(value).lower()
    if field in ("status", "horizon"):
        return str(value).upper()
    return value


def portal_priority(value):
    """A goal's priority in the Portal's own spelling, P1 to P4."""
    m = PRIORITY.match(str(value or "").strip())
    return f"P{m.group(1)}" if m else value


def source_marker(source):
    """The marker of a create that captures one source item: `tsk` + 12 hex digits of the
    item's key alone, so the item has one task however its title is worded."""
    return "tsk" + hashlib.sha256(f"source:{source.strip()}".encode("utf-8")).hexdigest()[:12]


def marker_for(by, op):
    """`tsk` + 12 hex digits of the op's content (not its id or reason), so the same op
    proposed on another night is the same write."""
    kind = op.get("op")
    if kind == "create" and str(op.get("source") or "").strip():
        return source_marker(str(op["source"]))
    if kind in GOAL_OPS:
        content = {"op": kind, "goal": goal_id(op.get("goal")), "set": op.get("set"), "status": op.get("status")}
    else:
        keys = ("op", "project", "set", "status") if kind in PROJECT_OPS else (
            "op", "task", "into", "set", "title", "project", "domain", "body")
        content = {k: op.get(k) for k in keys}
        if kind in PROJECT_OPS and content.get("project"):
            content["project"] = project_id(content["project"]) or content["project"]
        for k in ("task", "into"):
            if content.get(k):
                content[k] = task_id(content[k]) or content[k]
        if content.get("title"):
            content["title"] = c.normalise_title(str(content["title"]))
    content = {k: v for k, v in content.items() if v not in (None, "", {})}
    raw = json.dumps({"by": by, **content}, sort_keys=True, default=str)
    return "tsk" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def live_project(project):
    """Open for new tasks: not archived, not closed (a catch-all counts)."""
    return not project.get("is_archived") and c.status_of(project).lower() not in c.CLOSED_PROJECT_STATUSES


def truthy_flag(value):
    """--dry-run-if from a scheduler placeholder: only an unmistakable value is accepted."""
    text = str(value or "").strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    raise c.Stop(f"--dry-run-if wants true or false, got {value!r}; nothing was written")


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def append_jsonl(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def read_jsonl(path):
    if not path.is_file():
        return []
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise c.Stop(f"{path} line {n} is not JSON ({exc.msg})") from None
            if isinstance(row, dict):
                rows.append(row)
    return rows


@contextmanager
def locked(root):
    """Two applies (or an apply and an undo) never interleave."""
    root.mkdir(parents=True, exist_ok=True)
    with (root / "apply.lock").open("w") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise c.Stop("another task-stack apply or undo holds the lock; nothing was written") from None
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


# --------------------------------------------------------------------------- the change set

def load_changes(data):
    """The set and its ops. A set that is not one is refused whole; a bad op is refused alone."""
    if not isinstance(data, dict):
        raise Refused("INVALID_SET", "the change set is not a JSON object")
    if data.get("tool") != TOOL:
        raise Refused("INVALID_SET", f"the change set's tool is {data.get('tool')!r}, not {TOOL!r}")
    if data.get("version") != VERSION:
        raise Refused("INVALID_SET", f"change set version {data.get('version')!r}; this command reads {VERSION}")
    if not isinstance(data.get("dry_run"), bool):
        raise Refused("INVALID_SET", "the change set must say dry_run: true or false, so a malformed file is "
                                     "never read as a live one")
    ops = data.get("ops")
    if not isinstance(ops, list):
        raise Refused("INVALID_SET", "`ops` is not a list")
    ids = [o.get("id") for o in ops if isinstance(o, dict)]
    dup = sorted({str(i) for i in ids if ids.count(i) > 1})
    if dup:
        raise Refused("INVALID_SET", f"op ids appear twice: {', '.join(dup)}")
    orchestrator = data.get("orchestrator")
    if orchestrator is not None and not AGENT.match(str(orchestrator)):
        raise Refused("INVALID_SET", f"orchestrator {orchestrator!r} is not an agent name")
    return data, ops


def evidence_ref(value):
    """(kind, id) for a Portal reference, ("link", url) for a link, else None."""
    text = str(value or "").strip()
    m = PORTAL_REF.match(text)
    if m:
        return m.group(1), m.group(2).lower()
    return ("link", text) if LINK_REF.match(text) else None


def check_fields(fields, dates, ids, out):
    """Shared checks on a `set`: dates, ids and priority in their forms."""
    for f in dates:
        if fields.get(f) not in (None, "") and not DATE.match(str(fields[f])):
            out.append(f"{f} is YYYY-MM-DD or null")
    for f in ids:
        if fields.get(f) not in (None, "") and not UUID.match(str(fields[f])):
            out.append(f"{f} is a uuid or null")


def shape_problems(op):
    """What is wrong with one op's shape, before the Portal is read."""
    if not isinstance(op, dict):
        return ["the op is not a JSON object"]
    out, kind = [], op.get("op")
    if not OP_ID.match(str(op.get("id") or "")):
        out.append("id is required (letters, digits, _ . : -)")
    if kind not in OPS:
        return out + [f"op must be one of {', '.join(OPS)}"]
    if not str(op.get("reason") or "").strip():
        out.append("reason is required")
    if op.get("by") is not None and not AGENT.match(str(op["by"])):
        out.append(f"by {op['by']!r} is not an agent name")
    if op.get("evidence") not in (None, "") and evidence_ref(op["evidence"]) is None:
        out.append("evidence is portal://<email|note|calendar_event|task|project|goal|document>/<uuid> "
                   "or an https:// link")
    fields = op.get("set")
    if kind in PROJECT_OPS:
        if not project_id(op.get("project")):
            out.append("project is portal://project/<uuid> or the uuid")
        if kind == "project_edit":
            if not isinstance(fields, dict) or not fields:
                return out + ["project_edit needs set, the fields and their new values"]
            bad = sorted(k for k in fields if k not in PROJECT_EDITABLE)
            if bad:
                out.append(f"project_edit may not set {', '.join(bad)} (it may set {', '.join(PROJECT_EDITABLE)})")
            if "status" in fields and str(fields["status"] or "").upper() not in PROJECT_OPEN_STATUSES:
                out.append(f"project_edit sets status only to {', '.join(PROJECT_OPEN_STATUSES)}; use project_close")
            check_fields(fields, DATE_FIELDS, ("goal_id", "assignee_contact_id"), out)
            if fields.get("priority") not in (None, "") and not PRIORITY.match(str(fields["priority"])):
                out.append("priority is 1 to 4")
        else:
            status = str(op.get("status") or "CANCELLED").upper()
            if status not in PROJECT_CLOSE_STATUSES:
                out.append(f"project_close status is one of {', '.join(PROJECT_CLOSE_STATUSES)}")
            if status == "COMPLETED" and not op.get("evidence"):
                out.append("project_close to COMPLETED needs evidence that the work was done")
        return out
    if kind in GOAL_OPS:
        if not goal_id(op.get("goal")):
            out.append("goal is portal://goal/<uuid> or the uuid")
        if kind == "goal_edit":
            if not isinstance(fields, dict) or not fields:
                return out + ["goal_edit needs set, the fields and their new values"]
            bad = sorted(k for k in fields if k not in GOAL_EDITABLE)
            if bad:
                out.append(f"goal_edit may not set {', '.join(bad)} (it may set {', '.join(GOAL_EDITABLE)})")
            if "status" in fields and str(fields["status"] or "").upper() not in GOAL_OPEN_STATUSES:
                out.append(f"goal_edit sets status only to {', '.join(GOAL_OPEN_STATUSES)}; use goal_close")
            if "priority" in fields and not PRIORITY.match(str(fields["priority"] or "")):
                out.append("priority is P1 to P4")
            if fields.get("horizon") not in (None, "") and str(fields["horizon"]).upper() not in HORIZONS:
                out.append(f"horizon is one of {', '.join(HORIZONS)} or null")
            if "title" in fields and not 0 < len(str(fields["title"] or "").strip()) <= TITLE_MAX:
                out.append(f"title is 1 to {TITLE_MAX} characters")
            check_fields(fields, ("due_date", "deadline"), (), out)
        else:
            status = str(op.get("status") or "CANCELLED").upper()
            if status not in GOAL_CLOSE_STATUSES:
                out.append(f"goal_close status is one of {', '.join(GOAL_CLOSE_STATUSES)}")
            if status == "ACHIEVED" and not op.get("evidence"):
                out.append("goal_close to ACHIEVED needs evidence that the goal was met")
        return out
    if kind != "create" and not task_id(op.get("task")):
        out.append("task is portal://task/<uuid> or the uuid")
    if kind == "complete" and not op.get("evidence"):
        out.append("complete needs evidence: the sent mail, meeting note, commit, event or document that did it")
    if kind == "merge":
        if not task_id(op.get("into")):
            out.append("merge needs into, the task kept")
        elif task_id(op.get("into")) == task_id(op.get("task")):
            out.append("merge's task and into are the same task")
    if kind == "edit":
        if not isinstance(fields, dict) or not fields:
            out.append("edit needs set, the fields and their new values")
        else:
            bad = sorted(k for k in fields if k not in EDITABLE)
            if bad:
                out.append(f"edit may not set {', '.join(bad)} (it may set {', '.join(EDITABLE)})")
            if "status" in fields and str(fields["status"] or "").upper() not in EDIT_STATUSES:
                out.append("edit sets status only to TODO, IN_PROGRESS or WAITING; use complete or cancel")
            check_fields(fields, DATE_FIELDS, ID_FIELDS, out)
            if "title" in fields and not 0 < len(str(fields["title"] or "").strip()) <= TITLE_MAX:
                out.append(f"title is 1 to {TITLE_MAX} characters")
            if fields.get("priority") not in (None, "") and not PRIORITY.match(str(fields["priority"])):
                out.append("priority is 1 to 4")
    if kind == "create":
        if not 0 < len(str(op.get("title") or "").strip()) <= TITLE_MAX:
            out.append(f"create needs a title of 1 to {TITLE_MAX} characters")
        if not (UUID.match(str(op.get("project") or "")) or UUID.match(str(op.get("domain") or ""))):
            out.append("create needs a project, or a domain whose catch-all project takes it (uuids)")
        for f in ("owner", "task_contact"):
            if op.get(f) not in (None, "") and not UUID.match(str(op[f])):
                out.append(f"{f} is a uuid")
        if op.get("due_date") not in (None, "") and not DATE.match(str(op["due_date"])):
            out.append("due_date is YYYY-MM-DD")
        if op.get("source") not in (None, "") and not SOURCE_KEY.match(str(op["source"])):
            out.append("source is a capture source key, <source>:<item id> (letters, digits, _ . : -)")
    elif op.get("source") not in (None, ""):
        out.append("source belongs only on a create")
    if kind == "comment":
        body = str(op.get("body") or "").strip()
        if not body or len(body) > COMMENT_MAX - 200:
            out.append(f"comment needs a body of at most {COMMENT_MAX - 200} characters")
    return out


# --------------------------------------------------------------------------- the writer

class Applier:
    """Applies the ops of one change set: one Portal client, one journal, one undo log."""

    def __init__(self, client, dry_run, state, log, orchestrator, domain="", max_changes=MAX_CHANGES,
                 hand_edit_days=HAND_EDIT_DAYS, stale_cancel_days=STALE_CANCEL_DAYS,
                 stale_close_days=STALE_CLOSE_DAYS, now=None):
        self.client, self.dry_run, self.state, self.log = client, dry_run, state, log
        self.orchestrator, self.domain, self.max_changes = orchestrator, domain.strip(), max_changes
        self.hand_edit = timedelta(days=hand_edit_days)
        self.stale_cancel = timedelta(days=stale_cancel_days)
        self.stale_close = timedelta(days=stale_close_days)
        self.now = now or datetime.now(timezone.utc)
        self.writes = 0
        self.closing = set()     # tasks this run closed (or would): a project close counts them closed
        self.done = []           # (op, result) in order: a later op may count an earlier one
        self._owner = self._journals = self._domains = self._open = self._projects = self._goals = None

    # ---------------------------------------------------------------- reads

    def owner(self):
        if self._owner is None:
            who = self.client.call("whoami")
            principal = ((who or {}).get("principal") or {}) if isinstance(who, dict) else {}
            contact = str(principal.get("contact_id") or "")
            if not UUID.match(contact):
                raise c.Stop("whoami named no contact for the owner; nothing is written ownerless")
            self._owner = contact.lower()
        return self._owner

    def check_assignee(self, contact):
        """Work goes only to the owner or a contact in the assignable_contacts setting."""
        who = str(contact or "").lower()
        if who and who not in {self.owner(), *(a.lower() for a in c.setting_list("assignable_contacts"))}:
            raise Refused("NOT_ASSIGNABLE", f"{who} has not agreed to receive agent assignments (not the owner, "
                                            "not in the [task-stack-workstream] assignable_contacts setting); "
                                            "the first assignment is the owner's call")

    def read(self, kind, ident, detail="full"):
        """One task, project or goal. A task carries its comments and hierarchy beside it under
        `_comments` and `_hierarchy`; a full project carries its tasks under `_tasks`."""
        out = self.client.call("get", {"entity_type": kind, "id_or_query": ident, "detail": detail})
        if not isinstance(out, dict) or out.get("error"):
            raise Refused("NOT_FOUND", f"{kind} {ident} could not be read: "
                                       f"{out.get('error') if isinstance(out, dict) else 'no answer'}")
        record = dict(out.get(kind) if isinstance(out.get(kind), dict) else out)
        if str(record.get("id") or "").lower() != ident:
            raise Refused("NOT_FOUND", f"the read for {kind} {ident} returned another record")
        if kind == "task":
            record["_comments"] = [x for x in out.get("comments") or [] if isinstance(x, dict)]
            record["_hierarchy"] = out.get("hierarchy") if isinstance(out.get("hierarchy"), dict) else {}
        if kind == "project" and detail == "full":
            record["_tasks"] = [t for t in out.get("tasks") or [] if isinstance(t, dict)]
            record["_open"] = {str(t.get("id")).lower() for t in record["_tasks"]
                               if norm("status", t.get("status")) in OPEN and not t.get("is_archived")}
        return record

    def read_task(self, tid):
        return self.read("task", tid)

    def check_evidence(self, value):
        """Empty when the evidence holds, else why not. A link is taken as given; a Portal
        reference must exist and read back as itself, and an event must have started."""
        ref = evidence_ref(value)
        if ref is None:
            return "no evidence"
        kind, ident = ref
        if kind == "link":
            return ""
        try:
            out = self.client.call("get", {"entity_type": kind, "id_or_query": ident, "detail": "summary"})
        except Exception as exc:
            return f"the evidence {value} could not be read ({type(exc).__name__})"
        if not isinstance(out, dict) or out.get("error"):
            return f"the evidence {value} was not found"
        # Some kinds nest the record (an event under `event`); an email answers with its thread
        # and its own `_ref`.
        inner = out.get(kind) if isinstance(out.get(kind), dict) else (
            out.get("event") if isinstance(out.get("event"), dict) else out)
        own = {str(inner.get("id") or "").lower(), str(out.get("_ref") or "").lower()}
        if ident not in own and f"portal://{kind}/{ident}" not in own:
            return f"the evidence {value} read back as another record"
        if kind == "calendar_event":
            start = c.parse_time(inner.get("start_time") or inner.get("start"))
            if start is None or start > self.now:
                return f"the event {value} has not happened yet"
        return ""

    def evidence_holds(self, op):
        if op.get("evidence"):
            problem = self.check_evidence(op["evidence"])
            if problem:
                raise Refused("EVIDENCE", problem)

    def domains_in_scope(self):
        if not self.domain:
            return None
        if self._domains is None:
            rows, _ = c.page_through(self.client, "domain", {"include_inactive": True})
            want = self.domain.lower()
            self._domains = {str(d.get("id")).lower() for d in rows
                             if str(d.get("id")).lower() == want or want in str(d.get("name") or "").lower()}
            if not self._domains:
                raise c.Stop(f"no domain matches --domain {self.domain!r}; nothing was written")
        return self._domains

    def in_scope(self, domain_id, what):
        scope = self.domains_in_scope()
        if scope is not None and (str(domain_id or "").lower() or None) not in scope:
            raise Refused("OUT_OF_SCOPE", f"{what} is outside --domain {self.domain!r}")

    def listing(self, kind):
        cache = {"task": "_open", "project": "_projects", "goal": "_goals"}[kind]
        if getattr(self, cache) is None:
            setattr(self, cache, c.page_through(self.client, kind)[0])
        return getattr(self, cache)

    def tasks_with_marker(self, marker):
        out = self.client.call("list_entities", {"entity_type": "task", "limit": 50,
                                                 "filters": {"search": marker, "status": ALL_STATUSES}})
        if not isinstance(out, dict) or out.get("error"):
            raise c.Stop(f"the marker lookup failed: {out.get('error') if isinstance(out, dict) else 'no answer'}")
        return [t for t in out.get("items") or [] if isinstance(t, dict)
                and (marker in str(t.get("description") or "") or str(t.get("source_reference") or "") == marker)]

    # ---------------------------------------------------------------- the journal and hand edits

    def journal(self, key):
        """The last journal row per record, for one of task_id, project_id or goal_id."""
        if self._journals is None:
            self._journals = {"task_id": {}, "project_id": {}, "goal_id": {}}
            for row in read_jsonl(self.state / "writes.jsonl"):
                for k in ("task_id", "project_id", "goal_id"):
                    if row.get(k) and (k == "task_id" or not row.get("task_id")):
                        self._journals[k][str(row[k]).lower()] = row
                        break
        return self._journals[key]

    def remember(self, key, record, op, by):
        """After a write: the record's updated_at and tracked values, for the hand-edit test."""
        tracked = {"task_id": TRACKED, "project_id": PROJECT_TRACKED, "goal_id": GOAL_TRACKED}[key]
        row = {key: str(record["id"]).lower(), "updated_at": record.get("updated_at"),
               "fields": {f: record.get(f) for f in tracked}, "op_id": op.get("id"), "by": by,
               "at": self.now.isoformat(timespec="seconds")}
        append_jsonl(self.state / "writes.jsonl", row)
        self.journal(key)[row[key]] = row

    def protected(self, record, key="task_id"):
        """The fields a write may not touch, and why. Free when not updated inside the window,
        never edited since creation, or last changed by this script; otherwise the fields that
        differ from the journal (or every field when the journal has no row) are protected."""
        tracked = {"task_id": TRACKED, "project_id": PROJECT_TRACKED, "goal_id": GOAL_TRACKED}[key]
        updated, created = c.parse_time(record.get("updated_at")), c.parse_time(record.get("created_at"))
        if updated is None or self.now - updated > self.hand_edit:
            return set(), ""
        if created is not None and abs((updated - created).total_seconds()) <= 60:
            return set(), ""
        entry = self.journal(key).get(str(record["id"]).lower())
        if entry and c.parse_time(entry.get("updated_at")) == updated:
            return set(), ""
        when = updated.isoformat(timespec="minutes")
        if entry:
            then = entry.get("fields") or {}
            changed = {f for f in tracked if norm(f, record.get(f)) != norm(f, then.get(f))}
            return changed, f"changed by someone else at {when}, inside the {self.hand_edit.days}-day window"
        return set(tracked), (f"updated at {when}, inside the {self.hand_edit.days}-day window, and never "
                              "written by task-stack-apply, so any field may be a hand edit")

    def guard(self, record, fields, key="task_id"):
        blocked, why = self.protected(record, key)
        hit = sorted(set(fields) & blocked)
        if hit:
            raise Refused("HAND_EDIT", f"{', '.join(hit)} {'is' if len(hit) == 1 else 'are'} protected: {why}")

    def take_slot(self):
        if self.writes >= self.max_changes:
            raise Refused("DEFERRED", f"--max-changes {self.max_changes} reached; it comes back next run")
        self.writes += 1

    # ---------------------------------------------------------------- write primitives

    def open_task(self, tid, what="task"):
        task = self.read_task(tid)
        if task.get("is_archived"):
            raise Refused("CLOSED", f"the {what} is archived")
        owner = str(task.get("owner_contact_id") or "").lower()
        if owner and owner != self.owner():
            raise Refused("NOT_OWNER", f"the {what} is {task.get('owner_name') or 'another person'}'s; "
                                       "only the owner's own tasks are changed")
        dom = (task.get("_hierarchy") or {}).get("domain") or {}
        self.in_scope(dom.get("id") or task.get("domain_id"), f"the {what}")
        return task

    @staticmethod
    def has_marker(task, marker):
        return any(marker in str(x.get("body") or x.get("content") or "") for x in task.get("_comments") or [])

    def comment(self, tid, body, marker, by, op_id):
        text = f"{body.rstrip()}\n\n{by} via task-stack-apply, op {op_id}. Marker: {marker}"
        out = self.client.call("create_task_comment", {"task_id": tid, "body": text[:COMMENT_MAX]})
        cid = out.get("id") if isinstance(out, dict) else None
        if not cid and isinstance(out, dict) and isinstance(out.get("comment"), dict):
            cid = out["comment"].get("id")
        return str(cid) if cid else None

    def write_back(self, kind, record, fields, status=None):
        """One update, sent against the version just read, then read back. The record is read
        again first; a tracked field that changed since the op's read means someone is editing
        it now, and nothing is written. Tasks also send expected_updated_at."""
        tracked = {"task": TRACKED, "project": PROJECT_TRACKED, "goal": GOAL_TRACKED}[kind]
        rid = str(record["id"]).lower()
        fresh = self.read(kind, rid, "full" if kind == "task" else "summary")
        moved = [f for f in tracked if norm(f, fresh.get(f)) != norm(f, record.get(f))]
        if moved:
            raise RuntimeError(f"{', '.join(moved)} changed while this ran; nothing written to the {kind}")
        args = {"id": fresh["id"]}
        if kind == "task" and fresh.get("updated_at"):
            args["expected_updated_at"] = fresh["updated_at"]
        if status:
            args["status"] = status
        if fields:
            args["fields"] = ({f: portal_priority(v) if f == "priority" else v for f, v in fields.items()}
                              if kind == "goal" else fields)
        self.client.call(f"update_{kind}", args)
        after = self.read(kind, rid, "full" if kind == "task" else "summary")
        wrong = [f"status read back {after.get('status')}"] if status and norm("status", after.get("status")) != status else []
        wrong += [f"{f} read back {after.get(f)!r}" for f, v in fields.items() if norm(f, after.get(f)) != norm(f, v)]
        if wrong:
            raise RuntimeError("; ".join(wrong))
        return after

    def logged(self, op, by, write, before, after, marker, changed, comment_ids=(), entity="task"):
        """Append the undo-log line for one write and remember the record in the journal."""
        key = f"{entity}_id"
        row = {"op_id": op.get("id"), "op": op.get("op"), "write": write, key: str(after["id"]).lower(),
               "title": after.get("name") if entity == "project" else after.get("title"), "by": by,
               "marker": marker, "before": {f: before.get(f) for f in changed}, "after": dict(changed),
               "updated_at_after": after.get("updated_at"), "comment_ids": [x for x in comment_ids if x],
               "evidence": op.get("evidence"), "reason": op.get("reason"),
               "at": self.now.isoformat(timespec="seconds")}
        if entity != "task":
            row["entity"] = entity
        if self.log is not None:
            append_jsonl(self.log, row)
        self.remember(key, after, op, by)
        return row

    # ---------------------------------------------------------------- task ops

    def op_complete(self, op, by, marker):
        return self.close(op, by, marker, "DONE", f"Completed: {op['reason']}\nEvidence: {op['evidence']}")

    def op_cancel(self, op, by, marker):
        if by in CHECKED_CANCELS and str(op.get("check") or "").upper() != "PASS":
            raise Refused("UNCHECKED", f"{by}'s cancels go through task-reconcile-checker whatever their "
                                       "confidence; this one carries no \"check\": \"PASS\"")
        evidence = f"\nEvidence: {op['evidence']}" if op.get("evidence") else ""
        return self.close(op, by, marker, "CANCELLED", f"Cancelled: {op['reason']}{evidence}")

    def close(self, op, by, marker, target, body):
        tid = task_id(op["task"])
        task = self.open_task(tid)
        status = norm("status", task.get("status"))
        if status == target:
            self.closing.add(tid)
            return {"outcome": "unchanged", "reason": f"already {target}"}
        if status not in OPEN:
            raise Refused("CLOSED", f"the task is {status}, not open")
        if target == "CANCELLED" and not op.get("evidence"):
            hier = task.get("_hierarchy") or {}
            if task.get("goal_id") or (hier.get("goal") or {}).get("id") or (hier.get("project") or {}).get("goal_id"):
                raise Refused("GOAL_LINKED", "the task links to a goal; cancel it only with evidence it was "
                                             "overtaken, else ask the owner")
            updated = c.parse_time(task.get("updated_at")) or c.parse_time(task.get("created_at"))
            if updated is None or self.now - updated <= self.stale_cancel:
                days = (self.now - updated).days if updated else "?"
                raise Refused("NOT_STALE", f"last updated {days} days ago; a cancel without evidence needs "
                                           f"{self.stale_cancel.days} days with no activity")
        self.evidence_holds(op)
        self.guard(task, ["status"])
        self.take_slot()
        self.closing.add(tid)
        if self.dry_run:
            return {"outcome": "would_apply", "change": {"status": [status, target]}}
        cid = None if self.has_marker(task, marker) else self.comment(tid, body, marker, by, op["id"])
        after = self.write_back("task", task, {}, target)
        row = self.logged(op, by, "update", task, after, marker, {"status": target}, [cid])
        return {"outcome": "applied", "change": {"status": [status, target]}, "undo": row["before"]}

    def op_edit(self, op, by, marker):
        tid = task_id(op["task"])
        task = self.open_task(tid)
        status = norm("status", task.get("status"))
        if status not in OPEN:
            raise Refused("CLOSED", f"the task is {status}; edit changes open tasks")
        want = {f: (None if v in ("", None) else v) for f, v in op["set"].items()}
        if "status" in want:
            want["status"] = str(want["status"]).upper()
        if want.get("priority") is not None:
            want["priority"] = norm("priority", want["priority"])
        change = {f: v for f, v in want.items() if norm(f, task.get(f)) != norm(f, v)}
        self.check_assignee(change.get("owner_contact_id"))
        final_status = change.get("status", status)
        if final_status == "WAITING" and not (change["due_date"] if "due_date" in change else task.get("due_date")):
            raise Refused("WAITING_NO_FOLLOW_UP", "a WAITING task needs a due date, its follow-up date")
        if final_status == "WAITING" and status != "WAITING":
            waiting_on = change.get("waiting_on_contact_id", task.get("waiting_on_contact_id"))
            if not (waiting_on or str(task.get("waiting_on_name") or "").strip() or task.get("assignees")):
                raise Refused("WAITING_NO_PARTY", "a task moved to WAITING names who it waits on "
                                                  "(waiting_on_contact_id)")
        if change.get("title") is not None and not c.is_next_action(str(change["title"])):
            raise Refused("NOT_NEXT_ACTION", f"the new title starts with {c.first_word(str(change['title']))!r}, "
                                             "not a verb")
        if change.get("project_id"):
            self.check_filing(change["project_id"], want.get("domain_id"))
        if not change:
            return {"outcome": "unchanged", "reason": "the task already holds these values"}
        self.evidence_holds(op)
        self.guard(task, list(change))
        self.take_slot()
        diff = {f: [task.get(f), v] for f, v in change.items()}
        if self.dry_run:
            return {"outcome": "would_apply", "change": diff}
        after = self.write_back("task", task, {f: v for f, v in change.items() if f != "status"}, change.get("status"))
        row = self.logged(op, by, "update", task, after, marker, change)
        return {"outcome": "applied", "change": diff, "undo": row["before"]}

    def check_filing(self, pid, domain_id):
        """A task filed by an edit goes into an open project, in the op's domain (when it names
        one) and inside --domain."""
        p = {str(x.get("id")).lower(): x for x in self.listing("project")}.get(str(pid).lower())
        if p is None or not live_project(p):
            raise Refused("NO_PROJECT", f"project {pid} is not an open project")
        home = str(p.get("domain_id") or "").lower() or None
        if domain_id and home and str(domain_id).lower() != home:
            raise Refused("DOMAIN_MISMATCH", f"project {pid} is in domain {home}, not {domain_id}")
        self.in_scope(home or domain_id, f"project {pid}")

    def op_merge(self, op, by, marker):
        dup_id, keep_id = task_id(op["task"]), task_id(op["into"])
        dup, keep = self.open_task(dup_id, "duplicate"), self.open_task(keep_id, "kept task")
        dup_status, keep_status = norm("status", dup.get("status")), norm("status", keep.get("status"))
        if dup_status == "DONE" and self.has_marker(dup, marker):
            return {"outcome": "unchanged", "reason": "already merged"}
        if dup_status not in OPEN:
            raise Refused("CLOSED", f"the duplicate is {dup_status}, not open")
        if keep_status not in OPEN:
            raise Refused("CLOSED", f"the kept task is {keep_status}, not open")
        owners = {str(dup.get("owner_contact_id") or "").lower(), str(keep.get("owner_contact_id") or "").lower()}
        if len(owners) != 1 or "" in owners:
            raise Refused("NOT_SAME_OWNER", "a merge needs the same owner on both tasks")
        if (str(keep.get("created_at") or ""), keep_id) > (str(dup.get("created_at") or ""), dup_id):
            raise Refused("KEEP_OLDER", "the kept task (into) must be the older one; swap task and into")
        self.evidence_holds(op)
        fill = {f: dup.get(f) for f in MERGE_FILL if not keep.get(f) and dup.get(f)}
        self.guard(dup, ["status"])
        if fill:
            self.guard(keep, list(fill))
        self.take_slot()
        change = {"duplicate": {"status": [dup_status, "DONE"]}, "kept": {f: [None, v] for f, v in fill.items()}}
        self.closing.add(dup_id)
        if self.dry_run:
            return {"outcome": "would_apply", "change": change}
        cids = []
        if not self.has_marker(keep, marker):
            lines = [f"Merged in {tref(dup_id)}, a duplicate: {dup.get('title')}", f"Why: {op['reason']}"]
            if str(dup.get("description") or "").strip():
                lines += ["", "Its description:", str(dup["description"]).strip()[:1500]]
            for x in dup.get("_comments") or []:
                lines.append(f"- {x.get('author_name') or x.get('author') or 'comment'} "
                             f"{str(x.get('created_at') or '')[:10]}: {str(x.get('body') or '')[:300]}")
            cids.append(self.comment(keep_id, "\n".join(lines)[:COMMENT_MAX - 300], marker, by, op["id"]))
        if fill:
            keep_after = self.write_back("task", keep, fill)
            self.logged(op, by, "update", keep, keep_after, marker, fill, cids)
        if not self.has_marker(dup, marker):
            cids.append(self.comment(dup_id, f"Duplicate of {tref(keep_id)}: {keep.get('title')}\nWhy: {op['reason']}",
                                     marker, by, op["id"]))
        dup_after = self.write_back("task", dup, {}, "DONE")
        self.logged(op, by, "update", dup, dup_after, marker, {"status": "DONE"}, cids[-1:])
        return {"outcome": "applied", "change": change}

    def op_create(self, op, by, marker):
        title = str(op["title"]).strip()
        if not c.is_next_action(title):
            raise Refused("NOT_NEXT_ACTION", f"the title starts with {c.first_word(title)!r}, not a verb")
        found = self.tasks_with_marker(marker)
        if found:
            return {"outcome": "unchanged", "reason": f"already created as {tref(found[0]['id'])}",
                    "task": tref(str(found[0]["id"]))}
        project, domain = str(op.get("project") or "").lower() or None, str(op.get("domain") or "").lower() or None
        projects = {str(p.get("id")).lower(): p for p in self.listing("project")}
        if project:
            p = projects.get(project)
            if p is None or not live_project(p):
                raise Refused("NO_PROJECT", f"project {project} is not an open project")
            domain = str(p.get("domain_id") or "").lower() or domain
        else:
            general = [p for p in projects.values() if p.get("is_general")
                       and str(p.get("domain_id") or "").lower() == domain and live_project(p)]
            if not general:
                raise Refused("NO_PROJECT", f"domain {domain} has no catch-all project; name the project")
            project = str(general[0]["id"]).lower()
        self.in_scope(domain, "the new task's domain")
        owner = str(op.get("owner") or "").lower() or self.owner()
        self.check_assignee(owner)
        mine = c.normalise_title(title)
        for t in self.listing("task"):
            if str(t.get("project_id") or "").lower() == project:
                score = c.similarity(mine, c.normalise_title(str(t.get("title") or "")))
                if score >= DUP_THRESHOLD:
                    raise Refused("DUPLICATE", f"{tref(str(t.get('id')))} ({t.get('title')!r}) is already it "
                                               f"(similarity {score:.2f})")
        self.evidence_holds(op)
        self.take_slot()
        description = "\n".join(x for x in (
            str(op.get("description") or "").rstrip(), f"Why: {op['reason']}",
            f"Evidence: {op['evidence']}" if op.get("evidence") else "",
            f"Captured from: {op['source']}" if op.get("source") else "",
            f"{by} via task-stack-apply, op {op['id']}. Marker: {marker}") if x)
        args = {"title": title, "project_id": project, "domain_id_or_name": domain, "owner_contact_id": owner,
                "description": description, "source_reference": marker, "due_date": op.get("due_date"),
                "priority": norm("priority", op.get("priority")), "task_contact_id": op.get("task_contact")}
        args = {k: v for k, v in args.items() if v not in (None, "")}
        if self.dry_run:
            return {"outcome": "would_apply", "change": {k: v for k, v in args.items() if k != "description"}}
        out = self.client.call("create_task", args)
        new_id = out.get("id") if isinstance(out, dict) else None
        if not new_id and isinstance(out, dict) and isinstance(out.get("task"), dict):
            new_id = out["task"].get("id")
        if not new_id:
            again = self.tasks_with_marker(marker)
            if not again:
                raise RuntimeError(f"create_task answered without an id: {str(out)[:200]}")
            new_id = again[0]["id"]
        task = self.read_task(str(new_id).lower())
        if marker not in str(task.get("description") or ""):
            raise RuntimeError("the new task read back without its marker")
        self.logged(op, by, "create", {"status": None}, task, marker, {"status": task.get("status")})
        return {"outcome": "applied", "task": tref(str(new_id).lower())}

    def op_comment(self, op, by, marker):
        tid = task_id(op["task"])
        task = self.open_task(tid)
        if self.has_marker(task, marker):
            return {"outcome": "unchanged", "reason": "this comment is already on the task"}
        self.evidence_holds(op)
        self.take_slot()
        if self.dry_run:
            return {"outcome": "would_apply", "change": {"comment": str(op["body"])[:200]}}
        cid = self.comment(tid, str(op["body"]), marker, by, op["id"])
        if cid is None:
            raise RuntimeError("create_task_comment answered without an id")
        after = self.read_task(tid)
        self.logged(op, by, "comment", {}, after, marker, {}, [cid])
        return {"outcome": "applied", "comment_id": cid}

    # ---------------------------------------------------------------- project ops

    def open_project(self, pid, full=False):
        project = self.read("project", pid, "full" if full else "summary")
        if project.get("is_archived"):
            raise Refused("CLOSED", "the project is archived")
        if project.get("is_general"):
            raise Refused("BUCKET", "the project is a domain's catch-all bucket, not a project; drain its "
                                    "tasks into real projects instead")
        status = norm("status", project.get("status"))
        if status in PROJECT_CLOSE_STATUSES or status == "ARCHIVED":
            raise Refused("CLOSED", f"the project is {status}")
        assignee = str(project.get("assignee_contact_id") or "").lower()
        if assignee and assignee != self.owner():
            raise Refused("NOT_OWNER", "the project is another person's; only the owner's projects are changed")
        self.in_scope(project.get("domain_id"), "the project")
        return project

    def op_project_edit(self, op, by, marker):
        project = self.open_project(project_id(op["project"]))
        want = {f: (None if v in ("", None) else v) for f, v in op["set"].items()}
        if want.get("status"):
            want["status"] = str(want["status"]).upper()
        if want.get("priority") is not None:
            want["priority"] = norm("priority", want["priority"])
        change = {f: v for f, v in want.items() if norm(f, project.get(f)) != norm(f, v)}
        if "status" in change and change["status"] is None:
            raise Refused("INVALID_OP", "a project's status cannot be cleared")
        if change.get("goal_id"):
            goal = {str(g.get("id")).lower(): g for g in self.listing("goal")}.get(str(change["goal_id"]).lower())
            if goal is None or goal.get("is_archived") or norm("status", goal.get("status")) in CLOSED_GOAL:
                raise Refused("NO_GOAL", f"goal {change['goal_id']} is not an active goal")
            home, there = str(project.get("domain_id") or "").lower(), str(goal.get("domain_id") or "").lower()
            if home and there and home != there:
                raise Refused("DOMAIN_MISMATCH", f"goal {change['goal_id']} is in domain {there}, the project in {home}")
        if change.get("assignee_contact_id") and project.get("assignee_contact_id"):
            raise Refused("NOT_OWNER", "the project already has an owner; changing it is the owner's call")
        self.check_assignee(change.get("assignee_contact_id"))
        if not change:
            return {"outcome": "unchanged", "reason": "the project already holds these values"}
        self.evidence_holds(op)
        self.guard(project, list(change), "project_id")
        self.take_slot()
        diff = {f: [project.get(f), v] for f, v in change.items()}
        if self.dry_run:
            return {"outcome": "would_apply", "change": diff}
        after = self.write_back("project", project, change)
        row = self.logged(op, by, "project_update", project, after, marker, change, entity="project")
        return {"outcome": "applied", "change": diff, "undo": row["before"]}

    def op_project_close(self, op, by, marker):
        pid = project_id(op["project"])
        target = str(op.get("status") or "CANCELLED").upper()
        if norm("status", self.read("project", pid, "summary").get("status")) == target:
            return {"outcome": "unchanged", "reason": f"already {target}"}
        project = self.open_project(pid, full=True)
        still_open = sorted(project["_open"] - self.closing)
        if still_open:
            raise Refused("OPEN_TASKS", f"{len(still_open)} open task(s) remain (first {tref(still_open[0])}); "
                                        "close or move them first, in the same change set")
        if op.get("evidence"):
            self.evidence_holds(op)
        else:
            if project.get("goal_id"):
                raise Refused("GOAL_LINKED", "the project links to a goal; close it only with evidence, else ask "
                                             "the owner")
            bulk = c.bulk_minutes(self.listing("project"))
            # This script's own writes (a task it just cancelled) are not activity on the project.
            mine = self.journal("task_id")
            tasks = [{k: v for k, v in t.items() if k not in ("updated_at", "completed_at")}
                     if (mine.get(str(t.get("id")).lower()) or {}).get("updated_at") == t.get("updated_at")
                     else t for t in project["_tasks"]]
            latest, _ = c.last_activity(project, tasks, bulk)
            if latest is None or self.now - latest <= self.stale_close:
                days = (self.now - latest).days if latest else "?"
                raise Refused("NOT_STALE", f"last activity {days} days ago; a close without evidence needs "
                                           f"{self.stale_close.days} days with no activity")
        self.guard(project, ["status"], "project_id")
        self.take_slot()
        status = norm("status", project.get("status"))
        if self.dry_run:
            return {"outcome": "would_apply", "change": {"status": [status, target]}}
        after = self.write_back("project", project, {"status": target})
        row = self.logged(op, by, "project_update", project, after, marker, {"status": target}, entity="project")
        return {"outcome": "applied", "change": {"status": [status, target]}, "undo": row["before"]}

    # ---------------------------------------------------------------- goal ops

    def open_goal(self, gid):
        goal = self.read("goal", gid, "summary")
        if goal.get("is_archived"):
            raise Refused("CLOSED", "the goal is archived")
        if goal.get("is_general"):
            raise Refused("BUCKET", "the goal is a domain's catch-all, not a goal the owner set")
        if norm("status", goal.get("status")) in CLOSED_GOAL:
            raise Refused("CLOSED", f"the goal is {norm('status', goal.get('status'))}")
        assignee = str(goal.get("assignee_contact_id") or "").lower()
        if assignee and assignee != self.owner():
            raise Refused("NOT_OWNER", "the goal is another person's; only the owner's goals are changed")
        self.in_scope(goal.get("domain_id"), "the goal")
        return goal

    def op_goal_edit(self, op, by, marker):
        gid = goal_id(op["goal"])
        goal = self.open_goal(gid)
        want = {}
        for f, v in op["set"].items():
            v = None if v in ("", None) else v
            if f in ("status", "horizon") and v is not None:
                v = str(v).upper()
            if f == "priority":
                v = portal_priority(v)
            if f == "title" and v is not None:
                v = " ".join(str(v).split())
            want[f] = v
        change = {f: v for f, v in want.items() if norm(f, goal.get(f)) != norm(f, v)}
        for f in ("status", "priority", "title"):
            if f in change and change[f] is None:
                raise Refused("INVALID_OP", f"a goal's {f} cannot be cleared")
        if not change:
            return {"outcome": "unchanged", "reason": "the goal already holds these values"}
        self.evidence_holds(op)
        self.guard(goal, list(change), "goal_id")
        self.take_slot()
        diff = {f: [goal.get(f), v] for f, v in change.items()}
        if self.dry_run:
            return {"outcome": "would_apply", "change": diff}
        after = self.write_back("goal", goal, change)
        row = self.logged(op, by, "goal_update", goal, after, marker, change, entity="goal")
        return {"outcome": "applied", "change": diff, "undo": row["before"]}

    def op_goal_close(self, op, by, marker):
        gid = goal_id(op["goal"])
        target = str(op.get("status") or "CANCELLED").upper()
        if norm("status", self.read("goal", gid, "summary").get("status")) == target:
            return {"outcome": "unchanged", "reason": f"already {target}"}
        goal = self.open_goal(gid)
        # Projects an earlier op of this set closed, or moved to another goal (or would, dry).
        settled = set()
        for prior, result in self.done:
            pid = project_id(prior.get("project"))
            if not pid or result.get("outcome") not in ("applied", "would_apply", "unchanged"):
                continue
            moved = prior.get("op") == "project_edit" and "goal_id" in (prior.get("set") or {}) \
                and str(prior["set"].get("goal_id") or "").lower() != gid
            if prior.get("op") == "project_close" or moved:
                settled.add(pid)
        projects, _ = c.page_through(self.client, "project")
        driving = sorted(str(p.get("id")).lower() for p in projects
                         if str(p.get("goal_id") or "").lower() == gid and c.is_active_project(p)
                         and str(p.get("id")).lower() not in settled)
        if driving:
            raise Refused("ACTIVE_PROJECTS", f"{len(driving)} active project(s) still serve the goal (first "
                                             f"portal://project/{driving[0]}); close or relink them first, in the "
                                             "same change set")
        goals, _ = c.page_through(self.client, "goal")
        subs = [g for g in goals if str(g.get("parent_goal_id") or "").lower() == gid and c.is_active_goal(g)]
        if subs:
            raise Refused("ACTIVE_SUBGOALS", f"{len(subs)} active sub-goal(s) sit under it; close or move them first")
        self.evidence_holds(op)
        self.guard(goal, ["status"], "goal_id")
        self.take_slot()
        status = norm("status", goal.get("status"))
        if self.dry_run:
            return {"outcome": "would_apply", "change": {"status": [status, target]}}
        after = self.write_back("goal", goal, {"status": target})
        row = self.logged(op, by, "goal_update", goal, after, marker, {"status": target}, entity="goal")
        return {"outcome": "applied", "change": {"status": [status, target]}, "undo": row["before"]}

    # ---------------------------------------------------------------- one op

    def one(self, op):
        is_dict = isinstance(op, dict)
        base = {"id": op.get("id") if is_dict else None, "op": op.get("op") if is_dict else None,
                "task": op.get("task") if is_dict else None}
        if is_dict and op.get("op") in PROJECT_OPS and op.get("project"):
            base["project"] = op["project"]
        problems = shape_problems(op)
        if problems:
            return dict(base, outcome="refused", code="INVALID_OP", reason="; ".join(problems))
        by = str(op.get("by") or self.orchestrator or "")
        if not AGENT.match(by):
            return dict(base, outcome="refused", code="INVALID_OP",
                        reason="no producing orchestrator: give the op `by` or the set `orchestrator`")
        marker = marker_for(by, op)
        base.update(by=by, marker=marker, reason=op.get("reason"), evidence=op.get("evidence"))
        if op.get("into"):
            base["into"] = op["into"]
        if op["op"] in GOAL_OPS:
            base["goal"] = f"portal://goal/{goal_id(op['goal'])}"
        try:
            result = getattr(self, f"op_{op['op']}")(op, by, marker)
        except Refused as exc:
            return dict(base, outcome="deferred" if exc.code == "DEFERRED" else "refused",
                        code=exc.code, reason=exc.reason)
        except Exception as exc:  # one op failing is that op's result, not the run's
            return dict(base, outcome="failed", reason=c.safe(f"{type(exc).__name__}: {exc}"))
        self.done.append((op, result))
        return dict(base, **result)


def apply(client, data, dry_run, state, log, domain="", max_changes=MAX_CHANGES, hand_edit_days=HAND_EDIT_DAYS,
          stale_cancel_days=STALE_CANCEL_DAYS, stale_close_days=STALE_CLOSE_DAYS, now=None):
    """Apply a change set. Raises Refused when the whole set is refused."""
    changes, ops = load_changes(data)
    if changes["dry_run"] and not dry_run:
        raise Refused("DRY_RUN", "the change set was written by a dry-run session; apply it with --dry-run")
    applier = Applier(client, dry_run, state, None if dry_run else log, changes.get("orchestrator"), domain,
                      max_changes, hand_edit_days, stale_cancel_days, stale_close_days, now)
    results = [applier.one(op) for op in ops]
    counts = {}
    for r in results:
        per = counts.setdefault(str(r.get("op")), {})
        per[r["outcome"]] = per.get(r["outcome"], 0) + 1
    outcomes = {r["outcome"] for r in results}
    status = ("nothing" if not results else "would_apply" if dry_run
              else "partial" if "failed" in outcomes else "applied")
    return {"tool": "task-stack-apply", "status": status, "dry_run": dry_run,
            "orchestrator": changes.get("orchestrator"), "ops": len(ops), "writes": applier.writes,
            "max_changes": max_changes, "domain": domain or None, "counts": counts, "results": results,
            "questions": changes.get("questions") or [],
            "at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")}


# --------------------------------------------------------------------------- undo

def undo(client, rows, dry_run, state, op_id=None, now=None):
    """Put back what the log's writes changed, newest first, only where the record still holds
    the new values (a person's later change is kept). A create is undone by cancelling the
    task and a comment by a retraction comment; nothing is deleted."""
    picked = [r for r in rows if op_id is None or str(r.get("op_id")) == op_id]
    if op_id is not None and not picked:
        raise c.Stop(f"the log has no write for op {op_id}")
    applier = Applier(client, dry_run, state, None, "task-stack-undo", max_changes=10 ** 6, now=now)
    results = []
    for row in reversed(picked):
        entity = row.get("entity") or "task"
        rid = str(row.get(f"{entity}_id") or "").lower()
        out = {"op_id": row.get("op_id"), "write": row.get("write"), entity: f"portal://{entity}/{rid}"}
        try:
            results.append(dict(out, **undo_one(applier, row, entity, rid, dry_run)))
        except Exception as exc:
            results.append(dict(out, outcome="failed", reason=c.safe(f"{type(exc).__name__}: {exc}")))
    counts = {}
    for r in results:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    status = "would_undo" if dry_run else ("partial" if counts.get("failed") else "undone")
    return {"tool": "task-stack-undo", "status": status, "dry_run": dry_run, "counts": counts, "results": results}


def undo_one(applier, row, entity, rid, dry_run):
    op = {"id": f"undo-{row.get('op_id')}", "op": "undo"}
    marker = str(row.get("marker") or "")
    record = applier.read(entity, rid, "full" if entity == "task" else "summary")
    if entity == "task" and row.get("write") == "comment":
        if dry_run:
            return {"outcome": "would_undo", "change": "a retraction comment"}
        cid = applier.comment(rid, f"Retracted: the comment {', '.join(row.get('comment_ids') or [])} "
                                   f"({marker}) was undone.", marker, "task-stack-undo", op["id"])
        return {"outcome": "undone", "comment_id": cid}
    if entity == "task" and row.get("write") == "create":
        status = norm("status", record.get("status"))
        if status == "CANCELLED":
            return {"outcome": "unchanged", "reason": "already cancelled"}
        if dry_run:
            return {"outcome": "would_undo", "change": {"status": [status, "CANCELLED"]}}
        applier.comment(rid, "Cancelled: this task was created in error and its creation was undone.",
                        marker, "task-stack-undo", op["id"])
        applier.remember("task_id", applier.write_back("task", record, {}, "CANCELLED"), op, "task-stack-undo")
        return {"outcome": "undone", "change": {"status": [status, "CANCELLED"]}}
    after_vals, before_vals = row.get("after") or {}, row.get("before") or {}
    if all(norm(f, record.get(f)) == norm(f, v) for f, v in before_vals.items()):
        return {"outcome": "unchanged", "reason": f"the {entity} already holds the old values"}
    moved = [f for f, v in after_vals.items() if norm(f, record.get(f)) != norm(f, v)]
    if moved:
        return {"outcome": "refused", "code": "CHANGED_SINCE",
                "reason": f"{', '.join(moved)} changed since the write; a person's later change is kept"}
    if entity == "task":
        status = before_vals.get("status")
        fields = {f: v for f, v in before_vals.items() if f != "status"}
        diff = {f: [record.get(f), v] for f, v in before_vals.items()}
    else:
        cannot_clear = ("status",) if entity == "project" else ("status", "priority", "title")
        status = None
        fields = {f: v for f, v in before_vals.items() if not (f in cannot_clear and v in (None, ""))}
        diff = {f: [record.get(f), v] for f, v in fields.items()}
    if dry_run:
        return {"outcome": "would_undo", "change": diff}
    if entity == "task":
        applier.comment(rid, f"Undone: {', '.join(before_vals)} put back to the value before op {row.get('op_id')}.",
                        marker, "task-stack-undo", op["id"])
    after = applier.write_back(entity, record, fields, norm("status", status) if status else None)
    applier.remember(f"{entity}_id", after, op, "task-stack-undo")
    return {"outcome": "undone", "change": diff}


# --------------------------------------------------------------------------- command line

def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise c.Stop(f"{path} could not be read ({type(exc).__name__})") from None
    except json.JSONDecodeError as exc:
        raise c.Stop(f"{path} is not JSON ({exc.msg} at line {exc.lineno})") from None


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="task_stack_apply.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("changes_path", nargs="?", help="A change set file (or use --run)")
    p.add_argument("--run", dest="run_dir", help="The Run folder: reads changes.json, writes apply.json and undo.jsonl")
    p.add_argument("--dry-run", action="store_true", help="Read and check everything, write nothing")
    p.add_argument("--dry-run-if", help="true or false (a scheduler placeholder); true is --dry-run")
    p.add_argument("--log", dest="log_path", help="The undo log (default RUN/undo.jsonl, or beside the change set)")
    p.add_argument("--out", dest="out_path", help="Where to write the results (default RUN/apply.json or apply-dry-run.json)")
    p.add_argument("--domain", default="", help="Only ops on records in this domain (id, or name contains)")
    p.add_argument("--max-changes", default=str(MAX_CHANGES), help="At most this many writes")
    p.add_argument("--hand-edit-days", type=int, default=HAND_EDIT_DAYS)
    p.add_argument("--stale-cancel-days", type=int, default=STALE_CANCEL_DAYS)
    p.add_argument("--stale-close-days", type=int, default=STALE_CLOSE_DAYS,
                   help="A project closed without evidence has had no activity for this many days")
    p.add_argument("--state", dest="state_path", help="The write journal and lock (default <state_dir>/task-stack)")
    p.add_argument("--undo", dest="undo_log", help="Undo the writes in this undo log instead of applying")
    p.add_argument("--op", dest="op_id", help="With --undo, only this op's writes")
    p.add_argument("--config", help="MCP config holding the Portal (default: setting portal_mcp_config)")
    p.add_argument("--server", help="Server name in the MCP config (default: setting portal_server)")
    return p.parse_args(argv)


def main(argv=None, client=None):
    args = parse_args(argv)
    try:
        dry_run = args.dry_run or (truthy_flag(args.dry_run_if) if args.dry_run_if is not None else False)
        for name, value, low, high in (("hand-edit-days", args.hand_edit_days, 0, 365),
                                       ("stale-cancel-days", args.stale_cancel_days, 1, 3650),
                                       ("stale-close-days", args.stale_close_days, 1, 3650)):
            if not low <= value <= high:
                raise c.Stop(f"--{name} is {low} to {high}")
        if args.undo_log:
            log = c.guard_run_path(args.undo_log)
            if not log.is_file():
                raise c.Stop(f"{log} does not exist")
            rows = read_jsonl(log)
            state = c.state_root(args.state_path)
            with locked(state):
                result = undo(client or c.Portal(args.config, args.server), rows, dry_run, state, args.op_id)
            if not dry_run:
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                atomic_json(log.with_name(f"{log.stem}.undone-{stamp}.json"), result)
            c.emit(result, 3 if result["status"] == "partial" else 0)
        if not re.fullmatch(r"\d{1,5}", str(args.max_changes).strip()):
            raise c.Stop(f"--max-changes wants a whole number, got {args.max_changes!r}")
        cap = int(str(args.max_changes).strip())
        if bool(args.changes_path) == bool(args.run_dir):
            raise c.Stop("give the change set file or --run, one of them")
        run = c.guard_run_path(args.run_dir) if args.run_dir else None
        source = run / "changes.json" if run else c.guard_run_path(args.changes_path)
        if not source.is_file():
            raise c.Stop(f"{source} does not exist; nothing was written")
        log = (c.guard_run_path(args.log_path) if args.log_path
               else (run / "undo.jsonl" if run else source.with_name("undo.jsonl")))
        target = (c.guard_run_path(args.out_path) if args.out_path
                  else (run / ("apply-dry-run.json" if dry_run else "apply.json")) if run else None)
        data = read_json(source)
        state = c.state_root(args.state_path)
        with locked(state):
            try:
                result = apply(client or c.Portal(args.config, args.server), data, dry_run, state, log, args.domain,
                               cap, args.hand_edit_days, args.stale_cancel_days, args.stale_close_days)
            except Refused as exc:
                c.emit({"tool": "task-stack-apply", "status": "refused", "code": exc.code, "reason": exc.reason,
                        "written": 0}, 3)
        result["changes"] = str(source)
        if not dry_run:
            result["undo_log"] = str(log)
        if target is not None:
            atomic_json(target, result)
            result["out"] = str(target)
    except (c.Stop, c.PortalError) as exc:
        c.emit({"status": "error", "reason": str(exc)}, 2)
    c.emit(result, 3 if result["status"] == "partial" else 0)


if __name__ == "__main__":
    main()
