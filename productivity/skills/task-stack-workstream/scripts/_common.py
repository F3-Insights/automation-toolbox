"""What the task-stack scripts share: settings, the Insights Portal client, the paged reader,
dates, and the tests a task title and a project are judged by.

task_stack_check.py scores the stack with these; task_stack_apply.py writes it under the same
tests, so the score and the writer cannot drift apart.
"""

import json
import os
import re
import sys
import tomllib
import urllib.error
import urllib.request
from collections import Counter
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlsplit

SKILL = "task-stack-workstream"
SKILL_DIR = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- settings

def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


def setting_list(key):
    """A list setting of this skill's table, e.g. `assignable_contacts`; empty when unset."""
    value = settings(SKILL).get(key) or []
    return [str(v).strip() for v in (value if isinstance(value, list) else [value]) if str(v).strip()]


class Stop(Exception):
    """A problem that stops the script: printed on one line, exit 2."""


def state_root(explicit=None):
    """The task stack's state folder (write journal, lock, capture ledger): `--state`, else
    `<state_dir>/task-stack` from the shared `state_dir` setting."""
    if explicit:
        return Path(explicit).expanduser()
    base = settings().get("state_dir")
    if not base:
        raise Stop("setting state_dir is needed (the folder where the task stack keeps its journal), "
                   "or pass --state")
    return Path(base).expanduser() / "task-stack"


def guard_run_path(path):
    """A Run folder or file never lives inside this skill's own folder."""
    target = Path(path).expanduser().resolve()
    if target == SKILL_DIR or SKILL_DIR in target.parents:
        raise Stop(f"{target} is inside the skill folder; Run files live outside it")
    return target


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
    """(url, Authorization header) for the Portal, from the MCP config the settings name.

    The token is INSIGHTS_PORTAL_ASSISTANT_TOKEN when set, else the config's Authorization
    header with ${VAR} expanded from the environment. HTTPS only, except plain HTTP to
    localhost. Errors name what is missing, never a value.
    """
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
    """A small JSON-RPC client for the Portal's MCP tools: `call(tool, args)` returns the
    tool's parsed answer. Only the calls the task-stack scripts make go through it."""

    def __init__(self, config=None, server=None, timeout=60):
        self.url, self._auth = portal_endpoint(config, server)
        self.timeout = timeout
        self._id = 0
        self.calls = 0

    def call(self, tool, arguments=None):
        self._id += 1
        self.calls += 1
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


RETRY_PAGES = (200, 50, 10, 1)


def page_through(client, entity_type, filters=None, max_calls=400):
    """Every row of one entity type, page by page: (rows, rows it could not read).

    A page the server refuses (one stored row it will not serialise) is retried at smaller
    sizes down to one row, and that one row is stepped over, so a single bad record costs one
    row rather than the whole listing. Reading nothing at all, with failures, is an error.
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
        raise PortalError(f"could not read any {entity_type} rows from the Portal ({failure})")
    return items, unreadable


# --------------------------------------------------------------------------- dates and states

CLOSED_PROJECT_STATUSES = frozenset({"completed", "complete", "done", "cancelled", "canceled", "archived",
                                     "closed", "abandoned"})
CLOSED_TASK_STATUSES = frozenset({"done", "completed", "complete", "cancelled", "canceled", "archived",
                                  "closed", "dropped"})
CLOSED_GOAL_STATUSES = frozenset({"achieved", "completed", "complete", "done", "cancelled", "canceled",
                                  "abandoned", "archived", "closed"})
DUE_KEYS = ("due_date", "deadline")
ACTIVITY_KEYS = ("updated_at", "completed_at", "created_at")


def parse_time(value):
    """An ISO timestamp or date as an aware UTC datetime; None when it will not parse.
    A timestamp without a zone is read as UTC, the Portal's own zone."""
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


def status_of(item):
    return str(item.get("status") or "").strip().upper()


def is_open_task(task):
    return not task.get("is_archived") and status_of(task).lower() not in CLOSED_TASK_STATUSES


def is_active_project(project):
    """Active and judged: not archived, not closed, not a domain's catch-all bucket."""
    return (not project.get("is_archived") and not project.get("is_general")
            and status_of(project).lower() not in CLOSED_PROJECT_STATUSES)


