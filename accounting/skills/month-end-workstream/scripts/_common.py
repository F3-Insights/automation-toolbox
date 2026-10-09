"""What month_end_check.py and month_end_record.py share: the Month-End folder's layout, the
markdown readers, and the month's evidence file.

The evidence file, {yyyy}/{yyyy-mm}/MONTH-END-EVIDENCE-{yyyy-mm}.csv, holds one row per item of
work, keyed by id "<test>:<item>". Only month_end_record.py writes it, and it keeps these
promises: the header is exactly COLUMNS, a row is created or updated but never deleted, every
other row keeps its exact text (line endings, byte-order mark, quoted multi-line cells), and the
file is replaced atomically.
"""

import calendar
import csv
import io
import os
import re
import tempfile
from datetime import date
from pathlib import Path

COLUMNS = ["id", "test", "item", "state", "evidence", "amount", "pull_date", "review", "review_file",
           "note", "updated_at", "by"]
TESTS = ("entries", "reconciliations", "flux", "questions")
STATES = ("open", "waiting", "drafted", "booked", "reconciled", "explained", "answered", "not-needed")
# States that fit only one test; open, waiting and not-needed fit any.
STATE_TEST = {"drafted": "entries", "booked": "entries", "reconciled": "reconciliations",
              "explained": "flux", "answered": "questions"}
BOM = "\ufeff"


class Bad(Exception):
    """A bad argument, a missing folder or a malformed file (exit 2)."""


# Periods and folders

def check_period(period):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period or ""):
        raise Bad(f"--period {period!r} is not yyyy-mm")
    return period


def shift(period, months):
    year, month = (int(x) for x in period.split("-"))
    index = year * 12 + month - 1 + months
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def period_end(period):
    year, month = (int(x) for x in period.split("-"))
    return f"{period}-{calendar.monthrange(year, month)[1]:02d}"


def month_folder(root, period):
    return Path(root) / period[:4] / period


def evidence_path(root, period):
    return month_folder(root, period) / f"MONTH-END-EVIDENCE-{period}.csv"


def open_month(folder, period=None):
    """(root, period, month folder). Without a period, the root STATUS.md's 'Current period'."""
    root = Path(folder).expanduser()
    if not root.is_dir():
        raise Bad(f"the Month-End folder does not exist: {folder}")
    if period:
        check_period(period)
    else:
        status = root / "STATUS.md"
        if not status.is_file():
            raise Bad(f"no --period given and {status.name} is missing at the folder root")
        m = re.search(r"Current period:\**\s*`?(\d{4}-\d{2})", status.read_text(encoding="utf-8"))
        if not m:
            raise Bad("no --period given and the root STATUS.md has no 'Current period: yyyy-mm' line")
        period = check_period(m.group(1))
    month = month_folder(root, period)
    if not month.is_dir():
        raise Bad(f"the month folder does not exist: {period[:4]}/{period}")
    return root, period, month


# Markdown and values

def section(text, title):
    """The body of a '## title' section, or None."""
    m = re.search(rf"^##\s+{re.escape(title)}\s*$(.*?)(?=^#{{1,2}}\s|\Z)", text, re.M | re.S | re.I)
    return m.group(1) if m else None


def tables(text):
    """Every markdown table in the text, each a list of {header: cell} rows."""
    def cells(row):
        return [c.strip() for c in row.strip().strip("|").split("|")]
    blocks, block = [], []
    for raw in text.splitlines() + [""]:
        if raw.strip().startswith("|"):
            block.append(raw.strip())
        elif block:
            blocks.append(block)
            block = []
    out = []
    for rows in blocks:
        if len(rows) < 2:
            continue
        head = cells(rows[0])
        body = rows[2:] if re.fullmatch(r"[|\s:\-]+", rows[1]) else rows[1:]
        out.append([{h: (c[i] if i < len(c) else "") for i, h in enumerate(head)} for c in map(cells, body)])
    return out


