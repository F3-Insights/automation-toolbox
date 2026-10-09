"""What the weekly report's scripts share.

Every script in this folder imports this file by name. It holds the small things more than one
command needs: reading owner settings, the author's store folder, dates and periods, JSON files
written safely, the patterns a report line is read with (references, figures, dates, headings
and bullets), the exclusion-list matcher, the carry-over cues, the week folder's file names and
the reader for a comms-confirm request file.

Exit codes are the same in every script: 0 ok, 2 the command could not run, 3 a refusal or a
failed check. A failure prints one line on standard error.
"""

import json
import os
import re
import subprocess
import sys
import tomllib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
OK, ERROR, FAILED = 0, 2, 3


class Fail(Exception):
    """A failure the command reports in one line and exits on (2 by default, 3 a refusal)."""

    def __init__(self, message, code=ERROR):
        super().__init__(message)
        self.code = code


def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


SECRET = re.compile(r"(?i)(bearer\s+\S+|authorization[\"'\s:=]+(?:bearer\s+)?\S+"
                    r"|[?&](?:key|token|api_key|access_token)=[^\s&\"']+)")


def safe(text):
    """Text with anything shaped like a credential taken out, for anything printed."""
    return SECRET.sub("[redacted]", str(text))


def run_main(fn):
    """Run a command's main function and turn a Fail into its one-line message and exit code."""
    try:
        code = fn()
    except Fail as exc:
        print(safe(f"ERROR {exc}" if exc.code == ERROR else f"REFUSED {exc}"), file=sys.stderr)
        sys.exit(exc.code)
    except Exception as exc:  # noqa: BLE001 - an input nobody foresaw still means "could not run": exit 2
        print(safe(f"ERROR {type(exc).__name__}: {exc}"), file=sys.stderr)
        sys.exit(ERROR)
    sys.exit(code or OK)


def emit(data, as_json=True):
    print(safe(json.dumps(data, indent=1, default=str) if as_json else data))


def run_script(name, args, timeout=1800):
    """Run another command of this skill as its own process: (exit code, stdout, stderr)."""
    try:
        done = subprocess.run([sys.executable, str(HERE / f"{name}.py"), *map(str, args)],
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return ERROR, "", f"{name} timed out after {timeout} seconds"
    return done.returncode, done.stdout, done.stderr


def first_line(text):
    return next((line.strip() for line in str(text or "").splitlines() if line.strip()), "")


# --------------------------------------------------------------------------- the store

STORE_ENV = "REPORT_STORE_DIR"


def store_dir(explicit="", must_exist=False):
    """The author's folder: --store, else $REPORT_STORE_DIR. There is no default path."""
    chosen = str(explicit or "").strip() or os.environ.get(STORE_ENV, "").strip()
    if not chosen:
        raise Fail(f"no report store: pass --store <dir> or set {STORE_ENV}; there is no default")
    root = Path(chosen).expanduser()
    if must_exist and not root.is_dir():
        raise Fail(f"no report store at {root}")
    return root


# --------------------------------------------------------------------------- dates

PERIOD = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_utc():
    return datetime.now(timezone.utc).date()


def as_date(value):
    """A stored date or timestamp as a plain date, or None when it is not one."""
    text = str(value or "").strip().replace("Z", "+00:00")
    for attempt in (text, text[:10]):
        try:
            return datetime.fromisoformat(attempt).date()
        except ValueError:
            continue
    return None


def check_period(text, option="--period"):
    """A period end date, YYYY-MM-DD, checked because it also names files."""
    body = str(text or "").strip()
    if not PERIOD.match(body) or as_date(body) is None:
        raise Fail(f"{option} {body!r} is not a date; write it as YYYY-MM-DD")
    return body


def friday_of(day):
    """The period a day belongs to: this week's Friday, or the Friday just past at a weekend."""
    weekday = day.weekday()
    return day + timedelta(days=4 - weekday) if weekday <= 4 else day - timedelta(days=weekday - 4)


def resolve_period(given, today=None):
    if not str(given or "").strip():
        return friday_of(today or date.today()).isoformat()
    return check_period(given)


def week_start(period):
    """The Monday of the period's week, the first day the report covers."""
    end = date.fromisoformat(period)
    return (end - timedelta(days=end.weekday())).isoformat()


# --------------------------------------------------------------------------- files

def read_text(path):
    """A text file, with the byte-order mark a spreadsheet export starts with taken off."""
    return Path(path).expanduser().read_bytes().decode("utf-8").lstrip("\ufeff")


def read_json(path, what="file"):
    target = Path(str(path)).expanduser()
    if not target.is_file():
        raise Fail(f"no {what} at {target}")
    try:
        return json.loads(read_text(target))
    except (OSError, ValueError) as exc:
        raise Fail(f"{target} could not be read as JSON: {type(exc).__name__}") from None


def json_or_none(path):
    try:
        return json.loads(read_text(path))
    except (OSError, ValueError, TypeError, UnicodeDecodeError):
        return None


def write_text(path, text):
    """Write through a temporary file, so a reader never sees half a file."""
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, target)
    return target


