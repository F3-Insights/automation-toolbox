"""What the calendar steward's scripts share: owner settings, the Insights Portal client, the
calendar read and its cleaning, the steward's home folder, the proposal file's contract, the
numbered approval list, the item ledger and how the owner's answers are read.

The steward proposes; the owner approves; calendar_apply.py makes exactly what they approved.

The Portal endpoint and bearer come from the MCP config file the `portal_mcp_config` setting
names (server `portal_server`, default `insights-portal`). The bearer is
`INSIGHTS_PORTAL_ASSISTANT_TOKEN` when set, else the config's Authorization header with
`${VAR}` expanded from the environment. It is never printed. HTTPS only, except plain HTTP to
localhost, and a redirect is refused so the bearer goes nowhere but the configured URL.

THE HOME (--home, else the setting [calendar-steward-method] home, else <state_dir>/calendar-steward)

    CALENDAR-STEWARD-ITEMS.csv   one row per numbered item of every list, its answer and outcome
    journal.jsonl                one line per write calendar_apply.py made
    <yyyy-mm-dd>/                one folder per list (the day it was proposed)
        scan.json, proposals.json    what the list was built from
        items.json                   the numbered items the owner answers, frozen when published
        PROPOSALS.md                 the list as the owner reads it
        publish.json                 the approval task, the list's hash, when
        ANSWERS.md                   optional: the owner's answers written in a file
        approve-<stamp>/             each apply: answers.json, changes.json, apply.json,
                                     undo.jsonl, EVENTS.md and events.ics
        superseded-<stamp>/          an earlier unanswered list the same day replaced

THE PROPOSAL FILE (RUN/proposals.json, written by the orchestrator)

    {"tool": "calendar-steward", "version": 1, "date": "2026-10-05", "dry_run": false,
     "summary": "one line on the fortnight",
     "proposals": [
      {"id": "p1", "kind": "focus-block", "date": "2026-10-06", "start": "09:00", "end": "10:30",
       "title": "Focus: board pack", "for": "portal://task/<uuid>", "why": "...",
       "source": "steward" | "daily-plan", "from": "2026-10-05:f1"},
      {"id": "p2", "kind": "move", "event": "portal://calendar_event/<uuid>", "date": "...",
       "start": "10:00", "end": "11:00", "title": "...",
       "to": {"date": "...", "start": "14:00", "end": "15:00"}, "why": "..."},
      {"id": "p3", "kind": "decline", "event": "...", "date": "...", "start": "...", "end": "...",
       "title": "...", "draft": "the reply, never sent", "why": "..."},
      {"id": "p4", "kind": "prep", "event": "...", "date": "...", "start": "...", "title": "...",
       "prepare": "one line", "due": "2026-10-06", "why": "..."}],
     "findings": [{"ids": ["conflict:2026-10-06:ab12cd34"], "proposal": "p2"},
                  {"ids": ["no-agenda:2026-10-08:..."], "dismissed": "a standing internal meeting"}],
     "questions": [{"ask": "...", "why": "..."}], "notes": ["..."]}

Times are local HH:MM in the owner's timezone.

THE ANSWERS: "1) ok 2) no", one per line or on one line, "3-5) ok", "rest ok". ok (yes,
approve, go) approves; no (skip, keep, leave) declines. An answer that says more than its verb
("2) ok but at 10") is `modified`: never applied, reported back. Sources are read oldest first,
a later answer winning: the owner's comments on the approval task, ANSWERS.md in the list's
folder, then the launch form (which answers the newest list only).
"""

import csv
import hashlib
import io
import json
import os
import re
import tomllib
import urllib.error
import urllib.request
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class Bad(Exception):
    """A bad argument or an unreadable input: exit 2."""


class Failure(Exception):
    """The command could not do its job; the message says why."""


class PortalError(Failure):
    """The Portal refused the call or gave no usable answer."""


class PortalUnreachable(PortalError):
    """The call never got an answer (network, TLS, an HTTP status, a redirect)."""


def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


_SECRETS = re.compile(r"(?i)(bearer\s+\S+|authorization[\"'\s:=]+(?:bearer\s+)?\S+"
                      r"|[?&](?:key|token|api_key|access_token)=[^\s&\"']+)")


def safe(text):
    """Everything on its way to the screen passes through here, so no token is ever shown."""
    return _SECRETS.sub("[redacted]", str(text))


