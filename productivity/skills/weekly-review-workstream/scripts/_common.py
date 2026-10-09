"""What the weekly-review scripts share: the week, the home, the review contract, the owner's
answers and the pack's text.

THE HOME: <home>/<yyyy>/<yyyy>-W<ww>/ (the ISO year), where <home> is --home or
<state_dir>/weekly-review. It holds inputs/ (the facts the gather read), review.json and
PACK.md, publish.json (where the pack went), ANSWERS.md (the owner's answers in a file),
WEEKLY-REVIEW-ITEMS-<week>.csv (one row per item and its outcome) and applied.json with an
approve-<stamp>/ folder per approval. Only the finish step writes there.

THE REVIEW (review.json, written by the session):
  {"schema": "weekly-review/review@1", "week": "2030-W10", "dry_run": false,
   "summary": ["one line"], "notes": {"<section>": "..."}, "reflection": "a question",
   "items": [{"section": "overdue", "task": "portal://task/<uuid>", "task_title": "Call the bank",
              "title": "...", "proposal": "Move the due date to Friday", "why": "...",
              "evidence": "portal://email/<uuid>", "default": "ok",
              "options": {"ok": [{"op": "edit", "task": "...", "set": {"due_date": "2030-03-08"}}]}},
             {"section": "decisions", "title": "...", "proposal": "Choose a or b", "default": "a",
              "choices": {"a": "...", "b": "..."}, "options": {"a": [...], "b": []}}]}
Each option is a list of task-stack ops (task-stack-workstream has the shape); ids and missing
reasons are filled here. `no` is always offered and never writes. An item with a task also
gets `park` (title prefixed "[Someday] ", status TODO, due date cleared, plus a comment)
unless it gives its own or says "no_park": true.

THE ANSWERS: "1) ok 2) park 3) no", ranges ("4-6) ok"), "rest ok", a letter for a choice.
Synonyms: yes/approve for ok, someday/later for park, complete for done, drop for cancel,
skip/keep/leave for no. An answer that says more than its verb is `modified`, never applied.
"""

import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

SKILL_DIR = Path(__file__).resolve().parents[1]
SKILLS_HOME = Path("~/.claude/skills").expanduser()
TASK_STACK_CHECK = SKILLS_HOME / "task-stack-workstream" / "scripts" / "task_stack_check.py"
TASK_STACK_APPLY = SKILLS_HOME / "task-stack-workstream" / "scripts" / "task_stack_apply.py"
STACK_CHECK_TIMEOUT = 600   # seconds; the score pages through every open task


# --------------------------------------------------------------------------- settings and files

def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


class Bad(Exception):
    """A bad argument or an unreadable input: one line on stderr, exit 2."""


def home_path(home=""):
    """The home: --home, else <state_dir>/<HOME_NAME> from the shared state_dir setting."""
    if (home or "").strip():
        return Path(home.strip()).expanduser()
    base = settings().get("state_dir")
    if not base:
        raise Bad(f"setting state_dir is needed (the folder that holds {HOME_NAME}/), or pass --home")
    return Path(base).expanduser() / HOME_NAME


def guard_run_path(path):
    """A Run folder never lives inside this skill's own folder."""
    target = Path(path).expanduser().resolve()
    if target == SKILL_DIR or SKILL_DIR in target.parents:
        raise Bad(f"{target} is inside the skill folder; Run files live outside it")
    return target


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise Bad(f"{path} could not be read ({type(exc).__name__})") from None
    except ValueError as exc:
        raise Bad(f"{path} is not JSON ({exc})") from None


def maybe_json(path):
    return read_json(path) if Path(path).is_file() else None


def write_text(path, text):
    """Atomic: a synced temporary file beside it, renamed over it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def write_json(path, value):
    write_text(path, json.dumps(value, indent=1, ensure_ascii=False, default=str) + "\n")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ledger_rows(path):
    """The rows of an items ledger CSV in file order, values stripped; the first row of an id
    wins and a row with no id is skipped. A missing file is an empty list."""
    if not Path(path).is_file():
        return []
    text = Path(path).read_text(encoding="utf-8").lstrip("﻿")
    out, seen = [], set()
    for raw in csv.DictReader(text.splitlines()):
        row = {k: (v or "").strip() for k, v in raw.items() if k}
        if row.get("id") and row["id"] not in seen:
            seen.add(row["id"])
            out.append(row)
    return out


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
    INSIGHTS_PORTAL_ASSISTANT_TOKEN when set, else the config's header with ${VAR} expanded.
    HTTPS only, except plain HTTP to localhost."""
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
    """A small JSON-RPC client for the Portal's MCP tools: `call(tool, args)` returns the answer."""

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


RETRY_PAGES = (200, 50, 10, 1)


def page_through(client, entity_type, filters=None, max_calls=400):
    """Every row of one entity type, page by page: (rows, rows it could not read). A page the
    server refuses is retried smaller, down to one row, and that row is stepped over."""
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
        if size >= RETRY_PAGES[0] and not out.get("has_more"):
            break
    if failure and not items:
        raise PortalError(f"could not read any {entity_type} rows from the Portal ({failure})")
    return items, unreadable


def owner_contact(client):
    who = client.call("whoami")
    return str((((who or {}).get("principal") or {}) if isinstance(who, dict) else {}).get("contact_id")
               or "").lower() or None


