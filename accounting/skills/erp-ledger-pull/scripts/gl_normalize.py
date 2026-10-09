#!/usr/bin/env python3
# /// script
# dependencies = ["pyyaml"]
# ///
"""Map one accounting system's exports onto the standard ledger shape every finance tool reads.

Inputs: --system (intacct, or csv with --map), --period, --out, --lines (required) and any of
--headers, --ap-bills, --ap-bills-next, --ar-invoices. Each may be a CSV, a JSON list of rows
or a {meta, rows} snapshot.

Writes into --out one {meta, rows} file per input: gl-lines.json, je-headers.json (built from
the lines when no header export is given), ap-bills.json, ap-bills-next.json, ar-invoices.json.
meta carries system, period, pulled_at and server_total. A CSV carries no server count, so
server_total is null and server_total_reason says why; pulled_at is then the file's
modification time.

The standard fields:
  gl-lines     je_id, line_no, journal, date, posting_date, account, account_name, department,
               location, class, debit, credit, memo, description, state, created_at, created_by,
               reversed_from, vendor, customer
  je-headers   je_id, journal, date, description, state, reversed_from, reversed_by, created_by
               (optional je_number, schedule_id)
  documents    doc_id, date, posting_date, counterparty, account, department, location, amount,
               memo (optional account_name)

The map. --system intacct uses the map built in below. Any other system needs --map, a YAML
file kept with the client's files that names, for each standard field, the export's column:

    system: <label written into meta.system>
    date_format: "%m/%d/%Y"          # only for dates not already yyyy-mm-dd
    gl-lines:
      fields: {<standard name>: <column> | [<column>, <fallback column>], ...}
      amount: {debit: <col>, credit: <col>}          # or
              {signed: <col>}                        # debits positive, or
              {value: <col>, type: <col>, debit_if_starts_with: [d]}
      constants: {state: posted}     # fixed values for fields the export lacks
    je-headers: {fields: {...}, constants: {...}}
    ap-bills: {fields: {...}}        # ap-bills-next reads the same section
    ar-invoices: {fields: {...}}

Lines are joined to their headers on je_id and take the entry's description and reversal.
A header learns reversed_by when a later entry reverses it (same date as the child's
reversed_from and the same description once months and numbers are folded out).

Prints one summary line and the files written; exit 0, or 2 with a one-line reason.

Example:
    python3 gl_normalize.py --system csv --map gl-map.yaml --period 2026-08 --out ./standard \\
        --lines gl-detail.csv --ap-bills bills.csv
"""

from __future__ import annotations

import argparse
import codecs
import csv
import io
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from _common import money, server_total

LINE, HEADER, DOC = "line", "header", "doc"
FIELDS = {
    LINE: ("je_id", "line_no", "journal", "date", "posting_date", "account", "account_name", "department",
           "location", "class", "debit", "credit", "memo", "description", "state", "created_at", "created_by",
           "reversed_from", "vendor", "customer"),
    HEADER: ("je_id", "journal", "date", "description", "state", "reversed_from", "reversed_by", "created_by"),
    DOC: ("doc_id", "date", "posting_date", "counterparty", "account", "department", "location", "amount", "memo"),
}
OPTIONAL = {LINE: (), HEADER: ("je_number", "schedule_id"), DOC: ("account_name",)}
# Output file -> (map section, row kind). ap-bills-next shares the ap-bills section.
OUTPUTS = {"gl-lines": ("gl-lines", LINE), "je-headers": ("je-headers", HEADER), "ap-bills": ("ap-bills", DOC),
           "ap-bills-next": ("ap-bills", DOC), "ar-invoices": ("ar-invoices", DOC)}
DATE_FIELDS = {"date", "posting_date", "reversed_from"}

_DOC = {"department": "dimensions.department.id", "location": "dimensions.location.id", "amount": "baseAmount",
        "account": "glAccount.id", "account_name": "glAccount.name", "memo": "memo"}