def column(row, name):
    """A table cell by header name, ignoring case and emphasis around the header."""
    for key, value in row.items():
        if key.strip("*_ ").lower() == name.lower():
            return value
    return ""


def first_date(text):
    m = re.search(r"\d{4}-\d{2}-\d{2}", text or "")
    try:
        return date.fromisoformat(m.group(0)) if m else None
    except ValueError:
        return None


def money(value):
    """'1,234.50', '$(99)' or '-5' as a number; None when blank. Raises ValueError otherwise."""
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    negative = text.startswith("(") and text.endswith(")")
    amount = float(text.strip("()").replace(",", "").replace("$", ""))
    return -amount if negative else amount


def read_text(path):
    """A file's text with a leading byte-order mark dropped and line endings kept."""
    data = Path(path).read_bytes().decode("utf-8")
    return data[1:] if data.startswith(BOM) else data


# The evidence file

def read_evidence(path):
    """{id: row} with values stripped; the first row of an id wins; rows without an id skipped."""
    path = Path(path)
    if not path.is_file():
        return {}
    out = {}
    for raw in csv.DictReader(io.StringIO(read_text(path), newline="")):
        row = {k: (v or "").strip() for k, v in raw.items() if k}
        if row.get("id") and row["id"] not in out:
            out[row["id"]] = row
    return out


def _records(text):
    """The CSV records, each with the exact text it came from (a cell may span lines)."""
    lines = text.splitlines(keepends=True)
    reader = csv.reader(iter(lines))
    out, used = [], 0
    for row in reader:
        out.append((row, "".join(lines[used:reader.line_num])))
        used = reader.line_num
    return out


def _line(values, ending):
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator=ending).writerow(values)
    return buffer.getvalue()


def upsert_evidence(path, key, values):
    """Create or update the row with id `key`. A field not in `values` keeps its recorded value.
    A change of state, evidence or amount without a new review clears the review and its file.
    Returns (action, row, review_cleared)."""
    path = Path(path)
    bom = text = ""
    if path.is_file():
        text = read_text(path)
        bom = BOM if path.read_bytes().startswith(BOM.encode()) else ""
    records = _records(text) if text.strip() else []
    ending = "\r\n" if records and records[0][1].endswith("\r\n") else "\n"
    if records and [c.strip() for c in records[0][0]] != COLUMNS:
        raise Bad(f"{path.name} does not start with the header {','.join(COLUMNS)}")
    if not records:
        records = [(COLUMNS, _line(COLUMNS, ending))]

    index = next((i for i, (cells, _) in enumerate(records) if i and cells and cells[0].strip() == key), None)
    old = dict(zip(COLUMNS, records[index][0] + [""] * len(COLUMNS))) if index else {}
    row = {c: old.get(c, "") for c in COLUMNS}
    row.update({k: "" if v is None else str(v) for k, v in values.items()})
    row["id"] = key

    work_changed = any(f in values and row[f] != old.get(f, "") for f in ("state", "evidence", "amount"))
    cleared = bool(old) and work_changed and "review" not in values and bool(old.get("review"))
    if cleared:
        row["review"] = ""
        if "review_file" not in values:
            row["review_file"] = ""
    owner = STATE_TEST.get(row["state"])
    if row["state"] not in STATES:
        raise Bad(f"--state {row['state']!r} is not one of {', '.join(STATES)}")
    if owner and owner != row["test"]:
        raise Bad(f"--state {row['state']} belongs to the {owner} test, not {row['test']}")

    new = _line([row[c] for c in COLUMNS], ending)
    if index:
        records[index] = (records[index][0], new)
    else:
        if not records[-1][1].endswith(("\n", "\r")):
            records[-1] = (records[-1][0], records[-1][1] + ending)
        records.append(([], new))
    _atomic_write(path, bom + "".join(raw for _, raw in records))
    return ("updated" if index else "created"), row, cleared


def _atomic_write(path, text):
    """Write through a synced temporary file renamed over the old one, keeping its permissions."""
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
