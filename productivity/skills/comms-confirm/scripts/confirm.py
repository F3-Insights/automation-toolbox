#!/usr/bin/env python3
"""Confirmation requests: ask a person to confirm something, record it, notice the answer.

    python3 scripts/confirm.py who FOLDER --role ROLE
    python3 scripts/confirm.py new STORE --question TEXT --of ROLE --channel CH [...]
    python3 scripts/confirm.py task STORE ID [--domain D] [--project UUID] [--dry-run]
    python3 scripts/confirm.py record STORE ID [--draft ID] [--subject TEXT] [--thread REF]
    python3 scripts/confirm.py check PATH [PATH ...] [--today yyyy-mm-dd] [--no-portal]
    python3 scripts/confirm.py close STORE ID --by WHO (--answer TEXT | --assumed | --withdrawn)
    python3 scripts/confirm.py reopen STORE ID --by WHO [--note TEXT]
    python3 scripts/confirm.py relay PATH [PATH ...] [--dry-run]
    python3 scripts/confirm.py remind [PATH ...] [--today yyyy-mm-dd] [--dry-run]
    python3 scripts/confirm.py list STORE

STORE is the caller's CONFIRMATIONS.md, a plain markdown file in the work's own folder (for an
engagement folder, the period folder). It is created on the first `new`. A person may type an
answer on a request's `- Answer:` line; the next `check` records it. The contract is in
rules.md beside this skill.

Standard library only. The Portal is reached through one script, `confirm_portal.py` beside
this one, which reads a JSON request on stdin and prints JSON; set CONFIRM_PORTAL_CMD to run
another program in its place. Nothing here writes to anyone but the owner: an email is a draft
made by the caller's drafting skill, and `record` only notes its id and subject. `relay` and
`remind` send the owner one message through the comms-reply-to-email skill's script,
`python3 ~/.claude/skills/comms-reply-to-email/scripts/notify_owner.py`; set CONFIRM_NOTIFY_CMD
to run another program in its place. Nothing is looked up on PATH.

Delivery is a setting. `relay`, the default, asks the owner to put the question to the person
and records the request as waiting on them; `direct` lets the caller draft an email to the
person. It is `--delivery` on `new`, else CONFIRM_DELIVERY, else relay.

Exit 0, 2 when an argument or a file is wrong or the Portal or the notifier could not be
reached, 3 when a request refuses the change (unknown id, a closed request, a missing answer).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

STORE_NAME = "CONFIRMATIONS.md"
CHANNELS = ("owner", "task", "email")
FALLBACKS = ("proceed", "escalate", "wait")
STATES = ("open", "answered", "closed")
DELIVERIES = ("relay", "direct")
DEFAULT_DELIVERY = "relay"
DEFAULT_DUE_BUSINESS_DAYS = 1
FIELDS = ("Question", "State", "Asked of", "Person", "Contact", "Portal user", "Channels", "Delivery",
          "Asked at", "Due", "Fallback", "Context", "Record", "Task", "Email subject", "Email thread", "Draft",
          "Relayed", "Reminded", "Answer", "Answered by", "Evidence", "Answered at", "Seen", "Log")
ID_RE = re.compile(r"^CR-[0-9a-f]{10}$")
HEAD_RE = re.compile(r"^## (CR-[0-9a-f]{10})\s*$")
FIELD_RE = re.compile(r"^- ([A-Za-z ]+):[ \t]?(.*)$")
UUID_RE = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
ROLE_RE = re.compile(r"^\s*[-*]\s+(?P<role>[^:]+?):\s*(?P<name>[^<]*?)\s*(?:<(?P<email>[^>\s]+@[^>\s]+)>)?\s*$")
HOW = {"task": "task", "email": "email draft", "owner": "question to owner"}
URL_IN_TEXT = re.compile(r"https?://\S+", re.I)
QUESTION_CHARS = 200

HEADER = """# Confirmations