INTACCT_MAP = {
    "system": "intacct",
    "gl-lines": {
        "fields": {"je_id": "journalEntry.key", "line_no": "id", "journal": "journalEntry.glJournal.id",
                   "date": "entryDate", "posting_date": "entryDate", "account": "glAccount.id",
                   "account_name": "glAccount.name", "department": "dimensions.department.id",
                   "location": "dimensions.location.id", "class": "dimensions.class.id", "memo": "description",
                   "state": ["journalEntry.state", "state"], "created_at": "audit.createdDateTime",
                   "created_by": "audit.createdBy", "vendor": "dimensions.vendor.id",
                   "customer": "dimensions.customer.id"},
        "amount": {"value": ["baseAmount", "txnAmount"], "type": "txnType", "debit_if_starts_with": ["d"]},
    },
    "je-headers": {"fields": {"je_id": ["key", "id"], "je_number": "id", "journal": "glJournal.id",
                              "date": "postingDate", "description": "description", "state": "state",
                              "reversed_from": "reversedFromDate", "created_by": "audit.createdBy",
                              "schedule_id": "scheduledOperationKey"}},
    "ap-bills": {"fields": {"doc_id": "bill.id", "date": "bill.postingDate", "posting_date": "bill.postingDate",
                            "counterparty": "vendor.name", **_DOC}},
    "ar-invoices": {"fields": {"doc_id": "invoice.id", "date": "invoice.invoiceDate",
                               "posting_date": "invoice.invoiceDate", "counterparty": "invoice.customer.name",
                               **_DOC}},
}


class Refused(Exception):
    """A bad map, input or argument (exit 2)."""


# --- the map ----------------------------------------------------------------------------------


def load_map(system, map_path=""):
    if not map_path:
        if system != "intacct":
            raise Refused(f"--system {system} needs --map: the client's field map YAML")
        return INTACCT_MAP
    path = Path(map_path).expanduser()
    if not path.is_file():
        raise Refused(f"--map points at a file that does not exist: {path}")
    import yaml  # only a custom map needs PyYAML

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise Refused(f"{path}: a map is a mapping of sections (gl-lines, je-headers, ...)")
    validate_map(data, path)
    data.setdefault("system", system)
    return data


def validate_map(data, where="map"):
    """Refuse a map that names a field the standard lacks, or gives the lines no single amount."""
    for section, kind in dict(OUTPUTS.values()).items():
        spec = data.get(section)
        if spec is None:
            continue
        named = set(spec.get("fields") or {}) | set(spec.get("constants") or {})
        unknown = sorted(named - set(FIELDS[kind]) - set(OPTIONAL[kind]))
        if unknown:
            raise Refused(f"{where}: {section} names fields the standard shape lacks: {', '.join(unknown)}")
        if kind == LINE and named & {"debit", "credit"}:
            raise Refused(f"{where}: gl-lines reads debit and credit under amount, not fields")
    lines = data.get("gl-lines")
    if lines is not None:
        amount = lines.get("amount") or {}
        forms = [bool(amount.get("debit") or amount.get("credit")), bool(amount.get("signed")),
                 bool(amount.get("value"))]
        if sum(forms) != 1:
            raise Refused(f"{where}: gl-lines.amount must use exactly one of debit/credit, signed, or value with type")
        if amount.get("value") and not amount.get("type"):
            raise Refused(f"{where}: gl-lines.amount.value needs a type column naming debit or credit")


# --- reading and mapping rows -----------------------------------------------------------------


