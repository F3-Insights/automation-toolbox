"""meeting-validate: check a meeting plan against its transcript before anyone relies on it.

Step 6 of the meeting-scheduled-worker skill, between the analyst and the checker (and
again inside meeting-publish). Reads source.json, plan.json and, when present,
existing.json in the recording's folder; writes nothing.

It checks that every summary claim and action carries evidence whose quote appears verbatim
(spacing folded) in the segment it names; that a new task has an owner and a domain and no
existing task, a linked task has its id, ids are UUIDs, a due date is YYYY-MM-DD and a title
fits the Portal's 200 characters; that enrichment targets are portal://contact/<uuid> or
portal://company/<uuid>; that clarifications are objects with a question; that the note
carries no reserved marker text; and that a task an earlier attempt created for plan index
N is still that action, or linked by id, so a retry never makes a second task.

Prints one JSON object: `status` valid or invalid, the errors, the counts, and `plan_hash`,
which covers the plan and the meeting note it was made against. The checker copies
plan_hash into its record, and meeting-publish refuses a plan whose hash differs.
Exit 0 valid, 3 invalid, 2 could not run.

Example:
    python3 meeting_validate.py ~/.local/state/meeting-processing/recordings/<RID>-<D>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import _common as c

STATUSES = ("valid", "invalid")


def run(folder: Path) -> dict:
    source = c.read_json(folder / "source.json")
    plan = c.read_json(folder / "plan.json")
    existing = c.read_json(folder / "existing.json") if (folder / "existing.json").is_file() else {}
    errors = c.validate(plan, source, existing)
    counts = {}
    if isinstance(plan, dict) and isinstance(plan.get("actions"), list):
        counts = {d: sum(1 for a in plan["actions"] if isinstance(a, dict) and a.get("disposition") == d)
                  for d in c.DISPOSITIONS}
        counts["clarifications"] = len(plan.get("clarifications") or [])
        counts["enrichment"] = len(plan.get("enrichment_refs") or [])
    return {"status": "invalid" if errors else "valid", "folder": str(folder), "errors": errors,
            "plan_hash": c.plan_hash(plan, source) if isinstance(plan, dict) else None, "counts": counts}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="meeting-validate", description=__doc__.split("\n\n")[0])
    p.add_argument("folder", help="the recording's folder")
    a = p.parse_args(argv)
    try:
        result = run(c.outside_toolbox(a.folder))
    except Exception as exc:
        return c.fail(c.reason_of(exc, "meeting-validate"))
    return c.emit(result, c.OK if result["status"] == "valid" else c.STOP)


if __name__ == "__main__":
    sys.exit(main())
