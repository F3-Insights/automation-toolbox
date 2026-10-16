#!/usr/bin/env python3
"""calendar-time: where did the owner's meeting time go over a period, and how much of it
belongs to one scope.

Reads the calendar for the window, keeps the rows whose kind is `meeting`, counts and drops
availability blocks, all-day and cancelled ones, collapses the duplicates a cloned recurring
event leaves behind (keeping the copy with the most attendees), and does the arithmetic:
hours summed, hours of wall clock actually occupied (overlaps counted once; the difference is
double booking), hours by day in the owner's timezone, and hours by category when a category
file is given.

An event carries no client or work area, so a scope is matched on what is visible: an
attendee's email domain (the owner's own addresses never count) or a title pattern. Each
in-scope meeting says which put it there; out-of-scope time is a total, never listed. This is
meeting time only: desk work leaves no calendar row, so a small number is not a light week.

Inputs: --since and --until (YYYY-MM-DD, midnight in the owner's timezone, or an ISO instant;
the window is half open; default the last seven full days), --scope-domain, --scope-title,
--exclude-title (each repeatable), --categories (a TOML or JSON file mapping a category name
to a list of title patterns; first match wins), --json, --explain (the item keys the Portal
returned, never values), --config and --server (in place of the settings). Prints a compact table, or JSON; warnings go to stderr. Read only.
Exit 0, or 2 on an error.

Example:
    python3 calendar_time.py --since 2026-09-01 --until 2026-09-08 --scope-domain example.com --json
"""

import argparse
import json
import re
import sys
import tomllib
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import _common as c

DEFAULT_PERIOD_DAYS = 7
UNCATEGORISED = "uncategorised"
NOTES = ("This is meeting time only, not desk work. Anything that left no calendar row is invisible here, so a "
         "small number is not a light week.",
         "Scope matching is a heuristic. An event carries no domain in this Portal, so a meeting is put in scope "
         "by an attendee's email domain or by a title pattern, and the reason is reported per meeting.")


# --------------------------------------------------------------------------- arithmetic

def deduplicate(events):
    """Collapse rows sharing start, end and normalised title, keeping the copy with the most
    attendees (a clone often arrives with its list stripped). Order is kept."""
    best, order, dropped = {}, [], 0
    for e in events:
        seen = best.get(e.key)
        if seen is None:
            best[e.key] = e
            order.append(e.key)
            continue
        dropped += 1
        if len(e.attendees) > len(seen.attendees):
            best[e.key] = e
    return [best[k] for k in order], dropped


def sum_hours(events):
    return round(sum(e.hours for e in events), 2)


def union_hours(events):
    """Wall clock actually occupied, overlapping meetings counted once."""
    spans = c.merge_spans((e.start, e.end) for e in events if e.start and e.end and e.end > e.start)
    return round(sum((end - start).total_seconds() for start, end in spans) / 3600.0, 2)


# --------------------------------------------------------------------------- scope

def compile_patterns(patterns, option):
    out = []
    for text in (str(p or "").strip() for p in patterns):
        if text:
            try:
                out.append((text, re.compile(text, re.IGNORECASE)))
            except re.error as exc:
                raise c.Bad(f"{option} {text!r} is not a valid regular expression: {exc}") from None
    return out


def matches_any(patterns, title):
    return [text for text, rx in patterns if rx.search(title)]


def scope_match(event, domains, title_patterns, own):
    """Why this meeting is in scope, or that it is not. The owner's own address never counts:
    they are on every meeting they hold."""
    hit_domains = []
    for address in event.attendees:
        d = c.domain_of(address)
        if address not in own and d in domains and d not in hit_domains:
            hit_domains.append(d)
    hit_titles = matches_any(title_patterns, event.title)
    reasons = (["attendee_domain"] if hit_domains else []) + (["title"] if hit_titles else [])
    return {"in_scope": bool(reasons), "matched_by": reasons, "matched_domains": hit_domains,
            "matched_titles": hit_titles}