# --------------------------------------------------------------------------- the Portal

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect: urllib would otherwise resend the bearer to the new address."""

    def redirect_request(self, *args, **kwargs):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def portal_endpoint(config_path=None, server=None):
    """(url, Authorization header) for the Portal, from settings and the environment. A config
    path or server name given here replaces the `portal_mcp_config` or `portal_server` setting."""
    top = settings()
    config_path = config_path or top.get("portal_mcp_config")
    server = server or top.get("portal_server") or "insights-portal"
    if not config_path:
        raise Failure("set portal_mcp_config in the owner settings to the MCP config holding the Portal")
    path = Path(str(config_path)).expanduser()
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))["mcpServers"][server]
    except (OSError, ValueError, KeyError, TypeError):
        raise Failure(f"{path} has no usable mcpServers entry named {server!r}") from None
    token = os.environ.get("INSIGHTS_PORTAL_ASSISTANT_TOKEN", "").strip()
    auth = f"Bearer {token}" if token else (cfg.get("headers") or {}).get("Authorization") or ""
    url = cfg.get("url") or ""

    def expand(value, what):
        def one(match):
            if not os.environ.get(match.group(1)):
                raise Failure(f"the Portal {what} needs {match.group(1)}, which is not set")
            return os.environ[match.group(1)]
        value = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", one, value)
        if "${" in value or "\n" in value or "\r" in value:
            raise Failure(f"the Portal {what} is malformed")
        return value

    if not url or not auth:
        raise Failure(f"the {server!r} entry in {path} needs a url and a token")
    url, auth = expand(url, "URL"), expand(auth, "token")
    parts = urlsplit(url)
    local = parts.hostname in ("localhost", "127.0.0.1", "::1")
    if not parts.hostname or parts.username or parts.password or not (
            parts.scheme == "https" or (parts.scheme == "http" and local)):
        raise Failure("the Portal URL must be HTTPS (HTTP only on localhost)")
    if not auth.startswith("Bearer ") or not auth[7:].strip():
        raise Failure("the Portal token is not a bearer token")
    return url, auth


class Portal:
    """A JSON-RPC client for the Portal's MCP server: one `call` per tool."""

    def __init__(self, url, auth, timeout=60):
        self.url, self._auth, self.timeout = url, auth, timeout
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
            if 300 <= exc.code < 400:
                raise PortalUnreachable(f"portal {tool}: HTTP {exc.code}, a redirect, refused") from None
            raise PortalUnreachable(f"portal {tool}: HTTP {exc.code}") from None
        except urllib.error.URLError as exc:
            raise PortalUnreachable(f"portal {tool}: {exc.reason}") from None
        except OSError as exc:
            raise PortalUnreachable(f"portal {tool}: {type(exc).__name__}") from None
        return unwrap(tool, raw)

    def whoami(self):
        return self.call("whoami")


def unwrap(tool, raw):
    """The tool's answer from a JSON or event-stream response, parsed when it is JSON."""
    messages = []
    if raw.lstrip().startswith("{"):
        messages.append(json.loads(raw))
    else:
        for line in raw.splitlines():
            if line.startswith("data:"):
                try:
                    messages.append(json.loads(line[5:].strip()))
                except ValueError:
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
        except ValueError:
            return text
    return result


def client(config_path=None, server=None):
    """The Portal client, built from the owner settings."""
    return Portal(*portal_endpoint(config_path, server))




def zone(name=None):
    """The named IANA zone, else the [calendar-steward-method] timezone setting, else UTC."""
    name = (name or "").strip() or str(settings("calendar-steward-method").get("timezone") or "").strip() or "UTC"
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise Bad(f"unknown timezone {name!r}") from None


def blank(value):
    """A launch form left blank sends `--x=`: the same as not given."""
    return str(value or "").strip()


def truthy(value):
    return blank(value).lower() in ("1", "true", "yes", "on")


def toolbox_root():
    """The repository (or, copied alone, the skill folder) these scripts live in."""
    here = Path(__file__).resolve().parent
    for folder in [here, *here.parents]:
        if (folder / ".git").exists():
            return folder
    return here.parent


def guard_run_path(path):
    """A run file never lives inside the toolbox: no state in the code."""
    target = Path(path).expanduser().resolve()
    try:
        target.relative_to(toolbox_root())
    except ValueError:
        return target
    raise Bad(f"{target} is inside the toolbox; run files live outside it")


def state_folder(explicit, key, name):
    """--flag, else the skill's setting, else <state_dir>/<name>; None when none is set."""
    chosen = blank(explicit) or blank(settings("calendar-steward-method").get(key))
    if not chosen and blank(settings().get("state_dir")):
        chosen = str(Path(blank(settings()["state_dir"])) / name)
    return Path(chosen).expanduser() if chosen else None


def home_dir(explicit):
    home = state_folder(explicit, "home", "calendar-steward")
    if home is None:
        raise Bad("set state_dir in the owner settings (or pass --home) for the steward's home folder")
    return home


# --------------------------------------------------------------------------- the calendar

CANCELLED_PREFIXES = ("canceled:", "cancelled:")
_CLONE_MARKER = re.compile(r"(?i)\s*[\(\[][^\)\]]*\bclone\b[^\)\]]*[\)\]]")
_REPLY_PREFIX = re.compile(r"^\s*(re|fwd|fw|aw|antw|rv|vs)\s*(\[\d+\])?\s*:\s*", re.IGNORECASE)
FOCUS_TITLE = r"(?i)\b(deep work|focus( time| block)?)\b"
# Personal mail domains are never an organisation's internal domain.
PUBLIC_MAIL = frozenset({"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "yahoo.com",
                         "icloud.com", "me.com", "aol.com", "proton.me", "protonmail.com"})