def write_json(path, data, compact=False):
    body = (json.dumps(data, separators=(",", ":"), default=str) if compact
            else json.dumps(data, indent=1, default=str) + "\n")
    return write_text(path, body)


def one_line(text, limit=0):
    body = " ".join(str(text or "").split())
    return body[:limit].rstrip() + "…" if limit and len(body) > limit else body


# --------------------------------------------------------------------------- a report line

# Every evidence reference a draft can carry. A trailing full stop or colon belongs to the
# sentence, not to the reference.
REFERENCE = re.compile(r"\b(?:portal|pack|owner|facts|ledger|file|mail|calendar|record)://"
                       r"[^\s\]\)\},;\"'<>]+")
# The bracketed short form a writer sometimes uses: [task/45ba27a9].
SHORT_REFERENCE = re.compile(r"\[(task|project|goal|note|email|calendar_event|contact|company"
                             r"|domain|draft)/([0-9A-Za-z][0-9A-Za-z\-]{3,})\]")


def refs_in(line):
    """Every reference on a line, short forms written out as portal:// references."""
    out = [m.group(0).rstrip(".:") for m in REFERENCE.finditer(str(line))]
    out += [f"portal://{kind}/{ident}" for kind, ident in SHORT_REFERENCE.findall(str(line))]
    return out


def strip_refs(text):
    return SHORT_REFERENCE.sub(" ", REFERENCE.sub(" ", str(text)))


TITLE_LINE = re.compile(r"^\s*#{0,6}\s*\**\s*Weekly Highlights\s*[-–]\s*(.+?)\s*[-–]\s*(.+?)"
                        r"\s*\**\s*$", re.IGNORECASE)
HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
# A whole line in bold is a header too: that is what a report pasted into an email looks like.
BOLD_HEADER = re.compile(r"^\s{0,3}(?:\*\*|__)\s*([^*_\n]{2,80}?)\s*:?\s*(?:\*\*|__)\s*$")
# A top-level bullet (indent of at most one space), and a bullet at any depth.
TOP_BULLET = re.compile(r"^(?P<indent>\s{0,1})(?:[-*+]|\d{1,2}[.)])\s+(?P<rest>.*)$")
ANY_BULLET = re.compile(r"^\s{0,8}(?:[-*+]|\d{1,2}[.)])\s+\S")
BOLD_LABEL = re.compile(r"^\*\*\s*([^*\n]{2,80}?)\s*:?\s*\*\*\s*:?\s+\S")


def header_of(line):
    """The text of a Markdown heading or a bold header line, or None."""
    if TITLE_LINE.match(line):
        return None
    hit = HEADING.match(line)
    if hit:
        return hit.group(2).strip()
    hit = BOLD_HEADER.match(line)
    return hit.group(1).strip() if hit else None