def categorise(event, categories):
    """The first category with a matching pattern, in the file's order, else uncategorised."""
    return next((name for name, patterns in categories if matches_any(patterns, event.title)), UNCATEGORISED)


def load_categories(path):
    chosen = Path(str(path).strip()).expanduser()
    if not chosen.is_file():
        raise c.Bad(f"no categories file at {chosen}")
    text = chosen.read_text(encoding="utf-8")
    try:
        data = json.loads(text) if chosen.suffix.lower() == ".json" else tomllib.loads(text)
    except (ValueError, tomllib.TOMLDecodeError) as exc:
        raise c.Bad(f"{chosen} is not valid {'JSON' if chosen.suffix.lower() == '.json' else 'TOML'}: {exc}") from None
    if not isinstance(data, dict):
        raise c.Bad(f"{chosen} has to hold a mapping of category name to a list of regexes")
    if isinstance(data.get("categories"), dict):
        data = data["categories"]
    out = []
    for name, patterns in data.items():
        patterns = [patterns] if isinstance(patterns, str) else patterns
        if not isinstance(patterns, (list, tuple)):
            raise c.Bad(f"category {name!r} in {chosen} is not a list of regexes")
        out.append((str(name), compile_patterns([str(p) for p in patterns], f"category {name!r}")))
    if not out:
        raise c.Bad(f"{chosen} names no categories")
    return out


# --------------------------------------------------------------------------- owner and period

def owner_profile(portal):
    """The owner's timezone and own addresses. A failure warns: a period reported in UTC is
    still a period, and it says so."""
    warnings, name, addresses = [], "", []
    try:
        who = portal.call("whoami")
    except Exception:
        who = None
        warnings.append("whoami failed: using UTC for day boundaries and treating no address as the owner's own")
    if isinstance(who, dict):
        principal = who.get("principal") if isinstance(who.get("principal"), dict) else {}
        name = str(principal.get("timezone") or "")
        primary = str(principal.get("primary_email") or "").strip().lower()
        if "@" in primary:
            addresses.append(primary)
        for inbox in who.get("inboxes") or []:
            address = str(inbox.get("address") if isinstance(inbox, dict) else inbox or "").strip().lower()
            if "@" in address and address not in addresses:
                addresses.append(address)
    tz, tz_name = timezone.utc, "UTC"
    if name:
        try:
            tz, tz_name = c.ZoneInfo(name), name
        except Exception:
            warnings.append(f"unknown timezone {name!r}: day boundaries computed in UTC")
    elif who is not None:
        warnings.append("whoami returned no principal.timezone: day boundaries computed in UTC")
    if not addresses:
        warnings.append("whoami returned no inbox addresses, so an attendee cannot be told from the owner and a "
                        "scope domain the owner shares will over-match")
    return {"tz": tz, "timezone": tz_name, "addresses": addresses, "warnings": warnings}


def local_midnight(moment, tz):
    return datetime.combine(moment.astimezone(tz).date(), time(0, 0), tzinfo=tz).astimezone(timezone.utc)


def resolve_bound(text, tz, option):
    """A bare date is midnight starting that day in the owner's timezone; an instant is as given."""
    raw = str(text or "").strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            return datetime.combine(date.fromisoformat(raw), time(0, 0), tzinfo=tz).astimezone(timezone.utc)
        found = c.parse_time(raw)
    except ValueError:
        found = None
    if found is None:
        raise c.Bad(f"{option} wants YYYY-MM-DD or an ISO instant, got {raw!r}")
    return found


def resolve_period(since, until, tz, now):
    """Default: the last seven full days, ending at this morning's midnight, so a run at 09:00
    and one at 17:00 report the same week."""
    end = resolve_bound(until, tz, "--until") if str(until).strip() else local_midnight(now, tz)
    start = (resolve_bound(since, tz, "--since") if str(since).strip()
             else local_midnight(end.astimezone(tz) - timedelta(days=DEFAULT_PERIOD_DAYS), tz))
    if start >= end:
        raise c.Bad(f"--since {start.isoformat()} is not before --until {end.isoformat()}")
    return start, end


