#!/usr/bin/env python3
"""Subledger sanity checks over a folder of AR and AP snapshots. Reads only; never writes.

Inputs: --snap, a folder holding four JSON lists of ERP rows (the dotted field names an
Intacct-style query returns, such as customer.id and audit.createdDateTime):
ar_invoices.json, ar_open.json, ap_bills.json, ap_open.json. --month is the target month.

Checks, printed as one JSON object:
  1. Customers invoiced in at least --min-active baseline months and silent this month
     (missing revenue or a billing lag).
  2. Vendors billed in at least --min-active baseline months, silent this month, with a
     baseline average at or above --vendor-floor (accrual candidates).
  3. Vendors whose bills this month exceed --spike-factor times their baseline average.
  4. Late postings: this month's documents created after month end, and last month's
     bills created this month or later.
  5. Negative (credit) invoices this month.
  6. Aging of open AR and AP as of --as-of, in buckets, with the largest counterparties and
     the documents older than --old-days and at least --old-min.

Example:
    python3 ar_ap_hygiene.py --snap ./snapshots/2026-09 --month 2026-09 --as-of 2026-09-30
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import sys
from pathlib import Path

BUCKETS = [(30, "0-30"), (60, "31-60"), (90, "61-90"), (180, "91-180"), (10**6, ">180")]
FILES = ("ar_invoices.json", "ar_open.json", "ap_bills.json", "ap_open.json")


def num(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def months_back(target: str, n: int) -> list[str]:
    """The n months before target, oldest first."""
    y, m = int(target[:4]), int(target[5:7])
    out = []
    for _ in range(n):
        m -= 1
        if m == 0:
            m, y = 12, y - 1
        out.append(f"{y:04d}-{m:02d}")
    return sorted(out)


def bucket(days: int) -> str:
    return next(name for limit, name in BUCKETS if days <= limit)


def aging(rows, date_field, today, name_field, id_field, old_days, old_min):
    amounts, counts, by_party, old = collections.defaultdict(float), collections.Counter(), collections.defaultdict(float), []
    for r in rows:
        age = (today - dt.date.fromisoformat(r[date_field][:10])).days
        amt = num(r.get("totalBaseAmountDue"))
        amounts[bucket(age)] += amt
        counts[bucket(age)] += 1
        by_party[f"{r.get(id_field, '')} {str(r.get(name_field, ''))[:30]}"] += amt
        if age > old_days and amt >= old_min:
            old.append({"doc": r.get("invoiceNumber") or r.get("billNumber"), "party": str(r.get(name_field, ""))[:30],
                        "date": r[date_field][:10], "due": round(amt)})
    return {
        "buckets": {name: {"amount": round(amounts[name]), "count": counts[name]} for _, name in BUCKETS},
        "total": round(sum(amounts.values())),
        "top_parties": [{"party": p, "due": round(a)} for p, a in sorted(by_party.items(), key=lambda x: -x[1])[:12]],
        f"older_than_{old_days}d_over_{int(old_min)}": sorted(old, key=lambda x: -x["due"]),
    }


def by_month(rows, date_field, months):
    """Count and total of documents per month, for the baseline and target months."""
    out = collections.defaultdict(lambda: {"count": 0, "total": 0.0})
    for r in rows:
        out[r[date_field][:7]]["count"] += 1
        out[r[date_field][:7]]["total"] += num(r.get("totalBaseAmount"))
    return {k: {"count": v["count"], "total": round(v["total"])} for k, v in sorted(out.items()) if k in months}


def matrix(rows, id_field, name_field, date_field):
    """Amount per party per month, and each party's name."""
    m, names = collections.defaultdict(lambda: collections.defaultdict(float)), {}
    for r in rows:
        m[r.get(id_field)][r[date_field][:7]] += num(r.get("totalBaseAmount"))
        names[r.get(id_field)] = r.get(name_field, "")
    return m, names


