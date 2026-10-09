#!/usr/bin/env python3
# /// script
# dependencies = ["pyyaml"]
# ///
"""Write one contract's draft invoice from a preparer's lines file, or verify an existing draft.

    python3 firm_billing_draft.py FOLDER --period P --contract ID --lines FILE [--period-dir DIR] [--format text|json]
    python3 firm_billing_draft.py FOLDER --verify JSON [--period P] [--period-dir DIR] [--format text|json]

Drafting checks the lines file (BILLING.md beside this skill, "The lines file") against
BILLING.yaml and the period's billing pull. Any breach prints "REFUSED: <reason>" per line and
writes nothing. Otherwise it writes invoices/<contract> <period> invoice DRAFT.{json,md,html} in
the period folder (DRAFT v2, v3 ... when one is already there; never overwrites) and prints
"DRAFTED: <json path> total <amount>". The draft carries the pull's proposed number; the owner
assigns the real number when issuing.

--verify re-derives an existing draft and prints "OK: <json path> total <amount>" or the
refusals. A blank --period is the draft's own period.

Exit 0 drafted or verified, 1 refused, 2 a bad argument or an unreadable file.

Example:
    python3 firm_billing_draft.py ~/Billing --period 2026-09 --contract acme-ops \\
        --lines ~/Billing/2026/2026-09/work/lines/acme-ops.json
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import _common as c


def free_stem(invoices: Path, contract: str, period: str) -> str:
    """The first "... DRAFT[ vN]" stem none of whose three files exists."""
    version = 1
    while True:
        stem = f"{contract} {period} invoice DRAFT" + ("" if version == 1 else f" v{version}")
        if not any((invoices / f"{stem}{ext}").exists() for ext in (".json", ".md", ".html")):
            return stem
        version += 1


def party_lines(party: dict, attention: bool = False) -> list[str]:
    out = [str(party.get("name", ""))] if attention else []
    if attention and party.get("attention"):
        out.append(f"Attention: {party['attention']}")
    out += [str(a) for a in party.get("address") or []]
    if party.get("email"):
        out.append(str(party["email"]))
    return out


def render_md(d: dict) -> str:
    firm, bill = d["firm"] or {}, d["bill_to"] or {}
    number = d["proposed_number"] or "to be assigned"
    out = [f"# DRAFT invoice, proposed number {number}", "",
           "DRAFT: not issued. The owner assigns the real number when issuing.", "",
           f"**{firm.get('name', '')}**", *party_lines(firm), "", "**Bill to**", *party_lines(bill, True), "",
           f"- Proposed number: {number}", f"- Invoice date: {d['invoice_date']}",
           f"- Due date: {d['due_date']}", f"- Period: {', '.join(d['months'])}"]
    if d.get("po_number"):
        out.append(f"- PO: {d['po_number']}")
    out += ["", "| Description | Quantity | Unit price | Amount |", "|---|---:|---:|---:|"]
    out += [f"| {l['description']} | {l['quantity']:g} | {c.fmt_money(l['unit_price'])} | {c.fmt_money(l['amount'])} |"
            for l in d["lines"]]
    out += [f"| **Total ({d['currency']})** | | | **{c.fmt_money(d['total'])}** |", ""]
    if firm.get("payment_instructions"):
        out += ["**Payment**", "", str(firm["payment_instructions"]), ""]
    return "\n".join(out)


def render_html(d: dict) -> str:
    e = lambda v: html.escape(str(v if v is not None else ""))  # noqa: E731
    firm, bill = d["firm"] or {}, d["bill_to"] or {}
    rows = "\n".join(f"<tr><td>{e(l['description'])}</td><td class=n>{e(format(l['quantity'], 'g'))}</td>"
                     f"<td class=n>{e(c.fmt_money(l['unit_price']))}</td><td class=n>{e(c.fmt_money(l['amount']))}</td></tr>"
                     for l in d["lines"])
    po = f"<div>PO: {e(d['po_number'])}</div>" if d.get("po_number") else ""
    pay = f"<h3>Payment</h3><p>{e(firm['payment_instructions'])}</p>" if firm.get("payment_instructions") else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>DRAFT invoice {e(d['contract'])} {e(d['period'])}</title>
<style>
body{{font-family:Helvetica,Arial,sans-serif;color:#111;margin:2.5em auto;max-width:48em;font-size:11pt}}
.draft{{color:#b00;font-size:28pt;font-weight:bold;letter-spacing:.2em}}
header{{display:flex;justify-content:space-between;border-bottom:2px solid #111;padding-bottom:1em}}
table{{width:100%;border-collapse:collapse;margin:1.5em 0}}
th,td{{border-bottom:1px solid #ccc;padding:.4em;text-align:left}} .n{{text-align:right}}
tfoot td{{font-weight:bold;border-top:2px solid #111}}
.meta div{{margin:.15em 0}} .bill{{margin:1.5em 0}}
@media print{{body{{margin:1em}}}}
</style></head><body>
<header><div><div class="draft">DRAFT</div><strong>{e(firm.get('name', ''))}</strong><br>{'<br>'.join(e(x) for x in party_lines(firm))}</div>
<div class="meta"><div>Proposed number: {e(d['proposed_number'] or 'to be assigned')}</div><div>Invoice date: {e(d['invoice_date'])}</div>
<div>Due date: {e(d['due_date'])}</div><div>Period: {e(', '.join(d['months']))}</div>{po}</div></header>
<p>DRAFT: not issued. The proposed number is assigned by the owner when the invoice is issued.</p>
<div class="bill"><strong>Bill to</strong><br>{'<br>'.join(e(x) for x in party_lines(bill, True))}</div>
<table><thead><tr><th>Description</th><th class=n>Quantity</th><th class=n>Unit price</th><th class=n>Amount</th></tr></thead>
<tbody>
{rows}
</tbody>
<tfoot><tr><td colspan=3>Total ({e(d['currency'])})</td><td class=n>{e(c.fmt_money(d['total']))}</td></tr></tfoot></table>
{pay}
</body></html>
"""


