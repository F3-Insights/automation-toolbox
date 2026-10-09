"""The role profile and the outline it projects to, read and checked in one place.

The executive edits one Markdown document, the role profile: twelve `## ` sections saying what
the seat answers for, who reads the report, the standing categories (three to seven, the last
the `Other topics` catch-all), the standing metrics, the direct reports, the collection tier,
the form rules, delivery, the two exclusion lists and the review date. `report_profile.py`
validates it.

Every command that sorts the week wants the **outline**: the categories with their signals,
the seats, the leadership team, the length, materiality and exclusion lists. The outline is a
projection of the profile, never a second document: `parse_outline` accepts either a profile
(projected through `outline_text`) or an older hand-written outline document, so
`--outline-file <profile.md>` works and no category list is typed twice.

Assignment lives here too: `assign` puts one piece of evidence into at most one category,
first match in category order, recording the signal that matched. An item that matches nothing
is unassigned and is never folded into the catch-all.
"""

import re
from datetime import date
from pathlib import Path

from _common import STOPWORDS, Fail

KINDS = ("operational", "project", "other")
OTHER_NAME = "Other topics"
MIN_CATEGORIES, MAX_CATEGORIES = 3, 7
DEFAULT_PRIOR_REPORTS = 4
WORDS_MIN, WORDS_MAX, WORDS_CAP, WORDS_PER_PAGE = 450, 600, 1100, 550
TIERS = ("portal", "harvester", "manual")
SOURCE_BY_HAND = "supplied by hand"
CADENCES = ("weekly", "monthly", "quarterly", "annual")
REVIEW_MONTHS = 3
PLACEHOLDER = re.compile(r"<[^<>]*>")

# --------------------------------------------------------------------------- list fields

LIST_ITEM = re.compile(r"^\s*(?:\d{1,2}[.)]|[-*+•])\s+(.*\S)\s*$")


def field_items(value):
    """The items of a field written as a numbered or bulleted list, wrapped lines rejoined.

    A value with no list lines that starts with `1.` is read in its one-line form, `1. a 2. b`.
    """
    items = []
    for line in str(value or "").splitlines():
        hit = LIST_ITEM.match(line)
        if hit:
            items.append(hit.group(1).strip())
        elif line.strip() and items:
            items[-1] = f"{items[-1]} {line.strip()}"
    if items:
        return items
    single = " ".join(str(value or "").split())
    if re.match(r"^\d{1,2}[.)]\s+", single):
        parts = [p.strip() for p in re.split(r"(?:(?<=^)|(?<=\s))\d{1,2}[.)]\s+", single) if p.strip()]
        if len(parts) > 1:
            return parts
    return []


def patterns_in(text):
    """The values inside one signal entry: backticked, slashed (`/x/i`) or comma separated."""
    found = [p.strip() for p in re.findall(r"`([^`]+)`", str(text)) if p.strip()]
    if not found:
        found = [f"(?i){b}" if "i" in f else b for b, f in re.findall(r"/(.+?)/([a-z]*)", str(text))]
    if not found:
        found = [p.strip() for p in re.split(r"[,;]", str(text)) if p.strip()]
    out = []
    for item in found:
        body = item.strip().strip("`").strip()
        hit = re.fullmatch(r"/(.+)/([a-z]*)", body)
        if hit:
            body = f"(?i){hit.group(1)}" if "i" in hit.group(2) else hit.group(1)
        if body and body not in out:
            out.append(body)
    return out


# --------------------------------------------------------------------------- signals

SIGNAL_KEYS = {
    "title": "title_patterns", "titles": "title_patterns", "title pattern": "title_patterns",
    "title patterns": "title_patterns", "subject": "subject_patterns",
    "subjects": "subject_patterns", "subject pattern": "subject_patterns",
    "subject patterns": "subject_patterns", "keyword": "keywords", "keywords": "keywords",
    "project": "projects", "projects": "projects", "goal": "goals", "goals": "goals",
    "counterparty": "counterparties", "counterparties": "counterparties",
    "domain": "counterparties", "domains": "counterparties", "contact": "counterparties",
    "contacts": "counterparties",
}
SIGNAL_FIELDS = ("title_patterns", "subject_patterns", "keywords", "projects", "goals",
                 "counterparties")
# Named things first, patterns after: "this is the ERP project" is a better recorded reason
# than "the word system appeared in the title".
SIGNAL_ORDER = ("projects", "goals", "counterparties", "title_patterns", "subject_patterns",
                "keywords")


def empty_signals():
    return {field: [] for field in SIGNAL_FIELDS}


def key_value(text):
    """`Seat: Finance` as ("seat", "Finance"). A line with no colon has no key."""
    body = str(text or "").strip().lstrip("-*+• ").strip()
    hit = re.match(r"^\*{0,2}\s*([A-Za-z][A-Za-z \-]{0,30}?)\s*\*{0,2}\s*:\s*(.*)$", body)
    return (" ".join(hit.group(1).split()).casefold(), hit.group(2).strip()) if hit else ("", body)


def parse_signals(text, children=()):
    """One category's signals, from the one-line form (`Titles: ...; Keywords: ...`) or one
    child bullet per kind."""
    out = empty_signals()
    for entry in list(children) + " ".join(str(text or "").split()).split(";"):
        key, rest = key_value(entry)
        field = SIGNAL_KEYS.get(key)
        for value in patterns_in(rest) if field and rest else []:
            if value not in out[field]:
                out[field].append(value)
    return out


