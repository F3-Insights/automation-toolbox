"""The facts set: every figure and table the weekly report prints, none of them from a model.

A facts set is one JSON file (schema "report-facts/1") holding a period, `figures` and
`tables`. Every figure carries a source, an as-of date and a status (preliminary or final);
one the week could not produce is null with a reason, so the report says "not available"
rather than printing a zero.

Two kinds of table. A **supplied** table is whatever the executive pasted (CSV, a Markdown pipe
table, or tab-separated cells from a spreadsheet), stored verbatim; nothing is computed over it.
A **computed** table is built from a CSV of base columns (actual, budget, forecast per row) and
this file computes the variances, the variance percentages, the percent-of-revenue lines and
checks that each subtotal foots, with Decimal arithmetic under one declared rounding rule.

The writer never types a table: it places `{{table:<key>}}` and report_render.py puts the
rendered table there. `tie_out` checks that every number in a bullet under a table marker, or on
a line citing `facts://<key>`, is a number the set holds at the precision the prose used.
"""

import csv
import io
import re
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from _common import (ANY_BULLET, ISO_DATE, REFERENCE, SLASH_DATE, TEXT_DATE, YEAR, Fail,
                     header_of, read_json, read_text, readable_figures, write_json)

SCHEMA = "report-facts/1"
STATUSES = ("preliminary", "final")
UNITS = ("usd", "percent", "pp", "days", "count", "ratio", "text")
NOT_SUPPLIED = "not supplied"
SUPPLIED_SOURCE = "supplied by the executive"
TABLE_MARKER = re.compile(r"\{\{table:\s*([A-Za-z0-9_.\-]+)\s*\}\}")
ROUNDING = "amounts to the dollar and percentages to one decimal place, half away from zero"
BASE = (("actual", "Actual"), ("budget", "Budget"), ("forecast", "Forecast"))
COLUMNS = (("actual", "Actual"), ("budget", "Budget"), ("vs_budget", "vs Budget"),
           ("vs_budget_pct", "vs Budget %"), ("forecast", "Forecast"),
           ("vs_forecast", "vs Forecast"), ("vs_forecast_pct", "vs Forecast %"))
VARIANCES = (("vs_budget", "vs_budget_pct", "budget"), ("vs_forecast", "vs_forecast_pct", "forecast"))
TOLERANCE = Decimal("0.01")


# --------------------------------------------------------------------------- numbers

