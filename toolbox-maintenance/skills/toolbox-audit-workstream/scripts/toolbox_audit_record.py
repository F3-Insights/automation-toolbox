# /// script
# dependencies = ["pyyaml"]
# ///
"""Write a toolbox audit Run's REPORT.md and keep the findings ledger week over week.

Reads RUN/findings.json (the session's ranked findings), RUN/scan.json (the counts and the
sections it could not read) and RUN/fix-commit.json (the fix branch), and:

- writes RUN/REPORT.md: the findings in rank order, each with its evidence and its one fix, marked
  new or still open against the ledger; the fix branch; what this audit could not see;
- upserts one row per finding in AUDIT_FOLDER/TOOLBOX-AUDIT-FINDINGS.csv (`first_seen` kept,
  `runs_seen` counted), and marks `resolved` every open row from an earlier Run whose finding is
  gone while its section was read this time;
- copies the report to AUDIT_FOLDER/reports/TOOLBOX-AUDIT-<yyyy-mm-dd>.md (` v2` beside it, never
  over it) and appends the Run to AUDIT_FOLDER/runs.jsonl, which toolbox_audit_check.py
  --precheck reads;
- writes RUN/changes.json for task-stack-apply: one create op per finding the session marked
  `task` (its `task_title` and the finding as the description) in --task-domain's catch-all
  project, each with the source key `toolbox-audit:<finding id>`, so a finding still open next
  week is never filed twice. With no --task-domain the ops are left out and the notes say so.

A denylisted name in a finding is written as "(withheld)" everywhere. A dry run writes RUN/REPORT.md and RUN/changes.json (marked dry) and nothing in the audit folder.
First line `RECORDED: ...` or `WOULD RECORD: ...`; `STALE: ...` when there is no findings.json.
Exit 0 when it ran, 2 when RUN is not a folder.

Example:
    python3 toolbox_audit_record.py --run RUN --folder ~/audits/toolbox --task-domain <domain uuid>
"""

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import _common as c

LEDGER = "TOOLBOX-AUDIT-FINDINGS.csv"
COLUMNS = ("id", "section", "level", "where", "title", "fix", "state", "first_seen", "last_seen", "runs_seen",
           "branch", "commit", "note", "updated_at", "by")
STATE_OF = {"proposed": "open", "fixed": "fixed", "task": "task", "dismissed": "dismissed"}


def read_ledger(folder):
    path = folder / LEDGER
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8", newline="") as fh:
        return {row["id"]: row for row in csv.DictReader(fh) if row.get("id")}


def write_ledger(folder, rows):
    path = folder / LEDGER
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for key in sorted(rows):
            writer.writerow({col: rows[key].get(col, "") for col in COLUMNS})
    tmp.replace(path)