def keyword_matcher(word):
    """A keyword matches as a whole word or phrase, allowing a simple plural. Written in
    capitals it is an acronym and matched case-sensitively, so `AR` never matches "are"."""
    text = " ".join(str(word or "").split())
    if not text:
        return None
    sensitive = any(c.isalpha() for c in text) and text == text.upper()
    body = r"\s+".join(re.escape(part) for part in text.split(" ")) + r"(?:e?s)?"
    return text, re.compile(r"(?<![0-9A-Za-z_])" + body + r"(?![0-9A-Za-z_])",
                            0 if sensitive else re.IGNORECASE)


def keyword_warning(word):
    """Why a keyword will claim far more than it means, or an empty string."""
    text = " ".join(str(word or "").split())
    if len(text) <= 2 and text == text.casefold():
        return (f"the keyword {text!r} is {len(text)} lower-case character(s) and will match far "
                f"more than it means; write an acronym in capitals or use the longer word")
    if text.casefold() in STOPWORDS:
        return (f"the keyword {text!r} is one of the commonest words in a title, so it will claim "
                f"items from every other category; pair it with a second word")
    return ""


def compile_signals(signals):
    """(the compiled signals, the patterns that would not compile)."""
    signals = signals or {}
    compiled = {
        "title_patterns": [], "subject_patterns": [],
        "keywords": [m for m in (keyword_matcher(k) for k in signals.get("keywords") or []) if m],
        "projects": [p.casefold() for p in signals.get("projects") or []],
        "goals": [g.casefold() for g in signals.get("goals") or []],
        "counterparties": [c.casefold().lstrip("@") for c in signals.get("counterparties") or []],
    }
    broken = []
    for field in ("title_patterns", "subject_patterns"):
        for pattern in signals.get(field) or []:
            try:
                compiled[field].append((pattern, re.compile(pattern, re.IGNORECASE)))
            except re.error:
                broken.append(pattern)
    return compiled, broken


# --------------------------------------------------------------------------- category blocks

BULLET = re.compile(r"^(\s*)(?:\d{1,2}[.)]|[-*+•])\s+(.*\S)\s*$")
METRIC = re.compile(r"^(?P<name>.+?)\s+from\s+[`'\"]?(?P<source>facts:[A-Za-z0-9_.\-]+|owner)"
                    r"[`'\"]?\.?$", re.IGNORECASE)


def bullet_tree(text):
    """A nested bullet list as [(top-level text, [child text, ...])]."""
    rows = []
    for line in str(text or "").splitlines():
        hit = BULLET.match(line)
        if hit:
            rows.append((len(hit.group(1).expandtabs(4)), hit.group(2).strip()))
        elif line.strip() and rows:
            rows[-1] = (rows[-1][0], f"{rows[-1][1]} {line.strip()}")
    if not rows:
        return []
    top, out = min(indent for indent, _ in rows), []
    for indent, body in rows:
        if indent <= top or not out:
            out.append((body, []))
        else:
            out[-1][1].append(body)
    return out


def parse_metrics(text, children=()):
    """`<name> from `facts:<key>`` or `<name> from owner`; anything else has no source."""
    entries = list(children) or [c.strip() for c in " ".join(str(text or "").split()).split(";")
                                 if c.strip()]
    out = []
    for entry in entries:
        hit = METRIC.match(entry.strip().strip("-*+• ").strip())
        if hit:
            source = hit.group("source").casefold()
            out.append({"name": " ".join(hit.group("name").split()).strip(" .:"), "source": source,
                        "facts_key": source.split(":", 1)[1] if source.startswith("facts:") else ""})
    return out


def parse_category(heading, body):
    entry = {"name": " ".join(str(heading).split()), "seat": "", "kind": "", "covers": "",
             "signals": empty_signals(), "standing_metrics": [], "owner": ""}
    for top, children in bullet_tree(body):
        key, rest = key_value(top)
        if key in ("seat", "seats"):
            entry["seat"] = rest
        elif key == "kind":
            entry["kind"] = rest.strip(".").casefold()
        elif key in ("covers", "what it covers"):
            entry["covers"] = rest
        elif key in ("signals", "signal"):
            entry["signals"] = parse_signals(rest, children)
        elif key in ("standing metrics", "standing metric", "metrics"):
            entry["standing_metrics"] = parse_metrics(rest, children)
        elif key == "owner":
            entry["owner"] = rest
    return entry


def parse_categories(text):
    """Every `### Name` block, in the order written."""
    lines = str(text or "").splitlines()
    starts = [(i, m.group(1).strip()) for i, line in enumerate(lines)
              if (m := re.match(r"^\s*#{2,6}\s+(.+?)\s*#*\s*$", line))]
    return [parse_category(head, "\n".join(lines[i + 1:(starts[n + 1][0] if n + 1 < len(starts)
                                                        else len(lines))]))
            for n, (i, head) in enumerate(starts)]


# --------------------------------------------------------------------------- shared readers

def parse_seats(value):
    items = field_items(value) or ([" ".join(str(value).split())] if str(value or "").strip() else [])
    out = []
    for item in items:
        text = item.strip().strip("*").strip()
        name, _, description = text.partition(":")
        if not description.strip():
            name, _, description = text.partition(".")
        if name.strip():
            out.append({"name": " ".join(name.split()).strip("*").strip(),
                        "description": " ".join(description.split())})
    return out