def read_source(path):
    """(rows, meta) from a CSV (a byte-order mark is dropped), a JSON list or a snapshot."""
    path = Path(path).expanduser()
    if not path.is_file():
        raise Refused(f"input not found: {path}")
    if path.suffix.lower() == ".csv":
        data = path.read_bytes()
        text = data[len(codecs.BOM_UTF8):] if data.startswith(codecs.BOM_UTF8) else data
        return [dict(r) for r in csv.DictReader(io.StringIO(text.decode("utf-8"), newline=""))], {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return list(data.get("rows") or []), dict(data.get("meta") or {})
    if isinstance(data, list):
        return data, {}
    raise Refused(f"{path}: expected CSV, a list of rows, or a {{meta, rows}} snapshot")


def pick(row, source):
    """A column, or the first non-empty of a list of columns."""
    for column in [source] if isinstance(source, str) else list(source or []):
        if row.get(column) not in (None, ""):
            return row[column]
    return None


def to_date(value, date_format, where):
    if value in (None, ""):
        return None
    text = str(value).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", text):
        return text[:10]
    if not date_format:
        raise Refused(f"{where}: date {text!r} is not yyyy-mm-dd and the map gives no date_format")
    try:
        return datetime.strptime(text, date_format).date().isoformat()
    except ValueError:
        raise Refused(f"{where}: date {text!r} does not match date_format {date_format!r}") from None


def amounts(row, spec, where):
    """(debit, credit), both zero or positive, from whichever amount form the map uses."""
    try:
        if spec.get("signed"):
            value = money(pick(row, spec["signed"]))
            return (value, 0.0) if value >= 0 else (0.0, -value)
        if spec.get("value"):
            value = money(pick(row, spec["value"]))
            flags = tuple(str(p).lower() for p in spec.get("debit_if_starts_with") or ["d"])
            is_debit = str(pick(row, spec["type"]) or "").strip().lower().startswith(flags)
            if value < 0:  # a negative unsigned amount belongs on the other side
                value, is_debit = -value, not is_debit
            return (value, 0.0) if is_debit else (0.0, value)
        debit, credit = money(pick(row, spec.get("debit"))), money(pick(row, spec.get("credit")))
    except ValueError as exc:
        raise Refused(f"{where}: an amount is not a number ({exc})") from None
    if debit < 0 or credit < 0:  # a negative debit is a credit, and the reverse
        debit, credit = max(debit, 0.0) + max(-credit, 0.0), max(credit, 0.0) + max(-debit, 0.0)
    return debit, credit


def map_rows(rows, section, kind, date_format="", label="rows"):
    """Source rows to standard rows of one kind; every standard field is present."""
    columns, constants = dict(section.get("fields") or {}), dict(section.get("constants") or {})
    names = FIELDS[kind] + tuple(n for n in OPTIONAL[kind] if n in columns or n in constants)
    out = []
    for index, row in enumerate(rows, start=1):
        where = f"{label} row {index}"
        mapped = {}
        for name in names:
            if kind == LINE and name == "debit":
                debit, credit = amounts(row, section.get("amount") or {}, where)
                mapped["debit"], mapped["credit"] = round(debit, 2), round(credit, 2)
            if kind == LINE and name in ("debit", "credit"):
                continue
            value = pick(row, columns[name]) if name in columns else constants.get(name)
            if name in DATE_FIELDS:
                value = to_date(value, date_format, where)
            elif name == "amount":
                value = None if value is None else round(money(value), 2)
            elif value is not None:
                value = str(value).strip() or None
            mapped[name] = value
        out.append(mapped)
    return out


# --- entries ----------------------------------------------------------------------------------

MONTHS = ("JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER"
          "|JAN|FEB|MAR|APR|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC")


def description_key(text):
    """A description folded so that the same entry in another month matches: upper case, the
    reversal prefix dropped, month names and numbers replaced, punctuation squeezed."""
    body = re.sub(r"^REVERSED?\s*-\s*", "", str(text or ""), flags=re.I).upper()
    body = re.sub(rf"\b({MONTHS})\b", "<M>", body)
    body = re.sub(r"\d+([.,]\d+)*", "<N>", body)
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9<>]+", " ", body)).strip()


def join_headers(lines, headers):
    """Give each line its entry's description and reversal, and fill its blanks from the entry."""
    by_id = {h["je_id"]: h for h in headers if h.get("je_id")}
    for line in lines:
        head = by_id.get(line.get("je_id"))
        if head:
            for field, source in (("description", "description"), ("reversed_from", "reversed_from"),
                                  ("journal", "journal"), ("posting_date", "date"), ("state", "state")):
                line[field] = line.get(field) or head.get(source)


def headers_from_lines(lines):
    """One header per entry, from its first line, when the export has no headers."""
    first = {}
    for line in lines:
        if line.get("je_id"):
            first.setdefault(line["je_id"], line)
    return [{"je_id": je, "journal": x.get("journal"), "date": x.get("posting_date") or x.get("date"),
             "description": x.get("description") or x.get("memo"), "state": x.get("state"),
             "reversed_from": x.get("reversed_from"), "reversed_by": None, "created_by": x.get("created_by")}
            for je, x in first.items()]


