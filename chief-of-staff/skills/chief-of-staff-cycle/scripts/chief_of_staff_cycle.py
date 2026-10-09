#!/usr/bin/env python3
"""chief-of-staff-cycle: open, record and close one chief-of-staff cycle.

    start [--date D] [--dry-run] [--trigger-items JSON|-] [--goals G] [--vault V] [--health H] [--autonomy A]
    record CYCLE_DIR --doer NAME [--args A] --status S --outcome "one line" [--local-path P]
    finish CYCLE_DIR --status ok|failed [--reason "..."]

What starts a cycle, and when, is outside this toolbox: a person or a runtime's scheduler.

`start` makes the cycle folder, <state>/cycles/<date>/<HHMMSS>/ (state: --state, else
the setting [chief-of-staff-cycle] state, else <state_dir>/chief-of-staff), and writes
cycle.json: the date and weekday, the cycle time (00:00 for a backfill of another date),
whether Monday's week in review is still due today, the day's cycle and dispatch counts for
the receipt's usage line, the doers the owner's registry allows, and the paths of the owner's
own documents the decider reads (each a setting; a missing one is named in `notes`).

`--trigger-items` carries why a runtime's Monitor started this cycle: the JSON list of
{"key", "summary"} the Monitor's check (cos_watch.py) reported, given inline, on stdin
with `-`, or from a file with `@<path>` (a runtime session that may not redirect writes the
list to its run folder and passes the path). It is kept in cycle.json as `trigger_items` ([] when the cycle was not woken by a
change). A list that cannot be read is left out and named in `notes`; the cycle still runs.

`record` adds one dispatch's outcome to execution.json; one dispatch failing never stops the
next. `finish` closes the cycle and reports whether verify.json shows this cycle's own block
in the receipt note (`this_cycle_written`). The session saying ok is a claim; the note is the
evidence. A second finish answers `already_finished`.

--dry-run on start marks the cycle as a dry run: the folder name ends in -dry-run. Exit 0 to
go on, 2 when it could not run.

Example:
    python3 chief_of_staff_cycle.py start
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import _common as c

STATUSES = ("dispatched", "prepared", "already_prepared", "blocked", "held", "failed", "invalid",
            "dry-run", "skipped", "launched", "refused")

# The owner's documents the decider reads, by setting. Each is a file except vault_dir.
DOCUMENTS = (("charter", "charter"), ("profile", "owner_profile"), ("goals", "goals_doc"),
             ("principles", "principles"), ("roster", "doer_roster"), ("ledger", "event_ledger"),
             ("vault", "vault_dir"), ("health_probe", "health_probe"), ("autonomy", "autonomy_policy"))


def _cycles_today(root, day):
    folder = Path(root) / "cycles" / day
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_dir() and not p.name.endswith("-dry-run"))


def _week_in_review_written(cycles):
    for f in cycles:
        receipt = c.load_object((f / "receipt.json").read_text(encoding="utf-8", errors="replace")) \
            if (f / "receipt.json").exists() else None
        if "week in review" in str((receipt or {}).get("content") or "").lower():
            return True
        if (c.read_json(f / "cycle.json") or {}).get("week_in_review"):
            return True
    return False


def _dispatched(cycles):
    return sum(1 for f in cycles for row in c.read_json(f / "execution.json") or []
               if isinstance(row, dict) and row.get("status") not in ("dry-run", "skipped"))


def resolve_paths(overrides=None):
    """The owner's documents: a flag, else the setting. Nothing has a default path."""
    overrides = overrides or {}
    paths, notes = {}, []
    for key, name in DOCUMENTS:
        value = overrides.get(key) or c.setting(name) or ""
        paths[key] = str(Path(value).expanduser()) if value else ""
        if not value:
            notes.append(f"no {key.replace('_', ' ')}: setting {name} is not set")
        elif not Path(paths[key]).exists():
            notes.append(f"{key.replace('_', ' ')} not found (setting {name})")
    return {"paths": paths, "notes": notes}


MAX_TRIGGER_ITEMS = 50