def parse_leadership(value):
    """The leadership team by role and what each answers for; the audience test runs on it."""
    out = []
    for item in field_items(value):
        text = item.strip().strip("*").strip()
        role, _, answers = text.partition(":")
        if not answers.strip():
            role, _, answers = text.partition(",")
        answers = " ".join(answers.split())
        for opener in ("answers for", "owns"):
            if answers.casefold().startswith(opener):
                answers = answers[len(opener):].strip()
        if role.strip():
            out.append({"role": " ".join(role.split()).strip("*").strip(), "answers_for": answers})
    return out


def parse_names_to_roles(value):
    """The optional names map, so a problem sentence can carry the role instead of the person."""
    out = []
    for item in field_items(value):
        text = " ".join(item.split()).strip("*").strip()
        name, _, role = text.partition(":")
        if not role.strip():
            name, _, role = text.partition(",")
        name = name.strip("*").strip()
        if name and not PLACEHOLDER.fullmatch(name):
            out.append({"name": name, "role": " ".join(role.split()).strip(" .")})
    return out


MATERIALITY = re.compile(r"(?P<currency>[$£€])?\s*(?P<value>\d[\d,]*(?:\.\d+)?)\s*"
                         r"(?P<scale>k\b|m\b|bn\b|thousand\b|million\b|billion\b)?", re.IGNORECASE)
SCALE = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "bn": 1e9, "billion": 1e9}


def parse_materiality(value):
    """The amount below which a figure is not reportable on its own. Optional; anything still
    in angle brackets is an unanswered placeholder, not a threshold."""
    text = " ".join(str(value or "").split())
    answered = " ".join(PLACEHOLDER.sub(" ", text).split())
    out = {"text": text if answered else "", "amount": None, "currency": "", "stated": False}
    hit = MATERIALITY.search(answered) if answered else None
    if hit:
        out.update(amount=float(hit.group("value").replace(",", ""))
                   * SCALE.get((hit.group("scale") or "").casefold(), 1),
                   currency=hit.group("currency") or "", stated=True)
    return out


def parse_length(value):
    """A word target and a hard cap. Pages convert at 550 words; a `cap ... N words` wins."""
    text = " ".join(str(value or "").split())
    out = {"text": text, "target_words_min": WORDS_MIN, "target_words_max": WORDS_MAX,
           "hard_cap_words": WORDS_CAP}
    numbers = {"one": 1, "two": 2, "three": 3}
    pages = [numbers.get(p.casefold()) or int(p)
             for p in re.findall(r"(?i)(\d+|one|two|three)\s+pages?", text)]
    span = re.search(r"(?i)(\d[\d,]*)\s*(?:to|-|–)\s*(\d[\d,]*)\s*words", text)
    if span:
        low, high = (int(g.replace(",", "")) for g in span.groups())
        out["target_words_min"], out["target_words_max"] = min(low, high), max(low, high)
    elif pages:
        out["target_words_min"] = max(1, min(pages) - 1) * WORDS_PER_PAGE + 100
        out["target_words_max"] = min(pages) * WORDS_PER_PAGE
    cap = re.search(r"(?i)cap[^.]*?(\d[\d,]*)\s*words", text)
    if cap:
        out["hard_cap_words"] = int(cap.group(1).replace(",", ""))
    elif pages:
        out["hard_cap_words"] = max(pages) * WORDS_PER_PAGE
    out["hard_cap_words"] = max(out["hard_cap_words"], out["target_words_max"])
    return out


def parse_direct_reports(value):
    """Each direct report, what they report on, and where the update arrives: mail from an
    address with a subject pattern, a note titled with a pattern, or a file under a glob."""
    out = []
    for item in field_items(value):
        text = item.strip().strip("*").strip()
        head, _, arrives = text.partition(";")
        name, _, reports = head.partition(",")
        reports = re.sub(r"(?i)^\s*reports on\s+", "", reports).strip()
        entry = {"name": " ".join(name.split()).strip("*").strip(), "reports_on": " ".join(reports.split()),
                 "arrives": " ".join(arrives.split()), "source": "", "sender": "",
                 "subject_pattern": "", "title_pattern": "", "path_glob": ""}
        sender = re.search(r"(?i)mail\s+from\s+[`'\"]?([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+"
                           r"|[A-Za-z0-9.\-]+\.[A-Za-z]{2,})[`'\"]?", arrives)
        note = re.search(r"(?i)note\s+titled\s+(.+)$", arrives)
        glob = re.search(r"(?i)(?:file|path)\s+[`'\"]?([^`'\";\s]+)[`'\"]?", arrives)
        if sender:
            entry["source"], entry["sender"] = "mail", sender.group(1).casefold()
            subject = re.search(r"(?i)subject\s+(?:pattern\s+)?(.+)$", arrives)
            entry["subject_pattern"] = (patterns_in(subject.group(1)) or [""])[0] if subject else ""
        elif note:
            entry["source"], entry["title_pattern"] = "note", (patterns_in(note.group(1)) or [""])[0]
        elif glob:
            entry["source"], entry["path_glob"] = "file", glob.group(1)
        if entry["name"]:
            out.append(entry)
    return out


# --------------------------------------------------------------------------- the outline

OUTLINE_FIELDS = ("Report title", "Author and seats", "Audience and recipients",
                  "Leadership team", "Length", "Materiality", "Names to roles", "Form rules",
                  "Never appears", "Never recorded", "Delivery", "Cadence",
                  "Prior reports to read", "Direct reports", "Meeting signals")
