#!/usr/bin/env python3
"""Check that a set of reports quote the same figure for the same metric and period.

Input is a claim ledger: a CSV with one row per figure quoted in a report, with the columns
file, period, metric, value and, optionally, location (page, slide or cell). Values are read
as printed: "$1.2M", "(450)", "(74)k" and "-3,100" are all understood.

For each metric it prints a table of period by file and the spread per period (largest
value minus smallest). A finding is raised when a period's spread is above --tolerance
(default $1), when a file quotes the metric for some periods but not this one, or when a
value cannot be read. Exit 0 when everything ties, 1 on any finding, 2 when the ledger
cannot be used.

    python3 report_tieout.py tieout-ledger.csv --metric "Consolidated EBITDA" --tolerance 500
    python3 report_tieout.py tieout-ledger.csv --format json
"""

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

REQUIRED = ["file", "period", "metric", "value"]
SUFFIX = {"k": 1e3, "m": 1e6, "mm": 1e6, "b": 1e9, "bn": 1e9}


def parse_value(raw):
    """A printed figure as a number, or None when it is not one."""
    s = str(raw or "").strip().lower().replace("$", "").replace(",", "").replace(" ", "")
    s = s.replace("−", "-")  # the typographic minus sign
    if not s:
        return None
    # Parentheses mean negative, and decks print both "(74)k" and "(74k)".
    negative = s.startswith("-") or (s.startswith("(") and (
        s.endswith(")") or re.search(r"\)(k|mm|m|bn|b)$", s) is not None))
    s = s.replace("(", "").replace(")", "").lstrip("-")
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(k|mm|m|bn|b)?", s)
    if not match:
        return None
    value = float(match.group(1)) * SUFFIX.get(match.group(2) or "", 1.0)
    return -value if negative else value


def tieout(rows, metric, tolerance):
    """Line the figures up by metric, period and file and list every disagreement."""
    figures = {}   # metric -> period -> file -> value
    where = {}     # (metric, period, file) -> location
    findings = []
    for row in rows:
        name = row["metric"].strip()
        if metric and name.lower() != metric.lower():
            continue
        period, file = row["period"].strip(), row["file"].strip()
        value = parse_value(row["value"])
        if value is None:
            findings.append({"check": "unparsed", "file": row["file"], "period": row["period"],
                             "metric": name, "value": row["value"],
                             "detail": f"could not read value {row['value']!r}"})
            continue
        figures.setdefault(name, {}).setdefault(period, {})[file] = value
        where[(name, period, file)] = (row.get("location") or "").strip()
    if not figures:
        raise ValueError(f"no rows for metric {metric!r}" if metric else "ledger has no parseable rows")

    matrices = {}
    found = []
    for name, periods in figures.items():
        files = sorted({f for values in periods.values() for f in values})
        table = []
        for period in sorted(periods):
            values = periods[period]
            present = [values[f] for f in files if f in values]
            spread = max(present) - min(present)
            table.append({"period": period, **{f: values.get(f) for f in files}, "spread": round(spread, 2)})
            if spread > tolerance:
                detail = ", ".join(
                    f"{f} {values[f]:,.0f}" + (f" ({where[(name, period, f)]})" if where[(name, period, f)] else "")
                    for f in files if f in values)
                found.append({"check": "disagree", "metric": name, "period": period,
                              "spread": round(spread, 2), "detail": detail})
            missing = [f for f in files if f not in values]
            if missing:
                found.append({"check": "missing", "metric": name, "period": period,
                              "detail": f"not quoted in {', '.join(missing)}"})
        matrices[name] = {"files": files, "rows": table}
    findings = found + findings  # unreadable values are listed last
    return {"metrics": matrices, "findings": findings, "tolerance": tolerance, "passed": not findings}


def read_ledger(path):
    text = Path(path).expanduser().read_text(encoding="utf-8").removeprefix("\ufeff")  # drop the byte-order mark Excel writes
    # newline="" keeps a line break or form feed inside a quoted cell part of that cell.
    rows = list(csv.DictReader(io.StringIO(text, newline="")))
    if not rows:
        raise ValueError("ledger is empty")
    missing = [c for c in REQUIRED if c not in rows[0]]
    if missing:
        raise ValueError(f"ledger needs columns {', '.join(missing)}; present: {', '.join(rows[0].keys())}")
    return rows


def print_text(result):
    for name, m in result["metrics"].items():
        print(name)
        print("  " + f"{'period':10}" + "".join(f"{f[:18]:>20}" for f in m["files"]) + f"{'spread':>12}")
        for row in m["rows"]:
            cells = "".join(f"{row[f]:>20,.0f}" if row.get(f) is not None else f"{'-':>20}" for f in m["files"])
            flag = "  <--" if row["spread"] > result["tolerance"] else ""
            print(f"  {row['period']:10}{cells}{row['spread']:>12,.0f}{flag}")
    for f in result["findings"]:
        print(f"  {f['check'].upper():9} {f.get('metric', ''):24} {f.get('period', ''):10} {f['detail']}")
    print("ALL TIE" if result["passed"] else f"{len(result['findings'])} FINDINGS")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Line reports up by period and metric; exit 1 if any disagree.")
    parser.add_argument("ledger", help="the claim ledger CSV (file, period, metric, value, location)")
    parser.add_argument("--metric", default="", help="only this metric (default: every metric in the ledger)")
    parser.add_argument("--tolerance", type=float, default=1.0, help="largest spread between files that still ties")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    try:
        result = tieout(read_ledger(args.ledger), args.metric or None, args.tolerance)
    except (OSError, ValueError) as exc:
        print(f"report-tieout: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(result, indent=1))
    else:
        print_text(result)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
