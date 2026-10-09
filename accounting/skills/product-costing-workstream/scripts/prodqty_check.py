"""Sanity checks on production and sales quantities before they enter a cost model.

Input is a CSV, one row per product per month: product, month (YYYY-MM), prod_qty and
optionally sales_qty. Other header names are mapped with --map key=Header,... (keys:
product, month, prod_qty, sales_qty, qty). Checks, each a finding with a severity:

  carry_forward      (error) in consecutive months, the share of products (at least five in
                     common) with identical prod_qty is at or above --carry-threshold; a
                     refreshed file never looks like that
  movement_recon     (error) with --movements (signed raw movements: product, month, qty),
                     the net per product and month equals prod_qty within --tolerance units
  negative_net       (info)  a product with a negative net movement, sign kept, never clipped
  no_labor_standard  (warning) with --standards (product plus any columns), a product with
                     production and no standard row
  duplicate_key      (error) the same product and month twice; the second row is dropped

Prints a text report (or JSON with --format json). Exit 1 when any error finding exists,
2 on a bad --map.

Example:
  python3 prodqty_check.py work/quantities.csv --movements work/movements.csv --standards work/labor_std.csv
"""

import argparse
import json
import sys
from collections import defaultdict

from _common import fail, num, parse_map, read_csv, require

DEFAULT_MAP = {"product": "product", "month": "month", "prod_qty": "prod_qty", "sales_qty": "sales_qty", "qty": "qty"}


def check_quantities(rows, colmap, movements=None, standards=None, carry_threshold=0.9, tolerance=0.5):
    p, m, q = colmap["product"], colmap["month"], colmap["prod_qty"]
    require(rows, colmap, ["product", "month", "prod_qty"], "quantities file")
    findings = []
    qty = defaultdict(dict)  # month -> product -> quantity
    seen = set()
    for r in rows:
        key = (r[p].strip(), r[m].strip())
        if key in seen:
            findings.append({"check": "duplicate_key", "severity": "error", "product": key[0], "month": key[1], "detail": "product and month appear twice"})
            continue
        seen.add(key)
        v = num(r.get(q))
        if v is not None:
            qty[key[1]][key[0]] = v
    months = sorted(qty)

    for prev, cur in zip(months, months[1:]):
        common = set(qty[prev]) & set(qty[cur])
        if len(common) < 5:
            continue  # too few products to judge
        same = sum(1 for k in common if qty[prev][k] == qty[cur][k])
        share = same / len(common)
        if share >= carry_threshold:
            findings.append({"check": "carry_forward", "severity": "error", "month": cur, "detail": f"{same} of {len(common)} products have the same prod_qty as {prev} ({share:.0%}); the file was probably not refreshed"})

    if movements is not None:
        require(movements, colmap, ["product", "month", "qty"], "movements file")
        net = defaultdict(float)
        for r in movements:
            v = num(r.get(colmap["qty"]))
            if v is not None:
                net[(r[p].strip(), r[m].strip())] += v
        for (product, month), n in sorted(net.items()):
            reported = qty.get(month, {}).get(product)
            if n < 0:
                findings.append({"check": "negative_net", "severity": "info", "product": product, "month": month, "detail": f"net movement {n:g}; keep the sign"})
            if reported is None:
                findings.append({"check": "movement_recon", "severity": "error", "product": product, "month": month, "detail": f"movements net {n:g} but no quantity row"})
            elif abs(reported - n) > tolerance:
                findings.append({"check": "movement_recon", "severity": "error", "product": product, "month": month, "detail": f"reported {reported:g}, movements net {n:g}, difference {reported - n:g}"})

    if standards is not None:
        require(standards, colmap, ["product"], "standards file")
        have = {r[p].strip() for r in standards}
        produced = {product for month in qty for product, v in qty[month].items() if v}
        for product in sorted(produced - have):
            findings.append({"check": "no_labor_standard", "severity": "warning", "product": product, "detail": "produced in the period but has no labour standard; its minutes will be absorbed by everyone else"})

    errors = sum(1 for f in findings if f["severity"] == "error")
    return {"months": months, "products": len({x for month in qty for x in qty[month]}), "findings": findings, "errors": errors, "passed": errors == 0}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check production quantities before they enter a cost model. Exit 1 on any error.")
    ap.add_argument("path", help="Quantities CSV (product, month, prod_qty, sales_qty)")
    ap.add_argument("--movements", default="", help="Signed raw movements CSV (product, month, qty)")
    ap.add_argument("--standards", default="", help="Labour standards CSV (product, ...)")
    ap.add_argument("--map", dest="mapping", default="", help="Column overrides: key=Header (keys: " + ", ".join(DEFAULT_MAP) + ")")
    ap.add_argument("--carry-threshold", type=float, default=0.9, help="Share of identical quantities that flags a carry-forward (default 0.9)")
    ap.add_argument("--tolerance", type=float, default=0.5, help="Units of difference tolerated in the movement reconciliation (default 0.5)")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    a = ap.parse_args(argv)

    try:
        colmap = {**DEFAULT_MAP, **parse_map(a.mapping, DEFAULT_MAP)}
    except ValueError as exc:
        fail(str(exc), 2)
    try:
        r = check_quantities(read_csv(a.path, "quantities file"), colmap,
                             read_csv(a.movements, "movements file") if a.movements else None,
                             read_csv(a.standards, "standards file") if a.standards else None,
                             a.carry_threshold, a.tolerance)
    except ValueError as exc:
        fail(str(exc))
    if a.format == "json":
        print(json.dumps(r, indent=1))
    else:
        print(f"{r['products']} products across {', '.join(r['months'])}: {len(r['findings'])} findings, {r['errors']} errors")
        for f in r["findings"]:
            where = " ".join(str(f[k]) for k in ("product", "month") if k in f)
            print(f"  {f['severity'].upper():7} {f['check']:18} {where:24} {f['detail']}")
        print("PASS" if r["passed"] else "FAIL")
    return 0 if r["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