def key_report(rows):
    """Which keys the Portal put on these items. Keys only, never values."""
    keys, nested = {}, {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key in row:
            keys[str(key)] = keys.get(str(key), 0) + 1
        for entry in row.get("attendees") or []:
            for key in entry if isinstance(entry, dict) else ():
                nested[str(key)] = nested.get(str(key), 0) + 1
    return {"items": len(rows), "keys": dict(sorted(keys.items())), "attendee_keys": dict(sorted(nested.items()))}


# --------------------------------------------------------------------------- the build

def build(rows, since, until, tz, tz_name, own, scope_domains, scope_titles, exclude_titles, categories, unreadable=0):
    """The whole answer from one listing. No I/O and no clock reads."""
    events = [c.Event(row) for row in rows]
    availability = [e for e in events if e.is_availability]
    other_kinds = sorted({e.kind or "(none)" for e in events if not e.is_meeting and not e.is_availability})
    meetings = [e for e in events if e.is_meeting]
    all_day = [e for e in meetings if e.all_day]
    timed = [e for e in meetings if not e.all_day]
    cancelled = [e for e in timed if e.cancelled]
    live = [e for e in timed if not e.cancelled]
    excluded = [e for e in live if matches_any(exclude_titles, e.title)]
    distinct, duplicates = deduplicate([e for e in live if e not in excluded])
    undated = [e for e in distinct if e.start is None or e.end is None or e.hours <= 0]
    domains = [str(d).strip().lower().lstrip("@") for d in scope_domains if str(d).strip()]
    scoped = bool(domains or scope_titles)
    own = {a.lower() for a in own}

    items, in_scope, out_scope = [], [], []
    for e in distinct:
        match = scope_match(e, domains, scope_titles, own)
        if scoped and not match["in_scope"]:
            out_scope.append(e)
            continue
        in_scope.append(e)
        items.append({"start_local": e.start.astimezone(tz).isoformat() if e.start else None,
                      "end_local": e.end.astimezone(tz).isoformat() if e.end else None,
                      "day": e.start.astimezone(tz).date().isoformat() if e.start else None,
                      "hours": round(e.hours, 2), "title": e.title, "matched_by": match["matched_by"],
                      "matched_domains": match["matched_domains"], "matched_titles": match["matched_titles"],
                      "attendee_count": len(e.attendees),
                      "category": categorise(e, categories) if categories else None, "_ref": e.ref or None})
    items.sort(key=lambda r: (r["start_local"] or "", r["title"].lower()))

    by_day = {}
    for e in in_scope:
        if e.start:
            day = e.start.astimezone(tz).date().isoformat()
            by_day[day] = round(by_day.get(day, 0.0) + e.hours, 2)
    by_category = None
    if categories:
        by_category = {name: 0.0 for name, _ in categories}
        by_category[UNCATEGORISED] = 0.0
        for e in in_scope:
            name = categorise(e, categories)
            by_category[name] = round(by_category[name] + e.hours, 2)

    total_sum, total_union = sum_hours(distinct), union_hours(distinct)
    focus_sum, focus_union = sum_hours(in_scope), union_hours(in_scope)
    return {
        "period": {"since": c.iso_z(since), "until": c.iso_z(until), "since_local": since.astimezone(tz).isoformat(),
                   "until_local": until.astimezone(tz).isoformat(),
                   "days": round((until - since).total_seconds() / 86400.0, 2), "timezone": tz_name},
        "scope": {"applied": scoped, "domains": domains, "title_patterns": [t for t, _ in scope_titles],
                  "exclude_patterns": [t for t, _ in exclude_titles],
                  "categories": [name for name, _ in categories] or None},
        "counts": {"rows_read": len(events), "availability_blocks": len(availability), "meetings": len(meetings),
                   "all_day": len(all_day), "cancelled": len(cancelled), "excluded_by_title": len(excluded),
                   "duplicates_collapsed": duplicates, "distinct": len(distinct), "in_scope": len(in_scope),
                   "out_of_scope": len(out_scope), "zero_length": len(undated), "unreadable_rows": unreadable,
                   "other_event_kinds": other_kinds},
        "totals": {"hours_sum": total_sum, "hours_union": total_union,
                   "double_booked_hours": round(total_sum - total_union, 2)},
        "in_scope": {"meetings": len(in_scope), "hours_sum": focus_sum, "hours_union": focus_union,
                     "double_booked_hours": round(focus_sum - focus_union, 2), "by_day": dict(sorted(by_day.items())),
                     "by_category": by_category, "items": items},
        "out_of_scope": {"meetings": len(out_scope), "hours_sum": sum_hours(out_scope),
                         "hours_union": union_hours(out_scope)} if scoped else None,
        "notes": list(NOTES),
    }


def run(portal, since="", until="", scope_domains=(), scope_titles=(), exclude_titles=(), categories_path="", now=None):
    now = now or datetime.now(timezone.utc)
    owner = owner_profile(portal)
    start, end = resolve_period(since, until, owner["tz"], now)
    titles = compile_patterns(scope_titles, "--scope-title")
    excludes = compile_patterns(exclude_titles, "--exclude-title")
    categories = load_categories(categories_path) if str(categories_path).strip() else []
    rows, unreadable = c.page_events(portal, start, end)
    result = build(rows, start, end, owner["tz"], owner["timezone"], owner["addresses"], scope_domains, titles,
                   excludes, categories, unreadable)
    warnings = list(owner["warnings"])
    if unreadable:
        warnings.append(f"the Portal would not serialise {unreadable} calendar row(s); they were stepped over and are "
                        "missing from these totals")
    if result["counts"]["zero_length"]:
        warnings.append(f"{result['counts']['zero_length']} meetings carried no usable start and end and contribute "
                        "zero hours; run --explain and check the keys")
    if result["counts"]["other_event_kinds"]:
        warnings.append("event kinds this command does not know were present and were dropped: "
                        + ", ".join(result["counts"]["other_event_kinds"]))
    if not result["counts"]["distinct"]:
        warnings.append("no meetings survived filtering for this period")
    result["warnings"] = warnings
    result["explain"] = {"calendar_event": key_report(rows)}
    return result


# --------------------------------------------------------------------------- output

def cell(text, width):
    text = " ".join(str(text or "").split()).replace("|", "/")
    return text if len(text) <= width else text[: width - 1] + "…"


def as_markdown(result):
    """A compact table. Titles are the owner's own data; attendee addresses never appear."""
    p, n, t, focus, scope = result["period"], result["counts"], result["totals"], result["in_scope"], result["scope"]
    lines = [f"# Meeting time, {p['since_local'][:10]} to {p['until_local'][:10]} ({p['timezone']})", "",
             f"{n['rows_read']} rows read: {n['availability_blocks']} availability blocks, {n['meetings']} meetings, "
             f"of which {n['all_day']} all day, {n['cancelled']} cancelled, {n['excluded_by_title']} excluded by title "
             f"and {n['duplicates_collapsed']} duplicates collapsed, leaving {n['distinct']} distinct.",
             f"Totals: {t['hours_sum']} hours summed, {t['hours_union']} hours of wall clock, "
             f"{t['double_booked_hours']} hours double booked."]
    if scope["applied"]:
        how = (["attendee domain " + ", ".join(scope["domains"])] if scope["domains"] else []) + \
              (["title " + ", ".join(scope["title_patterns"])] if scope["title_patterns"] else [])
        out = result["out_of_scope"]
        lines += ["", f"In scope ({'; '.join(how)}): {focus['meetings']} meetings, {focus['hours_sum']} hours summed, "
                      f"{focus['hours_union']} hours of wall clock.",
                  f"Out of scope: {out['meetings']} meetings, {out['hours_sum']} hours summed, "
                  f"{out['hours_union']} hours of wall clock. Not listed."]
    if focus["by_day"]:
        lines += ["", "| Day | Hours |", "|-----|------:|"] + [f"| {d} | {h} |" for d, h in focus["by_day"].items()]
    if focus["by_category"]:
        lines += ["", "| Category | Hours |", "|----------|------:|"]
        lines += [f"| {cell(name, 28)} | {h} |" for name, h in focus["by_category"].items()]
    if focus["items"]:
        lines += ["", "| Start | Hrs | Meeting | Matched | Att |", "|-------|----:|---------|---------|----:|"]
        for row in focus["items"]:
            matched = " ".join(row["matched_by"] or ["-"]) + (" " + ",".join(row["matched_domains"]) if row["matched_domains"] else "")
            lines.append(f"| {(row['start_local'] or '')[:16].replace('T', ' ')} | {row['hours']} | "
                         f"{cell(row['title'], 40)} | {cell(matched, 28)} | {row['attendee_count']} |")
    return "\n".join(lines + [""] + list(result["notes"]))


def report(result, as_json, explain):
    for warning in result.get("warnings") or []:
        print(c.safe(f"warning: {warning}"), file=sys.stderr)
    if as_json:
        payload = {k: v for k, v in result.items() if k != "explain"}
        if explain:
            payload["explain"] = result["explain"]
        print(c.safe(json.dumps(payload, indent=1, default=str)))
        return
    print(c.safe(as_markdown(result)))
    if explain:
        for entity, seen in result["explain"].items():
            print(f"keys seen on {entity} items ({seen['items']} read):", file=sys.stderr)
            for key, count in seen["keys"].items():
                print(f"  {key} ({count})", file=sys.stderr)
            for key, count in seen["attendee_keys"].items():
                print(f"  attendees[].{key} ({count})", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Where the owner's meeting time went over a period, optionally "
                                                 "for one scope. Read only. Exit 0, or 2 on an error.")
    parser.add_argument("--since", default="", help="start of the period, YYYY-MM-DD or an ISO instant")
    parser.add_argument("--until", default="", help="end of the period, exclusive")
    parser.add_argument("--scope-domain", dest="scope_domains", action="append", default=[],
                        help="an attendee at this domain, other than the owner, puts a meeting in scope (repeatable)")
    parser.add_argument("--scope-title", dest="scope_titles", action="append", default=[],
                        help="a title matching this regex puts a meeting in scope (repeatable)")
    parser.add_argument("--exclude-title", dest="exclude_titles", action="append", default=[],
                        help="a title matching this regex drops the meeting entirely (repeatable)")
    parser.add_argument("--categories", default="", help="TOML or JSON file: category name to a list of title regexes")
    parser.add_argument("--json", dest="as_json", action="store_true", help="print the whole result as JSON")
    parser.add_argument("--explain", action="store_true", help="also print the item keys the Portal returned")
    parser.add_argument("--config", default="", help="the MCP config holding the Portal (default: the setting)")
    parser.add_argument("--server", default="", help="the server's name in that config (default: the setting)")
    args = parser.parse_args()
    try:
        result = run(c.client(args.config or None, args.server or None), args.since, args.until, args.scope_domains, args.scope_titles, args.exclude_titles,
                     args.categories)
    except (c.Bad, c.Failure) as exc:
        print(c.safe(f"ERROR {exc}"), file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # a period that was not read is an error, never an empty calendar
        print(c.safe(f"ERROR calendar-time could not complete: {type(exc).__name__}: {exc}"), file=sys.stderr)
        sys.exit(2)
    report(result, args.as_json, args.explain)


if __name__ == "__main__":
    main()
