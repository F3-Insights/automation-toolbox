# /// script
# dependencies = ["pyyaml", "openpyxl"]
# ///
"""Read one forecast workbook into an account x month extract, footed and tied.

Reads the sheet the Forecast folder's FORECAST-SETTINGS.yaml layout names, read-only (the
workbook is never saved). Keeps one row per account x department x location x class with every
month column it finds, and works out per-year totals (revenue, COGS, SG&A, bonus, pre-bonus and
post-bonus EBITDA) and quarter EBITDA on the folder's basis. Checks the workbook's own controls
(tie rows such as its EBITDA row, "must be zero" rows) and that the rows foot to the totals.

Inputs: the workbook, --folder (the Forecast folder), optionally --layout, --years, --label.
Writes the extract as JSON to --out when given; prints a summary (or the extract without its
rows, with --format json).

Exit 0 when it foots and ties, 1 when a foot or control fails (the extract is still written),
2 on a bad argument, a missing sheet or a missing column.

Example:
    python3 forecast_extract.py "delivery/Northwind forecast rev3.xlsx" --folder ~/Forecast --out new.json
"""

import argparse
import json
import sys
from pathlib import Path

from _common import ForecastError, extract


def render(x):
    lines = [f"{'OK' if x['ok'] else 'FAIL'}: {x['label']} ({Path(x['workbook']).name}!{x['sheet']}), "
             f"{len(x['rows'])} rows, months {x['months'][0]} to {x['months'][-1]}, basis {x['basis']}"]
    for year, summary in x["years"].items():
        t = summary["totals"]
        lines.append(f"  FY{year}: revenue {t['revenue']:,.0f}  COGS {t['cogs']:,.0f}  SG&A {t['sga']:,.0f}  "
                     f"bonus {t['bonus']:,.0f}  EBITDA pre-bonus {t['ebitda_pre_bonus']:,.0f}  "
                     f"post-bonus {t['ebitda']:,.0f}")
    lines += [f"  FAIL {c['name']}: {c['detail']}" for c in x["checks"] if not c["ok"]]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read one forecast workbook into a footed, tied extract.")
    parser.add_argument("workbook")
    parser.add_argument("--folder", required=True, help="the Forecast folder whose settings say how to read it")
    parser.add_argument("--layout", default="", help="a named layout in the settings; blank: default")
    parser.add_argument("--years", default="", help="fiscal years to summarise, comma-separated; blank: all present")
    parser.add_argument("--label", default="", help="what to call this forecast in the bridge (default: file name)")
    parser.add_argument("--out", default="", help="write the extract here (JSON)")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    try:
        years = [int(y) for y in args.years.split(",") if y.strip()] or None
    except ValueError:
        print(f"forecast-extract: --years must be comma-separated years, got {args.years!r}", file=sys.stderr)
        return 2
    try:
        x = extract(args.workbook, args.folder, args.layout, years, args.label)
    except ForecastError as exc:
        print(f"forecast-extract: {exc}", file=sys.stderr)
        return 2
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(x, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in x.items() if k != "rows"}, indent=1) if args.format == "json" else render(x))
    return 0 if x["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