PROFILE_ONLY_FIELDS = ("Leadership team", "Never recorded", "Form rules")


def label_blocks(text, fields):
    """A labelled document as {field: text}, first block per field. Six label shapes are read:
    a table row, `**Field.**`, `**Field**:`, `**Field**` alone, `## Field` and `Field:`."""
    names = "|".join(re.escape(f) for f in fields)
    forms = (
        re.compile(rf"^\s*\|\s*\*{{0,2}}\s*({names})\s*\*{{0,2}}\s*\|\s*(.*?)\s*\|\s*$", re.I),
        re.compile(rf"^\s*(?:[-*+]\s*)?\*\*\s*({names})\s*[.:]\s*\*\*\s*(.*)$", re.I),
        re.compile(rf"^\s*(?:[-*+]\s*)?\*\*\s*({names})\s*\*\*\s*[:.]\s*(.*)$", re.I),
        re.compile(rf"^\s*(?:[-*+]\s*)?\*\*\s*({names})\s*\*\*\s*$", re.I),
        re.compile(rf"^\s*#{{1,6}}\s*({names})\s*:?\s*$", re.I),
        re.compile(rf"^\s*(?:[-*+]\s*)?({names})\s*:\s*(.*)$", re.I),
    )
    found, current = {}, ""
    for line in str(text or "").splitlines():
        hit = next((m for m in (f.match(line) for f in forms) if m), None)
        if hit:
            field = next(f for f in fields if f.casefold() == " ".join(hit.group(1).split()).casefold())
            rest = hit.group(2).strip() if hit.lastindex and hit.lastindex >= 2 else ""
            current = "" if field in found else field
            if current:
                found[field] = [rest] if rest else []
        elif current:
            found[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in found.items()}


def split_categories(text):
    """The document either side of its `## Categories` heading, so a category's own sub-labels
    are never read as the document's fields."""
    lines = str(text or "").splitlines()
    for start, line in enumerate(lines):
        hit = re.match(r"^\s*(#{1,6})\s*(.+?)\s*:?\s*$", line)
        if hit and hit.group(2).strip().casefold() == "categories":
            level = len(hit.group(1))
            end = next((i for i in range(start + 1, len(lines))
                        if (m := re.match(r"^\s*(#{1,6})\s+\S", lines[i])) and len(m.group(1)) <= level),
                       len(lines))
            return "\n".join(lines[:start] + lines[end:]), "\n".join(lines[start + 1:end])
    return str(text or ""), ""


def outline_of_document(text, source="unknown"):
    head, body = split_categories(text)
    fields = label_blocks(head, OUTLINE_FIELDS)
    prior = re.search(r"\d+", fields.get("Prior reports to read", ""))
    return {
        "source": source, "read_as": "outline",
        "report_title": " ".join(fields.get("Report title", "").split()),
        "seats": parse_seats(fields.get("Author and seats", "")),
        "audience": " ".join(fields.get("Audience and recipients", "").split()),
        "leadership_team": parse_leadership(fields.get("Leadership team", "")),
        "length": parse_length(fields.get("Length", "")),
        "materiality": parse_materiality(fields.get("Materiality", "")),
        "names_to_roles": parse_names_to_roles(fields.get("Names to roles", "")),
        "form_rules": [" ".join(i.split()) for i in field_items(fields.get("Form rules", ""))]
        or ([" ".join(fields["Form rules"].split())] if fields.get("Form rules", "").strip() else []),
        "never_appears": fields.get("Never appears", "").strip(),
        "never_recorded": fields.get("Never recorded", "").strip(),
        "delivery": " ".join(fields.get("Delivery", "").split()),
        "cadence": " ".join(fields.get("Cadence", "").split()),
        "prior_reports": min(12, int(prior.group(0))) if prior else DEFAULT_PRIOR_REPORTS,
        "direct_reports": parse_direct_reports(fields.get("Direct reports", "")),
        "meeting_signals": " ".join(fields.get("Meeting signals", "").split()),
        "categories": parse_categories(body),
        "drop_empty_categories": bool(re.search(r"(?i)\bempty categor(?:y|ies)\s+(?:may|can)\s+be"
                                                r"\s+dropped\b|\bdrop\s+empty\s+categor", str(text))),
        "missing_sections": [f for f in PROFILE_ONLY_FIELDS if f not in fields],
    }


def looks_like_a_profile(text):
    """A profile announces itself in its title, or carries two sections no outline has."""
    if re.search(r"(?im)^\s{0,3}#\s*Weekly\s+report\s+profile\b", str(text or "")):
        return True
    blocks, _ = split_sections(text)
    return len([n for n in blocks if n in PROFILE_ONLY_SECTIONS]) >= 2


def parse_outline(text, source="unknown"):
    """An outline document, or a role profile projected through `outline_text`."""
    if looks_like_a_profile(text):
        profile = parse_profile(text, source)
        found = outline_of_document(outline_text(profile), f"{source} (read as a role profile)")
        found["read_as"] = "profile"
        # The exact list report-record refuses on, so report-verify checks the same terms.
        found["never_published"] = exclusion_terms(profile["exclusions"]["never_published"])
        found["profile_sections_missing"] = profile["sections_missing"]
        return found
    return outline_of_document(text, source)


