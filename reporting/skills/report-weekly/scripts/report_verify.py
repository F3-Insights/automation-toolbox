#!/usr/bin/env python3
"""report-verify: check a drafted weekly report against the pack it was written from.

Errors (exit 3), which no correct report contains:
  UNKNOWN_REFERENCE         a reference that is not in the pack (portal://, mail://, file://,
                            ledger://, pack://, facts://)
  NEVER_APPEARS             a term the profile's Never published list bars
  UNCITED_COMPLETION_CLAIM  "completed", "marked done" or "closed" with nothing cited
  OVER_LENGTH_CAP           more words than the profile's hard cap

Findings (exit 0), worth a person's eye and possibly right: UNCITED_FIGURE, NOT_IN_CITED_RECORD,
NAME_NOT_IN_PACK, STYLE_EM_DASH, STYLE_EMOJI, TITLE_LINE, MISSING_CATEGORY, EXTRA_HEADER,
CATEGORIES_OUT_OF_ORDER, CATEGORY_COUNT, OTHER_NOT_LAST, BULLET_NO_LABEL, OVER_LENGTH,
UNDER_LENGTH, CARRY_OVER_NOT_ADDRESSED, FIGURE_NOT_CITED_TO_FACTS, FILLER_PHRASE, the facts
tie-out (FIGURE_NOT_IN_FACTS, UNKNOWN_TABLE), and the seven audience-bar findings:
ACTIVITY_HOURS, TRACKER_VOCABULARY, UNRESOLVED_PUBLISHED, IMMATERIAL_FIGURE (skipped, and
said so, when the profile states no materiality threshold), NO_DECISIONS_BLOCK, PERSON_BLAMED
and AUTHOR_TASK_UPDATE. The verifier reports and never rewrites; Gate 3 decides.

owner://gate1, owner://gate2 and owner://questions/<id> are the executive's own answers: a
figure cited to one is not checked against anything.

Prints a text summary, or {errors, findings, stats} with --json. Exit 0 no errors, 3 errors,
2 the check did not run.

Example:
  python3 report_verify.py --report draft.md --pack pack.json --json
"""

import argparse
import json
import re
from pathlib import Path

import _facts as fx
import _profile as pf
from _common import (BOLD_LABEL, CURRENCY, FAILED, HEADING, NUMBER, OK, PERCENT, TITLE_LINE, TOP_BULLET,
                     YEAR, Fail, dates_in,
                     header_of, normalise_number, numbers_in, read_json, readable_figures, refs_in,
                     run_main, safe, strip_refs, term_pattern)

FILLER = ("great progress", "we are pleased", "pleased to report", "on track", "as always",
          "continued strong", "moving forward", "at this time", "it is worth noting", "needless to say",
          "in order to", "going forward", "a lot of work", "hit the ground running", "circle back",
          "touch base", "low-hanging fruit", "deep dive", "robust", "leverage", "synergy", "exciting")
COMPLETION = re.compile(r"(?i)\b(completed|marked done|closed(?:\s+out)?)\b")
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF\U0000FE0F\U00002B00-\U00002BFF]")
PROPER_PAIR = re.compile(r"\b([A-Z][a-z]{1,15})\s+([A-Z][a-z]{1,15})\b")
NAME_STOPLIST = {"next period", "this period", "last period", "weekly report", "open items", "portal note",
                 "not determined", "could not", "no one", "the owner", "action required", "risk register",
                 "due date", "status update", "key risks", "what moved", "decisions needed", "look ahead",
                 "in progress", "not started", "on hold", "meeting time", "wall clock", "double booked",
                 "email draft"}
