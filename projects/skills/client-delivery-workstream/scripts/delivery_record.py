# /// script
# dependencies = ["pyyaml"]
# ///
"""The one writer of an engagement's delivery ledgers, DELIVERY-EVIDENCE.csv and RAID.csv.

  delivery_record.py ENGAGEMENT milestone --id M3 --state delivered --evidence REF [--source REF] [--note TEXT]
  delivery_record.py ENGAGEMENT milestone --from milestones.json
  delivery_record.py ENGAGEMENT change --id C2 --milestone M3 --to 2026-11-20 --state proposed --reason TEXT [--source REF]
  delivery_record.py ENGAGEMENT change --from changes.json
  delivery_record.py ENGAGEMENT raid --from raid.json
  delivery_record.py ENGAGEMENT session --mode plan|check|milestone-review [--state done|dry-run]
  delivery_record.py ENGAGEMENT show [--format text|json]

Every subcommand also takes --working DIR (the working folder; a dry run's copy), --by NAME
(default client-delivery-orchestrator), --as-of DATE and --contexts-dir DIR.

The rows and their rules:
- milestone:<id>  planned, in-progress, at-risk, delivered, accepted. Delivered and accepted
  need evidence; accepted needs the owner's confirmation as its source. The milestone must be
  in PLAN.md.
- change:<id>     proposed, approved, rejected: a milestone's planned date moved. Needs the new
  date and a reason (prefixed with the date it moves from); approved needs a source.
- session:<as-of>-<mode>  done or dry-run.
- RAID rows: id (R, A, I or D and a number by type, the next free one when absent), type,
  title, owner, raised, review_by, state (open, closed), severity, source, mitigation, note. An
  open item needs an owner, a source and a review date; review_by defaults to the as-of date
  plus the rules' RAID review days.

A --from file holds a JSON list of rows, or an object with a milestones, changes or raid list
(at its top or under "extra"). Every row is tried on a scratch copy first, so one bad row
writes nothing. Rows are upserted by id; nothing is deleted.

Prints one line per row written. Exit 0 recorded; 1 when a row is refused; 2 on a bad
argument or an unreadable file.

Example:
  python3 delivery_record.py northwind-delivery raid --from RUN/returns/raid.json --working W
"""

import argparse
import json
import re
import shutil
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

import _common as dc

BY = "client-delivery-orchestrator"
RAID_PREFIX = {"risk": "R", "assumption": "A", "issue": "I", "dependency": "D"}
RAID_ID = re.compile(r"^[RAID]\d{1,4}$")


def clean(value):
    return "" if value is None else str(value).strip()


def rows_from(path, key):
    data = dc.load_json(Path(path).expanduser(), path)
    if isinstance(data, dict):
        data = data[key] if key in data else (data.get("extra") or {}).get(key)
    if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
        raise dc.Bad(f"{path}: wants a JSON list of {key} rows, or an object with a '{key}' list")
    return data


def write_all(make_ledger, working, rows):
    """Try every row on a scratch copy first, so one bad row writes nothing; then write them."""
    live = make_ledger(working)
    with tempfile.TemporaryDirectory() as scratch:
        if live.path.is_file():
            shutil.copyfile(live.path, Path(scratch) / live.path.name)
        trial = make_ledger(Path(scratch))
        for row in rows:
            trial.upsert(row)
    working.mkdir(parents=True, exist_ok=True)
    return [live.upsert(row) for row in rows]


def plan_ids(working):
    return {m["id"]: m for m in dc.read_plan(working / dc.PLAN_MD)["milestones"]}


def milestone_row(item, working, by):
    mid = clean(item.get("id") or item.get("milestone")).removeprefix("milestone:")
    if mid not in plan_ids(working):
        raise dc.Refused(f"milestone {mid!r} is not in {dc.PLAN_MD}; write it in the plan first")
    row = {"id": f"milestone:{mid}", "kind": "milestone", "item": mid, "state": clean(item.get("state")),
           "evidence": clean(item.get("evidence")), "source": clean(item.get("source")),
           "note": clean(item.get("note")), "updated_at": dc.now_utc(), "by": by}
    if row["state"] == "accepted" and not row["source"]:
        raise dc.Refused(f"{row['id']}: accepted needs the owner's confirmation as its source")
    return row


def change_row(item, working, by):
    cid = clean(item.get("id")).removeprefix("change:")
    if not dc.ID_RE.match(cid):
        raise dc.Bad(f"change id {cid!r} is not a short id such as C3")
    mid = clean(item.get("milestone") or item.get("item"))
    plan = plan_ids(working)
    if mid not in plan:
        raise dc.Refused(f"change {cid}: milestone {mid!r} is not in {dc.PLAN_MD}")
    reason = clean(item.get("reason") or item.get("note"))
    was = plan[mid].get("baseline due") or plan[mid].get("planned due") or "no date"
    note = reason if not reason or reason.startswith("from ") else f"from {was}: {reason}"
    return {"id": f"change:{cid}", "kind": "change", "item": mid, "state": clean(item.get("state")),
            "due": clean(item.get("to") or item.get("due")), "source": clean(item.get("source")),
            "evidence": clean(item.get("evidence")), "note": note, "updated_at": dc.now_utc(), "by": by}


