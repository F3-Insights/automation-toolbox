"""What the client-update scripts share: the engagement, its rules, the week and its files, and
the week's evidence file.

THE ENGAGEMENT
    ENGAGEMENT is a Context name or the path to a Context YAML file. A name is looked up as
    <contexts>/<name>.yaml (or .yml), where <contexts> is --contexts-dir, else the owner
    setting contexts_dir in [client-update-workstream], else the top-level contexts_dir. The
    Context lists sources ({name, kind, path}); these scripts use the folders named rules
    (holds UPDATE-RULES.md) and updates (the engagement's update folder), and the background
    source, which says where the engagement context is kept. The pack also reads every folder
    source named engagement or engagement-<anything> (the client folders, read only) and repo
    (a git checkout whose log is a source).

THE RULES
    UPDATE-RULES.md holds "- Key: value" lines under "## Update inputs". These scripts read
    Variant (deck or memo), Update day (default Friday), Week folder (default {week}), Draft
    file, Review note (default "{date} review-notes.md"), Cover email (required for a memo),
    Previous updates, Banned phrases, Banned characters (default U+2014), Slot minutes and
    Engagement context. The pack and the delivery also read Default length (weekly or full),
    Portal domain, Client email domains, Source folders, Never open, Email delivery
    (outlook-drafts or file, default file), Lookback days (21), Catch-up after days (14),
    Catch-up days (30) and Recipients (";"-separated). File names take {date} (the update date) and {week} (yyyy-Www).

THE WEEK
    WEEK is yyyy-Www, a yyyy-mm-dd date in the week, or blank (the week of --as-of, else
    today). The update date is the rules' Update day in that week. The week folder is
    <updates>/<Week folder>, or --week-dir; its work/ folder holds sources.json,
    UPDATE-EVIDENCE.csv, claims.json, CONFIRMATIONS.md, context-proposed.md and the rest.
    The engagement's ledger of open items across weeks is <updates>/UPDATES-LEDGER.csv.

THE WINDOW
    The update covers the time since the last update (the newest earlier update's date). When
    that update is more than Catch-up after days old, it is a catch-up of the most recent
    Catch-up days, never reaching back past the last update. With no earlier update, it covers
    Lookback days.
"""

from __future__ import annotations

import csv
import fnmatch
import io
import json
import os
import re
import sys
import tempfile
import tomllib
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

RULES_MD = "UPDATE-RULES.md"
SOURCES_JSON = "sources.json"
SOURCES_MD = "sources.md"
SOURCES_A_MD = "sources-a.md"
SOURCES_B_MD = "sources-b.md"
SOURCES_DIR = "sources"
SOURCES_SCHEMA = "client-update/sources/1"
DELIVERY_JSON = "delivery.json"
DELIVERY_RESULT_JSON = "delivery-result.json"
EVIDENCE_CSV = "UPDATE-EVIDENCE.csv"
CLAIMS_JSON = "claims.json"
CONFIRMATIONS_MD = "CONFIRMATIONS.md"
CONTEXT_PROPOSED_MD = "context-proposed.md"
ENGAGEMENT_CONTEXT_MD = "ENGAGEMENT-CONTEXT.md"
UPDATES_LEDGER_CSV = "UPDATES-LEDGER.csv"

EVIDENCE_COLUMNS = ("id", "kind", "item", "state", "sources", "location", "evidence", "review",
                    "review_file", "note", "updated_at", "by")
CLAIM_STATES = ("pending", "verified", "flagged", "contradicted", "unsupported", "cut")
REVIEW_STATES = ("ran", "passed", "failed")
CARRY_STATES = ("done", "moved", "dropped", "open")
STATE_KINDS = {**{s: "claim" for s in CLAIM_STATES}, **{s: "review" for s in REVIEW_STATES},
               **{s: "carry" for s in CARRY_STATES}}
LEDGER_COLUMNS = ("id", "item", "owner", "due", "state", "opened_week", "last_week", "note", "updated_at", "by")
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

DATE_RE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
WEEK_RE = re.compile(r"^(\d{4})-[Ww](\d{1,2})$")
WEEK_IN_TEXT_RE = re.compile(r"(?<!\d)(\d{4})-[Ww](\d{2})(?!\d)")


