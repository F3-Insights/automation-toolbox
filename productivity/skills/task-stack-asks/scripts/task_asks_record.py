"""Advance the domain's task-asks cursor past what one Run decided.

Runs after task-stack-apply in the task-asks finish step. It reads only what the
deterministic steps and the session wrote in the Run folder:

- asks-queue.json: the items task_asks_queue.py queued and deferred, and the cursor's path;
- changes.json: its `asks` list, one decision per queued item, {"source": <key>,
  "decision": "create" | "done" | "exists" | "skip" | "ask", "ops": [<op ids>], "reason": "..."};
- apply.json (or apply-dry-run.json): what task-stack-apply did with each op.

An item is decided when its decision is exists, skip or ask, or when every create it names was
applied, would apply, found unchanged by its marker or refused as a DUPLICATE. Anything else
(no decision, a create refused, deferred or failed, an item deferred past the cap) is left for
the next Run. The cursor's `since` moves to the newest instant up to which every item is
decided (the queue's `until` when all are), and `decided` keeps the decided keys dated at or
after it less the queue's overlap (_common.OVERLAP), so a later Run neither skips an undecided
item nor decides one twice, even re-reading the overlap. It never moves back.

A dry Run (--dry-run, or --dry-run-if true) writes RUN/asks-record-dry-run.json and leaves the
cursor alone; a live one writes RUN/asks-record.json and the cursor.

First line: `RECORDED: 9 decided, 2 left; cursor 2030-03-04T17:00:00Z` (`WOULD RECORD: ...` dry).
Exit 0 when it ran (no change set: `STALE`, nothing recorded), 2 when the Run folder is not one.

Example:
    python3 task_asks_record.py --run RUN --dry-run-if=false
"""

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

import _common as c

TOOL = "task-asks-record"
DONE_OUTCOMES = ("applied", "would_apply", "unchanged")
SETTLED = ("exists", "skip", "ask")


def _load(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def decided_keys(queue, changes, results):
    """{key: why} for the queued items this Run settled."""
    by_op = {str(r.get("id")): r for r in results}
    ops_of = {}
    for op in changes.get("ops") or []:
        if isinstance(op, dict) and op.get("source"):
            base = ":".join(str(op["source"]).split(":")[:3])
            ops_of.setdefault(base, []).append(str(op.get("id")))
    out = {}
    queued = {i["key"] for i in queue.get("items") or []}
    for d in changes.get("asks") or []:
        if not isinstance(d, dict) or d.get("source") not in queued:
            continue
        key, kind = d["source"], d.get("decision")
        if kind in SETTLED:
            out[key] = kind
            continue
        ids = [str(x) for x in (d.get("ops") or ([d["op"]] if d.get("op") else []))] or ops_of.get(key, [])
        rows = [by_op.get(i) for i in ids]
        if ids and all(r and (r.get("outcome") in DONE_OUTCOMES or r.get("code") == "DUPLICATE") for r in rows):
            out[key] = kind
    return out


def advance(queue, decided, old):
    """The new cursor: since, and the decided keys dated inside the overlap before it or later."""
    items = {i["key"]: i.get("date") for i in (queue.get("items") or []) + (queue.get("deferred") or [])}
    open_dates = [c.parse_time(d) for k, d in items.items() if k not in decided and c.parse_time(d)]
    since = (min(open_dates) - timedelta(seconds=1)) if open_dates else c.parse_time(queue["window"]["until"])
    before = c.parse_time(old.get("since"))
    if before is not None and since < before:
        since = before
    merged = dict(old.get("decided") or {}, **{k: items[k] for k in decided})
    keep = {k: d for k, d in merged.items() if (c.parse_time(d) or since) >= since - c.OVERLAP}
    return {"since": c.iso(since), "decided": dict(sorted(keep.items()))}


def main(argv=None):
    p = argparse.ArgumentParser(prog="task_asks_record.py", description=__doc__.split("\n\n")[0])
    p.add_argument("--run", required=True, help="The Run folder")
    p.add_argument("--dry-run", action="store_true", help="Record nothing; write asks-record-dry-run.json")
    p.add_argument("--dry-run-if", default="", help="A scheduler's placeholder: true means --dry-run")
    a = p.parse_args(argv)
    try:
        run = c.guard_run_path(a.run)
        if not run.is_dir():
            raise c.Bad(f"{run} is not a Run folder")
        dry = a.dry_run or (c.truthy_flag(a.dry_run_if) if a.dry_run_if.strip() else False)
        queue = _load(run / "asks-queue.json")
        if queue is None or queue.get("tool") != "task-asks-queue":
            raise c.Bad(f"{run} holds no asks-queue.json from task-asks-queue")
    except c.Bad as exc:
        c.fail(exc)
    changes = _load(run / "changes.json")
    if changes is None:
        print("STALE: no changes.json in the Run; the cursor is unchanged")
        return 0
    applied = _load(run / ("apply-dry-run.json" if dry else "apply.json")) or {}
    decided = decided_keys(queue, changes, applied.get("results") or [])
    path = Path(queue["cursor"])
    old = c.read_cursor(path)
    new = advance(queue, decided, old)
    left = len(queue.get("items") or []) + len(queue.get("deferred") or []) - len(decided)
    result = {"tool": TOOL, "dry_run": dry, "cursor": str(path), "before": old, "after": new,
              "decided": decided, "left": left}
    (run / ("asks-record-dry-run.json" if dry else "asks-record.json")).write_text(
        json.dumps(result, indent=1) + "\n", encoding="utf-8")
    if not dry:
        c.write_cursor(path, new)
    print(f"{'WOULD RECORD' if dry else 'RECORDED'}: {len(decided)} decided, {left} left; cursor {new['since']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