def stack_check(out, as_of, stale_days=None, baseline=None, config=None, server=None):
    """The task stack's trust score, from task-stack-workstream's task_stack_check.py run as
    its own process, its json written to `out`. A Portal it cannot read is an error here."""
    cmd = [sys.executable, str(TASK_STACK_CHECK), "--format", "json", "--out", str(out), "--as-of", as_of]
    if stale_days:
        cmd += ["--stale-days", str(stale_days)]
    if baseline:
        cmd += ["--baseline", str(baseline)]
    if config:
        cmd += ["--config", config]
    if server:
        cmd += ["--server", server]
    if Path(out).exists():
        Path(out).unlink()
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=STACK_CHECK_TIMEOUT,
                              stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        raise PortalError(f"task_stack_check.py gave no score within {STACK_CHECK_TIMEOUT} seconds") from None
    if done.returncode != 0 or not Path(out).is_file():
        first = (done.stdout or done.stderr or "no output").strip().splitlines()[:1]
        raise PortalError(f"task_stack_check.py gave no score: {first[0] if first else 'no output'}")
    return read_json(out)


# --------------------------------------------------------------------------- dates and states

def parse_time(value):
    """An ISO timestamp or date as an aware UTC datetime; None when it will not parse."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
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


def day(value):
    when = parse_time(value)
    return when.date() if when else None


CLOSED_TASK = {"done", "completed", "complete", "cancelled", "canceled", "archived", "closed", "dropped"}
CLOSED_PROJECT = {"completed", "complete", "done", "cancelled", "canceled", "archived", "closed", "abandoned"}
CLOSED_GOAL = {"achieved", "completed", "complete", "done", "cancelled", "canceled", "abandoned", "archived", "closed"}


def status_of(item):
    return str(item.get("status") or "").strip().upper()


def is_open_task(task):
    return not task.get("is_archived") and status_of(task).lower() not in CLOSED_TASK


def is_active_project(project):
    """Not archived, not closed, not a domain's catch-all bucket."""
    return (not project.get("is_archived") and not project.get("is_general")
            and status_of(project).lower() not in CLOSED_PROJECT)


def is_active_goal(goal):
    return not goal.get("is_archived") and status_of(goal).lower() not in CLOSED_GOAL


def task_domain(task, projects):
    """A task's domain is its project's domain, else its own."""
    project = projects.get(str(task.get("project_id") or ""))
    if project and project.get("domain_id"):
        return str(project["domain_id"])
    return str(task["domain_id"]) if task.get("domain_id") else None


# --------------------------------------------------------------------------- answers

_ITEM = re.compile(r"(?:(?<=[\s,;])|^)(\d{1,3})(?:\s*-\s*(\d{1,3}))?\s*[).:]\s*(?=[A-Za-z])", re.M)
_LINE = re.compile(r"^[ \t]*(\d{1,3})(?:[ \t]*-[ \t]*(\d{1,3}))?[ \t]+(?=[A-Za-z])", re.M)
_ALL = re.compile(r"(?:(?<=[\s,;])|^)(all|rest|others)\b\s*[).:]?\s*(?=[A-Za-z])", re.I | re.M)
_WORD = re.compile(r"^\s*([A-Za-z]+)\b(.*)$", re.S)
_TRAILING = " \t\r\n,.;!-"
AGENT_LINE = re.compile(r"\(posted by .+?, an agent\)\s*\Z", re.S)
LETTERS = tuple("abcdef")


def parse_answers(text):
    """Item number to its raw answer (`1) ok 2) park`, `4-6) ok`, one per line or on one line),
    and the raw answer for every other item (`rest ok`), or None."""
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
        if a <= b <= a + 100:
            for n in range(a, b + 1):
                answers[n] = body
    return answers, rest


def read_answer(raw):
    """The verb (or letter) an answer starts with, and anything said beyond it."""
    m = _WORD.match(raw or "")
    if not m:
        return None, (raw or "").strip()
    word, extra = m.group(1).lower(), m.group(2).strip(_TRAILING)
    if word in SYNONYMS:
        return SYNONYMS[word], extra
    if len(word) == 1 and word in LETTERS:
        return word, extra
    return None, (raw or "").strip()


def answer_states(items, sources, extra_row=lambda it: {}):
    """Each item's answer and state, and the ops the approval may apply. States: approved (ops
    to apply), recorded (a decision with no ops), declined (no), modified (said more than its
    verb), unavailable (a verb the item does not offer), unclear (no verb), unanswered. Sources
    are read oldest first, so a later answer to the same item wins."""
    explicit, rest = {}, None
    for src in sources:
        found, all_rest = parse_answers(str(src.get("text") or ""))
        for n, raw in found.items():
            explicit[n] = {"raw": raw, "source": src.get("source")}
        if all_rest is not None:
            rest = {"raw": all_rest, "source": src.get("source"), "rest": True}
    rows, ops, chosen_items = [], [], []
    for it in items:
        ans = explicit.get(it["n"]) or (dict(rest) if rest else None)
        row = {"n": it["n"], "section": it["section"], "title": it["title"], **extra_row(it),
               "answer": ans["raw"] if ans else None, "source": ans["source"] if ans else None,
               "by_rest": bool(ans and ans.get("rest")), "verb": None, "state": "unanswered", "ops": []}
        if ans:
            verb, extra = read_answer(ans["raw"])
            if verb == "ok" and "ok" not in it["options"] and it.get("default") in it["options"]:
                verb = it["default"]
            row["verb"] = verb
            if verb is None:
                row["state"] = "unclear"
            elif extra:
                row["state"], row["extra"] = "modified", extra
            elif verb == "no":
                row["state"] = "declined"
            elif verb not in it["options"]:
                row["state"] = "unavailable"
            else:
                chosen = it["options"][verb]
                row["state"] = "approved" if chosen else "recorded"
                row["ops"] = [op["id"] for op in chosen]
                ops.extend(chosen)
                chosen_items.append((it, verb))
        rows.append(row)
    counts = {}
    for r in rows:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    return {"items": rows, "ops": ops, "counts": counts,
            "stray_numbers": sorted(n for n in explicit if n not in {it["n"] for it in items}),
            "sources": [{"source": s.get("source"), "chars": len(str(s.get("text") or ""))} for s in sources]}, \
        chosen_items


