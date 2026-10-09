# /// script
# dependencies = ["pyyaml"]
# ///
"""Read and keep a review register: what is open, at risk, reconciled, owed and proposed.

A register is a folder of YAML files, one per table: open_items, risk_register, rec_status,
owed_by_owner and proposals. Every row has an id (OI-001, RR-001, REC-001, OBO-001, P1), a
status, evidence, timestamps and a history of who changed it. Rows are never deleted.

Subcommands, all after --dir <register folder>:
  summary                          row counts per table and status (JSON)
  list TABLE [--status S] [--all]  one JSON row per line; open rows only unless asked
  render [--period YYYY-MM]        the tables as Markdown, for a memo
  add TABLE --by WHO --field k=v   add a row (repeat --field); prints the new id. Never a
                                   closed row: a closing status, closed_at or closed_by is refused
  close TABLE ID --by WHO --status S --reason TEXT
                                   close a row; WHO must be a person or a ledger proof
                                   (gl:JE1234), never a tool or agent

The owed_by_owner heading in render uses the setting owner_name from the [review-register]
table of the owner settings file, or "the owner".

Exit 0 on success, 1 when a row is refused, 2 on a bad argument.

Example:
    python3 register.py --dir ~/clients/northwind/register add open_items --by Dana \\
        --field description="Book the freight accrual" --field owner=Dana --field due=2027-08-05
"""

import argparse
import json
import os
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

PREFIX = {"open_items": "OI", "risk_register": "RR", "rec_status": "REC", "owed_by_owner": "OBO", "proposals": "P"}
COMMON = {"id": "", "key": "", "status": "open", "evidence": [], "created_at": "", "updated_at": "",
          "closed_at": "", "closed_by": "", "history": [], "portal_task_id": ""}
# Each table's own fields with their defaults, and the statuses it allows (the first is the default).
FIELDS = {
    "open_items": {"period": "", "source": "", "check": "", "description": "", "owner": "", "due": "", "amount": None},
    "risk_register": {"opened_period": "", "description": "", "severity": "medium", "estimate_booked": None,
                      "estimate_note": "", "research_owner": "", "follow_up": "", "resolution": ""},
    "rec_status": {"account": "", "account_name": "", "period": "", "preparer": "", "reviewer": "",
                   "difference": None, "oldest_open_item": "", "workbook": "", "note": ""},
    "owed_by_owner": {"handoff_no": 0, "group": "other", "title": "", "detail": "", "blocks": "", "due": "",
                      "answer": ""},
    "proposals": {"title": "", "rationale": "", "source": "", "reason": "", "decided_at": ""},
}
STATUSES = {
    "open_items": ("open", "waiting", "done", "dropped"),
    "risk_register": ("open", "monitoring", "closed"),
    "rec_status": ("not_started", "prepared", "reviewed", "tied", "exception"),
    "owed_by_owner": ("open", "answered", "done", "dropped"),
    "proposals": ("proposed", "approved", "rejected", "applied"),
}
SEVERITIES = ("low", "medium", "high")
CLOSED = {"done", "dropped", "closed", "tied", "rejected", "applied", "answered"}
TOOL_NAMES = ("tool", "claude", "agent", "engine", "runbooks", "close-cli", "")


class Refused(Exception):
    """A row the register will not write."""


def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def blank_row(table):
    return dict(COMMON, status=STATUSES[table][0], evidence=[], history=[], **FIELDS[table])


def checked(table, row):
    """The row with every field present and typed, or Refused for an unknown field or bad value."""
    out = blank_row(table)
    unknown = [k for k in row if k not in out]
    if unknown:
        raise Refused(f"{table} has no field {', '.join(unknown)}")
    out.update(row)
    if out["status"] not in STATUSES[table]:
        raise Refused(f"{table} status must be one of {', '.join(STATUSES[table])}, got {out['status']!r}")
    if table == "risk_register" and out["severity"] not in SEVERITIES:
        raise Refused(f"severity must be one of {', '.join(SEVERITIES)}")
    if isinstance(out["evidence"], str):   # from the command line: comma-separated
        out["evidence"] = [e.strip() for e in out["evidence"].split(",") if e.strip()]
    try:
        for name in ("amount", "estimate_booked", "difference"):
            if name in out and out[name] not in (None, ""):
                out[name] = float(out[name])
            elif name in out:
                out[name] = None
        if table == "owed_by_owner":
            out["handoff_no"] = int(out["handoff_no"] or 0)
    except (TypeError, ValueError) as exc:
        raise Refused(f"{table}: a number field is not a number ({exc})") from None
    return out


