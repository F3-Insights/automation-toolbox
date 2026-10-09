"""What the nightly-sweep scripts share: the owner's settings, the Insights Portal client, the
local-day windows, the state folder and its ledger of swept dates, the run folder's dates.json,
the markers that make every write findable again, and the Portal lookups.

Settings live in the owner's settings file under `[nightly-sweep-workstream]`:

    timezone            the owner's IANA zone (--tz overrides); required
    state               the state folder (--state overrides); default <state_dir>/nightly-sweep
    assistant_email     the executive assistant's address; their mail is never noise
    portal_brief_email  the sender of the Portal's own generated Brief; its items already exist
    owner_names         the owner's names, never distinctive words, and a signature line
    firm_names          the firm's names, never distinctive words
    vip_stale_days      days after which a VIP or High contact is stale (default 30)
    daily_note_private  true makes the Daily Note private (default false)
"""

import fcntl
import json
import os
import re
import sys
import tomllib
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SKILL = "nightly-sweep-workstream"
SKILL_DIR = Path(__file__).resolve().parents[1]
OK, STOP, ERROR = 0, 3, 2
DRY_RUN_ENV = "F3I_TOOLBOX_DRY_RUN"

DATES_PER_RUN = 3       # catch-up: the oldest unswept dates first, at most this many a run
LOOKBACK_DAYS = 7       # an unswept date older than this is reported, not swept
FIRST_RUN_DATES = 2     # empty ledger and no Daily Note found: the newest closed date and the one before
RECOVERY_DATES = 3      # empty ledger: at most this many dates back to the newest Daily Note found
RETRIES = 2             # an incomplete date is offered again at most this many times
IN_PROGRESS_HOURS = 3   # a date another run started this recently is not swept again
MAX_EMAIL_PAGES = 20    # 200 rows a page; a day past 4,000 messages is reported, not read
VIP_STALE_DAYS = 30
SWEEP_TAG = "nightly-sweep"

