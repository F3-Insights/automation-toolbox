"""Shared helpers for this skill's scripts: owner settings, a read-only Insights Portal
client, and the date and status rules a project score is built from.

The Portal endpoint and bearer come from the MCP config file the `portal_mcp_config` setting
names (server `portal_server`, default `insights-portal`). The bearer is
`INSIGHTS_PORTAL_ASSISTANT_TOKEN` when set, else the config's Authorization header with
`${VAR}` expanded from the environment. It is never printed. HTTPS only, except plain HTTP
to localhost, and a redirect is refused so the bearer goes nowhere else.
"""

import json
import os
import re
import tomllib
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


class SettingMissing(Exception):
    """An owner setting the script needs is not set."""


class PortalError(Exception):
    """The Portal could not be reached or refused the call."""


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
    """Text on its way to the screen, with anything shaped like a token blanked out."""
    return _SECRETS.sub("[redacted]", str(text))


# --------------------------------------------------------------------------- the Portal

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def portal_endpoint(config_path=None, server=None):
    """(url, Authorization header) for the Portal, from settings and the environment."""
    top = settings()
    config_path = config_path or top.get("portal_mcp_config")
    server = server or top.get("portal_server") or "insights-portal"
    if not config_path:
        raise SettingMissing("set portal_mcp_config in the owner settings to the MCP config holding the Portal")
    path = Path(str(config_path)).expanduser()
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))["mcpServers"][server]
    except (OSError, ValueError, KeyError, TypeError):
        raise PortalError(f"{path} has no usable mcpServers entry named {server!r}") from None
    token = os.environ.get("INSIGHTS_PORTAL_ASSISTANT_TOKEN", "").strip()
    auth = f"Bearer {token}" if token else (cfg.get("headers") or {}).get("Authorization") or ""
    url = cfg.get("url") or ""

    def expand(value, what):
        def one(match):
            if not os.environ.get(match.group(1)):
                raise PortalError(f"the Portal {what} needs {match.group(1)}, which is not set")
            return os.environ[match.group(1)]
        value = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", one, value)
        if "${" in value or "\n" in value or "\r" in value:
            raise PortalError(f"the Portal {what} is malformed")
        return value

    if not url or not auth:
        raise PortalError(f"the {server!r} entry in {path} needs a url and a token")
    url, auth = expand(url, "URL"), expand(auth, "token")
    parts = urlsplit(url)
    local = parts.hostname in ("localhost", "127.0.0.1", "::1")
    if not parts.hostname or parts.username or parts.password or not (
            parts.scheme == "https" or (parts.scheme == "http" and local)):
        raise PortalError("the Portal URL must be HTTPS (HTTP only on localhost)")
    if not auth.startswith("Bearer ") or not auth[7:].strip():
        raise PortalError("the Portal token is not a bearer token")
    return url, auth