def answer_line(state_counts):
    order = ("approved", "recorded", "declined", "modified", "unavailable", "unclear", "unanswered")
    return ", ".join(f"{state_counts[k]} {k}" for k in order if state_counts.get(k)) or "no items"


def task_uuid(ref):
    m = re.search(r"([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})", str(ref or ""))
    return m.group(1).lower() if m else None


def answer_sources(folder, form="", client=None, task_ref=None):
    """Every place the owner answered, oldest first: their comments on the task (an agent's
    comment, or one carrying a write marker, is not theirs), ANSWERS.md, the launch form."""
    out = []
    tid = task_uuid(task_ref)
    if client is not None and tid:
        env = client.call("get", {"entity_type": "task", "id_or_query": tid, "detail": "full"})
        if not isinstance(env, dict) or env.get("error"):
            raise Bad(f"the task {tid} holding the answers could not be read")
        for x in sorted((x for x in env.get("comments") or [] if isinstance(x, dict)),
                        key=lambda x: str(x.get("created_at") or "")):
            body = str(x.get("body") or x.get("content") or "")
            if body.strip() and not AGENT_LINE.search(body) and not OWN_MARKER.search(body):
                out.append({"source": f"portal://task/{tid} comment {x.get('id') or x.get('created_at')}",
                            "text": body, "at": x.get("created_at")})
    path = Path(folder) / "ANSWERS.md"
    if path.is_file():
        out.append({"source": str(path), "text": path.read_text(encoding="utf-8", errors="replace")})
    if (form or "").strip():
        out.append({"source": "the launch form", "text": form})
    return out


def cell(value):
    """A table cell: one line, with the pipe escaped so a name cannot split the row."""
    return " ".join(str(value if value is not None else "-").split()).replace("|", "\\|")


def check_options(where, item, options, label, prefix, n, proposal, problems, verbs_text):
    """Each option's ops with their ids and reasons filled, and every problem with them."""
    choices = item.get("choices") or {}
    if not isinstance(choices, dict):
        problems.append(f"{where}: choices must be an object of letter to label")
        choices = {}
    clean = {}
    for verb, ops in options.items():
        if verb == "no":
            problems.append(f"{where}: 'no' is always offered and never writes; do not give it ops")
            continue
        if verb not in VERBS and verb not in LETTERS:
            problems.append(f"{where}: option {verb!r} is not one of {verbs_text} or a letter a to f")
            continue
        if verb in LETTERS and not str(choices.get(verb) or "").strip():
            problems.append(f"{where}: option {verb!r} needs a label in choices")
        if not isinstance(ops, list):
            problems.append(f"{where}: option {verb!r} must be a list of ops")
            continue
        filled = []
        for k, op in enumerate(ops, start=1):
            if not isinstance(op, dict):
                problems.append(f"{where}: option {verb!r} op {k} is not an object")
                continue
            op = dict(op, id=f"{prefix}{n}-{verb}-{k}")
            op.setdefault("reason", f"{label}, item {n}: {proposal}"[:300])
            problems += [f"{where}: option {verb!r} op {k}: {p}" for p in shape_problems(op)]
            filled.append(op)
        clean[verb] = filled
    for letter in choices:
        if letter not in clean:
            problems.append(f"{where}: choice {letter!r} has no option (give it ops, or [] to record it)")
    default = str(item.get("default") or "").strip().lower() or ("ok" if "ok" in clean else None)
    if default and default != "no" and default not in clean:
        problems.append(f"{where}: default {default!r} is not one of its options")
    if not clean:
        problems.append(f"{where}: no options; give at least one, or leave the item out")
    return clean, {k: " ".join(str(v).split()) for k, v in choices.items()}, default


def number_items(raw, problems):
    """(n, item) in section order, then the session's order; bad items are problems."""
    order = {s: i for i, s in enumerate(ITEM_SECTIONS)}
    indexed = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            problems.append(f"item {i + 1} is not an object")
        elif item.get("section") not in order:
            problems.append(f"item {i + 1}: section must be one of {', '.join(ITEM_SECTIONS)}")
        else:
            indexed.append((order[item["section"]], i, item))
    indexed.sort(key=lambda t: (t[0], t[1]))
    return [(n, item) for n, (_, _, item) in enumerate(indexed, start=1)]


def verbs_of(item):
    if item["choices"]:
        return "  ".join(f"{k}) {v}" for k, v in sorted(item["choices"].items())) + "  (or no)"
    verbs = [v for v in VERBS if v in item["options"]] + ["no"]
    if item.get("default") in verbs and verbs[0] != item["default"]:
        verbs.remove(item["default"])
        verbs.insert(0, item["default"])
    return " | ".join(verbs)


def approval_list(items):
    out = []
    for it in items:
        line = f"{it['n']}. [{SECTION_TITLES[it['section']]}] {it['title']}: {it['proposal']}"
        if not line.endswith((".", "?", "!")):
            line += "."
        if it.get("why"):
            line += f" Why: {it['why']}" + ("" if it["why"].endswith((".", "?", "!")) else ".")
        out.append(line + f" ({verbs_of(it)})")
    return out