def parse_number(raw):
    """`1,187,400`, `(62,600)`, `$1.2M` and `-5.0%` as a Decimal, or None. Never rounds."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float, Decimal)):
        return Decimal(str(raw))
    text = str(raw).strip()
    negative = text.startswith("(") and text.endswith(")")
    text = re.sub(r"[$£€,%]", "", text.strip("()")).strip()
    hit = re.fullmatch(r"(?i)(-?\d+(?:\.\d+)?)\s*(k|thousand|mm|m|million|bn|b|billion)?", text)
    if not hit:
        return None
    scale = {"k": 1000, "thousand": 1000, "m": 10**6, "mm": 10**6, "million": 10**6,
             "b": 10**9, "bn": 10**9, "billion": 10**9}.get((hit.group(2) or "").casefold(), 1)
    value = Decimal(hit.group(1)) * scale
    return -value if negative else value


def quantise(value, unit):
    if value is None:
        return None
    step = Decimal("0.1") if unit in ("percent", "pp", "ratio") else Decimal("1")
    return float(value.quantize(step, rounding=ROUND_HALF_UP))


# --------------------------------------------------------------------------- the set

def empty_set(period, metrics=()):
    """A facts set with every standing metric present and unanswered (value null)."""
    figures = {}
    for metric in metrics:
        key = str(metric.get("facts_key") or metric.get("key") or "").strip()
        if key:
            figures[key] = {"key": key, "label": str(metric.get("name") or key), "value": None,
                            "unit": None, "source": None, "as_of": None, "status": "preliminary",
                            "supplied_by": None, "reason": NOT_SUPPLIED}
    return {"schema": SCHEMA, "period": period,
            "generated": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "figures": figures, "tables": {}}


def load_set(path):
    data = read_json(path, "facts set")
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise Fail(f"{path} is not a {SCHEMA} facts set")
    data.setdefault("figures", {})
    data.setdefault("tables", {})
    return data


def save_set(path, facts):
    return write_json(path, facts)


def set_figure(facts, key, *, label="", value=None, unit="usd", source="", as_of="", status="",
               supplied_by="", reason=""):
    """Record one figure. Source, as-of date and status are required, by design."""
    if not key.strip():
        raise Fail("a figure needs a key")
    if not as_of.strip():
        raise Fail(f"{key} needs an as-of date")
    if status not in STATUSES:
        raise Fail(f"{key} needs a status of preliminary or final")
    if unit not in UNITS:
        raise Fail(f"{key} carries the unit {unit!r}, which is not one of {', '.join(UNITS)}")
    if not source.strip():
        raise Fail(f"{key} needs a source")
    given = value is not None and str(value).strip() != ""
    parsed = parse_number(value) if given else None
    if given and parsed is None and unit != "text":
        raise Fail(f"{key}: {value!r} could not be read as a number")
    record = {"key": key, "label": label or (facts["figures"].get(key) or {}).get("label") or key,
              "value": str(value) if unit == "text" and given and parsed is None
              else (float(parsed) if parsed is not None else None),
              "unit": unit, "source": source.strip(), "as_of": as_of.strip(), "status": status,
              "supplied_by": supplied_by or None}
    if record["value"] is None:
        record["reason"] = reason.strip() or NOT_SUPPLIED
    facts["figures"][key] = record
    return record


def flat_figures(facts):
    """The figures as {key: {value, as_of, source, unit, status}}, what the pack carries."""
    return {k: {"value": r.get("value"), "as_of": r.get("as_of"), "source": r.get("source"),
                "unit": r.get("unit"), "status": r.get("status"),
                **({"reason": r.get("reason") or NOT_SUPPLIED} if r.get("value") is None else {})}
            for k, r in (facts.get("figures") or {}).items()}


def validate_set(facts):
    errors, warnings = [], []
    if facts.get("schema") != SCHEMA:
        errors.append({"kind": "SCHEMA", "key": None, "detail": f"the file does not declare {SCHEMA}"})
    if not str(facts.get("period") or "").strip():
        errors.append({"kind": "NO_PERIOD", "key": None, "detail": "the set names no period"})
    for key, r in (facts.get("figures") or {}).items():
        if r.get("value") is None:
            warnings.append({"kind": "NOT_SUPPLIED", "key": key,
                             "detail": f"{key} has no value: {r.get('reason') or NOT_SUPPLIED}; it "
                                       f"reads as not available this week"})
            continue
        for field, kind in (("source", "NO_SOURCE"), ("as_of", "NO_AS_OF")):
            if not str(r.get(field) or "").strip():
                errors.append({"kind": kind, "key": key, "detail": f"{key} carries a value and no {field}"})
        if r.get("status") not in STATUSES:
            errors.append({"kind": "NO_STATUS", "key": key, "detail": f"{key} is neither preliminary nor final"})
        if r.get("unit") not in UNITS:
            errors.append({"kind": "BAD_UNIT", "key": key, "detail": f"{key} carries the unit {r.get('unit')!r}"})
    for key, t in (facts.get("tables") or {}).items():
        for field, kind in (("source", "NO_SOURCE"), ("as_of", "NO_AS_OF")):
            if not str(t.get(field) or "").strip():
                errors.append({"kind": kind, "key": key, "detail": f"table {key} carries no {field}"})
        if t.get("status") not in STATUSES:
            errors.append({"kind": "NO_STATUS", "key": key, "detail": f"table {key} is neither preliminary nor final"})
        errors += footing_errors(key, t)
    figures = facts.get("figures") or {}
    return {"errors": errors, "warnings": warnings,
            "stats": {"figures": len(figures), "tables": len(facts.get("tables") or {}),
                      "figures_supplied": len([r for r in figures.values() if r.get("value") is not None]),
                      "errors": len(errors), "warnings": len(warnings)}}


# --------------------------------------------------------------------------- tables

def table_header(title, source, as_of, status):
    if status not in STATUSES:
        raise Fail("a table needs a status of preliminary or final")
    if not as_of.strip():
        raise Fail("a table needs an as-of date")
    if not source.strip():
        raise Fail("a table needs a source")


def read_pasted(text):
    """A pasted table as a grid of cells, header row first: a pipe table, tab-separated cells,
    or CSV, decided by the content. Ragged rows are padded, nothing is dropped."""
    lines = [line for line in str(text or "").splitlines() if line.strip()]
    if any(line.strip().startswith("|") for line in lines):
        grid = [[c.strip() for c in line.strip().strip("|").split("|")] for line in lines
                if line.strip().startswith("|")]
        grid = [r for r in grid if not all(re.fullmatch(r":?-+:?", c) for c in r if c)]
    elif any("\t" in line for line in lines):
        grid = [[c.strip() for c in line.split("\t")] for line in lines]
    else:
        grid = [[c.strip() for c in row] for row in csv.reader(lines)]
    grid = [r for r in grid if any(r)]
    if not grid:
        raise Fail("there is no table here: give a CSV, a pipe table or tab-separated cells, "
                   "with the header row first")
    width = max(len(r) for r in grid)
    return [r + [""] * (width - len(r)) for r in grid]


def supplied_table(grid, *, key, title, source, as_of, status):
    table_header(title, source, as_of, status)
    header, keys = grid[0], [f"c{i}" for i in range(1, len(grid[0]) + 1)]
    rows = [{"key": f"row_{n}", "label": raw[0], "type": "amount", "level": 0,
             "cells": {k: {"text": c, "value": float(v) if (v := parse_number(c)) is not None else None}
                       for k, c in zip(keys, raw)}} for n, raw in enumerate(grid[1:], 1)]

    def align(k):
        filled = [r["cells"][k]["text"] for r in rows if r["cells"][k]["text"].strip()]
        numeric = len([c for c in filled if parse_number(c) is not None])
        return "right" if filled and numeric * 2 > len(filled) else "left"

    return {"key": key, "title": title or key, "kind": "supplied", "row_header": header[0],
            "row_header_key": keys[0], "row_header_align": align(keys[0]),
            "columns": [{"key": k, "label": h, "align": align(k)} for k, h in zip(keys[1:], header[1:])],
            "rows": rows, "source": source, "as_of": as_of, "status": status, "rounding": None,
            "currency": None}


def computed_table(path, *, key, title, source, as_of, status, revenue_row="Revenue", row_header="Line"):
    """A results table from a CSV of base columns: row, type (amount or subtotal), components
    (for a subtotal, signed and `;` separated, like `Revenue;-COGS`), favourable (higher or
    lower), percent_of_revenue (yes or no), actual, budget, forecast."""
    table_header(title, source, as_of, status)
    target = Path(path).expanduser()
    if not target.is_file():
        raise Fail(f"no table CSV at {target}")
    reader = csv.DictReader(io.StringIO(read_text(target)))
    heads = {str(h or "").strip().casefold() for h in reader.fieldnames or []}
    missing = [h for h in ("row", "type", "favourable") if h not in heads]
    if missing:
        raise Fail(f"{target} has no {missing[0]!r} column; the columns are row, type, components, "
                   f"favourable, percent_of_revenue, actual, budget, forecast")
    entries, base = [], {}
    for raw in reader:
        row = {str(k or "").strip().casefold(): str(v or "").strip() for k, v in raw.items()}
        label = row.get("row", "")
        if not label:
            continue
        kind = row.get("type", "").casefold() or "amount"
        if kind not in ("amount", "subtotal"):
            raise Fail(f"{label}: the row type {kind!r} is neither amount nor subtotal")
        if row.get("favourable", "").casefold() not in ("higher", "lower"):
            raise Fail(f"{label} carries no favourable direction (higher or lower)")
        values = {}
        for column, _ in BASE:
            values[column] = parse_number(row.get(column)) if row.get(column) else None
            if row.get(column) and values[column] is None:
                raise Fail(f"{label}: {row[column]!r} in {column} is not a number")
        parts = []
        for part in filter(None, (p.strip() for p in row.get("components", "").split(";"))):
            parts.append((-1, part[1:].strip()) if part.startswith("-") else (1, part.lstrip("+").strip()))
        base[label.casefold()] = values
        entries.append({"label": label, "type": kind, "parts": parts,
                        "favourable": row["favourable"].casefold(),
                        "pct": row.get("percent_of_revenue", "").casefold() in ("yes", "y", "true", "1")})
    if not entries:
        raise Fail(f"{target} holds no rows")
    for e in entries:
        for column, name in BASE:
            total = base[e["label"].casefold()][column]
            if e["type"] != "subtotal" or not e["parts"] or total is None:
                continue
            if any(n.casefold() not in base for _, n in e["parts"]):
                raise Fail(f"{e['label']} foots to a row that is not in this table")
            if any(base[n.casefold()][column] is None for _, n in e["parts"]):
                continue
            running = sum(Decimal(s) * base[n.casefold()][column] for s, n in e["parts"])
            if abs(running - total) > TOLERANCE:
                raise Fail(f"{e['label']} does not foot in {name}: the file says {total:,} and its "
                           f"components come to {running:,}")
    revenue, rows = base.get(revenue_row.casefold()), []
    for e in entries:
        values, cells = base[e["label"].casefold()], {}
        for column, _ in BASE:
            cells[column] = {"value": quantise(values[column], "usd"), "unit": "usd"}
        better = lambda d: d >= 0 if e["favourable"] == "higher" else d <= 0  # noqa: E731
        for variance, percent, against in VARIANCES:
            actual, other = values["actual"], values[against]
            if actual is None or other is None:
                cells[variance], cells[percent] = {"value": None, "unit": "usd"}, {"value": None, "unit": "percent"}
                continue
            diff = actual - other
            cells[variance] = {"value": quantise(diff, "usd"), "unit": "usd", "favourable": better(diff)}
            cells[percent] = ({"value": None, "unit": "percent", "reason": "the comparison is zero"} if other == 0
                              else {"value": quantise(diff / abs(other) * 100, "percent"), "unit": "percent",
                                    "favourable": better(diff)})
        rows.append({"key": re.sub(r"[^a-z0-9]+", "_", e["label"].casefold()).strip("_"), "label": e["label"],
                     "type": e["type"], "level": 0,
                     "components": [f"{'-' if s < 0 else ''}{n}" for s, n in e["parts"]], "cells": cells})
        if not e["pct"] or revenue is None:
            continue
        shares = {c: (values[c] / revenue[c] * 100 if values[c] is not None and revenue[c] else None)
                  for c, _ in BASE}
        pct = {c: {"value": quantise(shares[c], "percent"), "unit": "percent"} for c, _ in BASE}
        for variance, percent, against in VARIANCES:
            a, b = shares["actual"], shares[against]
            pct[variance] = ({"value": None, "unit": "pp"} if a is None or b is None
                             else {"value": quantise(a - b, "pp"), "unit": "pp", "favourable": better(a - b)})
            pct[percent] = {"value": None, "unit": "percent", "reason": "a percent line carries points"}
        rows.append({"key": f"{rows[-1]['key']}__percent_of_revenue", "label": "% of revenue",
                     "type": "percent_of_revenue", "level": 1, "components": [], "cells": pct})
    return {"key": key, "title": title or key, "kind": "computed", "row_header": row_header,
            "row_header_align": "left",
            "columns": [{"key": k, "label": label, "align": "right"} for k, label in COLUMNS],
            "rows": rows, "source": source, "as_of": as_of, "status": status, "rounding": ROUNDING,
            "revenue_row": revenue_row, "currency": "dollars"}


def footing_errors(key, table):
    """Every subtotal of a computed table still foots to its components, on stored values."""
    out = []
    by_label = {r["label"].casefold(): r for r in table.get("rows") or [] if r.get("type") != "percent_of_revenue"}
    for row in table.get("rows") or []:
        if row.get("type") != "subtotal" or not row.get("components"):
            continue
        for column, name in BASE:
            total = parse_number((row["cells"].get(column) or {}).get("value"))
            parts = [(-1 if c.startswith("-") else 1,
                      parse_number(((by_label.get(c.lstrip("+-").casefold()) or {}).get("cells") or {})
                                   .get(column, {}).get("value"))) for c in row["components"]]
            if total is None or any(v is None for _, v in parts):
                continue
            running = sum(Decimal(s) * v for s, v in parts)
            if abs(running - total) > TOLERANCE:
                out.append({"kind": "DOES_NOT_FOOT", "key": key,
                            "detail": f"{key}: {row['label']} shows {total:,} in {name} and its "
                                      f"components come to {running:,}"})
    return out


def format_cell(cell):
    """A supplied cell prints as pasted; a computed one with separators, negatives in brackets."""
    cell = cell or {}
    if "text" in cell:
        return str(cell.get("text") or "")
    if cell.get("value") is None:
        return ""
    number = Decimal(str(cell["value"]))
    unit = cell.get("unit") or "usd"
    text = (f"{abs(number):,.1f}%" if unit == "percent" else f"{abs(number):,.1f} pp" if unit == "pp"
            else f"{abs(number):,.0f}")
    return f"({text})" if number < 0 else text


def render_markdown(table, proportional=False):
    """A pipe table, figures right-aligned, percent lines indented and italic, caption under it.

    With `proportional` the rule under the header is sized to each column's widest cell, which
    is how pandoc's Word writer decides column widths."""
    columns = table.get("columns") or []
    header = [str(table.get("row_header") or "Line")] + [str(c.get("label")) for c in columns]
    body = []
    for row in table.get("rows") or []:
        label = row.get("label") or ""
        if row.get("type") == "percent_of_revenue":
            label = f"  *{label}*"
        elif row.get("type") == "subtotal":
            label = f"**{label}**"
        body.append([label] + [format_cell((row.get("cells") or {}).get(c["key"])) for c in columns])
    aligns = [table.get("row_header_align") or "left"] + [c.get("align") or "right" for c in columns]
    widths = [max([len(header[i].replace("*", ""))] + [len(r[i].replace("*", "")) for r in body]) if proportional
              else 3 for i in range(len(header))]
    rule = "|" + "|".join(f":{'-' * max(w, 3)}" if a == "left" else f"{'-' * max(w, 3)}:"
                          for a, w in zip(aligns, widths)) + "|"
    caption = ". ".join(p for p in (str(table.get("title") or table.get("key")).rstrip("."),
                                    f"Amounts in {table['currency']}" if table.get("currency") else "",
                                    f"Source: {table.get('source')}", f"As of {table.get('as_of')}",
                                    str(table.get("status") or "").capitalize()) if p) + "."
    return "\n".join(["| " + " | ".join(header) + " |", rule]
                     + ["| " + " | ".join(r) + " |" for r in body] + ["", f"*{caption}*"])


