#!/usr/bin/env python3
"""task-stack-report: the short report of one task-stack Run, written from its Run folder.

Reads what the deterministic steps wrote, never the session's own account:
  before.json   task_stack_check.py before the session
  after.json    task_stack_check.py --baseline before.json after the writes
  apply.json    what task_stack_apply.py did (or apply-dry-run.json)
  changes.json  the session's change set, for its questions to the owner
  capture-record.json (or its dry-run twin) when the Run was a task capture

Writes RUN/REPORT.md: the trust score before and after, each component's direction, the
writes by op and outcome, every refused, failed or deferred op with its reason, the source
items of a capture, and the questions. A missing file is said to be missing.

Prints a first line such as "REPORT: score 57.7 -> 58.9 (+1.2); 14 applied, 3 refused" and the
path written. Exit 0 when it ran, 2 when the Run folder is not one.

Example:
  python3 task_stack_report.py --run RUN
"""

import argparse
import json
import sys

import _common as c


def load(path):
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def score(value):
    return "-" if not isinstance(value, (int, float)) else f"{value:.1f}"


def build(run):
    before, after = load(run / "before.json"), load(run / "after.json")
    applied, dry = load(run / "apply.json"), False
    if applied is None:
        applied = load(run / "apply-dry-run.json")
        dry = applied is not None
    changes = load(run / "changes.json")
    missing = [n for n, v in (("before.json", before), ("after.json", after), ("apply.json", applied),
                              ("changes.json", changes)) if v is None]
    if before is not None and after is not None and not after.get("baseline"):
        after = dict(after, baseline=c.compare(after, before))
    outcomes = {}
    for r in (applied or {}).get("results") or []:
        outcomes[r.get("outcome", "?")] = outcomes.get(r.get("outcome", "?"), 0) + 1
    return {"before": before, "after": after, "apply": applied, "dry_run": dry, "changes": changes,
            "missing": missing, "baseline": (after or {}).get("baseline") or {}, "outcomes": outcomes,
            "questions": (changes or {}).get("questions") or (applied or {}).get("questions") or [],
            "capture": load(run / "capture-record.json") or load(run / "capture-record-dry-run.json")}


def headline(r):
    b, parts = r["baseline"], []
    if b:
        delta = b.get("score_delta")
        parts.append(f"score {score(b.get('score_before'))} -> {score(b.get('score_after'))}"
                     + (f" ({delta:+.1f})" if isinstance(delta, (int, float)) else ""))
    elif r["before"]:
        parts.append(f"score before {score(((r['before'] or {}).get('overall') or {}).get('score'))}")
    if r["apply"] is not None:
        parts.append(", ".join(f"{n} {k.replace('_', ' ')}" for k, n in sorted(r["outcomes"].items())) or "no ops")
    if r["missing"]:
        parts.append("missing " + ", ".join(r["missing"]))
    return "REPORT: " + "; ".join(parts or ["nothing to report"])


def as_markdown(r, run):
    lines = ["# Task stack Run report", "", f"Run folder: `{run}`", "", headline(r), ""]
    b = r["baseline"]
    if b:
        lines += ["## Trust score", "", f"{score(b.get('score_before'))} before, {score(b.get('score_after'))} after.",
                  "", "| Component | Flagged before | Flagged after | Direction | New | Resolved |",
                  "|---|---:|---:|---|---:|---:|"]
        for k, e in (b.get("components") or {}).items():
            lines.append(f"| {k} | {e.get('flagged_before')} | {e.get('flagged_after')} | {e.get('direction')} "
                         f"| {e.get('new_items')} | {e.get('resolved_items')} |")
        worse = [k for k, e in (b.get("components") or {}).items() if e.get("direction") == "worse"]
        lines += ["", ("Worse: " + ", ".join(worse) + ". Other writers (people, other agents) also move the "
                       "score; the items below are this Run's.") if worse else "No component got worse.", ""]
    a = r["apply"]
    if a is not None:
        kinds = sorted(r["outcomes"])
        lines += ["## Writes" + (" (dry run: nothing was written)" if r["dry_run"] else ""), "",
                  "| Op | " + " | ".join(kinds) + " |", "|---|" + "---:|" * len(kinds)]
        for op, per in sorted((a.get("counts") or {}).items()):
            lines.append(f"| {op} | " + " | ".join(str(per.get(k, 0)) for k in kinds) + " |")
        lines.append("")
        for res in a.get("results") or []:
            if res.get("outcome") in ("applied", "would_apply"):
                lines.append(f"- {res.get('op')} {res.get('task') or res.get('id')}: {res.get('reason')}"
                             + (f" (evidence {res['evidence']})" if res.get("evidence") else ""))
        held = [x for x in a.get("results") or [] if x.get("outcome") in ("refused", "failed", "deferred")]
        if held:
            lines += ["", "### Not written", ""]
            for res in held:
                lines.append(f"- {res.get('op')} {res.get('task') or res.get('id')}: {res.get('outcome')} "
                             f"{res.get('code') or ''} {res.get('reason') or ''}".rstrip())
        if a.get("undo_log"):
            lines += ["", f"Undo: `python3 task_stack_apply.py --undo {a['undo_log']}` (add `--op ID` for one op)."]
        lines.append("")
    cap = r.get("capture")
    if cap and isinstance(cap.get("counts"), dict):
        lines += ["## Source items" + (" (dry run: the ledger was not written)" if cap.get("dry_run") else ""), "",
                  ", ".join(f"{n} {k}" for k, n in sorted(cap["counts"].items())) + ".", ""]
        for row in cap.get("rows") or []:
            if row.get("state") in ("seen", "stuck") and row.get("note") and row["note"] != "deferred past the cap":
                lines.append(f"- {row.get('id')}: {row.get('state')}, {row.get('note')}")
        lines.append("")
    if r["questions"]:
        lines += ["## Questions for the owner", ""]
        for i, q in enumerate(r["questions"], 1):
            q = q if isinstance(q, dict) else {"ask": str(q)}
            lines.append(f"{i}. {q.get('ask')}" + (f" ({q['task']})" if q.get("task") else "")
                         + (f" Why: {q['why']}" if q.get("why") else ""))
        lines.append("")
    if r["missing"]:
        lines += ["## Missing", "", "Not in the Run folder: " + ", ".join(r["missing"]) + ".", ""]
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(prog="task_stack_report.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run", dest="run_dir", required=True, help="The Run folder")
    args = p.parse_args(argv)
    try:
        run = c.guard_run_path(args.run_dir)
        if not run.is_dir():
            raise c.Stop(f"{run} is not a folder")
        result = build(run)
        (run / "REPORT.md").write_text(as_markdown(result, run), encoding="utf-8")
    except c.Stop as exc:
        print(c.safe(f"ERROR {exc}"), file=sys.stderr)
        sys.exit(2)
    print(c.safe(headline(result)))
    print(c.safe(f"  written: {run / 'REPORT.md'}"))
    sys.exit(0)


if __name__ == "__main__":
    main()
