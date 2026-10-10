#!/usr/bin/env python3
"""Scan every skill in this toolbox with NVIDIA SkillSpector and summarise the results.

SkillSpector (https://github.com/NVIDIA/SkillSpector) is NVIDIA's security scanner for
agent skills. Its recursive mode looks one folder down, and the skills here sit two
down (<department>/skills/<skill>), so this script scans each department's skills/
folder, then any skill a scan left out, and writes:

  <out>/<department>.json     SkillSpector's own JSON report per department
  <out>/summary.json          one row per skill: score, severity, findings
  <out>/summary.md            the tables docs/security/skillspector.md is built from

Usage:
  python3 scripts/skillspector_scan.py [--out DIR] [--llm]

It needs the skillspector command:
  uv tool install git+https://github.com/NVIDIA/skillspector.git@v2.12.0

By default it runs the static analysis only (--no-llm): fast, free and offline apart
from SkillSpector's dependency lookups. --llm adds its semantic analysis, which needs a
provider configured in SkillSpector's environment variables.

Exit status: 0 when every skill was scanned; 2 when SkillSpector failed or is missing.
Findings never fail the run; read the summary.
"""

from __future__ import annotations

import argparse
import collections
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

TOOLBOX = Path(__file__).resolve().parent.parent
SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")


def scan(target: Path, out: Path, llm: bool, recursive: bool) -> dict:
    cmd = ["skillspector", "scan", str(target), "--format", "json", "--output", str(out)]
    cmd += ["--recursive"] if recursive else []
    cmd += [] if llm else ["--no-llm"]
    run = subprocess.run(cmd, capture_output=True, text=True)
    if run.returncode not in (0, 1) or not out.exists():
        sys.exit(f"skillspector failed on {target}:\n{run.stdout[-2000:]}{run.stderr[-2000:]}")
    return json.loads(out.read_text(encoding="utf-8"))


def skill_rows(report: dict, department: str) -> list[dict]:
    entries = report.get("skills") if report.get("multi_skill") else [report]
    rows = []
    for s in entries or []:
        risk = s.get("risk_assessment") or {}
        score = s.get("risk_score", risk.get("score"))
        if score is None:  # a skill the multi-skill scan left out
            continue
        name = s.get("name") or (s.get("skill") or {}).get("name") or Path(s.get("path", "")).name
        rules = collections.Counter(f'{i["id"]} {i["category"]}' for i in s.get("issues", []))
        rows.append({"department": department, "skill": name, "score": score,
                     "severity": s.get("risk_severity", risk.get("severity")),
                     "findings": s.get("finding_count", len(s.get("issues", []))), "rules": dict(rules)})
    return rows


def version() -> str:
    run = subprocess.run(["skillspector", "--version"], capture_output=True, text=True)
    return run.stdout.strip() or "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default="skillspector-report", help="folder for the reports")
    parser.add_argument("--llm", action="store_true", help="add SkillSpector's LLM analysis")
    args = parser.parse_args()
    if not shutil.which("skillspector"):
        print("skillspector is not installed; see this script's docstring", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for skills_dir in sorted(TOOLBOX.glob("*/skills")):
        dept = skills_dir.parent.name
        rows += skill_rows(scan(skills_dir, out / f"{dept}.json", args.llm, True), dept)
        done = {r["skill"] for r in rows if r["department"] == dept}
        for skill in sorted(p for p in skills_dir.iterdir() if (p / "SKILL.md").exists() and p.name not in done):
            rows += skill_rows(scan(skill, out / f"{dept}--{skill.name}.json", args.llm, False), dept)

    total = sum(1 for p in TOOLBOX.glob("*/skills/*/SKILL.md"))
    by_sev = collections.Counter(r["severity"] for r in rows)
    rules = collections.Counter()
    for r in rows:
        rules.update(r["rules"])
    stamp = datetime.date.today().isoformat()
    meta = {"date": stamp, "skillspector": version(), "mode": "static and LLM" if args.llm else "static (--no-llm)",
            "skills_scanned": len(rows), "skills_total": total, "by_severity": dict(by_sev),
            "findings": sum(r["findings"] for r in rows)}
    (out / "summary.json").write_text(json.dumps({"meta": meta, "skills": rows}, indent=1) + "\n", encoding="utf-8")

    lines = [f"Scanned {meta['skills_scanned']} of {total} skills on {stamp} with {meta['skillspector']}, "
             f"{meta['mode']}: {meta['findings']} findings.", "",
             "| Severity | Skills |", "|---|---:|"]
    lines += [f"| {s} | {by_sev.get(s, 0)} |" for s in SEVERITIES]
    lines += ["", "| Skill | Department | Score | Severity | Findings |", "|---|---|---:|---|---:|"]
    for r in sorted(rows, key=lambda r: (-r["score"], r["skill"])):
        if r["severity"] in ("CRITICAL", "HIGH"):
            lines.append(f"| `{r['skill']}` | {r['department']} | {r['score']} | {r['severity']} | {r['findings']} |")
    lines += ["", "| Rule | Findings |", "|---|---:|"]
    lines += [f"| {rule} | {n} |" for rule, n in rules.most_common()]
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:8]))
    print(f"\nReports in {out}/")
    return 0 if len(rows) == total else 2


if __name__ == "__main__":
    sys.exit(main())