def draft(a) -> tuple[list, dict]:
    """(refusals, result). Nothing is written when there are refusals."""
    root = c.billing_folder(a.folder)
    if not c.blank(a.contract):
        raise c.Bad("--contract is required")
    if not c.blank(a.lines):
        raise c.Bad("--lines is required")
    period, _ = c.resolve_period(a.period)
    pdir = c.period_dir(root, period, a.period_dir)
    billing = c.billing_or_bad(root)
    lines_file = Path(c.blank(a.lines)).expanduser()
    doc = c.load_json(lines_file, "lines file")
    contract = billing.contract(c.blank(a.contract))
    if contract is None:
        return [f"contract {a.contract} is not in BILLING.yaml"], {}
    pull = c.load_pull(pdir)
    if pull is None:
        return [f"no billing pull at {c.pull_path(pdir)}; run firm-billing-pull first"], {}
    refusals = []
    if pull.get("billing_sha256") != billing.sha256:
        refusals.append("the pull is stale: BILLING.yaml changed since it was pulled")
    lines, total, reasons = c.lines_reasons(contract, pull, doc, period, (pdir, root))
    refusals += reasons
    invoice_date = c.blank(doc.get("invoice_date")) if isinstance(doc, dict) else None
    try:
        issued = date.fromisoformat(invoice_date) if invoice_date else date.today()
    except ValueError:
        refusals.append(f"invoice_date {invoice_date!r} is not a yyyy-mm-dd date")
        issued = date.today()
    if refusals:
        return refusals, {}
    invoices = pdir / "invoices"
    stem = free_stem(invoices, contract["id"], period)
    d = {"contract": contract["id"], "client": contract["client"], "period": period,
         "months": [str(m) for m in doc["months"]], "bill_to": contract.get("bill_to"), "firm": billing.firm,
         "proposed_number": pull.get("next_number"), "invoice_date": issued.isoformat(),
         "due_date": (issued + timedelta(days=billing.terms_days)).isoformat(), "currency": billing.currency,
         "po_number": contract["po"]["number"], "lines": lines, "total": c.money(total),
         "notes": doc.get("notes"), "lines_file": str(lines_file), "drafted_at": c.now_utc(),
         "pull_sha256": c.sha256_bytes(c.pull_path(pdir).read_bytes()), "billing_sha256": billing.sha256}
    d["content_sha256"] = c.content_sha256(d)
    invoices.mkdir(parents=True, exist_ok=True)
    paths = {ext: invoices / f"{stem}.{ext}" for ext in ("json", "md", "html")}
    for ext, text in (("json", c.dump_json(d)), ("md", render_md(d)), ("html", render_html(d))):
        with paths[ext].open("x", encoding="utf-8") as fh:   # "x": never over an existing file
            fh.write(text)
    return [], {**{k: str(v) for k, v in paths.items()}, "total": d["total"], "content_sha256": d["content_sha256"],
                "line": f"DRAFTED: {paths['json']} total {c.plain_money(d['total'])}"}


def verify(a) -> tuple[list, dict]:
    root = c.billing_folder(a.folder)
    path = Path(c.blank(a.verify)).expanduser()
    if not path.is_file():
        raise c.Bad(f"no draft at {path}")
    data = c.load_json(path, "draft")
    own = str(data.get("period") or "") if isinstance(data, dict) else ""
    period = c.parse_month(c.blank(a.period) or own, "--period" if c.blank(a.period) else "the draft's period")
    pdir = c.period_dir(root, period, a.period_dir)
    reasons, d = c.verify_draft(root, c.billing_or_bad(root), pdir, period, path)
    total = (d or {}).get("total")
    return reasons, {"json": str(path), "total": total, "content_sha256": (d or {}).get("content_sha256"),
                     "line": f"OK: {path} total {c.plain_money(total) if total is not None else 'none'}"}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="firm-billing-draft", description="Write or verify one draft invoice; never overwrites.")
    p.add_argument("folder", nargs="?", default="", help="the firm's billing folder, with BILLING.yaml")
    p.add_argument("--period", default="", help="the month billed (yyyy-mm); blank: the month before today")
    p.add_argument("--contract", default="", help="the contract id in BILLING.yaml")
    p.add_argument("--lines", default="", help="the preparer's lines file")
    p.add_argument("--period-dir", default="", help="use this folder as the period folder")
    p.add_argument("--verify", default="", help="re-derive this existing draft JSON instead")
    p.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)
    try:
        refusals, out = verify(a) if c.blank(a.verify) else draft(a)
    except c.Bad as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    if a.format == "json":
        status = "REFUSED" if refusals else out["line"].split(":", 1)[0]
        print(json.dumps({"status": status, "refusals": refusals, **({} if refusals else out)}, indent=1, default=str))
    else:
        print("\n".join(f"REFUSED: {r}" for r in refusals) if refusals else out["line"])
    return 1 if refusals else 0


if __name__ == "__main__":
    sys.exit(main())
