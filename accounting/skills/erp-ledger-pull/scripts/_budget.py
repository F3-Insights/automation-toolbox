"""Table helpers budget_detail_diff.py reads its inputs with (moved here from month-end-flux).

A pull is a JSON file, either {"meta": {...}, "rows": [...]} or a bare list of rows; an
upload sheet is a CSV file, a JSON list or JSON {"rows": [...]}. Standard library only.
"""

import calendar
import csv
import io
import json
from pathlib import Path


def money(value):
    """An amount as a number; blank or absent is zero."""
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).replace(",", "").replace("$", ""))


def load_pull(path):
    """The rows of a pull, in either file shape."""
    path = Path(path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"pull not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8").removeprefix("﻿"))
    if isinstance(data, dict):
        return list(data.get("rows") or [])
    if isinstance(data, list):
        return data
    raise ValueError(f"{path}: expected a list of rows or a {{meta, rows}} object")


def load_table(path):
    """Rows from a CSV file, a JSON list, or JSON {rows: [...]}."""
    path = Path(path).expanduser()
    if path.suffix.lower() == ".csv":
        # newline="" keeps a line break or form feed inside a quoted cell part of that cell.
        text = path.read_text(encoding="utf-8").removeprefix("﻿")
        return list(csv.DictReader(io.StringIO(text, newline="")))
    data = json.loads(path.read_text(encoding="utf-8").removeprefix("﻿"))
    if isinstance(data, dict):
        data = data.get("rows") or data.get("transactions") or []
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a list of rows")
    return [dict(r) for r in data]


def reporting_period_month(label):
    """'Month Ended March 2026' -> '2026-03'; anything else -> ''."""
    parts = str(label or "").split()
    if len(parts) < 4 or parts[0] != "Month" or parts[1] != "Ended":
        return ""
    names = [calendar.month_name[i].lower() for i in range(1, 13)]
    try:
        return f"{int(parts[3]):04d}-{names.index(parts[2].lower()) + 1:02d}"
    except (ValueError, IndexError):
        return ""