# --------------------------------------------------------------------------- figures and dates

CURRENCY = re.compile(r"[$£€]\s?\d[\d,]*(?:\.\d+)?")
PERCENT = re.compile(r"\d[\d,]*(?:\.\d+)?\s?%")
# The comma in the lookbehind stops a thousands separator starting a second number.
NUMBER = re.compile(r"(?<![\w.,$£€])\d[\d,]*(?:\.\d+)?(?![\w%])")
ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
SLASH_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")
MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december")
MONTH_INDEX = {**{m: i + 1 for i, m in enumerate(MONTHS)},
               **{m[:3]: i + 1 for i, m in enumerate(MONTHS)}, "sept": 9}
TEXT_DATE = re.compile(r"\b(?:(\d{1,2})\s+([A-Za-z]{3,9})|([A-Za-z]{3,9})\.?\s+(\d{1,2}))"
                       r"(?:,?\s+(\d{4}))?\b")
YEAR = re.compile(r"\b(19|20|21)\d{2}\b")
# Things that look like figures and are not: a section's own number, a count bound to a noun
# by a hyphen ("a 12-month term") and a priority label ("P1").
SECTION_NUMBER = re.compile(r"^\s*(?:[-*+]\s*|#{1,6}\s*)?\d{1,2}[.)](?=\s)")
HYPHEN_COUNT = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?-(?=[A-Za-z])")
PRIORITY_LABEL = re.compile(r"(?<![\w])[Pp]\d{1,2}(?![\w])")


def readable_figures(line, names_with_years=()):
    """A line with everything that only looks like a figure taken out.

    A record's own name carrying a year ("2026 Audit") is masked first, then section numbers,
    hyphenated counts and priority labels.
    """
    text = str(line)
    for name in names_with_years:
        text = re.sub(re.escape(name), " ", text, flags=re.IGNORECASE)
    return PRIORITY_LABEL.sub(" ", HYPHEN_COUNT.sub(" ", SECTION_NUMBER.sub(" ", text)))


def normalise_number(text):
    """`$78.93`, `78.93` and `78.930` compare equal; thousands separators and leading zeros go."""
    cleaned = re.sub(r"[^\d.]", "", str(text))
    if not cleaned:
        return ""
    if "." in cleaned:
        whole, fraction = cleaned.split(".", 1)
        fraction = fraction.replace(".", "").rstrip("0")
        whole = whole.lstrip("0") or "0"
        return f"{whole}.{fraction}" if fraction else whole
    return cleaned.lstrip("0") or "0"


def numbers_in(text):
    """Every money amount, percentage and bare number in a line, normalised, dates excluded."""
    body = SLASH_DATE.sub(" ", ISO_DATE.sub(" ", strip_refs(text)))
    out = []
    for pattern in (CURRENCY, PERCENT, NUMBER):
        for hit in pattern.findall(body):
            value = normalise_number(hit)
            if value and value not in out:
                out.append(value)
    return out


def date_forms(year, month, day):
    """Every spelling of one date that counts as the same date."""
    name = MONTHS[month - 1]
    forms = {f"{month:02d}-{day:02d}", f"{month}/{day}", f"{month:02d}/{day:02d}",
             f"{name} {day}", f"{name[:3]} {day}", f"{day} {name}", f"{day} {name[:3]}"}
    if year:
        forms.add(f"{year:04d}-{month:02d}-{day:02d}")
    return forms