# Capitalised only because they opened a sentence, ignored only in that position.
OPENERS = set("""did do does was were is are am be been being has have had will would shall should can could
may might must let see note given per with without from at on in into to by as of out up down against
between across around about above below beyond within i my me you your us our much many more most less
few several another other such once again together further finally overall only even just already
nothing none neither either both work working""".split())
STARTERS = set("""the this that these those a an and but for nor or so yet he she they we it there their his
her its no not all both each every some any one two three four five six seven eight nine ten first
second third next last new open closed due over under before after during since until while when where
which what who why how if then because although though however meanwhile also still now today yesterday
tomorrow week month quarter year monday tuesday wednesday thursday friday saturday sunday""".split())

# --- the audience bar: findings, never errors ---------------------------------------------
HOUR = r"\d[\d,]*(?:\.\d+)?\s*(?:-|\s)?\s*hours?"
ACTIVITY_HOURS = re.compile(
    rf"(?i)(?:\bmet\s+for\s+{HOUR}|\bspent\s+{HOUR}|{HOUR}\s+(?:this|last)\s+week\b|{HOUR}[^.]{{0,40}}\bmeetings?\b"
    rf"|\bmeetings?\b[^.]{{0,40}}{HOUR}|\bmeeting\s+hours?\b|\bhours?\s+of\s+meetings?\b"
    r"|\b(?:held|attended|sat\s+through|sat\s+in\s+on)\b[^.]{0,25}\b\d+\s+meetings?\b"
    r"|\b\d+\s+meetings?\b[^.]{0,25}\b(?:this|last)\s+week\b)")
TRACKER_WORDS = ("no next task", "waiting heavy", "waiting-heavy", "stale", "past due", "NO_OWNER",
                 "NO_TASKS", "NO_NEXT_TASK", "STALE_30D", "WAITING_HEAVY")
TRACKER = [(w, re.compile(r"(?<![\w-])" + r"\s+".join(map(re.escape, w.split())) + r"(?![\w-])",
                          0 if w.isupper() else re.IGNORECASE)) for w in TRACKER_WORDS]
TRACKER_FLAGGED = re.compile(r"(?i)(?<![\w-])flagged\s+(?:as\s+|with\s+)?(?:waiting\b|stale\b|past\s+due\b"
                             r"|overdue\b|no[\s_-]next[\s_-]task\b|[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+)")
PENDING_MARK = re.compile(r"(?i)\[\s*pending\b")
UNRESOLVED = ("status is unclear", "not yet confirmed", "we do not know", "not determined")
MONEY = re.compile(r"[$£€]\s?(\d[\d,]*(?:\.\d+)?)\s*(k|m|bn|thousand|million|billion)?\b", re.IGNORECASE)
MONEY_SCALE = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "bn": 1e9, "billion": 1e9}
PATTERN_TOTAL = re.compile(r"(?i)\b(total|totals|totalled|totaled|totalling|totaling|aggregate|in\s+aggregate|"
                           r"combined|altogether|across\s+\w+|recurring|a\s+pattern|each\s+month|per\s+month|"
                           r"so\s+far\s+this)\b")
NOT_MONTH = "january|february|march|april|may|june|july|august|september|october|november|december" \
            "|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
PATTERN_COUNT = re.compile(rf"(?i)\b(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|dozen|several"
                           rf"|\d{{1,4}})\s+(?!(?:{NOT_MONTH})\b)[a-z]{{3,}}")
DECISIONS = re.compile(r"(?i)^\s{0,3}(?:#{1,6}\s*|\*\*|__)?\s*decisions?\s+needed\b")
FAULT = re.compile(r"(?i)(?:\bwaiting\s+(?:on|for)\b|\b(?:is|are|was|were)\s+owed\b|\bowed\s+(?:by|to)\b"
                   r"|\b(?:has|have|had)\s+not\b|\b(?:do|does|did)\s+not\b|\b(?:has|have)\s+yet\s+to\b"
                   r"|\bfail(?:ed|s|ure)\b|\bmissed\b|\bblocked\s+by\b|\bheld\s+up\s+by\b|\bdelay(?:s|ed)?\b"
                   r"|\bmistake\b|\berror\b|\boverdue\s+from\b"
                   r"|['’]s\s+(?:mistake|error|delay|failure|oversight|omission|lapse|backlog|miss)\b)")