def render(run, findings, scan, fix, known, gaps, dry_run):
    counts = scan.get("counts") or {}
    kept = sorted((f for f in findings if f.get("state") != "dismissed"), key=lambda f: (int(f.get("rank") or 9999), str(f.get("id"))))
    dismissed = [f for f in findings if f.get("state") == "dismissed"]
    new = sum(1 for f in kept if str(f.get("id")) not in known)
    out = [f"# Toolbox audit {date.today().isoformat()}" + (" (dry run)" if dry_run else ""), "",
           f"Run {run.name}. Scanned {counts.get('departments', '?')} departments, {counts.get('agents', '?')} agents "
           f"({counts.get('orchestrators', '?')} orchestrators), {counts.get('skills', '?')} skills and "
           f"{counts.get('scripts', '?')} scripts.",
           f"{len(kept)} findings ({new} new, {len(kept) - new} still open from earlier audits); "
           f"{len(dismissed)} scan items dismissed with a reason."]
    if fix:
        out += ["", f"Fix branch: {fix.get('line', '')}"]
    out += ["", "## Findings", ""]
    for i, f in enumerate(kept, 1):
        seen = known.get(str(f.get("id")))
        age = "new" if seen is None else f"open since {seen.get('first_seen') or '?'}"
        state = {"fixed": "fixed on the branch", "task": "filed as a task", "proposed": "proposed"}.get(str(f.get("state")), str(f.get("state")))
        out.append(f"{i}. **{c.one_line(f.get('title'))}** ({f.get('section')}, {f.get('level')}, {age}; {state})")
        if f.get("where"):
            out.append(f"   Where: {c.one_line(f.get('where'))}")
        evidence = [c.one_line(e) for e in (f.get("evidence") or [])][:5]
        if evidence:
            out.append(f"   Evidence: {'; '.join(evidence)}")
        out.append(f"   Fix: {c.one_line(f.get('fix'))}")
    if not kept:
        out.append("Nothing found.")
    unseen = [f"{k}: {v.get('error')}" for k, v in (scan.get("sections") or {}).items() if not v.get("ok")]
    if unseen or gaps:
        out += ["", "## What this audit could not see", ""] + [f"- {c.one_line(g)}" for g in unseen + list(gaps)]
    if dismissed:
        out += ["", "## Dismissed", ""]
        out += [f"- {c.one_line(f.get('title') or f.get('id'))}: {c.one_line(f.get('reason'))}" for f in dismissed[:40]]
        if len(dismissed) > 40:
            out.append(f"- and {len(dismissed) - 40} more in findings.json")
    return "\n".join(out) + "\n"


def source_key(finding_id):
    """The task-stack source key of a finding: `toolbox-audit:` and the id in the key's alphabet,
    with a hash on the end when it is too long, so the same finding always has the same key."""
    slug = re.sub(r"[^A-Za-z0-9_.:-]+", "-", finding_id).strip("-.:_") or "finding"
    if len(slug) > 81:
        slug = slug[:72].rstrip("-.:_") + "-" + hashlib.sha1(finding_id.encode("utf-8")).hexdigest()[:8]
    return f"toolbox-audit:{slug}"


def changes(run, findings, domain, dry_run):
    ops, notes = [], []
    for n, f in enumerate(sorted((f for f in findings if f.get("state") == "task"), key=lambda f: int(f.get("rank") or 9999)), 1):
        title = c.one_line(f.get("task_title"))
        if not title:
            notes.append(f"{f.get('id')}: marked task with no task_title; not filed")
            continue
        if not domain:
            notes.append(f"{f.get('id')}: no --task-domain; not filed")
            continue
        body = [c.one_line(f.get("title")), "", f"Fix: {c.one_line(f.get('fix'))}"]
        evidence = [c.one_line(e) for e in (f.get("evidence") or [])][:5]
        if evidence:
            body.append(f"Evidence: {'; '.join(evidence)}")
        body.append(f"From the toolbox audit Run {run.name} (REPORT.md in the Run folder and the audit folder).")
        ops.append({"id": f"t{n}", "op": "create", "title": title[:120], "domain": domain, "description": "\n".join(body),
                    "reason": c.one_line(f.get("title")), "source": source_key(str(f.get("id") or ""))})
    return {"tool": "task-stack-changes", "version": 1, "orchestrator": "toolbox-audit-orchestrator",
            "dry_run": dry_run, "ops": ops, "questions": [], "notes": notes}


def report_path(folder, today):
    path, n = folder / "reports" / f"TOOLBOX-AUDIT-{today}.md", 1
    while path.exists():
        n += 1
        path = folder / "reports" / f"TOOLBOX-AUDIT-{today} v{n}.md"
    return path