def read_trigger_items(text):
    """([{key, summary}], note): the Monitor's items, each flattened to one short line. Empty
    text is no items; anything that is not such a list is no items and a note saying so."""
    text = (text or "").strip()
    if not text:
        return [], ""
    try:
        value = json.loads(text)
    except ValueError:
        return [], "trigger_items could not be read (not JSON); the cycle runs without them"
    if not isinstance(value, list) or not all(isinstance(i, dict) and i.get("key") for i in value):
        return [], "trigger_items could not be read (not a list of {key, summary}); the cycle runs without them"
    items = [{"key": c.flat(i["key"], 200), "summary": c.flat(i.get("summary"), 300)} for i in value]
    note = "" if len(items) <= MAX_TRIGGER_ITEMS else f"trigger_items cut to the first {MAX_TRIGGER_ITEMS} of {len(items)}"
    return items[:MAX_TRIGGER_ITEMS], note


def read_items_arg(value):
    """The text of `--trigger-items`: stdin for `-`, the file's text for `@<path>`, else the
    value itself. A file that cannot be read is no items, as unreadable JSON is."""
    if value == "-":
        return sys.stdin.read()
    if value.startswith("@"):
        try:
            return Path(value[1:]).expanduser().read_text(encoding="utf-8")
        except OSError:
            return "@unreadable"
    return value


def start(root, day, dry_run=False, paths=None, now=None, trigger_items=None):
    now = now or c.local_now()
    weekday = date.fromisoformat(day).strftime("%A")
    backfill = day != now.date().isoformat()
    base, tail = now.strftime("%H%M%S"), ("-dry-run" if dry_run else "")
    earlier = _cycles_today(root, day)
    folder = Path(root) / "cycles" / day / f"{base}{tail}"
    n = 1
    while folder.exists():  # two cycles in the same second never share a folder
        n += 1
        folder = Path(root) / "cycles" / day / f"{base}-{n}{tail}"
    folder.mkdir(parents=True, mode=0o700)
    registry = c.load_doers()
    resolved = paths or {"paths": {}, "notes": []}
    items, items_note = read_trigger_items(trigger_items)
    cycle = {
        "cycle_id": f"{day}/{folder.name}", "folder": str(folder), "date": day, "weekday": weekday,
        "cycle_time": "00:00" if backfill else now.strftime("%H:%M"),
        "dry_run": dry_run, "started_at": c.now_utc().isoformat(timespec="seconds"),
        "trigger_items": items,
        "is_monday": weekday == "Monday",
        "monday_synthesis_due": weekday == "Monday" and not _week_in_review_written(earlier),
        "first_cycle_today": not earlier, "display_name": c.display_name(),
        "usage_line": "Cycles today: %d. Doers dispatched today: %d. Model cost is on the runner's run page."
                      % (len(earlier) + (0 if dry_run else 1), _dispatched(earlier)),
        "doers": [{"doer": k, "route": v["route"], "runs": v.get("skill") or v["worker"], "args": v["args"],
                   "default_args": v["default_args"], "purpose": v["purpose"], "when": v["when"]}
                  for k, v in sorted(registry["doers"].items())],
        "retired_doers": registry["retired"],
        "paths": resolved["paths"], "notes": resolved["notes"] + registry["problems"] + ([items_note] if items_note else []),
    }
    c.atomic_json(folder / "cycle.json", cycle)
    c.atomic_json(folder / "execution.json", [])
    return {"status": "ok", **cycle}


def record(folder, doer, args, status, outcome, local_path=""):
    if status not in STATUSES:
        raise c.Bad(f"--status must be one of {', '.join(STATUSES)}")
    rows = c.read_json(Path(folder) / "execution.json", default=[]) or []
    row = {"doer": c.flat(doer, 80), "args": c.flat(args, 200), "status": status,
           "outcome": c.flat(outcome, 300), "at": c.now_utc().isoformat(timespec="seconds")}
    if local_path:
        row["local_path"] = local_path
    rows = [r for r in rows if not (r.get("doer") == row["doer"] and r.get("args") == row["args"])] + [row]
    c.atomic_json(Path(folder) / "execution.json", rows)
    return {"status": "recorded", "row": row, "dispatches": len(rows)}