def raid_row(item, taken, today, review_days, by):
    kind = clean(item.get("type")).lower()
    if kind not in dc.RAID_TYPES:
        raise dc.Refused(f"RAID type {kind!r} is not one of {', '.join(dc.RAID_TYPES)}")
    rid = clean(item.get("id"))
    if not rid:
        prefix = RAID_PREFIX[kind]
        numbers = [int(t[1:]) for t in taken if t.startswith(prefix) and t[1:].isdigit()]
        rid = f"{prefix}{max(numbers, default=0) + 1}"
    if not RAID_ID.match(rid):
        raise dc.Bad(f"RAID id {rid!r} is not R, A, I or D and a number")
    taken.append(rid)
    state = clean(item.get("state")) or "open"
    row = {"id": rid, "type": kind, "title": clean(item.get("title")), "owner": clean(item.get("owner")),
           "raised": clean(item.get("raised")) or today.isoformat(), "review_by": clean(item.get("review_by")),
           "state": state, "severity": clean(item.get("severity")).lower(), "source": clean(item.get("source")),
           "mitigation": clean(item.get("mitigation")), "note": clean(item.get("note")),
           "updated_at": dc.now_utc(), "by": by}
    if state == "open" and not row["review_by"]:
        row["review_by"] = (today + timedelta(days=review_days)).isoformat()
    return row


def run(a):
    eng = dc.load_engagement(a.engagement, a.contexts_dir)
    working = dc.working_folder(eng, a.working)
    by = dc.blank(a.by) or BY
    today = dc.as_of_date(a.as_of)
    if a.command == "milestone":
        items = rows_from(a.from_path, "milestones") if dc.blank(a.from_path) else [
            {"id": a.id, "state": a.state, "evidence": a.evidence, "source": a.source, "note": a.note}]
        return write_all(dc.evidence_ledger, working, [milestone_row(i, working, by) for i in items])
    if a.command == "change":
        items = rows_from(a.from_path, "changes") if dc.blank(a.from_path) else [
            {"id": a.id, "milestone": a.milestone, "to": a.to, "state": a.state, "reason": a.reason,
             "source": a.source}]
        return write_all(dc.evidence_ledger, working, [change_row(i, working, by) for i in items])
    if a.command == "raid":
        taken = [r["id"] for r in dc.raid_ledger(working).rows()]
        rows = [raid_row(i, taken, today, eng["rules"]["raid_review_days"], by) for i in rows_from(a.from_path, "raid")]
        return write_all(dc.raid_ledger, working, rows)
    if a.command == "session":
        row = {"id": f"session:{today.isoformat()}-{a.mode}", "kind": "session", "item": a.mode,
               "state": a.state, "note": a.note, "updated_at": dc.now_utc(), "by": by}
        return write_all(dc.evidence_ledger, working, [row])
    evidence, raid = dc.evidence_ledger(working).rows(), dc.raid_ledger(working).rows()
    if a.format == "json":
        return [json.dumps({"working": str(working), "evidence": evidence, "raid": raid}, indent=1)]
    out = [f"{dc.EVIDENCE_CSV}: {len(evidence)} row(s); {dc.RAID_CSV}: {len(raid)} row(s)"]
    out += [f"  {r['id']} {r.get('state')} {r.get('due') or ''} {r.get('evidence') or ''}".rstrip() for r in evidence]
    out += [f"  {r['id']} {r.get('type')} {r.get('state')} review {r.get('review_by')}: {r.get('title')}" for r in raid]
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description="The one writer of an engagement's DELIVERY-EVIDENCE.csv and RAID.csv.")
    p.add_argument("engagement", help="Context name or path to a Context YAML file")
    sub = p.add_subparsers(dest="command", required=True)

    def shared(sp):
        sp.add_argument("--working", default="", help="Use this folder as the working folder")
        sp.add_argument("--by", default="", help=f"Who records it (default {BY})")
        sp.add_argument("--as-of", default="", help="Today, for dates (yyyy-mm-dd)")
        sp.add_argument("--contexts-dir", default="", help="Where Context YAML files are found by name")
        return sp

    m = shared(sub.add_parser("milestone", help="Record a milestone's state and evidence"))
    for name in ("--id", "--state", "--evidence", "--source", "--note"):
        m.add_argument(name, default="")
    m.add_argument("--from", dest="from_path", default="", help="A JSON list of milestone rows")
    c = shared(sub.add_parser("change", help="Record a plan change: a milestone's date moved, and why"))
    for name in ("--id", "--milestone", "--to", "--state", "--reason", "--source"):
        c.add_argument(name, default="")
    c.add_argument("--from", dest="from_path", default="", help="A JSON list of change rows")
    r = shared(sub.add_parser("raid", help="Record RAID rows"))
    r.add_argument("--from", dest="from_path", required=True, help="A JSON list of RAID rows")
    s = shared(sub.add_parser("session", help="Record that a session ran"))
    s.add_argument("--mode", required=True, choices=dc.MODES)
    s.add_argument("--state", default="done", choices=dc.SESSION_STATES)
    s.add_argument("--note", default="")
    w = shared(sub.add_parser("show", help="Print both ledgers"))
    w.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)
    try:
        lines = run(a)
    except dc.Refused as exc:
        print(f"REFUSED {exc}", file=sys.stderr)
        return 1
    except (dc.Bad, ValueError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