def dates_in(text):
    """Every date in a line, each as the set of spellings equal to it."""
    found = [date_forms(int(y), int(m), int(d)) for y, m, d in ISO_DATE.findall(text)]
    for month, day, year in SLASH_DATE.findall(text):
        if 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
            found.append(date_forms(int(year) if len(year) == 4 else None, int(month), int(day)))
    for day_a, month_a, month_b, day_b, year in TEXT_DATE.findall(text):
        name = (month_a or month_b).casefold().rstrip(".")
        month = MONTH_INDEX.get(name) or MONTH_INDEX.get(name[:3])
        day = day_a or day_b
        if month and day and 1 <= int(day) <= 31 and len(name) >= 3:
            found.append(date_forms(int(year) if year else None, month, int(day)))
    return found


# --------------------------------------------------------------------------- exclusion lists

REDACTION = "[redacted: never recorded]"


def term_pattern(term):
    """One exclusion rule as a matcher: whole words, any case, any whitespace between words.

    Whitespace-flexible so a two-word rule still matches when the phrase wraps onto a new line.
    """
    parts = [re.escape(word) for word in str(term).split()]
    return re.compile(rf"(?<!\w){r'\s+'.join(parts)}(?!\w)", re.IGNORECASE) if parts else None


def redaction_pattern(rule):
    """One never-recorded rule as a matcher: the rule as plain text, any case, anywhere, a
    space matching any run of whitespace. Deliberately wider than `term_pattern`: a rule
    barring "Bluejay" takes it out of "Projectbluejay" too, because a near miss kept in the store
    is still a record of the thing the executive said is never kept."""
    parts = [re.escape(word) for word in str(rule).split()]
    return re.compile(r"\s+".join(parts), re.IGNORECASE) if parts else None


def redact(text, rules):
    """The text with every match of every rule replaced, and how often each rule matched.
    Case-insensitive substrings, not whole words (see `redaction_pattern`)."""
    body, hits = str(text or ""), []
    for rule in rules:
        pattern = redaction_pattern(rule)
        if pattern is None:
            continue
        body, count = pattern.subn(REDACTION, body)
        if count:
            hits.append({"rule": str(rule).strip(), "times": count})
    return body, hits


# --------------------------------------------------------------------------- earlier reports

# A top-level bullet in the house style opens with a bold topic label; continuity tracks topics
# by that label.
BULLET_LABEL = re.compile(r"^\s*(?:[-*+•]|\d{1,2}[.)])\s*\*\*\s*(?P<label>[^*\n]{2,80}?)\s*:?\s*"
                          r"\*\*\s*:?\s*(?P<text>.*)$")


def report_bullets(text):
    """A published report split into labelled bullets; sub-bullets fold into their parent."""
    out = []
    for line in str(text or "").splitlines():
        hit = BULLET_LABEL.match(line)
        if hit:
            out.append({"label": " ".join(hit.group("label").split()).strip(" .:"),
                        "text": " ".join(hit.group("text").split())})
        elif line.strip() and out and not HEADING.match(line):
            out[-1]["text"] = f"{out[-1]['text']} {' '.join(line.strip().lstrip('-*+• ').split())}"
    return [row for row in out if row["label"]]


# The closed list of cues that make an earlier bullet something this week has to answer for.
CARRY_CUES = (
    ("a problem was named", re.compile(r"(?i)\b(issue|issues|problem|problems|error|errors|"
                                       r"fail(?:ed|ure|ing)?|short(?:fall|falls)?|breach|"
                                       r"incident|dispute|risk|at risk)\b")),
    ("something was late or slipping", re.compile(r"(?i)\b(delay|delayed|delays|slipp(?:ed|ing|"
                                                  r"age)|behind schedule|overdue|late)\b")),
    ("it was waiting on somebody", re.compile(r"(?i)\b(waiting|awaiting|pending|blocked|on hold|"
                                              r"outstanding|unresolved|not yet)\b")),
    ("a decision was open", re.compile(r"(?i)\b(decision|decide|approval|approve|sign[- ]off|"
                                       r"to be agreed|tbd|to be confirmed)\b")),
    ("an expectation was stated", re.compile(r"(?i)\b(we expect|expected|expects|expect to|due by|"
                                             r"target(?:ed)? for|scheduled for|will be (?:submitted"
                                             r"|delivered|completed|filed))\b")),
)
BY_ISO = re.compile(r"(?i)\bby\s+(\d{4})-(\d{2})-(\d{2})\b")
BY_TEXT = re.compile(r"(?i)\bby\s+(?:(\d{1,2})\s+([A-Za-z]{3,9})|([A-Za-z]{3,9})\.?\s+(\d{1,2}))"
                     r"(?:,?\s+(\d{4}))?\b")


