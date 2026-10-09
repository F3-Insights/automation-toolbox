"""What the client-delivery scripts share: the engagement, its rules, its plan and its ledgers.

THE ENGAGEMENT
An engagement is named by a Context: one YAML file with a `name` and a `sources:` list of
`{name, kind: folder, path}`. ENGAGEMENT on the command line is a Context name, looked up as
`<contexts_dir>/<name>.yaml` (setting `contexts_dir`, or `--contexts-dir`), or a path to the
YAML file itself. The folder sources read by name:

- `rules` (required): the folder holding the owner's DELIVERY-RULES.md.
- `working` (required): the delivery working folder, where PLAN.md, RAID.csv,
  DELIVERY-EVIDENCE.csv, STATUS.md, LOG.md and CONFIRMATIONS.md live.
- `engagement` or `engagement-<anything>` (optional): the client folders, read only.
- `repo` (optional): the engagement's build repository; its git log is a source.

THE RULES (DELIVERY-RULES.md)
`- Key: value` lines under `## Delivery inputs`: Portal domain, SOW (`;`-separated paths
relative to the rules folder, or `missing`, or `none ...`), Lead time days (10), RAID review
days (14), Session stale days (4), Lookback days (14), Assignable (Portal contact ids),
Client email domains, Source folders, Never open. A `## Scope baseline` table
`| Id | Deliverable | Due | Acceptance |` written by the owner from the SOW.

THE PLAN (PLAN.md): a `## Milestones` table
`| Id | Milestone | Owner | Baseline due | Planned due | Client date | Acceptance | Source |`.

THE LEDGERS, written only by delivery_record.py: DELIVERY-EVIDENCE.csv (milestone, change and
session rows) and RAID.csv (risks, assumptions, issues, dependencies).
"""

import csv
import fnmatch
import io
import json
import os
import re
import tempfile
import tomllib
from datetime import date, datetime, timezone
from pathlib import Path

RULES_MD = "DELIVERY-RULES.md"
PLAN_MD = "PLAN.md"
RAID_CSV = "RAID.csv"
EVIDENCE_CSV = "DELIVERY-EVIDENCE.csv"
STATE_FILES = (PLAN_MD, RAID_CSV, EVIDENCE_CSV, "STATUS.md", "LOG.md", "CONFIRMATIONS.md")
PACK_DIR = "delivery"            # inside the Run folder
PACK_JSON = "pack.json"
CHANGES_JSON = "changes.json"    # at the Run folder's root, the task change set
PACK_SCHEMA = "client-delivery/pack/1"
MODES = ("plan", "check", "milestone-review")

EVIDENCE_COLUMNS = ("id", "kind", "item", "state", "due", "evidence", "source", "note", "review",
                    "review_file", "updated_at", "by")
MILESTONE_STATES = ("planned", "in-progress", "at-risk", "delivered", "accepted")
CHANGE_STATES = ("proposed", "approved", "rejected")
SESSION_STATES = ("done", "dry-run")
DONE_MILESTONE = ("delivered", "accepted")
KIND_STATES = {"milestone": MILESTONE_STATES, "change": CHANGE_STATES, "session": SESSION_STATES}

RAID_COLUMNS = ("id", "type", "title", "owner", "raised", "review_by", "state", "severity", "source",
                "mitigation", "note", "updated_at", "by")
RAID_TYPES = ("risk", "assumption", "issue", "dependency")

UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,19}$")
HEADING_RE = re.compile(r"^\s*#{1,6}\s+(.*?)\s*#*\s*$")
FIELD_RE = re.compile(r"^\s*[-*]\s+([^:]+?)\s*:\s*(.*?)\s*$")
TASK_OPS = ("complete", "edit", "merge", "cancel", "create", "comment")


class Bad(Exception):
    """A bad argument, or a missing Context, rules file or setting: exit 2."""


class Refused(Exception):
    """A ledger write refused because it breaks the contract: exit 1."""


def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


def blank(value):
    """A launch form left blank sends `--x=`: an empty value means not given (None)."""
    text = "" if value is None else str(value).strip()
    return text or None


def now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def truthy(value):
    return (blank(value) or "").lower() in ("true", "1", "yes", "on")


