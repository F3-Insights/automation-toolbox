# /// script
# dependencies = ["python-pptx", "openpyxl"]
# ///
"""List every figure printed in a board-package file, with where it is.

Reads a deck (.pptx: text, tables, charts and speaker notes, slide by slide), an HTML file
(tables and visible text), a workbook (.xlsx: every numeric cell) or a text file (.md, .txt:
running text and Markdown tables, line by line). A cell holding one number is a figure (a bare
year excepted); in running text only a number printed as one is ($, k, M, %, parentheses, a
thousands comma, a decimal point or a sign), so '3 sites' and dates are not. A table's unit
comes from its header or caption ($k, $000, thousands, $M, millions); --unit is the unit of a
bare number otherwise.

Three outputs:
  default     every figure: file, location, where, printed, value, unit, context
  --results   the results file's table figures (one HTML file) as results-figures rows:
              metric '<row label> | <column header>', value in dollars
  --ledger    the skeleton of the package's figure ledger (id,file,location,printed,unit,
              metric,source,note), ids F1, F2 ... across the files, source left blank

--out writes the CSV to a new file and refuses one that exists. Exit 0 when it ran, 1 when
--out exists, 2 on a bad argument or an unreadable file.

    python3 board_package_figures.py deck.pptx script.md email.md --ledger --out work/package-figures.csv
"""

import argparse
import json
from pathlib import Path

import _common as bc

FIGURE_COLUMNS = ("file", "location", "where", "printed", "value", "unit", "context")


def ledger_rows(paths, unit) -> list:
    rows = []
    for path in paths:
        for f in bc.extract(path, unit):
            loc = f["location"]
            if path.suffix.lower() == ".pptx" and f["where"] != "text":
                loc = f"{loc} {f['where']}"
            rows.append({"id": f"F{len(rows) + 1}", "file": path.name, "location": loc, "printed": f["printed"],
                         "unit": f["unit"], "metric": f["context"], "source": "", "note": ""})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Every figure printed in FILE..., with where it is.")
    parser.add_argument("files", nargs="*", metavar="FILE")
    parser.add_argument("--unit", default="", help="The unit of a bare number where no header names one: 1, k or M")
    parser.add_argument("--results", action="store_true", help="Write the results file's figure list (one HTML file)")
    parser.add_argument("--period", default="", help="yyyy-mm, for --results")
    parser.add_argument("--ledger", action="store_true", help="Write the skeleton of the package's figure ledger")
    parser.add_argument("--out", default="", help="Write the CSV here (refused if it exists)")
    parser.add_argument("--format", choices=["csv", "json", "text"], default="csv")
    args = parser.parse_args()

    paths = [Path(f).expanduser() for f in args.files if bc.blank(f)]
    if not paths:
        raise bc.Bad("FILE is required")
    unit = bc.blank(args.unit)
    if unit:
        bc.unit_multiplier(unit)
    if args.results and args.ledger:
        raise bc.Bad("--results and --ledger are different outputs; give one")
    if args.results:
        if len(paths) != 1:
            raise bc.Bad("--results reads one results file")
        rows, columns = bc.results_rows(paths[0], bc.check_period(bc.blank(args.period) or ""), unit), bc.RESULTS_COLUMNS
    elif args.ledger:
        rows, columns = ledger_rows(paths, unit), bc.PACKAGE_COLUMNS
    else:
        rows, columns = [f for p in paths for f in bc.extract(p, unit)], FIGURE_COLUMNS

    if bc.blank(args.out):
        target = Path(args.out).expanduser()
        if target.exists():
            raise bc.Refused(f"{target} exists; this command never overwrites (move it aside or pick another name)")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(bc.to_csv(rows, columns), encoding="utf-8")
        print(f"WROTE {target} ({len(rows)} rows)")
    elif args.format == "json":
        print(json.dumps(rows, indent=1, ensure_ascii=False))
    elif args.format == "text":
        for r in rows:
            print("  ".join(str(r.get(c, "")) for c in columns))
        print(f"{len(rows)} figure(s)")
    else:
        print(bc.to_csv(rows, columns), end="")
    return 0


if __name__ == "__main__":
    bc.run_main(main)