def fill_reversed_by(headers):
    """A parent learns its reversal: dated on the child's reversed_from, with the same text."""
    parents = defaultdict(list)
    for head in headers:
        parents[(head.get("date"), description_key(head.get("description")))].append(head)
    for child in headers:
        if not child.get("reversed_from"):
            continue
        for parent in parents.get((child["reversed_from"], description_key(child.get("description"))), []):
            if parent is not child and not parent.get("reversed_from") and not parent.get("reversed_by"):
                parent["reversed_by"] = child.get("je_id")
                break


def make_meta(system, period, source, source_meta, rows):
    total = server_total(source_meta)
    pulled = source_meta.get("pulled_at") or source_meta.get("pulled-at")
    meta = {"system": system, "period": period,
            "pulled_at": pulled or datetime.fromtimestamp(source.stat().st_mtime, timezone.utc).isoformat(),
            "server_total": total, "row_count": rows, "source": source.name, "shape": "standard"}
    if total is None:
        meta["server_total_reason"] = "the source export carries no server count"
    if not pulled:
        meta["pulled_at_source"] = "file modification time"
    return meta


def normalize(system, period, inputs, map_data):
    """{output name: {meta, rows}} for every input given; `inputs` is keyed by OUTPUTS names."""
    if not inputs.get("gl-lines"):
        raise Refused("--lines is required: the GL lines are what every tool reads")
    label, date_format = str(map_data.get("system") or system), str(map_data.get("date_format") or "")
    sources = {}
    for name, path in inputs.items():
        if not path:
            continue
        section_name, kind = OUTPUTS[name]
        if map_data.get(section_name) is None:
            raise Refused(f"the map has no {section_name} section for the {name} input")
        rows, meta = read_source(path)
        sources[name] = (Path(path).expanduser(), meta,
                         map_rows(rows, map_data[section_name], kind, date_format, name))
    lines = sources["gl-lines"][2]
    for line in lines:
        line["posting_date"] = line.get("posting_date") or line.get("date")
    if "je-headers" in sources:
        headers = sources["je-headers"][2]
        for head in headers:
            head.setdefault("reversed_by", None)
        join_headers(lines, headers)
    else:
        headers = headers_from_lines(lines)
    fill_reversed_by(headers)
    results = {name: {"meta": make_meta(label, period, path, meta, len(rows)), "rows": rows}
               for name, (path, meta, rows) in sources.items()}
    if "je-headers" not in results:
        path, meta, _ = sources["gl-lines"]
        meta = make_meta(label, period, path, meta, len(headers))
        meta.update(server_total=None, server_total_reason="built from the GL lines; no header export",
                    derived_from="gl-lines")
        results["je-headers"] = {"meta": meta, "rows": headers}
    return results


def main(argv=None):
    p = argparse.ArgumentParser(description="Write the standard-shape ledger files for one period.")
    p.add_argument("--system", required=True, choices=["intacct", "csv"], help="csv needs --map")
    p.add_argument("--map", default="", help="field map YAML; intacct has one built in")
    p.add_argument("--period", required=True, help="close period the export is for, yyyy-mm")
    p.add_argument("--out", required=True, help="folder the standard files are written to")
    p.add_argument("--lines", required=True, help="GL line export")
    p.add_argument("--headers", default="", help="JE header export; without it headers come from the lines")
    p.add_argument("--ap-bills", default="", help="AP bill-line export")
    p.add_argument("--ap-bills-next", default="", help="AP bill lines posted after the period")
    p.add_argument("--ar-invoices", default="", help="AR invoice-line export")
    args = p.parse_args(argv)
    try:
        if not re.fullmatch(r"\d{4}-\d{2}", args.period):
            raise Refused("--period must be yyyy-mm")
        map_data = load_map(args.system, args.map)
        results = normalize(args.system, args.period,
                            {"gl-lines": args.lines, "je-headers": args.headers, "ap-bills": args.ap_bills,
                             "ap-bills-next": args.ap_bills_next, "ar-invoices": args.ar_invoices}, map_data)
    except (Refused, ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    print(f"{map_data.get('system') or args.system} {args.period}: "
          + ", ".join(f"{n} {len(r['rows'])}" for n, r in results.items()))
    for name, payload in results.items():
        path = out / f"{name}.json"
        path.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
        print(f"  wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
