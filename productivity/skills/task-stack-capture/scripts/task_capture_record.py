"""Record what one task-capture Run did with each source item, in the capture ledger.

Runs after task-stack-apply in the task-capture finish step. It reads only what the
deterministic steps and the session wrote in the Run folder, never the session's account:

- capture-queue.json: the queue task_capture_queue.py gathered (queued, deferred, expired, closed);
- changes.json: the change set, whose `captures` list holds one decision per queued item,
  {"source": <key>, "decision": "create" | "exists" | "skip" | "ask", "op": <create op id>,
  "task": "portal://task/<id>", "reason": "..."}, and whose create ops carry `source: <key>`;
- apply.json (or apply-dry-run.json): what task-stack-apply did with each op.

It sets one ledger row per item:

    create applied (or would apply)                      created, with the task
    create unchanged: the marker found the task          exists, with that task
    create refused as a DUPLICATE                        exists, with the task the apply named
    create refused otherwise, deferred, failed, missing  seen, one more attempt; stuck at three
    decision exists naming a portal://task/<id>          exists
    decision skip / ask                                  skipped / asked
    queued but no decision                               seen (no attempt counted)
    deferred past the cap                                seen
    expired / closed at the source                       expired / closed

A row keeps its first_seen. The Run is appended to runs.jsonl and the result written to
RUN/capture-record.json. A dry Run (--dry-run, or --dry-run-if true) writes only
RUN/capture-record-dry-run.json and touches neither the ledger nor runs.jsonl.

First line: `RECORDED: 8 created, 2 exists, 1 skipped, ...; 2 left for the next Run`
(`WOULD RECORD: ...` in a dry run). Exit 0 when it ran (a Run with no queue says STALE and
records nothing), 2 when the Run folder is not one.

Example:
    python3 task_capture_record.py --run RUN --dry-run-if=false
"""

import argparse
import json
import re
import sys
from datetime import datetime

import _common as c

TOOL = "task-capture-record"
TASK = re.compile(r"portal://task/([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})")
SUMMARY = ("created", "exists", "skipped", "asked", "expired", "closed", "stuck")


def _load(path):
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _task(value):
    m = TASK.search(str(value or ""))
    return f"portal://task/{m.group(1).lower()}" if m else None


def outcome_of(decision, op, result):
    """(state, task, note, attempted) for one queued item."""
    if op is not None:
        if result is None:
            return "seen", None, f"create {op.get('id')} has no apply result", True
        outcome = result.get("outcome")
        if outcome in ("applied", "would_apply"):
            return "created", _task(result.get("task")), f"create {op.get('id')} {outcome}", True
        if outcome == "unchanged":
            return "exists", _task(result.get("task") or result.get("reason")), str(result.get("reason") or ""), True
        if outcome == "refused" and result.get("code") == "DUPLICATE":
            return "exists", _task(result.get("reason")), f"duplicate: {result.get('reason')}", True
        return "seen", None, f"{outcome} {result.get('code') or ''}: {result.get('reason') or ''}".strip(), True
    if decision is None:
        return "seen", None, "no decision this Run", False
    kind, reason = decision.get("decision"), str(decision.get("reason") or "")
    if kind == "exists":
        task = _task(decision.get("task"))
        if task:
            return "exists", task, reason, True
        return "seen", None, "decision exists without a portal://task/<id>", True
    if kind == "skip":
        return "skipped", None, reason, True
    if kind == "ask":
        return "asked", None, reason, True
    if kind == "create":
        return "seen", None, "decision create without its create op", True
    return "seen", None, f"unknown decision {kind!r}", True


