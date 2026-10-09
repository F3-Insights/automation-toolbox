# /// script
# dependencies = ["pyyaml", "pypdf", "openpyxl"]
# ///
"""Gather one engagement into the Run folder before the delivery session. Read only toward
every system.

Inputs: ENGAGEMENT (a Context name or path; _common.py says what it holds), --run-dir, and
optionally --mode (plan, check or milestone-review; blank: plan on Monday, else check),
--milestone, --dry-run-if, --as-of, --since, --contexts-dir, --no-portal.

Writes RUN/delivery/:
  pack.json          everything below, with each source's id, role and path
  sources.md         every source, grouped by role, one line each
  sources/S###.md    the SOW's text, each Portal item's text, the repo log
  tasks.json         the engagement domain's open tasks and projects
  check-before.json  delivery_check.py's result before the session
  working/           on a dry run, a copy of the working folder's state files, which the
                     session then uses instead of the live folder

The window runs from the last recorded session (else the rules' Lookback days) to the as-of
date; --since overrides. Sources are numbered S001... in this order: the SOW files (as text),
client-folder files changed or dated in the window (path only, never a Never open match), the
Portal domain's meetings, notes and mail for the window (mail only with a client email domain;
read by report-collect, the report-weekly skill's script), and the repo's git log.

The Portal connection comes from the owner settings (portal_mcp_config, portal_server) and
INSIGHTS_PORTAL_ASSISTANT_TOKEN; the Context library from the setting contexts_dir.

First line printed: `FRESH: <n> sources, <t> open tasks for <engagement> (<since> to <as-of>),
pack at <dir>; working folder <path>` or `STALE: <reason>; ...`, then indented detail lines.
--format json prints pack.json. Exit 0 when it ran, 2 on a bad argument or a missing Context
or rules file.

Example:
  python3 delivery_pack.py northwind-delivery --run-dir RUN --dry-run-if true
"""

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

import _common as dc

REPORT_COLLECT = Path("~/.claude/skills/report-weekly/scripts/report_collect.py").expanduser()
CHECK = Path(__file__).with_name("delivery_check.py")
OPEN_STATUSES = ("TODO", "IN_PROGRESS", "WAITING")
PORTAL_KINDS = ("meeting", "note", "mail")
TASK_FIELDS = ("id", "title", "status", "due_date", "deadline", "owner_contact_id", "owner_name",
               "assignees", "project_id", "project_name", "domain_id", "waiting_on_contact_id",
               "waiting_on_name", "updated_at", "created_at", "source_reference")
ROLES = ("sow", "folder", "portal", "repo")
MAX_BYTES = 25 * 1024 * 1024
MAX_FOLDER_FILES = 200
PAGE_SIZES = (200, 50, 10, 1)   # a page the server will not serialise is retried smaller
SECRET_RE = re.compile(r"(?i)(bearer\s+\S+|authorization[\"'\s:=]+(?:bearer\s+)?\S+"
                       r"|[?&](?:key|token|api_key|access_token)=[^\s&\"']+)")


# --------------------------------------------------------------------------- the Portal

