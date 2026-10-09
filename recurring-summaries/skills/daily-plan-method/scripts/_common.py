"""What the daily-plan scripts share: settings, the Insights Portal client, the day and the
pass, the plan note's title and markers, the plan file's contract, the state folder, the
markdown a plan renders to, and finding the day's note in the Portal.

The daily plan is one Portal note per day, "Daily Plan - <yyyy-mm-dd>", with one block per
pass between markers, the morning plan first and the evening close after it:

    # Daily Plan - 2030-03-04
    <!-- daily-plan:morning -->  ...  <!-- /daily-plan:morning -->
    <!-- daily-plan:evening -->  ...  <!-- /daily-plan:evening -->
    <!-- daily-plan:2030-03-04 -->

THE PLAN FILE (RUN/plan.json), written by the orchestrator:

    {"tool": "daily-plan", "version": 1, "date": "2030-03-04", "pass": "morning",
     "dry_run": false, "summary": "one line on the day",
     "top_three": [{"rank": 1, "title": "...", "ref": "portal://task/<id>", "reason": "...",
                    "slot": {"start": "09:00", "end": "10:30"}, "no_slot": ""}],
     "also_today": [{"title": "...", "ref": "...", "why": "..."}],
     "conflicts": [{"a": "portal://calendar_event/<id>", "b": "...", "when": "11:30-12:00", "suggest": "..."}],
     "prep": [{"ref": "...", "title": "...", "when": "11:30", "state": "prepped" | "needs prep",
               "note": "portal://note/<id>", "suggest": "..."}],
     "proposals": [{"id": "f1", "kind": "focus-block", "title": "Focus: ...", "start": "09:00",
                    "end": "10:30", "for": "portal://task/<id>", "why": "..."}],
     "close": {"items": [{"ref": "...", "title": "...", "outcome": "done" | "moved" | "carried" | "dropped",
                          "evidence": "portal://email/<id>", "new_date": "2030-03-05", "op": "e1",
                          "reason": "..."}],
               "done": ["..."], "tomorrow": [{"title": "...", "ref": "...", "reason": "..."}]},
     "questions": [{"ask": "...", "why": "..."}], "notes": ["..."]}

A morning plan has top_three and the lists after it; an evening plan has close. A slot is
local time on the plan's date.
"""

import hashlib
import json
import os
import re
import sys
import tomllib
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SKILL = "daily-plan-method"
SKILL_DIR = Path(__file__).resolve().parents[1]
TOOL, VERSION = "daily-plan", 1
PASSES = ("morning", "evening")
OUTCOMES = ("done", "moved", "carried", "dropped")
NOON = 12
TAGS = ("briefing", "daily-plan")
REF = re.compile(r"^portal://(task|calendar_event|project|goal|email|note|document)/"
                 r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Stop(Exception):
    """A problem that stops the script: one line, exit 2."""


# --------------------------------------------------------------------------- settings and folders

def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


def blank(value):
    """A launch form left blank sends `--x=`: the same as not given."""
    return (value or "").strip()


def state_root(explicit=None):
    """The daily plan's state folder: --state, else <state_dir>/daily-plan."""
    if blank(explicit):
        return Path(blank(explicit)).expanduser()
    base = settings().get("state_dir")
    if not base:
        raise Stop("setting state_dir is needed (where the daily plan keeps its published copies), or pass --state")
    return Path(base).expanduser() / "daily-plan"


def guard_run_path(path):
    """A Run folder or file never lives inside this skill's own folder."""
    target = Path(path).expanduser().resolve()
    if target == SKILL_DIR or SKILL_DIR in target.parents:
        raise Stop(f"{target} is inside the skill folder; Run files live outside it")
    return target


def state_file(state, day, pass_):
    return state / day.isoformat() / f"{pass_}.json"


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise Stop(f"{path} is not readable JSON ({type(exc).__name__})") from None


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=1, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)


# --------------------------------------------------------------------------- the Portal

class PortalError(Exception):
    """The Portal could not be reached or refused a call."""


_SECRETS = re.compile(r"(?i)(bearer\s+\S+|authorization[\"'\s:=]+\S+|[?&](?:key|token|api_key|access_token)=[^\s&\"']+)")