def run(a) -> dict:
    snap = Path(a.snap).expanduser()
    if not snap.is_dir():
        raise ValueError(f"not a directory: {snap}")
    missing = [n for n in FILES if not (snap / n).exists()]
    if missing:
        raise ValueError(f"missing in {snap}: {', '.join(missing)}")
    inv, ar_open, bills, ap_open = (json.loads((snap / n).read_text(encoding="utf-8")) for n in FILES)
    month = a.month
    base = months_back(month, a.baseline_months)
    prior = base[-1] if base else None
    today = dt.date.fromisoformat(a.as_of) if a.as_of else dt.date.today()
    next_month = (dt.date(int(month[:4]), int(month[5:7]), 1) + dt.timedelta(days=32)).replace(day=1).isoformat()

    cust, cnames = matrix(inv, "customer.id", "customer.name", "invoiceDate")
    vend, vnames = matrix(bills, "vendor.id", "vendor.name", "postingDate")

    silent_customers = []
    for c, months in cust.items():
        active = [b for b in base if months[b] != 0]
        if len(active) >= a.min_active and months[month] == 0:
            silent_customers.append({"id": c, "name": str(cnames[c])[:35],
                                     "prior_month": round(months[prior]) if prior else None,
                                     "baseline_avg": round(sum(months[b] for b in active) / len(active)),
                                     "active_months": len(active)})
    silent_vendors, spikes = [], []
    for v, months in vend.items():
        active = [b for b in base if months[b] != 0]
        if not active:
            continue
        avg = sum(months[b] for b in active) / len(active)
        if len(active) >= a.min_active and months[month] == 0 and avg >= a.vendor_floor:
            silent_vendors.append({"id": v, "name": str(vnames[v])[:35], "baseline_avg": round(avg),
                                   "prior_month": round(months[prior]) if prior else None})
        if len(active) >= 3 and avg >= a.spike_floor and months[month] > a.spike_factor * avg:
            spikes.append({"id": v, "name": str(vnames[v])[:35], "this_month": round(months[month]), "baseline_avg": round(avg)})

    created = lambda r: r.get("audit.createdDateTime", "")
    late_inv = [{"doc": r.get("invoiceNumber"), "customer": r.get("customer.id"), "amount": num(r.get("totalBaseAmount")),
                 "created": created(r)[:10]} for r in inv if r["invoiceDate"][:7] == month and created(r) >= next_month]
    late_bills = [r for r in bills if r["postingDate"][:7] == month and created(r) >= next_month]
    prior_late = [r for r in bills if prior and r["postingDate"][:7] == prior and created(r)[:7] >= month]
    credits = [{"doc": r.get("invoiceNumber"), "customer": str(r.get("customer.name", ""))[:25],
                "amount": num(r.get("totalBaseAmount")), "description": (r.get("description") or "")[:60]}
               for r in inv if r["invoiceDate"][:7] == month and num(r.get("totalBaseAmount")) < 0]
    total = lambda rows: {"count": len(rows), "total": round(sum(num(r.get("totalBaseAmount")) for r in rows))}

    return {
        "snap": str(snap), "month": month, "baseline": base, "as_of": today.isoformat(),
        "ar_by_month": by_month(inv, "invoiceDate", base + [month]),
        "ap_by_month": by_month(bills, "postingDate", base + [month]),
        "customers_silent": sorted(silent_customers, key=lambda x: -x["baseline_avg"]),
        "vendors_silent_accrual_candidates": sorted(silent_vendors, key=lambda x: -x["baseline_avg"]),
        "vendors_spiking": sorted(spikes, key=lambda x: -x["this_month"]),
        "late_postings": {"invoices_created_after_month_end": late_inv,
                          "bills_created_after_month_end": total(late_bills),
                          "prior_month_bills_created_this_month": total(prior_late)},
        "credits_this_month": credits,
        "ar_aging": aging(ar_open, "invoiceDate", today, "customer.name", "customer.id", a.old_days, a.old_min),
        "ap_aging": aging(ap_open, "postingDate", today, "vendor.name", "vendor.id", a.old_days, a.old_min),
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="ar-ap-hygiene", description="Subledger hygiene over AR and AP snapshots. JSON to stdout; never writes.")
    p.add_argument("--snap", required=True, help="folder holding ar_invoices.json, ar_open.json, ap_bills.json, ap_open.json")
    p.add_argument("--month", required=True, help="target month YYYY-MM")
    p.add_argument("--baseline-months", type=int, default=6)
    p.add_argument("--min-active", type=int, default=5, help="baseline months a party must be active in to count as silent now")
    p.add_argument("--vendor-floor", type=float, default=1000.0, help="minimum baseline average for a silent vendor to be listed")
    p.add_argument("--spike-factor", type=float, default=2.0)
    p.add_argument("--spike-floor", type=float, default=2000.0)
    p.add_argument("--as-of", help="aging date YYYY-MM-DD (default today)")
    p.add_argument("--old-days", type=int, default=90)
    p.add_argument("--old-min", type=float, default=5000.0)
    a = p.parse_args(argv)
    try:
        print(json.dumps(run(a), indent=1))
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ar-ap-hygiene: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
