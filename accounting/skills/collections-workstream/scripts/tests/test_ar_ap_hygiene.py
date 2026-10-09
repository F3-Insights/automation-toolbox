"""ar_ap_hygiene over an invented snapshot of Northwind Traders' subledgers."""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "ar_ap_hygiene.py"


def inv(cust, month, amt, created=None, num="INV"):
    return {"customer.id": cust, "customer.name": f"{cust} Co", "invoiceDate": f"{month}-15",
            "totalBaseAmount": amt, "invoiceNumber": f"{num}-{cust}-{month}",
            "audit.createdDateTime": created or f"{month}-15T10:00:00Z"}


def bill(vend, month, amt, created=None):
    return {"vendor.id": vend, "vendor.name": f"{vend} Supply", "postingDate": f"{month}-10",
            "totalBaseAmount": amt, "billNumber": f"B-{vend}-{month}",
            "audit.createdDateTime": created or f"{month}-10T10:00:00Z"}


def make_snap(tmp: Path) -> Path:
    base = ["2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"]
    invoices = [inv("ACME", m, 5000) for m in base]                         # silent in September
    invoices += [inv("LAKE", m, 1000) for m in base] + [inv("LAKE", "2026-09", 1200)]
    invoices += [inv("LAKE", "2026-09", 900, created="2026-10-03T09:00:00Z", num="LATE")]
    invoices += [inv("FAB", "2026-09", -300, num="CR")]
    bills = [bill("V1", m, 2500) for m in base]                              # silent: accrual candidate
    bills += [bill("V2", m, 3000) for m in base] + [bill("V2", "2026-09", 9000)]  # spike
    bills += [bill("V3", "2026-08", 400, created="2026-09-05T00:00:00Z")]    # prior month posted late
    ar_open = [{"customer.id": "ACME", "customer.name": "ACME Co", "invoiceDate": "2026-05-01",
                "totalBaseAmountDue": 8000, "invoiceNumber": "INV-OLD"},
               {"customer.id": "LAKE", "customer.name": "LAKE Co", "invoiceDate": "2026-09-20",
                "totalBaseAmountDue": 1200, "invoiceNumber": "INV-NEW"}]
    ap_open = [{"vendor.id": "V2", "vendor.name": "V2 Supply", "postingDate": "2026-09-10",
                "totalBaseAmountDue": 9000, "billNumber": "B-V2"}]
    snap = tmp / "snap"
    snap.mkdir()
    for name, rows in (("ar_invoices.json", invoices), ("ar_open.json", ar_open),
                       ("ap_bills.json", bills), ("ap_open.json", ap_open)):
        (snap / name).write_text(json.dumps(rows))
    return snap


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def test_checks(tmp_path):
    snap = make_snap(tmp_path)
    r = run("--snap", str(snap), "--month", "2026-09", "--as-of", "2026-09-30")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["baseline"][0] == "2026-03" and out["baseline"][-1] == "2026-08"
    assert [c["id"] for c in out["customers_silent"]] == ["ACME"]
    assert out["customers_silent"][0]["baseline_avg"] == 5000
    assert [v["id"] for v in out["vendors_silent_accrual_candidates"]] == ["V1"]
    assert out["vendors_spiking"] == [{"id": "V2", "name": "V2 Supply", "this_month": 9000, "baseline_avg": 3000}]
    assert [d["doc"] for d in out["late_postings"]["invoices_created_after_month_end"]] == ["LATE-LAKE-2026-09"]
    assert out["late_postings"]["prior_month_bills_created_this_month"] == {"count": 1, "total": 400}
    assert [c["doc"] for c in out["credits_this_month"]] == ["CR-FAB-2026-09"]
    ar = out["ar_aging"]
    assert ar["total"] == 9200 and ar["buckets"]["91-180"] == {"amount": 8000, "count": 1}
    assert ar["older_than_90d_over_5000"][0]["doc"] == "INV-OLD"
    assert out["ap_aging"]["buckets"]["0-30"]["amount"] == 9000


def test_missing_file_fails(tmp_path):
    snap = make_snap(tmp_path)
    (snap / "ap_open.json").unlink()
    r = run("--snap", str(snap), "--month", "2026-09")
    assert r.returncode == 1 and "ap_open.json" in r.stderr
