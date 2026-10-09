#!/usr/bin/env python3
"""report-collect: read one author's week once and write the evidence ledger.

Everything after collection reads the ledger and nothing after it knows which tier wrote it:

  portal     (default) the work tracker, calendar and mail are in the Insights Portal and are
             read here in code, read-only. Needs the setting portal_mcp_config.
  manual     --tier manual --from-dir DIR folds a folder of Markdown or text files in, one
             evidence item per file. A file named direct-report* or report-from* is a direct
             report's update; anything else is the executive's own notes. Front matter
             (`key: value` lines between `---` rules) may set kind, date, title, from, projects.
  harvester  a worker writes the ledger itself; `--validate FILE` checks it against the
             contract (and with --out writes the checked copy). A ledger naming no tier is
             recorded as the harvester tier and model-driven.

The ledger (schema "evidence-ledger/1") carries: tier, model_driven, generated_at, generator,
author {scope_kind, scope_name, ...}, period {since, until, timezone, as_of, ...}, outline
(the profile or outline as read this week), items, direct_reports, prior_reports, goals,
calendar, provenance {caps_applied, warnings, could_not_determine}. One item carries source,
kind (task, project, note, mail, meeting, direct_report), ref (unique), title, detail, text,
occurred_at, hours, counterparties, projects, weight and extra. A thing that cannot be known is
null with its reason in provenance, never a zero.

Prints the path written, or the ledger as JSON with no --out. Exit 0 ok, 2 error.

Examples:
  python3 report_collect.py --domain "Northwind" --since 2027-11-08 --until 2027-11-13 \\
      --outline-file ~/reports/finance/profile.md --out ledger.json
  python3 report_collect.py --tier manual --from-dir ./incoming --domain "Finance" \\
      --since 2027-11-08 --until 2027-11-13 --outline-file profile.md --out ledger.json
  python3 report_collect.py --validate ledger.json --out ledger.json
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, time as clock, timedelta, timezone
from pathlib import Path

import _profile as pf
from _common import (ERROR, LEDGER_SCHEMA as SCHEMA, LEDGER_TIERS as TIERS, OK, Fail, as_date,
                     ledger_errors, normalise_ledger as normalise, now_utc, report_bullets,
                     read_text, run_main, safe, write_json)

SOURCE_OF = {"task": "work_tracker", "project": "work_tracker", "note": "note", "mail": "mail",
             "meeting": "calendar", "direct_report": "direct_report"}
TASK_LISTS = ("created_in_period", "due_in_lookahead", "overdue", "waiting")
CLOSED_TASK = {"done", "completed", "complete", "cancelled", "canceled", "archived", "closed", "dropped"}
CLOSED_PROJECT = {"completed", "complete", "done", "cancelled", "canceled", "archived", "closed", "abandoned"}
WAITING_TASK = {"waiting", "blocked", "waiting_on", "on_hold", "deferred"}
COULD_NOT = [
    {"what": "completions", "why": "the task listing omits completed tasks and caps a completed "
                                   "listing at 1,000 rows in no date order, so completions cannot "
                                   "be windowed from a listing"},
    {"what": "outbound mail", "why": "a sent message exposes no recipient, so outbound volume by "
                                     "counterpart cannot be reported"},
    {"what": "cash and profit and loss figures", "why": "those live in the accounting system, not "
                                                        "the Portal"},
]
PRIOR_PREFIXES = ("Weekly Highlights", "Weekly report:")
PROFILE_TITLES = ("Weekly report profile", "Weekly report outline")
REPLY_PREFIX = re.compile(r"^\s*(re|fwd|fw|aw|antw|rv|vs)\s*(\[\d+\])?\s*:\s*", re.IGNORECASE)
QUOTE_START = re.compile(r"^\s*(?:>|-{2,}\s*Original Message|_{5,}|From:\s|Sent:\s|On .{0,160}\bwrote:"
                         r"\s*$|Sent from my |Get Outlook for )", re.IGNORECASE)


# --------------------------------------------------------------------------- the manual tier

FRONT_MATTER = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n?", re.DOTALL)


def manual_item(path, index):
    """One supplied file as one evidence item. The date comes from the front matter, else from
    the file's modified time, because a date read out of the prose would be a guess."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    fields, body = {}, raw
    hit = FRONT_MATTER.match(raw)
    if hit:
        body = raw[hit.end():]
        for line in hit.group("body").splitlines():
            found = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_\- ]*)\s*:\s*(.*)$", line)
            if found:
                fields["_".join(found.group(1).casefold().split())] = found.group(2).strip().strip("'\"")
    kind = fields.get("kind", "").casefold().replace("-", "_")
    if kind not in ("direct_report", "note"):
        kind = "direct_report" if re.match(r"(?i)^(direct[-_ ]?report|report[-_ ]from)\b", path.stem) else "note"
    when = fields.get("occurred_at") or fields.get("date") or ""
    dated = "the file's front matter"
    if not when:
        when = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        dated = "the file's modified time, because it carries no date"
    title = fields.get("title") or next((ln.lstrip("# ").strip() for ln in body.splitlines()
                                         if ln.strip().startswith("#")), "") \
        or path.stem.replace("-", " ").replace("_", " ")
    author = fields.get("from") or fields.get("author") or ""
    return {"source": SOURCE_OF[kind], "kind": kind, "ref": f"file://{index}/{path.name}",
            "title": title, "detail": (f"from {author}, " if author else "")
            + f"supplied as a file, dated from {dated}",
            "text": body.strip(), "occurred_at": when, "hours": None,
            "counterparties": [author] if author else [],
            "projects": [p.strip() for p in fields.get("projects", "").split(",") if p.strip()],
            "weight": 0.0, "extra": {"file": path.name, "front_matter": fields or None}}