NAMEISH = r"[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?"
# A capitalised name governed by a fault phrase: "waiting on <name>", "<name> is owed", "<name> has
# not", "<name>'s error". A pair the pack has never heard of is blamed only in these shapes.
BLAME_TARGET = re.compile(
    rf"(?:(?:waiting\s+(?:on|for)|owed\s+(?:to|by)|blocked\s+by|held\s+up\s+by|overdue\s+from|chasing"
    rf"|pending\s+(?:on|from))\s+(?P<after>{NAMEISH})|(?P<before>{NAMEISH})\s+(?:is|are|was|were)\s+owed\b"
    rf"|(?P<third>{NAMEISH})\s+(?:has|have|had)\s+not\b"
    rf"|(?P<owner>{NAMEISH})['’]s\s+(?:mistake|error|delay|failure|oversight|omission|lapse|backlog|miss)\b)")
NOT_A_NAME = {"The", "This", "That", "We", "Our", "It", "They", "Their", "His", "Her", "Confirmation", "Approval",
              "Sign", "Feedback", "Payment", "Review", "Decision", "Response", "Delivery", "Nothing", "None"}
COMPANY_SUFFIXES = {"ltd", "limited", "inc", "llc", "plc", "gmbh", "group", "holdings", "partners", "bank",
                    "company", "corporation", "corp", "co", "associates", "industries", "systems", "services",
                    "solutions"}
UNDONE = re.compile(
    r"(?i)(?:\b(?:is|are|was|were|remain|remains)\s+(?:still\s+)?(?:owed|outstanding|unanswered|unresolved|undone"
    r"|incomplete|uncompleted|needed)\b|\bstill\s+(?:outstanding|owed|unanswered|unresolved|need|needs|needed)\b"
    r"|\b(?:still|yet)\s+to\s+be\s+[a-z]+|\b(?:has|have|had)\s+(?:still\s+)?(?:not|yet\s+to)\b"
    r"|\bneeds?\s+(?:to\s+be\s+[a-z]+|[a-z]+ing\b)|\bcannot\s+be\s+[a-z]+ed\b|\bawait(?:s|ed|ing)\b"
    r"|\bwaiting\s+(?:on|for)\b|\bowed\s+(?:to|by)\b|\bunanswered\b)")
CONSEQUENCE = re.compile(
    r"(?i)(?:\buntil\b|\bunless\b|\bso\s+that\b|\bin\s+order\s+that\b|\bwhich\s+(?:moves|holds|delays|pushes|slips"
    r"|means|leaves|blocks|stops|prevents|puts|costs|forces|exposes|keeps)\b|\bmeans\s+that\b|\bresults?\s+in\b"
    r"|\bat\s+risk\b|\b(?:holds|held)\s+(?:up\s+)?the\b|\b(?:delays|delayed|blocks|blocked|stops|stopped|prevents"
    r"|prevented|forces|forced|exposes|exposed|slips|slipped|pushes|pushed)\s+the\b)")
OWNER_REF = re.compile(r"owner://(?:gate1|gate2|questions/[A-Za-z0-9_.\-]+)")
PERSON_KEYS = {"names", "counterparties", "attendees", "from_name", "contact", "people"}


# --------------------------------------------------------------------------- reading the pack

def deep_text(node):
    """Every key and value under a node, joined: generous on purpose, the question is only
    whether a number appears in the record at all."""
    if isinstance(node, dict):
        return "\n".join(f"{k}\n{deep_text(v)}" for k, v in node.items())
    if isinstance(node, (list, tuple)):
        return "\n".join(deep_text(v) for v in node)
    return "" if node is None or isinstance(node, bool) else str(node)


