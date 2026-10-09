"""An invented billing folder shared by the firm-billing tests.

The firm bills Acme Components (a retainer plus capped hours, in arrears, one month to catch up),
Northwind Traders (a milestone and travel at cost, terms not yet confirmed), Fabrikam Logistics
(a quarterly retainer that needs a PO) and Lakeview Hardware (billed in advance, already invoiced).
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import yaml

SCRIPTS = Path(__file__).resolve().parents[1]
PERIOD = "2026-09"
AS_OF = "2026-10-05"   # a Monday
LAKEVIEW_INVOICE = "(F3) Invoice 0017 to (Lakeview) 2026-09-01.pdf"


def billing_data(tmp: Path) -> dict:
    return {
        "version": 1,
        "settings": {"invoice_folders": [str(tmp / "issued")], "payment_terms_days": 30,
                     "time_records_dir": str(tmp / "time"), "currency": "USD"},
        "firm": {"name": "F3 Insights", "address": ["1 Example Way"], "email": "billing@example.com",
                 "payment_instructions": "ACH to the account on file"},
        "contracts": [
            {"id": "acme-ops", "client": "Acme Components", "invoice_tag": "Acme",
             "bill_to": {"name": "Acme Components", "attention": "Accounts Payable", "address": ["9 Mill Road"],
                         "email": "ap@example.com"},
             "time_records_client_key": "acme", "start": "2026-01-01", "cadence": "monthly", "timing": "arrears",
             "email_delivery": "outlook-drafts", "confirmed": True,
             "rates": [{"id": "retainer", "kind": "retainer", "amount": 5000, "description": "Operations support"},
                       {"id": "hours", "kind": "hourly", "rate": 200, "cap_hours": 10,
                        "description": "Additional hours"}]},
            {"id": "northwind-build", "client": "Northwind Traders", "invoice_tag": "Northwind",
             "bill_to": {"name": "Northwind Traders"}, "start": "2026-06-01", "cadence": "milestone",
             "email_delivery": "file", "confirmed": False,
             "rates": [{"id": "m1", "kind": "milestone", "amount": 7500, "due": "2026-09",
                        "description": "Phase 1 readout"},
                       {"id": "travel", "kind": "pass-through", "markup_pct": 0, "description": "Travel at cost"}]},
            {"id": "fabrikam-qtr", "client": "Fabrikam Logistics", "invoice_tag": "Fabrikam",
             "bill_to": {"name": "Fabrikam Logistics"}, "start": "2026-01-01", "cadence": "quarterly",
             "po": {"required": True, "number": None}, "confirmed": True,
             "rates": [{"id": "retainer", "kind": "retainer", "amount": 3000, "description": "Advisory retainer"}]},
            {"id": "lakeview-adv", "client": "Lakeview Hardware", "invoice_tag": "Lakeview",
             "bill_to": {"name": "Lakeview Hardware"}, "start": "2026-03-01", "timing": "advance", "confirmed": True,
             "rates": [{"id": "retainer", "kind": "retainer", "amount": 2000, "description": "Retainer"}]},
        ],
    }


def contract_of(data: dict, cid: str) -> dict:
    return next(k for k in data["contracts"] if k["id"] == cid)


def write_yaml(folder: Path, mutate=None) -> None:
    data = billing_data(folder.parent)
    if mutate:
        mutate(data)
    (folder / "BILLING.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def time_records(tmp: Path, last_day_of_september: int = 30) -> None:
    """Acme 0.5 h a day in August and 0.4 h a day in September; and 3 h for other-co, a client key no contract names."""
    rows = ["date,client_key,hours"]
    rows += [f"2026-08-{d:02d},acme,0.5" for d in range(1, 32)]
    rows += [f"2026-09-{d:02d},acme,0.4" for d in range(1, last_day_of_september + 1)]
    rows += ["2026-09-03,other-co,3"]
    (tmp / "time").mkdir(parents=True, exist_ok=True)
    (tmp / "time" / "hours.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")


def billing_folder(tmp: Path, mutate=None, september_days: int = 30) -> Path:
    folder = tmp / "billing"
    folder.mkdir(parents=True, exist_ok=True)
    write_yaml(folder, mutate)
    issued = tmp / "issued" / "2026"
    (issued / "07").mkdir(parents=True, exist_ok=True)
    for name in ("(F3) Invoice 0016 to (Acme) 2026-08-01.pdf", "(F3) Invoice 0015 to (Fabrikam) 2026-07-01.pdf",
                 LAKEVIEW_INVOICE, "not an invoice.txt"):
        (issued / name).write_text("pdf")
    (issued / "07" / "(F3) Invoice 0014 to (Acme) 2026-07-01.pdf").write_text("pdf")
    time_records(tmp, september_days)
    return folder


def pdir_of(folder: Path) -> Path:
    return folder / PERIOD[:4] / PERIOD


def run(script: str, *args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)], capture_output=True, text=True)


def pull(folder: Path, *extra) -> dict:
    res = run("firm_billing_pull.py", folder, "--period", PERIOD, "--as-of", AS_OF, *extra)
    assert res.returncode == 0, res.stderr
    return json.loads((pdir_of(folder) / "work" / "source" / "billing-pull.json").read_text())


def acme_lines(folder: Path, **change) -> Path:
    doc = {"contract": "acme-ops", "period": PERIOD, "invoice_date": "2026-10-01", "months": ["2026-09"],
           "lines": [{"rate_id": "retainer", "month": "2026-09", "quantity": 1, "unit_price": 5000, "amount": 5000},
                     {"rate_id": "hours", "month": "2026-09", "quantity": 10, "unit_price": 200, "amount": 2000}]}
    doc.update(change)
    path = pdir_of(folder) / "work" / "lines" / "acme-ops.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc))
    return path


def draft_acme(folder: Path, **change) -> Path:
    res = run("firm_billing_draft.py", folder, "--period", PERIOD, "--contract", "acme-ops",
              "--lines", acme_lines(folder, **change))
    assert res.returncode == 0, res.stdout + res.stderr
    return Path(res.stdout.split("DRAFTED: ", 1)[1].rsplit(" total ", 1)[0])


def record(folder: Path, cid: str, state: str, *extra) -> subprocess.CompletedProcess:
    return run("firm_billing_record.py", folder, "--period", PERIOD, "--contract", cid, "--state", state, *extra)


def done_folder(tmp: Path) -> Path:
    """A period with every test met: Acme drafted and passed (hours trimmed to August's cap and
    August named in the note), the rest given reasons."""
    folder = billing_folder(tmp, lambda d: contract_of(d, "fabrikam-qtr").update(po={"required": True, "number": "PO-7"}))
    pull(folder)
    path = draft_acme(folder)
    review = pdir_of(folder) / "review" / "acme-ops review.md"
    review.parent.mkdir(parents=True, exist_ok=True)
    review.write_text("PASS")
    assert record(folder, "acme-ops", "drafted", "--draft", path, "--note", "2026-08 billed on its own invoice",
                  "--review", "PASS", "--review-file", review).returncode == 0
    assert record(folder, "northwind-build", "question", "--question", "Q-1", "--note", "milestone not evidenced").returncode == 0
    assert record(folder, "fabrikam-qtr", "not-billable", "--note", "billed next quarter").returncode == 0
    assert record(folder, "lakeview-adv", "already-billed", "--evidence", LAKEVIEW_INVOICE).returncode == 0
    assert record(folder, "client:other-co", "not-billable", "--note", "internal work").returncode == 0
    return folder