def outline_from_file(path):
    target = Path(str(path)).expanduser()
    if not target.is_file():
        raise Fail(f"no outline or profile at {target}")
    found = parse_outline(target.read_text(encoding="utf-8"), f"outline-file:{target}")
    found.update(found=True, note_ref=None, note_title=None)
    return found


def validate_outline(outline):
    """(errors, warnings) as sentences. An error is something no report can be written from."""
    errors, warnings = [], []
    categories = list(outline.get("categories") or [])
    seats = {str(s.get("name") or "").casefold() for s in outline.get("seats") or []}
    if not MIN_CATEGORIES <= len(categories) <= MAX_CATEGORIES:
        errors.append(f"the outline names {len(categories)} categories; it has to name between "
                      f"{MIN_CATEGORIES} and {MAX_CATEGORIES}, the last of them the catch-all")
    if not seats:
        errors.append("the outline names no seat, so no category can say which seat it belongs to")
    others = [i for i, c in enumerate(categories) if str(c.get("kind") or "") == "other"]
    if not others:
        errors.append("no category has kind 'other'; exactly one does, and it is last")
    elif len(others) > 1:
        errors.append(f"{len(others)} categories have kind 'other'; exactly one does")
    elif others[0] != len(categories) - 1:
        errors.append(f"the 'other' category {categories[others[0]].get('name')!r} is not last")
    seen = set()
    for category in categories:
        name = str(category.get("name") or "").strip()
        if not name:
            errors.append("a category block has no name")
            continue
        if name.casefold() in seen:
            errors.append(f"two categories are both called {name!r}")
        seen.add(name.casefold())
        kind = str(category.get("kind") or "")
        if kind not in KINDS:
            errors.append(f"category {name!r} has kind {kind or '(none)'!r}; it is one of "
                          f"{', '.join(KINDS)}")
        seat = str(category.get("seat") or "").strip()
        if not seat:
            errors.append(f"category {name!r} names no seat")
        elif seats and seat.casefold() not in seats:
            errors.append(f"category {name!r} names the seat {seat!r}, which the outline does not "
                          f"declare")
        compiled, broken = compile_signals(category.get("signals"))
        errors += [f"the signal pattern {p!r} on category {name!r} is not a valid regular "
                   f"expression" for p in broken]
        if kind != "other" and not any(compiled.values()):
            warnings.append(f"category {name!r} carries no signals, so nothing can be assigned to "
                            f"it and it is on the silent list every week")
        if not str(category.get("covers") or "").strip():
            warnings.append(f"category {name!r} does not say what it covers in one line")
    return errors, warnings


# --------------------------------------------------------------------------- assignment

def compile_outline(outline):
    return [dict(name=str(c.get("name") or ""), seat=str(c.get("seat") or ""),
                 kind=str(c.get("kind") or ""), covers=str(c.get("covers") or ""),
                 owner=str(c.get("owner") or ""),
                 standing_metrics=list(c.get("standing_metrics") or []),
                 matchers=compile_signals(c.get("signals"))[0])
            for c in outline.get("categories") or []]


def _hit(matchers, row, field):
    """The signal to record when this kind of signal matches this evidence row, else ''."""
    if field in ("projects", "goals"):
        haystack = [str(v).casefold() for v in row.get(field) or []]
        wanted = next((w for w in matchers[field] if any(w == h or w in h for h in haystack)), None)
        return f"{field[:-1]}:{wanted}" if wanted else ""
    if field == "counterparties":
        names = " ".join(row.get("names") or []).casefold()
        for wanted in matchers["counterparties"]:
            if any(d == wanted or d.endswith("." + wanted) for d in row.get("domains") or []) \
                    or (len(wanted) >= 3 and wanted in names):
                return f"counterparty:{wanted}"
        return ""
    if field == "title_patterns":
        target = row.get("title") or ""
    elif field == "subject_patterns":
        target = row.get("subject") or row.get("title") or ""
    else:
        target = f"{row.get('title') or ''}\n{row.get('subject') or ''}\n{row.get('text') or ''}"
        return next((f"keyword:{w}" for w, p in matchers["keywords"] if p.search(target)), "")
    label = "title" if field == "title_patterns" else "subject"
    return next((f"{label}:{p}" for p, c in matchers[field] if c.search(target)), "")


def assign(categories, row):
    """File one evidence row under at most one category, first match in outline order."""
    for category in categories:
        for field in SIGNAL_ORDER:
            if category["matchers"].get(field):
                signal = _hit(category["matchers"], row, field)
                if signal:
                    row["category"], row["matched_signal"] = category["name"], signal
                    return row
    row["category"], row["matched_signal"] = None, None
    return row


# --------------------------------------------------------------------------- the role profile

PROFILE_SECTIONS = ("Author and organisation", "Seats", "Leadership team", "Standing categories",
                    "Standing metrics", "Direct reports", "Collection tier and scope signals",
                    "Form rules", "Delivery", "Never published", "Never recorded", "Review date")
OPTIONAL_SECTIONS = ("Names to roles",)
PROFILE_ONLY_SECTIONS = ("Author and organisation", "Seats", "Standing metrics",
                         "Collection tier and scope signals", "Never published", "Review date")
