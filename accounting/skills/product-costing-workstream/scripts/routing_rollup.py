"""Routing minutes per finished good, its own and its components', tagged by factory.

A finished good's labour content is its own routing operations plus those of every
component it consumes, scaled by quantity per and divided by each routing's base quantity.
Inputs are CSV files; other header names are mapped with --map key=Header,...

  routing      material, operation, work_center, minutes, base_qty (blank base_qty is 1)
  --bom        parent, component, qty_per; recursed to any depth, a cycle reported and cut
  --wc-map     work_center, factory; an unmapped work centre is an error
  --standards  material, std_dl (the ERP's direct-labour standard per unit), optional
  --rates      factory, rate_per_min (the budget rate), optional

For each finished good (--fg to name them, else every parent that is not itself a
component) it reports own, linked and total minutes, the factories touched and a
mixed_factory flag. With standards and rates it compares the implied rate (std_dl /
total minutes) with the budget rate of the first factory: within --linked-tol when the
good has components, within --own-tol when it has none, otherwise the verdict is reject.

Prints a table (or JSON with --format json); --out also writes the per-part table as CSV.
Exit 1 when a rate is rejected, a work centre is unmapped or the BOM has a cycle; 2 on a
bad --map.

Example:
  python3 routing_rollup.py work/routing.csv --bom work/bom.csv --wc-map work/wc_factory.csv \\
      --standards work/std_dl.csv --rates work/rates.csv --out work/routing_rollup.csv
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

from _common import fail, num, parse_map, read_csv, require

DEFAULT_MAP = {k: k for k in ("material", "operation", "work_center", "minutes", "base_qty", "parent", "component", "qty_per", "factory", "std_dl", "rate_per_min")}


def own_minutes(routing, cm):
    """Minutes per unit and the work centres used, per material."""
    mins, wcs = defaultdict(float), defaultdict(set)
    for r in routing:
        mat = r[cm["material"]].strip()
        mins[mat] += (num(r.get(cm["minutes"]), 0.0) or 0.0) / (num(r.get(cm["base_qty"]), 1.0) or 1.0)
        wc = (r.get(cm["work_center"]) or "").strip()
        if wc:
            wcs[mat].add(wc)
    return mins, wcs


def rollup(routing, bom, wc_map, cm, standards, rates, only=None, own_tol=0.10, linked_tol=0.05):
    mins, wcs = own_minutes(routing, cm)
    children, components = defaultdict(list), set()
    for r in bom:
        parent, comp = r[cm["parent"]].strip(), r[cm["component"]].strip()
        children[parent].append((comp, num(r.get(cm["qty_per"]), 1.0) or 1.0))
        components.add(comp)
    findings = [{"check": "unmapped_work_center", "severity": "error", "work_center": wc, "detail": "no factory in --wc-map"}
                for wc in sorted({w for s in wcs.values() for w in s if w not in wc_map})]

    def linked(mat, path):
        """Minutes and work centres of everything under `mat`, cutting any cycle."""
        total, wcset = 0.0, set()
        for comp, qty in children.get(mat, []):
            if comp in path:
                findings.append({"check": "bom_cycle", "severity": "error", "material": comp, "detail": " -> ".join(path + (comp,))})
                continue
            sub_min, sub_wc = linked(comp, path + (comp,))
            total += qty * (mins.get(comp, 0.0) + sub_min)
            wcset |= wcs.get(comp, set()) | sub_wc
        return total, wcset

    goods = sorted(only) if only else sorted(set(children) - components) or sorted(mins)
    parts = []
    for fg in goods:
        own = mins.get(fg, 0.0)
        link, link_wc = linked(fg, (fg,))
        all_wc = wcs.get(fg, set()) | link_wc
        factories = sorted({wc_map[w] for w in all_wc if w in wc_map})
        row = {"material": fg, "own_min": round(own, 4), "linked_min": round(link, 4), "total_min": round(own + link, 4),
               "work_centers": sorted(all_wc), "factories": factories, "mixed_factory": len(factories) > 1}
        if row["mixed_factory"]:
            findings.append({"check": "mixed_factory", "severity": "warning", "material": fg, "detail": "routing crosses " + " and ".join(factories) + "; keep the pools separate"})
        std = standards.get(fg)
        if std is not None and factories and row["total_min"]:
            budget = rates.get(factories[0])
            if budget:
                implied = std / row["total_min"]
                basis, tol = ("linked", linked_tol) if link else ("own", own_tol)
                dev = (implied - budget) / budget
                row.update({"implied_rate": round(implied, 4), "budget_rate": budget, "deviation": round(dev, 4), "basis": basis, "verdict": "accept" if abs(dev) <= tol else "reject"})
                if row["verdict"] == "reject":
                    findings.append({"check": "rate_validation", "severity": "error", "material": fg, "detail": f"implied {implied:.4f}/min vs budget {budget:.4f}/min ({dev:+.1%}); {basis} tolerance is {tol:.0%}"})
        elif std is not None and not row["total_min"]:
            findings.append({"check": "standard_without_routing", "severity": "warning", "material": fg, "detail": f"std_dl {std:g} but zero routing minutes"})
        parts.append(row)
    errors = sum(1 for f in findings if f["severity"] == "error")
    return {"parts": parts, "findings": findings, "errors": errors, "passed": errors == 0}


def load(routing, bom="", wc_map="", standards="", rates="", cm=DEFAULT_MAP):
    """Read the input files and check their columns."""
    rt = read_csv(routing, "routing")
    require(rt, cm, ["material", "minutes"], "routing")
    bom_rows, wcm, std, rate = [], {}, {}, {}
    if bom:
        bom_rows = read_csv(bom, "bom")
        require(bom_rows, cm, ["parent", "component"], "bom")
    if wc_map:
        rows = read_csv(wc_map, "wc-map")
        require(rows, cm, ["work_center", "factory"], "wc-map")
        wcm = {r[cm["work_center"]].strip(): r[cm["factory"]].strip() for r in rows}
    if standards:
        rows = read_csv(standards, "standards")
        require(rows, cm, ["material", "std_dl"], "standards")
        std = {r[cm["material"]].strip(): v for r in rows if (v := num(r.get(cm["std_dl"]))) is not None}
    if rates:
        rows = read_csv(rates, "rates")
        require(rows, cm, ["factory", "rate_per_min"], "rates")
        rate = {r[cm["factory"]].strip(): v for r in rows if (v := num(r.get(cm["rate_per_min"]))) is not None}
    return rt, bom_rows, wcm, std, rate


def main(argv=None):
    ap = argparse.ArgumentParser(description="Roll routing minutes up to finished goods. Exit 1 on a rejected rate, an unmapped work centre or a BOM cycle.")
    ap.add_argument("routing", help="Routing CSV (material, operation, work_center, minutes, base_qty)")
    ap.add_argument("--bom", default="", help="Component list CSV (parent, component, qty_per)")
    ap.add_argument("--wc-map", default="", help="Work centre to factory CSV")
    ap.add_argument("--standards", default="", help="Direct-labour standards CSV (material, std_dl)")
    ap.add_argument("--rates", default="", help="Budget rate per minute by factory CSV")
    ap.add_argument("--fg", default="", help="Comma-separated finished goods to report (default: every top-level parent)")
    ap.add_argument("--map", dest="mapping", default="", help="Column overrides: key=Header")
    ap.add_argument("--own-tol", type=float, default=0.10, help="Rate tolerance for a good with no components (default 0.10)")
    ap.add_argument("--linked-tol", type=float, default=0.05, help="Rate tolerance for a good with components (default 0.05)")
    ap.add_argument("--out", help="Also write the per-part table as CSV")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    a = ap.parse_args(argv)

    try:
        cm = {**DEFAULT_MAP, **parse_map(a.mapping, DEFAULT_MAP)}
    except ValueError as exc:
        fail(str(exc), 2)
    try:
        routing, bom, wc_map, standards, rates = load(a.routing, a.bom, a.wc_map, a.standards, a.rates, cm)
    except ValueError as exc:
        fail(str(exc))
    only = {s.strip() for s in a.fg.split(",") if s.strip()} or None
    r = rollup(routing, bom, wc_map, cm, standards, rates, only, a.own_tol, a.linked_tol)
    if a.out:
        cols = ["material", "own_min", "linked_min", "total_min", "factories", "mixed_factory", "implied_rate", "budget_rate", "deviation", "basis", "verdict"]
        with Path(a.out).expanduser().open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for p in r["parts"]:
                w.writerow({**p, "factories": "|".join(p["factories"])})
    if a.format == "json":
        print(json.dumps(r, indent=1))
    else:
        print(f"{'material':16} {'own':>8} {'linked':>8} {'total':>8}  factories        verdict")
        for p in r["parts"]:
            v = p.get("verdict", "")
            if v:
                v += f" ({p['deviation']:+.1%} {p['basis']})"
            print(f"{p['material']:16} {p['own_min']:8.3f} {p['linked_min']:8.3f} {p['total_min']:8.3f}  {'+'.join(p['factories']) or '-':16} {v}")
        for f in r["findings"]:
            print(f"  {f['severity'].upper():7} {f['check']:24} {f.get('material') or f.get('work_center', ''):16} {f['detail']}")
        print("PASS" if r["passed"] else "FAIL")
    return 0 if r["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