Questions this work has put to people, one section each. To answer one by hand, type it after
`- Answer:` and, if you like, your name after `- Answered by:`; the next check records it.
Everything else here is kept by the confirm script.
"""


class Refused(Exception):
    """A request refuses the change: exit 3."""


class Bad(Exception):
    """An argument or a file is wrong, or the Portal could not be reached: exit 2."""


# ---------------------------------------------------------------------------------------------
# Time


def now_stamp(at: Optional[str] = None) -> str:
    """ISO minutes with the local offset, so a Portal time in UTC compares correctly."""
    if at:
        try:
            moment = datetime.fromisoformat(at)
        except ValueError:
            raise Bad(f"--at {at!r} is not an ISO date and time") from None
        return (moment if moment.tzinfo else moment.astimezone()).isoformat(timespec="minutes")
    return datetime.now().astimezone().isoformat(timespec="minutes")


def parse_day(text: str) -> Optional[date]:
    try:
        return date.fromisoformat(str(text or "").strip()[:10])
    except ValueError:
        return None


def short_day(day: Optional[date]) -> str:
    """`Mon 5 Oct`, the way a person reads a date in a message."""
    return f"{day:%a} {day.day} {day:%b}" if day else "an unknown day"


def add_business_days(start: date, days: int) -> date:
    """`days` whole business days after `start`, weekends skipped. One business day after a
    Friday is the Monday: the answer is wanted by the end of the next full working day."""
    out = start
    while days > 0:
        out += timedelta(days=1)
        if out.weekday() < 5:
            days -= 1
    return out


# ---------------------------------------------------------------------------------------------
# The store


def request_id(scope: str, question: str, role: str) -> str:
    key = "\n".join((scope.strip(), " ".join(question.split()).casefold(), " ".join(role.split()).casefold()))
    return "CR-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:10]


def one_line(text: Any) -> str:
    return " ".join(str(text or "").split())


class Store:
    """CONFIRMATIONS.md as lines; each request is a `## CR-...` section of `- Field: value` lines.

    Only the lines of the fields it is told to change are rewritten, so any other text a person
    adds stays where it was."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.lines: List[str] = (self.path.read_text(encoding="utf-8").splitlines()
                                 if self.path.is_file() else HEADER.rstrip("\n").splitlines())

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(self.lines).rstrip("\n") + "\n", encoding="utf-8")

    def spans(self) -> Dict[str, Tuple[int, int]]:
        out: Dict[str, Tuple[int, int]] = {}
        heads = [(i, m.group(1)) for i, ln in enumerate(self.lines) if (m := HEAD_RE.match(ln))]
        for k, (i, rid) in enumerate(heads):
            end = next((j for j in range(i + 1, len(self.lines)) if self.lines[j].startswith(("## ", "# "))),
                       len(self.lines))
            out[rid] = (i, end)
        return out

    def ids(self) -> List[str]:
        return list(self.spans())

    def get(self, rid: str) -> Dict[str, str]:
        span = self.spans().get(rid)
        if span is None:
            raise Refused(f"no request {rid} in {self.path.name}")
        out = {"Id": rid}
        for line in self.lines[span[0] + 1: span[1]]:
            m = FIELD_RE.match(line)
            if m and m.group(1).strip() in FIELDS:
                out.setdefault(m.group(1).strip(), m.group(2).strip())
        return out

    def all(self) -> List[Dict[str, str]]:
        return [self.get(rid) for rid in self.ids()]

    def set(self, rid: str, name: str, value: str) -> None:
        start, end = self.spans()[rid]
        for i in range(start + 1, end):
            m = FIELD_RE.match(self.lines[i])
            if m and m.group(1).strip() == name:
                self.lines[i] = f"- {name}: {one_line(value)}".rstrip()
                return
        last = max((i for i in range(start + 1, end) if FIELD_RE.match(self.lines[i])), default=start)
        self.lines.insert(last + 1, f"- {name}: {one_line(value)}".rstrip())

    def append(self, rid: str, name: str, value: str) -> None:
        have = self.get(rid).get(name, "")
        self.set(rid, name, f"{have}; {value}" if have else value)

    def add(self, rid: str, fields: Dict[str, str]) -> None:
        while self.lines and not self.lines[-1].strip():
            self.lines.pop()
        self.lines += ["", f"## {rid}", ""]
        self.lines += [f"- {name}: {one_line(fields.get(name, ''))}".rstrip() for name in FIELDS]

    def log(self, rid: str, at: str, by: str, what: str) -> None:
        self.append(rid, "Log", f"{at[:16].replace('T', ' ')} {what} by {one_line(by)}")


# ---------------------------------------------------------------------------------------------
# The record: an engagement folder's Waiting on row, or a caller's file