def manual_ledger(from_dir, domain, since, until, outline_file):
    if not str(from_dir or "").strip():
        raise Fail("--from-dir is required for the manual tier: the folder of reports and notes")
    root = Path(from_dir).expanduser()
    if not root.is_dir():
        raise Fail(f"no folder at {root}")
    everything = sorted(p for p in root.iterdir() if p.is_file())
    files = [p for p in everything if p.suffix.casefold() in (".md", ".markdown", ".txt", ".text")]
    skipped = [p.name for p in everything if p not in files]
    warnings = ([f"{len(skipped)} file(s) in {root} are not Markdown or text and were not read: "
                 f"{', '.join(skipped[:5])}"] if skipped else [])
    if not files:
        warnings.append(f"{root} holds no Markdown or text file, so the whole week comes from the gates")
    items = [manual_item(path, index) for index, path in enumerate(files, 1)]
    outline = pf.outline_from_file(outline_file) if str(outline_file or "").strip() else {}
    stamp = now_utc()
    start = str(since or "").strip() or min((str(i["occurred_at"])[:10] for i in items), default=stamp[:10])
    end = str(until or "").strip() or stamp[:10]
    name = str(domain or "").strip() or root.name
    return {
        "schema": SCHEMA, "tier": "manual", "model_driven": False, "generated_at": stamp,
        "generator": "report-collect (manual tier)",
        "author": {"scope_kind": "manual", "scope_id": None, "scope_name": name, "short_name": name,
                   "seats": [s["name"] for s in outline.get("seats") or []]},
        # The until date is exclusive, so the period's last day is the day before it.
        "period": {"since": start, "until": end, "timezone": "UTC",
                   "as_of": (as_date(end) - timedelta(days=1)).isoformat() if str(until or "").strip() and as_date(end)
                   else end,
                   "lookahead_until": None, "lookahead_days": 0},
        "outline": outline_block(outline),
        "items": items,
        "direct_reports": [{"name": (i["counterparties"] or ["a direct report"])[0], "reports_on": None,
                            "source": "file", "found": True, "ref": i["ref"], "title": i["title"],
                            "received": i["occurred_at"], "text": i["text"]}
                           for i in items if i["kind"] == "direct_report"],
        "prior_reports": [], "goals": [], "calendar": None,
        "provenance": {"caps_applied": [], "warnings": warnings, "files_read": [p.name for p in files],
                       "could_not_determine": [{"what": "the work tracker, the calendar and the mail",
                                                "why": "the manual tier reads none of them"}]},
    }


def outline_block(outline, text=""):
    return {"source": str(outline.get("source") or "none"), "read_as": outline.get("read_as"),
            "note_title": outline.get("note_title"), "found": bool(outline.get("found")),
            "note_ref": outline.get("note_ref"), "text": text, "parsed": outline or None}


# --------------------------------------------------------------------------- the portal tier