def path_of(folder, table):
    return Path(folder) / f"{table}.yaml"


def load(folder, table):
    import yaml
    path = path_of(folder, table)
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [checked(table, row) for row in data.get("rows") or []]


def save(folder, table, rows):
    import yaml
    path = path_of(folder, table)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"table": table, "updated_at": now(), "rows": rows}
    path.write_text(f"# Review register: {table}. Written by the register script, never by hand.\n"
                    + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")


def next_id(table, rows):
    prefix = PREFIX[table]
    numbers = []
    for row in rows:
        tail = row["id"].rsplit("-", 1)[-1] if "-" in row["id"] else row["id"][len(prefix):]
        if tail.isdigit():
            numbers.append(int(tail))
    n = max(numbers, default=0) + 1
    return f"P{n}" if prefix == "P" else f"{prefix}-{n:03d}"


def add(folder, table, by, fields):
    """A new row, never a closed one: only a person closes a row, through `close`."""
    if str(fields.get("status") or "").strip() in CLOSED:
        raise Refused(f"a row is never added closed ({fields['status']!r}); add it open, then a person runs close")
    preset = [k for k in ("closed_at", "closed_by") if str(fields.get(k) or "").strip()]
    if preset:
        raise Refused(f"add cannot set {', '.join(preset)}; only a person closes a row, through close")
    rows = load(folder, table)
    row_id = str(fields.pop("id", "") or next_id(table, rows))
    if any(r["id"] == row_id for r in rows):
        raise Refused(f"{table} already has id {row_id}")
    stamp = now()
    row = checked(table, dict(fields, id=row_id, created_at=stamp, updated_at=stamp))
    row["history"].append({"at": stamp, "by": by, "text": "created"})
    save(folder, table, rows + [row])
    return row


def close_row(folder, table, row_id, by, status, reason):
    """A person closes a row, or the ledger proves it closed (by = gl:JE1234). A tool never does."""
    who = (by or "").strip()
    if who.lower() in TOOL_NAMES or who.lower().startswith(("tool", "claude", "agent")):
        raise Refused(f"`by` must name a person or a ledger proof (gl:JE1234), got {by!r}")
    if status not in CLOSED:
        raise Refused(f"{status!r} is not a closing status")
    if not reason.strip():
        raise Refused("closing a row needs a reason")
    rows = load(folder, table)
    row = next((r for r in rows if r["id"] == row_id), None)
    if row is None:
        raise Refused(f"no {table} row with id {row_id}")
    stamp = now()
    row = dict(row, status=status, closed_at=stamp, closed_by=who, updated_at=stamp)
    if table == "risk_register" and not row["resolution"]:
        row["resolution"] = reason
    if table == "owed_by_owner" and status == "answered" and not row["answer"]:
        row["answer"] = reason
    if table == "proposals":
        row["decided_at"] = stamp
        row["reason"] = row["reason"] or reason
    row = checked(table, row)
    row["history"].append({"at": stamp, "by": who, "text": f"{status}: {reason}"})
    save(folder, table, [row if r["id"] == row_id else r for r in rows])
    return row


def summary(folder):
    out = {}
    for table in PREFIX:
        counts = {}
        for row in load(folder, table):
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        out[table] = counts
    return out


def render(folder, period=""):
    """The open items, risks, reconciliations, owed items and proposals as Markdown."""
    lines = []
    opens = [r for r in load(folder, "open_items") if r["status"] in ("open", "waiting")]
    opens = [r for r in opens if not period or not r["period"] or r["period"] == period]
    lines.append(f"## Open items ({len(opens)})")
    for r in sorted(opens, key=lambda r: (r["due"] or "9999", r["id"])):
        lines.append(f"- **{r['id']}** [{r['status']}] {r['description']}"
                     + (f" ${r['amount']:,.0f}" if r["amount"] else "")
                     + f", owner {r['owner'] or 'unassigned'}"
                     + (f", due {r['due']}" if r["due"] else "") + (f" (source {r['source']})" if r["source"] else ""))
    risks = [r for r in load(folder, "risk_register") if r["status"] != "closed"]
    lines.append(f"\n## Risk register ({len(risks)})")
    for r in risks:
        estimate = f" estimate booked ${r['estimate_booked']:,.0f}" if r["estimate_booked"] else " no estimate booked"
        lines.append(f"- **{r['id']}** [{r['severity']}] {r['description']};{estimate}; research "
                     f"{r['research_owner'] or 'unassigned'}" + (f", follow-up {r['follow_up']}" if r["follow_up"] else ""))
    recs = [r for r in load(folder, "rec_status") if not period or r["period"] == period]
    lines.append(f"\n## Reconciliation status ({len(recs)})")
    for r in sorted(recs, key=lambda r: r["account"]):
        lines.append(f"- {r['account']} {r['account_name']}: {r['status']}"
                     + ("" if r["difference"] is None else f", difference ${r['difference']:,.2f}")
                     + (f"; preparer {r['preparer']}" if r["preparer"] else "")
                     + (f"; reviewer {r['reviewer']}" if r["reviewer"] else "") + (f"; {r['note']}" if r["note"] else ""))
    owed = [r for r in load(folder, "owed_by_owner") if r["status"] == "open"]
    lines.append(f"\n## Owed by {settings('review-register').get('owner_name') or 'the owner'} ({len(owed)})")
    for r in sorted(owed, key=lambda r: r["handoff_no"]):
        lines.append(f"- **{r['id']}** ({r['handoff_no']}) {r['title']}, blocks: {r['blocks'] or 'n/a'}")
    proposals = [r for r in load(folder, "proposals") if r["status"] == "proposed"]
    lines.append(f"\n## Proposals awaiting decision ({len(proposals)})")
    lines += [f"- **{r['id']}** {r['title']}" for r in proposals]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Open items, risks, reconciliations, owed items and proposals.")
    parser.add_argument("--dir", required=True, help="the register folder (one YAML file per table)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("summary", help="row counts per table and status")
    listing = sub.add_parser("list", help="rows in one table")
    listing.add_argument("table", choices=list(PREFIX))
    listing.add_argument("--status", help="only rows with this status; default: open rows")
    listing.add_argument("--all", action="store_true", help="include closed rows")
    rendering = sub.add_parser("render", help="every table as Markdown")
    rendering.add_argument("--period", default="", help="label for the period, such as 2027-08")
    adding = sub.add_parser("add", help="add a row")
    adding.add_argument("table", choices=list(PREFIX))
    adding.add_argument("--by", required=True, help="who is adding it (a person, never a tool)")
    adding.add_argument("--field", action="append", default=[], help="key=value; repeat")
    closing = sub.add_parser("close", help="close a row with a status and a reason")
    closing.add_argument("table", choices=list(PREFIX))
    closing.add_argument("row_id")
    closing.add_argument("--by", required=True)
    closing.add_argument("--status", required=True, choices=sorted(CLOSED))
    closing.add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "summary":
            print(json.dumps(summary(args.dir), indent=1))
        elif args.command == "list":
            for row in load(args.dir, args.table):
                if (row["status"] == args.status) if args.status else (args.all or row["status"] not in CLOSED):
                    print(json.dumps(row, ensure_ascii=False))
        elif args.command == "render":
            print(render(args.dir, args.period), end="")
        elif args.command == "add":
            bad = [f for f in args.field if "=" not in f]
            if bad:
                print(f"register: --field must be key=value, got {bad[0]!r}", file=sys.stderr)
                return 2
            print(add(args.dir, args.table, args.by, dict(f.split("=", 1) for f in args.field))["id"])
        else:
            row = close_row(args.dir, args.table, args.row_id, args.by, args.status, args.reason)
            print(f"{row['id']} -> {row['status']}")
    except Refused as exc:
        print(f"register: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