def parse_date(value, what="date"):
    text = blank(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise Bad(f"{what} {text!r} is not a yyyy-mm-dd date") from None


def as_of_date(value):
    return parse_date(value, "--as-of") or date.today()


def split_list(value, sep=","):
    return [p.strip().strip("`").strip() for p in (value or "").split(sep) if p.strip().strip("`").strip()]


def load_json(path, what):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise Bad(f"no {what} at {path}") from None
    except (OSError, ValueError) as exc:
        raise Bad(f"{path} could not be read as JSON: {type(exc).__name__}") from None


# --------------------------------------------------------------------------- markdown

def field_lines(text, heading):
    """The `- Key: value` lines under one heading, keys lower-cased, backticks unwrapped."""
    out, inside, wanted = {}, False, heading.strip().lower()
    for line in text.splitlines():
        head = HEADING_RE.match(line)
        if head:
            inside = head.group(1).strip().lower() == wanted
            continue
        found = FIELD_RE.match(line) if inside else None
        if found:
            key = re.sub(r"\s+", " ", found.group(1).strip().strip("*_").strip()).lower()
            value = found.group(2).strip()
            if len(value) >= 2 and value[0] == value[-1] == "`":
                value = value[1:-1].strip()
            out[key] = value
    return out


def table_under(text, heading):
    """The first markdown table under a heading, as rows keyed by lower-cased header; None when
    the heading or its table is missing."""
    lines = text.splitlines()
    wanted = heading.strip().lower()
    start = next((i + 1 for i, line in enumerate(lines)
                  if HEADING_RE.match(line) and HEADING_RE.match(line).group(1).strip().lower() == wanted), None)
    if start is None:
        return None
    header, rows = None, []
    for line in lines[start:]:
        if HEADING_RE.match(line):
            break
        stripped = line.strip()
        if not stripped.startswith("|"):
            if header is not None and stripped:
                break
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if header is None:
            header = [re.sub(r"\s+", " ", c).lower() for c in cells]
        elif not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            rows.append({h: (cells[i] if i < len(cells) else "") for i, h in enumerate(header)})
    return rows if header is not None else None


# --------------------------------------------------------------------------- the engagement

def load_context(ref, contexts_dir=None):
    """(name, file, folder sources in order as (name, Path)) for the Context ENGAGEMENT names."""
    import yaml  # the Context files are YAML

    name = blank(ref)
    if not name:
        raise Bad("ENGAGEMENT is required: a Context name or the path to a Context YAML file")
    if name.endswith((".yaml", ".yml")) or "/" in name or name.startswith("."):
        path = Path(name).expanduser()
        if not path.is_file():
            raise Bad(f"no Context file at {path}")
    else:
        library = blank(contexts_dir) or blank(settings().get("contexts_dir"))
        if not library:
            raise Bad("setting contexts_dir is needed (the folder of Context YAML files), "
                      "or pass --contexts-dir or a path to the Context file")
        library = Path(library).expanduser()
        path = next((library / f"{name}{s}" for s in (".yaml", ".yml") if (library / f"{name}{s}").is_file()), None)
        if path is None:
            raise Bad(f"no Context named {name!r} in {library}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise Bad(f"{path} could not be read as YAML: {type(exc).__name__}") from None
    if not isinstance(data, dict):
        raise Bad(f"{path} is not a Context: the top level is not a mapping")
    sources = []
    for s in data.get("sources") or []:
        if not isinstance(s, dict) or str(s.get("kind") or "folder").strip() != "folder":
            continue
        sname, where = str(s.get("name") or "").strip(), str(s.get("path") or "").strip()
        if sname and where and not where.startswith("portal://"):
            sources.append((sname, Path(where).expanduser()))
    return str(data.get("name") or path.stem), path, sources


def is_client_folder(name):
    low = name.strip().lower()
    return low == "engagement" or low.startswith("engagement-")


def parse_sow(value, rules_dir):
    """{state: files|none|missing, files, note}. A SOW named but not on disk is missing."""
    text = blank(value)
    if text is None or text.lower().startswith("missing"):
        note = text[len("missing"):].strip().strip("()").strip() if text else ""
        return {"state": "missing", "files": [], "note": note or "the rules name no SOW"}
    if text.lower().startswith("none"):
        return {"state": "none", "files": [], "note": text}
    files = []
    for part in split_list(text, ";"):
        path = Path(part).expanduser()
        files.append(path if path.is_absolute() else rules_dir / path)
    absent = [str(p) for p in files if not p.is_file()]
    if absent:
        return {"state": "missing", "files": files,
                "note": "the rules name a SOW that is not on disk: " + "; ".join(absent)}
    return {"state": "files", "files": files, "note": f"{len(files)} SOW file(s) on file"}


def whole(raw, key, default):
    value = blank(raw.get(key))
    if value is None:
        return default
    if not re.fullmatch(r"\d{1,4}", value):
        raise Bad(f"{RULES_MD}: {key.capitalize()} {value!r} is not a whole number")
    return int(value)


def parse_rules(text, rules_dir):
    raw = field_lines(text, "Delivery inputs")
    baseline = [r for r in (table_under(text, "Scope baseline") or []) if blank(r.get("id"))]
    ids = [r["id"] for r in baseline]
    if len(ids) != len(set(ids)):
        raise Bad(f"{RULES_MD}: the Scope baseline repeats an Id")
    return {
        "portal_domain": blank(raw.get("portal domain")),
        "sow": parse_sow(raw.get("sow"), rules_dir),
        "lead_time_days": whole(raw, "lead time days", 10),
        "raid_review_days": whole(raw, "raid review days", 14),
        "session_stale_days": whole(raw, "session stale days", 4),
        "lookback_days": whole(raw, "lookback days", 14) or 14,
        "assignable": [m.lower() for m in UUID_RE.findall(raw.get("assignable") or "")],
        "client_email_domains": [d.lstrip("@").lower() for d in split_list(raw.get("client email domains"))],
        "source_folders": split_list(raw.get("source folders")),
        "never_open": split_list(raw.get("never open")),
        "baseline": baseline,
    }


def load_engagement(ref, contexts_dir=None):
    """The engagement: name, context file, rules file and rules, working folder, client
    folders and repo."""
    name, path, sources = load_context(ref, contexts_dir)
    named = {}
    for sname, where in sources:
        if not is_client_folder(sname):
            named.setdefault(sname, where)
    for required in ("rules", "working"):
        if required not in named:
            raise Bad(f"{path}: the Context has no '{required}' source")
    rules_file = named["rules"] / RULES_MD
    if not rules_file.is_file():
        raise Bad(f"no {RULES_MD} in the rules folder {named['rules']}")
    clients = []
    for sname, where in sources:
        if is_client_folder(sname) and where not in clients:
            clients.append(where)
    return {"name": name, "context_file": path, "rules_file": rules_file,
            "rules": parse_rules(rules_file.read_text(encoding="utf-8"), named["rules"]),
            "working": named["working"], "engagements": clients, "repo": named.get("repo")}


def working_folder(eng, override):
    return Path(blank(override)).expanduser() if blank(override) else eng["working"]


# --------------------------------------------------------------------------- the plan

PLAN_KEYS = {"id": ("id",), "milestone": ("milestone", "deliverable"), "owner": ("owner",),
             "baseline due": ("baseline due", "baseline"), "planned due": ("planned due", "planned", "due"),
             "client date": ("client date", "client"), "acceptance": ("acceptance", "acceptance test"),
             "source": ("source", "sources")}


def read_plan(path):
    """PLAN.md's milestones: {present, milestones, problems}."""
    if not path.is_file():
        return {"present": False, "milestones": [], "problems": [f"no {PLAN_MD} yet"]}
    table = table_under(path.read_text(encoding="utf-8", errors="replace"), "Milestones")
    if table is None:
        return {"present": True, "milestones": [], "problems": [f"{PLAN_MD} has no '## Milestones' table"]}
    milestones = []
    for row in table:
        item = {key: next((row[n].strip().strip("`").strip() for n in names if n in row), "")
                for key, names in PLAN_KEYS.items()}
        if item["id"]:
            item["client date"] = "yes" if item["client date"].lower() in ("yes", "y", "true", "client") else "no"
            milestones.append(item)
    return {"present": True, "milestones": milestones, "problems": []}


# --------------------------------------------------------------------------- the ledgers

def read_text_nobom(path):
    data = path.read_bytes()
    return data[3:].decode("utf-8") if data.startswith(b"\xef\xbb\xbf") else data.decode("utf-8")


class Ledger:
    """One CSV ledger keyed by its first column. Upsert by id; nothing is ever deleted; every
    other row keeps its exact text; written through a temporary file and a rename. When a work
    field changes and no new review is given, the review fields are cleared."""

    def __init__(self, path, columns, validate, work_fields=(), review_fields=()):
        self.path, self.columns, self.validate = Path(path), list(columns), validate
        self.work_fields, self.review_fields = work_fields, review_fields

    def rows(self):
        """The rows in file order, values stripped; the first row of an id wins."""
        if not self.path.is_file():
            return []
        out, seen = [], set()
        for raw in csv.DictReader(io.StringIO(read_text_nobom(self.path), newline="")):
            row = {k: (v or "").strip() for k, v in raw.items() if k}
            if row.get(self.columns[0]) and row[self.columns[0]] not in seen:
                seen.add(row[self.columns[0]])
                out.append(row)
        return out

    def _records(self):
        """Each record with the exact text it came from, the line ending, and the BOM."""
        if not self.path.is_file():
            return [], "\n", ""
        bom = "﻿" if self.path.read_bytes().startswith(b"\xef\xbb\xbf") else ""
        lines = read_text_nobom(self.path).splitlines(keepends=True)
        reader, records, used = csv.reader(iter(lines)), [], 0
        for row in reader:
            records.append((row, "".join(lines[used:reader.line_num])))
            used = reader.line_num
        if records and [c.strip() for c in records[0][0]] != self.columns:
            raise Refused(f"{self.path.name} does not start with the header {','.join(self.columns)}")
        ending = "\r\n" if records and records[0][1].endswith("\r\n") else "\n"
        return records, ending, bom

    def upsert(self, row):
        """Create or update the row with this id. Returns 'created ...' or 'updated ...'."""
        records, ending, bom = self._records()

        def line(values):
            buf = io.StringIO()
            csv.writer(buf, lineterminator=ending).writerow(values)
            return buf.getvalue()

        if not records:
            records = [(self.columns, line(self.columns))]
        key = row["id"]
        index = next((i for i, (r, _) in enumerate(records) if i and r and r[0].strip() == key), None)
        old = dict(zip(self.columns, [c.strip() for c in records[index][0]] + [""] * len(self.columns))) if index else {}
        new = {c: old.get(c, "") for c in self.columns}
        new.update({k: "" if v is None else str(v) for k, v in row.items()})
        changed = any(f in row and new[f] != old.get(f, "") for f in self.work_fields)
        cleared = bool(old) and self.review_fields and changed and self.review_fields[0] not in row \
            and bool(old.get(self.review_fields[0]))
        if cleared:
            for f in self.review_fields:
                if f not in row:
                    new[f] = ""
        self.validate(new)
        text = line([new[c] for c in self.columns])
        if index:
            records[index] = (records[index][0], text)
        else:
            if not records[-1][1].endswith(("\n", "\r")):
                records[-1] = (records[-1][0], records[-1][1] + ending)
            records.append(([], text))
        write_atomic(self.path, bom + "".join(raw for _, raw in records))
        return f"{'updated' if index else 'created'} {key} ({new.get('state')})" + (", review cleared" if cleared else "")


def write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp",
                                         delete=False, encoding="utf-8", newline="")
    try:
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(handle.name, path.stat().st_mode & 0o777)
        os.replace(handle.name, path)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise


def validate_evidence(row):
    kind, state = row.get("kind"), row.get("state")
    if kind not in KIND_STATES:
        raise Refused(f"kind {kind!r} is not milestone, change or session")
    if state not in KIND_STATES[kind]:
        raise Refused(f"{row['id']}: state {state!r} is not one of {', '.join(KIND_STATES[kind])}")
    if not blank(row.get("item")):
        raise Refused(f"{row['id']}: item is required (the milestone id, or the session's mode)")
    due = blank(row.get("due"))
    if due and not DATE_RE.match(due):
        raise Refused(f"{row['id']}: due {due!r} is not a yyyy-mm-dd date")
    if kind == "milestone" and state in DONE_MILESTONE and not blank(row.get("evidence")):
        raise Refused(f"{row['id']}: a {state} milestone needs its evidence")
    if kind == "change":
        if not due:
            raise Refused(f"{row['id']}: a plan change needs the new date (due)")
        if not blank(row.get("note")):
            raise Refused(f"{row['id']}: a plan change needs its reason (note)")
        if state == "approved" and not blank(row.get("source")):
            raise Refused(f"{row['id']}: an approved change needs where the owner approved it (source)")


def validate_raid(row):
    if row.get("type") not in RAID_TYPES:
        raise Refused(f"{row['id']}: type {row.get('type')!r} is not one of {', '.join(RAID_TYPES)}")
    if row.get("state") not in ("open", "closed"):
        raise Refused(f"{row['id']}: state {row.get('state')!r} is not open or closed")
    if row.get("severity", "") not in ("", "low", "medium", "high"):
        raise Refused(f"{row['id']}: severity {row.get('severity')!r} is not low, medium or high")
    if not blank(row.get("title")):
        raise Refused(f"{row['id']}: title is required")
    for name in ("raised", "review_by"):
        value = blank(row.get(name))
        if value and not DATE_RE.match(value):
            raise Refused(f"{row['id']}: {name} {value!r} is not a yyyy-mm-dd date")
    if row.get("state") == "open":
        missing = [n for n in ("owner", "source", "review_by") if not blank(row.get(n))]
        if missing:
            raise Refused(f"{row['id']}: an open item needs {', '.join(missing)}")


def evidence_ledger(working):
    return Ledger(working / EVIDENCE_CSV, EVIDENCE_COLUMNS, validate_evidence,
                  work_fields=("state", "due", "evidence"), review_fields=("review", "review_file"))


def raid_ledger(working):
    return Ledger(working / RAID_CSV, RAID_COLUMNS, validate_raid)


def latest_session(rows):
    days = [date.fromisoformat(m.group(1)) for r in rows if r.get("kind") == "session"
            for m in [re.match(r"^session:(\d{4}-\d{2}-\d{2})", r.get("id") or "")] if m]
    return max(days) if days else None


# --------------------------------------------------------------------------- the pack and authority

def load_pack(path):
    """A pack.json, given as the file, the pack folder or the Run folder."""
    path = Path(path).expanduser()
    for candidate in (path, path / PACK_JSON, path / PACK_DIR / PACK_JSON):
        if candidate.is_file():
            data = load_json(candidate, PACK_JSON)
            if not isinstance(data, dict) or data.get("schema") != PACK_SCHEMA:
                raise Bad(f"{candidate} is not a client-delivery pack")
            return data
    raise Bad(f"no {PACK_JSON} at {path}")


def uuid_in(ref):
    found = UUID_RE.search(str(ref or ""))
    return found.group(0).lower() if found else ""


def authority_problems(changes, pack):
    """(op id, why) for each op the engagement's rules do not allow: not a task op, a task or
    project outside the engagement's domain, or work assigned to someone other than the owner
    and the rules' Assignable people."""
    rules = pack.get("settings") or {}
    domain = str(rules.get("portal_domain") or "").lower()
    allowed = {str(pack.get("owner_contact") or "").lower(), *[str(a).lower() for a in rules.get("assignable") or []]} - {""}
    task_ids = {str(t.get("id")).lower() for t in (pack.get("tasks") or {}).get("items") or []}
    projects = {str(p.get("id")).lower() for p in pack.get("projects") or []}
    out = []
    for op in changes.get("ops") or []:
        if not isinstance(op, dict):
            continue
        oid, kind = str(op.get("id") or "?"), op.get("op")
        if kind not in TASK_OPS:
            out.append((oid, f"{kind} is not a task op; client delivery changes only the engagement's tasks"))
            continue
        if kind == "create":
            assignee = str(op.get("owner") or "").lower()
            project, op_domain = uuid_in(op.get("project")), uuid_in(op.get("domain"))
            if project and project not in projects:
                out.append((oid, "creates a task in a project outside the engagement's domain"))
                continue
            if not project and op_domain != domain:
                out.append((oid, "creates a task outside the engagement's domain"))
                continue
        else:
            refs = [op.get("task")] + ([op.get("into")] if kind == "merge" else [])
            if any(uuid_in(r) not in task_ids for r in refs):
                out.append((oid, "touches a task that is not an open task of the engagement's domain"))
                continue
            fields = op.get("set") if kind == "edit" and isinstance(op.get("set"), dict) else {}
            assignee = str(fields.get("owner_contact_id") or "").lower()
            if fields.get("project_id") and uuid_in(fields["project_id"]) not in projects:
                out.append((oid, "moves a task to a project outside the engagement's domain"))
                continue
            if fields.get("domain_id") and uuid_in(fields["domain_id"]) != domain:
                out.append((oid, "moves a task out of the engagement's domain"))
                continue
        if assignee and assignee not in allowed:
            out.append((oid, "assigns work to a person who has not agreed to receive agent assignments; "
                             "the first assignment is the owner's call"))
    return out


def matches_never_open(globs, name, relative):
    """Whether a Never open glob matches the file name, its relative path or any folder on it."""
    parts = [p for p in relative.replace(os.sep, "/").split("/") if p]
    return any(fnmatch.fnmatchcase(text, g) for g in globs for text in [name, relative.replace(os.sep, "/"), *parts])