def expectation_dates(text, reference):
    """Every `by <date>` in a bullet. A date with no year takes the report's year, rolled
    forward when that would put it more than half a year before the report."""
    found = []
    for year, month, day in BY_ISO.findall(str(text or "")):
        try:
            found.append(date(int(year), int(month), int(day)))
        except ValueError:
            pass
    for day_a, month_a, month_b, day_b, year in BY_TEXT.findall(str(text or "")):
        name = (month_a or month_b).casefold().rstrip(".")
        month, day = MONTH_INDEX.get(name) or MONTH_INDEX.get(name[:3]), day_a or day_b
        if not month or not day:
            continue
        try:
            when = date(int(year) if year else reference.year, month, int(day))
            if not year and (reference - when).days > 182:
                when = date(reference.year + 1, month, int(day))
            found.append(when)
        except ValueError:
            pass
    return found


def carry_reasons(label, text):
    body = f"{label}: {text}"
    return [name for name, pattern in CARRY_CUES if pattern.search(body)]


STOPWORDS = frozenset("""
a an and are as at be by for from has have in is it its of on or re that the their this to
was were will with you your our we us not no if but so all any can may re fw fwd meeting
call update weekly monthly new please thanks thank regards hi hello team
""".split())
WORD = re.compile(r"[A-Za-z][A-Za-z'\-]{2,}")


# --------------------------------------------------------------------------- the evidence ledger

# The contract between collection and everything after it; report_collect.py writes it and
# report_organize.py reads it, whichever tier collected the week.
LEDGER_SCHEMA = "evidence-ledger/1"
LEDGER_TIERS = ("portal", "harvester", "manual")
ITEM_SOURCES = ("work_tracker", "calendar", "mail", "direct_report", "note", "other")
ITEM_KINDS = ("task", "project", "note", "mail", "meeting", "direct_report")


def ledger_errors(found):
    """Everything wrong with an evidence ledger, as sentences. An empty list is a pass."""
    if not isinstance(found, dict):
        return ["the top level of the file is not an object"]
    errors = []
    if found.get("schema") != LEDGER_SCHEMA:
        errors.append(f"the schema is {found.get('schema')!r}; this reader understands {LEDGER_SCHEMA!r}")
    for key in ("schema", "tier", "generated_at", "generator", "author", "period", "outline",
                "items", "direct_reports", "prior_reports", "provenance"):
        if key not in found:
            errors.append(f"the ledger has no {key!r}")
    if found.get("tier") and found["tier"] not in LEDGER_TIERS:
        errors.append(f"the tier is {found['tier']!r}; it has to be one of {', '.join(LEDGER_TIERS)}")
    author, period = found.get("author"), found.get("period")
    if isinstance(author, dict):
        errors += [f"the author block has no {k!r}" for k in ("scope_kind", "scope_name")
                   if not str(author.get(k) or "").strip()]
    elif "author" in found:
        errors.append("the author block is not an object")
    if isinstance(period, dict):
        errors += [f"the period has no {k!r}" for k in ("since", "until", "timezone")
                   if not str(period.get(k) or "").strip()]
        if str(period.get("since") or "") > str(period.get("until") or "~"):
            errors.append("the period starts after it ends")
    elif "period" in found:
        errors.append("the period block is not an object")
    items = found.get("items")
    if not isinstance(items, list):
        return errors + (["'items' is not a list"] if "items" in found else [])
    seen = {}
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            errors.append(f"item {index} is not an object")
            continue
        ref = str(item.get("ref") or "").strip()
        if not ref:
            errors.append(f"item {index} carries no 'ref', so nothing can cite it")
        seen[ref] = seen.get(ref, 0) + 1
        if item.get("source") not in ITEM_SOURCES:
            errors.append(f"item {index} has source {item.get('source')!r}; it is one of {', '.join(ITEM_SOURCES)}")
        if item.get("kind") not in ITEM_KINDS:
            errors.append(f"item {index} has kind {item.get('kind')!r}; it is one of {', '.join(ITEM_KINDS)}")
        if not str(item.get("title") or "").strip():
            errors.append(f"item {index} carries no title")
    errors += [f"the reference {r!r} appears on {n} items; a reference has to be unique"
               for r, n in sorted(seen.items()) if r and n > 1]
    return errors