class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect, so the bearer never goes anywhere but the configured URL."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Portal:
    """A read-only Portal MCP client: whoami and list_entities only."""

    def __init__(self):
        conf = dc.blank(dc.settings().get("portal_mcp_config"))
        if not conf:
            raise dc.Bad("setting portal_mcp_config is needed (the MCP config file holding the Portal server)")
        server = dc.blank(dc.settings().get("portal_server")) or "insights-portal"
        try:
            cfg = json.loads(Path(conf).expanduser().read_text(encoding="utf-8"))["mcpServers"][server]
        except (OSError, KeyError, TypeError, ValueError):
            raise dc.Bad(f"{conf} has no usable mcpServers entry named {server!r}") from None
        token = os.environ.get("INSIGHTS_PORTAL_ASSISTANT_TOKEN", "").strip()
        auth = f"Bearer {token}" if token else (cfg.get("headers") or {}).get("Authorization") or ""

        def expand(value):
            def one(m):
                if not os.environ.get(m.group(1)):
                    raise dc.Bad(f"the Portal config needs {m.group(1)}, which is not set")
                return os.environ[m.group(1)]
            return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", one, value)

        self.url, self.auth = expand(str(cfg.get("url") or "")), expand(auth)
        parts = urlsplit(self.url)
        local = parts.hostname in ("localhost", "127.0.0.1", "::1")
        if not parts.hostname or not (parts.scheme == "https" or (parts.scheme == "http" and local)):
            raise dc.Bad("the Portal URL must be HTTPS (HTTP only on localhost)")
        if not self.auth.startswith("Bearer ") or not self.auth[7:].strip():
            raise dc.Bad("no Portal bearer token: set INSIGHTS_PORTAL_ASSISTANT_TOKEN or put one in the config")
        self.opener, self.next_id = urllib.request.build_opener(NoRedirect), 0

    def call(self, tool, arguments=None):
        self.next_id += 1
        body = json.dumps({"jsonrpc": "2.0", "id": self.next_id, "method": "tools/call",
                           "params": {"name": tool, "arguments": arguments or {}}}).encode()
        req = urllib.request.Request(self.url, data=body, method="POST", headers={
            "Authorization": self.auth, "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"})
        try:
            with self.opener.open(req, timeout=60) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"portal {tool}: HTTP {exc.code}") from None
        except (urllib.error.URLError, OSError) as exc:
            raise RuntimeError(f"portal {tool}: {type(exc).__name__}") from None
        messages = [json.loads(raw)] if raw.lstrip().startswith("{") else [
            json.loads(line[5:]) for line in raw.splitlines() if line.startswith("data:") and line[5:].strip()]
        if not messages or "error" in messages[-1]:
            raise RuntimeError(f"portal {tool}: no result")
        result = messages[-1].get("result", messages[-1])
        if isinstance(result, dict) and "content" in result:
            text = "\n".join(c.get("text", "") for c in result["content"] if c.get("type") == "text")
            if result.get("isError"):
                raise RuntimeError(f"portal {tool}: refused")
            try:
                return json.loads(text)
            except ValueError:
                return text
        return result


def page_through(client, entity_type, filters, max_calls=400):
    """Every row of one entity type, and how many rows could not be read. A page the server
    will not serialise is retried smaller, down to one row, which is then stepped over."""
    items, offset, unreadable, total, calls, failed = [], 0, 0, None, 0, False
    while calls < max_calls:
        served = None
        for size in PAGE_SIZES:
            if calls >= max_calls:
                break
            args = {"entity_type": entity_type, "limit": size, "filters": dict(filters)}
            if offset:
                args["offset"] = offset
            calls += 1
            try:
                out = client.call("list_entities", args)
            except Exception:  # a page the server will not serialise, or a dead transport
                failed = True
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
        total = out["total"] if isinstance(out.get("total"), int) else total
        items += rows
        offset += len(rows)
        if not rows or (total is not None and offset >= total) or (size == PAGE_SIZES[0] and not out.get("has_more")):
            break
    if failed and not items:
        raise RuntimeError(f"could not read any {entity_type} rows from the Portal")
    return items, unreadable


def read_tasks(client, domain):
    """The domain's projects, its open tasks (in the domain or one of its projects), and the
    owner's contact id."""
    projects, unreadable = page_through(client, "project", {"domain_id": domain})
    projects = [p for p in projects if not p.get("is_archived")]
    seen = {}
    for status in OPEN_STATUSES:
        rows, skipped = page_through(client, "task", {"domain_id": domain, "status": status})
        unreadable += skipped
        for row in rows:
            seen.setdefault(str(row.get("id")), row)
    for project in projects:
        rows, skipped = page_through(client, "task", {"project_id": project.get("id")})
        unreadable += skipped
        for row in rows:
            if str(row.get("status") or "").upper() in OPEN_STATUSES:
                seen.setdefault(str(row.get("id")), row)
    try:
        owner = str(((client.call("whoami", {}) or {}).get("principal") or {}).get("contact_id") or "") or None
    except Exception:  # the pack stands without it; the gaps then skip the owner test
        owner = None
    tasks = sorted(({k: t.get(k) for k in TASK_FIELDS} for t in seen.values()),
                   key=lambda t: (str(t.get("due_date") or "9999"), str(t.get("title") or "")))
    return {"projects": [{"id": p.get("id"), "name": p.get("name"), "status": p.get("status"),
                          "is_general": bool(p.get("is_general")), "due_date": p.get("due_date"),
                          "assignee_contact_id": p.get("assignee_contact_id")} for p in projects],
            "tasks": tasks, "owner": owner, "unreadable": unreadable}