def records(pack):
    """{reference: the text of every record that carries it}, plus the pack's own sections."""
    out = {}

    def walk(node):
        if isinstance(node, dict):
            for key in ("ref", "_ref"):
                ref = node.get(key)
                if isinstance(ref, str) and "://" in ref:
                    out[ref] = out.get(ref, "") + "\n" + deep_text(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str):
            for ref in refs_in(node):
                out.setdefault(ref, "")

    walk(pack)
    out["pack://calendar"] = deep_text(pack.get("calendar") or {})
    for key, record in ((pack.get("facts") or {}).get("items") or {}).items():
        out[f"facts://{key}"] = deep_text({"key": key, **(record or {})})
    return out


def resolve(ref, known):
    """The pack reference a draft's reference names, or None. A portal id shortened to its
    first eight characters still resolves. Only the three owner answers resolve as owner://;
    any other owner:// reference is unknown, or it would exempt its line from every check."""
    if ref.startswith("owner://"):
        return ref if OWNER_REF.fullmatch(ref) else None
    if ref in known:
        return ref
    kind, _, ident = ref.partition("://")[2].partition("/")
    if ref.startswith("portal://") and len(ident) == 8:
        return next((k for k in known if k.startswith(f"portal://{kind}/{ident}")), None)
    return None


def names_with_years(pack):
    """Record names carrying a year ("2026 Audit"), masked so the year is not read as a figure."""
    found = {" ".join(r["title"].split()) for r in pack.get("items") or []
             if YEAR.search(str(r.get("title") or "")) and 4 < len(str(r.get("title"))) <= 120}
    return sorted(found, key=len, reverse=True)


def people_in(pack):
    """(names the pack holds as people, names it holds as organisations)."""
    people, organisations = set(), set()

    def person(text):
        body = " ".join(str(text or "").split()).strip(" ,;:.")
        words = body.split()
        if not body or "@" in body or "." in body or len(body) > 60 or not 1 <= len(words) <= 4:
            return ""
        if not body[0].isupper() or words[-1].casefold() in COMPANY_SUFFIXES:
            return ""
        return body

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                values = value if isinstance(value, list) else [value]
                if key in PERSON_KEYS:
                    people.update(p for v in values if isinstance(v, str) and (p := person(v)))
                elif key in ("organisation", "company", "projects", "domains", "scope_name", "short_name"):
                    organisations.update(str(v).strip() for v in values if isinstance(v, str) and v.strip())
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk({k: v for k, v in pack.items() if k != "outline"})
    for row in ((pack.get("outline") or {}).get("names_to_roles") or []) + \
            ((pack.get("direct_reports") or {}).get("items") or []):
        if person(row.get("name")):
            people.add(person(row.get("name")))
    return people, organisations


def is_organisation(pair, organisations):
    low = pair.casefold()
    for org in organisations:
        other = org.casefold()
        if low == other or (other.startswith(low) and other[len(low):len(low) + 1] in (" ", "-", ",")) \
                or re.search(rf"(?<![\w'’-]){re.escape(other)}(?![\w'’-])", low):
            return True
    return any(w.casefold() in COMPANY_SUFFIXES for w in pair.split())


def proper_names(lines):
    """Two capitalised words in a row that look like a person's name, by line number."""
    out = []
    for number, line in lines:
        if HEADING.match(line):
            continue
        for hit in PROPER_PAIR.finditer(line):
            first, second = hit.groups()
            pair = f"{first} {second}"
            if pair.casefold() in NAME_STOPLIST or first.casefold() in STARTERS or second.casefold() in STARTERS:
                continue
            before = line[:hit.start()].rstrip()
            if first.casefold() in OPENERS and (not before or before[-1] in ".!?:;" or before.endswith(("-", "*"))):
                continue
            out.append((number, pair))
    return out