def waiting_rows():
    """waiting.py beside this script: it keeps an engagement folder's Waiting on rows."""
    path = Path(__file__).resolve().parent / "waiting.py"
    spec = importlib.util.spec_from_file_location("comms_confirm_waiting", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_record(value: str) -> Dict[str, str]:
    """`waiting-on W3 in ../.. period 2026-09` or `file notes/answers.md`; paths are relative to
    the store's folder."""
    m = re.match(r"^waiting-on (W\d+) in (.+?) period (\d{4}-\d{2})$", value.strip())
    if m:
        return {"kind": "waiting-on", "row": m.group(1), "folder": m.group(2), "period": m.group(3)}
    m = re.match(r"^file (.+)$", value.strip())
    if m:
        return {"kind": "file", "path": m.group(1)}
    return {"kind": "none"} if not value.strip() else {"kind": "unknown", "text": value}


def engagement_row(store: Path, rec: Dict[str, str]) -> Dict[str, str]:
    """The Waiting on row a request is linked to, as {column: value}, or {} when unreadable."""
    waiting = waiting_rows()
    try:
        return waiting.row((store.parent / rec["folder"]).resolve(), rec["row"], rec["period"])
    except waiting.ContractError:
        return {}


def write_record(store: Path, req: Dict[str, str], state: str, answer: str, by: str, at: str) -> str:
    """Carry an answer or a close to the request's record. Returns what was done, in words."""
    rec = parse_record(req.get("Record", ""))
    if rec["kind"] == "waiting-on":
        waiting = waiting_rows()
        folder = (store.parent / rec["folder"]).resolve()
        stamp = at[:16].replace("T", " ")
        try:
            if state == "answered":
                waiting.answer(folder, by, rec["row"], answer, period=rec["period"], at=stamp)
            else:
                waiting.close(folder, by, rec["row"], answer or None, period=rec["period"], at=stamp)
        except waiting.ContractError as exc:
            raise Refused(f"the Waiting on row {rec['row']} refused the change: {exc}") from None
        return f"Waiting on {rec['row']} {state}"
    if rec["kind"] == "file":
        target = (store.parent / rec["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(f"- {at[:16].replace('T', ' ')} {req['Id']} {state} by {one_line(by)}: "
                     f"{one_line(req.get('Question'))} Answer: {one_line(answer)}\n")
        return f"{rec['path']} appended"
    return "no record to update"


# ---------------------------------------------------------------------------------------------
# The Portal, through one command


NOTIFY_SCRIPT = "~/.claude/skills/comms-reply-to-email/scripts/notify_owner.py"


def portal_argv() -> List[str]:
    """CONFIRM_PORTAL_CMD, else python3 and confirm_portal.py beside this script."""
    override = os.environ.get("CONFIRM_PORTAL_CMD")
    if override:
        return shlex.split(override)
    return [sys.executable or "python3", str(Path(__file__).resolve().parent / "confirm_portal.py")]


def notify_argv() -> List[str]:
    """CONFIRM_NOTIFY_CMD, else python3 and the comms-reply-to-email skill's notify_owner.py."""
    override = os.environ.get("CONFIRM_NOTIFY_CMD")
    if override:
        return shlex.split(override)
    return [sys.executable or "python3", str(Path(NOTIFY_SCRIPT).expanduser())]


def portal(command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run `confirm_portal.py COMMAND` with the payload as JSON on stdin; its JSON answer back."""
    base = portal_argv()
    try:
        done = subprocess.run(base + [command], input=json.dumps(payload), capture_output=True, text=True,
                              timeout=300)
    except FileNotFoundError:
        raise Bad(f"{base[0]} was not found; it is the Portal half of this skill "
                  "(run check with --no-portal to read only the local records)") from None
    except subprocess.TimeoutExpired:
        raise Bad(f"{base[0]} {command} took longer than five minutes") from None
    try:
        out = json.loads(done.stdout or "{}")
    except ValueError:
        raise Bad(f"{base[0]} {command} printed no JSON (exit {done.returncode}): "
                  f"{(done.stderr or done.stdout).strip()[:300]}") from None
    if done.returncode != 0 or out.get("status") == "error":
        raise Bad(f"{base[0]} {command} failed: {out.get('reason') or done.stderr.strip()[:300]}")
    return out


# ---------------------------------------------------------------------------------------------
# Commands


def bare_role(text: str) -> str:
    """'The AP lead' and 'AP lead' are the same role."""
    out = one_line(text).casefold()
    return out[4:] if out.startswith("the ") else out


def is_owner(role: str) -> bool:
    return bare_role(role) == "owner"


def delivery_setting(value: Optional[str] = None) -> str:
    """`relay` or `direct`: the argument, else CONFIRM_DELIVERY, else relay."""
    out = one_line(value or os.environ.get("CONFIRM_DELIVERY") or DEFAULT_DELIVERY).lower()
    if out not in DELIVERIES:
        raise Bad(f"delivery is one of: {', '.join(DELIVERIES)} (got {out!r})")
    return out


def who(folder: Path, role: str) -> Dict[str, str]:
    """The person a role maps to in BACKGROUND.md's Roles: a bullet `- Role: Name <address>`."""
    path = Path(folder) / "BACKGROUND.md"
    if not path.is_file():
        raise Refused(f"{path.name} not found in the folder; resolve the role from the caller's context")
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.strip().lower() == "## roles"), None)
    if start is None:
        raise Refused("BACKGROUND.md has no ## Roles section")
    want = bare_role(role)
    hits = []
    for line in lines[start + 1:]:
        if line.startswith("#"):
            break
        m = ROLE_RE.match(line)
        if m and bare_role(m.group("role")) == want:
            hits.append({"role": one_line(m.group("role")), "name": one_line(m.group("name")),
                         "email": (m.group("email") or "").lower()})
    if not hits:
        raise Refused(f"no '- {role}: Name <address>' line under ## Roles; the role is in prose or absent, "
                      "so resolve it by judgment or ask the owner")
    if len(hits) > 1:
        raise Refused(f"{len(hits)} people are listed for {role}; ask the owner which one")
    return hits[0]


def new(store_path: Path, question: str, of: str, channels: List[str], person: str = "", contact: str = "",
        user: str = "", due: Optional[str] = None, due_days: int = DEFAULT_DUE_BUSINESS_DAYS,
        fallback: str = "escalate", assume: str = "", context: Optional[List[str]] = None,
        engagement: Optional[Path] = None, period: Optional[str] = None, phase: str = "",
        record_file: Optional[str] = None, scope: Optional[str] = None, by: str = "", at: Optional[str] = None,
        escalates: str = "", delivery: Optional[str] = None) -> Dict[str, Any]:
    question = one_line(question)
    delivery = delivery_setting(delivery)
    if not question or not one_line(of):
        raise Bad("--question and --of must say something")
    if len(question) > 300 or question.count("?") > 1:
        raise Bad("a question is one answerable sentence, at most 300 characters and one question mark")
    channels = [c.strip().lower() for c in channels]
    if not channels or any(c not in CHANNELS for c in channels):
        raise Bad(f"--channel is one or more of: {', '.join(CHANNELS)}")
    if fallback not in FALLBACKS:
        raise Bad(f"--fallback is one of: {', '.join(FALLBACKS)}")
    if fallback == "proceed" and not one_line(assume):
        raise Bad("--fallback proceed needs --assume: what the work assumes when no answer comes")
    if contact and not UUID_RE.search(contact):
        raise Bad("--contact is the person's Portal contact id")
    if user and not UUID_RE.search(user):
        raise Bad("--user is the person's Portal user id")
    if "email" in channels and delivery == "relay":
        raise Bad("delivery is relay: the owner puts the question to the person, so no email is drafted to "
                  "them; use the task channel (delivery direct is the setting that allows email)")
    if "email" in channels and not contact:
        raise Bad("the email channel needs --contact, so a reply from the person can be found")
    if engagement and record_file:
        raise Bad("a request has one record: --engagement or --record-file, not both")
    stamp = now_stamp(at)
    due_day = parse_day(due) if due else add_business_days(parse_day(stamp), due_days)
    if due_day is None:
        raise Bad(f"--due {due!r} is not yyyy-mm-dd")
    store_path = Path(store_path)
    store = Store(store_path)
    if escalates and escalates not in store.ids():
        raise Refused(f"--escalates {escalates}: no such request in {store_path.name}")
    rid = request_id(scope if scope is not None else str(store_path.resolve()), question, of)
    if rid in store.ids():
        have = store.get(rid)
        return {"id": rid, "outcome": "existing", "state": have.get("State"), "record": have.get("Record"),
                "task": have.get("Task"), "draft": have.get("Draft"), "store": str(store_path)}
    record = ""
    if engagement:
        waiting = waiting_rows()
        folder = Path(engagement)
        how = HOW[next(c for c in ("task", "email", "owner") if c in channels)]
        try:
            period = waiting.current_period(folder.resolve(), period)
            row = waiting.ask(folder.resolve(), by or "comms-confirm", f"{question} ({rid})", of, how, phase,
                             period=period, at=stamp[:16].replace("T", " "))
        except waiting.ContractError as exc:
            raise Refused(f"the engagement folder refused the Waiting on row: {exc}") from None
        rel = os.path.relpath(folder.resolve(), store_path.resolve().parent)
        record = f"waiting-on {row} in {Path(rel).as_posix()} period {period}"
    elif record_file:
        record = f"file {record_file}"
    fallback_text = f"{fallback}: {one_line(assume)}" if assume else fallback
    store.add(rid, {"Question": question, "State": "open", "Asked of": of, "Person": person,
                    "Contact": contact, "Portal user": user, "Channels": ", ".join(channels),
                    "Delivery": "owner" if is_owner(of) else delivery,
                    "Asked at": stamp, "Due": due_day.isoformat(), "Fallback": fallback_text,
                    "Context": ", ".join(one_line(c) for c in context or []), "Record": record})
    store.log(rid, stamp, by or "comms-confirm", "asked" + (f", escalating {escalates}" if escalates else ""))
    if escalates:
        store.set(escalates, "Fallback", f"escalated to {rid}")
        store.log(escalates, stamp, by or "comms-confirm", f"escalated to {rid}")
    store.save()
    return {"id": rid, "outcome": "created", "state": "open", "record": record, "due": due_day.isoformat(),
            "delivery": "owner" if is_owner(of) else delivery, "store": str(store_path)}


def task_payload(req: Dict[str, str], domain: str = "", project: str = "") -> Dict[str, Any]:
    """Every task goes on the owner's own list, waiting on the person when they have a contact;
    it is never assigned to them, Portal user or not."""
    contact = (UUID_RE.search(req.get("Contact", "")) or [None])[0] if req.get("Contact") else None
    return {"id": req["Id"], "question": req["Question"], "asked_of": req.get("Asked of", ""),
            "person": req.get("Person", ""), "contact_id": contact,
            "relayed": req.get("Delivery") == "relay",
            "due": req.get("Due") or None, "context": req.get("Context", ""),
            "fallback": req.get("Fallback", ""), "domain": domain or None, "project_id": project or None}


def task(store_path: Path, rid: str, domain: str = "", project: str = "", dry_run: bool = False,
         by: str = "", at: Optional[str] = None) -> Dict[str, Any]:
    store = Store(store_path)
    req = store.get(rid)
    if req.get("State") == "closed":
        raise Refused(f"{rid} is closed")
    if req.get("Task"):
        return {"id": rid, "outcome": "existing", "task": req["Task"]}
    out = portal("task", dict(task_payload(req, domain, project), dry_run=dry_run))
    if dry_run:
        return {"id": rid, "outcome": "would_create", "portal": out}
    ref = out.get("ref") or (f"portal://task/{out['task_id']}" if out.get("task_id") else "")
    if not ref:
        raise Bad(f"confirm-portal task answered without a task: {str(out)[:200]}")
    store.set(rid, "Task", ref)
    store.log(rid, now_stamp(at), by or "comms-confirm", f"task {out.get('outcome', 'created')}")
    store.save()
    return {"id": rid, "outcome": out.get("outcome", "created"), "task": ref}


def record(store_path: Path, rid: str, draft: str = "", subject: str = "", thread: str = "", by: str = "",
           at: Optional[str] = None) -> Dict[str, Any]:
    store = Store(store_path)
    req = store.get(rid)
    if req.get("State") == "closed":
        raise Refused(f"{rid} is closed")
    if not (draft or subject or thread):
        raise Bad("record needs --draft, --subject or --thread")
    changed = []
    for name, value in (("Draft", draft), ("Email subject", subject), ("Email thread", thread)):
        if value:
            store.set(rid, name, value)
            changed.append(name.lower())
    store.log(rid, now_stamp(at), by or "comms-confirm", "recorded " + ", ".join(changed))
    store.save()
    return {"id": rid, "recorded": changed}


def set_answered(store: Store, rid: str, text: str, by: str, evidence: str, at: str) -> str:
    """Mark a request answered and carry the answer to its record; returns what the record did."""
    store.set(rid, "State", "answered")
    store.set(rid, "Answer", text)
    store.set(rid, "Answered by", by)
    store.set(rid, "Evidence", evidence)
    store.set(rid, "Answered at", at)
    store.log(rid, at, "check", f"answer found ({evidence})")
    return write_record(store.path, store.get(rid), "answered", text, by or "check", at)


def find_stores(paths: List[Path]) -> List[Path]:
    out: List[Path] = []
    for p in paths:
        p = Path(p)
        if p.is_file():
            out.append(p)
        elif p.is_dir():
            out += sorted(f for f in p.rglob(STORE_NAME)
                          if not any(part.startswith(".") for part in f.relative_to(p).parts))
        else:
            raise Bad(f"{p} is neither a file nor a folder")
    return out


def check(paths: List[Path], today: Optional[date] = None, use_portal: bool = True,
          at: Optional[str] = None) -> Tuple[List[str], List[str], List[str]]:
    """(answered ids, past-due ids, detail lines). Records every answer it finds."""
    today = today or date.today()
    stamp = now_stamp(at)
    answered: List[str] = []
    late: List[str] = []
    lines: List[str] = []
    for path in find_stores(paths):
        store = Store(path)
        look: List[Dict[str, Any]] = []
        for req in store.all():
            rid, state = req["Id"], req.get("State", "").lower()
            if state not in STATES:
                lines.append(f"- {rid} in {path.name}: state {state!r} is not one of {', '.join(STATES)}")
                continue
            if state != "open":
                continue
            typed = req.get("Answer", "").strip()
            if typed:
                did = set_answered(store, rid, typed, req.get("Answered by") or "typed into the record",
                                   req.get("Evidence") or f"{path.name}, typed", stamp)
                lines.append(f"- {rid} answered, typed into {path.name}: {typed[:120]} ({did})")
                continue
            rec = parse_record(req.get("Record", ""))
            if rec["kind"] == "waiting-on":
                row = engagement_row(path, rec)
                if row.get("Answer", "").strip() and row.get("State", "").lower() == "open":
                    text = row["Answer"].strip()
                    set_answered(store, rid, text, "typed into the Waiting on row",
                                 f"Waiting on {rec['row']}", stamp)
                    lines.append(f"- {rid} answered in Waiting on {rec['row']}: {text[:120]}")
                    continue
                if row.get("State", "").lower() == "closed":
                    store.set(rid, "State", "closed")
                    store.set(rid, "Answer", row.get("Answer") or "(closed in the Waiting on row)")
                    store.log(rid, stamp, "check", f"closed in Waiting on {rec['row']}")
                    lines.append(f"- {rid} was closed in Waiting on {rec['row']}; closed here too")
                    continue
            if req.get("Task") or (req.get("Contact") and (req.get("Email subject") or req.get("Email thread"))):
                look.append({"id": rid, "task": req.get("Task") or None, "asked_at": req.get("Asked at"),
                             "contact_id": (UUID_RE.search(req.get("Contact", "")) or [None])[0],
                             "subject": req.get("Email subject") or None, "thread": req.get("Email thread") or None,
                             "seen": [s.strip() for s in req.get("Seen", "").split(";") if s.strip()]})
            elif "email" in req.get("Channels", "") and not req.get("Email subject"):
                lines.append(f"- {rid}: the email channel has no subject recorded yet, so no reply can be "
                             "matched (run record once the draft exists)")
        if look and use_portal:
            store.save()
            found = portal("look", {"requests": look})
            for item in found.get("findings") or []:
                rid = item.get("id")
                if rid not in store.ids() or store.get(rid).get("State") != "open":
                    continue
                if item.get("kind") == "task_cancelled":
                    store.set(rid, "State", "closed")
                    store.set(rid, "Answer", "(withdrawn: the Portal task was cancelled)")
                    store.set(rid, "Evidence", item.get("evidence", ""))
                    store.log(rid, stamp, "check", "withdrawn, task cancelled")
                    did = write_record(path, store.get(rid), "closed", "(withdrawn)", "check", stamp)
                    lines.append(f"- {rid} withdrawn: its Portal task was cancelled ({did})")
                    continue
                did = set_answered(store, rid, item.get("text") or item.get("kind", "answered"),
                                   item.get("by") or "", item.get("evidence") or "", stamp)
                lines.append(f"- {rid} answered by {item.get('by') or 'someone'} ({item.get('kind')}, "
                             f"{item.get('evidence')}): {str(item.get('text') or '')[:120]} ({did})")
            for problem in found.get("problems") or []:
                lines.append(f"- {problem.get('id')}: {problem.get('reason')}")
        elif look:
            lines.append(f"- {len(look)} requests in {path.name} were not looked up in the Portal (--no-portal)")
        for req in store.all():
            state = req.get("State", "").lower()
            rid = req["Id"]
            if state == "answered":
                answered.append(rid)
                if not any(rid in ln and "answered" in ln for ln in lines):
                    lines.append(f"- {rid} answered, not yet used: {req.get('Answer', '')[:120]}")
            elif state == "open":
                due = parse_day(req.get("Due", ""))
                if due is not None and today > due:
                    fallback = req.get("Fallback", "")
                    if fallback.startswith("proceed"):
                        late.append(rid)
                        lines.append(f"- {rid} past due since {due.isoformat()}, asked of {req.get('Asked of')}; "
                                     f"fallback {fallback}: {req.get('Question')}")
                    elif fallback.startswith("escalate") and not fallback.startswith("escalated"):
                        lines.append(f"- {rid} past due since {due.isoformat()}, asked of {req.get('Asked of')}; "
                                     f"escalated to the owner by the morning reminder: {req.get('Question')}")
                    else:
                        lines.append(f"- {rid} still waiting, due {due.isoformat()} ({fallback}): "
                                     f"{req.get('Question')}")
        store.save()
    return answered, late, lines


def close(store_path: Path, rid: str, by: str, answer: str = "", evidence: str = "", assumed: bool = False,
          withdrawn: bool = False, finish_task: bool = True, at: Optional[str] = None) -> Dict[str, Any]:
    store = Store(store_path)
    req = store.get(rid)
    if req.get("State") == "closed":
        raise Refused(f"{rid} is already closed")
    if sum(map(bool, (answer.strip(), assumed, withdrawn))) != 1:
        raise Bad("close takes exactly one of --answer, --assumed or --withdrawn")
    stamp = now_stamp(at)
    if assumed:
        fallback = req.get("Fallback", "")
        if not fallback.startswith("proceed:"):
            raise Refused(f"{rid} has fallback {fallback!r}; --assumed needs a proceed fallback with an assumption")
        text = f"(assumed, no answer by {req.get('Due')}) {fallback.split(':', 1)[1].strip()}"
    elif withdrawn:
        text = "(withdrawn)"
    else:
        text = answer.strip()
    store.set(rid, "State", "closed")
    store.set(rid, "Answer", text)
    if not withdrawn and not assumed:
        store.set(rid, "Answered by", by if not req.get("Answered by") else req["Answered by"])
    if evidence:
        store.set(rid, "Evidence", evidence)
    if not req.get("Answered at"):
        store.set(rid, "Answered at", stamp)
    store.log(rid, stamp, by, "closed" + (" as assumed" if assumed else " as withdrawn" if withdrawn else ""))
    did = write_record(store.path, store.get(rid), "closed", text, by, stamp)
    store.save()
    out = {"id": rid, "state": "closed", "answer": text, "record": did}
    task_id = (UUID_RE.search(req.get("Task", "")) or [None])[0] if req.get("Task") else None
    if task_id and finish_task:
        status = "CANCELLED" if withdrawn else "DONE"
        comment = (f"Closed by {by}: {text}" + (f" Evidence: {evidence or req.get('Evidence')}"
                                                 if (evidence or req.get("Evidence")) else ""))
        try:
            got = portal("finish", {"task_id": task_id, "status": status, "comment": comment, "id": rid})
            out["task"] = got.get("outcome", "finished")
        except Bad as exc:
            out["task"] = f"not finished: {exc}"
    return out


def reopen(store_path: Path, rid: str, by: str, note: str = "", at: Optional[str] = None) -> Dict[str, Any]:
    """An answer found that does not answer the question: back to open, its evidence remembered
    under Seen so the next check does not find it again."""
    store = Store(store_path)
    req = store.get(rid)
    if req.get("State") != "answered":
        raise Refused(f"{rid} is {req.get('State')}; only an answered request is reopened")
    stamp = now_stamp(at)
    if req.get("Evidence"):
        store.append(rid, "Seen", req["Evidence"])
    for name in ("Answer", "Answered by", "Evidence", "Answered at"):
        store.set(rid, name, "")
    store.set(rid, "State", "open")
    store.log(rid, stamp, by, "reopened" + (f": {one_line(note)}" if note else ""))
    rec = parse_record(req.get("Record", ""))
    if rec["kind"] == "waiting-on":
        waiting = waiting_rows()
        try:
            waiting.reopen((store.path.parent / rec["folder"]).resolve(), by, rec["row"], note,
                          period=rec["period"], at=stamp[:16].replace("T", " "))
        except waiting.ContractError as exc:
            store.log(rid, stamp, by, f"Waiting on {rec['row']} not reopened: {exc}")
    store.save()
    return {"id": rid, "state": "open"}


# ---------------------------------------------------------------------------------------------
# Telling the owner: one message per relay or reminder, through one command


def notify(title: str, bullets: List[str], record_ref: str = "", dry_run: bool = False) -> Dict[str, Any]:
    """Send the owner one message with notify_owner.py. Returns its JSON answer: `sent` true, or
    false with a reason when notifications are off or rehearsing (exit 0). A command that fails
    or cannot be found raises Bad. A dry run returns the argv and runs nothing."""
    base = notify_argv()
    argv = base + ["--title", title]
    for bullet in bullets:
        argv += ["--bullet", bullet]
    if record_ref:
        argv += ["--record-ref", record_ref]
    if dry_run:
        return {"sent": False, "dry_run": True, "reason": "dry run: nothing sent", "argv": argv}
    if not os.environ.get("CONFIRM_NOTIFY_CMD") and not Path(base[-1]).is_file():
        raise Bad(f"{base[-1]} was not found; link the comms-reply-to-email skill into "
                  "~/.claude/skills, or set CONFIRM_NOTIFY_CMD") from None
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        raise Bad(f"{base[0]} was not found; it is how the owner is told") from None
    except subprocess.TimeoutExpired:
        raise Bad(f"{base[0]} took longer than two minutes") from None
    try:
        out = json.loads(done.stdout or "{}")
    except ValueError:
        out = {}
    if not isinstance(out, dict):
        out = {}
    if done.returncode != 0:
        raise Bad(f"{base[0]} did not send (exit {done.returncode}): "
                  f"{out.get('reason') or (done.stderr or done.stdout).strip()[:300]}")
    out.setdefault("sent", False)
    return out


def safe_text(text: Any, limit: int = QUESTION_CHARS) -> str:
    """One line with no URL in it (the notifier refuses a link in a bullet), clipped."""
    out = URL_IN_TEXT.sub("(link)", one_line(text))
    return out if len(out) <= limit else out[: limit - 3].rstrip() + "..."


def person_of(req: Dict[str, str]) -> str:
    name = one_line(req.get("Person", "")).split("<")[0].strip()
    return name or one_line(req.get("Asked of", "")) or "the person"


def where_to_answer(req: Dict[str, str], store: Path, roots: List[Path]) -> str:
    if req.get("Task"):
        return "comment the answer on its Portal task"
    shown = str(store)
    for root in roots:
        try:
            shown = str(Path(store).resolve().relative_to(Path(root).resolve().parent if Path(root).is_file()
                                                           else Path(root).resolve()))
            break
        except ValueError:
            continue
    return f"type the answer after '- Answer:' in {shown}"


def stores_of(paths: List[Path]) -> List[Tuple[Path, Store]]:
    return [(path, Store(path)) for path in find_stores(paths)]


def relay(paths: List[Path], dry_run: bool = False, by: str = "", at: Optional[str] = None) -> Dict[str, Any]:
    """One message asking the owner to put every open relay request not yet relayed to its person.
    Each one relayed is marked, so a second run sends nothing for it."""
    stamp = now_stamp(at)
    picked: List[Tuple[Path, Store, Dict[str, str]]] = []
    for path, store in stores_of(paths):
        for req in store.all():
            if req.get("State") == "open" and req.get("Delivery") == "relay" and not req.get("Relayed") \
                    and not is_owner(req.get("Asked of", "")):
                picked.append((path, store, req))
    if not picked:
        return {"outcome": "nothing", "line": "NOTHING", "ids": []}
    n = len(picked)
    title = f"Please ask {n} question{'s' if n != 1 else ''} for me"
    bullets = []
    for path, _, req in picked:
        due = parse_day(req.get("Due", ""))
        bullets.append(f"Ask {person_of(req)} ({one_line(req.get('Asked of'))}): {safe_text(req.get('Question'))} "
                       f"Wanted by {short_day(due)}; {where_to_answer(req, path, paths)}.")
    tasks = [req["Task"] for _, _, req in picked if req.get("Task")]
    record_ref = tasks[0] if len(tasks) == 1 and n == 1 else ""
    got = notify(title, bullets, record_ref, dry_run)
    ids = [req["Id"] for _, _, req in picked]
    if got.get("sent"):
        for path, store, req in picked:
            store.set(req["Id"], "Relayed", stamp)
            store.log(req["Id"], stamp, by or "comms-confirm",
                      f"relayed to the owner to ask {person_of(req)} ({got.get('channel') or 'sent'})")
        for store in {id(s): s for _, s, _ in picked}.values():
            store.save()
        line = f"SENT: relayed {n} question{'s' if n != 1 else ''} to the owner ({got.get('channel') or 'sent'})"
        outcome = "sent"
    elif got.get("dry_run"):
        line, outcome = f"DRY RUN: would relay {n} question{'s' if n != 1 else ''}", "dry_run"
    else:
        line, outcome = f"NOT SENT: {got.get('reason') or 'the notifier did not send it'}", "not_sent"
    return {"outcome": outcome, "line": line, "ids": ids, "title": title, "bullets": bullets,
            "record_ref": record_ref, "notify": got}


def remind(paths: List[Path], today: Optional[date] = None, dry_run: bool = False, by: str = "",
           at: Optional[str] = None) -> Dict[str, Any]:
    """The morning reminder, the escalation of every request: one message listing the open
    requests past due or due today that have not been in a reminder today. Each one listed is
    marked with today's date, so a second run the same day sends nothing new."""
    today = today or date.today()
    stamp = now_stamp(at)
    if not paths:
        return {"outcome": "nothing", "line": "NOTHING: no stores given", "ids": []}
    picked: List[Tuple[Path, Store, Dict[str, str], date]] = []
    for path, store in stores_of(paths):
        for req in store.all():
            due = parse_day(req.get("Due", ""))
            if req.get("State") != "open" or due is None or due > today:
                continue
            if req.get("Fallback", "").startswith("escalated") or req.get("Reminded", "")[:10] == today.isoformat():
                continue
            picked.append((path, store, req, due))
    if not picked:
        return {"outcome": "nothing", "line": "NOTHING", "ids": []}
    picked.sort(key=lambda item: (item[3], item[2].get("Asked at", "")))
    n = len(picked)
    late = sum(1 for *_, due in picked if due < today)
    noun = f"{n} confirmation{'s' if n != 1 else ''}"
    title = (f"{noun} past due" if late == n else f"{noun} due today" if late == 0
             else f"{noun} past due or due today")
    bullets = []
    for path, _, req, due in picked:
        asked = parse_day(req.get("Asked at", ""))
        who = "you" if is_owner(req.get("Asked of", "")) else \
            f"{person_of(req)} ({one_line(req.get('Asked of'))})"
        when = "due today" if due == today else f"due {short_day(due)}"
        bullets.append(f"{who}, asked {short_day(asked)}, {when}: {safe_text(req.get('Question'))} "
                       f"To answer, {where_to_answer(req, path, paths)}.")
    tasks = [req["Task"] for _, _, req, _ in picked if req.get("Task")]
    record_ref = tasks[0] if len(tasks) == 1 and n == 1 else ""
    got = notify(title, bullets, record_ref, dry_run)
    ids = [req["Id"] for _, _, req, _ in picked]
    if got.get("sent"):
        for _, store, req, _ in picked:
            store.set(req["Id"], "Reminded", today.isoformat())
            store.log(req["Id"], stamp, by or "remind", f"in the owner's reminder ({got.get('channel') or 'sent'})")
        for store in {id(s): s for _, s, _, _ in picked}.values():
            store.save()
        line, outcome = f"SENT: {title} ({got.get('channel') or 'sent'})", "sent"
    elif got.get("dry_run"):
        line, outcome = f"DRY RUN: would send {title}", "dry_run"
    else:
        line, outcome = f"NOT SENT: {got.get('reason') or 'the notifier did not send it'}", "not_sent"
    return {"outcome": outcome, "line": line, "ids": ids, "title": title, "bullets": bullets,
            "record_ref": record_ref, "notify": got}


# ---------------------------------------------------------------------------------------------
# The command line


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("who")
    p.add_argument("folder", type=Path)
    p.add_argument("--role", required=True)

    p = sub.add_parser("new")
    p.add_argument("store", type=Path)
    p.add_argument("--question", required=True)
    p.add_argument("--of", required=True, help="the role asked, such as 'AP lead' or 'owner'")
    p.add_argument("--person", default="", help="the resolved person, 'Name <address>'")
    p.add_argument("--contact", default="", help="the person's Portal contact id")
    p.add_argument("--user", default="", help="the person's Portal user id, to put the task on their list")
    p.add_argument("--channel", action="append", default=[], help="owner, task or email; repeatable")
    p.add_argument("--due", help="yyyy-mm-dd; default the end of the next full business day after asking")
    p.add_argument("--due-days", type=int, default=DEFAULT_DUE_BUSINESS_DAYS)
    p.add_argument("--fallback", default="escalate", help="proceed, escalate or wait")
    p.add_argument("--assume", default="", help="with --fallback proceed: what the work assumes")
    p.add_argument("--context", action="append", default=[], help="a link to the evidence; repeatable")
    p.add_argument("--engagement", type=Path, help="engagement folder: add a Waiting on row there")
    p.add_argument("--period", help="yyyy-mm for --engagement; default its current period")
    p.add_argument("--phase", default="", help="the phase the answer unblocks, for --engagement")
    p.add_argument("--record-file", help="a file, relative to the store, where answers are appended")
    p.add_argument("--scope", help="what makes the id unique across stores; default the store's path")
    p.add_argument("--escalates", default="", help="the past-due request this one escalates to the owner")
    p.add_argument("--delivery", default=None, help="relay or direct; default CONFIRM_DELIVERY, else relay")
    p.add_argument("--by", default="")
    p.add_argument("--at")

    p = sub.add_parser("task")
    p.add_argument("store", type=Path)
    p.add_argument("id")
    p.add_argument("--domain", default="")
    p.add_argument("--project", default="")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--by", default="")

    p = sub.add_parser("record")
    p.add_argument("store", type=Path)
    p.add_argument("id")
    p.add_argument("--draft", default="")
    p.add_argument("--subject", default="")
    p.add_argument("--thread", default="")
    p.add_argument("--by", default="")

    p = sub.add_parser("check")
    p.add_argument("paths", type=Path, nargs="+", help="stores, or folders searched for CONFIRMATIONS.md")
    p.add_argument("--today", help="yyyy-mm-dd; default today")
    p.add_argument("--no-portal", action="store_true", help="read the local records only")
    p.add_argument("--at")

    p = sub.add_parser("close")
    p.add_argument("store", type=Path)
    p.add_argument("id")
    p.add_argument("--by", required=True)
    p.add_argument("--answer", default="")
    p.add_argument("--evidence", default="")
    p.add_argument("--assumed", action="store_true")
    p.add_argument("--withdrawn", action="store_true")
    p.add_argument("--leave-task", action="store_true", help="do not mark the Portal task done")
    p.add_argument("--at")

    p = sub.add_parser("reopen")
    p.add_argument("store", type=Path)
    p.add_argument("id")
    p.add_argument("--by", required=True)
    p.add_argument("--note", default="")

    p = sub.add_parser("relay")
    p.add_argument("paths", type=Path, nargs="+", help="stores, or folders searched for CONFIRMATIONS.md")
    p.add_argument("--dry-run", action="store_true", help="print the message; send and mark nothing")
    p.add_argument("--by", default="")

    p = sub.add_parser("remind")
    p.add_argument("paths", type=Path, nargs="*", help="stores, or folders searched for CONFIRMATIONS.md")
    p.add_argument("--today", help="yyyy-mm-dd; default today")
    p.add_argument("--dry-run", action="store_true", help="print the message; send and mark nothing")
    p.add_argument("--by", default="")

    p = sub.add_parser("list")
    p.add_argument("store", type=Path)

    args = ap.parse_args(argv)
    try:
        if args.command == "check":
            today = parse_day(args.today) if args.today else None
            if args.today and today is None:
                raise Bad(f"--today {args.today!r} is not yyyy-mm-dd")
            answered, late, lines = check(args.paths, today, not args.no_portal, args.at)
            reasons = ([f"answered {', '.join(answered)}"] if answered else []) + \
                      ([f"past due {', '.join(late)}"] if late else [])
            print(f"WORK: {'; '.join(reasons)}" if reasons else "NOTHING")
            for line in lines:
                print(line)
            return 0
        if args.command in ("relay", "remind"):
            if args.command == "relay":
                got = relay(args.paths, args.dry_run, args.by)
            else:
                today = parse_day(args.today) if args.today else None
                if args.today and today is None:
                    raise Bad(f"--today {args.today!r} is not yyyy-mm-dd")
                got = remind(args.paths, today, args.dry_run, args.by)
            print(got["line"])
            if got.get("title"):
                print(f"- {got['title']}")
                for bullet in got["bullets"]:
                    print(f"  - {bullet}")
            return 0
        if args.command == "who":
            out: Any = who(args.folder, args.role)
        elif args.command == "new":
            out = new(args.store, args.question, args.of, args.channel, args.person, args.contact, args.user,
                      args.due, args.due_days, args.fallback, args.assume, args.context, args.engagement,
                      args.period, args.phase, args.record_file, args.scope, args.by, args.at, args.escalates,
                      args.delivery)
        elif args.command == "task":
            out = task(args.store, args.id, args.domain, args.project, args.dry_run, args.by)
        elif args.command == "record":
            out = record(args.store, args.id, args.draft, args.subject, args.thread, args.by)
        elif args.command == "close":
            out = close(args.store, args.id, args.by, args.answer, args.evidence, args.assumed, args.withdrawn,
                        not args.leave_task, args.at)
        elif args.command == "reopen":
            out = reopen(args.store, args.id, args.by, args.note)
        else:
            out = Store(args.store).all() if Path(args.store).is_file() else []
    except Refused as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)}, indent=1))
        return 3
    except Bad as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