ALIASES = {
    "author and organization": "Author and organisation", "author": "Author and organisation",
    "seat": "Seats", "leadership": "Leadership team", "categories": "Standing categories",
    "standing category": "Standing categories", "standing metric": "Standing metrics",
    "metrics": "Standing metrics", "direct report": "Direct reports",
    "collection tier": "Collection tier and scope signals", "form": "Form rules",
    "form rule": "Form rules", "review": "Review date", "review dates": "Review date",
    "names": "Names to roles", "name map": "Names to roles", "names and roles": "Names to roles",
    "names to role": "Names to roles",
}


def canonical_section(heading):
    key = " ".join(re.sub(r"^\s*\d{1,2}[.)]\s*", "", heading).strip().strip(":").split()).casefold()
    return next((n for n in PROFILE_SECTIONS + OPTIONAL_SECTIONS if n.casefold() == key),
                ALIASES.get(key, ""))


def split_sections(text):
    """{section: body} from the `## ` headings, first block per section, fenced code skipped,
    plus the headings that name no section."""
    found, unknown, current, fenced = {}, [], "", False
    for line in str(text or "").splitlines():
        if re.match(r"^\s*(?:```|~~~)", line):
            fenced = not fenced
        hit = None if fenced else re.match(r"^\s{0,3}##\s+(.+?)\s*#*\s*$", line)
        if hit:
            name = canonical_section(hit.group(1))
            if not name:
                unknown.append(" ".join(hit.group(1).split()))
            current = name if name and name not in found else ""
            if current:
                found[current] = []
        elif current:
            found[current].append(line)
    return {n: "\n".join(lines).strip() for n, lines in found.items()}, unknown


KEY_LINE = re.compile(r"^\s{0,4}(?:[-*+•]\s*|\d{1,2}[.)]\s*)?\*{0,2}\s*([A-Za-z][A-Za-z \-]{0,40}?)"
                      r"\s*\*{0,2}\s*:\s*(.*)$")


def key_values(text):
    """The `- Key: value` lines of a flat section; a plain line continues the value above."""
    out, current = {}, ""
    for line in str(text or "").splitlines():
        hit = KEY_LINE.match(line)
        if hit:
            key = " ".join(hit.group(1).split()).casefold()
            current = key if key not in out else ""
            if current:
                out[current] = hit.group(2).strip()
        elif not line.strip() or LIST_ITEM.match(line):
            current = ""
        elif current:
            out[current] = f"{out[current]} {line.strip()}"
    return out


def first(fields, *keys):
    return next((fields[k].strip() for k in keys if str(fields.get(k) or "").strip()), "")


def items_or_sentences(text):
    """A section's list items, or its sentences when it was written as a paragraph."""
    items = [" ".join(i.split()).strip("*").strip() for i in field_items(text)]
    if items:
        return [i for i in items if i]
    return [b for c in re.split(r"[.;\n]", str(text or ""))
            if len(b := " ".join(c.replace("*", "").split()).strip(" -")) >= 3]


def as_iso(value):
    hit = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", str(value or ""))
    try:
        return date(*map(int, hit.groups())).isoformat() if hit else None
    except ValueError:
        return None


def add_months(when, months):
    month = when.month - 1 + months
    year, month = when.year + month // 12, month % 12 + 1
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    return date(year, month, min(when.day, [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31,
                                            30, 31][month - 1]))


def parse_standing_metrics(text):
    """`<name> from `facts:<key>`, weekly` or `<name>, supplied by hand, monthly`."""
    out = []
    for item in [" ".join(i.split()).strip("*").strip() for i in field_items(text)]:
        facts = re.search(r"(?i)(?:\bfrom\s+)?[`'\"]?facts:([A-Za-z0-9_.\-]+)[`'\"]?", item)
        hand = re.search(r"(?i)(?:\bfrom\s+)?\b(?:supplied\s+by\s+hand|by\s+hand|from\s+the\s+owner"
                         r"|from\s+owner|hand\s+supplied)\b", item)
        cut = min([m.start() for m in (facts, hand) if m] + [len(item)])
        cadences = re.findall(r"(?i)\b(weekly|monthly|quarterly|annual(?:ly)?)\b", item)
        cadence = cadences[-1].casefold().replace("annually", "annual") if cadences else ""
        name = re.sub(r"(?i)\s+from$", "", item[:cut].strip(" ,;:.")).strip(" ,;:.")
        if cadence:
            name = re.sub(rf"(?i)[,;]?\s*{cadence}(?:ly)?$", "", name).strip(" ,;:.")
        if name:
            out.append({"name": name, "facts_key": facts.group(1) if facts else "",
                        "source": f"facts:{facts.group(1)}" if facts else (SOURCE_BY_HAND if hand else ""),
                        "cadence": cadence})
    return out