def never_terms(pack):
    """The Never published list as terms to scan for, complete. A pack organised from a role
    profile carries the list report-record refuses on (`outline.never_published`), so the two
    commands check the same terms; an older outline document's free-text field is split into
    its items. No term is dropped for its length: each is matched as a whole phrase, so a long
    one cannot match by accident inside other words."""
    outline = pack.get("outline") or {}
    listed = outline.get("never_published")
    if isinstance(listed, list):
        chunks = [str(t).strip() for t in listed if str(t).strip()]
    else:
        chunks = pf.exclusion_terms(" ".join(c.replace("*", "").split()).strip(" -–")
                                    for c in re.split(r"[.;\n]|,(?=\s*[A-Z])", str(outline.get("never_appears") or "")))
    terms = []
    for chunk in chunks:
        if chunk.casefold() not in (t.casefold() for t in terms):
            terms.append(chunk)
    return terms


def body_words(report):
    text = strip_refs(report)
    return len([w for line in text.splitlines() if not TITLE_LINE.match(line)
                for w in line.split() if any(c.isalnum() for c in w)])


def same(text, names):
    body = str(text or "").strip().casefold()
    return bool(body) and any(body == n.casefold() or body in n.casefold() or n.casefold() in body
                              for n in names if n)


# --------------------------------------------------------------------------- the check

def check(report, pack):
    """Every check over one report and one pack. No input or output, so it is testable."""
    errors, findings = [], []

    def add(target, kind, line, text, detail):
        target.append({"kind": kind, "line": line, "text": str(text).strip()[:200], "detail": detail})

    known = records(pack)
    years = names_with_years(pack)
    lines = list(enumerate(report.splitlines(), 1))
    references, figure_lines = 0, 0
    for number, line in lines:
        cited, owner = [], False
        for ref in refs_in(line):
            references += 1
            found = resolve(ref, known)
            if found is None:
                add(errors, "UNKNOWN_REFERENCE", number, line, f"{ref} is not in the pack")
            elif found.startswith("owner://"):
                owner = True
            else:
                cited.append(found)
        readable = readable_figures(line, years)
        figures, dates = numbers_in(readable), dates_in(strip_refs(readable))
        if figures or dates:
            figure_lines += 1
            if not cited and not owner and not TITLE_LINE.match(line):
                add(findings, "UNCITED_FIGURE", number, line, "a figure or a date with no reference on the same line")
        if cited and not owner:
            # A line citing three records is one claim drawn from them, so ANY may carry the figure.
            record = "\n".join(known.get(r, "") for r in cited).casefold()
            held = {normalise_number(h) for p in (NUMBER, CURRENCY, PERCENT) for h in p.findall(record)}
            shown = ", ".join(sorted(cited))
            for value in figures:
                if value not in held:
                    add(findings, "NOT_IN_CITED_RECORD", number, line,
                        f"the figure {value} is in none of the records cited on this line ({shown})")
            for forms in dates:
                if not any(f.casefold() in record for f in forms):
                    add(findings, "NOT_IN_CITED_RECORD", number, line,
                        f"the date {sorted(forms)[0]} is in none of the records cited on this line ({shown})")
        if COMPLETION.search(line) and not cited and not owner:
            add(errors, "UNCITED_COMPLETION_CLAIM", number, line,
                "a completion is claimed with nothing cited; the pack cannot know completions")
        if "—" in line:
            add(findings, "STYLE_EM_DASH", number, line, "an em-dash")
        if EMOJI.search(line):
            add(findings, "STYLE_EMOJI", number, line, "an emoji")

    for term in never_terms(pack):
        pattern = term_pattern(term)
        for index, (number, line) in enumerate(lines):
            window = line + ("\n" + lines[index + 1][1] if index + 1 < len(lines) else "")
            hit = pattern.search(window)
            if hit and hit.start() <= len(line):
                add(errors, "NEVER_APPEARS", number, line, f"the profile's Never published list bars {term!r}")

    blob = deep_text(pack).casefold()
    headings = {h.casefold() for _, l in lines if (h := header_of(l))}
    for number, name in proper_names(lines):
        if name.casefold() not in headings and all(w.casefold() not in blob for w in name.split()):
            add(findings, "NAME_NOT_IN_PACK", number, name, f"neither word of {name} appears anywhere in the pack")

    house_errors, house_findings, stats = house_style(report, pack, lines, years)
    errors += house_errors
    findings += house_findings
    findings += table_tie_out(report, pack)
    stats.update({"report_lines": len(lines), "references_seen": references, "lines_with_a_figure": figure_lines,
                  "never_appears_terms": len(never_terms(pack)), "errors": len(errors), "findings": len(findings),
                  "errors_by_kind": tally(errors), "findings_by_kind": tally(findings)})
    return {"errors": errors, "findings": findings, "stats": stats}