def parse_time(value):
    """An ISO timestamp or date as an aware UTC datetime, or None."""
    text = str(value or "").strip().replace("Z", "+00:00").replace("z", "+00:00")
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        try:
            moment = datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return None
    return (moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def iso(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def day_of(moment):
    return moment.date().isoformat() if moment else None


def clip(text, limit):
    body = str(text or "")
    return body if limit <= 0 or len(body) <= limit else body[:limit].rstrip() + "… [truncated]"


def items_of(out, key="items"):
    return [r for r in ((out or {}).get(key) or []) if isinstance(r, dict)] if isinstance(out, dict) else []


def owner_of(portal):
    """The owner's timezone and own addresses, from one whoami. Failures warn, never stop."""
    warnings, addresses, tz, tz_name = [], [], timezone.utc, "UTC"
    who = portal.safe_call("whoami")
    if not isinstance(who, dict):
        warnings.append("whoami failed: day boundaries are in UTC and no address is the owner's own")
        who = {}
    principal = who.get("principal") or {}
    for address in [principal.get("primary_email")] + [
            i.get("address") if isinstance(i, dict) else i for i in who.get("inboxes") or []]:
        address = str(address or "").strip().casefold()
        if "@" in address and address not in addresses:
            addresses.append(address)
    if principal.get("timezone"):
        try:
            from zoneinfo import ZoneInfo
            tz, tz_name = ZoneInfo(principal["timezone"]), principal["timezone"]
        except Exception:  # noqa: BLE001 - an unknown zone name is a warning, not a stop
            warnings.append(f"unknown timezone {principal['timezone']!r}: day boundaries are in UTC")
    return {"tz": tz, "timezone": tz_name, "addresses": addresses, "warnings": warnings}


def resolve_period(since, until, tz, now):
    """[since, until): a bare date is local midnight; the default is the last seven full days."""
    def bound(text, option):
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            day = as_date(text)
            return datetime.combine(day, clock(0), tzinfo=tz).astimezone(timezone.utc)
        found = parse_time(text)
        if found is None:
            raise Fail(f"{option} wants YYYY-MM-DD or an ISO instant, got {text!r}")
        return found
    midnight = lambda m: datetime.combine(m.astimezone(tz).date(), clock(0), tzinfo=tz).astimezone(timezone.utc)  # noqa: E731
    end = bound(until.strip(), "--until") if until.strip() else midnight(now)
    start = bound(since.strip(), "--since") if since.strip() else midnight(end.astimezone(tz) - timedelta(days=7))
    if start >= end:
        raise Fail(f"--since {start.isoformat()} is not before --until {end.isoformat()}")
    return start, end


def resolve_domain(portal, wanted):
    """The one domain whose id or name matches. An ambiguous match is an error, not a guess."""
    if not str(wanted or "").strip():
        raise Fail("--domain is required for the portal tier: a name substring or a uuid")
    rows, _ = portal.page("domain")
    exact = [r for r in rows if str(r.get("id") or "") == wanted.strip()]
    hits = exact or [r for r in rows if wanted.strip().casefold() in str(r.get("name") or "").casefold()]
    if len(hits) > 1:
        hits = [r for r in hits if str(r.get("name") or "").strip().casefold() == wanted.strip().casefold()] or hits
    if not hits:
        raise Fail(f"no domain name contains {wanted!r} ({len(rows)} domains read)")
    if len(hits) > 1:
        raise Fail(f"{len(hits)} domains match {wanted!r}; pass a longer name or the uuid")
    return hits[0]


def scope_term_for(name, override=""):
    """The short name a search runs on: text in parentheses, else the first two words."""
    if str(override or "").strip():
        return override.strip()
    inside = re.search(r"\(([^)]{2,})\)", name or "")
    return inside.group(1).strip() if inside else " ".join(str(name or "").split()[:2])


def note_body(portal, note):
    full = portal.safe_call("get", {"entity_type": "note", "id_or_query": str(note.get("id") or "")})
    full = full if isinstance(full, dict) else {}
    return full, str(full.get("content") if full.get("content") is not None else note.get("content_preview") or "")


def resolve_outline(portal, domain_id, outline_file, warnings):
    """--outline-file, else the scope's `Weekly report profile` note, else an older `Weekly
    report outline` note. With none, the categories are empty and every item is unassigned."""
    if str(outline_file or "").strip():
        found = pf.outline_from_file(outline_file)
        return found, Path(outline_file).expanduser().read_text(encoding="utf-8")
    for title in PROFILE_TITLES:
        listed = items_of(portal.safe_call("list_entities", {
            "entity_type": "note", "limit": 25,
            "filters": {"entity_type": "domain", "entity_id": domain_id, "search": title}}))
        titled = sorted((n for n in listed if str(n.get("title") or "").strip().casefold() == title.casefold()),
                        key=lambda n: str(n.get("updated_at") or ""), reverse=True)
        if titled:
            full, text = note_body(portal, titled[0])
            found = pf.parse_outline(text, f"note:{title}")
            found.update(found=True, note_title=title, note_ref=full.get("_ref") or titled[0].get("_ref"))
            if len(titled) > 1:
                warnings.append(f"{len(titled)} notes on this scope are titled {title!r}; the newest was used")
            return found, text
    warnings.append("no 'Weekly report profile' or 'Weekly report outline' note on this scope and no "
                    "--outline-file, so the categories are empty; write the role profile first")
    return {"source": "none", "read_as": "none", "found": False, "categories": [], "seats": []}, ""


def meeting_signals(text):
    """Attendee domains, title patterns and mail terms from the outline's Meeting signals field."""
    body = str(text or "")
    domains = [d.casefold() for d in re.findall(r"(?i)\bdomains?\s*[:=]?\s*[`'\"]?([A-Za-z0-9.\-]+\.[A-Za-z]{2,})", body)]
    titles = re.findall(r"(?i)\btitles?(?:\s+patterns?)?\s*[:=]?\s*`([^`]+)`", body)
    titles += [f"(?i){p}" if "i" in f else p
               for p, f in re.findall(r"(?i)\btitles?(?:\s+patterns?)?\s*[:=]?\s*/(.+?)/([a-z]*)", body)]
    terms = re.findall(r"(?i)\bmail\s+terms?\s*[:=]?\s*`([^`]+)`", body)
    good = []
    for pattern in titles:
        try:
            re.compile(pattern)
            good.append(pattern)
        except re.error:
            pass
    return {"domains": list(dict.fromkeys(domains)), "titles": list(dict.fromkeys(good)),
            "terms": list(dict.fromkeys(terms)), "bad_titles": [p for p in titles if p not in good]}


def is_open(task):
    return not task.get("is_archived") and str(task.get("status") or "").casefold() not in CLOSED_TASK


def task_lists(tasks, since, until, lookahead_end, cap, caps):
    """The four lists a report cites. A task in two lists is one item carrying both names."""
    lists = {name: [] for name in TASK_LISTS}
    for task in tasks:
        if task.get("is_archived"):
            continue
        made, due = parse_time(task.get("created_at")), parse_time(task.get("due_date") or task.get("deadline"))
        if made and since <= made < until:
            lists["created_in_period"].append(task)
        if due and is_open(task):
            if until <= due < lookahead_end:
                lists["due_in_lookahead"].append(task)
            elif due < until:
                lists["overdue"].append(task)
        if is_open(task) and str(task.get("status") or "").casefold() in WAITING_TASK:
            lists["waiting"].append(task)
    order = {"created_in_period": ("created_at", True), "due_in_lookahead": ("due_date", False),
             "overdue": ("due_date", False), "waiting": ("updated_at", True)}
    for name, rows in lists.items():
        key, newest = order[name]
        rows.sort(key=lambda t: str(t.get(key) or t.get("deadline") or ""), reverse=newest)
        if len(rows) > cap:
            caps.append(f"{len(rows) - cap} tasks beyond the first {cap} were left out of the {name} list")
            del rows[cap:]
    return lists


def project_rows(projects, tasks, goals, now, limit, required, caps):
    """Each active project with its counts and pressure flags. The top `limit` by pressure are
    kept, plus every flagged project and every project a listed task or note belongs to."""
    by_project, goal_names = {}, {str(g.get("id")): str(g.get("title") or g.get("name") or "") for g in goals}
    for task in tasks:
        if task.get("project_id"):
            by_project.setdefault(str(task["project_id"]), []).append(task)
    rows = []
    for project in projects:
        if project.get("is_archived") or project.get("is_general") \
                or str(project.get("status") or "").casefold() in CLOSED_PROJECT:
            continue
        mine = by_project.get(str(project.get("id")), [])
        live = [t for t in mine if is_open(t)]
        dues = [d for t in live if (d := parse_time(t.get("due_date") or t.get("deadline")))]
        overdue = len([d for d in dues if d.date() < now.date()])
        soon = len([d for d in dues if 0 <= (d.date() - now.date()).days <= 7])
        waiting = len([t for t in live if str(t.get("status") or "").casefold() in WAITING_TASK])
        stamps = [m for x in [project] + mine for k in ("updated_at", "completed_at", "created_at")
                  if (m := parse_time(x.get(k)))]
        idle = (now.date() - max(stamps).date()).days if stamps else None
        flags = [f for f, on in (("OVERDUE", overdue), ("DUE_SOON", soon),
                                 ("WAITING_HEAVY", waiting >= 3 or (waiting and waiting * 2 >= len(live))),
                                 ("STALE_30D", idle is not None and idle >= 30),
                                 ("NO_NEXT_TASK", not [d for d in dues if d.date() >= now.date()])) if on]
        rows.append({"project_id": str(project.get("id") or ""), "_ref": project.get("_ref"),
                     "name": str(project.get("name") or project.get("title") or ""),
                     "goal": goal_names.get(str(project.get("goal_id") or "")) or None,
                     "status": project.get("status"), "flags": flags, "open_tasks": len(live),
                     "waiting_tasks": waiting, "overdue_tasks": overdue,
                     "nearest_due_date": day_of(min(dues)) if dues else None,
                     "days_since_activity": idle, "score": 3 * overdue + 2 * soon + waiting})
    rows.sort(key=lambda r: (-r["score"], r["name"].casefold()))
    keep = [r for i, r in enumerate(rows) if i < limit or r["project_id"] in required
            or {"OVERDUE", "DUE_SOON", "WAITING_HEAVY"} & set(r["flags"])]
    if len(keep) < len(rows):
        caps.append(f"{len(rows) - len(keep)} active projects below the top {limit}, with no pressure "
                    f"flag and no listed task or note, were left out")
    return keep


def gather_notes(portal, domain_id, project_ids, since, until, term, max_project_calls, cap,
                 max_chars, caps):
    """Notes edited or written in the period, from the domain, its projects and a search on the
    scope's short name, each read in full. The listing's `since` matches the last edit, so a note
    written before the period is marked as edited rather than authored in it."""
    seen = {}
    listings = [{"entity_type": "domain", "entity_id": domain_id}] + \
               [{"entity_type": "project", "entity_id": p} for p in project_ids[:max(0, max_project_calls)]]
    if len(project_ids) > max_project_calls:
        caps.append(f"{len(project_ids) - max_project_calls} projects had no note listing run, the "
                    f"cap being {max_project_calls}")
    for filters in listings:
        for note in items_of(portal.safe_call("list_entities", {
                "entity_type": "note", "limit": 200, "filters": dict(filters, since=iso(since))})):
            seen.setdefault(str(note.get("id")), note)
    if term:
        for note in items_of(portal.safe_call("search", {"query": term}), "notes"):
            seen.setdefault(str(note.get("id")), note)
    inside = [n for n in seen.values() if any((m := parse_time(n.get(k))) and since <= m < until
                                              for k in ("updated_at", "created_at"))]
    inside.sort(key=lambda n: str(n.get("updated_at") or n.get("created_at") or ""), reverse=True)
    if len(inside) > cap:
        caps.append(f"{len(inside) - cap} notes beyond the newest {cap} were left out")
    out = []
    for note in inside[:cap]:
        full, text = note_body(portal, note)
        created = parse_time(full.get("created_at") or note.get("created_at"))
        out.append({"id": str(note.get("id")), "_ref": full.get("_ref") or note.get("_ref"),
                    "title": str(full.get("title") or note.get("title") or ""),
                    "note_type": full.get("note_type") or note.get("note_type") or "note",
                    "created_at": day_of(created),
                    "attached": [{"entity_type": a.get("entity_type"), "entity_id": str(a.get("entity_id"))}
                                 for a in full.get("associations") or [] if isinstance(a, dict)],
                    "authored_in_period": not (created and created < since),
                    "content": clip(text, max_chars)})
    return out, list(seen.values())


def calendar_block(portal, owner, since, until, lookahead_end, signals, term, warnings):
    """In-scope meeting time for the period and the look-ahead. An event carries no domain, so
    a meeting is in scope by an attendee's email domain (never the owner's own address) or a
    title pattern; with neither, by a title match on the scope's short name."""
    domains, titles = signals["domains"], list(signals["titles"])
    fallback = not domains and not titles and bool(term)
    if fallback:
        titles = [f"(?i){re.escape(term)}"]
    compiled = [(t, re.compile(t, re.IGNORECASE)) for t in titles]
    own = set(owner["addresses"])

    def read(start, end):
        rows, unreadable = portal.page("calendar_event", {"since": iso(start), "until": iso(end)})
        if unreadable:
            warnings.append(f"{unreadable} calendar rows could not be read and are missing")
        best = {}
        for row in rows:
            title = str(row.get("title") or "").strip()
            begin, finish = parse_time(row.get("start_time")), parse_time(row.get("end_time"))
            if str(row.get("event_kind") or "").casefold() != "meeting" or row.get("is_all_day") \
                    or re.match(r"(?i)^\s*cancell?ed:", title) or not begin or not finish or finish <= begin:
                continue
            attendees = [str(a.get("email") if isinstance(a, dict) else a or "").strip().casefold()
                         for a in row.get("attendees") or []]
            attendees = [a for a in attendees if "@" in a]
            plain = re.sub(r"(?i)\s*[\(\[]\s*clone(?:\s*\d+)?\s*[\)\]]", "", title)
            while REPLY_PREFIX.match(plain):
                plain = REPLY_PREFIX.sub("", plain, count=1)
            key = (begin.isoformat(), finish.isoformat(), " ".join(plain.split()).casefold())
            if key not in best or len(attendees) > len(best[key][3]):
                best[key] = (row, begin, finish, attendees)
        meetings, every = [], []
        for row, begin, finish, attendees in best.values():
            hours = round((finish - begin).total_seconds() / 3600, 2)
            every.append(hours)
            hit_domains = sorted({a.split("@")[1] for a in attendees if a not in own and a.split("@")[1] in domains})
            hit_titles = [t for t, c in compiled if c.search(row.get("title") or "")]
            if not hit_domains and not hit_titles:
                continue
            meetings.append({"ref": row.get("_ref") or f"portal://calendar_event/{row.get('id')}",
                             "title": str(row.get("title") or "").strip(), "hours": hours,
                             "begin": begin, "finish": finish,
                             "start_local": begin.astimezone(owner["tz"]).isoformat(),
                             "attendee_count": len(attendees), "matched_domains": hit_domains,
                             "matched_by": (["attendee_domain"] if hit_domains else []) + (["title"] if hit_titles else [])})
        meetings.sort(key=lambda m: m["start_local"])
        return meetings, round(sum(every), 2)

    period, everything = read(since, until)
    ahead, _ = read(until, lookahead_end)
    spans, union = sorted((m["begin"], m["finish"]) for m in period), 0.0
    current = None
    for begin, finish in spans:
        if current and begin <= current[1]:
            current = (current[0], max(current[1], finish))
            continue
        union += (current[1] - current[0]).total_seconds() if current else 0
        current = (begin, finish)
    union += (current[1] - current[0]).total_seconds() if current else 0
    by_day = {}
    for m in period:
        by_day[m["start_local"][:10]] = round(by_day.get(m["start_local"][:10], 0) + m["hours"], 2)
    summed = round(sum(m["hours"] for m in period), 2)
    strip = lambda rows: [{k: v for k, v in m.items() if k not in ("begin", "finish")} for m in rows]  # noqa: E731
    return strip(period), {
        "scope_match": {"domains": domains, "title_patterns": titles, "fell_back_to_scope_term": fallback},
        "period": {"meetings_in_scope": len(period), "hours_sum": summed,
                   "hours_union": round(union / 3600, 2), "double_booked_hours": round(summed - union / 3600, 2),
                   "by_day": dict(sorted(by_day.items())), "all_meetings_hours_sum": everything},
        "lookahead": {"meetings_in_scope": len(ahead), "hours_sum": round(sum(m["hours"] for m in ahead), 2),
                      "items": strip(ahead)},
        "note": "meeting time, not working time; scope is matched on attendee domains and title patterns"}


def excerpt_of(body, limit=400):
    """The readable head of one message, the quoted tail and signature cut off."""
    kept = []
    for line in str(body or "").splitlines():
        if QUOTE_START.match(line) or re.match(r"^\s*(?:--\s*|__+\s*)$", line):
            break
        kept.append(line)
    return clip(" ".join(" ".join(kept).split()) or " ".join(str(body or "").split()), limit)


def mail_threads(portal, owner, since, until, terms, domains, max_pages, max_threads,
                 max_excerpts, caps, could_not):
    """Received mail in the period that belongs to this scope, grouped into threads on the
    normalised subject (the listing carries no thread id). Whether each is still waiting on the
    owner is read from the thread; a thread waiting on the owner carries a short excerpt."""
    base = {"direction": "received", "since": iso(since), "until": iso(until)}
    found, excluded = {}, 0

    def listing(filters):
        nonlocal excluded
        offset = 0
        for page in range(max(1, max_pages)):
            args = {"entity_type": "email", "filters": filters, "limit": 200}
            if offset:
                args["offset"] = offset
            out = portal.safe_call("list_entities", args)
            if not isinstance(out, dict):
                return
            excluded = max(excluded, int(((out.get("inbox_scope") or {}).get("excluded_by_inbox")) or 0))
            for row in items_of(out):
                yield row
            nxt = out.get("next_offset")
            if not out.get("has_more") or not isinstance(nxt, int) or nxt <= offset:
                return
            offset = nxt
            if page == max_pages - 1:
                caps.append(f"a received-mail listing hit the {max_pages}-page cap and is incomplete")

    for term in terms:
        for row in listing(dict(base, search=term)):
            found.setdefault(str(row.get("id")), row)
    if domains:
        for row in listing(dict(base)):
            if str(row.get("from_address") or "").rsplit("@", 1)[-1].casefold() in domains:
                found.setdefault(str(row.get("id")), row)
    grouped = {}
    for message in found.values():
        subject = str(message.get("subject") or "")
        while REPLY_PREFIX.match(subject):
            subject = REPLY_PREFIX.sub("", subject, count=1)
        grouped.setdefault(" ".join(subject.split()).casefold() or str(message.get("id")), []).append(message)
    threads = []
    for batch in grouped.values():
        batch.sort(key=lambda m: str(m.get("received_at") or ""), reverse=True)
        latest = batch[0]
        threads.append({"id": str(latest.get("id")), "ref": latest.get("_ref") or f"portal://email/{latest.get('id')}",
                        "subject": str(latest.get("subject") or ""),
                        "name": str(latest.get("from_name") or "") or None,
                        "domain": str(latest.get("from_address") or "").rsplit("@", 1)[-1].casefold() or None,
                        "count": len(batch), "latest": str(latest.get("received_at") or "") or None,
                        "priority": min((str(m.get("priority")) for m in batch if m.get("priority")), default=None),
                        "summary": latest.get("summary"), "awaiting_owner": None, "excerpt": None})
    threads.sort(key=lambda t: t["latest"] or "", reverse=True)
    ranked = sorted(threads, key=lambda t: str(t["priority"] or "zz"))
    own = set(owner["addresses"])
    for thread in ranked[:max(0, max_threads)]:
        out = portal.safe_call("get", {"entity_type": "email", "id_or_query": thread["id"]})
        if not isinstance(out, dict):
            continue
        thread["awaiting_owner"] = not any(
            str(m.get("received_at") or "") >= (thread["latest"] or "")
            and str(m.get("direction") or "").casefold() == "sent"
            and (not own or str(m.get("from_address") or "").casefold() in own)
            for m in out.get("thread") or [] if isinstance(m, dict))
    if len(ranked) > max_threads:
        caps.append(f"{len(ranked) - max_threads} threads were not read for awaiting_owner, the cap "
                    f"being {max_threads}; those carry null")
    waiting = [t for t in threads if t["awaiting_owner"]]
    chosen = {t["id"]: t for t in waiting[:max(0, max_excerpts)]}
    ids = list(chosen)
    for start in range(0, len(ids), 10):
        out = portal.safe_call("email_bodies", {"ids": ids[start:start + 10]})
        rows = out if isinstance(out, list) else items_of(out)
        for row in rows:
            thread = chosen.get(str(row.get("id"))) if isinstance(row, dict) else None
            if thread and row.get("body"):
                thread["excerpt"] = excerpt_of(row["body"])
    if len(waiting) > max_excerpts:
        caps.append(f"{len(waiting) - max_excerpts} threads waiting on the owner carry no excerpt, "
                    f"the cap being {max_excerpts}")
    if excluded:
        could_not.append({"what": "the whole message history",
                          "why": f"{excluded} messages were excluded by inbox scope"})
    return threads


def prior_reports(portal, domain_id, wanted):
    """The last reports filed on this scope as notes, newest first, split into their bullets."""
    found = {}
    for prefix in PRIOR_PREFIXES:
        for note in items_of(portal.safe_call("list_entities", {
                "entity_type": "note", "limit": 50,
                "filters": {"entity_type": "domain", "entity_id": domain_id, "search": prefix}})):
            if str(note.get("title") or "").strip().casefold().startswith(prefix.casefold()):
                found.setdefault(str(note.get("id")), note)
    ranked = sorted(found.values(), key=lambda n: str(n.get("created_at") or n.get("updated_at") or ""),
                    reverse=True)[:max(0, wanted)]
    out = []
    for note in ranked:
        full, text = note_body(portal, note)
        when = as_date(full.get("created_at") or note.get("created_at"))
        out.append({"ref": full.get("_ref") or note.get("_ref") or f"portal://note/{note.get('id')}",
                    "title": str(full.get("title") or note.get("title") or ""),
                    "date": when.isoformat() if when else None, "bullets": report_bullets(text[:8000])})
    return out


def matches(pattern, text):
    """A profile's pattern against a subject or title. A pattern that is not a valid regular
    expression is matched as plain text, so one bad entry cannot stop the collect."""
    try:
        return re.search(pattern, str(text or ""), re.IGNORECASE) is not None
    except re.error:
        return str(pattern).casefold() in str(text or "").casefold()


def direct_reports(portal, domain_id, entries, since, until, base_dir):
    """Each direct report's latest update, in whichever form it arrives. One that cannot be
    found comes back with found false and why: "nothing from this person" is itself news."""
    out = []
    for entry in entries:
        row = {"name": entry.get("name"), "reports_on": entry.get("reports_on"),
               "source": entry.get("source") or "none", "found": False, "why": "", "ref": None,
               "title": None, "received": None, "text": ""}
        if entry.get("source") == "mail" and portal:
            sender, pattern = entry.get("sender") or "", entry.get("subject_pattern") or ""
            hits = [m for m in items_of(portal.safe_call("list_entities", {
                        "entity_type": "email", "limit": 50,
                        "filters": {"direction": "received", "since": iso(since), "until": iso(until),
                                    "search": sender}}))
                    if sender in str(m.get("from_address") or "").casefold()
                    and (not pattern or matches(pattern, m.get("subject")))]
            if hits:
                latest = max(hits, key=lambda m: str(m.get("received_at") or ""))
                bodies = portal.safe_call("email_bodies", {"ids": [str(latest.get("id"))]})
                body = next((b.get("body") for b in (bodies if isinstance(bodies, list) else items_of(bodies))
                             if isinstance(b, dict) and b.get("body")), latest.get("summary") or "")
                row.update(found=True, ref=latest.get("_ref") or f"portal://email/{latest.get('id')}",
                           title=latest.get("subject"), received=latest.get("received_at"), text=str(body)[:1200])
            else:
                row["why"] = f"no message from {sender} in the period matched the subject pattern"
        elif entry.get("source") == "note" and portal:
            pattern = entry.get("title_pattern") or ""
            words = " ".join(re.sub(r"[^A-Za-z0-9 ]+", " ", re.sub(r"^\(\?[a-z]+\)", "", pattern)).split())
            hits = [n for n in items_of(portal.safe_call("list_entities", {
                        "entity_type": "note", "limit": 25,
                        "filters": {"entity_type": "domain", "entity_id": domain_id,
                                    "search": words or entry.get("name")}}))
                    if pattern and matches(pattern, n.get("title"))]
            if hits:
                latest = max(hits, key=lambda n: str(n.get("created_at") or n.get("updated_at") or ""))
                full, text = note_body(portal, latest)
                row.update(found=True, ref=full.get("_ref") or latest.get("_ref") or f"portal://note/{latest.get('id')}",
                           title=full.get("title") or latest.get("title"),
                           received=full.get("created_at") or latest.get("created_at"), text=text[:1200])
            else:
                row["why"] = f"no note on this scope has a title matching {pattern!r}"
        elif entry.get("source") == "file":
            glob = entry.get("path_glob") or ""
            target = Path(glob).expanduser()
            if target.is_absolute():
                base, pattern = Path(target.anchor), str(target.relative_to(target.anchor))
            elif str(base_dir or "").strip():
                base, pattern = Path(base_dir).expanduser(), glob
            else:
                row["why"] = f"the update is a file at {glob!r} and no --direct-report-dir was given"
                out.append(row)
                continue
            matches = sorted((p for p in base.glob(pattern) if p.is_file()), key=lambda p: p.stat().st_mtime)
            if matches:
                latest = matches[-1]
                # Cited by its path under the reports folder (--direct-report-dir), or in full when
                # it lies outside it: two people's files can share a name.
                folder = Path(base_dir).expanduser().resolve() if str(base_dir or "").strip() else None
                where = latest.resolve()
                cited = where.relative_to(folder).as_posix() if folder and where.is_relative_to(folder) \
                    else where.as_posix()
                row.update(found=True, ref=f"file://{cited}", title=latest.name,
                           received=datetime.fromtimestamp(latest.stat().st_mtime).date().isoformat(),
                           text=latest.read_text(encoding="utf-8", errors="replace")[:1200])
            else:
                row["why"] = f"no file under {base} matches {glob!r}"
        else:
            row["why"] = "the profile does not say where this person's update arrives"
        out.append(row)
    return out


def portal_ledger(args):
    from _portal import Portal

    portal, started = Portal(), time.monotonic()
    now = datetime.now(timezone.utc)
    caps, warnings, could_not = [], [], [dict(c) for c in COULD_NOT]
    owner = owner_of(portal)
    warnings += owner["warnings"]
    since, until = resolve_period(args.since, args.until, owner["tz"], now)
    if args.lookahead_days < 0:
        raise Fail("--lookahead-days cannot be negative")
    ahead = until + timedelta(days=args.lookahead_days)
    scope = resolve_domain(portal, args.domain)
    domain_id, name = str(scope.get("id") or ""), str(scope.get("name") or scope.get("title") or "")
    term = scope_term_for(name, args.scope_term)
    outline, outline_text = resolve_outline(portal, domain_id, args.outline_file, warnings)
    errors, notes = pf.validate_outline(outline) if outline.get("found") else ([], [])
    outline.update(errors=errors, warnings=notes)
    warnings += [f"outline: {w}" for w in notes] + [f"outline is not valid: {e}" for e in errors]
    signals = meeting_signals(outline.get("meeting_signals"))
    warnings += [f"a meeting title pattern is not a valid regular expression: {p!r}" for p in signals["bad_titles"]]

    goals, _ = portal.page("goal", {"domain_id": domain_id})
    projects, bad_projects = portal.page("project", {"domain_id": domain_id})
    tasks, bad_tasks = portal.page("task", {"domain_id": domain_id})
    if bad_projects or bad_tasks:
        warnings.append(f"the Portal would not serialise {bad_projects} project and {bad_tasks} task "
                        f"row(s); they were stepped over")
    goal_of = {str(g.get("id")): str(g.get("title") or g.get("name") or "") for g in goals}
    lists = task_lists(tasks, since, until, ahead, args.max_tasks, caps)
    required = {str(t.get("project_id")) for rows in lists.values() for t in rows if t.get("project_id")}
    board_caps = []
    board = project_rows(projects, tasks, goals, until, args.max_projects, required, board_caps)
    notes_read, listings = gather_notes(portal, domain_id, [r["project_id"] for r in board], since, until,
                                        term, args.max_project_note_calls, args.max_notes,
                                        args.max_note_chars, caps)
    attached = {a["entity_id"] for n in notes_read for a in n["attached"] if a["entity_type"] == "project"}
    if attached - {r["project_id"] for r in board}:
        board_caps = []
        board = project_rows(projects, tasks, goals, until, args.max_projects, required | attached, board_caps)
    caps += board_caps
    project_name = {r["project_id"]: r["name"] for r in board}
    project_name.update({str(p.get("id")): str(p.get("name") or "") for p in projects})
    meetings, calendar = calendar_block(portal, owner, since, until, ahead, signals, term, warnings)
    domains = sorted(set(signals["domains"]) | {
        c.casefold().lstrip("@") for cat in outline.get("categories") or []
        for c in (cat.get("signals") or {}).get("counterparties") or []
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9\-]*(?:\.[A-Za-z0-9\-]+)+", c.lstrip("@"))})
    threads = mail_threads(portal, owner, since, until, [t for t in [term] + signals["terms"] if t],
                           domains, args.max_mail_pages, args.max_threads, args.max_excerpts, caps, could_not)

    items = []
    weights = {"overdue": 3.0, "waiting": 2.0, "due_in_lookahead": 2.0, "created_in_period": 0.5}
    tasks_seen = {}
    for list_name in TASK_LISTS:
        for task in lists[list_name]:
            ident = str(task.get("id"))
            if ident in tasks_seen:
                tasks_seen[ident]["extra"]["lists"].append(list_name)
                tasks_seen[ident]["weight"] += weights[list_name]
                continue
            priority, due = str(task.get("priority") or ""), day_of(parse_time(task.get("due_date") or task.get("deadline")))
            project = str(task.get("project_name") or project_name.get(str(task.get("project_id")), "") or "")
            goal = str(task.get("goal_id") or "")
            detail = "; ".join(p for p in (str(task.get("status") or ""), priority, f"due {due}" if due else "",
                                           f"project {project}" if project else "") if p)
            row = {"source": "work_tracker", "kind": "task", "ref": task.get("_ref") or f"portal://task/{ident}",
                   "title": str(task.get("title") or task.get("name") or ""), "detail": detail,
                   "text": clip(task.get("description"), 400 if list_name != "created_in_period" else 300),
                   "occurred_at": day_of(parse_time(task.get("created_at"))) or due, "hours": None,
                   "counterparties": [str(task.get("task_contact_name") or "")] if task.get("task_contact_name") else [],
                   "projects": [p for p in (project, str(task.get("project_id") or "")) if p],
                   "weight": weights[list_name] + (2.0 if priority.upper() == "P1" else 0.0),
                   "extra": {"id": ident, "lists": [list_name], "priority": priority or None, "due_date": due,
                             "status": task.get("status"), "goals": [g for g in (goal_of.get(goal), goal) if g]}}
            tasks_seen[ident] = row
            items.append(row)
    for r in board:
        items.append({"source": "work_tracker", "kind": "project", "ref": r["_ref"] or f"portal://project/{r['project_id']}",
                      "title": r["name"], "text": "", "occurred_at": None, "hours": None, "counterparties": [],
                      "detail": "; ".join([f"flags {', '.join(r['flags'])}" if r["flags"] else "no flags",
                                           f"{r['open_tasks']} open, {r['waiting_tasks']} waiting, {r['overdue_tasks']} overdue"]),
                      "projects": [r["name"], r["project_id"]], "weight": 1.0 + len(r["flags"]),
                      "extra": {k: r[k] for k in ("flags", "goal", "status", "open_tasks", "waiting_tasks",
                                                  "overdue_tasks", "nearest_due_date", "days_since_activity")}
                      | {"goals": [r["goal"]] if r["goal"] else []}})
    for n in notes_read:
        ids = [a["entity_id"] for a in n["attached"] if a["entity_type"] == "project"]
        items.append({"source": "note", "kind": "note", "ref": n["_ref"] or f"portal://note/{n['id']}",
                      "title": n["title"], "text": n["content"], "occurred_at": n["created_at"], "hours": None,
                      "detail": f"{n['note_type']}; authored {n['created_at']}"
                      + ("" if n["authored_in_period"] else ", edited in the period rather than written in it"),
                      "counterparties": [], "projects": [project_name.get(i, "") for i in ids if project_name.get(i)] + ids,
                      "weight": 2.0 if n["authored_in_period"] else 1.0,
                      "extra": {"id": n["id"], "authored_in_period": n["authored_in_period"],
                                "note_type": n["note_type"], "attached_to": n["attached"]}})
    for t in threads:
        items.append({"source": "mail", "kind": "mail", "ref": t["ref"], "title": t["subject"],
                      "text": t["excerpt"] or t["summary"] or "", "occurred_at": t["latest"], "hours": None,
                      "detail": f"{t['name'] or 'unnamed sender'} at {t['domain']}; {t['count']} messages; "
                                f"latest {t['latest']}; priority {t['priority'] or 'none'}"
                                + ("; awaiting the owner" if t["awaiting_owner"] else ""),
                      "counterparties": [c for c in (t["name"], t["domain"]) if c], "projects": [],
                      "weight": (3.0 if t["awaiting_owner"] else 1.0) + (1.0 if str(t["priority"]).upper() == "P1" else 0.0),
                      "extra": {"id": t["id"], "subject": t["subject"], "awaiting_owner": t["awaiting_owner"],
                                "message_count": t["count"], "priority": t["priority"], "excerpt": t["excerpt"]}})
    for m in meetings:
        items.append({"source": "calendar", "kind": "meeting", "ref": m["ref"], "title": m["title"], "text": "",
                      "occurred_at": m["start_local"], "hours": m["hours"],
                      "detail": f"{m['start_local']}, {m['hours']} hours, {m['attendee_count']} attendees",
                      "counterparties": m["matched_domains"], "projects": [], "weight": m["hours"],
                      "extra": {"attendee_count": m["attendee_count"], "matched_by": m["matched_by"]}})
    found_direct = direct_reports(portal, domain_id, outline.get("direct_reports") or [], since, until,
                                  args.direct_report_dir)
    for row in found_direct:
        if row["found"]:
            items.append({"source": "direct_report", "kind": "direct_report", "ref": row["ref"],
                          "title": str(row["title"] or ""), "text": row["text"], "occurred_at": row["received"],
                          "detail": f"from {row['name']}, received {row['received']}", "hours": None,
                          "counterparties": [row["name"]], "projects": [], "weight": 0.0,
                          "extra": {"reports_on": row["reports_on"]}})
    unique = {}
    for row in items:
        unique.setdefault(row["ref"], row)
    return {
        "schema": SCHEMA, "tier": "portal", "model_driven": False, "generated_at": now_utc(),
        "generator": "report-collect (portal tier)",
        "author": {"scope_kind": "domain", "scope_id": domain_id or None, "scope_name": name,
                   "short_name": term, "scope_ref": scope.get("_ref"),
                   "owner_terms": " ".join(sorted({w.casefold() for a in owner["addresses"]
                                                   for w in re.findall(r"[A-Za-z]{3,}", a.split("@")[0])})),
                   "seats": [s["name"] for s in outline.get("seats") or []]},
        "period": {"since": iso(since), "until": iso(until),
                   "since_local": since.astimezone(owner["tz"]).isoformat(),
                   "until_local": until.astimezone(owner["tz"]).isoformat(), "lookahead_until": iso(ahead),
                   "lookahead_days": args.lookahead_days, "timezone": owner["timezone"],
                   "as_of": (until - timedelta(seconds=1)).astimezone(owner["tz"]).date().isoformat()},
        "outline": outline_block(outline, outline_text),
        "items": list(unique.values()),
        "direct_reports": found_direct,
        "prior_reports": prior_reports(portal, domain_id, args.prior_reports or outline.get("prior_reports")
                                       or pf.DEFAULT_PRIOR_REPORTS),
        "goals": [{"id": str(g.get("id")), "_ref": g.get("_ref"), "title": str(g.get("title") or g.get("name") or ""),
                   "priority": g.get("priority"), "horizon": g.get("horizon"), "status": g.get("status"),
                   "target_value": g.get("target_value"), "current_value": g.get("current_value"),
                   "target_unit": g.get("target_unit")} for g in goals if not g.get("is_archived")],
        "calendar": calendar,
        "provenance": {"caps_applied": caps, "warnings": warnings, "could_not_determine": could_not,
                       "portal_calls": portal.calls, "seconds": round(time.monotonic() - started, 2)},
    }


def main():
    parser = argparse.ArgumentParser(description="Read one author's week into the evidence ledger.")
    parser.add_argument("--tier", choices=TIERS, default="portal", help="which reader collects the week")
    parser.add_argument("--domain", default="", help="the Portal scope's name or uuid (portal tier); "
                                                     "the scope's name (manual tier)")
    parser.add_argument("--since", default="", help="start of the period, YYYY-MM-DD or an ISO instant")
    parser.add_argument("--until", default="", help="end of the period, exclusive")
    parser.add_argument("--lookahead-days", type=int, default=7, help="days past the period read for what is coming")
    parser.add_argument("--outline-file", default="", help="the role profile (or an older outline)")
    parser.add_argument("--from-dir", default="", help="manual tier: the folder to fold in")
    parser.add_argument("--direct-report-dir", default="", help="where a direct report's file update arrives")
    parser.add_argument("--prior-reports", type=int, default=0, help="earlier reports to read; 0 takes the profile's")
    parser.add_argument("--scope-term", default="", help="override the short name searches run on")
    parser.add_argument("--max-tasks", type=int, default=25, help="tasks per list")
    parser.add_argument("--max-projects", type=int, default=25, help="projects kept by pressure, before flagged ones")
    parser.add_argument("--max-notes", type=int, default=40, help="notes read in full, newest first")
    parser.add_argument("--max-note-chars", type=int, default=4000, help="characters of each note kept")
    parser.add_argument("--max-threads", type=int, default=25, help="threads read for awaiting_owner")
    parser.add_argument("--max-excerpts", type=int, default=20, help="waiting threads given an excerpt")
    parser.add_argument("--max-project-note-calls", type=int, default=25, help="projects given a note listing")
    parser.add_argument("--max-mail-pages", type=int, default=20, help="pages per received-mail listing")
    parser.add_argument("--validate", default="", help="check a ledger written by anything, instead of collecting")
    parser.add_argument("--out", default="", help="write the ledger here, compact; stdout without it")
    args = parser.parse_args()

    if args.validate.strip():
        target = Path(args.validate).expanduser()
        try:
            found = json.loads(read_text(target))
        except (OSError, ValueError) as exc:
            raise Fail(f"{target} could not be read as JSON: {type(exc).__name__}") from None
        if not isinstance(found, dict):
            raise Fail(f"{target} is not an evidence ledger: the top level is not an object")
        ledger = normalise(found)
        errors = ledger_errors(ledger)
        print(json.dumps({"file": str(target), "schema": ledger.get("schema"), "tier": ledger.get("tier"),
                          "model_driven": ledger.get("model_driven"), "items": len(ledger.get("items") or []),
                          "valid": not errors, "errors": errors}, indent=1))
        for problem in errors:
            print(safe(f"ledger error: {problem}"), file=sys.stderr)
        if errors:
            return ERROR
        if args.out.strip():
            write_json(args.out, ledger, compact=True)
        return OK

    ledger = (manual_ledger(args.from_dir, args.domain, args.since, args.until, args.outline_file)
              if args.tier == "manual" else portal_ledger(args) if args.tier == "portal" else None)
    if ledger is None:
        raise Fail("the harvester tier is written by the report-harvester worker; check its file with --validate")
    for warning in ledger["provenance"]["warnings"]:
        print(safe(f"warning: {warning}"), file=sys.stderr)
    if args.out.strip():
        path = write_json(args.out, ledger, compact=True)
        print(f"{path} ({len(ledger['items'])} evidence items, tier {ledger['tier']})")
    else:
        print(safe(json.dumps(ledger, indent=1, default=str)))
    return OK


if __name__ == "__main__":
    run_main(main)