def parse_time(value):
    """An ISO timestamp or date as an aware UTC datetime; one with no zone is read as UTC.
    Anything that will not parse is None, so one bad row cannot take down a period."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso_z(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalise_title(title):
    """The comparable part of a title: clone markers, Canceled: and Re:/Fw: gone, case folded."""
    text = _CLONE_MARKER.sub("", str(title or ""))
    for prefix in CANCELLED_PREFIXES:
        if text.strip().lower().startswith(prefix):
            text = text.strip()[len(prefix):]
    while True:
        stripped = _REPLY_PREFIX.sub("", text, count=1)
        if stripped == text:
            break
        text = stripped
    return " ".join(text.split()).casefold()


def domain_of(address):
    return address.rsplit("@", 1)[-1].strip().lower() if "@" in address else ""


class Event:
    """One calendar row, read defensively. Never raises on a bad shape."""

    def __init__(self, raw):
        data = raw if isinstance(raw, dict) else {}
        self.raw = data
        self.ref = str(data.get("_ref") or "")
        self.title = str(data.get("title") or "").strip()
        self.kind = str(data.get("event_kind") or "").strip().lower()
        self.all_day = bool(data.get("is_all_day"))
        self.start = parse_time(data.get("start_time"))
        self.end = parse_time(data.get("end_time"))
        seconds = (self.end - self.start).total_seconds() if self.start and self.end else 0
        self.hours = round(seconds / 3600.0, 4) if seconds > 0 else 0.0
        self.people = [a for a in data.get("attendees") or [] if isinstance(a, dict)]
        self.attendees = []
        for entry in data.get("attendees") or []:
            address = entry if isinstance(entry, str) else next(
                (str(entry[k]) for k in ("email", "address", "email_address", "value")
                 if isinstance(entry, dict) and str(entry.get(k) or "").strip()), "")
            address = address.strip().strip("<>").lower()
            if "@" in address and address not in self.attendees:
                self.attendees.append(address)
        self.cancelled = self.title.lower().startswith(CANCELLED_PREFIXES)
        self.calendar_name = str(data.get("calendar_name") or "")
        self.key = (self.start.isoformat() if self.start else "", self.end.isoformat() if self.end else "",
                    normalise_title(self.title))

    @property
    def is_meeting(self):
        return self.kind == "meeting"

    @property
    def is_availability(self):
        return self.kind == "availability_block"


def page_events(portal, since, until, page=50, max_calls=200):
    """Every calendar row in [since, until), halving a page the server will not serialise
    (a large response fails outright rather than truncating), down to stepping over one bad
    row. Returns the rows and how many could not be read. Reading nothing at all is an error,
    never an empty calendar."""
    filters = {"since": iso_z(since), "until": iso_z(until)}
    items, offset, unreadable, total, calls = [], 0, 0, None, 0
    failure, read_any = "", False
    while calls < max_calls:
        served, size = None, page
        while calls < max_calls:
            args = {"entity_type": "calendar_event", "filters": filters, "limit": size}
            if offset:
                args["offset"] = offset
            calls += 1
            try:
                out = portal.call("list_entities", args)
            except Exception as exc:  # a page too large to serialise: try a smaller one
                failure = type(exc).__name__
                if size == 1:
                    break
                size = max(1, size // 2)
                continue
            served = out if isinstance(out, dict) else None
            break
        if served is None:
            unreadable += 1
            offset += 1
            if total is None or offset >= total:
                break
            continue
        read_any = True
        rows = [r for r in served.get("items") or [] if isinstance(r, dict)]
        if isinstance(served.get("total"), int):
            total = served["total"]
        items.extend(rows)
        if not rows:
            break
        offset += len(rows)
        if total is not None and offset >= total:
            break
        if not served.get("has_more") and size >= page:
            break
    if failure and not read_any:
        raise Failure(f"could not read any calendar rows from the Portal ({failure})")
    return items, unreadable


def owner_info(me, extra_internal=()):
    """The owner's contact, timezone, own addresses and internal mail domains, from whoami."""
    principal = me.get("principal") if isinstance(me.get("principal"), dict) else {}
    addresses = []
    for inbox in me.get("inboxes") or []:
        if isinstance(inbox, dict) and "@" in str(inbox.get("address") or ""):
            addresses.append(str(inbox["address"]).strip().lower())
    primary = str(principal.get("primary_email") or "").strip().lower()
    if primary and primary not in addresses:
        addresses.append(primary)
    domains = sorted({domain_of(a) for a in addresses if domain_of(a) not in PUBLIC_MAIL}
                     | {d.strip().lower() for d in extra_internal if d.strip()})
    return {"contact_id": principal.get("contact_id"), "timezone": principal.get("timezone"),
            "addresses": addresses, "internal_domains": [d for d in domains if d]}


def day_bounds(day, tz):
    start = datetime.combine(day, time(0, 0), tz)
    return start, datetime.combine(day + timedelta(days=1), time(0, 0), tz)


def local_hm(moment, tz):
    return moment.astimezone(tz).strftime("%H:%M") if moment else ""


def hhmm(text, option):
    value = blank(text)
    if not HHMM.match(value):
        raise Bad(f"{option} wants HH:MM, got {text!r}")
    return int(value[:2]), int(value[3:])


def owner_response(event, addresses):
    for person in event.people:
        if str(person.get("email") or "").strip().lower() in addresses:
            return str(person.get("response_status") or "")
    return ""