def tally(rows):
    out = {}
    for row in rows:
        out[row["kind"]] = out.get(row["kind"], 0) + 1
    return dict(sorted(out.items()))


def table_tie_out(report, pack):
    """The facts tie-out, when the pack names the facts set it was organised with."""
    path = str((pack.get("facts") or {}).get("path") or "")
    if not path or not Path(path).is_file():
        return []
    try:
        return fx.tie_out(report, fx.load_set(path))
    except Fail:
        return []


def house_style(report, pack, lines, years):
    """The checks the profile and the house style add. Only the length cap is an error."""
    errors, findings = [], []
    add = lambda target, kind, line, text, detail: target.append(  # noqa: E731
        {"kind": kind, "line": line, "text": str(text).strip()[:200], "detail": detail})
    categories = [c for c in pack.get("categories") or [] if c.get("name")]
    names = [c["name"] for c in categories]
    outline = pack.get("outline") or {}
    seats = [s.get("name") for s in outline.get("seats") or [] if s.get("name")]
    first = next((l for _, l in lines if l.strip()), "")
    if not TITLE_LINE.match(first):
        add(findings, "TITLE_LINE", 1, first, "the first line is not 'Weekly Highlights - <Department(s)> - <date>'")
    headers = [(n, h) for n, l in lines if (h := header_of(l))]
    matched = [h for _, h in headers if same(h, names)]
    order = [next(i for i, n in enumerate(names) if same(h, [n])) for h in matched]
    if order != sorted(order):
        add(findings, "CATEGORIES_OUT_OF_ORDER", None, ", ".join(matched), "the category headers are not in the profile's order")
    for name in names:
        if not same(name, matched):
            add(findings, "MISSING_CATEGORY", None, name, "the profile names this category and the report has no header for it")
    for number, header in headers:
        if not same(header, names) and not same(header, seats) and not DECISIONS.match(header):
            add(findings, "EXTRA_HEADER", number, header, "a header that is neither a category nor a seat the profile names")
    if names and not 3 <= len(names) <= 7:
        add(findings, "CATEGORY_COUNT", None, f"{len(names)} categories", "a report carries between 3 and 7 categories")
    if categories and categories[-1].get("kind") != "other":
        add(findings, "OTHER_NOT_LAST", None, names[-1], "the last category is not the catch-all, which always comes last")
    elif matched and not same(matched[-1], names[-1:]):
        add(findings, "OTHER_NOT_LAST", None, matched[-1], f"the report's last category header is not {names[-1]!r}")
    bullets = 0
    for number, line in lines:
        hit = TOP_BULLET.match(line)
        if hit and len(hit.group("indent")) <= 1:
            bullets += 1
            if not BOLD_LABEL.match(hit.group("rest").strip()):
                add(findings, "BULLET_NO_LABEL", number, line, "a top-level bullet does not open with a bold topic label")
    length = outline.get("length") or {}
    words, cap = body_words(report), int(length.get("hard_cap_words") or 0)
    low, high = int(length.get("target_words_min") or 0), int(length.get("target_words_max") or 0)
    if cap and words > cap:
        add(errors, "OVER_LENGTH_CAP", None, f"{words} words", f"{words} words against the hard cap of {cap}")
    elif high and words > high:
        add(findings, "OVER_LENGTH", None, f"{words} words", f"{words} words against a target of {low} to {high}")
    elif low and words < low:
        add(findings, "UNDER_LENGTH", None, f"{words} words", f"{words} words against a target of {low} to {high}")
    carries = [x for c in categories for x in c.get("carry_overs") or []] + \
        list((pack.get("continuity") or {}).get("carry_overs_unassigned") or [])
    unanswered = [x for x in carries if str(x.get("label") or "").casefold() not in report.casefold()]
    for x in unanswered:
        add(findings, "CARRY_OVER_NOT_ADDRESSED", None, x.get("label"),
            f"the pack carries {x.get('label')!r} forward from {x.get('report_date') or 'an earlier report'} "
            f"({x.get('reason')}) and the report never names it")
    for key, record in ((pack.get("facts") or {}).get("items") or {}).items():
        value = normalise_number(str((record or {}).get("value") or ""))
        for number, line in lines if len(value) >= 2 else []:
            if f"facts://{key}" not in line and value in numbers_in(readable_figures(line, years)):
                add(findings, "FIGURE_NOT_CITED_TO_FACTS", number, line,
                    f"the figure {value} is the facts set's {key!r} and the line does not cite facts://{key}")
    for number, line in lines:
        for phrase in FILLER:
            if phrase in line.casefold():
                add(findings, "FILLER_PHRASE", number, line, f"{phrase!r} would read the same in any report")
    bar, bar_stats = bar_checks(lines, pack, years)
    findings += bar
    stats = {"categories": len(names), "category_headers_matched": len(matched), "top_level_bullets": bullets,
             "words": words, "word_target": [low, high], "word_cap": cap, "carry_overs_in_pack": len(carries),
             "carry_overs_not_addressed": len(unanswered), **bar_stats}
    return errors, findings, stats


