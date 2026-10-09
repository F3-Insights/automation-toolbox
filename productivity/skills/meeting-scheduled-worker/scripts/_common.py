"""What the meeting-processing scripts share.

The Portal client, the owner settings, the markers and transcript digests, the task lookup
by marker, the state folder and its ledger, the owner's answers on an admin task, the plan
check (`validate`, `plan_hash`) and the acknowledgment. Each `meeting_*.py` script beside
this file imports it; nothing else does.

One recording is one unit of work. Every hold becomes a result code for that recording,
and the ledger keeps a recording that keeps failing from taking a slot in every later run.

Exit codes for every script: 0 go on, 3 skip this recording (or stop, for
`meeting-pending`), 2 could not run.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import sys
import time
import tomllib
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

OK, STOP, ERROR = 0, 3, 2
SKILL = "meeting-scheduled-worker"
STATE_ENV = "MEETING_PROCESSING_STATE"
DRY_RUN_ENV = "F3I_TOOLBOX_DRY_RUN"  # a runner sets this for a dry run; writes then need --dry-run
TOKEN_ENV = "INSIGHTS_PORTAL_ASSISTANT_TOKEN"

CAP_SECONDS = 3 * 60 * 60
MAX_ATTEMPTS = 3
BACKOFF_HOURS = 6.0
LOCK_WAIT_SECONDS = 10.0
MAX_ANSWERS_CHARS = 20000
NOTE_MARK = "<!-- meeting-processing:recording:{rid}:{digest} -->"
UUID = re.compile(r"^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")
SECRETS = re.compile(r"(?i)(bearer\s+\S+|authorization[\"'\s:=]+(?:bearer\s+)?\S+|[?&](?:key|token|api_key|access_token)=[^\s&\"']+)")


class Stop(Exception):
    """A failure the script reports as one line; the recording is skipped."""


class Unreachable(Stop):
    """The Portal gave no answer (network, TLS, HTTP status). Says nothing about the recording."""


class Busy(Stop):
    """Another command holds the lock; this recording is skipped, never the run."""


# --------------------------------------------------------------------------- settings and output

def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


def safe(text) -> str:
    """Everything on its way to stdout or stderr passes through here, so no token is printed."""
    return SECRETS.sub("[redacted]", str(text))


def emit(payload: dict, code: int) -> int:
    print(safe(json.dumps(payload, indent=1, default=str)))
    return code


def fail(message: str) -> int:
    """A command that could not run prints a JSON error (the skill reads stdout) and a one-line stderr."""
    print(safe(json.dumps({"status": "error", "reason": message}, indent=1)))
    print(safe(message), file=sys.stderr)
    return ERROR


def reason_of(exc: BaseException, command: str) -> str:
    return str(exc) if isinstance(exc, Stop) else f"{command} could not complete: {type(exc).__name__}: {exc}"


def dry_run_refusal(dry: bool):
    """Why a real write is refused: the runner says this run is dry and the call is not."""
    if dry or str(os.environ.get(DRY_RUN_ENV, "")).strip().lower() not in ("1", "true", "yes", "on"):
        return None
    return f"this run is a dry run ({DRY_RUN_ENV}=1) and the call is not: nothing written; pass --dry-run"


# --------------------------------------------------------------------------- the Portal

class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect, so the bearer token is never sent to another address."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def endpoint() -> tuple:
    """(url, Authorization header) from the MCP config the setting `portal_mcp_config` names."""
    cfg_path = settings().get("portal_mcp_config")
    server = settings().get("portal_server") or "insights-portal"
    if not cfg_path:
        raise Stop("the setting portal_mcp_config (the MCP config file holding the Portal server) is needed")
    try:
        cfg = json.loads(Path(cfg_path).expanduser().read_text(encoding="utf-8"))["mcpServers"][server]
    except (OSError, KeyError, TypeError, ValueError):
        raise Stop(f"the file portal_mcp_config names has no usable mcpServers entry {server!r}") from None
    token = os.environ.get(TOKEN_ENV, "").strip()
    auth = f"Bearer {token}" if token else str((cfg.get("headers") or {}).get("Authorization") or "")
    url = str(cfg.get("url") or "")

    def expand(value: str, what: str) -> str:
        def one(m):
            if not os.environ.get(m.group(1)):
                raise Stop(f"the Portal {what} needs {m.group(1)}, which is not set")
            return os.environ[m.group(1)]
        value = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", one, value)
        if "${" in value or "\n" in value or "\r" in value:
            raise Stop(f"the Portal {what} is malformed")
        return value

    if not url or not auth:
        raise Stop(f"no Portal URL or token: set {TOKEN_ENV} or give the config an Authorization header")
    url, auth = expand(url, "URL"), expand(auth, "token")
    parts = urlsplit(url)
    local = parts.hostname in ("localhost", "127.0.0.1", "::1")
    if not parts.hostname or parts.username or parts.password or not (
            parts.scheme == "https" or (parts.scheme == "http" and local)):
        raise Stop("the Portal URL must be HTTPS (plain HTTP only to localhost)")
    if not auth.startswith("Bearer ") or not auth[7:].strip():
        raise Stop("the Portal token is not a bearer token")
    return url, auth


class Portal:
    """A JSON-RPC client for the Portal MCP. Only `call`, `whoami` and `list_entities`."""

    def __init__(self, url: str, auth: str, timeout: int = 60):
        self.url, self._auth, self.timeout, self._id = url, auth, timeout, 0

    def call(self, tool: str, arguments=None):
        self._id += 1
        body = json.dumps({"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
                           "params": {"name": tool, "arguments": arguments or {}}}).encode()
        req = urllib.request.Request(self.url, data=body, method="POST", headers={
            "Authorization": self._auth, "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"})
        try:
            with OPENER.open(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise Unreachable(f"portal {tool}: HTTP {exc.code}" + (", a redirect, refused" if 300 <= exc.code < 400 else "")) from None
        except urllib.error.URLError as exc:
            raise Unreachable(f"portal {tool}: {exc.reason}") from None
        except OSError as exc:
            raise Unreachable(f"portal {tool}: {type(exc).__name__}") from None
        messages = []
        if raw.lstrip().startswith("{"):
            messages.append(json.loads(raw))
        for line in raw.splitlines() if not messages else []:
            if line.startswith("data:"):
                try:
                    messages.append(json.loads(line[5:].strip()))
                except ValueError:
                    pass
        if not messages:
            raise Stop(f"portal {tool}: empty response")
        out = messages[-1]
        if "error" in out:
            raise Stop(f"portal {tool}: {out['error']}")
        result = out.get("result", out)
        if isinstance(result, dict) and "content" in result:
            text = "\n".join(c.get("text", "") for c in result["content"] if c.get("type") == "text")
            if result.get("isError"):
                raise Stop(f"portal {tool}: {text[:300]}")
            try:
                return json.loads(text)
            except ValueError:
                return text
        return result

    def whoami(self):
        return self.call("whoami")

    def list_entities(self, entity_type: str, filters=None, limit: int = 200, max_pages: int = 50) -> list:
        """Every item of one type, following `next_offset` until `has_more` is false."""
        args = {"entity_type": entity_type, "limit": max(1, min(int(limit), 200))}
        if filters:
            args["filters"] = filters
        items, offset = [], 0
        for _ in range(max(1, max_pages)):
            if offset:
                args["offset"] = offset
            out = self.call("list_entities", args)
            if not isinstance(out, dict):
                break
            items.extend(i for i in out.get("items") or [] if isinstance(i, dict))
            nxt = out.get("next_offset")
            if not out.get("has_more") or not isinstance(nxt, int) or nxt <= offset:
                break
            offset = nxt
        return items


def client() -> Portal:
    return Portal(*endpoint())


def principal(portal) -> dict:
    who = portal.whoami()
    return (who or {}).get("principal") or {} if isinstance(who, dict) else {}


def owner_email(portal) -> str:
    email = principal(portal).get("primary_email")
    if not email:
        raise Stop("whoami carried no primary_email, so the owner's comments cannot be told apart")
    return str(email)


# --------------------------------------------------------------------------- markers and digests

def admin_marker(recording_id: str, digest: str) -> str:
    """The admin task's `source_reference`; `complete_fellow_recording` requires exactly this."""
    return f"meeting-processing:recording:{recording_id}:{digest}"


