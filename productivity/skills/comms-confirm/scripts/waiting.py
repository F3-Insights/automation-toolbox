"""The `## Waiting on` table of an engagement folder's period STATUS.md, for confirm.py.

Standard library only. A folder keeps one STATUS.md per period at `{yyyy}/{yyyy-mm}/STATUS.md`,
and the root STATUS.md names the current period in a `Current period: yyyy-mm` line. The period
file carries a `## Phases` table and a `## Waiting on` table with the columns

    | Id | Phase | Question | Asked of | How | Asked at | State | Answer | Answered at |

A row is open, answered or closed. Every function here changes only the row it names and the
file's `Last updated:` line, so any text a person wrote by hand stays where it was. A `|` inside
a cell is written as `\\|`.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PERIOD_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
HOW_VALUES = ("question to owner", "task", "email draft", "sub-agent")
PHASE_COLS = ["Phase", "State", "Files", "Note"]
WAIT_COLS = ["Id", "Phase", "Question", "Asked of", "How", "Asked at", "State", "Answer", "Answered at"]


class ContractError(Exception):
    """The folder or its STATUS.md is not in the shape this module edits."""


# ---------------------------------------------------------------------------------------------
# Periods, time and lines


def check_period(period: str) -> str:
    if not PERIOD_RE.match(period or ""):
        raise ContractError(f"period {period!r} is not yyyy-mm")
    return period


def stamp(at: Optional[str] = None) -> str:
    """`yyyy-mm-dd HH:MM`, local time, or the given value once it is checked."""
    if at:
        if not re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$", at):
            raise ContractError(f"--at {at!r} is not 'yyyy-mm-dd HH:MM'")
        return at
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def read_lines(path: Path) -> List[str]:
    return path.read_text(encoding="utf-8").splitlines()


def write_lines(path: Path, lines: List[str]) -> None:
    path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")


def find_field(lines: List[str], name: str) -> Tuple[Optional[int], Optional[str]]:
    """The first `Name: value` line, as (index, value)."""
    pattern = re.compile(rf"^{re.escape(name)}:\s*(.*?)\s*$", re.IGNORECASE)
    for i, line in enumerate(lines):
        m = pattern.match(line)
        if m:
            return i, m.group(1)
    return None, None


def set_field(lines: List[str], name: str, value: str) -> None:
    """Replace a field's value, or add the field after the H1 when there is none."""
    i, _ = find_field(lines, name)
    if i is not None:
        lines[i] = f"{name}: {value}"
        return
    at = next((k + 1 for k, ln in enumerate(lines) if ln.startswith("# ")), 0)
    lines.insert(at, f"{name}: {value}")
    if at == 1:
        lines.insert(at, "")


def current_period(folder: Path, given: Optional[str]) -> str:
    """The given period, or the root STATUS.md's `Current period:`."""
    if given:
        return check_period(given)
    path = folder / "STATUS.md"
    value = find_field(read_lines(path), "Current period")[1] if path.is_file() else None
    if not value:
        raise ContractError("no --period given and the root STATUS.md names no current period")
    return check_period(value.strip())


def period_status_path(folder: Path, period: str) -> Path:
    check_period(period)
    return folder / period[:4] / period / "STATUS.md"


# ---------------------------------------------------------------------------------------------
# Sections and tables


def find_section(lines: List[str], title: str) -> Optional[Tuple[int, int]]:
    """(heading index, end index exclusive) of `## title`, matched without case."""
    want = title.strip().lower()
    for i, line in enumerate(lines):
        if line.startswith("## ") and line[3:].strip().lower() == want:
            end = next((k for k in range(i + 1, len(lines)) if lines[k].startswith(("## ", "# "))), len(lines))
            return i, end
    return None


