#!/usr/bin/env python3
"""report-facts: the weekly report's figures and tables, kept in one facts set.

No number in the report comes from a model. Every figure carries a source, an as-of date and a
status (preliminary or final); a figure the week could not produce is recorded as not
available, never zero.

Subcommands:
  init          start a facts set for a period, one unanswered figure per standing metric
                (--profile seeds them from the role profile; --metric key=label adds one)
  set           record one figure (--value, or --not-available --reason); --source defaults
                to "the executive at Gate <n>"
  add-table     store a table exactly as supplied: --from a CSV, a Markdown pipe table or
                tab-separated cells (or standard input). Nothing is computed over it
  import-table  build a results table from a CSV of base columns, computing the variances,
                percent-of-revenue lines and the footing check (optional; never required)
  validate      check sources, dates, statuses and footing: exit 0 clean, 3 on an error
  tie-out       every number in a bullet under {{table:<key>}}, or on a line citing
                facts://<key>, has to be a cell or a figure: exit 0 clean, 3 findings

Example:
  python3 report_facts.py add-table --facts facts.json --key october --from pasted.txt \\
      --title "October results" --as-of 2027-10-31
"""

import argparse
import json
import sys
from pathlib import Path

import _facts as fx
import _profile as pf
from _common import FAILED, OK, Fail, read_text, run_main