def is_active_goal(goal):
    return not goal.get("is_archived") and status_of(goal).lower() not in CLOSED_GOAL_STATUSES


def owner_of(project, tasks):
    """Whether anyone owns the project: its assignee, or the owner of an open task on it."""
    if str(project.get("assignee_contact_id") or "").strip():
        return True, "project.assignee_contact_id"
    for task in tasks:
        if is_open_task(task) and str(task.get("owner_contact_id") or task.get("owner_user_id") or "").strip():
            return True, "task.owner_contact_id"
    return False, ""


# A minute of `updated_at` shared by this many projects (or tasks) is a bulk edit of the
# records, not work on them, and does not count as activity.
BULK_PROJECTS, BULK_TASKS = 5, 10


def minute(value):
    when = parse_time(value)
    return when.strftime("%Y-%m-%dT%H:%M") if when else None


def bulk_minutes(projects, tasks=()):
    """The `updated_at` minutes shared by so many records that they are bulk edits."""
    out = set()
    for rows, floor in ((projects, BULK_PROJECTS), (tasks, BULK_TASKS)):
        counts = Counter(m for m in (minute(r.get("updated_at")) for r in rows) if m)
        out |= {m for m, n in counts.items() if n >= floor}
    return out


def last_activity(project, tasks, bulk=frozenset()):
    """The latest real timestamp over the project and its tasks, and where it was read."""
    latest, basis = None, ""
    for item, kind in [(project, "project"), *((t, "task") for t in tasks)]:
        for key in ACTIVITY_KEYS:
            if key == "updated_at" and minute(item.get(key)) in bulk:
                continue
            when = parse_time(item.get(key))
            if when is not None and (latest is None or when > latest):
                latest, basis = when, f"{kind}.{key}"
    return latest, basis


# --------------------------------------------------------------------------- titles

# Imperative verbs a next action starts with. Lower case; letters only, so "re-run" is "rerun".
VERBS = frozenset("""
accept add adjust agree align allocate amend analyse analyze answer apply approve archive
arrange ask assemble assess assign attach attend audit authorise authorize back backup book
brainstorm brief bring build buy calculate call cancel capture catch chase check choose
circle clarify clean clear close coach collect compare compile complete configure confirm
connect consolidate contact convert coordinate copy correct create cut debug decide define
delegate delete deliver deploy design determine develop discuss distribute document download
draft drop edit email enable engage enter escalate establish estimate evaluate execute
explain explore export extend fax file fill finalise finalize find finish fix flag follow
forward gather generate get give go hand handle help hire identify implement import improve
include inform input install integrate interview introduce investigate invite invoice issue
join keep kick label launch learn leave list load locate log look mail make map mark meet
merge message migrate move negotiate notify obtain onboard open order organise organize
outline pay pick pin ping plan populate post prepare present price print prioritise
prioritize process produce proofread propose provide publish pull purchase push put
quote raise reach read rebook recalculate receive reconcile record recover reduce refresh
register reject release remind remove renew reorganise reorganize repair replace reply
report request research reschedule resolve respond restart restore resubmit return
reverse review revise rerun run save scan schedule scope screen search secure select send
set setup share ship sign simplify sort source speak specify split start stop submit
summarise summarize supply support switch sync take talk test text thank tidy track train
transfer triage try turn unblock update upgrade upload validate verify visit wait walk
watch write
accelerate advance advise assist backfill begin bill chat compute consider crossreference direct
dissolve do enrich enroll ensure figure filter grant guide host incorporate instruct monitor
observe pilot prep prototype ratify reapprove rearchitect rebuild reclone relaunch reprogram
resend reset retain retrofit revisit roll rotate route rsvp sit stand strip structure suppress
tell think tighten touch trace work change
""".split())

_TAG = re.compile(r"^\s*(?:\[[^\]]*\]\s*|\([^)]*\)\s*|(?:re|fw|fwd|todo|action|task)\s*:\s*)+", re.I)
_LEAD = re.compile(r"^[^A-Za-z]+")
_PUNCT = re.compile(r"[^a-z0-9 ]+")
STOP_WORDS = frozenset("a an and the to for with of on in at by from re fw fwd about please".split())
LEAD_WORDS = ("please", "pls", "i", "we", "to")
MONTHS = frozenset("january february march april may june july august september october november december "
                   "jan feb mar apr jun jul aug sep sept oct nov dec q1 q2 q3 q4".split())