def bar_checks(lines, pack, years):
    """The audience bar. Each finding quotes its line and states the rule; nothing is removed."""
    findings = []
    add = lambda kind, line, text, detail: findings.append(  # noqa: E731
        {"kind": kind, "line": line, "text": str(text).strip()[:200], "detail": detail})
    materiality = (pack.get("outline") or {}).get("materiality") or {}
    threshold, currency = materiality.get("amount"), materiality.get("currency") or ""
    people, organisations = people_in(pack)
    pairs = {}
    for number, pair in proper_names(lines):
        if not is_organisation(pair, organisations):
            pairs.setdefault(number, []).append(pair)
    decisions = False
    for number, line in lines:
        body = line.strip()
        if not body:
            continue
        if DECISIONS.match(line):
            decisions = True
            continue
        if ACTIVITY_HOURS.search(line):
            add("ACTIVITY_HOURS", number, body, "hours spent, meetings held or attended are never a bullet: how busy "
                                                "the author was is not a reason for a leadership reader to know something")
        words = [w for w, p in TRACKER if p.search(line)]
        flagged = TRACKER_FLAGGED.search(line)
        words = ([" ".join(flagged.group(0).split()).casefold()] if flagged else []) + words
        if words:
            add("TRACKER_VOCABULARY", number, body, f"{', '.join(map(repr, words))} describe a record in a work tracker; "
                                                    f"report the consequence instead")
        known = [p for p in sorted(people)
                 if any(re.search(rf"(?<![\w'’-]){re.escape(t)}(?![\w'’-])", body)
                        for t in {p, *(w for w in p.split() if len(w) >= 3)})]
        governed = []
        for match in BLAME_TARGET.finditer(body):
            target = next(g for g in match.groups() if g)
            if target.split()[0] not in NOT_A_NAME and not is_organisation(target, organisations) \
                    and target not in governed:
                governed.append(target)
        named = list(dict.fromkeys(known + governed + [p for p in pairs.get(number, [])
                                                       if any(p == g or p in g or g in p for g in governed)]))
        if named and (governed or FAULT.search(line)):
            add("PERSON_BLAMED", number, body, f"{', '.join(map(repr, named))} is named in a sentence that attaches a "
                                               f"person to a mistake, a delay or an unmet obligation; state the event "
                                               f"without the actor, or name the role")
        if UNDONE.search(line):
            readable = readable_figures(line, years)
            if not (dates_in(readable) or numbers_in(readable) or CONSEQUENCE.search(line)):
                add("AUTHOR_TASK_UPDATE", number, body,
                    "this bullet reports that work has not happened yet and carries nothing a reader acts on: no "
                    "binding date, no figure, no stated consequence")
        phrase = next((p for p in UNRESOLVED if p in line.casefold()), "")
        if PENDING_MARK.search(line) or (phrase and not dates_in(line) and not re.search(r"(?i)\bnot\s+available\b", line)):
            add("UNRESOLVED_PUBLISHED", number, body, f"{'a pending marker' if PENDING_MARK.search(line) else repr(phrase)} "
                                                      f"publishes an unknown; hold it out and ask, or say when it will be known")
        if threshold is not None:
            amounts = [float(v.replace(",", "")) * MONEY_SCALE.get(s.casefold(), 1) for v, s in MONEY.findall(line)]
            small = [a for a in amounts if a < threshold]
            if small and not (any(a >= threshold for a in amounts) or PATTERN_TOTAL.search(line)
                              or PATTERN_COUNT.search(MONEY.sub(" ", line))):
                add("IMMATERIAL_FIGURE", number, body, f"{currency}{min(small):,.2f} is below the materiality threshold of "
                                                       f"{currency}{threshold:,.0f} and stands on its own")
    if not decisions:
        add("NO_DECISIONS_BLOCK", None, "Decisions needed", "the report ends with a 'Decisions needed' block, reading "
                                                            "'None this week.' when there is nothing")
    counted = tally(findings)
    return findings, {"decisions_block": decisions, "people_in_pack": len(people), "materiality_threshold": threshold,
                      "immaterial_check": ("skipped: the profile states no materiality threshold" if threshold is None
                                           else f"run against {currency}{threshold:,.0f}"),
                      **{k.lower(): counted.get(k, 0) for k in ("ACTIVITY_HOURS", "TRACKER_VOCABULARY",
                                                                "UNRESOLVED_PUBLISHED", "IMMATERIAL_FIGURE",
                                                                "PERSON_BLAMED", "AUTHOR_TASK_UPDATE")}}


