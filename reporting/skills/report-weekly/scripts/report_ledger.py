#!/usr/bin/env python3
"""report-ledger: continuity as a ledger, not a look-back window.

Every published report is broken into entries, one per bullet, kept in
<store>/report-ledger.jsonl (--store, else $REPORT_STORE_DIR; there is no default path).
Retrieval is deterministic and age-blind, so something from six weeks, a quarter or a year ago
comes back when this week has to answer it.

Subcommands:
  add         break a published report into entries. A bullet takes the seat of the nearest
              heading naming a declared seat, else --seat. The kind (open_issue,
              pending_decision, dated_expectation, recurring, information) is proposed from a
              closed list of cues; --classification FILE (by topic) overrides it with the
              executive's answer. The profile's Never recorded list is redacted before a line
              is written (--refuse-never-recorded refuses instead, exit 3).
  candidates  every entry this week might have to answer, with why: every open entry, every
              dated expectation falling in or before --as-of, every entry sharing a topic word,
              counterparty or project with this week's --pack or --evidence, and every recurring
              entry whose cycle comes due (including the same week a quarter and a year back)
  answer      record that this cycle was answered; the entry stays open for the next one
  close       close entries; a recurring one is refused (exit 3) unless --retire says the
              recurrence itself is over
  list        the entries, oldest report first (--open, --kind, --seat)

Prints JSON. Exit 0 ok, 2 error, 3 a refusal.

Example:
  python3 report_ledger.py candidates --evidence ledger.json --as-of 2027-11-12 --store ~/reports/finance
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import _profile as pf
from _common import (FAILED, HEADING, OK, STOPWORDS, WORD, Fail, as_date, carry_reasons, emit,
                     expectation_dates, json_or_none, now_utc, redact, report_bullets, run_main,
                     store_dir, today_utc)

SCHEMA = "report-ledger/1"
KINDS = ("open_issue", "pending_decision", "dated_expectation", "recurring", "information")
OPEN_KINDS = ("open_issue", "pending_decision", "dated_expectation")
CYCLES = {"weekly": 7, "monthly": 30, "quarterly": 91, "annual": 365}
CYCLE_WORDS = (("annual", r"\b(annual|annually|each year|every year|year[- ]end)\b"),
               ("quarterly", r"\b(quarterly|each quarter|every quarter|Q[1-4]\b)"),
               ("monthly", r"\b(monthly|each month|every month|month[- ]end)\b"),
               ("weekly", r"\b(weekly|each week|every week|this week)\b"))
# A figure as a report writes one: money, a percentage, a count with a unit, a separated number.
FIGURE = re.compile(r"(?<![\w.])(?:[$£€]\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:k|m|bn|million|billion))?"
                    r"|\d[\d,]*(?:\.\d+)?\s?(?:percent|%)|\d[\d,]*(?:\.\d+)?\s?(?:days?|hours?|weeks?|months?"
                    r"|units?|tickets?|items?)|\d{1,3}(?:,\d{3})+(?:\.\d+)?)(?![\w.])")
DOMAIN = re.compile(r"\b([A-Za-z0-9][A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,})\b")
PROJECT_TAG = re.compile(r"\(Project\)\s*([^.;:,]+)")


def ledger_file(store):
    return store_dir(store) / "report-ledger.jsonl"


def read_entries(store):
    path = ledger_file(store)
    if not path.is_file():
        return []
    out = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                raise Fail(f"{path} line {number} is not JSON; one bad line makes the ledger unreadable") from None
    return out


def write_entries(entries, store):
    path = ledger_file(store)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e, separators=(",", ":")) + "\n" for e in entries), encoding="utf-8")
    return path


def classify(label, text, when):
    """The kind code proposes. A dated expectation binds somebody, so it wins; then an open
    decision; then a problem; then something that comes round again; else information."""
    body = f"{label}: {text}"
    dates = expectation_dates(body, when or today_utc())
    reasons = carry_reasons(label, text)
    cycle = next((name for name, pattern in CYCLE_WORDS if re.search(pattern, body, re.IGNORECASE)), None)
    if dates:
        kind, why = "dated_expectation", f"it names a date, {min(dates).isoformat()}"
    elif "a decision was open" in reasons:
        kind, why = "pending_decision", "a decision was open"
    elif set(reasons) & {"a problem was named", "something was late or slipping", "it was waiting on somebody"}:
        kind, why = "open_issue", "; ".join(r for r in reasons if r != "an expectation was stated")
    elif cycle:
        kind, why = "recurring", f"it names a {cycle} cycle"
    else:
        kind, why = "information", "no cue matched"
    return kind, why, min(dates).isoformat() if dates else None, cycle


def bullets_by_seat(text, seats, default):
    """Each bullet with the seat of the nearest heading naming a declared seat (whole words)."""
    blocks, current = [(default, [])], default
    for line in str(text or "").splitlines():
        hit = HEADING.match(line)
        heading = " ".join(hit.group(2).split()).casefold().strip(" .:") if hit else ""
        found = next((s for s in seats if heading == s.casefold()), None) or next(
            (s for s in seats if heading and re.search(rf"\b{re.escape(s.casefold())}\b", heading)), None)
        if found:
            current = found
            blocks.append((current, []))
        else:
            blocks[-1][1].append(line)
    return [dict(b, seat=seat) for seat, lines in blocks for b in report_bullets("\n".join(lines))]


def add_report(text, date, seat, store, profile="", seats=(), classification="", pack="", source_ref="",
               refuse=False):
    """One published report's text into the ledger; the record's text arrives already redacted."""
    when = as_date(date)
    if not when:
        raise Fail(f"the report date {date!r} is not a date; write it as YYYY-MM-DD")
    chosen = profile or (str(store_dir(store) / "profile.md") if (store_dir(store) / "profile.md").is_file() else "")
    rules = pf.exclusions(chosen)[1]
    warnings = [] if chosen and Path(chosen).expanduser().is_file() else [
        f"no role profile at {chosen or store_dir(store) / 'profile.md'}, so no never-recorded rule was applied"]
    text, hits = redact(text, rules)
    if hits and refuse:
        raise Fail(f"the report trips a never-recorded rule {hits[0]['times']} time(s) and "
                   f"--refuse-never-recorded was given; nothing was written", FAILED)
    declared = list(seats) or pf.seat_names(chosen)
    overrides = {}
    found = json_or_none(Path(classification).expanduser()) if classification else None
    rows = found.get("items") if isinstance(found, dict) else found
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict) and row.get("topic"):
            overrides[str(row["topic"]).casefold()] = row
    category_of = {}
    found = json_or_none(Path(pack).expanduser()) if pack else None
    for category in (found or {}).get("categories") or []:
        for label in list(category.get("prior_labels") or []) + [c.get("label") for c in category.get("carry_overs") or []]:
            category_of.setdefault(str(label).casefold(), category.get("name"))
    fresh = []
    for bullet in bullets_by_seat(text, declared, seat or "unnamed seat"):
        topic, body = bullet["label"], bullet["text"]
        kind, why, due, cycle = classify(topic, body, when)
        override = overrides.get(topic.casefold()) or {}
        if override.get("kind") in KINDS:
            kind, why = override["kind"], str(override.get("kind_reason") or "the executive's answer")
        fresh.append({"schema": SCHEMA, "id": "led-" + hashlib.sha1(
                          f"{when.isoformat()}|{bullet['seat'].casefold()}|{topic.casefold()}".encode()).hexdigest()[:8],
                      "report_date": when.isoformat(), "seat": bullet["seat"],
                      "category": override.get("category") or category_of.get(topic.casefold()),
                      "topic": topic, "text": body, "figures": list(dict.fromkeys(m.strip() for m in FIGURE.findall(body))),
                      "counterparties": sorted({d.casefold() for d in DOMAIN.findall(body)}
                                               | {str(c).casefold() for c in override.get("counterparties") or []}),
                      "projects": sorted({" ".join(p.split()) for p in PROJECT_TAG.findall(body)}
                                         | {str(p) for p in override.get("projects") or []}),
                      "kind": kind, "kind_reason": why, "kind_source": "executive" if override.get("kind") else "code",
                      "due_date": override.get("due_date", due),
                      "cycle": override.get("cycle", cycle) if override.get("cycle", cycle) in (None, *CYCLES) else cycle,
                      "last_answered": None, "closed": False, "closed_by": None, "closed_on": None,
                      "retired": False, "source_ref": source_ref or None, "added_at": now_utc()})
    entries, added = {e["id"]: e for e in read_entries(store)}, 0
    for entry in fresh:
        old = entries.get(entry["id"])
        if old:
            entry.update({k: old.get(k) for k in ("closed", "closed_by", "closed_on", "retired", "last_answered",
                                                  "added_at")})
        else:
            added += 1
        entries[entry["id"]] = entry
    path = write_entries(list(entries.values()), store)
    return {"action": "add", "store": str(path), "report_date": when.isoformat(), "bullets": len(fresh),
            "added": added, "updated": len(fresh) - added,
            "by_kind": {k: len([e for e in fresh if e["kind"] == k]) for k in KINDS},
            "seats_declared": declared, "never_recorded": {"rules": len(rules), "redactions": len(hits)},
            "redacted": bool(hits), "entries_total": len(entries), "warnings": warnings}


def cycle_due(entry, as_of):
    """Whether a recurring entry comes round in the week ending as_of."""
    cycle, when = entry.get("cycle"), as_date(entry.get("report_date"))
    if not cycle or not when or cycle not in CYCLES:
        return None
    answered = as_date(entry.get("last_answered"))
    if answered:
        if cycle == "weekly":
            return "it recurs weekly" if (as_of - answered).days >= 7 else None
        if (as_of - answered).days < CYCLES[cycle] - 7:
            return None
    gap = (as_of - when).days
    if gap < 0:
        return None
    if cycle == "weekly":
        return "it recurs weekly"
    turns = max(1, round(gap / CYCLES[cycle]))
    if abs(gap - turns * CYCLES[cycle]) > 7:
        return None
    if turns == 1 and cycle in ("quarterly", "annual"):
        return f"it was reported in the same week one {'quarter' if cycle == 'quarterly' else 'year'} back"
    return f"its {cycle} cycle comes round for the {turns} time since it was reported"


def week_terms(source):
    """This week's topic words, counterparties and projects, from a pack or an evidence ledger."""
    words, parties, projects = set(), set(), set()

    def absorb(title, counterparties=(), named=()):
        words.update(w.casefold() for w in WORD.findall(str(title or ""))
                     if w.casefold() not in STOPWORDS and len(w) >= 4)
        parties.update(str(p).strip().casefold() for p in counterparties if str(p or "").strip())
        projects.update(str(p).strip().casefold() for p in named if str(p or "").strip())

    for category in source.get("categories") or []:
        absorb(category.get("name"))
        for row in category.get("evidence") or []:
            absorb(row.get("title"))
    for row in source.get("items") or []:
        absorb(row.get("title"), list(row.get("counterparties") or []) + list(row.get("domains") or []),
               row.get("projects") or [])
    return {"words": words, "counterparties": parties, "projects": projects}