class Portal:
    """A JSON-RPC client for the Portal MCP server. Only read calls are used here."""

    def __init__(self, url, auth, timeout=60):
        self.url, self._auth, self.timeout = url, auth, timeout
        self.calls = 0

    def call(self, tool, arguments=None):
        self.calls += 1
        body = json.dumps({"jsonrpc": "2.0", "id": self.calls, "method": "tools/call",
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
        except urllib.error.URLError as exc:
            raise PortalError(f"portal {tool}: {exc.reason}") from None
        except OSError as exc:
            raise PortalError(f"portal {tool}: {type(exc).__name__}") from None
        # The server answers with plain JSON or a server-sent-events stream; take the last message.
        messages = [json.loads(raw)] if raw.lstrip().startswith("{") else []
        for line in raw.splitlines() if not messages else []:
            if line.startswith("data:"):
                try:
                    messages.append(json.loads(line[5:].strip()))
                except ValueError:
                    pass
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


def connect(config_path=None, server=None):
    return Portal(*portal_endpoint(config_path, server))


RETRY_PAGES = (200, 50, 10, 1)


def page_through(client, entity_type, filters=None, max_calls=400):
    """Every row of one entity type, page by page.

    A page the server refuses to serialise (one bad row makes a whole page fail) is retried
    at smaller sizes down to one row, so a bad row costs that row and not the corpus.
    Returns (rows, how many rows could not be read).
    """
    items, offset, unreadable, total, calls, failure = [], 0, 0, None, 0, ""
    while calls < max_calls:
        served = None
        for size in RETRY_PAGES:
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
            except Exception as exc:  # a page the server will not serialise
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
        if size >= RETRY_PAGES[0] and not out.get("has_more"):
            break
    if failure and not items:
        # Reading nothing at all is a dead connection, not an empty portfolio.
        raise PortalError(f"could not read any {entity_type} rows from the Portal ({failure})")
    return items, unreadable


# --------------------------------------------------------------------------- dates and statuses

# Any status not listed as closed counts as open, so an unfamiliar one stays visible.
CLOSED_PROJECT = {"completed", "complete", "done", "cancelled", "canceled", "archived", "closed", "abandoned"}
CLOSED_TASK = {"done", "completed", "complete", "cancelled", "canceled", "archived", "closed", "dropped"}
WAITING_TASK = {"waiting", "blocked", "waiting_on", "on_hold", "deferred"}
DUE_KEYS = ("due_date", "deadline")
ACTIVITY_KEYS = ("updated_at", "completed_at", "created_at")
WEIGHTS = {"deadline": 0.20, "staleness": 0.20, "risk": 0.15}
MECHANICAL_MAX = 55  # deadline, staleness and risk weights, on the composite's 0-100 scale
DUE_SOON_DAYS, STALE_DAYS, WAITING_AGE_DAYS, WAITING_HEAVY = 7, 30, 7, 3


def parse_time(value):
    """An ISO date or timestamp as an aware UTC datetime; a stamp with no zone is UTC.
    Anything that will not parse gives None, so one bad row cannot stop the read."""
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


def first_time(item, keys):
    for key in keys:
        found = parse_time(item.get(key))
        if found is not None:
            return found
    return None


def days_between(later, earlier):
    """Whole calendar days from earlier to later."""
    return (later.date() - earlier.date()).days


def is_active_project(p):
    if p.get("is_archived") or p.get("is_general"):
        return False
    return str(p.get("status") or "").strip().lower() not in CLOSED_PROJECT


def is_open_task(t):
    return not t.get("is_archived") and str(t.get("status") or "").strip().lower() not in CLOSED_TASK


def is_waiting_task(t):
    return str(t.get("status") or "").strip().lower() in WAITING_TASK


def owner_of(project, tasks):
    """(has an owner, where it was read): the project's assignee, else any open task's owner."""
    if str(project.get("assignee_contact_id") or "").strip():
        return True, "project.assignee_contact_id"
    for t in tasks:
        if is_open_task(t) and str(t.get("owner_contact_id") or t.get("owner_user_id") or "").strip():
            return True, "task.owner_contact_id"
    return False, ""


# --------------------------------------------------------------------------- the mechanical score

def deadline_component(tasks, now):
    """Tasks due within 7 days: 1 = 25, 2 = 50, 3+ = 75; any overdue P1 or P2 = 100."""
    soon = overdue = urgent = bad = 0
    nearest = None
    for t in tasks:
        when = first_time(t, DUE_KEYS)
        if when is None:
            if any(str(t.get(k) or "").strip() for k in DUE_KEYS):
                bad += 1  # a due date was there and would not parse
            continue
        gap = days_between(when, now)
        if nearest is None or when < nearest:
            nearest = when
        if gap < 0:
            overdue += 1
            urgent += str(t.get("priority") or "").strip().upper() in ("P1", "P2")
        elif gap <= DUE_SOON_DAYS:
            soon += 1
    score = 100 if urgent else {0: 0, 1: 25, 2: 50}.get(soon, 75)
    return {"score": score, "nearest_due_date": nearest.date().isoformat() if nearest else None,
            "days_to_nearest_due": days_between(nearest, now) if nearest else None,
            "due_within_7d": soon, "overdue": overdue, "overdue_p1_p2": urgent, "unparseable_due_dates": bad}


def staleness_component(project, tasks, now):
    """Days since the latest timestamp on the project or any of its tasks:
    0-7 = 0, 8-14 = 25, 15-30 = 50, 31-60 = 75, over 60 = 100. Nothing datable scores 100."""
    latest, basis = None, ""
    for item, kind in [(project, "project"), *((t, "task") for t in tasks)]:
        for key in ACTIVITY_KEYS:
            when = parse_time(item.get(key))
            if when is not None and (latest is None or when > latest):
                latest, basis = when, f"{kind}.{key}"
    if latest is None:
        return {"score": 100, "last_activity_at": None, "days_since_activity": None, "basis": None, "datable": False}
    days = max(0, days_between(now, latest))
    score = 0 if days <= 7 else 25 if days <= 14 else 50 if days <= 30 else 75 if days <= 60 else 100
    return {"score": score, "last_activity_at": latest.date().isoformat(), "days_since_activity": days,
            "basis": basis, "datable": True}


def load_component(tasks, now):
    """Open, waiting and overdue counts, and the risk arithmetic:
    30 per overdue task plus 20 per task waiting over 7 days, capped once at 100."""
    open_tasks = [t for t in tasks if is_open_task(t)]
    waiting = [t for t in open_tasks if is_waiting_task(t)]
    waiting_old = sum(1 for t in waiting if (w := first_time(t, ACTIVITY_KEYS)) and days_between(now, w) > WAITING_AGE_DAYS)
    overdue = sum(1 for t in open_tasks if (d := first_time(t, DUE_KEYS)) and days_between(d, now) < 0)
    created = sum(1 for t in tasks if (c := parse_time(t.get("created_at"))) and days_between(now, c) <= DUE_SOON_DAYS)
    return {"open_tasks": len(open_tasks), "waiting_tasks": len(waiting), "waiting_over_7d": waiting_old,
            "overdue_tasks": overdue, "total_tasks": len(tasks),
            # A listing does not reliably include completed tasks, so this is unknown, not zero.
            "completed_last_7d": None, "created_last_7d": created,
            "risk_from_counts": min(100, 30 * overdue + 20 * waiting_old)}


def next_dated_task(tasks, now):
    """The soonest due date on an open task that has not passed."""
    dates = [d for t in tasks if is_open_task(t) and (d := first_time(t, DUE_KEYS)) and days_between(d, now) >= 0]
    return min(dates).date().isoformat() if dates else None


def flags_for(deadline, staleness, load, has_owner, has_goal, next_task):
    flags = []
    if not has_owner:
        flags.append("NO_OWNER")
    if not has_goal:
        flags.append("NO_GOAL")
    if load["total_tasks"] == 0:
        flags.append("NO_TASKS")
    if next_task is None:
        flags.append("NO_NEXT_TASK")
    if deadline["overdue"]:
        flags.append("OVERDUE")
    if deadline["due_within_7d"]:
        flags.append("DUE_SOON")
    if not staleness["datable"]:
        flags.append("UNDATED")
    elif (staleness["days_since_activity"] or 0) >= STALE_DAYS:
        flags.append("STALE_30D")
    w = load["waiting_tasks"]
    if w >= WAITING_HEAVY or (w and w * 2 >= load["open_tasks"]):
        flags.append("WAITING_HEAVY")
    return flags


def score_project(project, tasks, domains, goals, now):
    """One project's mechanical score: deadline, staleness and the risk counts.
    Heat, domain weight and neglect are left as null for a model to fill."""
    deadline = deadline_component(tasks, now)
    staleness = staleness_component(project, tasks, now)
    load = load_component(tasks, now)
    next_task = next_dated_task(tasks, now)
    has_owner, basis = owner_of(project, tasks)
    goal_id = str(project.get("goal_id") or "").strip()
    components = {"deadline": deadline["score"], "staleness": staleness["score"],
                  "risk": None, "heat": None, "domain_weight": None, "neglect": None}
    score = round(deadline["score"] * WEIGHTS["deadline"] + staleness["score"] * WEIGHTS["staleness"]
                  + load["risk_from_counts"] * WEIGHTS["risk"], 1)
    return {
        "project_id": str(project.get("id") or ""),
        "name": str(project.get("name") or project.get("title") or "").strip(),
        "domain": domains.get(str(project.get("domain_id") or "").strip(), ""),
        "goal": goals.get(goal_id, "") if goal_id else "",
        "status": str(project.get("status") or ""),
        "priority": str(project.get("priority") or ""),
        "components": components,
        "mechanical": {"deadline_pressure": deadline, "staleness": staleness, "load": load,
                       "has_owner": has_owner, "owner_basis": basis or None,
                       "has_goal": bool(goal_id), "next_dated_task": next_task},
        "mechanical_score": score,
        "mechanical_score_max": MECHANICAL_MAX,
        "flags": flags_for(deadline, staleness, load, has_owner, bool(goal_id), next_task),
    }