def task_gaps(tasks, owner):
    mine, out = (owner or "").lower(), []
    for t in tasks:
        who = str(t.get("owner_contact_id") or "").lower()
        problems = (["no owner"] if not who else []) + \
                   (["no due date"] if not t.get("due_date") and (not who or (mine and who == mine)) else [])
        if problems:
            out.append({"id": t.get("id"), "title": t.get("title"), "problems": problems})
    return out


def read_activity(domain, since, until):
    """report-collect's read-only sweep of the domain for [since, until] (its evidence ledger)."""
    if not REPORT_COLLECT.is_file():
        raise RuntimeError(f"report-collect is not installed at {REPORT_COLLECT}")
    with tempfile.TemporaryDirectory() as scratch:
        out = Path(scratch) / "ledger.json"
        done = subprocess.run([sys.executable, str(REPORT_COLLECT), "--domain", domain,
                               "--since", since.isoformat(), "--until", (until + timedelta(days=1)).isoformat(),
                               "--lookahead-days", "7", "--out", str(out)],
                              capture_output=True, text=True, timeout=900, check=False)
        if done.returncode != 0 or not out.is_file():
            raise RuntimeError(f"report-collect exited {done.returncode}: {done.stderr.strip()[:200]}")
        return json.loads(out.read_text(encoding="utf-8"))


def portal_items(ledger, domains):
    """The ledger's meetings, notes and mail, each ref once, mail only with a client domain."""
    kept, counts, seen = [], {}, set()
    for item in ledger.get("items") or []:
        kind = str(item.get("kind") or "")
        if kind not in PORTAL_KINDS:
            continue
        counts[f"{kind}_read"] = counts.get(f"{kind}_read", 0) + 1
        if kind == "mail" and domains and not any(
                str(p or "").strip().lower() == d or str(p or "").strip().lower().endswith(("@" + d, "." + d))
                for p in item.get("counterparties") or [] for d in domains):
            continue
        ref = str(item.get("ref") or "")
        if ref and ref in seen:
            continue
        seen.add(ref)
        counts[kind] = counts.get(kind, 0) + 1
        kept.append(item)
    return kept, counts


def portal_text(item):
    extra = item.get("extra") or {}
    body = str(item.get("text") or "").strip() or str(extra.get("excerpt") or "").strip()
    lines = [f"# {item.get('title') or '(untitled)'}", "", f"- Kind: {item.get('kind')}",
             f"- When: {item.get('occurred_at') or 'not known'}",
             f"- Who: {', '.join(str(c) for c in item.get('counterparties') or []) or 'not recorded'}",
             f"- Detail: {item.get('detail') or ''}".rstrip(),
             f"- Projects: {', '.join(str(p) for p in item.get('projects') or [])}".rstrip(),
             f"- Ref: {item.get('ref') or ''}".rstrip(), ""]
    return "\n".join(lines + ([body, ""] if body else []))


def safe(exc):
    return SECRET_RE.sub("[redacted]", f"{type(exc).__name__}: {exc}")[:300]


# --------------------------------------------------------------------------- files

def sow_text(path):
    """(text or None, a note): the SOW as text, for Word, slides, PDF, workbooks and text."""
    ext = path.suffix.lower()
    w, a = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}", \
        "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    try:
        if ext in (".md", ".txt"):
            return path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff"), ""
        if ext == ".docx":
            with zipfile.ZipFile(path) as z:
                body = ElementTree.fromstring(z.read("word/document.xml")).find(f"{w}body")

            def para(p):
                return "".join(n.text if n.tag == f"{w}t" and n.text else "\t" if n.tag == f"{w}tab" else ""
                               for n in p.iter())
            lines = []
            for child in body if body is not None else []:
                if child.tag == f"{w}p":
                    lines.append(para(child))
                elif child.tag == f"{w}tbl":
                    lines += [" | ".join(" ".join(para(p) for p in tc.iter(f"{w}p")).strip()
                                         for tc in tr.iter(f"{w}tc")) for tr in child.iter(f"{w}tr")]
            return "\n".join(lines).strip() + "\n", ""
        if ext == ".pptx":
            with zipfile.ZipFile(path) as z:
                names = sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                               key=lambda n: int(re.findall(r"\d+", n)[-1]))
                slides = [f"## Slide {i}\n" + "\n".join(t.text for t in ElementTree.fromstring(z.read(n)).iter(f"{a}t")
                                                         if t.text) for i, n in enumerate(names, 1)]
            return "\n\n".join(slides).strip() + "\n", ""
        if ext == ".pdf":
            from pypdf import PdfReader
            return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages), ""
        if ext in (".xlsx", ".xlsm"):
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            out = []
            for ws in wb.worksheets:
                out.append(f"## Sheet {ws.title}")
                out += [" | ".join(f"{c.coordinate}: {c.value}" for c in row if c.value not in (None, ""))
                        for row in ws.iter_rows() if any(c.value not in (None, "") for c in row)]
            wb.close()
            return "\n".join(out) + "\n", ""
    except ImportError as exc:
        return None, f"{exc.name} is not installed"
    except Exception as exc:  # a damaged file is a warning, not a dead pack
        return None, f"could not convert: {type(exc).__name__}"
    return None, "unsupported format"