def normalise_ledger(found):
    """A ledger somebody else wrote, filled in where the contract has a default. A ledger that
    names no tier was written by a worker, so it is the harvester tier and model-driven."""
    out = dict(found)
    out.setdefault("schema", LEDGER_SCHEMA)
    if not str(out.get("tier") or "").strip():
        out["tier"] = "harvester"
    out.setdefault("model_driven", out["tier"] == "harvester")
    out.setdefault("generated_at", now_utc())
    out.setdefault("generator", "unknown")
    out.setdefault("direct_reports", [])
    out.setdefault("prior_reports", [])
    out.setdefault("outline", {"source": "unknown", "found": False, "note_ref": None, "text": ""})
    provenance = dict(out.get("provenance") or {})
    for key in ("caps_applied", "warnings", "could_not_determine"):
        provenance.setdefault(key, [])
    out["provenance"] = provenance
    return out


# --------------------------------------------------------------------------- the week folder

# Run unattended, a week's working files live in <store>/work/<period>/ under these names.
WORK_DIR = "work"
FILES = {
    "prepare": "prepare.json", "ledger": "ledger.json", "candidates": "candidates.json",
    "facts": "facts.json", "pack": "pack.json", "digest": "digest.md",
    "continuity": "continuity.txt", "editor": "editor.txt", "verdicts": "verdicts.json",
    "questions": "questions.json", "gates": "gates.json", "gates_md": "gates.md",
    "confirmations": "CONFIRMATIONS.md", "answers": "gate-answers.json", "gate1": "gate1.json",
    "owner_input": "owner-input.md", "draft": "draft.md", "approved": "approved.md",
    "log": "LOG.md",
}
GATES_QUESTION = "Weekly report gates"
DRAFT_QUESTION = "Weekly report draft"


def week_dir(store, period):
    return Path(store) / WORK_DIR / period


def week_file(folder, role):
    return Path(folder) / FILES[role]


REQUEST_HEAD = re.compile(r"^## (CR-[0-9a-f]+)\s*$")
REQUEST_FIELD = re.compile(r"^- ([A-Za-z ]+):\s?(.*)$")


def request_for(path, opening):
    """The latest comms-confirm request in a CONFIRMATIONS.md whose question opens so."""
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    requests, current = [], None
    for line in lines:
        head = REQUEST_HEAD.match(line)
        if head:
            current = {"Id": head.group(1)}
            requests.append(current)
            continue
        field = REQUEST_FIELD.match(line)
        if current is not None and field:
            current[field.group(1).strip()] = field.group(2).strip()
    found = [r for r in requests if r.get("Question", "").startswith(opening)]
    return found[-1] if found else None


def request_state(request, today):
    """none, open, past-due, answered or closed."""
    if not request:
        return "none"
    state = request.get("State", "").casefold()
    if state in ("answered", "closed"):
        return state
    due = as_date(request.get("Due", ""))
    return "past-due" if due and today > due else "open"