# --------------------------------------------------------------------------- the tie-out

PROSE_FIGURE = re.compile(r"(?<![\w.])(?P<currency>[$£€])?\s?(?P<number>\d[\d,]*(?:\.\d+)?)"
                          r"\s*(?P<scale>thousand|million|billion|mm|bn|[kmb])?(?P<percent>\s?%)?(?![\w])",
                          re.IGNORECASE)
SCALES = {"": 1, "k": 1000, "thousand": 1000, "m": 10**6, "mm": 10**6, "million": 10**6,
          "b": 10**9, "bn": 10**9, "billion": 10**9}


def prose_figures(line):
    """Every figure on a line with the precision the prose used: "$1.2M" is a claim to the
    nearest hundred thousand, so it is satisfied by 1,187,400."""
    text = readable_figures(line)
    for pattern in (ISO_DATE, SLASH_DATE, TEXT_DATE, YEAR, TABLE_MARKER, REFERENCE):
        text = pattern.sub(" ", text)
    out = []
    for hit in PROSE_FIGURE.finditer(text):
        raw = hit.group("number")
        scale = Decimal(SCALES[(hit.group("scale") or "").casefold()])
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        out.append({"text": hit.group(0).strip(), "value": Decimal(raw.replace(",", "")) * scale,
                    "quantum": scale / (Decimal(10) ** decimals)})
    return out


