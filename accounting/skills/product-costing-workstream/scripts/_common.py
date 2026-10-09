"""Helpers the product-costing scripts share: owner settings, reading CSV files Excel
wrote, numbers from messy cells, the file hash, and the cost-model layout file with the
two parsers that read a per-finished-good P&L workbook through it.

The layout file is JSON. It says where things sit in one client's cost model, because
every client lays the workbook out differently:

    {
      "month_tab": "P&L by month",       tab with one row per product, a block per month
      "ytd_tab": "P&L YTD",               optional, the same shape with year-to-date blocks
      "tb_tab": "Trial balance",          trial-balance tab (matched by prefix)
      "alloc_tab": "Allocation",          optional, the tab costmodel-audit checks formulas on
      "first_row": 4,                     first data row on every tab (1-based)
      "info_columns": {"customer_group": 0, "product_fg": 1, "description": 2},
      "block_start": 6,                   0-based column where the first period block begins
      "block_width": 12,                  columns per period block
      "block_fields": ["sales_qty", "sales_amount", "prod_qty", "std_dm", "var_dm", ...],
      "periods": 12,
      "tb_columns": {"category": 0, "subcategory": 2, "description": 4},
      "tb_first_amount_col": 5,           0-based column of month 1 on the TB tab
      "revenue_category": "Revenue"
    }

`block_fields` lists the fields of one period block in column order; it must include
`sales_amount`, `total_cost`, `cm` and `cm_pct`, and each cost component as a
`std_<x>` and `var_<x>` pair (for example `std_dm`, `var_dm`).
"""

import codecs
import csv
import hashlib
import io
import json
import os
import sys
import tomllib
from pathlib import Path

SKILL = "product-costing-workstream"
ERRS = {"#N/A", "#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#NULL!", "#NUM!"}
REQUIRED_LAYOUT = ["month_tab", "tb_tab", "first_row", "info_columns", "block_start", "block_width", "block_fields", "tb_columns", "tb_first_amount_col"]
REQUIRED_FIELDS = ["sales_amount", "total_cost", "cm", "cm_pct"]


def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


def fail(message, code=1):
    """Print one line to stderr and stop."""
    print(message, file=sys.stderr)
    sys.exit(code)


def open_csv_text(path):
    """A text handle over a CSV file with any byte-order mark Excel wrote dropped."""
    data = Path(path).expanduser().read_bytes()
    if data.startswith(codecs.BOM_UTF8):
        data = data[len(codecs.BOM_UTF8):]
    return io.StringIO(data.decode("utf-8"), newline="")


def num(value, default=None):
    """A float from a cell, or `default` for blanks, Excel error values and text."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text or text in ERRS:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def text(value):
    """A stripped string, or None for a blank cell."""
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_layout(layout_path, overrides):
    """The cost-model layout from --layout or the `cost_model_layout` setting, with any
    tab names given on the command line laid over it. Exit 2 when there is none."""
    path = layout_path or settings(SKILL).get("cost_model_layout")
    if not path:
        fail(f"No cost-model layout: pass --layout or set cost_model_layout in [{SKILL}] of the owner settings", 2)
    try:
        layout = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        fail(f"Could not read the layout file {path}: {exc}", 2)
    layout.update({k: v for k, v in overrides.items() if v})
    missing = [k for k in REQUIRED_LAYOUT if k not in layout]
    missing += [f"block_fields:{f}" for f in REQUIRED_FIELDS if f not in layout.get("block_fields", [])]
    if "product_fg" not in layout.get("info_columns", {}):
        missing.append("info_columns:product_fg")
    if "category" not in layout.get("tb_columns", {}):
        missing.append("tb_columns:category")
    if missing:
        fail(f"The layout file is missing {', '.join(missing)}", 2)
    layout.setdefault("periods", 12)
    layout.setdefault("revenue_category", "Revenue")
    return layout


def cell(row, i):
    return row[i] if i is not None and i < len(row) else None


def parse_product_tab(ws, basis, year, layout):
    """One row per product per loaded period from the per-product P&L tab.

    A row with no product and no customer group is a subtotal or a blank and is skipped.
    A period block that is all blank or zero was not loaded and is skipped. A product with
    revenue and no standard cost is `cost_pending` and its margin percentages are null,
    never 0% or 100%."""
    info, fields = layout["info_columns"], layout["block_fields"]
    start0, width = layout["block_start"], layout["block_width"]
    rows = []
    for r in ws.iter_rows(min_row=layout["first_row"], values_only=True):
        r = list(r)
        rec = {name: text(cell(r, i)) for name, i in info.items()}
        if not rec.get("product_fg") and not rec.get("customer_group"):
            continue
        for b in range(layout["periods"]):
            start = start0 + width * b
            if start >= len(r):
                break
            block = {f: num(cell(r, start + off)) for off, f in enumerate(fields)}
            if all(v in (None, 0.0) for v in block.values()):
                continue
            revenue, cost = block.get("sales_amount") or 0.0, block.get("total_cost") or 0.0
            block["cost_pending"] = bool(revenue and not cost)
            if block["cost_pending"]:
                block["cm_pct"] = None
                if "gp_pct" in block:
                    block["gp_pct"] = None
            rows.append({**rec, "basis": basis, "year": year, "month_no": b + 1, **block})
    return rows


def parse_tb(ws, year, layout):
    """One row per trial-balance line per month. A category cell carries down to the
    lines under it until the next category."""
    cols, first = layout["tb_columns"], layout["tb_first_amount_col"]
    rows, category = [], None
    for r in ws.iter_rows(min_row=layout["first_row"], values_only=True):
        r = list(r)
        cat, sub, desc = text(cell(r, cols.get("category"))), text(cell(r, cols.get("subcategory"))), text(cell(r, cols.get("description")))
        if cat:
            category = cat
        if not (cat or sub or desc):
            continue
        for m in range(layout["periods"]):
            amount = num(cell(r, first + m))
            if amount is not None:
                rows.append({"category": category, "subcategory": sub, "description": desc, "year": year, "month_no": m + 1, "amount": amount})
    return rows


def find_tab(sheetnames, prefix):
    """The first tab whose name starts with `prefix`, ignoring case."""
    return next((t for t in sheetnames if t.lower().startswith(prefix.lower())), None)


def read_csv(path, label=None):
    """Rows of a CSV file as dicts. Raises ValueError when it cannot be read or is empty."""
    try:
        with open_csv_text(path) as fh:
            rows = list(csv.DictReader(fh))
    except OSError as exc:
        raise ValueError(f"Could not read {path}: {exc}") from exc
    if not rows:
        raise ValueError(f"{label or path} is empty")
    return rows


def require(rows, colmap, keys, label):
    """Raise a DATA REQUEST naming the columns a file lacks."""
    missing = [colmap[k] for k in keys if colmap[k] not in rows[0]]
    if missing:
        raise ValueError(f"DATA REQUEST: {label} needs columns {', '.join(missing)}. Present: {', '.join(rows[0].keys())}. Or pass --map.")


def parse_map(mapping, keys):
    """'product=Part No,month=Period' -> {'product': 'Part No', 'month': 'Period'}."""
    out = {}
    for part in filter(None, (s.strip() for s in mapping.split(","))):
        if "=" not in part:
            raise ValueError(f"--map entries are key=Header, got {part!r}")
        k, v = part.split("=", 1)
        if k not in keys:
            raise ValueError(f"unknown map key {k!r}; keys: {', '.join(keys)}")
        out[k] = v
    return out