def split_row(line: str) -> List[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|") and not text.endswith("\\|"):
        text = text[:-1]
    cells, cur, i = [], "", 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text) and text[i + 1] == "|":
            cur += "|"
            i += 2
            continue
        if text[i] == "|":
            cells.append(cur.strip())
            cur = ""
        else:
            cur += text[i]
        i += 1
    cells.append(cur.strip())
    return cells


def cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def format_row(cells: List[str]) -> str:
    return "| " + " | ".join(cell(c) for c in cells) + " |"


class Table:
    """A markdown table inside one section: its header line, its rows and where each sits."""

    def __init__(self, header_index: int, header: List[str], rows: List[Tuple[int, List[str]]], end: int):
        self.header_index = header_index
        self.header = header
        self.rows = rows
        self.end = end  # index after the last table line

    def col(self, name: str) -> int:
        return [h.lower() for h in self.header].index(name.lower())

    def get(self, cells: List[str], name: str) -> str:
        k = self.col(name)
        return cells[k] if k < len(cells) else ""


def find_table(lines: List[str], title: str) -> Optional[Table]:
    span = find_section(lines, title)
    if span is None:
        return None
    start, end = span
    first = next((k for k in range(start + 1, end) if lines[k].strip().startswith("|")), None)
    if first is None:
        return None
    header = split_row(lines[first])
    rows: List[Tuple[int, List[str]]] = []
    k = first + 1
    if k < end and re.match(r"^\s*\|?\s*:?-{3,}", lines[k]):
        k += 1
    while k < end and lines[k].strip().startswith("|"):
        rows.append((k, split_row(lines[k])))
        k += 1
    return Table(first, header, rows, k)


def _period_status(folder: Path, period: Optional[str]):
    period = current_period(folder, period)
    path = period_status_path(folder, period)
    if not path.is_file():
        raise ContractError(f"{path.relative_to(folder).as_posix()} does not exist")
    return period, path, read_lines(path)


def _table(lines: List[str], title: str, cols: List[str]) -> Table:
    table = find_table(lines, title)
    if table is None:
        raise ContractError(f'no "## {title}" table')
    missing = [c for c in cols if c.lower() not in [h.lower() for h in table.header]]
    if missing:
        raise ContractError(f'the "## {title}" table has no column {", ".join(missing)}')
    return table


def _padded(table: Table, cells: List[str]) -> List[str]:
    """A row's cells laid out in the table's own column order, padded to its width."""
    return cells + [""] * (len(table.header) - len(cells))


def _find(table: Table, row_id: str, period: str) -> Tuple[int, List[str]]:
    found = next(((i, c) for i, c in table.rows if table.get(c, "Id") == row_id), None)
    if found is None:
        raise ContractError(f"no Waiting on row {row_id} in {period}")
    return found[0], _padded(table, list(found[1]))


# ---------------------------------------------------------------------------------------------
# The rows


def row(folder: Path, row_id: str, period: str) -> Dict[str, str]:
    """A Waiting on row as {column: value}, or {} when the file, the table or the row is missing."""
    path = period_status_path(folder, period)
    if not path.is_file():
        return {}
    table = find_table(read_lines(path), "Waiting on")
    if table is None:
        return {}
    for _, cells in table.rows:
        if table.get(cells, "Id") == row_id:
            return {h: table.get(cells, h) for h in table.header}
    return {}