def file_source(role, path, when, title, size):
    return {"role": role, "kind": "file", "title": title, "occurred_at": when.isoformat() if when else None,
            "ref": None, "path": str(path), "size": int(size)}


def scan_folders(folders, since, until, source_folders, never_open, skip_under):
    """Client-folder files modified in [since, until], or whose name holds a date in it. Files
    are only listed and stat'ed, never opened; Never open globs are skipped; the newest
    MAX_FOLDER_FILES are kept."""
    warnings, found, too_big, seen = [], [], [], set()
    skip = [os.path.abspath(str(p)) for p in skip_under]
    start = datetime.combine(since, datetime.min.time()).timestamp()
    end = datetime.combine(until + timedelta(days=1), datetime.min.time()).timestamp()

    def under(path, folder):
        return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)

    for folder in folders:
        base = os.path.abspath(str(folder))
        if not os.path.isdir(base):
            warnings.append(f"the engagement folder {folder} does not exist; skipped")
            continue
        # "." in Source folders means the folder's own files, without descending.
        roots = [(base, False) if sub.strip().rstrip("/") in (".", "") else
                 (os.path.normpath(os.path.join(base, sub)), True) for sub in source_folders] or [(base, True)]
        for root, recursive in roots:
            rel_root = os.path.relpath(root, base).replace(os.sep, "/")
            if not os.path.isdir(root) or any(under(root, s) for s in skip) or (
                    rel_root != "." and dc.matches_never_open(never_open, os.path.basename(root), rel_root)):
                continue
            stack = [root]
            while stack:
                current = stack.pop()
                try:
                    entries = list(os.scandir(current))
                except OSError as exc:
                    warnings.append(f"could not list {os.path.relpath(current, base)}: {type(exc).__name__}")
                    continue
                for entry in entries:
                    name, full = entry.name, entry.path
                    relative = os.path.relpath(full, base).replace(os.sep, "/")
                    if name.startswith((".", "~$")) or name.lower() == "desktop.ini" or \
                            dc.matches_never_open(never_open, name, relative):
                        continue
                    try:   # a synced drive can fail one entry; skip it, not the pack
                        is_dir = entry.is_dir(follow_symlinks=False)
                        info = None if is_dir else entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if is_dir:
                        if recursive and not any(under(full, s) for s in skip):
                            stack.append(full)
                        continue
                    if full in seen or not stat.S_ISREG(info.st_mode):
                        continue
                    dated = []
                    for m in re.finditer(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)", name):
                        try:
                            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                        except ValueError:
                            continue
                        if since <= d <= until:
                            dated.append(d)
                    if not (start <= info.st_mtime < end or dated):
                        continue
                    seen.add(full)
                    if info.st_size > MAX_BYTES:
                        too_big.append(relative)
                        continue
                    when = dated[0] if dated else datetime.fromtimestamp(info.st_mtime).date()
                    found.append((info.st_mtime, file_source("folder", Path(full), when, relative, info.st_size)))
    if too_big:
        warnings.append(f"{len(too_big)} file(s) over {MAX_BYTES // (1024 * 1024)} MB left out: "
                        + ", ".join(sorted(too_big)[:10]) + (" ..." if len(too_big) > 10 else ""))
    found.sort(key=lambda t: t[0], reverse=True)
    if len(found) > MAX_FOLDER_FILES:
        warnings.append(f"{len(found)} engagement-folder files in the window; the newest {MAX_FOLDER_FILES} kept")
        found = found[:MAX_FOLDER_FILES]
    return sorted((s for _, s in found), key=lambda s: (s.get("occurred_at") or "", s["title"])), warnings