UUID = re.compile(r"^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
OPEN = ("TODO", "IN_PROGRESS", "WAITING")
ALL_STATUSES = ["TODO", "IN_PROGRESS", "WAITING", "DONE", "CANCELLED"]
CLOSED_TASK_STATUSES = frozenset({"done", "completed", "complete", "cancelled", "canceled", "archived",
                                  "closed", "dropped"})


class Stop(Exception):
    """A problem that stops the script: printed as one JSON error, exit 2."""


# --------------------------------------------------------------------------- settings

def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


def own(key, default=None):
    """One key of this skill's settings table."""
    return settings(SKILL).get(key, default)


def address_setting(key):
    return str(own(key) or "").strip().lower()


def name_list(key):
    """A list setting of names, each as its lower-case words joined by spaces."""
    value = own(key) or []
    if isinstance(value, str):
        value = [value]
    return [" ".join(re.findall(r"[a-z0-9][a-z0-9&]*", str(v).lower())) for v in value if str(v).strip()]


def vip_stale_days():
    """(days, note): the VIP and High staleness threshold, and why the default was used, if it was."""
    raw = own("vip_stale_days", VIP_STALE_DAYS)
    try:
        days = int(str(raw).strip())
    except ValueError:
        days = 0
    if 1 <= days <= 3650:
        return days, None
    return VIP_STALE_DAYS, (f"vip_stale_days {raw!r} is not a whole number of days from 1 to 3650; "
                            f"the default {VIP_STALE_DAYS} was used")


def note_private():
    return own("daily_note_private", False) is True


def timezone_name(explicit=None):
    name = (explicit or "").strip() or str(own("timezone") or "").strip()
    if not name:
        raise Stop(f"setting [{SKILL}] timezone is needed, or pass --tz")
    zone(name)
    return name


def zone(name):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise Stop(f"unknown timezone {name!r}") from None


# --------------------------------------------------------------------------- output

_SECRETS = re.compile(r"(?i)(bearer\s+\S+|authorization[\"'\s:=]+\S+|[?&](?:key|token|api_key|access_token)=[^\s&\"']+)")


def safe(text):
    """Everything printed passes through here, so a bearer token is never shown."""
    return _SECRETS.sub("[redacted]", str(text))


def emit(payload, code=OK):
    """Print one JSON object (secrets redacted) and exit."""
    print(safe(json.dumps(payload, indent=1, default=str)))
    sys.exit(code)


def fail(message):
    emit({"status": "error", "reason": str(message)}, ERROR)


def run_main(fn, name):
    """Run a script's body; a Stop or any surprise becomes one JSON error and exit 2."""
    try:
        fn()
    except Stop as exc:
        fail(exc)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - one line, never a traceback
        fail(f"{name} could not complete: {type(exc).__name__}: {exc}")


def dry_run_refusal(dry):
    """Why a real write is refused: the runner says this run is dry and the call is not."""
    if dry or str(os.environ.get(DRY_RUN_ENV, "")).strip().lower() not in ("1", "true", "yes", "on"):
        return None
    return f"this run is a dry run ({DRY_RUN_ENV}=1) and the call is not: nothing written; pass --dry-run"


# --------------------------------------------------------------------------- the Portal

class PortalError(Exception):
    """The Portal could not be reached or refused a call."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect, so the bearer token only ever goes to the configured URL."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def portal_endpoint():
    """(url, Authorization header) from the MCP config the settings name. The token is
    INSIGHTS_PORTAL_ASSISTANT_TOKEN when set, else the config's Authorization header with
    ${VAR} expanded. HTTPS only, except plain HTTP to localhost."""
    conf = settings()
    config = conf.get("portal_mcp_config")
    server = conf.get("portal_server") or "insights-portal"
    if not config:
        raise Stop("setting portal_mcp_config is needed (the MCP config holding the Portal server)")
    try:
        entry = json.loads(Path(config).expanduser().read_text())["mcpServers"][server]
    except (OSError, KeyError, TypeError, ValueError):
        raise Stop(f"the MCP config has no usable server named {server!r}") from None
    token = os.environ.get("INSIGHTS_PORTAL_ASSISTANT_TOKEN", "").strip()
    auth = f"Bearer {token}" if token else (entry.get("headers") or {}).get("Authorization", "")

    def expand(value, what):
        def one(match):
            if not os.environ.get(match.group(1)):
                raise Stop(f"the Portal {what} needs {match.group(1)}, which is not set")
            return os.environ[match.group(1)]
        value = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", one, value or "")
        if "${" in value or "\n" in value:
            raise Stop(f"the Portal {what} is malformed")
        return value

    url, auth = expand(entry.get("url", ""), "URL"), expand(auth, "token")
    parts = urlsplit(url)
    local = parts.hostname in ("localhost", "127.0.0.1", "::1")
    if not parts.hostname or not (parts.scheme == "https" or (parts.scheme == "http" and local)):
        raise Stop("the Portal URL must be HTTPS (HTTP only on localhost)")
    if not auth.startswith("Bearer ") or not auth[7:].strip():
        raise Stop("no Portal bearer token: set INSIGHTS_PORTAL_ASSISTANT_TOKEN or put one in the config")
    return url, auth


class Portal:
    """A small JSON-RPC client for the Portal's MCP tools."""

    def __init__(self, timeout=60):
        self.url, self._auth = portal_endpoint()
        self.timeout = timeout
        self._id = 0

    def call(self, tool, arguments=None):
        self._id += 1
        body = json.dumps({"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
                           "params": {"name": tool, "arguments": arguments or {}}}).encode()
        req = urllib.request.Request(self.url, data=body, method="POST")
        req.add_header("Authorization", self._auth)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json, text/event-stream")
        try:
            with _OPENER.open(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise PortalError(f"portal {tool}: HTTP {exc.code}") from None
        except (urllib.error.URLError, OSError) as exc:
            raise PortalError(f"portal {tool}: {getattr(exc, 'reason', type(exc).__name__)}") from None
        messages = []
        lines = [raw] if raw.lstrip().startswith("{") else [l[5:] for l in raw.splitlines() if l.startswith("data:")]
        for line in lines:
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if not messages:
            raise PortalError(f"portal {tool}: empty response")
        out = messages[-1]
        if "error" in out:
            raise PortalError(f"portal {tool}: {out['error']}")
        result = out.get("result", out)
        if isinstance(result, dict) and "content" in result:
            text = "\n".join(c.get("text", "") for c in result["content"] if c.get("type") == "text")
            if result.get("isError"):
                raise PortalError(f"portal {tool}: {text[:300]}")
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        return result


def page_through(client, entity_type, filters=None, sizes=(200, 50, 10, 1), max_calls=400):
    """Every row of one entity type, page by page: (rows, rows it could not read).

    A page the server refuses (one stored row it will not serialise) is retried at smaller
    sizes down to one row, and that row is stepped over, so a bad record costs one row rather
    than the whole listing. Reading nothing at all, with failures, is an error.
    """
    items, offset, unreadable, total, calls, failure = [], 0, 0, None, 0, ""
    while calls < max_calls:
        served = None
        for size in sizes:
            if calls >= max_calls:
                break
            args = {"entity_type": entity_type, "limit": size}
            if filters:
                args["filters"] = dict(filters)
            if offset:
                args["offset"] = offset
            calls += 1
            try:
                out = client.call("list_entities", args)
            except Exception as exc:  # noqa: BLE001 - a page the server will not serialise
                failure = type(exc).__name__
                continue
            if isinstance(out, dict):
                served = (out, size)
                break
        if served is None:
            unreadable += 1
            offset += 1
            if total is None or offset >= total:
                break
            continue
        out, size = served
        rows = [r for r in out.get("items") or [] if isinstance(r, dict)]
        if isinstance(out.get("total"), int):
            total = out["total"]
        items.extend(rows)
        if not rows:
            break
        offset += len(rows)
        if total is not None and offset >= total:
            break
        if size >= sizes[0] and not out.get("has_more"):
            break
    if failure and not items:
        raise Stop(f"could not read any {entity_type} rows from the Portal ({failure})")
    return items, unreadable


# --------------------------------------------------------------------------- dates and windows

def is_uuid(value):
    return bool(UUID.match(str(value or "")))


def parse_date(value):
    text = str(value or "").strip()
    if not DATE_RE.match(text):
        raise Stop(f"a date is YYYY-MM-DD, got {text!r}")
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise Stop(f"{text!r} is not a calendar date") from None


def parse_time(value):
    """An ISO instant as an aware datetime (UTC when it carries no zone), else None."""
    if not value:
        return None
    try:
        out = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return out if out.tzinfo else out.replace(tzinfo=timezone.utc)


def utc_iso(moment):
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def local_day(day, tz):
    """The local day as a half-open UTC window: since is local midnight, until the next one.

    Built from local midnights, so a 23-hour or 25-hour day (the clocks changing) is still
    exactly that day. A message belongs to the day when since <= received_at < until.
    """
    start = datetime.combine(day, time(0, 0), tzinfo=tz)
    end = datetime.combine(day + timedelta(days=1), time(0, 0), tzinfo=tz)
    return {"since": utc_iso(start), "until": utc_iso(end),
            "since_local": start.isoformat(), "until_local": end.isoformat()}


def in_window(when, window):
    moment, since, until = parse_time(when), parse_time(window["since"]), parse_time(window["until"])
    return bool(moment and since and until and since <= moment < until)


def is_closed(day, tz, now):
    """True once the date's local day is over: its next local midnight has passed."""
    return now >= parse_time(local_day(day, tz)["until"])


def now_or(text):
    if not text:
        return datetime.now(timezone.utc)
    moment = parse_time(text)
    if moment is None:
        raise Stop(f"--now is an ISO instant, got {text!r}")
    return moment


# --------------------------------------------------------------------------- files and folders

def toolbox_root():
    """The checkout these scripts live in (the nearest folder above holding .git), or, for a skill
    copied on its own, the skill folder."""
    for folder in SKILL_DIR.parents:
        if (folder / ".git").exists():
            return folder
    return SKILL_DIR


def guard_run_path(path):
    """A Run folder, state folder or output file never lives inside the toolbox checkout (or this
    skill's own folder): no state is ever written beside the code."""
    target = Path(path).expanduser().resolve()
    for root in {SKILL_DIR, toolbox_root()}:
        if target == root or root in target.parents:
            raise Stop(f"{target} is inside the toolbox ({root}); Run and state files live outside it")
    return target


def state_root(explicit=None):
    """The state folder: --state, else [nightly-sweep-workstream] state, else <state_dir>/nightly-sweep."""
    chosen = (explicit or "").strip() or str(own("state") or "").strip()
    if not chosen:
        base = str(settings().get("state_dir") or "").strip()
        if not base:
            raise Stop(f"setting state_dir (or [{SKILL}] state) is needed for the sweep's ledger, or pass --state")
        chosen = str(Path(base).expanduser() / "nightly-sweep")
    root = guard_run_path(chosen)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def out_path(path):
    target = guard_run_path(path)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    return target


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def atomic_json(path, value):
    atomic_text(path, json.dumps(value, indent=1, ensure_ascii=False, default=str))


def read_json(path):
    path = Path(path)
    if not path.is_file():
        raise Stop(f"{path} does not exist")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        raise Stop(f"{path} is not JSON") from None


def json_or_none(path):
    try:
        return read_json(path)
    except Stop:
        return None


@contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


# --------------------------------------------------------------------------- the ledger

PARTS = ("dates", "in_progress", "published")


def load_state(root):
    """The ledger: `dates` (one entry per swept date), `in_progress` (dates a run is sweeping now)
    and `published` (the Daily Note each date last got from this job)."""
    path = Path(root) / "ledger.json"
    if not path.is_file():
        return {k: {} for k in PARTS}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        raise Stop(f"{path} is not JSON; move it aside to start a fresh ledger") from None
    data = data if isinstance(data, dict) else {}
    return {k: data.get(k) if isinstance(data.get(k), dict) else {} for k in PARTS}


def save_state(root, state):
    atomic_json(Path(root) / "ledger.json", {k: dict(sorted((state.get(k) or {}).items())) for k in PARTS})


def is_done(entry):
    """A ledger entry that needs no re-sweep; one without `complete` counts as done."""
    return not (isinstance(entry, dict) and entry.get("complete") is False)


def record_date(root, day, **fields):
    """Mark one date swept, under the lock, and clear its in-progress mark. An incomplete sweep
    counts an attempt, which sweep_dates uses to stop offering the date after RETRIES more tries."""
    with locked(Path(root) / "ledger.lock"):
        state = load_state(root)
        before = state["dates"].get(day) if isinstance(state["dates"].get(day), dict) else {}
        entry = dict(fields, completed_at=datetime.now(timezone.utc).isoformat())
        if entry.get("complete") is False:
            entry["attempts"] = int(before.get("attempts") or 0) + 1
        elif before.get("attempts"):
            entry["attempts"] = before["attempts"]
        state["dates"][day] = entry
        state["in_progress"].pop(day, None)
        save_state(root, state)
        return entry


def record_published(root, day, note_id, updated_at):
    """The note's updated_at as read back after this job wrote it: a later one means an edit."""
    with locked(Path(root) / "ledger.lock"):
        state = load_state(root)
        state["published"][day] = {"note_id": note_id, "updated_at": str(updated_at or ""),
                                   "published_at": datetime.now(timezone.utc).isoformat()}
        save_state(root, state)


def clear_in_progress(root, day):
    with locked(Path(root) / "ledger.lock"):
        state = load_state(root)
        if state["in_progress"].pop(day, None) is not None:
            save_state(root, state)


def in_progress_fresh(entry, now, run=None):
    """True while another run's mark on a date is younger than IN_PROGRESS_HOURS. The same run
    folder may take its own date again; a crashed run's mark expires."""
    if not isinstance(entry, dict):
        return False
    if run and entry.get("run") == run:
        return False
    started = parse_time(entry.get("started_at"))
    return bool(started and now - started < timedelta(hours=IN_PROGRESS_HOURS))


# --------------------------------------------------------------------------- the run folder

def run_dates(run):
    """RUN/dates.json as sweep_dates wrote it, or None when there is none to read."""
    if not run:
        return None
    path = Path(run) / "dates.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        raise Stop(f"{path} is not JSON") from None
    return data if isinstance(data, dict) else None


def run_date_rows(run):
    """The date rows of RUN/dates.json, for the --run modes; a missing file stops the script."""
    data = run_dates(run)
    if data is None:
        raise Stop(f"{Path(run) / 'dates.json'} is missing; run sweep_dates.py --run first")
    return [r for r in data.get("dates") or [] if isinstance(r, dict) and DATE_RE.match(str(r.get("date") or ""))]


def run_refusal(run, dry_run, day):
    """(code, reason) when a writer must not write in this run, else None.

    DRY_RUN: the runner marked a dry run, or dates.json says so, and --dry-run was forgotten.
    NO_RUN: a live write with no dates.json that says, as a boolean, whether the run is a dry
    run, or for a date dates.json does not hand out. A missing file is never read as live.
    """
    if dry_run:
        return None
    env = dry_run_refusal(dry_run)
    if env:
        return ("DRY_RUN", env)
    path = Path(run) / "dates.json" if run else None
    data = run_dates(run)
    if data is None:
        return ("NO_RUN", f"{path or 'the run folder'} has no dates.json; run sweep_dates.py --run first, or pass "
                          "--dry-run. Nothing was written")
    if not isinstance(data.get("dry_run"), bool):
        return ("NO_RUN", f"{path} does not say whether this run is a dry run (no boolean dry_run); "
                          "nothing was written")
    if data["dry_run"]:
        return ("DRY_RUN", f"{path} says this run is a dry run; run the command again with --dry-run. "
                           "Nothing was written")
    days = {str(r.get("date")) for r in data.get("dates") or [] if isinstance(r, dict)}
    if day not in days:
        return ("NO_RUN", f"{path} does not hand out {day} (it lists {', '.join(sorted(days)) or 'no date'}); "
                          "nothing was written")
    return None


# --------------------------------------------------------------------------- markers

def task_marker(email_id, item):
    """One task per item of one email, whichever night's run proposes it."""
    return f"nightly-sweep:email:{email_id}:{item}"


def note_marker(key):
    return f"<!-- nightly-sweep:note:{key} -->"


def daily_note_title(day):
    return f"Daily Note - {day}"


def daily_note_marker(day):
    return f"<!-- nightly-sweep:daily-note:{day} -->"


def email_ref(value):
    return f"portal://email/{value}" if value else ""


# --------------------------------------------------------------------------- Portal reads

def owner_contact(client):
    """The owner's contact id from whoami; tasks are never created ownerless."""
    who = client.call("whoami", {})
    principal = (who or {}).get("principal") or {} if isinstance(who, dict) else {}
    contact = principal.get("contact_id")
    if not is_uuid(contact):
        raise Stop("whoami named no contact for the owner; tasks are never created ownerless")
    return str(contact)


def _search_notes(client, query):
    out = client.call("search", {"query": f'"{query}"', "limit": 10})
    if not isinstance(out, dict):
        raise Stop("search returned nothing usable")
    if out.get("error"):
        raise Stop(f"search failed: {out['error']}")
    return [n for n in out.get("notes") or [] if isinstance(n, dict) and is_uuid(n.get("id"))]


def get_record(client, kind, uid):
    out = client.call("get", {"entity_type": kind, "id_or_query": uid, "detail": "full"})
    if not isinstance(out, dict) or out.get("error"):
        reason = out.get("error") if isinstance(out, dict) else "no answer"
        raise Stop(f"{kind} {uid} could not be read: {reason}")
    inner = out.get(kind) if isinstance(out.get(kind), dict) else out
    if str(inner.get("id") or "") != uid:
        raise Stop(f"the {kind} read returned another record than {uid}")
    return inner


def notes_titled(client, title, marker=None):
    """Notes whose title is exactly this one, or whose content carries this marker, oldest first.

    The cross-entity search matches note titles and body text, so a note this job wrote is found
    by its marker even when its title was changed; a marker hit is read in full and kept only
    when its content holds the marker. A failed marker search is not an error.
    """
    rows = {}
    for n in _search_notes(client, title):
        if str(n.get("title") or "").strip() == title.strip():
            rows.setdefault(str(n["id"]), n)
    if marker:
        key = marker.replace("<!--", "").replace("-->", "").strip()
        try:
            hits = _search_notes(client, key)
        except Exception:  # noqa: BLE001 - the title lookup stands on its own
            hits = []
        for n in hits:
            if str(n["id"]) in rows:
                continue
            try:
                full = get_record(client, "note", str(n["id"]))
            except Exception:  # noqa: BLE001 - an unreadable hit is not this note
                continue
            if marker in str(full.get("content") or ""):
                rows[str(n["id"])] = dict(n, found_by="marker")
    return sorted(rows.values(), key=lambda n: str(n.get("created_at") or ""))


def tasks_mentioning(client, needle):
    """Every task in any status whose text holds this id. The status list is passed every time:
    without it the listing returns open tasks only. The task search does not match
    source_reference, so every task this job makes carries its email id in the description."""
    rows, offset = {}, 0
    for _ in range(5):
        out = client.call("list_entities", {"entity_type": "task", "limit": 50, "offset": offset,
                                            "filters": {"search": needle, "status": ALL_STATUSES}})
        if not isinstance(out, dict) or out.get("error"):
            reason = out.get("error") if isinstance(out, dict) else "no answer"
            raise Stop(f"the task lookup failed: {reason}")
        for row in out.get("items") or []:
            if isinstance(row, dict) and row.get("id"):
                rows.setdefault(str(row["id"]), row)
        if not out.get("has_more"):
            break
        offset = int(out.get("next_offset") or offset + 50)
    return list(rows.values())


def with_marker(tasks, marker):
    hits = [t for t in tasks if str(t.get("source_reference") or "") == marker
            or marker in str(t.get("description") or "").splitlines()]
    return sorted(hits, key=lambda t: str(t.get("created_at") or ""))


def newest_daily_note(client, newest, days=LOOKBACK_DAYS):
    """The newest date, from `newest` back `days` dates, with a note titled exactly
    `Daily Note - <date>`: where a first run, or a run after a lost ledger, picks up.
    One exact-title search per date, newest first, so ranking cannot hide a recent note."""
    for n in range(max(days, 1)):
        day = (newest - timedelta(days=n)).isoformat()
        title = daily_note_title(day)
        if any(str(r.get("title") or "").strip() == title for r in _search_notes(client, title)):
            return day
    return None


# --------------------------------------------------------------------------- tasks

def status_of(item):
    return str(item.get("status") or "").strip().upper()


def is_open_task(task):
    return not task.get("is_archived") and status_of(task).lower() not in CLOSED_TASK_STATUSES


def due_of(task):
    for key in ("due_date", "deadline"):
        moment = parse_time(task.get(key))
        if moment:
            return moment.date()
        text = str(task.get(key) or "")[:10]
        if DATE_RE.match(text):
            try:
                return date.fromisoformat(text)
            except ValueError:
                pass
    return None


def task_domain(task, projects):
    """A task's domain is its project's domain, else its own."""
    project = projects.get(str(task.get("project_id") or ""))
    if project and project.get("domain_id"):
        return str(project["domain_id"])
    return str(task["domain_id"]) if task.get("domain_id") else None