def plan(run, recorded):
    queue = _load(run / "capture-queue.json")
    if queue is None or queue.get("tool") != "task-capture-queue":
        return {"stale": "capture-queue.json is missing or not a task-capture-queue output; nothing recorded"}
    changes = _load(run / "changes.json") or {}
    applied = _load(run / "apply.json") or _load(run / "apply-dry-run.json") or {}
    results = {str(r.get("id")): r for r in applied.get("results") or [] if isinstance(r, dict)}
    ops = {str(o.get("source")): o for o in changes.get("ops") or []
           if isinstance(o, dict) and o.get("op") == "create" and o.get("source")}
    decisions = {str(d["source"]): d for d in changes.get("captures") or [] if isinstance(d, dict) and d.get("source")}
    started = str(queue.get("generated_at") or "")
    rows, queued_keys = [], set()

    def row(key, item, state, task, note, attempted):
        old = recorded.get(key) or {}
        attempts = int(old.get("attempts") or 0) + (1 if attempted and state == "seen" else 0)
        if state == "seen" and attempts >= c.MAX_ATTEMPTS:
            state, note = "stuck", f"{note} (attempt {attempts})"
        rows.append({"id": key, "source": item.get("source") or old.get("source") or key.split(":")[0],
                     "ref": item.get("ref") or old.get("ref") or "", "state": state,
                     "task": task or old.get("task") or "", "marker": item.get("marker") or old.get("marker") or "",
                     "item_date": item.get("date") or old.get("item_date") or "",
                     "first_seen": old.get("first_seen") or started, "last_run": run.name,
                     "attempts": str(attempts), "note": note[:300]})

    for item in queue.get("items") or []:
        key = str(item.get("key"))
        queued_keys.add(key)
        op = ops.get(key)
        result = results.get(str(op.get("id"))) if op else None
        row(key, item, *outcome_of(decisions.get(key), op, result))
    for item in queue.get("deferred") or []:
        row(str(item["key"]), item, "seen", None, "deferred past the cap", False)
    for item in queue.get("expired") or []:
        row(str(item["key"]), item, "expired", None, f"dated before the {queue.get('horizon_days')}-day horizon", False)
    for item in queue.get("closed") or []:
        row(str(item["key"]), item, "closed", None, "closed at the source", False)
    counts = {}
    for r in rows:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    return {"started_at": started, "rows": rows, "counts": counts,
            "strays": sorted(k for k in set(ops) | set(decisions) if k not in queued_keys),
            "apply": "apply.json" if (run / "apply.json").is_file() else
                     ("apply-dry-run.json" if (run / "apply-dry-run.json").is_file() else None)}


def first_line(result, dry):
    if result.get("stale"):
        return f"STALE: {result['stale']}"
    n = result["counts"]
    parts = ", ".join(f"{n.get(s, 0)} {s}" for s in SUMMARY)
    stray = f"; {len(result['strays'])} decision(s) for items not in the queue" if result["strays"] else ""
    return f"{'WOULD RECORD' if dry else 'RECORDED'}: {parts}; {n.get('seen', 0)} left for the next Run{stray}"


def main(argv=None):
    p = argparse.ArgumentParser(prog="task_capture_record.py", description=__doc__.split("\n\n")[0])
    p.add_argument("--run", required=True, help="The Run folder")
    p.add_argument("--dry-run", action="store_true", help="Say what would be recorded; write only the dry-run file")
    p.add_argument("--dry-run-if", default=None, help="A dry run when this is true (a scheduler placeholder)")
    p.add_argument("--state", default="", help="The task-stack state folder")
    p.add_argument("--format", choices=("text", "json"), default="text")
    a = p.parse_args(argv)
    dry = a.dry_run
    try:
        if a.dry_run_if is not None:
            dry = dry or c.truthy_flag(a.dry_run_if)
        run = c.guard_run_path(a.run)
        if not run.is_dir():
            raise c.Bad(f"no Run folder {run}")
        root = c.state_root(a.state)
        with c.locked(root):
            result = plan(run, c.read_ledger(root))
            if not result.get("stale"):
                result.update(tool=TOOL, dry_run=dry, run=str(run),
                              recorded_at=datetime.now().astimezone().isoformat(timespec="seconds"))
                if not dry:
                    stamp = result["recorded_at"]
                    path = c.write_ledger(root, {r["id"]: dict(r, updated_at=stamp, by=TOOL) for r in result["rows"]})
                    with (root / "runs.jsonl").open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps({"run": str(run), "started_at": result["started_at"],
                                             "recorded_at": stamp, "dry_run": False,
                                             "counts": result["counts"]}) + "\n")
                    result["ledger"] = str(path)
                c.atomic_json(run / ("capture-record-dry-run.json" if dry else "capture-record.json"), result)
    except c.Bad as exc:
        c.fail(exc)
    if a.format == "json":
        print(json.dumps(result, indent=1, ensure_ascii=False, default=str))
    else:
        print(first_line(result, dry))
    return 0


if __name__ == "__main__":
    sys.exit(main())