def parse_form(text):
    fields = key_values(text)
    length, cap = first(fields, "length", "length target", "target"), first(fields, "hard cap", "cap", "hard limit")
    deadline = first(fields, "deadline", "deadline day", "due")
    materiality = parse_materiality(first(fields, "materiality", "materiality threshold", "material"))
    span = re.search(r"(?i)(\d[\d,]*)\s*(?:to|-|–)\s*(\d[\d,]*)\s*words", length)
    single = re.search(r"(?i)(\d[\d,]*)\s*words", length)
    cap_words = re.search(r"(?i)(\d[\d,]*)\s*words", cap)
    cap_pages = re.search(r"(?i)(\d+|one|two|three|four)\s+pages?", cap)
    day = re.search(r"(?i)\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", deadline)
    time = re.search(r"(?i)\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)|\d{1,2}:\d{2})\b", deadline)
    keys = {"length", "length target", "target", "hard cap", "cap", "hard limit", "deadline",
            "deadline day", "due", "holiday rule", "holidays", "holiday", "materiality",
            "materiality threshold", "material"}
    rules = [i for i in (" ".join(x.split()) for x in field_items(text))
             if not ((m := KEY_LINE.match(i)) and " ".join(m.group(1).split()).casefold() in keys)]
    return {
        "target_words": int((span.group(2) if span else single.group(1)).replace(",", ""))
        if (span or single) else None,
        "hard_cap_words": int(cap_words.group(1).replace(",", "")) if cap_words else None,
        "hard_cap_pages": ({"one": 1, "two": 2, "three": 3, "four": 4}.get(cap_pages.group(1).casefold())
                           or int(cap_pages.group(1))) if cap_pages else None,
        "materiality_text": materiality["text"], "materiality_amount": materiality["amount"],
        "materiality_currency": materiality["currency"],
        "deadline_day": day.group(1).capitalize() if day else "",
        "deadline_time": time.group(1).strip() if time else "",
        "holiday_rule": first(fields, "holiday rule", "holidays", "holiday"),
        "rules": rules, "length_text": length, "cap_text": cap,
    }


def parse_profile(text, source="unknown"):
    """A role profile into the record every stage reads. A missing section never raises; it is
    empty and named in `sections_missing`, so a half-written profile can still be checked."""
    blocks, unknown = split_sections(text)
    body = lambda name: blocks.get(name, "")  # noqa: E731
    author = key_values(body("Author and organisation"))
    tier_text = first(key_values(body("Collection tier and scope signals")), "tier",
                      "collection tier").casefold()
    named = [t for t in TIERS if re.search(rf"\b{t}\b", tier_text)]
    scope = key_values(body("Collection tier and scope signals"))
    delivery = key_values(body("Delivery"))
    recipients = first(delivery, "recipients", "recipient", "goes to", "to")
    review = key_values(body("Review date"))
    last = as_iso(first(review, "last reviewed", "last review", "last", "reviewed"))
    following = as_iso(first(review, "next review", "next", "next review date"))
    if not following and last:
        following = add_months(date.fromisoformat(last), REVIEW_MONTHS).isoformat()
    return {
        "source": source,
        "author": {"role": first(author, "role", "author", "position", "seat"),
                   "organisation": first(author, "organisation", "organization", "company", "org")},
        "seats": parse_seats(body("Seats")),
        "leadership": parse_leadership(body("Leadership team")),
        "categories": parse_categories(body("Standing categories")),
        "standing_metrics": parse_standing_metrics(body("Standing metrics")),
        "direct_reports": [dict(r, role=r.pop("name")) for r in parse_direct_reports(body("Direct reports"))],
        "tier": named[0] if len(named) == 1 else " ".join(tier_text.split()),
        "scope_signals": {
            "domains": [d.casefold().lstrip("@") for d in patterns_in(
                first(scope, "attendee domains", "domains", "domain", "meeting attendee domains"))],
            "titles": patterns_in(first(scope, "title patterns", "titles", "title", "title pattern")),
            "terms": patterns_in(first(scope, "mail terms", "terms", "keywords", "mail term"))},
        "form": parse_form(body("Form rules")),
        "names_to_roles": parse_names_to_roles(body("Names to roles")),
        "delivery": {"recipients": [r.strip() for r in re.split(r"(?i)\s*(?:,|;|\band\b)\s*", recipients)
                                    if r.strip()] if recipients else field_items(body("Delivery")),
                     "folder": first(delivery, "folder", "file folder", "directory", "path")},
        "exclusions": {"never_published": items_or_sentences(body("Never published")),
                       "never_recorded": items_or_sentences(body("Never recorded"))},
        "review": {"last": last, "next": following},
        "sections_present": [n for n in PROFILE_SECTIONS if n in blocks],
        "sections_missing": [n for n in PROFILE_SECTIONS if n not in blocks],
        "sections_unknown": unknown,
    }


def load_profile(path):
    """(the parsed profile, reading warnings). A missing file is a usage error."""
    target = Path(str(path or "").strip()).expanduser()
    if not str(path or "").strip():
        raise Fail("--profile is required")
    if not target.is_file():
        raise Fail(f"no profile at {target}")
    text = target.read_text(encoding="utf-8")
    profile = parse_profile(text, str(target))
    warnings = [f"{target} is empty"] if not text.strip() else []
    warnings += [f"the heading '## {h}' names no section of a profile, so everything under it is "
                 f"ignored; a relabelled heading reads as a missing section"
                 for h in profile["sections_unknown"]]
    return profile, warnings


def exclusions(path):
    """(never published, never recorded) from a profile, or two empty lists without one."""
    if not str(path or "").strip() or not Path(str(path)).expanduser().is_file():
        return [], []
    found = load_profile(path)[0]["exclusions"]
    return exclusion_terms(found["never_published"]), exclusion_terms(found["never_recorded"])


def exclusion_terms(items):
    """One exclusion list as the terms matched: every item, however long, with a leading
    article taken off ("the Lakeview settlement" bars "Lakeview settlement" too). The verifier
    and the record both read this, so the list that refuses a record is the list that stops a
    draft; no item is dropped for its length, because a long item is matched as a whole phrase."""
    return [re.sub(r"(?i)^(anything|any|no|never|the|a|an)\s+", "", t.strip()) for t in items if t.strip()]