def safe(text):
    """Everything printed passes through here, so a bearer token is never shown."""
    return _SECRETS.sub("[redacted]", str(text))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect, so the bearer token only ever goes to the configured URL."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def portal_endpoint(config=None, server=None):
    """(url, Authorization header) from the MCP config the settings name. The token is
    INSIGHTS_PORTAL_ASSISTANT_TOKEN when set, else the config's Authorization header with
    ${VAR} expanded. HTTPS only, except plain HTTP to localhost."""
    conf = settings()
    config = config or conf.get("portal_mcp_config")
    server = server or conf.get("portal_server") or "insights-portal"
    if not config:
        raise PortalError("setting portal_mcp_config is needed (the MCP config holding the Portal server)")
    try:
        entry = json.loads(Path(config).expanduser().read_text())["mcpServers"][server]
    except (OSError, KeyError, TypeError, ValueError):
        raise PortalError(f"the MCP config has no usable server named {server!r}") from None
    token = os.environ.get("INSIGHTS_PORTAL_ASSISTANT_TOKEN", "").strip()
    auth = f"Bearer {token}" if token else (entry.get("headers") or {}).get("Authorization", "")

    def expand(value, what):
        def one(match):
            if not os.environ.get(match.group(1)):
                raise PortalError(f"the Portal {what} needs {match.group(1)}, which is not set")
            return os.environ[match.group(1)]
        value = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", one, value or "")
        if "${" in value or "\n" in value:
            raise PortalError(f"the Portal {what} is malformed")
        return value

    url, auth = expand(entry.get("url", ""), "URL"), expand(auth, "token")
    parts = urlsplit(url)
    local = parts.hostname in ("localhost", "127.0.0.1", "::1")
    if not parts.hostname or not (parts.scheme == "https" or (parts.scheme == "http" and local)):
        raise PortalError("the Portal URL must be HTTPS (HTTP only on localhost)")
    if not auth.startswith("Bearer ") or not auth[7:].strip():
        raise PortalError("no Portal bearer token: set INSIGHTS_PORTAL_ASSISTANT_TOKEN or put one in the config")
    return url, auth


class Portal:
    """A small JSON-RPC client for the Portal's MCP tools."""

    def __init__(self, config=None, server=None, timeout=60):
        self.url, self._auth = portal_endpoint(config, server)
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


def list_all(client, entity_type, filters=None, limit=200, max_pages=50):
    """Every item of one entity type, following next_offset until has_more is false."""
    args = {"entity_type": entity_type, "limit": limit}
    if filters:
        args["filters"] = filters
    items, offset = [], 0
    for _ in range(max_pages):
        if offset:
            args["offset"] = offset
        out = client.call("list_entities", args)
        if not isinstance(out, dict):
            break
        items.extend(i for i in out.get("items") or [] if isinstance(i, dict))
        nxt = out.get("next_offset")
        if not out.get("has_more") or not isinstance(nxt, int) or nxt <= offset:
            break
        offset = nxt
    return items


def page_through(client, entity_type, filters=None, sizes=(200, 50, 10, 1), max_calls=400):
    """Every row of one entity type, page by page: (rows, rows it could not read).

    A page the server refuses (one stored row it will not serialise) is retried at smaller
    sizes down to one row, and that one row is stepped over, so a bad record costs one row
    rather than the whole listing. Reading nothing at all, with failures, is an error.
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
            except Exception as exc:
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
        raise PortalError(f"could not read any {entity_type} rows from the Portal ({failure})")
    return items, unreadable


def emit(payload, code=0):
    """Print one JSON object (secrets redacted) and exit."""
    print(safe(json.dumps(payload, indent=1, default=str)))
    sys.exit(code)


def owner_timezone(client):
    """The owner's timezone name from whoami, or ""."""
    me = client.call("whoami")
    return str(((me or {}).get("principal") or {}).get("timezone") or "") if isinstance(me, dict) else ""


# --------------------------------------------------------------------------- the day and the pass

