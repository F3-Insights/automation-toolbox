# /// script
# dependencies = ["pyyaml"]
# ///
"""Apply the delivery session's task change set to the engagement's Portal domain.

The finish step after a delivery session. It reads RUN/changes.json (the task change set the
session wrote) and RUN/delivery/pack.json (from delivery_pack.py), then:

1. Gates authority, with the same test delivery_check.py uses: an op that is not a task op,
   touches a task outside the engagement's domain, or assigns work to anyone but the owner and
   the rules' Assignable people is held back and becomes a question for the owner.
2. Applies the rest through task-stack-apply (the task-stack-workstream skill's script),
   limited to the rules' Portal domain, which enforces the owner's task-stack rules and keeps
   the undo log RUN/undo.jsonl.

Writes RUN/delivery/changes-gated.json (the change set that was applied) and the result to
RUN/apply.json (RUN/apply-dry-run.json on a dry run), with the held ops under "gated", and
prints the result as JSON. No change set means status "nothing". A dry run (--dry-run, or
--dry-run-if true) writes nothing to the Portal.

Exit 0 (applied, nothing, would_apply); 3 when a write failed or the set was refused; 2 on an
error.

Example:
  python3 delivery_apply.py northwind-delivery --run-dir RUN --dry-run-if true
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import _common as dc

SKILL_DIR = Path(__file__).resolve().parent.parent
TASK_STACK_APPLY = Path("~/.claude/skills/task-stack-workstream/scripts/task_stack_apply.py").expanduser()


def gate(changes, pack):
    """The change set without the ops the engagement's rules refuse, and those ops, each also
    added to the questions for the owner."""
    refused = dict(dc.authority_problems(changes, pack))
    ops = changes.get("ops") or []
    kept = [op for op in ops if str((op or {}).get("id") or "?") not in refused]
    gated = [{"id": oid, "why": why, "op": next((op for op in ops if str((op or {}).get("id")) == oid), None)}
             for oid, why in refused.items()]
    questions = list(changes.get("questions") or [])
    for g in gated:
        op = g["op"] or {}
        questions.append({"ask": f"Approve {op.get('op')} {op.get('title') or op.get('task') or ''}".strip()
                          + f" ({op.get('reason') or 'no reason given'})?", "task": op.get("task"), "why": g["why"]})
    return {**changes, "ops": kept, "questions": questions}, gated


def apply(engagement, run_dir, dry_run, max_changes, state, contexts):
    eng = dc.load_engagement(engagement, contexts)
    source = run_dir / dc.CHANGES_JSON
    target = run_dir / ("apply-dry-run.json" if dry_run else "apply.json")
    if not source.is_file():
        result = {"tool": "delivery-apply", "status": "nothing", "dry_run": dry_run,
                  "reason": f"no {dc.CHANGES_JSON} in the Run folder: the session changed no task"}
        dc.write_atomic(target, json.dumps(result, indent=1) + "\n")
        return result
    changes = dc.load_json(source, dc.CHANGES_JSON)
    pack = dc.load_pack(run_dir)
    domain = eng["rules"]["portal_domain"]
    if not domain:
        raise dc.Bad(f"{dc.RULES_MD} names no Portal domain; no task is written without one")
    if str((pack.get("settings") or {}).get("portal_domain") or "") != domain:
        raise dc.Bad("the pack's Portal domain is not the rules' one; re-run delivery_pack.py")
    kept, gated = gate(changes, pack)
    gated_file = run_dir / dc.PACK_DIR / "changes-gated.json"
    dc.write_atomic(gated_file, json.dumps(kept, indent=1) + "\n")
    command = [sys.executable, str(TASK_STACK_APPLY), str(gated_file), "--log", str(run_dir / "undo.jsonl"),
               "--out", str(target), "--domain", domain]
    if max_changes:
        command += ["--max-changes", str(max_changes)]
    if state:
        command += ["--state", state]
    if dry_run:
        command.append("--dry-run")
    if not TASK_STACK_APPLY.is_file():
        raise dc.Bad(f"task-stack-apply is not installed at {TASK_STACK_APPLY}")
    target.unlink(missing_ok=True)   # so an earlier run's result is never read as this one's
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    try:
        result = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else json.loads(done.stdout)
    except ValueError:
        raise dc.Bad(f"task-stack-apply gave no result (exit {done.returncode}): "
                     f"{(done.stderr or done.stdout).strip()[:300]}") from None
    # task-stack-apply exits 2 with {"status": "error"} when it could not run (no Portal, a bad
    # change set); that is this script's error too, never a success.
    if done.returncode == 2 or result.get("status") == "error":
        raise dc.Bad(f"task-stack-apply failed: {result.get('reason') or 'no reason given'}")
    result.update({"tool": "delivery-apply", "engagement": eng["name"], "gated": gated, "changes": str(source)})
    if not dry_run and result.get("status") != "refused":
        result["undo_log"] = str(run_dir / "undo.jsonl")
    dc.write_atomic(target, json.dumps(result, indent=1, default=str) + "\n")
    result["out"] = str(target)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description="Apply the session's task change set to the engagement's "
                                            "Portal domain, after holding back any op its rules do not allow.")
    p.add_argument("engagement", nargs="?", default="", help="Context name or path to a Context YAML file")
    p.add_argument("--run-dir", default="", help="The Run folder: changes.json and delivery/pack.json")
    p.add_argument("--dry-run", action="store_true", help="Read and check everything, write nothing")
    p.add_argument("--dry-run-if", default="", help="true, 1, yes or on: a dry run")
    p.add_argument("--max-changes", default="", help="At most this many writes (blank: task-stack-apply's default)")
    p.add_argument("--state", default="", help="task-stack-apply's write journal and lock folder")
    p.add_argument("--contexts-dir", default="", help="Where Context YAML files are found by name")
    a = p.parse_args(argv)
    try:
        if not a.engagement.strip():
            raise dc.Bad("ENGAGEMENT is required: the engagement's Context name")
        if not dc.blank(a.run_dir):
            raise dc.Bad("--run-dir is required")
        cap = dc.blank(a.max_changes)
        if cap and not cap.isdigit():
            raise dc.Bad(f"--max-changes wants a whole number, got {a.max_changes!r}")
        run_dir = Path(a.run_dir.strip()).expanduser().resolve()
        if run_dir == SKILL_DIR or SKILL_DIR in run_dir.parents:
            raise dc.Bad(f"{run_dir} is inside the skill folder; Run files live outside it")
        result = apply(a.engagement, run_dir,
                       a.dry_run or dc.truthy(a.dry_run_if), int(cap) if cap else None,
                       dc.blank(a.state), a.contexts_dir)
    except dc.Bad as exc:
        print(json.dumps({"tool": "delivery-apply", "status": "error", "reason": str(exc)}, indent=1))
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=1, default=str))
    return 3 if result.get("status") in ("partial", "refused") else 0


if __name__ == "__main__":
    sys.exit(main())