def legacy_marker(event_id: str, digest: str) -> str:
    """An older admin marker, keyed on the event, still recognised."""
    return f"meeting-processing:{event_id}:{digest}"


def action_marker(event_id: str, fhash: str, index: int) -> str:
    return f"local-meeting:{event_id}:{fhash[:16]}:{index}"


def enrichment_marker(kind: str, uid: str) -> str:
    return f"context-enrichment:{kind}:{uid}"


def queue_digest(segments: list) -> str:
    """The 16-hex digest the Portal lists as `transcript_hash`: speaker and folded text."""
    canonical = [[str((s or {}).get("speaker") or ""), " ".join(str((s or {}).get("text") or "").split())]
                 for s in segments if isinstance(s, dict)]
    return hashlib.sha256(json.dumps(canonical, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()[:16]


def full_hash(segments: list) -> str:
    """The whole-transcript hash whose first 16 characters are in every action marker."""
    return hashlib.sha256(json.dumps(segments, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def is_uuid(value) -> bool:
    return bool(UUID.match(str(value or "")))


def is_digest(value) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{16}", value or ""))


def parse_time(value):
    if not value:
        return None
    try:
        out = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return out if out.tzinfo else out.replace(tzinfo=timezone.utc)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def folded(text) -> str:
    return " ".join(str(text or "").split())


def fingerprint(text) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- Portal reads

def record(value, kind: str) -> dict:
    """The record inside a composite `get`, or a Stop naming what was wrong."""
    if not isinstance(value, dict):
        raise Stop(f"the {kind} read returned nothing usable")
    if value.get("error"):
        raise Stop(f"the {kind} could not be read: {value['error']}")
    inner = value.get(kind, value)
    if not isinstance(inner, dict) or not is_uuid(inner.get("id")):
        raise Stop(f"the {kind} read carried no id")
    return inner


def get_full(portal, kind: str, uid: str) -> dict:
    """The whole composite (`notes`, `comments`, `associations` beside the record)."""
    out = portal.call("get", {"entity_type": kind, "id_or_query": uid, "detail": "full"})
    record(out, kind)
    return out


def recording(portal, recording_id: str) -> dict:
    out = portal.call("get_fellow_recording", {"recording_id": recording_id})
    if not isinstance(out, dict) or out.get("error") or not isinstance(out.get("recording"), dict):
        raise Stop(f"recording {recording_id} could not be read: "
                   f"{out.get('error') if isinstance(out, dict) else 'no answer'}")
    if out["recording"].get("id") != recording_id:
        raise Stop("the Portal returned a different recording than the one asked for")
    return out


def ownership(portal) -> dict:
    """Local processing only when the Portal names owner `local` and no cloud runs are active."""
    state = portal.call("list_fellow_meetings", {"since": "2100-01-01T00:00:00Z", "limit": 1})
    if not isinstance(state, dict):
        raise Stop("list_fellow_meetings returned nothing usable")
    owner, runs = state.get("owner"), state.get("active_cloud_runs")
    return {"owner": owner, "active_cloud_runs": runs, "local": owner == "local" and runs == 0}


def tasks_mentioning(portal, *needles: str) -> list:
    """Every task, open or done, whose title or description mentions one of these ids.

    The task search does not match `source_reference`, so a task is found only because its
    description holds the id searched for. Every task this job creates therefore puts the
    recording id, the event id, or (for enrichment) the contact or company id in its
    description; the caller matches the exact marker on the rows.
    """
    rows = {}
    for needle in needles:
        if needle:
            for row in portal.list_entities("task", {"search": needle, "include_completed": True}):
                if isinstance(row, dict) and row.get("id"):
                    rows.setdefault(str(row["id"]), row)
    return list(rows.values())


def with_marker(tasks: list, *markers: str) -> list:
    """Tasks carrying one of the markers in `source_reference` or the description's first line, oldest first."""
    wanted = {m for m in markers if m}

    def first_line(t):
        return str(t.get("description") or "").strip().split("\n", 1)[0].strip()
    hits = [t for t in tasks if str(t.get("source_reference") or "") in wanted or first_line(t) in wanted]
    return sorted(hits, key=lambda t: str(t.get("created_at") or ""))


def admin_tasks(portal, recording_id: str, event_id: str, digest: str, tasks=None) -> list:
    """The recording's admin tasks, oldest first. More than one is flagged, never fatal."""
    tasks = tasks if tasks is not None else tasks_mentioning(portal, recording_id, event_id)
    return with_marker(tasks, admin_marker(recording_id, digest), legacy_marker(event_id, digest) if event_id else "")


def action_tasks(tasks: list, event_id: str, fhash: str) -> dict:
    """Action tasks an earlier attempt created for this transcript, by plan index."""
    prefix = f"local-meeting:{event_id}:{fhash[:16]}:"
    out = {}
    for t in tasks:
        ref = str(t.get("source_reference") or "")
        if ref.startswith(prefix) and ref[len(prefix):].isdigit():
            out.setdefault(int(ref[len(prefix):]), []).append(t)
    for rows in out.values():
        rows.sort(key=lambda t: str(t.get("created_at") or ""))
    return out


def task_line(t: dict) -> dict:
    return {"id": t.get("id"), "_ref": f"portal://task/{t.get('id')}", "title": t.get("title"),
            "status": t.get("status"), "source_reference": t.get("source_reference"),
            "owner_contact_id": t.get("owner_contact_id"), "created_at": t.get("created_at"),
            "updated_at": t.get("updated_at")}


def status_of(task: dict) -> str:
    return str(task.get("status") or "").upper()


# --------------------------------------------------------------------------- folders

def toolbox_root():
    """The toolbox repository this script sits in (the folder holding scripts/toolbox_check.py)."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "scripts" / "toolbox_check.py").is_file():
            return parent
    return Path(__file__).resolve().parents[1]  # copied out of the repository: guard the skill folder


def outside_toolbox(path) -> Path:
    """`path`, resolved; refused when it lies inside the toolbox, which holds no state."""
    target = Path(path).expanduser().resolve()
    try:
        target.relative_to(toolbox_root())
    except ValueError:
        return target
    raise Stop(f"{target} is inside the toolbox repository; run files live outside it")


def state_root(explicit=None) -> Path:
    """--state, else $MEETING_PROCESSING_STATE, else the setting, else `state_dir`/meeting-processing."""
    own, shared = settings(SKILL).get("state_dir"), settings().get("state_dir")
    chosen = explicit or os.environ.get(STATE_ENV) or own or (str(Path(shared) / "meeting-processing") if shared else None)
    if not chosen:
        raise Stop(f"no state folder: pass --state, or set [{SKILL}] state_dir or the top-level state_dir setting")
    root = outside_toolbox(chosen)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def recording_dir(root: Path, recording_id: str, digest: str) -> Path:
    if not is_uuid(recording_id) or not is_digest(digest):
        raise Stop("a recording id (UUID) and a 16-hex transcript digest are required")
    path = root / "recordings" / f"{recording_id}-{digest}"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def folder_ids(folder) -> tuple:
    """The recording id and digest a recording folder `<RID>-<D>` is named for."""
    name = Path(folder).name
    return name[:36], name[37:]


def state_of(folder):
    """The state folder a recording folder lies in (`<state>/recordings/<RID>-<D>`)."""
    folder = Path(folder)
    return folder.parent.parent if folder.parent.name == "recordings" else None


def inside(folder, path) -> Path:
    """`path`, resolved, when it lies inside the recording folder."""
    target = Path(path).expanduser().resolve()
    try:
        target.relative_to(Path(folder).resolve())
    except ValueError:
        raise Stop(f"{target} is outside the recording folder {folder}") from None
    return target


def atomic_json(path, value) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(value, fh, indent=1, ensure_ascii=False, default=str)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def read_json(path):
    path = Path(path)
    if not path.is_file():
        raise Stop(f"{path.name} is missing from {path.parent}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        raise Stop(f"{path} is not JSON") from None


def set_aside(folder, *names: str) -> list:
    """Move `plan.json`, `check.json` to the next free `plan-N.json`, `check-N.json`, keeping earlier rounds."""
    moved = []
    for name in names:
        src = Path(folder) / f"{name}.json"
        if not src.is_file():
            continue
        n = 1
        while (Path(folder) / f"{name}-{n}.json").exists():
            n += 1
        os.replace(src, Path(folder) / f"{name}-{n}.json")
        moved.append(f"{name}-{n}.json")
    return moved


@contextmanager
def locked(path, wait=None):
    """An exclusive lock on `path`, waited for at most LOCK_WAIT_SECONDS, so a lock left by a
    hung command costs one recording a skip instead of blocking the run."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    deadline = time.monotonic() + (LOCK_WAIT_SECONDS if wait is None else wait)
    with path.open("w") as fh:
        while True:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise Busy(f"{path.name} in {path.parent} is held by another command; "
                               "this recording is skipped and tried on a later run") from None
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


# --------------------------------------------------------------------------- the ledger

def ledger_key(recording_id: str, digest: str) -> str:
    return f"{recording_id}:{digest}"


def load_ledger(root: Path) -> dict:
    path = root / "ledger.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        raise Stop(f"{path} is not JSON; move it aside to start a fresh ledger") from None
    return data if isinstance(data, dict) else {}


def update_ledger(root: Path, recording_id: str, digest: str, **changes) -> dict:
    """Change one recording's entry under the lock. `attempt=True` counts an attempt;
    `refund=True` takes one back; `deferred=True` stamps a transient failure that counts
    none; `reason` is added to the history; any other key is set (None removes it)."""
    with locked(root / "ledger.lock"):
        ledger = load_ledger(root)
        key = ledger_key(recording_id, digest)
        entry = ledger.get(key) or {"recording_id": recording_id, "digest": digest, "attempts": 0, "history": []}
        stamp = now_utc().isoformat()
        if changes.pop("attempt", False):
            entry["attempts"] = int(entry.get("attempts") or 0) + 1
            entry["last_attempt_at"] = stamp
        if changes.pop("refund", False):
            entry["attempts"] = max(0, int(entry.get("attempts") or 0) - 1)
        if changes.pop("deferred", False):
            entry["deferred_at"] = stamp
        reason = changes.pop("reason", None)
        if reason:
            entry["last_reason"] = reason
            entry["history"] = (entry.get("history") or [])[-19:] + [{"at": stamp, "reason": reason}]
        for k, v in changes.items():
            if v is None:
                entry.pop(k, None)
            else:
                entry[k] = v
        ledger[key] = entry
        atomic_json(root / "ledger.json", ledger)
        return entry


def clear_ledger(root: Path, recording_id: str, digest=None) -> list:
    with locked(root / "ledger.lock"):
        ledger = load_ledger(root)
        gone = [k for k in ledger if k.startswith(f"{recording_id}:") and (not digest or k.endswith(f":{digest}"))]
        for k in gone:
            ledger.pop(k)
        atomic_json(root / "ledger.json", ledger)
        return gone


def deferred_until(entry: dict, backoff_hours: float):
    """When a failed recording may be tried again: the backoff after its last attempt or transient failure."""
    stamps = [t for t in (parse_time(entry.get("last_attempt_at")), parse_time(entry.get("deferred_at"))) if t]
    if not stamps or not entry.get("last_reason"):
        return None
    return max(stamps) + timedelta(hours=backoff_hours)


def transient(exc) -> bool:
    """A failure that says nothing about the recording: the Portal unreachable or the
    connection broken, here or as the cause of the error raised."""
    seen = 0
    while exc is not None and seen < 10:
        if isinstance(exc, (Unreachable, ConnectionError, TimeoutError)):
            return True
        exc, seen = exc.__cause__ or (None if exc.__suppress_context__ else exc.__context__), seen + 1
    return False


def defer(root, recording_id: str, digest: str, reason: str) -> None:
    """A transient failure after step 3: defer the recording for the backoff and take back the
    attempt `meeting-existing` counted, so an outage never parks a recording. Best effort."""
    if root is None or not is_uuid(recording_id) or not is_digest(digest):
        return
    try:
        update_ledger(root, recording_id, digest, deferred=True, refund=True, reason=safe("transient: " + reason)[:300])
    except Exception:  # the ledger is a convenience; the error itself is reported anyway
        pass


# --------------------------------------------------------------------------- the owner's answers

QUESTIONS_HEAD = "Questions for the owner (asked {at}):"
QUESTIONS_FOOT = ("Answer by commenting on this task, numbered like the questions, or move it to TODO "
                  "to go ahead without an answer (an answer typed into this description is read too). The "
                  "next run reads it and analyses the meeting again with your answers.")
HEAD_RE = re.compile(r"Questions for [^\n()]{1,40} \(asked (\S+)\):\n")
AGENT_LINE = re.compile(r"\(posted by .+?, an agent\)\s*\Z", re.S)


def relayed_head() -> str:
    """The first line a runner puts on an answer it posts for the owner under an agent's token
    (setting `relayed_answer_head`); such a comment is the owner's words. Empty: none."""
    return str(settings(SKILL).get("relayed_answer_head") or "")


def owner_wrote(body) -> bool:
    text, head = str(body or ""), relayed_head()
    return bool(text.strip()) and (not AGENT_LINE.search(text) or bool(head and text.lstrip().startswith(head)))


def split_questions(description) -> tuple:
    """(before, block, after) around the last questions section this job appended; `after` is
    whatever follows its closing line, such as an answer the owner typed below."""
    text = str(description or "")
    heads = list(HEAD_RE.finditer(text))
    if not heads:
        return text, "", ""
    start = heads[-1].start()
    if text[:start].endswith("\n\n"):
        start -= 2
    foot = text.find(QUESTIONS_FOOT, heads[-1].end())
    end = foot + len(QUESTIONS_FOOT) if foot >= 0 else len(text)
    return text[:start], text[start:end], text[end:]


def asked_at(description):
    heads = list(HEAD_RE.finditer(str(description or "")))
    return parse_time(heads[-1].group(1)) if heads else None


def read_answers(path) -> str:
    text = Path(path).read_text(encoding="utf-8")
    if len(text) > MAX_ANSWERS_CHARS:
        raise Stop(f"the answers file is over {MAX_ANSWERS_CHARS} characters; it is the owner's answers, not a document")
    return text


def answers(task_env: dict, email: str) -> dict:
    """The owner's answers on an admin task, from its comments (and its description when moved).

    The owner's comments are those whose `author_email` is whoami's `primary_email` and that
    carry no "(posted by ..., an agent)" line, or that start with the relayed-answer heading.
    `answered` is true when one is newer than the questions, or the owner moved the task off
    WAITING after they were asked.
    """
    task = task_env.get("task") if isinstance(task_env.get("task"), dict) else task_env
    status, asked = status_of(task), asked_at(task.get("description"))
    mine = [c for c in task_env.get("comments") or [] if isinstance(c, dict)
            and str(c.get("author_email") or "").casefold() == email.casefold() and owner_wrote(c.get("body"))]
    if asked is None:  # a WAITING task with questions this job did not write: any comment answers
        new = mine if status == "WAITING" else []
    else:
        new = [c for c in mine if (parse_time(c.get("created_at")) or asked) > asked]
    moved = asked is not None and status in ("TODO", "IN_PROGRESS")
    lines = []
    if mine:
        lines.append(f"The owner's comments on the admin task {task.get('id')}, verbatim, oldest first:")
        lines += [f"\n[{c.get('created_at')}]\n{str(c.get('body')).strip()}" for c in mine]
    if moved:
        lines.append(f"\nThe owner moved the admin task {task.get('id')} from WAITING to {status}. Any answer they "
                     "typed there is in its description, below. A question nothing here answers goes ahead "
                     "without their answer: record it as a flag in the note, not as a clarification.\n\n"
                     + str(task.get("description") or "").strip())
    if (task_env.get("comment_stats") or {}).get("has_more"):
        lines.append("\n(Older comments on the task were not returned; only the newest are above.)")
    return {"answered": bool(new) or moved, "asked_at": asked.isoformat() if asked else None,
            "comments": len(mine), "new_comments": len(new), "moved": moved, "status": status,
            "text": "\n".join(lines).strip()[:MAX_ANSWERS_CHARS]}


# --------------------------------------------------------------------------- the plan check

DISPOSITIONS = ("create", "link_existing", "proposal", "unresolved")
RESERVED = ("local-recording-section:", "meeting-processing:recording:")
ENRICH = re.compile(r"^portal://(contact|company)/([0-9a-fA-F-]{36})$")
TOP_KEYS = ("recording_id", "digest", "note_title", "note_content", "summary_evidence", "actions",
            "clarifications", "enrichment_refs", "flags")


def plan_hash(plan: dict, source: dict) -> str:
    """The plan and the meeting note it was made against: a changed note is a changed check."""
    note = (source or {}).get("source_note") or {}
    basis = {"plan": plan, "source_note": {k: note.get(k) for k in ("id", "title", "content", "updated_at")}}
    return "sha256:" + hashlib.sha256(json.dumps(basis, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def validate(plan, source: dict, existing=None) -> list:
    """Every error in a plan: quotes not in their segment, bad ids, dispositions and dates,
    reserved marker text, and an action an earlier attempt already made a task for."""
    if not isinstance(plan, dict):
        return ["the plan is not a JSON object"]
    missing = [k for k in TOP_KEYS if k not in plan]
    if missing:
        return ["the plan lacks " + ", ".join(missing)]
    errors = []
    if plan["recording_id"] != source.get("recording_id") or plan["digest"] != source.get("digest"):
        errors.append("the plan names another recording or revision than source.json")
    segments = source.get("segments") or []

    def evidence(items, where):
        if not isinstance(items, list) or not items:
            errors.append(f"{where}: no transcript evidence")
            return
        for item in items:
            if not isinstance(item, dict):
                errors.append(f"{where}: evidence item is not an object")
                continue
            i, quote = item.get("segment"), item.get("quote")
            if type(i) is not int or not 0 <= i < len(segments):
                errors.append(f"{where}: segment {i!r} is not an index into the {len(segments)} segments")
            elif not folded(quote):
                errors.append(f"{where}: an empty quote for segment {i}")
            elif folded(quote) not in folded(segments[i].get("text")):
                errors.append(f"{where}: quote not found in segment {i}: {str(quote)[:80]!r}")

    if not folded(plan["note_title"]) or not folded(plan["note_content"]):
        errors.append("the note title or content is empty")
    if any(mark in str(plan["note_content"]) + str(plan["note_title"]) for mark in RESERVED):
        errors.append("the note text carries a reserved marker string")
    evidence(plan["summary_evidence"], "summary")

    actions = plan["actions"] if isinstance(plan["actions"], list) else []
    if not isinstance(plan["actions"], list):
        errors.append("actions is not a list")
    linked = set()
    for n, action in enumerate(actions):
        where = f"action {n}"
        if not isinstance(action, dict):
            errors.append(f"{where}: not an object")
            continue
        disposition = action.get("disposition")
        if disposition not in DISPOSITIONS:
            errors.append(f"{where}: disposition {disposition!r} is not one of {', '.join(DISPOSITIONS)}")
        if not folded(action.get("title")):
            errors.append(f"{where}: no title")
        elif len(str(action["title"])) > 200:
            errors.append(f"{where}: the title is over the Portal's 200 characters")
        evidence(action.get("evidence"), where)
        for key in ("owner_contact_id", "domain_id", "project_id", "existing_task_id"):
            if action.get(key) is not None and not is_uuid(action.get(key)):
                errors.append(f"{where}: {key} is not a UUID")
        if disposition == "create" and (not action.get("owner_contact_id") or not action.get("domain_id")
                                        or action.get("existing_task_id")):
            errors.append(f"{where}: a new task needs a verified owner and domain and no existing task")
        if disposition == "link_existing":
            if not action.get("existing_task_id"):
                errors.append(f"{where}: link_existing needs existing_task_id")
            linked.add(str(action.get("existing_task_id")))
        if action.get("due_date"):
            try:
                date.fromisoformat(str(action["due_date"]))
            except ValueError:
                errors.append(f"{where}: due_date {action['due_date']!r} is not YYYY-MM-DD")

    refs = plan["enrichment_refs"] if isinstance(plan["enrichment_refs"], list) else ["(not a list)"]
    for ref in refs:
        m = ENRICH.match(str(ref))
        if not m or not is_uuid(m.group(2)):
            errors.append(f"enrichment target {ref!r} is not portal://contact/<uuid> or portal://company/<uuid>")
    clar = plan["clarifications"]
    if not isinstance(clar, list):
        errors.append("clarifications is not a list")
    else:
        for n, q in enumerate(clar):
            if not isinstance(q, dict) or not folded(q.get("question")):
                errors.append(f"clarification {n}: an object with a question is needed")
            elif q.get("options") is not None and not (isinstance(q["options"], list)
                                                        and all(isinstance(o, str) for o in q["options"])):
                errors.append(f"clarification {n}: options must be a list of strings")
    if not isinstance(plan["flags"], list) or not all(isinstance(f, str) for f in plan["flags"]):
        errors.append("flags must be a list of strings")

    # A task an earlier attempt made for plan index N must stay that action, or be linked by id.
    for idx, rows in ((existing or {}).get("existing_actions") or {}).items():
        try:
            n = int(idx)
        except ValueError:
            continue
        ids = {str(r.get("id")) for r in rows}
        if ids & linked:
            continue
        action = actions[n] if 0 <= n < len(actions) and isinstance(actions[n], dict) else None
        titles = {folded(r.get("title")) for r in rows}
        if action is None or action.get("disposition") != "create" or folded(action.get("title")) not in titles:
            errors.append(f"an earlier attempt created task {sorted(ids)[0]} ({sorted(titles)[0]!r}) for plan "
                          f"index {n}; make that action index {n} with the same title, or link the task by id")
    return errors


# --------------------------------------------------------------------------- the acknowledgment

ACK_CODES = ("NO_TASK", "NOT_DONE", "CHANGED", "NO_NOTE", "LINK_NOT_VERIFIED", "ACK_NOT_VERIFIED")
ACK_STATUSES = ("acknowledged", "already_acknowledged", "would_acknowledge", "refused")


def acknowledge(portal, recording_id: str, digest: str, dry_run: bool = False) -> dict:
    """Tell the Portal one recording revision is processed, only when it is: the transcript is
    still this revision, the admin task with the exact marker is DONE and shows the note. A DONE
    task with only the older marker is given the exact one first (read back)."""
    src = recording(portal, recording_id)
    row = src["recording"]
    base = {"recording_id": recording_id, "digest": digest}

    def refused(code, reason, **extra):
        return {**base, "status": "refused", "code": code, "reason": reason, **extra}

    if row.get("processed_hash") == digest:
        return {**base, "status": "already_acknowledged"}
    if src.get("transcript_hash") != digest:
        return refused("CHANGED", f"the recording is now revision {src.get('transcript_hash')}")
    note_id, event_id = row.get("note_id"), str(row.get("calendar_event_id") or "")
    if not note_id:
        return refused("NO_NOTE", "the recording has no note")
    marker = admin_marker(recording_id, digest)
    admins = admin_tasks(portal, recording_id, event_id, digest)
    if not admins:
        return refused("NO_TASK", "no admin task carries this recording's marker")
    done = [t for t in admins if status_of(t) == "DONE"]
    if not done:
        return refused("NOT_DONE", f"the admin task {admins[0]['id']} is {admins[0].get('status')}")
    chosen = ([t for t in done if t.get("source_reference") == marker] or done)[0]
    if chosen.get("source_reference") != marker:
        if dry_run:
            return {**base, "status": "would_acknowledge", "task_id": chosen["id"], "note_id": note_id,
                    "would_remark": {"task_id": chosen["id"], "source_reference": marker}}
        portal.call("update_task", {"id": chosen["id"], "source_reference": marker})
        if record(get_full(portal, "task", chosen["id"]), "task").get("source_reference") != marker:
            return refused("NO_TASK", f"the admin task {chosen['id']} did not take the exact marker")
        base["remarked"] = chosen["id"]
    task_env = get_full(portal, "task", chosen["id"])
    task = record(task_env, "task")
    if status_of(task) != "DONE":
        return refused("NOT_DONE", f"the admin task {task['id']} reads back {task.get('status')}")
    if not any(isinstance(n, dict) and n.get("id") == note_id for n in task_env.get("notes") or []):
        return refused("LINK_NOT_VERIFIED", f"the admin task {task['id']} does not show the note {note_id}")
    note = record(portal.call("get", {"entity_type": "note", "id_or_query": note_id, "detail": "full"}), "note")
    if dry_run:
        return {**base, "status": "would_acknowledge", "task_id": task["id"], "note_id": note["id"]}
    answer = portal.call("complete_fellow_recording", {
        "recording_id": recording_id, "transcript_digest": digest, "task_id": task["id"], "note_id": note["id"],
        "expected_recording_updated_at": row.get("updated_at"), "expected_task_updated_at": task.get("updated_at"),
        "expected_note_updated_at": note.get("updated_at")})
    after = recording(portal, recording_id)["recording"]
    if after.get("processed_hash") != digest:
        return refused("ACK_NOT_VERIFIED", "the Portal did not record the acknowledgment", answer=answer)
    return {**base, "status": "acknowledged", "task_id": task["id"], "note_id": note["id"],
            "processed_at": after.get("processed_at")}