def main():
    parser = argparse.ArgumentParser(description="The weekly report's figures and tables.")
    sub = parser.add_subparsers(dest="action", required=True)
    init = sub.add_parser("init")
    init.add_argument("--facts", required=True)
    init.add_argument("--period", required=True, help="the period end, YYYY-MM-DD")
    init.add_argument("--profile", default="", help="seed the standing metrics from this role profile")
    init.add_argument("--outline", default="", help="seed them from an older outline file")
    init.add_argument("--metric", action="append", default=[], help="key=label; repeatable")
    init.add_argument("--force", action="store_true")
    one = sub.add_parser("set")
    one.add_argument("--facts", required=True)
    one.add_argument("--key", required=True)
    one.add_argument("--label", default="")
    one.add_argument("--value", default=None)
    one.add_argument("--unit", default="usd", choices=fx.UNITS)
    one.add_argument("--as-of", required=True)
    one.add_argument("--status", required=True, choices=fx.STATUSES)
    one.add_argument("--source", default="")
    one.add_argument("--gate", default="2", choices=["1", "2", "3"])
    one.add_argument("--supplied-by", default="the executive")
    one.add_argument("--not-available", action="store_true")
    one.add_argument("--reason", default="")
    add = sub.add_parser("add-table")
    add.add_argument("--facts", required=True)
    add.add_argument("--key", required=True, help="what {{table:<key>}} names")
    add.add_argument("--from", "--csv", dest="source_path", default="", help="the table's file; stdin without it")
    add.add_argument("--title", required=True)
    add.add_argument("--as-of", required=True)
    add.add_argument("--source", default=fx.SUPPLIED_SOURCE)
    add.add_argument("--status", default="preliminary", choices=fx.STATUSES)
    add.add_argument("--json", action="store_true")
    imp = sub.add_parser("import-table")
    imp.add_argument("--facts", required=True)
    imp.add_argument("--key", required=True)
    imp.add_argument("--csv", required=True, help="row, type, components, favourable, percent_of_revenue, "
                                                  "actual, budget, forecast")
    imp.add_argument("--title", default="")
    imp.add_argument("--source", required=True)
    imp.add_argument("--as-of", required=True)
    imp.add_argument("--status", required=True, choices=fx.STATUSES)
    imp.add_argument("--revenue-row", default="Revenue")
    imp.add_argument("--row-header", default="Line")
    imp.add_argument("--json", action="store_true")
    for name in ("validate", "tie-out"):
        check = sub.add_parser(name)
        check.add_argument("--facts", required=True)
        check.add_argument("--json", action="store_true")
        if name == "tie-out":
            check.add_argument("--report", required=True, help="the drafted report, Markdown")
    args = parser.parse_args()

    if args.action == "init":
        target = Path(args.facts).expanduser()
        if target.exists() and not args.force:
            raise Fail(f"{target} exists; pass --force to overwrite it")
        seeds = []
        if args.profile:
            seeds += [m for m in pf.load_profile(args.profile)[0]["standing_metrics"] if m["facts_key"]]
        if args.outline:
            seeds += [m for c in pf.outline_from_file(args.outline)["categories"]
                      for m in c["standing_metrics"] if m["facts_key"]]
        seeds += [{"facts_key": k.strip(), "name": label.strip() or k.strip()}
                  for k, _, label in (m.partition("=") for m in args.metric) if k.strip()]
        facts = fx.empty_set(args.period, seeds)
        fx.save_set(target, facts)
        print(f"{target}: {len(facts['figures'])} figures, every one unanswered, for {args.period}")
        return OK

    facts = fx.load_set(args.facts)
    if args.action == "set":
        record = fx.set_figure(facts, args.key, label=args.label,
                               value=None if args.not_available else args.value, unit=args.unit,
                               source=args.source or f"the executive at Gate {args.gate}",
                               as_of=args.as_of, status=args.status, supplied_by=args.supplied_by,
                               reason=args.reason)
        fx.save_set(args.facts, facts)
        shown = "not available" if record["value"] is None else record["value"]
        print(f"{args.key}: {shown} ({record['unit']}), {record['status']}, as of {record['as_of']}, "
              f"from {record['source']}")
        return OK
    if args.action == "add-table":
        if args.source_path.strip():
            path = Path(args.source_path).expanduser()
            if not path.is_file():
                raise Fail(f"no table at {path}")
            text = read_text(path)
        elif sys.stdin.isatty():
            raise Fail("add-table was given no table: pass --from <path> or pipe it in")
        else:
            text = sys.stdin.read()
        table = fx.supplied_table(fx.read_pasted(text), key=args.key, title=args.title,
                                  source=args.source, as_of=args.as_of, status=args.status)
        facts["tables"][args.key] = table
        fx.save_set(args.facts, facts)
        print(json.dumps(table, indent=1) if args.json else
              f"{args.key}: {len(table['rows'])} rows under {len(table['columns']) + 1} columns, stored as "
              f"supplied, {table['status']}, as of {table['as_of']}. Nothing in it was computed. The "
              f"writer places {{{{table:{args.key}}}}}.")
        return OK
    if args.action == "import-table":
        table = fx.computed_table(args.csv, key=args.key, title=args.title, source=args.source,
                                  as_of=args.as_of, status=args.status, revenue_row=args.revenue_row,
                                  row_header=args.row_header)
        facts["tables"][args.key] = table
        fx.save_set(args.facts, facts)
        print(json.dumps(table, indent=1) if args.json else
              f"{args.key}: {len(table['rows'])} rows, {table['status']}, as of {table['as_of']}. "
              f"Rounding: {table['rounding']}. The writer places {{{{table:{args.key}}}}}.")
        return OK
    if args.action == "validate":
        result = fx.validate_set(facts)
        s = result["stats"]
        lines = ["# Facts set", "", f"{s['figures']} figures, {s['figures_supplied']} of them supplied, "
                 f"{s['tables']} table(s).", f"{s['errors']} errors, {s['warnings']} warnings."]
        for label, rows in (("Errors", result["errors"]), ("Warnings", result["warnings"])):
            lines += ["", f"## {label}"] + ([f"- {r['kind']}: {r['detail']}" for r in rows] or ["None."])
        print(json.dumps(result, indent=1) if args.json else "\n".join(lines))
        return FAILED if result["errors"] else OK
    report = Path(args.report).expanduser()
    if not report.is_file():
        raise Fail(f"no report at {report}")
    text = report.read_text(encoding="utf-8")
    findings = fx.tie_out(text, facts)
    result = {"findings": findings, "stats": {"markers": len(fx.TABLE_MARKER.findall(text)),
                                              "findings": len(findings)}}
    lines = [f"{result['stats']['markers']} table markers, {len(findings)} findings."]
    for row in findings:
        lines += [f"- {row['kind']} (line {row['line']}): {row['detail']}", f"    {row['text']}"]
    print(json.dumps(result, indent=1) if args.json else "\n".join(lines))
    return FAILED if findings else OK


if __name__ == "__main__":
    run_main(main)
