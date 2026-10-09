# /// script
# dependencies = ["pyyaml"]
# ///
"""Tie every figure in a board package to the closed books.

Reads the figure ledger the writer keeps (work/package-figures.csv: id,file,location,printed,
unit,metric,source,note) and computes each figure from the source it names:

  results:<metric> or results:R12   the results file's figure (work/results-figures.csv)
  tb:<accounts>                     the closed trial balance's ending balance, summed over the
                                    accounts (10400, 10400-10999, 10400, 10600)
  tb-month:<accounts>               the period's activity (year-to-date less the prior period's)
  tb-ytd:<accounts>                 the year-to-date activity
  calc:<expression>                 + - * / and parentheses over other figures by id (calc:F3/F1*100)
  text:                             an amount the results file prints in its prose
  person:<who and where>            stated by a person; not computed, named in the review note

A leading - negates (revenue is a credit in the ledger). The trial balance pulls are
<close>/{yyyy}/{yyyy-mm}/work/source/trial-balance-{yyyy-mm}.json. A figure ties when its
printed value equals the computed value rounded half up to the precision it is printed at
('951' in $k ties to 950,808), within the rules' Tie-out tolerance.

Writes tieout-ledger-<p>.csv beside the package in report-tieout's ledger format (one row for
the package and one for the books per computed figure) and the result to
work/tieout-<p>.json; a previous ledger that differs moves to work/superseded-<stamp>/ first.
--dry-run writes nothing. Exit 0 when every figure ties (stated figures and owner-approved
exceptions allowed), 1 when one does not, 2 on a bad argument or a missing file.

    python3 board_package_tieout.py acme-board --period 2026-09 --period-dir "Reporting/2026-09"
"""

import argparse
import json
import shutil

import _common as bc


def write(per, result) -> list:
    """Write the tie-out ledger and the result; a previous ledger that differs moves aside first."""
    text = bc.tieout_ledger_text(result)
    target = per.tieout_ledger
    notes = []
    if target.exists():
        if target.read_text(encoding="utf-8") == text:
            notes.append(f"UNCHANGED {target.name}")
        else:
            aside = per.work / f"superseded-{bc.stamp()}"
            aside.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(aside / target.name))
            notes.append(f"MOVED the previous {target.name} to {aside.name}/")
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        notes.append(f"WROTE {target}")
    per.tieout_json.parent.mkdir(parents=True, exist_ok=True)
    slim = {k: v for k, v in result.items() if k != "ledger_rows"}
    per.tieout_json.write_text(json.dumps(slim, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return notes


def render(result) -> str:
    counts = ", ".join(f"{n} {s}" for s, n in sorted(result["counts"].items()))
    out = [f"board-package-tieout {result['company']} {result['period']}: {counts}"]
    for f in result["figures"]:
        if f["state"] in ("differs", "error"):
            mark = "EXCEPTION" if f.get("exception") is not None else f["state"].upper()
            out.append(f"  {mark:9} {f['id']:5} {f['file']} {f['location']} {f['printed']}  "
                       f"[{f['source']}]  {f.get('detail', '')}")
    for k in result["report_tieout"]["findings"]:
        out.append(f"  REPORT-TIEOUT {k['check'].upper()} {k['metric']}: {k['detail']}")
    stated = [f["id"] for f in result["figures"] if f["state"] == "stated"]
    if stated:
        out.append(f"  stated by a person (name each in the review note): {', '.join(stated)}")
    out.append("ALL TIE" if result["passed"] else f"NOT TIED: {', '.join(result['failing']) or 'report-tieout findings'}")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Tie every figure in COMPANY's package for PERIOD to the closed books.")
    parser.add_argument("company", nargs="?", default="", metavar="COMPANY")
    bc.add_period_options(parser)
    parser.add_argument("--dry-run", action="store_true", help="Compute and report; write nothing")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    per = bc.resolve(args)
    result = bc.tieout(per)
    notes = [] if args.dry_run else write(per, result)
    if args.format == "json":
        print(json.dumps({k: v for k, v in result.items() if k != "ledger_rows"}, indent=1, ensure_ascii=False))
    else:
        print(render(result))
        for line in notes:
            print(line)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    bc.run_main(main)