def parse_time(value):
    """An ISO timestamp or date as an aware UTC datetime; None when it will not parse."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    text = str(value or "").strip()
    if not text:
        return None
    if text[-1] in "Zz":
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


def zone(name):
    """The owner's timezone: the name given (--tz or the Portal's), else the setting
    [daily-plan-method] timezone."""
    name = blank(name) or str(settings(SKILL).get("timezone") or "")
    if not name:
        raise Stop("no timezone: pass --tz, or set [daily-plan-method] timezone (the Portal named none)")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise Stop(f"unknown timezone {name!r}") from None


def resolve(day, pass_, tz, now=None):
    """The day (blank: today in the owner's zone) and the pass (blank: by the clock,
    morning before noon and evening after)."""
    now = (now or datetime.now(tz)).astimezone(tz)
    text = blank(day)
    if text:
        if not DAY.match(text):
            raise Stop(f"--date wants yyyy-mm-dd, got {text!r}")
        try:
            the_day = date.fromisoformat(text)
        except ValueError:
            raise Stop(f"--date {text!r} is not a date") from None
    else:
        the_day = now.date()
    which = blank(pass_).lower() or ("morning" if now.hour < NOON else "evening")
    if which not in PASSES:
        raise Stop(f"--pass is morning or evening, got {which!r}")
    return the_day, which


def hhmm(text, option):
    value = blank(text)
    if not HHMM.match(value):
        raise Stop(f"{option} wants HH:MM, got {text!r}")
    return int(value[:2]), int(value[3:])


def next_workday(day):
    nxt = day + timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    return nxt


# --------------------------------------------------------------------------- the note

def title(day):
    return f"Daily Plan - {day.isoformat()}"


def day_marker(day):
    return f"<!-- daily-plan:{day.isoformat()} -->"


def open_marker(pass_):
    return f"<!-- daily-plan:{pass_} -->"


def close_marker(pass_):
    return f"<!-- /daily-plan:{pass_} -->"


def blocks(content, pass_):
    """Every block of the pass in the note as (start, end just after the closing marker, inner text)."""
    out, pos = [], 0
    start_tag, end_tag = open_marker(pass_), close_marker(pass_)
    while True:
        i = content.find(start_tag, pos)
        j = content.find(end_tag, i) if i >= 0 else -1
        if i < 0 or j < 0:
            return out
        out.append((i, j + len(end_tag), content[i + len(start_tag):j].strip("\n")))
        pos = j + len(end_tag)


def digest(text):
    """A block's hash, line-end spaces and blank ends ignored, so it reads back the same
    however the Portal trims it."""
    norm = "\n".join(line.rstrip() for line in text.strip().splitlines())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def read_note(client, note_id):
    out = client.call("get", {"entity_type": "note", "id_or_query": note_id, "detail": "full"})
    if isinstance(out, dict) and isinstance(out.get("note"), dict):
        out = out["note"]
    return out if isinstance(out, dict) and not out.get("error") and out.get("id") else None


def find_notes(client, day):
    """Every note that is the day's plan note, oldest first, each read in full. Found by the
    title through search and confirmed by reading it: the title is exactly the day's, or the
    content carries the day's marker. The oldest is the day's note; others are reported."""
    name, marker = title(day), day_marker(day)
    out = client.call("search", {"query": f'"{name}"', "limit": 20})
    hits = [h for h in (out.get("notes") or []) if isinstance(h, dict)] if isinstance(out, dict) else []
    found = []
    for hit in hits:
        if not hit.get("id"):
            continue
        if str(hit.get("title") or "").strip() != name and marker not in str(hit.get("content_preview") or ""):
            continue
        note = read_note(client, str(hit["id"]))
        if note and (str(note.get("title") or "").strip() == name or marker in str(note.get("content") or "")):
            found.append(note)
    return sorted(found, key=lambda n: str(n.get("created_at") or ""))


def note_summary(note, others=0):
    """What the pull and the check say about the day's note."""
    if note is None:
        return {"exists": False}
    content = str(note.get("content") or "")
    return {"exists": True, "id": note.get("id"), "ref": f"portal://note/{note.get('id')}",
            "updated_at": note.get("updated_at"), "visibility": note.get("visibility"),
            "has_morning": bool(blocks(content, "morning")), "has_evening": bool(blocks(content, "evening")),
            "duplicates": others}


# --------------------------------------------------------------------------- the plan file

def plan_problems(plan, day=None, pass_=None):
    """What is wrong with a plan file's shape (empty when nothing)."""
    if not isinstance(plan, dict):
        return ["the plan is not a JSON object"]
    out = []
    if plan.get("tool") not in (TOOL, f"{TOOL}-orchestrator"):
        out.append(f"tool is {plan.get('tool')!r}, not {TOOL!r}")
    if plan.get("version") != VERSION:
        out.append(f"version {plan.get('version')!r}; this reads {VERSION}")
    if not isinstance(plan.get("dry_run"), bool):
        out.append("dry_run must be true or false")
    if plan.get("pass") not in PASSES:
        out.append(f"pass {plan.get('pass')!r} is not morning or evening")
    elif pass_ and plan.get("pass") != pass_:
        out.append(f"the plan is the {plan.get('pass')} pass, not the {pass_}")
    if not DAY.match(str(plan.get("date") or "")):
        out.append(f"date {plan.get('date')!r} is not yyyy-mm-dd")
    elif day and plan.get("date") != day.isoformat():
        out.append(f"the plan is for {plan.get('date')}, not {day.isoformat()}")
    for key in ("top_three", "also_today", "conflicts", "prep", "proposals", "questions"):
        if key in plan and not isinstance(plan[key], list):
            out.append(f"{key} is not a list")
    if "close" in plan and not isinstance(plan["close"], dict):
        out.append("close is not an object")
    return out


