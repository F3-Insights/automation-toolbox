# /// script
# dependencies = ["pyyaml"]
# ///
"""Gather one company's board-package period before the session, reading only.

Collects the close's state (the month-end-workstream check on the close folder, or the
rules' Closed by hand list, by the rules' Close gate), the trial balance pulls for the period
and the one before (with the PRELIMINARY or FINAL label their pulled.md gives), the period's
results file (the highest version the Results file glob matches) and its table figures, the
supporting files, the deck template, the newest earlier packages, any package a person already
made for this period, and the package files the rules name.

Writes work/sources.json, work/sources.md and work/results-figures.csv in the period folder
and nothing else; a results-figures file that differs moves to work/superseded-<stamp>/
first. With --dry-run-if true (or 1, yes, on) the period folder is
<run-dir>/board-package/<period>, so nothing is written in the Reporting folder.

The first line says where the period stands: READY, ALREADY (a person made the package) or
NOT READY with the reason. Exit 0 whenever it ran; 2 on a bad argument or a missing Context.

    python3 board_package_pack.py acme-board --period 2026-09 --run-dir /tmp/run --dry-run-if true
"""

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import _common as bc


def pull_state(per, p: str) -> dict:
    tb = per.tb_file(p)
    pulled = tb.parent / "pulled.md"
    label = None
    if pulled.is_file():
        first = pulled.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
        label = "PRELIMINARY" if first and "PRELIMINARY" in first[0].upper() else "FINAL"
    return {"period": p, "trial_balance": str(tb), "exists": tb.is_file(), "label": label}


def describe(path: Path) -> dict:
    stat = path.stat()
    return {"path": str(path), "name": path.name, "bytes": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).replace(microsecond=0).isoformat()}


def write_results(per, rows) -> str:
    target = per.work / bc.RESULTS_FIGURES_CSV
    text = bc.to_csv(rows, bc.RESULTS_COLUMNS)
    if target.exists():
        if target.read_text(encoding="utf-8") == text:
            return "unchanged"
        aside = per.work / f"superseded-{bc.stamp()}"
        aside.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target), str(aside / target.name))
    target.write_text(text, encoding="utf-8")
    return "written"


def status_line(pack: dict):
    who = f"{pack['company']} {pack['period']}"
    if pack["people_package"]:
        return "already", f"ALREADY: {who}: a person already made the package ({pack['people_package']['name']})"
    problems = []
    if not pack["close"]["done"]:
        problems.append(f"the close is not done ({pack['close']['why']})")
    if not pack["results"]["file"]:
        problems.append(f"no results file matches {pack['results']['pattern']!r} in {pack['close_month']}")
    if not pack["pulls"][0]["exists"]:
        problems.append(f"no trial balance pull for {pack['period']}")
    if problems:
        return "not-ready", f"NOT READY: {who}: " + "; ".join(problems)
    return "ready", (f"READY: {who}: close done ({pack['close']['why']}); results {pack['results']['file']['name']} "
                     f"({pack['results']['figures']} table figures); trial balance "
                     f"{pack['pulls'][0]['label'] or 'unlabelled'}; {len(pack['supporting'])} supporting file(s); "
                     f"period folder {pack['period_dir']}")