def repo_log(repo, since, until):
    """(the git log text for the window, or None and a note)."""
    if not repo.is_dir():
        return None, f"the repo {repo} does not exist"
    try:
        done = subprocess.run(["git", "-C", str(repo), "log", f"--since={since} 00:00:00",
                               f"--until={until} 23:59:59", "--date=short", "--pretty=format:%h %ad %an %s"],
                              capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"git log could not run in {repo}: {type(exc).__name__}"
    if done.returncode != 0:
        return None, f"git log failed in {repo}: {done.stderr.strip()[:200]}"
    return (done.stdout.strip(), None) if done.stdout.strip() else (None, f"no commits in {repo.name} from {since} to {until}")


# --------------------------------------------------------------------------- the pack

def copy_state(live, copy):
    """A dry run's working folder: the live folder's state files, copied once."""
    copy.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in dc.STATE_FILES:
        if (live / name).is_file() and not (copy / name).exists():
            shutil.copy2(live / name, copy / name)
            copied.append(name)
    return copied


def sources_md(pack):
    out = [f"# Sources for {pack['engagement']}, {pack['since']} to {pack['as_of']}", ""]
    for role in ROLES:
        mine = [s for s in pack["sources"] if s["role"] == role]
        if mine:
            out += [f"## {role} ({len(mine)})", ""]
            out += [f"- {s['id']} {s.get('occurred_at') or 'undated'} {s.get('kind')}: {s['title']}"
                    f"{' ' + s['ref'] if s.get('ref') else ''} ({s.get('path')})" for s in mine]
            out.append("")
    return "\n".join(out)


def resolve_mode(mode, milestone, today):
    chosen = (dc.blank(mode) or ("plan" if today.weekday() == 0 else "check")).lower()
    if chosen not in dc.MODES:
        raise dc.Bad(f"--mode {chosen!r} is not one of {', '.join(dc.MODES)}")
    if chosen == "milestone-review" and not dc.blank(milestone):
        raise dc.Bad("--mode milestone-review needs --milestone, the milestone's id in PLAN.md")
    return chosen


def build(engagement, run_dir, mode=None, milestone=None, dry_run_if=None, as_of=None, since=None,
          contexts=None, no_portal=False, portal=None):
    """Write the pack and return it. `portal` stands in for the Portal client in tests."""
    if not dc.blank(run_dir):
        raise dc.Bad("--run-dir is required")
    eng = dc.load_engagement(engagement, contexts)
    rules = eng["rules"]
    today = dc.as_of_date(as_of)
    chosen = resolve_mode(mode, milestone, today)
    milestone = dc.blank(milestone)
    dry = dc.truthy(dry_run_if)
    out_dir = Path(run_dir.strip()).expanduser() / dc.PACK_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    warnings, copied, working = [], [], eng["working"]
    if dry:
        working = out_dir / "working"
        copied = copy_state(eng["working"], working)
    plan = dc.read_plan(working / dc.PLAN_MD)
    evidence = dc.evidence_ledger(working).rows()
    raid = dc.raid_ledger(working).rows()
    if chosen == "milestone-review" and milestone not in {m["id"] for m in plan["milestones"]}:
        warnings.append(f"milestone {milestone} is not in {dc.PLAN_MD}")
    last = dc.latest_session(evidence)
    start = dc.parse_date(since, "--since") or (last if last and last < today else
                                                today - timedelta(days=rules["lookback_days"]))

    sow, sow_q, texts = rules["sow"], None, []
    if sow["state"] == "missing":
        sow_q = (f"No signed SOW is on file for {eng['name']} ({sow['note']}). Please supply the executed "
                 "SOW, or confirm there is none, so the plan has a scope baseline.")
        warnings.append("no SOW on file: the plan carries no baseline; the owner is asked")
    for path in sow["files"]:
        if path.is_file():
            text, note = sow_text(path)
            if text is None:
                warnings.append(f"the SOW {path.name} could not be read as text ({note}); read the file itself")
            source = file_source("sow", path, None, path.name, path.stat().st_size)
            source["kind"] = "sow"
            texts.append((source, text))
    if eng["engagements"]:
        found, notes = scan_folders(eng["engagements"], start, today, rules["source_folders"],
                                    rules["never_open"], [eng["working"], working])
        texts += [(s, None) for s in found]
        warnings += notes
    else:
        warnings.append("the Context has no engagement folder, so no folder files are in the pack")

    stale, projects, owner = None, [], None
    portal_info = {"domain": rules["portal_domain"], "read": False, "error": None, "counts": {}}
    tasks = {"read": False, "error": None, "items": [], "gaps": [], "unreadable": 0}
    if no_portal:
        portal_info["error"] = tasks["error"] = "not read: --no-portal"
    elif not rules["portal_domain"]:
        portal_info["error"] = tasks["error"] = "not read: the rules name no Portal domain"
        warnings.append("the rules name no Portal domain, so no task or activity was read")
    else:
        try:
            items, counts = portal_items(read_activity(rules["portal_domain"], start, today),
                                         rules["client_email_domains"])
            portal_info.update(read=True, counts=counts)
            for item in items:
                text = portal_text(item)
                texts.append(({"role": "portal", "kind": str(item.get("kind")),
                               "title": str(item.get("title") or "(untitled)"), "occurred_at": item.get("occurred_at"),
                               "ref": item.get("ref") or None, "path": None, "size": len(text.encode())}, text))
        except Exception as exc:  # an unreadable Portal is a stale pack, not a dead one
            portal_info["error"] = safe(exc)
            stale = f"the Portal activity could not be read ({portal_info['error']})"
            warnings.append(stale)
        try:
            read = read_tasks(portal if portal is not None else Portal(), rules["portal_domain"])
            projects, owner = read["projects"], read["owner"]
            tasks.update(read=True, items=read["tasks"], unreadable=read["unreadable"],
                         gaps=task_gaps(read["tasks"], owner))
            if read["unreadable"]:
                warnings.append(f"{read['unreadable']} task or project row(s) could not be read")
        except Exception as exc:
            tasks["error"] = safe(exc)
            stale = stale or f"the engagement's tasks could not be read ({tasks['error']})"
            warnings.append(f"the engagement's tasks could not be read ({tasks['error']})")

    if eng["repo"] is not None:
        log, note = repo_log(eng["repo"], start, today)
        if log:
            text = f"# git log of {eng['repo'].name}, {start} to {today}\n\n{log}\n"
            texts.append(({"role": "repo", "kind": "git-log", "title": f"git log of {eng['repo'].name}",
                           "occurred_at": today.isoformat(), "ref": None, "path": None, "size": len(text.encode())}, text))
        elif note:
            warnings.append(note)

    texts.sort(key=lambda pair: ROLES.index(pair[0]["role"]))
    src_dir = out_dir / "sources"
    if src_dir.exists():
        shutil.rmtree(src_dir)
    for number, (source, text) in enumerate(texts, start=1):
        source["id"] = f"S{number:03d}"
        if text is not None:
            src_dir.mkdir(parents=True, exist_ok=True)
            path = src_dir / f"{source['id']}.md"
            path.write_text(text, encoding="utf-8")
            source["text_path"] = str(path)
            source["path"] = source.get("path") or str(path)

    pack = {
        "schema": dc.PACK_SCHEMA, "engagement": eng["name"], "context_file": str(eng["context_file"]),
        "rules_file": str(eng["rules_file"]), "mode": chosen, "milestone": milestone,
        "as_of": today.isoformat(), "since": start.isoformat(), "dry_run": dry,
        "folders": {"working": str(working), "live_working": str(eng["working"]),
                    "working_exists": eng["working"].is_dir(), "copied": copied,
                    "rules": str(eng["rules_file"].parent), "engagements": [str(p) for p in eng["engagements"]],
                    "repo": str(eng["repo"]) if eng["repo"] else None, "pack": str(out_dir), "run": str(out_dir.parent)},
        "settings": {k: rules[k] for k in ("portal_domain", "lead_time_days", "raid_review_days",
                                           "session_stale_days", "assignable", "client_email_domains")},
        "sow": {"state": sow["state"], "files": [str(p) for p in sow["files"]], "note": sow["note"], "question": sow_q},
        "baseline": rules["baseline"], "plan": plan, "evidence": evidence, "raid": raid,
        "owner_contact": owner, "projects": projects, "tasks": tasks, "portal": portal_info,
        "sources": [{k: s.get(k) for k in ("id", "role", "kind", "title", "occurred_at", "ref", "path",
                                          "text_path", "size")} for s, _ in texts],
        "warnings": warnings, "stale": stale, "generated_at": dc.now_utc(),
    }
    (out_dir / dc.PACK_JSON).write_text(json.dumps(pack, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "tasks.json").write_text(json.dumps({"projects": projects, "tasks": tasks, "owner": owner},
                                                   indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "sources.md").write_text(sources_md(pack), encoding="utf-8")
    before_file = out_dir / "check-before.json"
    command = [sys.executable, str(CHECK), engagement, "--working", str(working), "--pack", str(out_dir),
               "--as-of", today.isoformat(), "--out", str(before_file), "--format", "json"]
    if dc.blank(contexts):
        command += ["--contexts-dir", contexts.strip()]
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise dc.Bad(f"delivery_check.py failed: {done.stderr.strip()[:300]}")
    before = json.loads(before_file.read_text(encoding="utf-8"))
    pack["check_before"] = {"met": before["met"], "of": before["of"],
                            "open": [n for n, t in before["tests"].items() if not t["met"]]}
    (out_dir / dc.PACK_JSON).write_text(json.dumps(pack, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return pack


def render(pack):
    n, t = len(pack["sources"]), len(pack["tasks"]["items"])
    where = f"pack at {pack['folders']['pack']}; working folder {pack['folders']['working']}"
    out = [f"STALE: {pack['stale']}; {n} sources, {t} open tasks, {where}" if pack.get("stale") else
           f"FRESH: {n} sources, {t} open tasks for {pack['engagement']} ({pack['since']} to {pack['as_of']}), {where}"]
    out.append(f"  mode: {pack['mode']}" + (f" {pack['milestone']}" if pack.get("milestone") else "")
               + (" (dry run: the working folder is a copy)" if pack["dry_run"] else ""))
    out.append("  by role: " + ", ".join(f"{r} {sum(1 for s in pack['sources'] if s['role'] == r)}" for r in ROLES))
    out.append(f"  sow: {pack['sow']['state']} ({pack['sow']['note']})")
    plan = pack["plan"]
    out.append(f"  plan: {len(plan['milestones'])} milestone(s)" if plan["present"] else "  plan: none yet")
    out.append(f"  raid: {sum(1 for r in pack['raid'] if r.get('state') == 'open')} open item(s)")
    out.append(f"  tasks: {t} open, {len(pack['tasks']['gaps'])} with gaps" if pack["tasks"]["read"]
               else f"  tasks: not read ({pack['tasks']['error']})")
    cb = pack["check_before"]
    out.append(f"  check before: {cb['met']} of {cb['of']} met" + (f"; open: {', '.join(cb['open'])}" if cb["open"] else ""))
    out += [f"  warning: {w}" for w in pack["warnings"]]
    return "\n".join(out)


def main(argv=None, portal=None):
    p = argparse.ArgumentParser(description="Gather one engagement into RUN/delivery/ before the delivery session.")
    p.add_argument("engagement", nargs="?", default="", help="Context name or path to a Context YAML file")
    p.add_argument("--run-dir", default="", help="The Run folder; the pack goes to RUN/delivery/")
    p.add_argument("--mode", default="", help="plan, check or milestone-review; blank: plan on Monday, else check")
    p.add_argument("--milestone", default="", help="The milestone id for a milestone review")
    p.add_argument("--dry-run-if", default="", help="true, 1, yes or on: copy the working folder into the Run folder")
    p.add_argument("--as-of", default="", help="Today (yyyy-mm-dd); blank: today")
    p.add_argument("--since", default="", help="Start of the window (yyyy-mm-dd); blank: the last session")
    p.add_argument("--contexts-dir", default="", help="Where Context YAML files are found by name")
    p.add_argument("--no-portal", action="store_true", help="Do not read the Portal")
    p.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)
    try:
        if not a.engagement.strip():
            raise dc.Bad("ENGAGEMENT is required: the engagement's Context name")
        pack = build(a.engagement, a.run_dir, a.mode, a.milestone, a.dry_run_if, a.as_of, a.since,
                     a.contexts_dir, a.no_portal, portal)
    except (dc.Bad, dc.Refused) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    print(json.dumps(pack, indent=1, ensure_ascii=False) if a.format == "json" else render(pack))
    return 0


if __name__ == "__main__":
    sys.exit(main())