def review_head(review, period_key, label, problems):
    """The checks every review shares: schema, period, dry_run, summary, notes."""
    if not isinstance(review, dict):
        return False
    if review.get("schema") != REVIEW_SCHEMA:
        problems.append(f"schema must be {REVIEW_SCHEMA!r}")
    if review.get(period_key) != label:
        problems.append(f"{period_key} is {review.get(period_key)!r}, this Run reviews {label}")
    if not isinstance(review.get("dry_run"), bool):
        problems.append("dry_run must be true or false")
    if not isinstance(review.get("summary"), list) or not review.get("summary"):
        problems.append("summary must be a non-empty list of lines")
    notes = review.get("notes")
    if not isinstance(notes, dict):
        problems.append("notes must be an object keyed by section")
    elif set(notes) - set(SECTION_TITLES):
        problems.append(f"notes has unknown sections: {', '.join(sorted(set(notes) - set(SECTION_TITLES)))}")
    return True


# --------------------------------------------------------------------------- the shape of an op
#
# A copy of task_stack_apply.py's shape check (task-stack-workstream), so an item's ops are
# refused here for the same reasons the writer would refuse them. Keep the two in step.

PROJECT_OPS = ("project_edit", "project_close")
GOAL_OPS = ("goal_edit", "goal_close")
OPS = ("complete", "edit", "merge", "cancel", "create", "comment") + PROJECT_OPS + GOAL_OPS
EDIT_STATUSES = ("TODO", "IN_PROGRESS", "WAITING")
EDITABLE = ("title", "status", "project_id", "domain_id", "goal_id", "due_date", "deadline", "start_date",
            "priority", "owner_contact_id", "waiting_on_contact_id", "waiting_reason")
DATE_FIELDS = ("due_date", "deadline", "start_date")
ID_FIELDS = ("project_id", "domain_id", "goal_id", "owner_contact_id", "waiting_on_contact_id", "assignee_contact_id")
PROJECT_EDITABLE = ("status", "goal_id", "assignee_contact_id", "priority", "due_date", "deadline", "start_date")
PROJECT_OPEN_STATUSES = ("NOT_STARTED", "PLANNING", "IN_PROGRESS", "ON_HOLD")
PROJECT_CLOSE_STATUSES = ("CANCELLED", "COMPLETED")
GOAL_EDITABLE = ("status", "priority", "horizon", "title", "due_date", "deadline")
GOAL_OPEN_STATUSES = ("NOT_STARTED", "IN_PROGRESS", "DEFERRED")
GOAL_CLOSE_STATUSES = ("ACHIEVED", "CANCELLED", "MISSED")
HORIZONS = ("VISION", "ANNUAL", "QUARTERLY", "MONTHLY")
COMMENT_MAX, OP_TITLE_MAX = 4000, 200
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

def _id(pattern, ref):
    m = pattern.match(str(ref or "").strip())
    return m.group(1).lower() if m else None


def task_id(ref):
    return _id(TASK_REF, ref)


def project_id(ref):
    return _id(PROJECT_REF, ref)


def goal_id(ref):
    return _id(GOAL_REF, ref)


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
            if "title" in fields and not 0 < len(str(fields["title"] or "").strip()) <= OP_TITLE_MAX:
                out.append(f"title is 1 to {OP_TITLE_MAX} characters")
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
            if "title" in fields and not 0 < len(str(fields["title"] or "").strip()) <= OP_TITLE_MAX:
                out.append(f"title is 1 to {OP_TITLE_MAX} characters")
            if fields.get("priority") not in (None, "") and not PRIORITY.match(str(fields["priority"])):
                out.append("priority is 1 to 4")
    if kind == "create":
        if not 0 < len(str(op.get("title") or "").strip()) <= OP_TITLE_MAX:
            out.append(f"create needs a title of 1 to {OP_TITLE_MAX} characters")
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


# --------------------------------------------------------------------------- the weekly review

HOME_NAME = "weekly-review"
ORCHESTRATOR = "weekly-review-orchestrator"
REVIEW_SCHEMA = "weekly-review/review@1"
PASS_SCHEMA = "weekly-review/pass@1"
ANSWERS_SCHEMA = "weekly-review/answers@1"
PASSES = ("auto", "pack", "approve")
SOMEDAY = "[Someday] "
SECTIONS = (("score", "Trust score"), ("projects", "Projects and next actions"),
            ("waiting", "Waiting for, and follow-ups due"), ("overdue", "Overdue and stale"),
            ("someday", "Someday/maybe candidates"), ("calendar", "Next week's calendar"),
            ("said", "Said but not seen"), ("decisions", "Decisions only you can make"),
            ("cadence", "Cadence and reflection"))
SECTION_TITLES = dict(SECTIONS)
ITEM_SECTIONS = ("projects", "waiting", "overdue", "someday", "calendar", "said", "decisions")
VERBS = ("ok", "park", "done", "cancel", "waiting", "no")
SYNONYMS = {
    "ok": "ok", "okay": "ok", "yes": "ok", "y": "ok", "approve": "ok", "approved": "ok", "go": "ok",
    "agree": "ok", "agreed": "ok", "do": "ok",
    "park": "park", "parked": "park", "someday": "park", "later": "park", "defer": "park",
    "done": "done", "complete": "done", "completed": "done", "finished": "done", "close": "done",
    "cancel": "cancel", "cancelled": "cancel", "drop": "cancel", "kill": "cancel",
    "waiting": "waiting", "wait": "waiting",
    "no": "no", "n": "no", "skip": "no", "keep": "no", "leave": "no", "pass": "no", "nope": "no",
}
OWN_MARKER = re.compile(r"\b(?:tsk|wkr)[0-9a-f]{12}\b")
MAX_ITEMS, TITLE_MAX = 60, 160
WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")