class Bad(Exception):
    """A bad argument, a missing Context, source or rules file: exit 2."""


class Refused(Exception):
    """A write refused because it would break the contract: exit 1."""


def run_main(main) -> None:
    """Run a script's main(), turning Refused into exit 1 and Bad into exit 2."""
    try:
        code = main()
    except Refused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        sys.exit(1)
    except Bad as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        sys.exit(2)
    sys.exit(code or 0)


def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


def blank(value) -> str | None:
    """A form left blank sends --x=; an empty or whitespace value counts as not given."""
    text = "" if value is None else str(value).strip()
    return text or None


def truthy(value) -> bool:
    return (blank(value) or "").lower() in ("true", "1", "yes", "on")


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stamp() -> str:
    return datetime.now().strftime("%Y%m%dT%H%M%S")


def free_path(path: Path) -> Path:
    """path if nothing is there, else the same name with -2, -3 ... before the suffix."""
    n = 2
    candidate = path
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}-{n}{path.suffix}")
        n += 1
    return candidate


def split_list(value, sep=","):
    return [p.strip().strip("`").strip() for p in (value or "").split(sep) if p.strip().strip("`").strip()]


def read_text(path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path is not None and path.is_file() else ""


def load_json(path: Path, what: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise Bad(f"no {what} at {path}") from None
    except (OSError, ValueError) as exc:
        raise Bad(f"{path} could not be read as JSON: {type(exc).__name__}") from None


def load_sources(work: Path) -> dict:
    data = load_json(work / SOURCES_JSON, SOURCES_JSON)
    if not isinstance(data, dict) or not isinstance(data.get("sources"), list):
        raise Bad(f"{work / SOURCES_JSON} is not a client-update pack")
    return data


def source_ids(pack) -> list:
    return [str(s.get("id")) for s in pack.get("sources") or [] if isinstance(s, dict)]


# --------------------------------------------------------------------------- the engagement and its rules

def context_file(engagement, contexts=None) -> Path:
    name = blank(engagement)
    if not name:
        raise Bad("ENGAGEMENT is required: a Context name or the path to a Context YAML file")
    if Path(name).suffix in (".yaml", ".yml") or "/" in name or os.sep in name or name.startswith("."):
        path = Path(name).expanduser()
        if not path.is_file():
            raise Bad(f"no Context file at {path}")
        return path
    folder = (blank(contexts) or blank(settings("client-update-workstream").get("contexts_dir"))
              or blank(settings().get("contexts_dir")))
    if not folder:
        raise Bad("set contexts_dir (in [client-update-workstream] or at the top level of the owner "
                  "settings), pass --contexts-dir, or give the Context file's path")
    for suffix in (".yaml", ".yml"):
        candidate = Path(folder).expanduser() / f"{name}{suffix}"
        if candidate.is_file():
            return candidate
    raise Bad(f"no Context named {name!r} in {folder} (pass --contexts-dir or a path)")


def field_lines(text: str, heading: str) -> dict:
    """The '- Key: value' lines under the heading, keys lower-cased, backticks unwrapped."""
    out, inside = {}, False
    for line in text.splitlines():
        found = re.match(r"^\s*#{1,6}\s+(.*?)\s*#*\s*$", line)
        if found:
            inside = found.group(1).strip().lower() == heading
            continue
        found = re.match(r"^\s*[-*]\s+([^:]+?)\s*:\s*(.*?)\s*$", line) if inside else None
        if found:
            key = re.sub(r"\s+", " ", found.group(1).strip().strip("*_").strip()).lower()
            value = found.group(2).strip()
            if len(value) >= 2 and value[0] == value[-1] == "`":
                value = value[1:-1].strip()
            out[key] = value
    return out


@dataclass
class Rules:
    variant: str
    update_day: int                 # 0 Monday .. 6 Sunday
    week_folder: str
    draft_file: str
    review_note: str
    cover_email: str | None
    previous_updates: list
    banned_phrases: list
    banned_characters: list
    slot_minutes: int | None
    engagement_context: str = ENGAGEMENT_CONTEXT_MD
    length_default: str = "weekly"
    portal_domain: str | None = None
    client_email_domains: list = field(default_factory=list)
    source_folders: list = field(default_factory=list)
    never_open: list = field(default_factory=list)
    email_delivery: str = "file"
    lookback_days: int = 21
    catch_up_after_days: int = 14
    catch_up_days: int = 30
    recipients: list = field(default_factory=list)


def whole_days(raw: dict, key: str, default: int) -> int:
    value = blank(raw.get(key))
    try:
        number = int(value) if value else default
    except ValueError:
        number = 0
    if number < 1:
        raise Bad(f"{RULES_MD}: {key.capitalize()} must be a whole number of days, 1 or more")
    return number


def parse_rules(text: str) -> Rules:
    raw = field_lines(text, "update inputs")
    variant = (blank(raw.get("variant")) or "").lower()
    if variant not in ("deck", "memo"):
        raise Bad(f"{RULES_MD}: Variant must be deck or memo under '## Update inputs'"
                  + (f", not {variant!r}" if variant else ""))
    day = (blank(raw.get("update day")) or "friday").lower()
    matches = [i for i, name in enumerate(WEEKDAYS) if len(day) >= 3 and name.startswith(day)]
    if len(matches) != 1:
        raise Bad(f"{RULES_MD}: Update day {day!r} is not a weekday")
    draft = blank(raw.get("draft file"))
    if not draft:
        raise Bad(f"{RULES_MD}: Draft file is required")
    want = ".html" if variant == "deck" else ".md"
    if not draft.lower().endswith(want):
        raise Bad(f"{RULES_MD}: a {variant}'s Draft file must end {want}, not {draft!r}")
    cover = blank(raw.get("cover email"))
    if variant == "memo" and not cover:
        raise Bad(f"{RULES_MD}: Cover email is required for a memo")
    slot = blank(raw.get("slot minutes"))
    try:
        slot_minutes = int(slot) if slot else None
    except ValueError:
        raise Bad(f"{RULES_MD}: Slot minutes {slot!r} is not a whole number") from None
    context = blank(raw.get("engagement context")) or ENGAGEMENT_CONTEXT_MD
    if "/" in context or "\\" in context or context.startswith("."):
        raise Bad(f"{RULES_MD}: Engagement context must be a file name in the rules folder, not {context!r}")
    length = (blank(raw.get("default length")) or "weekly").lower()
    if length not in ("weekly", "full"):
        raise Bad(f"{RULES_MD}: Default length must be weekly or full, not {length!r}")
    delivery = (blank(raw.get("email delivery")) or "file").lower()
    if delivery not in ("outlook-drafts", "file"):
        raise Bad(f"{RULES_MD}: Email delivery must be outlook-drafts or file, not {delivery!r}")
    return Rules(
        length_default=length, email_delivery=delivery, portal_domain=blank(raw.get("portal domain")),
        client_email_domains=[d.lstrip("@").lower() for d in split_list(raw.get("client email domains"))],
        source_folders=split_list(raw.get("source folders")), never_open=split_list(raw.get("never open")),
        lookback_days=whole_days(raw, "lookback days", 21),
        catch_up_after_days=whole_days(raw, "catch-up after days", 14),
        catch_up_days=whole_days(raw, "catch-up days", 30),
        recipients=split_list(raw.get("recipients"), ";"),
        variant=variant, update_day=matches[0], week_folder=blank(raw.get("week folder")) or "{week}",
        draft_file=draft, review_note=blank(raw.get("review note")) or "{date} review-notes.md",
        cover_email=cover if variant == "memo" else None,
        previous_updates=split_list(raw.get("previous updates")),
        banned_phrases=split_list(raw.get("banned phrases"), ";"),
        banned_characters=(blank(raw.get("banned characters")) or "").split() or ["\u2014"],
        slot_minutes=slot_minutes, engagement_context=context)


@dataclass
class Engagement:
    name: str
    rules_file: Path
    rules: Rules
    updates: Path
    background: str | None = None
    context_file: Path | None = None
    engagements: list = field(default_factory=list)   # the client folders, read only
    repo: Path | None = None

    @property
    def context_portal(self):
        """(note or project, id) when the background source is portal://note/<id> or
        portal://project/<id>, else None."""
        found = re.match(r"^portal://(note|project)/([^/\s]+)$", (self.background or "").strip())
        return (found.group(1), found.group(2)) if found else None

    @property
    def context_path(self) -> Path:
        """The engagement context file, which may not exist yet: the background source's file,
        or the rules' Engagement context file inside its folder; else the file beside the rules."""
        beside = self.rules_file.parent / self.rules.engagement_context
        if not self.background or self.background.startswith("portal://"):
            return beside
        where = Path(self.background).expanduser()
        return where / self.rules.engagement_context if where.is_dir() else where

    @property
    def context_label(self) -> str:
        """Where the engagement context is kept: a Portal ref as written, else the file's name."""
        if self.background and re.match(r"^portal://(note|project)/[^/\s]+$", self.background.strip()):
            return self.background
        if not self.background or self.background.startswith("portal://"):
            return self.rules.engagement_context
        where = Path(self.background).expanduser()
        return self.rules.engagement_context if where.is_dir() else where.name


def load_engagement(engagement, contexts=None) -> Engagement:
    import yaml  # only needed here, so --help works without it
    path = context_file(engagement, contexts)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise Bad(f"{path} could not be read as YAML: {type(exc).__name__}") from None
    if not isinstance(data, dict):
        raise Bad(f"{path} is not a Context: the top level is not a mapping")
    folders, background, engagements = {}, None, []
    for source in data.get("sources") or []:
        if not isinstance(source, dict):
            continue
        name, where = str(source.get("name") or "").strip(), str(source.get("path") or "").strip()
        if name == "background" and background is None:
            background = where or None
        if (name and where and str(source.get("kind") or "folder").strip() == "folder"
                and not where.startswith("portal://")):
            lowered = name.lower()
            if lowered == "engagement" or lowered.startswith("engagement-"):
                if Path(where).expanduser() not in engagements:
                    engagements.append(Path(where).expanduser())
            else:
                folders.setdefault(name, Path(where).expanduser())
    for required in ("rules", "updates"):
        if required not in folders:
            raise Bad(f"{path}: the Context has no '{required}' source")
    rules_file = folders["rules"] / RULES_MD
    if not rules_file.is_file():
        raise Bad(f"no {RULES_MD} in the rules folder {folders['rules']}")
    rules = parse_rules(rules_file.read_text(encoding="utf-8"))
    if not folders["updates"].is_dir():
        raise Bad(f"the updates folder {folders['updates']} does not exist")
    return Engagement(str(data.get("name") or path.stem), rules_file, rules, folders["updates"], background,
                      context_file=path, engagements=engagements, repo=folders.get("repo"))


def matches_never_open(globs, name: str, relative: str) -> bool:
    """Whether a Never open glob matches the file name, its path relative to the client folder,
    or any folder on that path (case-sensitive, as written in the rules)."""
    parts = [p for p in relative.replace(os.sep, "/").split("/") if p]
    return any(fnmatch.fnmatchcase(text, glob) for glob in globs for text in (name, relative, *parts))


# --------------------------------------------------------------------------- the week

def resolve_week(week, as_of=None):
    """(ISO year, ISO week) from yyyy-Www, a date, or blank (as_of or today)."""
    text = blank(week)
    try:
        if text is None:
            day = date.fromisoformat(blank(as_of)) if blank(as_of) else date.today()
            return day.isocalendar()[:2]
        found = WEEK_RE.match(text)
        if found:
            year, number = int(found.group(1)), int(found.group(2))
            date.fromisocalendar(year, number, 1)
            return year, number
        if DATE_RE.fullmatch(text):
            return date.fromisoformat(text).isocalendar()[:2]
    except ValueError:
        raise Bad(f"WEEK {text!r} is not an ISO week" if text else f"--as-of {as_of!r} is not a yyyy-mm-dd date") from None
    raise Bad(f"WEEK {text!r} is not yyyy-Www, a yyyy-mm-dd date or blank")


def fill(pattern: str, day: date, week: str) -> str:
    return pattern.replace("{date}", day.isoformat()).replace("{week}", week)


def as_glob(pattern: str) -> str:
    return pattern.replace("{date}", "*").replace("{week}", "*")


def date_in_text(text: str, update_day: int):
    """A yyyy-mm-dd date in the text, else a yyyy-Www week's update date, else None."""
    for found in DATE_RE.finditer(text):
        try:
            return date(int(found.group(1)), int(found.group(2)), int(found.group(3)))
        except ValueError:
            continue
    for found in WEEK_IN_TEXT_RE.finditer(text):
        try:
            return date.fromisocalendar(int(found.group(1)), int(found.group(2)), update_day + 1)
        except ValueError:
            continue
    return None


@dataclass
class Week:
    engagement: Engagement
    label: str
    date: date
    week_dir: Path

    @property
    def work(self) -> Path:
        return self.week_dir / "work"

    def file(self, pattern):
        return self.week_dir / fill(pattern, self.date, self.label) if pattern else None

    @property
    def draft(self) -> Path:
        return self.file(self.engagement.rules.draft_file)

    @property
    def review_note(self) -> Path:
        return self.file(self.engagement.rules.review_note)

    @property
    def cover_email(self):
        return self.file(self.engagement.rules.cover_email)

    @property
    def docx(self):
        return self.draft.with_suffix(".docx") if self.engagement.rules.variant == "memo" else None

    @property
    def ledger_file(self) -> Path:
        return self.engagement.updates / UPDATES_LEDGER_CSV

    @property
    def context_proposed(self) -> Path:
        return self.work / CONTEXT_PROPOSED_MD

    def files(self) -> dict:
        return {"draft": str(self.draft), "review_note": str(self.review_note),
                "cover_email": str(self.cover_email) if self.cover_email else None,
                "docx": str(self.docx) if self.docx else None}


def resolve(engagement, week=None, as_of=None, week_dir=None, contexts=None) -> Week:
    eng = load_engagement(engagement, contexts)
    year, number = resolve_week(week, as_of)
    label = f"{year}-W{number:02d}"
    day = date.fromisocalendar(year, number, eng.rules.update_day + 1)
    folder = Path(blank(week_dir)).expanduser() if blank(week_dir) else eng.updates / fill(eng.rules.week_folder, day, label)
    return Week(eng, label, day, folder)


def rule_matched_updates(week: Week) -> list:
    """Files the rules' Previous updates match whose name holds a date, as (date, path), newest first."""
    eng = week.engagement
    found = {}
    for pattern in eng.rules.previous_updates:
        for path in eng.updates.glob(pattern):
            when = date_in_text(path.name, eng.rules.update_day) if path.is_file() else None
            if when:
                found[path] = when
    return sorted(((d, p) for p, d in found.items()), key=lambda t: (t[0], str(t[1])), reverse=True)


def previous_updates(week: Week) -> list:
    """The rules' Previous updates plus drafts in other week folders, as (date, path), newest
    first. A draft's date comes from its path under the updates folder."""
    eng, rules = week.engagement, week.engagement.rules
    found = {p: d for d, p in rule_matched_updates(week)}
    own = (eng.updates / fill(rules.week_folder, week.date, week.label)).resolve()
    for path in eng.updates.glob(f"{as_glob(rules.week_folder)}/{as_glob(rules.draft_file)}"):
        if path.is_file() and path.parent.resolve() != own:
            when = date_in_text(str(path.relative_to(eng.updates)), rules.update_day)
            if when:
                found[path] = when
    return sorted(((d, p) for p, d in found.items()), key=lambda t: (t[0], str(t[1])), reverse=True)


def update_window(week: Week) -> dict:
    """What the update covers (THE WINDOW above): kind (since-previous, catch-up or first),
    since, until, the previous update and its date, the gap in days and a one-line note."""
    rules = week.engagement.rules
    earlier = [(d, p) for d, p in previous_updates(week) if d < week.date]
    until, previous, when = week.date, None, None
    if not earlier:
        kind, since = "first", until - timedelta(days=rules.lookback_days)
    else:
        when, previous = earlier[0]
        if (until - when).days > rules.catch_up_after_days:
            kind, since = "catch-up", max(when, until - timedelta(days=rules.catch_up_days))
        else:
            kind, since = "since-previous", when
    gap = (until - when).days if when else None
    span = f"{since.isoformat()} to {until.isoformat()}"
    note = {"catch-up": f"A catch-up update: the last update was {when.isoformat() if when else ''}, {gap} days "
                        f"ago, so this one covers the most recent {span}.",
            "first": f"No earlier update was found, so this one covers {span}.",
            "since-previous": f"Covers the time since the last update ({span})."}[kind]
    return {"kind": kind, "since": since, "until": until, "previous": previous, "previous_date": when,
            "gap_days": gap, "note": note}


# --------------------------------------------------------------------------- CSV ledgers

def read_rows(path: Path) -> dict:
    """A ledger's rows by id, values stripped; the first row of an id wins; no file is no rows."""
    if not path.is_file():
        return {}
    out = {}
    for raw in csv.DictReader(io.StringIO(path.read_text(encoding="utf-8").removeprefix("\ufeff"), newline="")):
        row = {k: (v or "").strip() for k, v in raw.items() if k}
        if row.get("id"):
            out.setdefault(row["id"], row)
    return out


def upsert_row(path: Path, columns, key: str, values: dict) -> str:
    """Create or update the row with id `key`. Other rows keep their exact text, the header
    must be the declared one, no row is ever deleted, and the file is replaced atomically.
    Returns 'created' or 'updated'."""
    raw = path.read_bytes() if path.is_file() else b""
    bom = "\ufeff" if raw.startswith(b"\xef\xbb\xbf") else ""
    lines = raw.decode("utf-8").removeprefix("\ufeff").splitlines(keepends=True)
    records, used = [], 0                      # (cells, the exact text they came from)
    reader = csv.reader(iter(lines))
    for cells in reader:
        records.append((cells, "".join(lines[used:reader.line_num])))
        used = reader.line_num
    end = "\r\n" if records and records[0][1].endswith("\r\n") else "\n"

    def line(cells):
        buffer = io.StringIO()
        csv.writer(buffer, lineterminator=end).writerow(cells)
        return buffer.getvalue()

    if records and [c.strip() for c in records[0][0]] != list(columns):
        raise Refused(f"{path.name} does not start with the header {','.join(columns)}")
    if not records:
        records = [(list(columns), line(columns))]
    index = next((i for i, (cells, _) in enumerate(records) if i and cells and cells[0].strip() == key), None)
    old = dict(zip(columns, [c.strip() for c in records[index][0]])) if index else {}
    row = {c: old.get(c, "") for c in columns}
    row.update({k: "" if v is None else str(v) for k, v in values.items()})
    row["id"] = key
    new = line([row[c] for c in columns])
    if index:
        records[index] = (records[index][0], new)
    else:
        if not records[-1][1].endswith(("\n", "\r")):
            records[-1] = (records[-1][0], records[-1][1] + end)
        records.append(([], new))
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp",
                                         delete=False, encoding="utf-8", newline="")
    try:
        with handle:
            handle.write(bom + "".join(t for _, t in records))
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(handle.name, path.stat().st_mode & 0o777)
        os.replace(handle.name, path)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise
    return "updated" if index else "created"


def record_evidence(work: Path, key: str, values: dict) -> str:
    """Upsert one row of the week's evidence file, refusing a state that does not fit the row's
    kind. A change to a claim's text, sources or location with no new review clears its review,
    so a verdict never outlives the claim it judged."""
    path = work / EVIDENCE_CSV
    old = read_rows(path).get(key, {})
    values = dict(values)
    changed = any(k in values and values[k] != old.get(k, "") for k in ("item", "sources", "location"))
    if old and changed and "review" not in values and old.get("review"):
        values.setdefault("review_file", "")
        values["review"] = ""
    state, kind = values.get("state", old.get("state", "")), values.get("kind", old.get("kind", ""))
    if state not in STATE_KINDS:
        raise Refused(f"--state {state!r} is not one of {', '.join(STATE_KINDS)}")
    if kind and STATE_KINDS[state] != kind:
        raise Refused(f"--state {state} belongs to the {STATE_KINDS[state]} kind, not {kind}")
    return upsert_row(path, EVIDENCE_COLUMNS, key, values)