def ask(folder: Path, by: str, question: str, of: str, how: str, phase: str = "",
        row_id: Optional[str] = None, period: Optional[str] = None, at: Optional[str] = None) -> str:
    """Add an open row; returns its id (W1, W2, ... unless row_id is given)."""
    if not question.strip() or not of.strip():
        raise ContractError("the question and whom it is asked of must say something")
    if how.strip().lower() not in HOW_VALUES:
        raise ContractError(f"how {how!r} is not one of: {', '.join(HOW_VALUES)}")
    period, path, lines = _period_status(folder, period)
    if phase.strip():
        phases = _table(lines, "Phases", PHASE_COLS)
        names = {phases.get(c, "Phase").lower(): phases.get(c, "Phase") for _, c in phases.rows}
        if phase.strip().lower() not in names:
            raise ContractError(f"no phase {phase!r} in {period} (phases: {', '.join(names.values()) or 'none'})")
        phase = names[phase.strip().lower()]
    table = _table(lines, "Waiting on", WAIT_COLS)
    ids = [table.get(c, "Id") for _, c in table.rows]
    if row_id is None:
        nums = [int(m.group(1)) for i in ids if (m := re.fullmatch(r"W(\d+)", i))]
        row_id = f"W{max(nums, default=0) + 1}"
    elif row_id in ids:
        raise ContractError(f"{period} already has a Waiting on row {row_id}")
    now = stamp(at)
    values = {"Id": row_id, "Phase": phase, "Question": question, "Asked of": of,
              "How": how.strip().lower(), "Asked at": now[:10], "State": "open", "Answer": "",
              "Answered at": ""}
    cells = [values.get(next((c for c in WAIT_COLS if c.lower() == h.lower()), ""), "") for h in table.header]
    lines.insert(table.end, format_row(cells))
    set_field(lines, "Last updated", f"{now} by {by}")
    write_lines(path, lines)
    return row_id


def _set_state(folder: Path, by: str, row_id: str, state: str, answer_text: Optional[str],
               period: Optional[str], at: Optional[str]) -> str:
    period, path, lines = _period_status(folder, period)
    table = _table(lines, "Waiting on", WAIT_COLS)
    index, cells = _find(table, row_id, period)
    now = stamp(at)
    if answer_text is not None and answer_text.strip():
        cells[table.col("Answer")] = answer_text
    if state == "answered" and not cells[table.col("Answer")].strip():
        raise ContractError("an answered row needs an answer")
    if state == "closed" and not cells[table.col("Answer")].strip():
        cells[table.col("Answer")] = "(withdrawn)"
    if answer_text or not cells[table.col("Answered at")].strip():
        cells[table.col("Answered at")] = now[:10]
    cells[table.col("State")] = state
    lines[index] = format_row(cells)
    set_field(lines, "Last updated", f"{now} by {by}")
    write_lines(path, lines)
    return f"{period} {row_id}: {state}"


def answer(folder: Path, by: str, row_id: str, text: str, period: Optional[str] = None,
           at: Optional[str] = None) -> str:
    return _set_state(folder, by, row_id, "answered", text, period, at)


def close(folder: Path, by: str, row_id: str, text: Optional[str] = None, period: Optional[str] = None,
          at: Optional[str] = None) -> str:
    """Closed: the answer has been acted on, or the question was withdrawn."""
    return _set_state(folder, by, row_id, "closed", text, period, at)


def reopen(folder: Path, by: str, row_id: str, note: str = "", period: Optional[str] = None,
           at: Optional[str] = None) -> str:
    """An answered row whose answer did not answer: back to open. The answer seen moves into the
    question cell as "(earlier reply: ...)", so nothing is lost."""
    period, path, lines = _period_status(folder, period)
    table = _table(lines, "Waiting on", WAIT_COLS)
    index, cells = _find(table, row_id, period)
    if cells[table.col("State")].strip().lower() != "answered":
        raise ContractError(f"{row_id} is {cells[table.col('State')] or 'open'}; only an answered row is reopened")
    seen = cells[table.col("Answer")].strip()
    extra = f"earlier reply: {seen}" + (f"; {note.strip()}" if note and note.strip() else "")
    cells[table.col("Question")] = f"{cells[table.col('Question')]} ({extra})"
    cells[table.col("Answer")] = ""
    cells[table.col("Answered at")] = ""
    cells[table.col("State")] = "open"
    lines[index] = format_row(cells)
    set_field(lines, "Last updated", f"{stamp(at)} by {by}")
    write_lines(path, lines)
    return f"{period} {row_id}: open"