def clean_calendar(rows, addresses):
    """(timed events kept, all-day events, counts dropped by reason). Cancelled rows and rows
    the owner declined go; duplicates collapse onto the copy that is a meeting with the most
    people; an availability block at exactly a kept meeting's time is the same busy time."""
    dropped = {"cancelled": 0, "declined": 0, "duplicate": 0, "clone": 0}
    timed, all_day = [], []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        e = Event(raw)
        if e.cancelled:
            dropped["cancelled"] += 1
        elif owner_response(e, addresses).lower() == "declined":
            dropped["declined"] += 1
        elif e.all_day:
            all_day.append(e)
        elif e.start and e.end and e.end > e.start:
            timed.append(e)
    best, order = {}, []
    for e in timed:
        key = e.key
        seen = best.get(key)
        if seen is None:
            best[key] = e
            order.append(key)
            continue
        dropped["duplicate"] += 1
        if (e.is_meeting, len(e.people)) > (seen.is_meeting, len(seen.people)):
            best[key] = e
    kept = [best[k] for k in order]
    meeting_spans = {e.key[:2] for e in kept if not e.is_availability}
    block_spans, out = set(), []
    for e in kept:
        if e.is_availability:
            if e.key[:2] in meeting_spans or e.key[:2] in block_spans:
                dropped["clone"] += 1
                continue
            block_spans.add(e.key[:2])
        out.append(e)
    out.sort(key=lambda e: (e.start, e.end, e.title))
    return out, all_day, dropped


def merge_spans(spans):
    out = []
    for start, end in sorted(spans):
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