def matches(candidate, figure):
    """Equal in magnitude after rounding both to the prose's precision (signs are words)."""
    q = figure["quantum"]
    return (abs(candidate) / q).quantize(Decimal(1), ROUND_HALF_UP) == \
        (abs(figure["value"]) / q).quantize(Decimal(1), ROUND_HALF_UP)


def table_values(table):
    return [v for r in table.get("rows") or [] for c in (r.get("cells") or {}).values()
            if (v := parse_number((c or {}).get("value"))) is not None]


def tie_out(report_text, facts):
    """FIGURE_NOT_IN_FACTS and UNKNOWN_TABLE findings for the explained lines of a report."""
    findings, tables, current = [], facts.get("tables") or {}, None
    for number, line in enumerate(str(report_text or "").splitlines(), 1):
        marker = TABLE_MARKER.search(line)
        if marker:
            current = marker.group(1)
            continue
        if header_of(line) is not None or re.match(r"^\s*#{1,6}\s", line):
            current = None
            continue
        cited = re.findall(r"facts://([A-Za-z0-9_.\-]+)", line)
        under = bool(current) and bool(ANY_BULLET.match(line))
        if not cited and not under:
            continue
        if under and current not in tables:
            findings.append({"kind": "UNKNOWN_TABLE", "line": number, "text": line.strip()[:200],
                             "detail": f"this bullet sits under {{{{table:{current}}}}} and the facts "
                                       f"set holds no table {current}"})
            continue
        candidates, where = [], []
        for key in ([current] if under else []) + cited:
            if key in tables:
                candidates += table_values(tables[key])
                where.append(f"the table {key}")
            else:
                value = parse_number(((facts.get("figures") or {}).get(key) or {}).get("value"))
                candidates += [value] if value is not None else []
                where.append(f"facts://{key}")
        where = list(dict.fromkeys(where))
        for figure in prose_figures(line):
            if not any(matches(v, figure) for v in candidates):
                findings.append({"kind": "FIGURE_NOT_IN_FACTS", "line": number, "text": line.strip()[:200],
                                 "detail": f"{figure['text']} is in none of {', '.join(where)}; a figure "
                                           f"matches when equal at the precision the prose used"})
    return findings