def lead_words():
    """Words before the verb that say nothing about the action ("please call", "we to book"),
    plus the owner's own from the `lead_words` setting (a first name, as in "Dana to call")."""
    return LEAD_WORDS + tuple(w.lower() for w in setting_list("lead_words"))


def _lead_word(text, skip):
    words = _LEAD.sub("", text).split()
    while words and words[0].lower().strip(",.:;") in skip:
        words = words[1:]
    return re.sub(r"[^a-z]", "", words[0].lower().split("/")[0]) if words else ""


def first_word(title, skip=None):
    """The word a next action is judged by: tags, mail prefixes and a polite lead removed."""
    return _lead_word(_TAG.sub("", str(title or "")), skip or lead_words())


def is_next_action(title, skip=None):
    """A verb first, or a verb straight after a short label such as "Acme: send the pack"."""
    skip = skip or lead_words()
    if first_word(title, skip) in VERBS:
        return True
    head, sep, rest = _TAG.sub("", str(title or "")).partition(":")
    return bool(sep) and len(head.split()) <= 5 and _lead_word(rest, skip) in VERBS


def normalise_title(title):
    text = _PUNCT.sub(" ", _TAG.sub("", str(title or "").lower()))
    return " ".join(w for w in text.split() if w not in STOP_WORDS)


def similarity(a, b):
    """How alike two normalised titles are, 0 to 1. Titles naming different numbers or
    periods ("OI-022" and "OI-023", "August" and "September") are different items."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ma = {w for w in a.split() if any(c.isdigit() for c in w) or w in MONTHS}
    mb = {w for w in b.split() if any(c.isdigit() for c in w) or w in MONTHS}
    if ma and mb and ma != mb:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


# --------------------------------------------------------------------------- the trust score

WEIGHTS = {"filing": 0.20, "next_action": 0.10, "overdue": 0.15, "stale": 0.10, "no_due_date": 0.05,
           "waiting": 0.10, "duplicates": 0.10, "projects": 0.15, "goals": 0.05}
COMPONENTS = tuple(WEIGHTS)


def compare(result, before):
    """The change per component, per domain and per item since an earlier json output."""
    prev = (before or {}).get("overall") or {}
    prev_comps, prev_find = prev.get("components") or {}, (before or {}).get("findings") or {}
    after_score = result["overall"]["score"]
    out = {"as_of": before.get("as_of"), "score_before": prev.get("score"), "score_after": after_score,
           "score_delta": None, "components": {}, "domains": {}}
    if isinstance(prev.get("score"), (int, float)) and isinstance(after_score, (int, float)):
        out["score_delta"] = round(after_score - prev["score"], 1)
    for k in COMPONENTS:
        now, old = result["overall"]["components"][k], prev_comps.get(k) or {}
        then_refs = {f.get("ref") for f in prev_find.get(k) or []}
        now_refs = {f["ref"] for f in result["findings"][k]}
        b, a = old.get("clean_share"), now.get("clean_share")
        direction = ("n/a" if b is None or a is None else "better" if a > b + 1e-9
                     else "worse" if a < b - 1e-9 else "same")
        out["components"][k] = {"flagged_before": old.get("flagged"), "flagged_after": now["flagged"],
                                "clean_share_before": b, "clean_share_after": a, "direction": direction,
                                "new_items": len(now_refs - then_refs), "resolved_items": len(then_refs - now_refs)}
    before_domains = {d.get("id"): d for d in (before or {}).get("domains") or []}
    for d in result["domains"]:
        old = before_domains.get(d["id"]) or {}
        delta = (round(d["score"] - old["score"], 1) if isinstance(old.get("score"), (int, float))
                 and isinstance(d["score"], (int, float)) else None)
        out["domains"][d["name"]] = {"before": old.get("score"), "after": d["score"], "delta": delta}
    return out


def emit(payload, code=0):
    """Print one JSON object (secrets redacted) and exit."""
    print(safe(json.dumps(payload, indent=1, ensure_ascii=False, default=str)))
    sys.exit(code)