def resolve_week(text, today=None):
    """A week label (2030-W10), a date in the week, or blank: the week of the latest Friday."""
    raw = (text or "").strip()
    if not raw:
        today = today or date.today()
        d = today - timedelta(days=(today.weekday() - 4) % 7)
    elif WEEK_RE.match(raw.upper()):
        y, w = WEEK_RE.match(raw.upper()).groups()
        try:
            d = date.fromisocalendar(int(y), int(w), 1)
        except ValueError:
            raise Bad(f"no such week {raw!r}") from None
    else:
        try:
            d = date.fromisoformat(raw)
        except ValueError:
            raise Bad(f"week is yyyy-Www or a date yyyy-mm-dd, got {raw!r}") from None
    y, w, _ = d.isocalendar()
    monday = date.fromisocalendar(y, w, 1)
    py, pw, _ = (monday - timedelta(days=7)).isocalendar()
    return {"week": f"{y}-W{w:02d}", "year": str(y), "monday": monday.isoformat(),
            "friday": (monday + timedelta(days=4)).isoformat(), "sunday": (monday + timedelta(days=6)).isoformat(),
            "next_monday": (monday + timedelta(days=7)).isoformat(),
            "next_sunday": (monday + timedelta(days=13)).isoformat(), "previous": f"{py}-W{pw:02d}"}


def week_dir(home, label):
    return Path(home) / label[:4] / label


def items_ledger_name(label):
    return f"WEEKLY-REVIEW-ITEMS-{label}.csv"


def marker(label):
    """The week's marker, on the review note and task so each is found again."""
    return "wkr" + hashlib.sha256(f"weekly-review|{label}".encode()).hexdigest()[:12]


def park_ops(task, title, label):
    new_title = title if title.startswith(SOMEDAY.strip()) else (SOMEDAY + title)[:200]
    return [{"op": "edit", "task": task, "set": {"title": new_title, "status": "TODO", "due_date": None},
             "reason": f"Parked as someday/maybe in the weekly review {label}"},
            {"op": "comment", "task": task,
             "body": f"Parked as someday/maybe in the weekly review {label}; the owner approved it.",
             "reason": f"Parked in the weekly review {label}"}]


def validate_review(review, label):
    """The numbered items, ready to render and apply, and every problem found. Numbers follow
    the section order, then the session's order; ops get their ids and reasons here, so the
    numbers in the pack are the ones the approval applies."""
    problems = []
    if not review_head(review, "week", label, problems):
        return [], ["review.json is not a JSON object"]
    raw = review.get("items")
    if not isinstance(raw, list):
        return [], problems + ["items must be a list"]
    if len(raw) > MAX_ITEMS:
        problems.append(f"{len(raw)} items; at most {MAX_ITEMS} fit a 30-minute review")
    out, seen = [], {}
    for n, item in number_items(raw, problems):
        where = f"item {n} ({item.get('section')})"
        title = " ".join(str(item.get("title") or "").split())
        proposal = " ".join(str(item.get("proposal") or "").split())
        if not title or len(title) > TITLE_MAX:
            problems.append(f"{where}: title is 1 to {TITLE_MAX} characters")
        if not proposal:
            problems.append(f"{where}: proposal is required, one line the owner reads")
        options = item.get("options") if item.get("options") is not None else {}
        if not isinstance(options, dict):
            problems.append(f"{where}: options must be an object of verb or letter to ops")
            options = {}
        task = str(item.get("task") or "").strip() or None
        if task:
            if task in seen:
                problems.append(f"{where}: the task is already item {seen[task]}")
            seen[task] = n
        options = {str(k).strip().lower(): v for k, v in options.items()}
        if task and "park" not in options and not item.get("no_park"):
            options["park"] = park_ops(task, str(item.get("task_title") or title), label)
        clean, choices, default = check_options(where, item, options, f"Weekly review {label}", "w", n, proposal,
                                                problems, ", ".join(VERBS[:-1]))
        out.append({"n": n, "section": item["section"], "title": title, "proposal": proposal,
                    "why": " ".join(str(item.get("why") or "").split()) or None,
                    "evidence": item.get("evidence") or None, "task": task,
                    "task_title": item.get("task_title") or None, "default": default,
                    "choices": choices, "options": clean})
    return out, problems


def resolve(items, sources):
    """Each item's answer and state, and the ops the approval may apply."""
    result, _ = answer_states(items, sources, lambda it: {"task": it.get("task")})
    return result


def fmt(value):
    return "-" if value is None else (f"{value:.1f}" if isinstance(value, float) else str(value))