def load_plan(path, day=None, pass_=None):
    plan = read_json(path)
    if plan is None:
        raise Stop(f"{path} does not exist")
    problems = plan_problems(plan, day, pass_)
    if problems:
        raise Stop(f"{path}: " + "; ".join(problems))
    return plan


# --------------------------------------------------------------------------- rendering

def _s(value):
    return " ".join(str(value or "").split())


def _ref(value):
    return f" ({_s(value)})" if _s(value) else ""


def _then(value):
    return f". {_s(value)}" if _s(value) else ""


def _dicts(value):
    return [x for x in value or [] if isinstance(x, dict)]


def _slot(item):
    slot = item.get("slot") if isinstance(item.get("slot"), dict) else None
    if slot and slot.get("start") and slot.get("end"):
        return f"{_s(slot['start'])}-{_s(slot['end'])}"
    return f"no slot: {_s(item.get('no_slot')) or 'none given'}"


def _questions(plan):
    questions = [q for q in _dicts(plan.get("questions")) if _s(q.get("ask"))]
    if not questions:
        return []
    return ["", "### For you", ""] + [f"{n}. {_s(q.get('ask'))}" + (f" ({_s(q.get('why'))})" if _s(q.get("why")) else "")
                                      for n, q in enumerate(questions, start=1)]


def render_morning(plan):
    out = ["## Morning plan", ""]
    if _s(plan.get("summary")):
        out += [_s(plan["summary"]), ""]
    out += ["### Top three", ""]
    top = _dicts(plan.get("top_three"))
    if not top:
        out.append("Nothing earns a top-three place today.")
    for n, item in enumerate(sorted(top, key=lambda t: t.get("rank") or 99), start=1):
        out.append(f"{n}. **{_s(item.get('title'))}** [{_slot(item)}]{_ref(item.get('ref'))}")
        out.append(f"   Why today: {_s(item.get('reason'))}")
    also = _dicts(plan.get("also_today"))
    if also:
        out += ["", "### Also today", ""]
        out += [f"- {_s(a.get('title'))}{_ref(a.get('ref'))}" + (f": {_s(a.get('why'))}" if _s(a.get("why")) else "")
                for a in also]
    conflicts = _dicts(plan.get("conflicts"))
    out += ["", "### Conflicts", ""]
    out += [f"- {_s(x.get('when'))}: {_s(x.get('a_title') or x.get('a'))} and {_s(x.get('b_title') or x.get('b'))}"
            + _then(x.get("suggest")) for x in conflicts] or ["None."]
    prep = _dicts(plan.get("prep"))
    if prep:
        out += ["", "### Meetings and prep", ""]
        out += [f"- {_s(p.get('when'))} {_s(p.get('title'))}: {_s(p.get('state'))}"
                + _ref(p.get("note") or p.get("ref")) + _then(p.get("suggest")) for p in prep]
    proposals = _dicts(plan.get("proposals"))
    if proposals:
        out += ["", "### Calendar proposals (the calendar steward's next approval list carries these)", ""]
        out += [f"{n}. {_s(p.get('kind') or 'focus-block')} {_s(p.get('start'))}-{_s(p.get('end'))}: "
                f"{_s(p.get('title'))}" + _then(p.get("why")) for n, p in enumerate(proposals, start=1)]
    return "\n".join(out + _questions(plan)).rstrip()


def render_evening(plan):
    close = plan.get("close") if isinstance(plan.get("close"), dict) else {}
    out = ["## Evening close", ""]
    if _s(plan.get("summary")):
        out += [_s(plan["summary"]), ""]
    items = _dicts(close.get("items"))
    out += ["### The plan against the day", ""]
    if not items:
        out.append("No morning plan to account for.")
    for item in items:
        outcome, tail = _s(item.get("outcome")), ""
        if outcome == "done" and _s(item.get("evidence")):
            tail = f", evidence {_s(item.get('evidence'))}"
        elif outcome == "moved":
            tail = f" to {_s(item.get('new_date'))}"
        out.append(f"- {outcome.upper() or '?'}{tail}: {_s(item.get('title'))}{_ref(item.get('ref'))}"
                   + _then(item.get("reason")))
    done = [d for d in close.get("done") or [] if _s(d)]
    if done:
        out += ["", "### Done today", ""] + [f"- {_s(d)}" for d in done]
    tomorrow = _dicts(close.get("tomorrow"))
    out += ["", "### Tomorrow's three", ""]
    out += [f"{n}. **{_s(t.get('title'))}**{_ref(t.get('ref'))}: {_s(t.get('reason'))}"
            for n, t in enumerate(tomorrow, start=1)] or ["None named."]
    return "\n".join(out + _questions(plan)).rstrip()


def render(plan):
    return render_morning(plan) if plan.get("pass") == "morning" else render_evening(plan)