def day_calendar(rows, day, tz, owner, work, min_focus, focus_title=FOCUS_TITLE):
    """One day's calendar, cleaned: events as meeting, hold or focus; conflicts; free slots
    inside working hours of at least `min_focus` minutes. No Portal calls."""
    focus = re.compile(focus_title)
    mine, internal = set(owner["addresses"]), set(owner["internal_domains"])
    kept, all_day, dropped = clean_calendar(rows, mine)
    kinds = [(e, "focus" if focus.search(_CLONE_MARKER.sub("", e.title)) else
              "meeting" if e.is_meeting else "hold") for e in kept]
    events = []
    for e, kind in kinds:
        ext = []
        if kind == "meeting":
            for address in e.attendees:
                d = domain_of(address)
                if address not in mine and d and d not in internal and d not in ext:
                    ext.append(d)
        where = str(e.raw.get("location") or "").lower()
        events.append({"ref": e.ref, "title": e.title, "kind": kind, "start": local_hm(e.start, tz),
                       "end": local_hm(e.end, tz), "minutes": int((e.end - e.start).total_seconds() // 60),
                       "attendees": len(e.people),
                       "names": [str(p.get("name") or p.get("email") or "") for p in e.people
                                 if str(p.get("email") or "").strip().lower() not in mine][:6],
                       "external": bool(ext), "external_domains": ext[:5],
                       "owner_response": owner_response(e, mine),
                       "online": bool(e.raw.get("meeting_url")) or "teams" in where or "zoom" in where,
                       "calendar": e.calendar_name})
    conflicts = []
    for i, (a, ka) in enumerate(kinds):
        for b, kb in kinds[i + 1:]:
            if "focus" in (ka, kb) or (ka, kb) == ("hold", "hold"):
                continue
            start, end = max(a.start, b.start), min(a.end, b.end)
            if end > start:
                conflicts.append({"a": a.ref, "b": b.ref, "a_title": a.title, "b_title": b.title, "kinds": [ka, kb],
                                  "when": f"{local_hm(start, tz)}-{local_hm(end, tz)}",
                                  "minutes": int((end - start).total_seconds() // 60)})
    (sh, sm), (eh, em) = work
    lo, hi = datetime.combine(day, time(sh, sm), tz), datetime.combine(day, time(eh, em), tz)
    busy = merge_spans((max(e.start, lo), min(e.end, hi)) for e, k in kinds
                       if k in ("meeting", "hold") and e.end > lo and e.start < hi)
    free, cursor = [], lo
    for start, end in busy + [(hi, hi)]:
        if start > cursor:
            mins = int((start - cursor).total_seconds() // 60)
            if mins >= min_focus:
                free.append({"start": local_hm(cursor, tz), "end": local_hm(start, tz), "minutes": mins,
                             "focus_blocks": [e.title for e, k in kinds if k == "focus" and e.start < start and e.end > cursor]})
        cursor = max(cursor, end)
    meeting_minutes = sum(int((e - s).total_seconds() // 60)
                          for s, e in merge_spans((e.start, e.end) for e, k in kinds if k == "meeting"))
    return {"date": day.isoformat(), "weekday": day.strftime("%A"),
            "work_hours": f"{sh:02d}:{sm:02d}-{eh:02d}:{em:02d}", "min_focus": min_focus, "events": events,
            "all_day": [{"ref": e.ref, "title": e.title} for e in all_day], "conflicts": conflicts, "free": free,
            "free_minutes": sum(f["minutes"] for f in free), "meeting_minutes": meeting_minutes,
            "dropped": dropped, "raw_rows": len(rows)}


# --------------------------------------------------------------------------- files

def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise Bad(f"{path} is not readable JSON ({type(exc).__name__})") from None


def write_text(path, text):
    """Written beside the target and renamed over it, so a reader never sees half a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_json(path, value):
    write_text(path, json.dumps(value, indent=1, default=str) + "\n")


def append_jsonl(path, row):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str) + "\n")


def iso_now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_dir(folder, prefix):
    base = Path(folder) / f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    path, n = base, 1
    while path.exists():
        n += 1
        path = base.with_name(f"{base.name}-{n}")
    path.mkdir(parents=True)
    return path


# --------------------------------------------------------------------------- the steward

TOOL = "calendar-steward"
VERSION = 1
SCAN_TOOL = "calendar-steward-scan"
ORCHESTRATOR = "calendar-steward-orchestrator"
PASSES = ("auto", "propose", "approve")
KINDS = ("focus-block", "move", "decline", "prep")
# Every scan finding of these kinds needs a proposal or a stated dismissal.
MUST_COVER = ("conflict", "focus-overlap", "no-prep", "no-agenda", "back-to-back", "focus-short",
              "unanswered", "daily-plan")
MAX_PROPOSALS = 12
TITLE_MAX = 160
DRAFT_MAX = 1500
LIST_DAYS = 14   # an unapplied list stays answerable this long
ITEM_COLUMNS = ("id", "date", "n", "proposal", "kind", "title", "when", "event", "answer", "state", "outcome",
                "result", "updated_at", "by")
ITEM_STATES = ("proposed", "approved", "declined", "modified", "unavailable", "unclear", "unanswered",
               "would_apply", "applied", "unchanged", "refused", "failed", "expired", "superseded", "undone")
FINAL = ("applied", "unchanged", "refused", "expired", "declined", "superseded", "undone")

HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
UUID = r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}"
EVENT_REF = re.compile(rf"^portal://calendar_event/({UUID})$")
ANY_REF = re.compile(rf"^portal://(task|calendar_event|project|goal|email|note|document)/{UUID}$")
PROP_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,31}$")


def marker(day):
    """The list's marker, on its approval task, so the task is found again and never made twice."""
    return "cst" + hashlib.sha256(f"calendar-steward|{day}".encode()).hexdigest()[:12]


def minutes(text):
    return int(text[:2]) * 60 + int(text[3:5])


def short_day(day):
    d = date.fromisoformat(day)
    return f"{d.strftime('%a')} {d.strftime('%m-%d')}"


def finding_id(kind, day, refs):
    digest = hashlib.sha256("|".join(sorted(str(r) for r in refs)).encode()).hexdigest()[:8]
    return f"{kind}:{day}:{digest}"


def day_folders(home):
    """The home's list folders, one per day, oldest first."""
    return sorted(p for p in Path(home).glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]")
                  if p.is_dir() and folder_day(p) is not None)


def folder_day(folder):
    try:
        return date.fromisoformat(Path(folder).name)
    except ValueError:
        return None


def resolve_day(text, tz, now=None):
    value = blank(text)
    if not value:
        return (now or datetime.now(tz)).astimezone(tz).date()
    if not DAY.match(value):
        raise Bad(f"--date wants yyyy-mm-dd, got {value!r}")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise Bad(f"--date {value!r} is not a date") from None


def resolve_pass(text):
    value = blank(text).lower() or "auto"
    if value not in PASSES:
        raise Bad(f"--pass is auto, propose or approve, got {value!r}")
    return value


class Ledger:
    """CALENDAR-STEWARD-ITEMS.csv: one row per item, keyed by `id`, upserted, never deleted.
    A file whose header is not exactly ITEM_COLUMNS is refused rather than rewritten."""

    def __init__(self, home):
        self.path = Path(home) / "CALENDAR-STEWARD-ITEMS.csv"

    def rows(self):
        if not self.path.is_file():
            return []
        reader = csv.DictReader(io.StringIO(self.path.read_text(encoding="utf-8").lstrip("\ufeff")))
        if tuple(reader.fieldnames or ()) != ITEM_COLUMNS:
            raise Bad(f"{self.path} does not have the columns {', '.join(ITEM_COLUMNS)}")
        return list(reader)

    def upsert(self, row_id, fields):
        if "state" in fields and fields["state"] not in ITEM_STATES:
            raise Bad(f"state {fields['state']!r} is not one of {', '.join(ITEM_STATES)}")
        rows = self.rows()
        row = next((r for r in rows if r["id"] == row_id), None)
        if row is None:
            row = {k: "" for k in ITEM_COLUMNS}
            row["id"] = row_id
            rows.append(row)
        row.update({k: "" if v is None else str(v) for k, v in fields.items() if k in ITEM_COLUMNS and k != "id"})
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=ITEM_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        write_text(self.path, out.getvalue())


def _s(value):
    return " ".join(str(value or "").split())


def scan_events(scan):
    """Every event of the scan by its reference, with its day."""
    out = {}
    for d in (scan or {}).get("days") or []:
        for e in d.get("events") or []:
            if e.get("ref"):
                out[str(e["ref"])] = dict(e, date=d.get("date"))
    return out


def busy_overlap(scan, day, start, end, ignore=()):
    """The meetings and holds of the scan that overlap `day start-end`, as short lines."""
    lo, hi = minutes(start), minutes(end)
    hits = []
    for d in (scan or {}).get("days") or []:
        if d.get("date") != day:
            continue
        for e in d.get("events") or []:
            if e.get("kind") not in ("meeting", "hold") or e.get("ref") in ignore:
                continue
            if not (HHMM.match(str(e.get("start") or "")) and HHMM.match(str(e.get("end") or ""))):
                continue
            s, f = minutes(e["start"]), minutes(e["end"])
            if f <= s:   # runs past midnight
                f = 24 * 60
            if s < hi and lo < f:
                hits.append(f"{e.get('title')} {e.get('start')}-{e.get('end')}")
    return hits


def proposal_problems(prop, scan=None):
    """What is wrong with one proposal. With the scan, its event must be in it, a new time must
    be free there, a meeting with other attendees is never moved, and a decline is for an
    invitation the owner did not organise."""
    if not isinstance(prop, dict):
        return ["a proposal is not a JSON object"]
    pid = str(prop.get("id") or "")
    tag = f"proposal {pid or '?'}"
    out = [] if PROP_ID.match(pid) else [f"{tag}: id is required (letters, digits, _ . : -)"]
    kind = prop.get("kind")
    if kind not in KINDS:
        return out + [f"{tag}: kind must be one of {', '.join(KINDS)}"]
    if not _s(prop.get("why")):
        out.append(f"{tag}: why is required")
    if not 0 < len(_s(prop.get("title"))) <= TITLE_MAX:
        out.append(f"{tag}: title is 1 to {TITLE_MAX} characters")
    day = str(prop.get("date") or "")
    if not DAY.match(day):
        out.append(f"{tag}: date is yyyy-mm-dd")
    start, end = str(prop.get("start") or ""), str(prop.get("end") or "")
    if not HHMM.match(start):
        out.append(f"{tag}: start is HH:MM")
    if kind != "prep" and not HHMM.match(end):
        out.append(f"{tag}: end is HH:MM")
    elif HHMM.match(start) and HHMM.match(end) and kind == "focus-block" and minutes(end) <= minutes(start):
        out.append(f"{tag}: end is after start")
    events = scan_events(scan) if scan is not None else {}
    if kind in ("move", "decline", "prep"):
        ref = str(prop.get("event") or "")
        if not EVENT_REF.match(ref):
            out.append(f"{tag}: event is portal://calendar_event/<uuid>")
        elif scan is not None and ref not in events:
            out.append(f"{tag}: event {ref} is not in the scan")
        elif scan is not None:
            ev = events[ref]
            if kind == "move" and ev.get("others"):
                out.append(f"{tag}: {ev.get('title')!r} has other attendees; the steward never moves a meeting "
                           f"with other people on it (propose a decline with a new time in the draft)")
            if kind == "decline" and ev.get("owner_organizer"):
                out.append(f"{tag}: the owner organizes {ev.get('title')!r}; a decline is for an invitation")
    if kind == "focus-block":
        if prop.get("for") not in (None, "") and not ANY_REF.match(str(prop["for"])):
            out.append(f"{tag}: for is a portal:// reference")
        if scan is not None and DAY.match(day) and HHMM.match(start) and HHMM.match(end):
            hits = busy_overlap(scan, day, start, end)
            if hits:
                out.append(f"{tag}: {day} {start}-{end} is not free ({'; '.join(hits[:3])})")
    if kind == "move":
        to = prop.get("to") if isinstance(prop.get("to"), dict) else {}
        if not (DAY.match(str(to.get("date") or "")) and HHMM.match(str(to.get("start") or ""))
                and HHMM.match(str(to.get("end") or "")) and minutes(to["end"]) > minutes(to["start"])):
            out.append(f"{tag}: to is {{date, start, end}} with end after start")
        elif scan is not None:
            hits = busy_overlap(scan, to["date"], to["start"], to["end"], ignore=[str(prop.get("event") or "")])
            if hits:
                out.append(f"{tag}: the new time {to['date']} {to['start']}-{to['end']} is not free "
                           f"({'; '.join(hits[:3])})")
    if kind == "decline":
        draft = _s(prop.get("draft"))
        if not draft or len(draft) > DRAFT_MAX:
            out.append(f"{tag}: draft is the reply, 1 to {DRAFT_MAX} characters")
    if kind == "prep":
        if not _s(prop.get("prepare")):
            out.append(f"{tag}: prepare says in one line what to prepare")
        if prop.get("due") not in (None, "") and not DAY.match(str(prop["due"])):
            out.append(f"{tag}: due is yyyy-mm-dd")
    return out


def proposals_problems(doc, scan=None, day=None):
    if not isinstance(doc, dict):
        return ["the proposal file is not a JSON object"]
    out = []
    if doc.get("tool") != TOOL:
        out.append(f"tool is {doc.get('tool')!r}, not {TOOL!r}")
    if doc.get("version") != VERSION:
        out.append(f"version {doc.get('version')!r}; this reads {VERSION}")
    if not isinstance(doc.get("dry_run"), bool):
        out.append("dry_run must be true or false")
    if not DAY.match(str(doc.get("date") or "")):
        out.append("date is yyyy-mm-dd")
    elif day and doc["date"] != day:
        out.append(f"the proposals are for {doc['date']}, not {day}")
    props = doc.get("proposals")
    if not isinstance(props, list):
        return out + ["proposals is not a list"]
    if len(props) > MAX_PROPOSALS:
        out.append(f"{len(props)} proposals; at most {MAX_PROPOSALS} a day")
    ids = [str(p.get("id")) for p in props if isinstance(p, dict)]
    if len(ids) != len(set(ids)):
        out.append("proposal ids repeat")
    for p in props:
        out += proposal_problems(p, scan)
    if not isinstance(doc.get("findings") or [], list):
        out.append("findings is not a list")
    return out


def coverage_gaps(doc, scan):
    """Each scan finding with neither a proposal nor a dismissal in the proposal file."""
    if not scan:
        return []
    ids = {str(p.get("id")) for p in doc.get("proposals") or [] if isinstance(p, dict)}
    covered = set()
    for f in doc.get("findings") or []:
        if isinstance(f, dict) and (f.get("proposal") in ids or _s(f.get("dismissed"))):
            refs = f.get("ids") if isinstance(f.get("ids"), list) else [f.get("id")]
            covered.update(str(r) for r in refs if r)
    return [f"{f.get('id')}: {f.get('text')}" for f in scan.get("findings") or []
            if f.get("kind") in MUST_COVER and f.get("id") not in covered]


# --------------------------------------------------------------------------- the list

def item_when(p):
    day = str(p.get("date") or "")
    when = short_day(day) if DAY.match(day) else day
    return f"{when} {p.get('start')}" if p.get("kind") == "prep" else f"{when} {p.get('start')}-{p.get('end')}"


def item_line(p):
    kind, title = p.get("kind"), _s(p.get("title"))
    if kind == "focus-block":
        text = f"Add a focus block {item_when(p)}: {title}"
    elif kind == "move":
        to = p.get("to") or {}
        text = f"Move {title} from {item_when(p)} to {short_day(to['date'])} {to.get('start')}-{to.get('end')}"
    elif kind == "decline":
        text = f"Decline {title} ({item_when(p)}); the reply is drafted, never sent"
    else:
        due = f", by {short_day(str(p['due']))}" if DAY.match(str(p.get("due") or "")) else ""
        text = f"Prepare for {title} ({item_when(p)}){due}: {_s(p.get('prepare'))}"
    why = _s(p.get("why"))
    return text + (f". {why[:1].upper()}{why[1:]}" if why else "")


def number_items(doc):
    """The numbered items the owner answers, in the proposal file's order."""
    out = []
    for n, p in enumerate([p for p in doc.get("proposals") or [] if isinstance(p, dict)], start=1):
        item = {k: p.get(k) for k in ("id", "kind", "date", "start", "end", "title", "event", "to", "for", "draft",
                                      "prepare", "due", "why", "source", "from") if p.get(k) not in (None, "")}
        item["n"] = n
        item["line"] = item_line(p)
        out.append(item)
    return out


def items_hash(items):
    text = json.dumps([{k: v for k, v in it.items() if k != "line"} for it in items], sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def approval_lines(items):
    return [f"{it['n']}. {it['line']}" for it in items]


def render_list(doc, items, scan):
    """PROPOSALS.md: what the owner reads."""
    out = [f"# Calendar proposals for {doc['date']}", ""]
    if _s(doc.get("summary")):
        out += [_s(doc["summary"]), ""]
    window = (scan or {}).get("window") or {}
    if window:
        out += [f"Window: {window.get('start')} to {window.get('end')}.", ""]
    out += ["## Approval list", "",
            "Answer by number in one comment on the approval task, for example \"1) ok 2) no\" (\"rest ok\" "
            "answers the rest). Nothing you do not approve is changed. A decline is a draft; nothing is sent.", ""]
    out += approval_lines(items) if items else ["Nothing to change."]
    drafts = [it for it in items if it.get("kind") == "decline"]
    if drafts:
        out += ["", "## Decline drafts", ""]
        for it in drafts:
            out += [f"{it['n']}. {it.get('title')}:", "", "> " + _s(it.get("draft")), ""]
    dismissed = [f for f in doc.get("findings") or [] if isinstance(f, dict) and _s(f.get("dismissed"))]
    if dismissed:
        out += ["", "## Seen and left alone", ""]
        texts = {f.get("id"): f.get("text") for f in (scan or {}).get("findings") or []}
        for f in dismissed:
            refs = f.get("ids") if isinstance(f.get("ids"), list) else [f.get("id")]
            what = "; ".join(_s(texts.get(r) or r) for r in refs[:3]) + (f" and {len(refs) - 3} more" if len(refs) > 3 else "")
            out.append(f"- {what}: {_s(f['dismissed'])}")
    questions = [q for q in doc.get("questions") or [] if isinstance(q, dict) and _s(q.get("ask"))]
    if questions:
        out += ["", "## For you", ""]
        out += [f"- {_s(q['ask'])}" + (f" ({_s(q.get('why'))})" if _s(q.get("why")) else "") for q in questions]
    return "\n".join(out).rstrip() + "\n"


def task_text(items, day, mark):
    lines = [f"The calendar steward's proposals for {day}. Answer the list below in one comment here, for example "
             f"\"1) ok 2) no\" (\"rest ok\" answers the rest). Only what you approve is changed; a decline is drafted "
             f"and never sent.", ""]
    lines += approval_lines(items)
    for it in items:
        if it.get("kind") == "decline":
            lines += ["", f"Draft for {it['n']}: {_s(it.get('draft'))}"]
    lines += ["", f"{ORCHESTRATOR} via calendar-apply publish. Marker: {mark}"]
    return "\n".join(lines)[:7800]


# --------------------------------------------------------------------------- answers

SYNONYMS = {
    "ok": "ok", "okay": "ok", "yes": "ok", "y": "ok", "approve": "ok", "approved": "ok", "go": "ok",
    "agree": "ok", "agreed": "ok", "do": "ok",
    "no": "no", "n": "no", "skip": "no", "keep": "no", "leave": "no", "pass": "no", "nope": "no",
    "park": "park", "parked": "park", "someday": "park", "later": "park", "defer": "park",
    "done": "done", "complete": "done", "completed": "done", "finished": "done", "close": "done",
    "cancel": "cancel", "cancelled": "cancel", "drop": "cancel", "kill": "cancel",
    "waiting": "waiting", "wait": "waiting",
}
LETTERS = tuple("abcdef")
_ITEM = re.compile(r"(?:(?<=[\s,;])|^)(\d{1,3})(?:\s*-\s*(\d{1,3}))?\s*[).:]\s*(?=[A-Za-z])", re.M)
_LINE = re.compile(r"^[ \t]*(\d{1,3})(?:[ \t]*-[ \t]*(\d{1,3}))?[ \t]+(?=[A-Za-z])", re.M)
_ALL = re.compile(r"(?:(?<=[\s,;])|^)(all|rest|others)\b\s*[).:]?\s*(?=[A-Za-z])", re.I | re.M)
_WORD = re.compile(r"^\s*([A-Za-z]+)\b(.*)$", re.S)
_TRAILING = " \t\r\n,.;!-"
AGENT_LINE = re.compile(r"\(posted by .+?, an agent\)\s*\Z", re.S)
APPLY_MARKER = re.compile(r"\b(?:tsk|wkr)[0-9a-f]{12}\b")


def parse_answers(text):
    """Item number to the raw answer, and the raw answer for every other item (`rest ok`)."""
    tokens = []
    for m in _ITEM.finditer(text):
        tokens.append((m.start(), m.end(), (int(m.group(1)), int(m.group(2) or m.group(1)))))
    for m in _LINE.finditer(text):
        if not any(s <= m.start(1) < e for s, e, _ in tokens):
            tokens.append((m.start(1), m.end(), (int(m.group(1)), int(m.group(2) or m.group(1)))))
    for m in _ALL.finditer(text):
        tokens.append((m.start(), m.end(), "all"))
    tokens.sort(key=lambda t: t[0])
    answers, rest = {}, None
    for i, (_, end, what) in enumerate(tokens):
        stop = tokens[i + 1][0] if i + 1 < len(tokens) else len(text)
        body = text[end:stop].strip(_TRAILING)
        if what == "all":
            rest = body
            continue
        a, b = what
        if b < a or b - a > 100:
            continue
        for n in range(a, b + 1):
            answers[n] = body
    return answers, rest


def read_answer(raw):
    """The verb an answer starts with, and anything said beyond it."""
    m = _WORD.match(raw or "")
    if not m:
        return None, (raw or "").strip()
    word, extra = m.group(1).lower(), m.group(2).strip(_TRAILING)
    if word in SYNONYMS:
        return SYNONYMS[word], extra
    if len(word) == 1 and word in LETTERS:
        return word, extra
    return None, (raw or "").strip()


def resolve_answers(items, sources):
    """Each item's answer and state: approved, declined, modified, unavailable, unclear or
    unanswered. Only `ok` approves."""
    explicit, rest = {}, None
    for src in sources:
        found, all_rest = parse_answers(str(src.get("text") or ""))
        for n, raw in found.items():
            explicit[n] = {"raw": raw, "source": src.get("source")}
        if all_rest is not None:
            rest = {"raw": all_rest, "source": src.get("source")}
    out = []
    for it in items:
        ans = explicit.get(int(it["n"])) or rest
        row = {"n": it["n"], "id": it.get("id"), "answer": ans["raw"] if ans else None,
               "source": ans["source"] if ans else None, "state": "unanswered"}
        if ans:
            verb, extra = read_answer(ans["raw"])
            if verb is None:
                row["state"] = "unclear"
            elif extra:
                row["state"], row["extra"] = "modified", extra
            else:
                row["state"] = {"ok": "approved", "no": "declined"}.get(verb, "unavailable")
        out.append(row)
    counts = {}
    for r in out:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    numbers = {int(it["n"]) for it in items}
    return {"items": out, "counts": counts, "stray_numbers": sorted(n for n in explicit if n not in numbers)}


def task_uuid(ref):
    m = re.search(rf"({UUID})", str(ref or ""))
    return m.group(1).lower() if m else None


def comment_sources(portal, task_ref):
    """The owner's comments on the approval task, oldest first; an agent's comment is not theirs."""
    tid = task_uuid(task_ref)
    if not tid or portal is None:
        return []
    env = portal.call("get", {"entity_type": "task", "id_or_query": tid, "detail": "full"})
    if not isinstance(env, dict) or env.get("error"):
        raise Bad(f"the approval task {tid} could not be read")
    rows = sorted((x for x in env.get("comments") or [] if isinstance(x, dict)), key=lambda x: str(x.get("created_at") or ""))
    out = []
    for x in rows:
        body = str(x.get("body") or x.get("content") or "")
        if body.strip() and not AGENT_LINE.search(body) and not APPLY_MARKER.search(body):
            out.append({"source": f"portal://task/{tid} comment {x.get('id') or x.get('created_at')}",
                        "text": body, "at": x.get("created_at")})
    return out


def answer_sources(folder, portal=None, task_ref=None, form=""):
    out = comment_sources(portal, task_ref) if portal is not None and task_ref else []
    path = Path(folder) / "ANSWERS.md"
    if path.is_file():
        out.append({"source": str(path), "text": path.read_text(encoding="utf-8", errors="replace")})
    if blank(form):
        out.append({"source": "the launch form", "text": form})
    return out