def render_pack(review, items, inputs, week):
    """PACK.md: the facts from the inputs, the session's notes, and one approval list."""
    notes = review.get("notes") or {}
    label = week["week"]
    out = [f"# Weekly review {label} ({week['monday']} to {week['sunday']})", "",
           "Answer the numbered list at the end in one pass, for example `1) ok 2) park 3) no`, in a "
           "comment on the review task or in ANSWERS.md. `ok` does what the item proposes, `park` moves the "
           "task to someday/maybe, `no` leaves it as it is, and a letter picks a choice. `rest ok` answers "
           "every item you did not. Nothing you do not approve is changed; an answer that says more than its "
           "verb is read back to you, not applied.", "", "## Summary", ""]
    out += [f"- {line}" for line in review.get("summary") or []]
    carry = inputs.get("carried") or {}
    if carry.get("items"):
        out.append(f"- {len(carry['items'])} item(s) from {carry['week']} were left unsettled; they are back below "
                   f"where they still matter.")
    out.append("")

    def section(key, body):
        out.extend([f"## {SECTION_TITLES[key]}", ""] + body)
        if notes.get(key):
            out.extend(["", str(notes[key]).strip()])
        mine = [it["n"] for it in items if it["section"] == key]
        if mine:
            out.extend(["", "Items: " + ", ".join(str(n) for n in mine) + "."])
        out.append("")

    stack = inputs.get("stack") or {}
    overall, base = stack.get("overall") or {}, stack.get("baseline") or {}
    body = []
    if overall:
        delta = base.get("score_delta")
        line = f"Trust score {fmt(overall.get('score'))} / 100"
        if base:
            line += (f", {fmt(base.get('score_before'))} at {base.get('as_of')}"
                     + (f" ({delta:+.1f})" if isinstance(delta, (int, float)) else ""))
        else:
            line += "; no earlier score to compare with"
        body += [line + f"; {overall.get('items_flagged')} items need attention.", "",
                 "| Component | Flagged | Pool | Since last |", "|---|---:|---:|---|"]
        for name, comp in (overall.get("components") or {}).items():
            then = (base.get("components") or {}).get(name) or {}
            since = f"{then.get('flagged_before')} -> {then.get('flagged_after')}, {then.get('direction')}" if then else "-"
            body.append(f"| {name} | {comp.get('flagged')} | {comp.get('pool')} | {since} |")
    else:
        body.append("No trust score was read this week.")
    section("score", body)

    projects = inputs.get("projects") or {}
    body = [f"{projects.get('active', 0)} active projects; {projects.get('with_next_action', 0)} have a next "
            f"action, {projects.get('gaps', 0)} do not."]
    rows = [p for p in projects.get("projects") or [] if p.get("gap")]
    if rows:
        body += ["", "| Project | Domain | Gap |", "|---|---|---|"]
        body += [f"| {cell(p['name'])} | {cell(p.get('domain'))} | {cell(p['gap'])} |" for p in rows[:40]]
        if len(rows) > 40:
            body.append(f"\nAnd {len(rows) - 40} more in inputs/projects.json.")
    section("projects", body)

    waiting = inputs.get("waiting") or {}
    counts = waiting.get("counts") or {}
    body = [f"{counts.get('waiting', 0)} WAITING: {counts.get('follow_up_overdue', 0)} follow-ups overdue, "
            f"{counts.get('follow_up_due', 0)} due by {week['next_sunday']}, {counts.get('no_follow_up', 0)} "
            f"with no follow-up date."]
    due = [w for w in waiting.get("tasks") or [] if w.get("bucket") in ("follow_up_overdue", "follow_up_due")]
    if due:
        body += [""] + [f"- {w['title']} (follow up {w.get('follow_up') or '-'}, waiting on "
                        f"{w.get('waiting_on') or 'nobody named'})" for w in due[:25]]
    section("waiting", body)

    tc = (inputs.get("tasks") or {}).get("counts") or {}
    section("overdue", [f"{tc.get('overdue', 0)} of your open tasks are overdue and {tc.get('stale', 0)} are "
                        f"stale; the items below are the ones worth your answer this week. The nightly passes "
                        f"handle the rest."])
    section("someday", [f"{tc.get('someday_candidates', 0)} tasks look like someday/maybe: no goal, no recent "
                        f"activity, long overdue or never dated."])

    cal = inputs.get("calendar") or {}
    if cal.get("error"):
        body = [f"The calendar could not be read: {cal['error']}."]
    else:
        totals = cal.get("totals") or {}
        body = [f"{cal.get('meetings', 0)} meetings, {fmt(totals.get('hours_union'))} hours of wall clock "
                f"({fmt(totals.get('double_booked_hours'))} double booked)."]
        if cal.get("by_day"):
            body.append("By day: " + ", ".join(f"{d} {h}" for d, h in cal["by_day"].items()) + ".")
        for x in (cal.get("conflicts") or [])[:15]:
            body.append(f"- Conflict {x['day']}: {x['a']} and {x['b']} overlap {x['minutes']} minutes")
    section("calendar", body)

    said = inputs.get("said") or {}
    if said.get("present"):
        body = [f"{len(said.get('items') or [])} commitments heard and not seen kept "
                f"(time study {', '.join(said.get('windows') or [])})."]
        body += [f"- {s.get('date')}: {s.get('commitment') or s.get('quote') or s.get('text')}"
                 + (f" (to {s['to']})" if s.get("to") else "") for s in (said.get("items") or [])[:20]]
    else:
        body = ["No said-but-not-seen list covers this week."]
    section("said", body)
    section("decisions", [] if any(it["section"] == "decisions" for it in items) else ["None this week."])

    cad = inputs.get("cadence") or {}
    body = []
    if cad.get("monthly_pulse_due"):
        body.append("This is the month's last review: the monthly goal alignment (its domain pulse) runs on the "
                    "first Monday of next month; answer its note there.")
    if cad.get("quarter_end"):
        body.append("The quarter ends this month: the quarterly review runs in the goal alignment, in the months "
                    "its rules name.")
    if review.get("reflection"):
        body.append(f"Reflection: {review['reflection']}")
    section("cadence", body or ["Nothing due beyond this review."])
    out += ["## Approval list", ""] + approval_list(items) + ["", f"<!-- weekly-review {label} {marker(label)} -->", ""]
    return "\n".join(out)