def candidates(entries, as_of, terms):
    out = []
    for e in entries:
        if e.get("closed"):
            continue
        reasons = [f"it is an open {e['kind'].replace('_', ' ')}"] if e.get("kind") in OPEN_KINDS else []
        due = as_date(e.get("due_date"))
        if due and due <= as_of:
            reasons.append(f"the date it named, {due.isoformat()}, falls in or before this week")
        party = sorted({c.casefold() for c in e.get("counterparties") or []} & terms["counterparties"])
        project = sorted({p.casefold() for p in e.get("projects") or []} & terms["projects"])
        shared = sorted({w.casefold() for w in WORD.findall(e.get("topic") or "")
                         if w.casefold() not in STOPWORDS and len(w) >= 4} & terms["words"])
        if party:
            reasons.append(f"it shares the counterparty {party[0]} with this week's evidence")
        elif project:
            reasons.append(f"it shares the project {project[0]} with this week's evidence")
        elif shared:
            reasons.append(f"its topic shares the term {shared[0]!r} with this week's evidence")
        recurring = cycle_due(e, as_of)
        if recurring:
            reasons.append(recurring)
        if reasons:
            when = as_date(e.get("report_date"))
            out.append({"id": e["id"], "report_date": e.get("report_date"), "report_title": e.get("source_ref"),
                        "seat": e.get("seat"), "category": e.get("category"), "topic": e.get("topic"),
                        "text": e.get("text"), "kind": e.get("kind"), "due_date": e.get("due_date"),
                        "cycle": e.get("cycle"), "figures": e.get("figures") or [], "_ref": f"ledger://{e['id']}",
                        "reason": "; ".join(reasons),
                        "weeks_running": max(1, (as_of - when).days // 7 + 1) if when else None})
    return sorted(out, key=lambda r: (str(r["report_date"]), str(r["topic"])))


def main():
    parser = argparse.ArgumentParser(description="Every published bullet as an entry, retrieved age-blind.")
    sub = parser.add_subparsers(dest="action", required=True)
    add = sub.add_parser("add")
    add.add_argument("--report", required=True, help="the published report, Markdown")
    add.add_argument("--date", default="", help="the report's date, YYYY-MM-DD; today in UTC without it")
    add.add_argument("--seat", default="")
    add.add_argument("--seat-name", action="append", default=[], help="a declared seat; repeatable")
    add.add_argument("--classification", default="", help="JSON of kind overrides by topic")
    add.add_argument("--pack", default="", help="the organised pack, read for each topic's category")
    add.add_argument("--profile", default="", help="the role profile; <store>/profile.md without it")
    add.add_argument("--source-ref", default="")
    add.add_argument("--refuse-never-recorded", action="store_true")
    cand = sub.add_parser("candidates")
    cand.add_argument("--pack", default="", help="this week's organised pack")
    cand.add_argument("--evidence", default="", help="this week's evidence ledger, where there is no pack")
    cand.add_argument("--as-of", default="", help="the last day of the period, YYYY-MM-DD")
    cand.add_argument("--json", action="store_true", help="accepted for compatibility; the output is always JSON")
    for name in ("answer", "close"):
        one = sub.add_parser(name)
        one.add_argument("--id", action="append", required=True, dest="ids")
        one.add_argument("--by", default="")
        one.add_argument("--on", default="", help="YYYY-MM-DD; today in UTC without it")
        if name == "close":
            one.add_argument("--retire", action="store_true", help="the recurrence itself is over")
    listing = sub.add_parser("list")
    listing.add_argument("--open", action="store_true")
    listing.add_argument("--kind", default="", choices=("",) + KINDS)
    listing.add_argument("--seat", default="")
    for one in (add, cand, listing) + tuple(sub.choices[n] for n in ("answer", "close")):
        one.add_argument("--store", default="", help="the author's folder; $REPORT_STORE_DIR without it")
    args = parser.parse_args()

    if args.action == "add":
        report = Path(args.report).expanduser()
        if not report.is_file():
            raise Fail(f"no published report at {report}")
        result = add_report(report.read_text(encoding="utf-8"), args.date or today_utc().isoformat(), args.seat,
                            args.store, args.profile, args.seat_name, args.classification, args.pack,
                            args.source_ref or f"file://{report.name}", args.refuse_never_recorded)
        emit(result)
        for warning in result["warnings"]:
            print(f"warning: {warning}", file=sys.stderr)
        return OK
    entries = read_entries(args.store)
    if args.action == "candidates":
        as_of = as_date(args.as_of) or today_utc()
        source = next((found for given in (args.pack, args.evidence) if given
                       and isinstance(found := json_or_none(Path(given).expanduser()), dict)), None)
        rows = candidates(entries, as_of, week_terms(source or {}))
        warnings = [] if source else ["no pack and no evidence ledger was read, so nothing was retrieved for "
                                      "sharing a topic, counterparty or project with this week"]
        emit({"action": "candidates", "schema": SCHEMA, "as_of": as_of.isoformat(), "entries_read": len(entries),
              "open_entries": len([e for e in entries if not e.get("closed")]), "candidates": rows,
              "count": len(rows), "warnings": warnings})
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)
        return OK
    if args.action == "list":
        rows = [e for e in entries if (not args.open or not e.get("closed")) and (not args.kind or e.get("kind") == args.kind)
                and (not args.seat or str(e.get("seat")).casefold() == args.seat.casefold())]
        emit({"action": "list", "count": len(rows),
              "entries": sorted(rows, key=lambda r: (str(r.get("report_date")), str(r.get("topic"))))})
        return OK
    on = args.on or today_utc().isoformat()
    if not as_date(on):
        raise Fail(f"--on {on!r} is not a date; write it as YYYY-MM-DD")
    wanted = {i.strip() for i in args.ids if i.strip()}
    if args.action == "close" and not args.retire:
        recurring = sorted(e["id"] for e in entries if e["id"] in wanted and e.get("kind") == "recurring"
                           and not e.get("closed"))
        if recurring:
            raise Fail(f"{', '.join(recurring)} recurs, so closing it says the recurrence is over; run `answer` "
                       f"for this cycle, or pass --retire. Nothing was written", FAILED)
    done = []
    for e in entries:
        if e["id"] not in wanted:
            continue
        if args.action == "answer":
            e["last_answered"], e["answered_by"] = on, args.by or "unnamed"
            done.append(e["id"])
        elif not e.get("closed"):
            e.update(closed=True, closed_by=args.by or "unnamed", closed_on=on,
                     retired=bool(args.retire) and e.get("kind") == "recurring")
            done.append(e["id"])
    path = write_entries(entries, args.store)
    emit({"action": args.action, "store": str(path), ("answered" if args.action == "answer" else "closed"): done,
          "not_found": sorted(wanted - {e["id"] for e in entries}), "on": on})
    return OK


if __name__ == "__main__":
    run_main(main)