def seat_names(path):
    if not str(path or "").strip() or not Path(str(path)).expanduser().is_file():
        return []
    return [s["name"] for s in load_profile(path)[0]["seats"] if s.get("name")]


# --------------------------------------------------------------------------- the projection

def sentence_case(text):
    body = " ".join(str(text or "").split())
    return body[0].upper() + body[1:] if body[:1].isalpha() and body[:1].islower() else body


def outline_text(profile):
    """The profile as the outline Markdown `outline_of_document` reads back identically."""
    seats = [s["name"] for s in profile.get("seats") or [] if s.get("name")]
    form, delivery = profile.get("form") or {}, profile.get("delivery") or {}
    signals = profile.get("scope_signals") or {}
    title = " and ".join(seats) or (profile.get("author") or {}).get("role") or "the author"
    lines = ["# Weekly report outline", "", f"- **Report title.** Weekly Highlights - {title}",
             "- **Author and seats.**"]
    lines += [f"  {i}. {s['name']}: {' '.join(str(s.get('description') or '').split())}"
              for i, s in enumerate(profile.get("seats") or [], 1)]
    members = [f"{m['role']} (answers for {m['answers_for'].strip(' .')})" if m.get("answers_for")
               else m["role"] for m in profile.get("leadership") or []]
    lines.append(f"- **Audience and recipients.** The leadership team: "
                 f"{'; '.join(members) or 'not stated in the profile'}.")
    if profile.get("leadership"):
        lines.append("- **Leadership team.**")
        lines += [f"  {i}. {m['role']}: answers for {m['answers_for'].strip(' .')}." if m.get("answers_for")
                  else f"  {i}. {m['role']}" for i, m in enumerate(profile["leadership"], 1)]
    length = ". ".join(p.rstrip(".") for p in (sentence_case(form.get("length_text")),
                                               f"Hard cap {form.get('cap_text')}" if form.get("cap_text") else "")
                       if p)
    lines.append(f"- **Length.** {length + '.' if length else 'One page.'}")
    if form.get("materiality_text"):
        lines.append(f"- **Materiality.** {sentence_case(form['materiality_text'])}")
    if profile.get("names_to_roles"):
        lines.append("- **Names to roles.**")
        lines += [f"  {i}. {p['name']}: {p['role']}" if p.get("role") else f"  {i}. {p['name']}"
                  for i, p in enumerate(profile["names_to_roles"], 1)]
    if form.get("rules"):
        lines.append("- **Form rules.**")
        lines += [f"  {i}. {sentence_case(r)}" for i, r in enumerate(form["rules"], 1)]
    sentences = lambda items: " ".join(i if i.endswith(".") else f"{i}." for i in items)  # noqa: E731
    lines.append(f"- **Never appears.** {sentences(profile['exclusions']['never_published'])}")
    if profile["exclusions"]["never_recorded"]:
        lines.append(f"- **Never recorded.** {sentences(profile['exclusions']['never_recorded'])}")
    lines.append(f"- **Delivery.** An email draft to "
                 f"{', '.join(delivery.get('recipients') or []) or 'the recipients the profile names'}, "
                 f"with the file filed in {delivery.get('folder') or 'the folder the profile names'}. "
                 f"Nothing is sent by the automation.")
    cadence = f"Weekly, {form.get('deadline_day') or 'the last working day'}"
    cadence += f" by {form['deadline_time']}" if form.get("deadline_time") else ""
    lines.append(f"- **Cadence.** {cadence}. {sentence_case(form.get('holiday_rule'))}".rstrip())
    lines.append(f"- **Prior reports to read.** {DEFAULT_PRIOR_REPORTS}")
    lines.append("- **Direct reports.**")
    for i, r in enumerate(profile.get("direct_reports") or [], 1):
        item = ", ".join(p for p in (r["role"], f"reports on {r['reports_on']}" if r.get("reports_on") else "") if p)
        lines.append(f"  {i}. {item}; {r['arrives']}" if r.get("arrives") else f"  {i}. {item}")
    meeting = ([f"Domain `{d}`." for d in signals.get("domains") or []]
               + [f"Title pattern `{p}`." for p in signals.get("titles") or []]
               + [f"Mail term `{t}`." for t in signals.get("terms") or []])
    if meeting:
        lines.append(f"- **Meeting signals.** {' '.join(meeting)}")
    lines += ["", "## Categories", ""]
    labels = (("title_patterns", "Titles"), ("subject_patterns", "Subjects"), ("keywords", "Keywords"),
              ("projects", "Projects"), ("goals", "Goals"), ("counterparties", "Counterparties"))
    for c in profile.get("categories") or []:
        lines.append(f"### {c['name']}")
        lines += [f"- Seat: {c['seat']}"] if c.get("seat") else []
        lines.append(f"- Kind: {c.get('kind') or ''}")
        lines += [f"- Covers: {c['covers']}"] if c.get("covers") else []
        written = [f"  - {label}: " + ", ".join(f"`{v}`" for v in c["signals"][field])
                   for field, label in labels if (c.get("signals") or {}).get(field)]
        lines += ["- Signals:"] + written if written else []
        if c.get("standing_metrics"):
            lines.append("- Standing metrics:")
            lines += [f"  - {m['name']} from `{m.get('source') or 'owner'}`" for m in c["standing_metrics"]]
        lines += [f"- Owner: {c['owner']}"] if c.get("owner") else []
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