def load_inputs(folder):
    """The gathered inputs by name, each None when absent."""
    names = ("stack", "projects", "waiting", "tasks", "calendar", "said", "cadence", "carried")
    return {n: maybe_json(Path(folder) / f"{n}.json") for n in names}


# --------------------------------------------------------------------------- the finish steps
#
# What the changes and publish scripts share: the Run's records, the items ledger, the private
# note found again by its marker, and every task write handed to task_stack_apply.py.

ITEM_STATES = ("proposed", "applied", "partial", "refused", "deferred", "recorded", "declined", "modified",
               "unavailable", "unclear", "unanswered", "would_apply")
CLEAN_STATES = ("approved", "recorded", "declined")


class Refuse(Exception):
    """A refusal that leaves everything as it was: exit 1."""


def resolve_pass(wanted, folder):
    """The pass this Run is, and the live publish record: approve once the period's pack is published
    (publish.json, not a dry run), pack until then."""
    wanted = (wanted or "").strip().lower() or "auto"
    if wanted not in PASSES:
        raise Bad(f"--pass is one of {', '.join(PASSES)}, got {wanted!r}")
    published = maybe_json(folder / "publish.json")
    live = published if isinstance(published, dict) and not published.get("dry_run") else None
    if wanted == "auto":
        wanted = "approve" if live else "pack"
    if wanted == "approve" and not live:
        raise Bad(f"nothing to approve: no published pack in {folder}")
    return wanted, live


def truthy(value):
    return str(value or "").strip().lower() in ("true", "1", "yes", "on")


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def new_dir(folder, prefix):
    """A new folder named for now; two in one second get a suffix, never the same folder."""
    base = Path(folder) / f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    path, n = base, 1
    while path.exists():
        n += 1
        path = base.with_name(f"{base.name}-{n}")
    path.mkdir(parents=True)
    return path


def append_log(folder, heading, line):
    path = Path(folder) / "LOG.md"
    old = path.read_text(encoding="utf-8") if path.is_file() else f"# {heading}: {Path(folder).name}\n\n"
    write_text(path, old + f"- {datetime.now().astimezone().isoformat(timespec='minutes')} {line}\n")


def upsert_items(path, columns, updates):
    """Create or update rows of an items ledger CSV by id; other rows are kept as they are."""
    rows = {r["id"]: r for r in ledger_rows(path)}
    for key, values in updates.items():
        row = rows.setdefault(str(key), {c: "" for c in columns})
        row.update({k: "" if v is None else str(v) for k, v in values.items()}, id=str(key))
    lines = [",".join(columns)]
    for row in rows.values():
        buffer = io.StringIO()
        csv.writer(buffer, lineterminator="").writerow([row.get(c, "") for c in columns])
        lines.append(buffer.getvalue())
    write_text(path, "﻿" + "\n".join(lines) + "\n")


def change_set(ops, questions=(), notes=(), dry_run=False):
    return {"tool": "task-stack-changes", "version": 1, "orchestrator": ORCHESTRATOR, "dry_run": dry_run,
            "ops": list(ops), "questions": list(questions), "notes": list(notes)}