def sources_md(pack: dict) -> str:
    close = pack["close"]
    out = [f"# Board package sources, {pack['company']} {pack['period']}", "",
           f"Packed {pack['packed_at']} by board-package-pack" + (" (dry run)" if pack["dry_run"] else "") + ".",
           "", pack["line"], "", "## Close", "",
           f"- Gate: {close['gate']}; done: {'yes' if close['done'] else 'no'} ({close['why']})"]
    for pull in pack["pulls"]:
        out.append(f"- Trial balance {pull['period']}: {'present' if pull['exists'] else 'missing'}"
                   + (f", {pull['label']}" if pull["label"] else "") + f" ({pull['trial_balance']})")
    out += ["", "## Results file", ""]
    if pack["results"]["file"]:
        out.append(f"- {pack['results']['file']['path']} ({pack['results']['figures']} table figures in "
                   f"work/{bc.RESULTS_FIGURES_CSV})")
        out += [f"- earlier version, not used: {other}" for other in pack["results"]["candidates"][1:]]
    else:
        out.append(f"- none matches {pack['results']['pattern']!r}")
    out += ["", "## Supporting files", ""] + ([f"- {s['path']}" for s in pack["supporting"]] or ["- none"])
    out += ["", "## Earlier packages (for the format)", ""] + (
        [f"- {s['path']} ({s['modified'][:10]})" for s in pack["previous_packages"]] or ["- none found"])
    if pack["template"]:
        out += ["", f"Deck template: {pack['template']['path']} "
                    f"({'present' if pack['template']['exists'] else 'missing'})"]
    if pack["people_package"]:
        out += ["", f"A person already made this period's package: {pack['people_package']['path']}"]
    out += ["", "## The package files", ""]
    for role, item in pack["package"].items():
        out.append(f"- {role}: " + ("none (the rules keep none)" if item is None else
                                     f"{item['path']} ({'exists' if item['exists'] else 'to write'})"))
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Gather COMPANY's PERIOD into the period folder's work/sources.json.")
    parser.add_argument("company", nargs="?", default="", metavar="COMPANY")
    bc.add_period_options(parser)
    parser.add_argument("--run-dir", default="", help="The Run folder")
    parser.add_argument("--dry-run-if", default="", help="true, 1, yes or on: write under --run-dir, never the package folder")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    dry = (bc.blank(args.dry_run_if) or "").lower() in ("true", "1", "yes", "on")
    per = bc.resolve(args)
    if dry and not bc.blank(args.period_dir):
        if not bc.blank(args.run_dir):
            raise bc.Bad("--dry-run-if is true but no --run-dir was given")
        per.period_dir = Path(args.run_dir.strip()).expanduser() / "board-package" / per.period
    rules = per.rules
    per.work.mkdir(parents=True, exist_ok=True)

    candidates = per.results_candidates()
    results = {"pattern": bc.fill(rules.results_file, per.period), "file": None,
               "candidates": [c.name for c in candidates], "figures": 0}
    if candidates:
        rows = bc.results_rows(candidates[0], per.period, rules.results_unit, rules.figure_ignore)
        results.update(file=describe(candidates[0]), figures=len(rows), written=write_results(per, rows),
                       csv=str(per.work / bc.RESULTS_FIGURES_CSV))
    people, template = per.people_package(), per.template()
    pack = {
        "schema": bc.SOURCES_SCHEMA, "company": per.company.name, "period": per.period, "dry_run": dry,
        "packed_at": bc.now_utc(), "period_dir": str(per.period_dir), "work": str(per.work),
        "close_folder": str(per.company.close), "close_month": str(per.close_month),
        "package_folder": str(per.company.package), "rules_file": str(per.company.rules_file),
        "close": bc.close_state(per),
        "pulls": [pull_state(per, per.period), pull_state(per, bc.prior_period(per.period))],
        "results": results,
        "supporting": [describe(p) for p in per.supporting()],
        "previous_packages": [describe(p) for p in per.previous_packages()],
        "people_package": describe(people) if people else None,
        "template": {"path": str(template), "exists": template.is_file()} if template else None,
        "package": {role: ({"path": str(p), "exists": p.is_file()} if p else None)
                    for role, p in per.package_files().items()},
        "review_note": str(per.review_note), "tieout_ledger": str(per.tieout_ledger),
        "evidence": str(per.evidence_file), "lender_pack": bool(rules.lender_pack),
    }
    pack["status"], pack["line"] = status_line(pack)
    (per.work / bc.SOURCES_JSON).write_text(json.dumps(pack, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (per.work / bc.SOURCES_MD).write_text(sources_md(pack), encoding="utf-8")
    if args.format == "json":
        print(json.dumps(pack, indent=1, ensure_ascii=False))
    else:
        print(pack["line"])
        print(f"  sources: {per.work / bc.SOURCES_JSON}")
    return 0


if __name__ == "__main__":
    bc.run_main(main)