def finish(folder, status, reason=""):
    folder = Path(folder)
    cycle = c.read_json(folder / "cycle.json")
    if not isinstance(cycle, dict):
        raise c.Bad(f"{folder} holds no cycle.json")
    if status not in ("ok", "failed"):
        raise c.Bad("--status must be ok or failed")
    if cycle.get("result"):
        return {"status": "already_finished", "result": cycle["result"], "cycle_id": cycle["cycle_id"],
                "finished_at": cycle.get("finished_at")}
    receipt = c.load_object((folder / "receipt.json").read_text(encoding="utf-8", errors="replace")) \
        if (folder / "receipt.json").exists() else None
    cycle.update({"finished_at": c.now_utc().isoformat(timespec="seconds"), "result": status,
                  "result_reason": reason,
                  "week_in_review": "week in review" in str((receipt or {}).get("content") or "").lower()})
    c.atomic_json(folder / "cycle.json", cycle)
    out = {"status": "finished", "result": status, "cycle_id": cycle["cycle_id"]}
    if cycle.get("dry_run"):
        return out
    verify = c.read_json(folder / "verify.json") or {}
    # The day's note can be found while this cycle's block is not in it (a later cycle whose
    # append was refused finds the morning's note); only this cycle's marker counts.
    if verify.get("status") == "found" and verify.get("this_cycle_written") is True:
        out["receipt"] = "verified"
    else:
        out["receipt"] = ("RECEIPT-FAILED: the day's receipt note was found but this cycle's block is not in it"
                          if verify.get("status") == "found"
                          else "RECEIPT-FAILED: " + (verify.get("reason") or "the receipt note was not verified"))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description="Open, record and close one chief-of-staff cycle. One JSON object out.")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start", help="Make the cycle folder and cycle.json")
    s.add_argument("--state", default=None, help="State folder (default: the settings)")
    s.add_argument("--date", dest="day", default=None, help="The date worked (default today)")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--trigger-items", default="",
                   help="The Monitor's items as a JSON list of {key, summary}, - to read them from stdin, "
                        "or @<path> to read them from a file")
    for key, name in (("goals", "goals_doc"), ("vault", "vault_dir"), ("health", "health_probe"),
                      ("autonomy", "autonomy_policy")):
        s.add_argument(f"--{key}", default=None, help=f"In place of the setting {name}")
    r = sub.add_parser("record", help="Add one dispatch's outcome to execution.json")
    r.add_argument("cycle_dir")
    r.add_argument("--doer", required=True)
    r.add_argument("--args", dest="args_", default="")
    r.add_argument("--status", dest="status_", required=True, choices=STATUSES)
    r.add_argument("--outcome", required=True, help="One line: what it produced or why not")
    r.add_argument("--local-path", default="", help="A private local artifact path (kept out of the receipt)")
    f = sub.add_parser("finish", help="Close the cycle and report whether its receipt was verified")
    f.add_argument("cycle_dir")
    f.add_argument("--status", dest="status_", required=True, choices=("ok", "failed"))
    f.add_argument("--reason", default="")
    args = p.parse_args(argv)
    try:
        if args.cmd == "start":
            paths = resolve_paths({"goals": args.goals, "vault": args.vault, "health_probe": args.health,
                                   "autonomy": args.autonomy})
            items = read_items_arg(args.trigger_items)
            c.emit(start(c.state_root(args.state), c.check_date(args.day), args.dry_run, paths,
                         trigger_items=items), c.OK)
        if args.cmd == "record":
            c.emit(record(c.cycle_dir(args.cycle_dir), args.doer, args.args_, args.status_, args.outcome,
                          args.local_path), c.OK)
        c.emit(finish(c.cycle_dir(args.cycle_dir), args.status_, c.flat(args.reason, 300)), c.OK)
    except c.Bad as exc:
        c.fail(str(exc))


if __name__ == "__main__":
    main()