def apply_tasks(run, name, ops, config=None, server=None):
    """Make task writes through task-stack-workstream's task_stack_apply.py, the one writer of
    the task stack: the ops go to RUN/<name>-changes.json and its result to RUN/<name>-apply.json.
    Returns each op's result by id; any op not applied or unchanged stops the step."""
    run = Path(run)
    path = run / f"{name}-changes.json"
    write_json(path, change_set(ops))
    cmd = [sys.executable, str(TASK_STACK_APPLY), str(path), "--log", str(run / f"{name}-undo.jsonl"),
           "--out", str(run / f"{name}-apply.json")]
    cmd += (["--config", config] if config else []) + (["--server", server] if server else [])
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=600, stdin=subprocess.DEVNULL)
        out = json.loads(done.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise Bad(f"task_stack_apply.py could not run ({type(exc).__name__})") from None
    if done.returncode != 0 or not isinstance(out, dict):
        raise Bad(f"task_stack_apply.py exited {done.returncode}: {out.get('reason') if isinstance(out, dict) else ''}")
    results = {str(r.get("id")): r for r in out.get("results") or []}
    for op in ops:
        r = results.get(op["id"], {})
        if r.get("outcome") not in ("applied", "unchanged"):
            raise Bad(f"task_stack_apply.py did not make {op['id']}: {r.get('outcome', 'no result')} "
                      f"{r.get('code') or ''} {r.get('reason') or ''}".rstrip())
    return results


def _record(out, kind):
    return out.get(kind) if isinstance(out, dict) and isinstance(out.get(kind), dict) else out


def find_note(client, mark, known=None):
    """The note carrying the marker: the one publish.json names, else a search."""
    ids = [task_uuid(known)] if task_uuid(known) else []
    found = client.call("search", {"query": mark, "limit": 10})
    ids += [str(h["id"]).lower() for h in ((found or {}).get("notes") if isinstance(found, dict) else None) or []
            if isinstance(h, dict) and h.get("id")]
    for nid in dict.fromkeys(ids):
        record = _record(client.call("get", {"entity_type": "note", "id_or_query": nid, "detail": "full"}), "note")
        if isinstance(record, dict) and mark in str(record.get("content") or "") and str(record.get("id")).lower() == nid:
            return record
    return None


def ensure_note(client, title, tag, content, mark, known=None, task_ref=None):
    """Find the note by its marker or create it once (on the task, else the owner's contact),
    then make it PRIVATE and read it back with its marker."""
    found = find_note(client, mark, known)
    if found:
        nid, outcome = str(found["id"]), "unchanged"
        if found.get("content") != content:
            client.call("update_note", {"id": nid, "fields": {"content": content}})
            outcome = "updated"
    else:
        target = ("task", task_uuid(task_ref)) if task_uuid(task_ref) else ("contact", owner_contact(client))
        out = client.call("create_note", {"title": title, "content": content, "tag_names": [tag], "associations": [
            {"entity_type": target[0], "entity_id": target[1], "is_primary": True}]})
        made = _record(out, "note")
        nid = str(made.get("id") or "") if isinstance(made, dict) else ""
        if not nid:
            raise Bad(f"create_note answered without an id: {safe(str(out)[:200])}")
        outcome = "created"

    def read():
        return _record(client.call("get", {"entity_type": "note", "id_or_query": nid, "detail": "full"}), "note") or {}

    record = read()
    if str(record.get("visibility") or "").upper() != "PRIVATE":
        client.call("update_note", {"id": nid, "fields": {"visibility": "PRIVATE"}})
        record = read()
    if mark not in str(record.get("content") or ""):
        raise Bad("the note did not read back with its marker")
    if str(record.get("visibility") or "").upper() != "PRIVATE":
        raise Bad("the note did not read back PRIVATE")
    return {"ref": f"portal://note/{nid.lower()}", "outcome": outcome, "visibility": "PRIVATE"}


def answered_already(folder, published, client):
    """Why a published note may no longer be replaced, or None."""
    if (Path(folder) / "ANSWERS.md").is_file():
        return f"{Path(folder) / 'ANSWERS.md'} exists"
    if (Path(folder) / "applied.json").is_file():
        return "an approval was already applied"
    if published and published.get("task") and client is not None \
            and answer_sources(Path(folder) / "no-answers-file", "", client, published["task"]):
        return "the owner has commented on the approval task"
    return None


def item_outcomes(answers, results):
    """Each item's final state, from its answer and what task_stack_apply.py did with its ops."""
    by_op = {str(r.get("id")): r for r in results}
    out = {}
    for row in answers.get("items") or []:
        state, outcome = row["state"], ""
        if state == "approved":
            got = [by_op.get(i, {}).get("outcome", "missing") for i in row["ops"]]
            done = {"applied", "unchanged"}
            state = ("applied" if all(g in done for g in got) else "would_apply" if all(g == "would_apply" for g in got)
                     else "deferred" if all(g == "deferred" for g in got) else "partial" if any(g in done for g in got)
                     else "refused")
            outcome = "; ".join(f"{i} {by_op.get(i, {}).get('outcome', 'missing')}"
                                + (f" ({by_op[i].get('code')}: {by_op[i].get('reason')})" if by_op.get(i, {}).get("code")
                                   else "") for i in row["ops"])
        elif state == "modified":
            outcome = f"said more than its verb: {row.get('extra')}"
        out[row["n"]] = {"state": state, "outcome": outcome, "answer": row.get("answer") or "", "ops": " ".join(row["ops"])}
    return out


def outcome_table(outcomes, questions):
    lines = [f"## Answers and outcomes ({datetime.now().astimezone().strftime('%Y-%m-%d %H:%M')})", "",
             "| # | Answer | Outcome |", "|---:|---|---|"]
    for n in sorted(outcomes):
        o = outcomes[n]
        lines.append(f"| {n} | {cell(o['answer'] or '-')} | {cell(o['state'] + ((': ' + o['outcome']) if o['outcome'] else ''))} |")
    return lines + [f"\n- {q['ask']}" for q in questions]


def approve_change_set(folder, label, published, form, client, close_id, what, order=None):
    """The approve pass's change set from the PUBLISHED review and every answer: exactly the ops
    of each approved verb, a question per answer that cannot be applied, and the approval task
    completed once every item has a clean answer. Also returns the resolution."""
    review = read_json(Path(folder) / "review.json")
    items, problems = validate_review(review, label)
    if problems:
        raise Refuse(f"the published review in {folder} does not validate: {problems[0]}")
    result = resolve(items, answer_sources(folder, form, client, published.get("task")))
    ops = sorted(result["ops"], key=lambda op: (order or {}).get(str(op.get("op")), 2))
    said = {"modified": "says more than its verb", "unclear": "starts with no verb I know",
            "unavailable": "names {verb!r}, which this item does not offer"}
    questions = [{"ask": f"Item {r['n']} ({r['title']}): your answer {r['answer']!r} "
                         f"{said[r['state']].format(verb=r['verb'])}, so nothing was changed; answer it again with one verb.",
                  "task": r.get("task"), "why": f"the {what} applies only a plain verb"}
                 for r in result["items"] if r["state"] in said]
    questions = [{k: v for k, v in q.items() if v is not None} for q in questions]
    if items and all(r["state"] in CLEAN_STATES for r in result["items"]) and published.get("task") \
            and published.get("note"):
        ops.append({"id": close_id, "op": "complete", "task": published["task"], "evidence": published["note"],
                    "reason": f"The owner answered every item of the {what}"})
    result.update(schema=ANSWERS_SCHEMA, preview=False, at=now_iso())
    return ops, questions, result