def record(run, folder, dry_run, task_domain=None):
    data = c.read_json(run / "findings.json")
    if data is None:
        return {"line": "STALE: no findings.json in the Run folder; nothing recorded", "recorded": False}
    # The session wrote the findings; a denylisted name in one is withheld from every file below.
    denylist = c.load_denylist()
    findings = c.scrub(c.findings_of(run), denylist)
    data = c.scrub(data, denylist)
    scan = c.read_json(run / "scan.json") or {}
    fix = c.read_json(run / "fix-commit.json")
    rows = read_ledger(folder)
    known = {k: v for k, v in rows.items() if v.get("state") in ("open", "task", "fixed")}
    text = render(run, findings, scan, fix, known, [str(g) for g in data.get("gaps") or []], dry_run)
    (run / "REPORT.md").write_text(text, encoding="utf-8")
    change_set = changes(run, findings, task_domain, dry_run)
    c.write_json(run / "changes.json", change_set)
    today = date.today().isoformat()
    ids = {str(f.get("id")) for f in findings}
    read_sections = {k for k, v in (scan.get("sections") or {}).items() if v.get("ok")}
    resolved = [k for k, v in known.items() if k not in ids and v.get("state") == "open" and v.get("section") in read_sections]
    kept = [f for f in findings if f.get("state") != "dismissed"]
    new = sum(1 for f in kept if str(f.get("id")) not in known)
    fixed = sum(1 for f in findings if f.get("state") == "fixed")
    summary = (f"{len(kept)} finding(s) ({new} new, {len(kept) - new} still open), {len(resolved)} resolved since the last "
               f"audit, {fixed} fixed on the branch, {len(change_set['ops'])} task(s) to file")
    if dry_run:
        return {"line": f"WOULD RECORD: {summary}; REPORT.md in the Run folder", "recorded": False}
    folder.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for f in findings:
        key = str(f.get("id") or "").strip()
        if not key:
            continue
        old = rows.get(key, {})
        is_fixed = f.get("state") == "fixed"
        rows[key] = {"id": key, "section": str(f.get("section") or ""), "level": str(f.get("level") or ""),
                     "where": c.one_line(f.get("where")), "title": c.one_line(f.get("title")), "fix": c.one_line(f.get("fix")),
                     "state": STATE_OF.get(str(f.get("state")), "open"), "first_seen": old.get("first_seen") or today,
                     "last_seen": today, "runs_seen": str(int(old.get("runs_seen") or 0) + 1),
                     "branch": (fix or {}).get("branch", "") if is_fixed else old.get("branch", ""),
                     "commit": (fix or {}).get("sha", "") if is_fixed else old.get("commit", ""),
                     "note": c.one_line(f.get("reason")), "updated_at": now, "by": run.name}
    for key in resolved:
        rows[key].update({"state": "resolved", "updated_at": now, "by": run.name, "note": f"not found by the audit of {today}"})
    write_ledger(folder, rows)
    report = report_path(folder, today)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(text, encoding="utf-8")
    with (folder / "runs.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"run": run.name, "date": today, "at": now, "findings": len(kept), "new": new,
                             "resolved": len(resolved), "fixed": fixed,
                             "branch": (fix or {}).get("branch") if (fix or {}).get("committed") else None,
                             "report": str(report)}) + "\n")
    return {"line": f"RECORDED: {summary}; {report}", "recorded": True, "report": str(report)}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render a toolbox audit Run's REPORT.md and keep the findings ledger.")
    ap.add_argument("--run", required=True, help="the Run folder")
    ap.add_argument("--folder", required=True, help="the audit folder (reports, the findings ledger, runs.jsonl)")
    ap.add_argument("--task-domain", default="", help="the Portal domain whose catch-all project takes the tasks")
    ap.add_argument("--dry-run", action="store_true", help="write REPORT.md and changes.json in the Run folder only")
    ap.add_argument("--dry-run-if", default="", help="a runner's dry-run value: true means --dry-run")
    args = ap.parse_args(argv)
    try:
        result = record(c.run_folder(args.run), Path(args.folder).expanduser(), args.dry_run or c.truthy(args.dry_run_if),
                        args.task_domain.strip() or None)
    except (c.AuditError, OSError, csv.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(result["line"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