def as_text(result):
    s = result["stats"]
    lines = ["# Report verify", "",
             f"{s['report_lines']} lines, {s['references_seen']} references, {s['lines_with_a_figure']} lines "
             f"carrying a figure or a date, {s['words']} words.",
             f"{s['errors']} errors, {s['findings']} findings.", f"Immaterial-figure check: {s['immaterial_check']}.",
             "The audience-bar findings are advisory. Nothing is removed from the report; Gate 3 decides."]
    for label, rows in (("Errors", result["errors"]), ("Findings", result["findings"])):
        lines += ["", f"## {label}"] + (["None."] if not rows else [])
        for row in rows:
            lines.append(f"- {row['kind']} ({'line ' + str(row['line']) if row['line'] else 'whole report'}): {row['detail']}")
            lines += [f"    {row['text']}"] if row["text"] else []
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Check a drafted weekly report against its pack.")
    parser.add_argument("--report", required=True, help="the drafted report, Markdown")
    parser.add_argument("--pack", required=True, help="the pack report_organize.py wrote")
    parser.add_argument("--json", action="store_true", help="print {errors, findings, stats} as JSON")
    args = parser.parse_args()
    report = Path(args.report).expanduser()
    if not report.is_file():
        raise Fail(f"no report at {report}")
    pack = read_json(args.pack, "pack")
    if not isinstance(pack, dict):
        raise Fail(f"{args.pack} does not hold a pack")
    result = check(report.read_text(encoding="utf-8"), pack)
    print(safe(json.dumps(result, indent=1, default=str) if args.json else as_text(result)))
    return FAILED if result["errors"] else OK


if __name__ == "__main__":
    run_main(main)
