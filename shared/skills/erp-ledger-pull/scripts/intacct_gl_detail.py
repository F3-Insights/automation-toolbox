#!/usr/bin/env python3
"""GL detail for one account and date range from Sage Intacct, read only.

Inputs: the account number and an optional date range. Prints the journal-entry lines as a
table (with debit, credit and net totals), CSV or JSON, or writes them to --output. Two
lookups help find the right names: --list-accounts prints the chart of accounts, and
--describe prints the API's model of an object so you can choose --fields.

Credentials come from the environment (SAGE_INTACCT_CLIENT_ID, SAGE_INTACCT_CLIENT_SECRET,
SAGE_INTACCT_COMPANY_ID, SAGE_INTACCT_API_USER; see _common.py). Nothing is ever printed
from them. Only a token request, GETs and queries are made.

Example:
    python3 intacct_gl_detail.py --account 6000 --start 2026-07-01 --end 2026-07-31 --format csv
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys

from _common import API_BASE, IntacctError, IntacctSession, NoCredentials, credentials

GL_LINE_OBJECT = "general-ledger/journal-entry-line"
DEFAULT_FIELDS = ["id", "key", "journalEntry.id", "glAccount.id", "glAccount.name", "entryDate",
                  "txnType", "txnAmount", "description"]


def as_table(rows, fields):
    if not rows:
        return "(no rows)"
    cells = [["" if r.get(f) is None else str(r.get(f)) for f in fields] for r in rows]
    widths = [max(len(h), *(len(c[i]) for c in cells)) for i, h in enumerate(fields)]
    out = ["  ".join(h.ljust(w) for h, w in zip(fields, widths)), "  ".join("-" * w for w in widths)]
    out += ["  ".join(c.ljust(w) for c, w in zip(cell, widths)) for cell in cells]
    return "\n".join(out)


def as_csv(rows, fields):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows({f: r.get(f) for f in fields} for r in rows)
    return buf.getvalue()


def totals(rows):
    """(debits, credits) from txnType and txnAmount, or None when no row carries both."""
    debits = credits = 0.0
    seen = False
    for r in rows:
        try:
            amount = float(r.get("txnAmount"))
        except (TypeError, ValueError):
            continue
        seen = True
        kind = str(r.get("txnType", "")).lower()
        if kind.startswith("d"):
            debits += amount
        elif kind.startswith("c"):
            credits += amount
    return (debits, credits) if seen else None


def emit(rows, fields, fmt, output):
    text = json.dumps(rows, indent=2) if fmt == "json" else as_csv(rows, fields) if fmt == "csv" \
        else as_table(rows, fields)
    if output:
        with open(output, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        print(f"Wrote {len(rows)} row(s) to {output}")
    else:
        print(text)


def describe(session, name, log):
    """The API's model of an object. The endpoint differs between API versions, so each known
    one is tried in turn."""
    last = None
    for endpoint in (f"/services/core/model?name={name}", f"/objects/{name.replace('.', '/')}::describe",
                     f"/services/core/model/{name}"):
        try:
            result = session.get(endpoint)
        except IntacctError as exc:
            last = exc
            continue
        log(f"(model from GET {endpoint})")
        print(json.dumps(result, indent=2))
        return
    raise IntacctError(f"no model for '{name}'. Last error: {last}")


def gl_detail(session, args, log):
    fields = args.fields.split(",") if args.fields else DEFAULT_FIELDS
    filters = [{"$eq": {"glAccount.id": args.account}}]
    if args.start:
        filters.append({"$gte": {args.date_field: args.start}})
    if args.end:
        filters.append({"$lte": {args.date_field: args.end}})
    log(f"account={args.account}  {args.date_field} in [{args.start or '-inf'} .. {args.end or '+inf'}]")
    rows, total = session.query(GL_LINE_OBJECT, fields, filters=filters,
                                order_by=[{args.date_field: "asc"}], max_records=args.limit)
    log(f"{len(rows)} line(s) returned (server total: {total})")
    emit(rows, fields, args.format, args.output)
    sums = totals(rows)
    if sums and args.format == "table" and not args.output:
        print(f"\nTotals:  debits {sums[0]:,.2f}   credits {sums[1]:,.2f}   net {sums[0] - sums[1]:,.2f}")


def main(argv=None):
    p = argparse.ArgumentParser(description="Read-only Sage Intacct GL detail for one account.")
    p.add_argument("--environment", default="SANDBOX", choices=["SANDBOX", "PROD"],
                   help="SANDBOX tries the _SANDBOX credential variables first (default SANDBOX)")
    p.add_argument("--account", help="GL account number")
    p.add_argument("--start", help="first date, yyyy-mm-dd (inclusive)")
    p.add_argument("--end", help="last date, yyyy-mm-dd (inclusive)")
    p.add_argument("--date-field", default="entryDate", help="field the date range filters on")
    p.add_argument("--fields", help="comma-separated fields (default: " + ",".join(DEFAULT_FIELDS) + ")")
    p.add_argument("--limit", type=int, help="stop after this many rows")
    p.add_argument("--format", default="table", choices=["table", "csv", "json"])
    p.add_argument("--output", help="write here instead of printing")
    p.add_argument("--list-accounts", nargs="?", const="", metavar="NAME_FILTER",
                   help="list GL accounts, optionally those whose name contains NAME_FILTER")
    p.add_argument("--describe", metavar="OBJECT", help="print the API model of OBJECT")
    p.add_argument("--quiet", action="store_true", help="print results only")
    args = p.parse_args(argv)
    if not (args.describe or args.list_accounts is not None or args.account):
        p.error("--account is required (or --list-accounts / --describe)")
    log = (lambda *a: None) if args.quiet else (lambda *a: print(*a, file=sys.stderr))
    if args.environment == "PROD":
        log("*** PRODUCTION credentials (read-only queries only) ***")
    try:
        cid, secret, company, user = credentials(args.environment)
    except NoCredentials as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    log(f"API base: {API_BASE}")
    session = IntacctSession(cid, secret, company, user)
    try:
        if args.describe:
            describe(session, args.describe, log)
        elif args.list_accounts is not None:
            filters = [{"$contains": {"name": args.list_accounts}}] if args.list_accounts else None
            rows, total = session.query("general-ledger/account", ["id", "name"], filters=filters,
                                        order_by=[{"id": "asc"}])
            log(f"{len(rows)} account(s) returned (server total: {total})")
            emit(rows, ["id", "name"], args.format, args.output)
        else:
            gl_detail(session, args, log)
    except IntacctError as exc:
        print(f"API ERROR: {exc}\nHTTP 400 is usually a bad field name (try --describe {GL_LINE_OBJECT});"
              " 401/403 is a credential problem.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
