#!/usr/bin/env python3
# /// script
# dependencies = ["pyyaml"]
# ///
"""Compute one period's billing pull: what each contract owes, from BILLING.yaml, the issued
invoices and the time records. Recomputed each time, never edited.

    python3 firm_billing_pull.py FOLDER [--period P] [--as-of D] [--run-dir R] [--dry-run-if V]
                                 [--period-dir DIR] [--format text|json]

FOLDER is the firm's billing folder. It reads BILLING.yaml, the issued invoice files in
settings.invoice_folders (each folder and two levels below it, names matched by
settings.invoice_pattern), the optional CSVs in settings.invoice_ledger (number, client, date) and,
when settings.time_records_dir is set, its hours.csv (date, client_key, hours). It writes
work/source/billing-pull.json and pulled.md in the period folder, plus STATUS.md and LOG.md stubs
when missing. The fields are in BILLING.md beside this skill.

The time records cover a month up to their latest date: a month the records stop short of is
warned about, and a month with no covered day has no hours. A time-record row whose date or
hours do not parse is skipped and reported, in time.warnings of the pull and on stderr, because
hours left unread would go unbilled.

First line: "FRESH: <n> contracts, <k> billable, <u> with unbilled months, ...; period folder <path>",
or "STALE: <reason>" when BILLING.yaml cannot be read (exit 0, nothing written). With
--dry-run-if true (1, yes, on) the period folder is <run-dir>/billing/{yyyy}/{yyyy-mm}/ and nothing
in the billing folder changes.

Exit 0 when it ran (FRESH or STALE); 2 on a bad argument or a missing folder.

Example:
    python3 firm_billing_pull.py ~/Billing --period 2026-09 --format json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import _common as c


def norm(text) -> str:
    return " ".join(str(text or "").split()).casefold()


# ---------------------------------------------------------------- issued invoices

def walk_files(folder: Path, depth: int = 2):
    """Files in the folder and in its sub-folders up to depth levels below it."""
    if not folder.is_dir():
        return
    try:
        entries = sorted(folder.iterdir())
    except OSError:
        return
    for entry in entries:
        if entry.is_file():
            yield entry
        elif entry.is_dir() and depth > 0:
            yield from walk_files(entry, depth - 1)


def invoice_ledgers(spec) -> list[dict]:
    """Issued invoices kept only as a record (a CSV with number, client, date, optional source)."""
    out = []
    for raw in [spec] if isinstance(spec, str) else list(spec or []):
        path = Path(str(raw)).expanduser()
        if not path.is_file():
            continue
        for row in c.read_csv(path):
            try:
                when = date.fromisoformat((row.get("date") or "").strip())
            except ValueError:
                continue
            number, client = (row.get("number") or "").strip(), (row.get("client") or "").strip()
            if number and client:
                out.append({"number": number, "client": client, "date": when.isoformat(),
                            "file": f"{path}#{row.get('source') or number}"})
    return out


def scan_invoices(billing: c.Billing) -> list[dict]:
    """Every issued invoice, oldest first. A file outranks a ledger row for the same invoice."""
    out, seen = [], set()
    for folder in billing.settings.get("invoice_folders") or []:
        for path in walk_files(Path(str(folder)).expanduser()):
            found = billing.pattern.search(path.name)
            if not found or path in seen:
                continue
            try:
                when = date.fromisoformat(found.group("date"))
            except ValueError:
                continue
            seen.add(path)
            out.append({"number": found.group("number"), "client": found.group("client").strip(),
                        "date": when.isoformat(), "file": str(path)})
    for row in invoice_ledgers(billing.settings.get("invoice_ledger")):
        if not any(i["number"] == row["number"] and i["client"].casefold() == row["client"].casefold() for i in out):
            out.append(row)
    out.sort(key=lambda i: (i["date"], int(i["number"]) if i["number"].isdigit() else 0, i["file"]))
    return out


def next_number(invoices) -> str | None:
    numbers = [i["number"] for i in invoices if str(i["number"]).isdigit()]
    if not numbers:
        return None
    return str(max(int(n) for n in numbers) + 1).zfill(max(len(n) for n in numbers))


# ---------------------------------------------------------------- time records

def time_records(folder, months) -> dict:
    """Hours per client key per month from <time_records_dir>/hours.csv, and each month's days
    covered (days from the first to the latest date in the file)."""
    out = {"present": False, "source": None, "months": {}, "hours": {}, "warnings": []}
    if not c.blank(folder):
        out["reason"] = "no time_records_dir in BILLING.yaml settings"
        return out
    path = Path(str(folder)).expanduser() / "hours.csv"
    out["source"] = str(path)
    rows = []
    if path.is_file():
        for line, r in enumerate(c.read_csv(path), start=2):
            # A row that cannot be read is skipped but never silently: unread hours are unbilled hours.
            raw_date, raw_hours = str(r.get("date") or "").strip(), str(r.get("hours") or "").strip()
            try:
                day = date.fromisoformat(raw_date)
            except ValueError:
                out["warnings"].append(f"{path.name} line {line}: the date {raw_date!r} is not yyyy-mm-dd; "
                                       f"row skipped ({r.get('client_key') or 'no client key'}, hours {raw_hours!r})")
                continue
            try:
                hours = c.dec(raw_hours, "hours")
                if not hours.is_finite():
                    raise ValueError
            except ValueError:
                out["warnings"].append(f"{path.name} line {line}: the hours {raw_hours!r} are not a number; "
                                       f"row skipped ({r.get('client_key') or 'no client key'}, {raw_date})")
                continue
            rows.append((day, norm(r.get("client_key")), hours))
    lo = min((d for d, _, _ in rows), default=None)
    hi = max((d for d, _, _ in rows), default=None)
    for month in months:
        first, last = c.first_day(month), c.last_day(month)
        days = last.day
        covered = 0 if lo is None else max(0, (min(hi, last) - max(lo, first)).days + 1)
        out["months"][month] = {"days_covered": covered, "days": days}
        if covered:
            out["present"] = True
            by: dict[str, Decimal] = {}
            for d, key, h in rows:
                if first <= d <= last:
                    by[key] = by.get(key, Decimal(0)) + h
            out["hours"][month] = by
        else:
            out["hours"][month] = None
    if not out["present"]:
        out["reason"] = f"{path} holds no day of {', '.join(months)}" if months else "no months asked"
    return out


def key_hours(time: dict, month: str, key) -> Decimal | None:
    """The client key's hours for the month to two places, or None when no day of it is covered."""
    by = time["hours"].get(month)
    if by is None or not c.blank(key):
        return None
    return c.cents(by.get(norm(key), Decimal(0)))


def uncontracted(billing: c.Billing, time: dict, period: str) -> list[dict]:
    """Client keys with time in the period that no contract names: work with nothing to bill it against."""
    named = {norm(k.get("time_records_client_key")) for k in billing.contracts}
    floor = c.dec(billing.settings.get("uncontracted_min_hours")
                  if billing.settings.get("uncontracted_min_hours") not in (None, "") else 1)
    out = []
    for key in sorted((time["hours"].get(period) or {})):
        if not key or key in named:
            continue
        hours = key_hours(time, period, key)
        if hours is not None and hours >= floor:
            slug = re.sub(r"[^a-z0-9]+", "-", key).strip("-") or "unnamed"
            out.append({"id": c.CLIENT_PREFIX + slug, "client_key": key, "hours": float(hours),
                        "why": f"{hours} hours in the time records in {period} and no contract in BILLING.yaml"})
    return out


# ---------------------------------------------------------------- per contract

def history(contract: dict, invoices: list, period: str):
    """(its issued invoices, last billed month, unbilled months)."""
    tag = str(contract["invoice_tag"]).strip().casefold()
    mine = [i for i in invoices if i["client"].casefold() == tag]
    lbm = None
    if mine:   # the invoice's month for advance and month-end billing, the month before for arrears
        month = mine[-1]["date"][:7]
        lbm = month if contract["timing"] in ("advance", "month-end") else c.add_months(month, -1)
    start = c.month_of(contract["start"])
    begin = max(c.add_months(lbm, 1), start) if lbm else start
    return mine, lbm, [m for m in c.months_between(begin, period) if c.active_in(contract, m)]


def billable(contract: dict, period: str, lbm) -> tuple[bool, str]:
    if not c.active_in(contract, period):
        end = contract["end"].isoformat() if contract["end"] else "open"
        return False, f"not active in {period} (start {contract['start'].isoformat()}, end {end})"
    if contract["cadence"] == "monthly":
        return True, f"monthly, active in {period}"
    if contract["cadence"] == "quarterly":
        if int(period[5:7]) % 3 == 0:
            return True, f"quarterly, {period} ends a quarter"
        return False, f"quarterly, {period} does not end a quarter"
    due = [r for r in contract["rates"] if r["kind"] == "milestone" and r["due"] <= period
           and (lbm is None or r["due"] > lbm)]
    if due:
        return True, "milestone due on or before the period: " + ", ".join(f"{r['id']} ({r['due']})" for r in due)
    return False, "no milestone due on or before the period that is not already billed"


def expected_lines(contract: dict, month: str, first_unbilled: str, lbm, hours) -> list[dict]:
    out = []
    key = c.blank(contract.get("time_records_client_key"))
    for rate in contract["rates"]:
        kind, rid = rate["kind"], rate["id"]
        line = {"rate_id": rid, "kind": kind, "description": f"{rate['description']}, {c.month_name(month)}"}
        if kind == "retainer":
            line.update(quantity=1, unit_price=c.money(rate["amount"]), amount=c.money(rate["amount"]),
                        basis=f"retainer {rid}, one month at {c.plain_money(rate['amount'])}", needs_evidence=False)
        elif kind == "hourly":
            if hours is None:
                why = "no time_records_client_key for this contract" if not key else "the time records have no day of this month"
                line.update(quantity=None, unit_price=c.money(rate["rate"]), amount=None,
                            basis=f"hourly {rid} at {c.plain_money(rate['rate'])}: {why}", needs_evidence=True)
            else:
                cap = rate.get("cap_hours")
                capped = cap is not None and hours > cap
                qty = cap.quantize(c.CENT) if capped else hours
                basis = (f"{hours} h from the time records ({key})" + (f", capped at {cap} h" if capped else "")
                         + f", at {c.plain_money(rate['rate'])} an hour")
                line.update(quantity=float(qty), unit_price=c.money(rate["rate"]), amount=c.money(qty * rate["rate"]),
                            basis=basis, needs_evidence=False)
        elif kind == "milestone":
            due = rate["due"]
            catch_up = month == first_unbilled and due < month and (lbm is None or due > lbm)
            if not (due == month or catch_up):
                continue
            line.update(quantity=None, unit_price=None, amount=None, needs_evidence=True,
                        basis=f"milestone {rid}, {c.plain_money(rate['amount'])} when met (due {due}); needs evidence it was met")
        else:
            line.update(quantity=None, unit_price=None, amount=None, needs_evidence=True,
                        basis=f"pass-through {rid} at cost plus {rate['markup_pct']}%; needs the receipts")
        out.append(line)
    return out


def contract_entry(contract: dict, period: str, invoices: list, time: dict, shared: dict) -> dict:
    mine, lbm, unbilled = history(contract, invoices, period)
    is_billable, why = billable(contract, period, lbm)
    key = c.blank(contract.get("time_records_client_key"))
    has_hourly = any(r["kind"] == "hourly" for r in contract["rates"])
    hours, expected, warnings = {}, {}, []
    for month in unbilled:
        h = key_hours(time, month, key) if key else None
        hours[month] = None if h is None else float(h)
        expected[month] = expected_lines(contract, month, unbilled[0], lbm, h)
        if has_hourly and key:
            covered, days = time["months"][month]["days_covered"], time["months"][month]["days"]
            if covered < days:
                warnings.append(f"the time records cover {covered} of {days} days of {month}")
        if contract["start"] > c.first_day(month):
            warnings.append(f"a partial month: the contract starts {contract['start'].isoformat()}, in {month}")
        if contract["end"] is not None and contract["end"] < c.last_day(month):
            warnings.append(f"a partial month: the contract ends {contract['end'].isoformat()}, in {month}")
    if has_hourly and not key:
        warnings.append("an hourly rate with no time_records_client_key")
    if key and len(shared.get(norm(key), [])) > 1:
        others = [o for o in shared[norm(key)] if o != contract["id"]]
        warnings.append(f"two contracts on one client key: {key} is also {', '.join(others)}'s")
    if contract["po"]["required"] and not contract["po"]["number"]:
        warnings.append("a PO is required and BILLING.yaml has none")
    if not contract["confirmed"]:
        warnings.append("unconfirmed terms: confirmed is false in BILLING.yaml")
    first = c.first_day(period).isoformat()
    return {"id": contract["id"], "client": contract["client"], "confirmed": contract["confirmed"],
            "cadence": contract["cadence"], "timing": contract["timing"],
            "po_required": contract["po"]["required"], "po_number": contract["po"]["number"],
            "billable": is_billable, "why": why, "last_invoice": mine[-1] if mine else None,
            "last_billed_month": lbm, "unbilled_months": unbilled,
            "invoices_since_period_start": [i for i in mine if i["date"] >= first],
            "expected": expected, "hours": hours, "warnings": warnings}


# ---------------------------------------------------------------- the pull

def resolve_dir(root: Path, period: str, run_dir, dry_run_if, given) -> tuple[Path, bool]:
    if not c.truthy(dry_run_if):
        return c.period_dir(root, period, given), False
    if not c.blank(run_dir):
        raise c.Bad("--dry-run-if is true but no --run-dir was given")
    target = Path(c.blank(run_dir)).expanduser() / "billing" / period[:4] / period
    if c.blank(given) and Path(c.blank(given)).expanduser().resolve() != target.resolve():
        raise c.Bad(f"on a dry run the period folder is {target}; --period-dir names another")
    return target, True


def build(a) -> dict:
    root = c.billing_folder(a.folder)
    period, today = c.resolve_period(a.period, a.as_of)
    pdir, dry = resolve_dir(root, period, a.run_dir, a.dry_run_if, a.period_dir)
    try:
        billing = c.load_billing(root)
    except c.Stale as exc:
        return {"status": "STALE", "reason": str(exc), "line": f"STALE: {exc}"}
    invoices = scan_invoices(billing)
    shared: dict[str, list] = {}
    for k in billing.contracts:
        if c.blank(k.get("time_records_client_key")):
            shared.setdefault(norm(k["time_records_client_key"]), []).append(k["id"])
    months = sorted({m for k in billing.contracts for m in history(k, invoices, period)[2]} | {period})
    time = time_records(billing.settings.get("time_records_dir"), months)
    entries = [contract_entry(k, period, invoices, time, shared) for k in billing.contracts]
    pull = {
        "period": period, "first": c.first_day(period).isoformat(), "last": c.last_day(period).isoformat(),
        "as_of": today.isoformat(), "computed_at": c.now_utc(), "billing_yaml": str(billing.path),
        "billing_sha256": billing.sha256, "period_dir": str(pdir), "dry_run": dry, "currency": billing.currency,
        "time": {"present": time["present"], "source": time["source"], "months": time["months"],
                 "warnings": time["warnings"],
                 **({"reason": time["reason"]} if time.get("reason") else {})},
        "invoices_found": invoices, "next_number": next_number(invoices),
        "contracts": entries, "uncontracted": uncontracted(billing, time, period),
    }
    write(pdir, pull)
    n_billable = sum(1 for e in entries if e["billable"])
    n_unbilled = sum(1 for e in entries if e["unbilled_months"])
    return {"status": "FRESH", "pull": pull, "written": str(c.pull_path(pdir)),
            "line": (f"FRESH: {len(entries)} contracts, {n_billable} billable, {n_unbilled} with unbilled months, "
                     f"{len(pull['uncontracted'])} client key(s) with time and no contract; period folder {pdir}")}


def pulled_md(pull: dict) -> str:
    time = pull["time"]
    out = [f"# Billing pull {pull['period']}", "",
           f"Computed {pull['computed_at']} as of {pull['as_of']} from {pull['billing_yaml']}"
           + (" (dry run)" if pull["dry_run"] else "") + ".", "",
           f"Time records: {'present' if time['present'] else 'absent'}"
           + (f" ({time['reason']})" if time.get("reason") else "") + ".", ""]
    out += [f"- {m}: {v['days_covered']} of {v['days']} days" for m, v in sorted(time["months"].items())]
    out += [f"- Warning: {w}" for w in time.get("warnings") or []]
    out += ["", f"Issued invoices found: {len(pull['invoices_found'])}; proposed next number "
            f"{pull['next_number'] or 'none (no invoice found)'}.", ""]
    for e in pull["contracts"]:
        last = e["last_invoice"]
        out += [f"## {e['id']} ({e['client']})", "",
                f"- Billable: {'yes' if e['billable'] else 'no'} ({e['why']})",
                f"- Last invoice: {Path(last['file']).name if last else 'none found'}; "
                f"last billed month {e['last_billed_month'] or 'none'}",
                f"- Unbilled months: {', '.join(e['unbilled_months']) or 'none'}"]
        for month in e["unbilled_months"]:
            for line in e["expected"].get(month) or []:
                amount = "to be evidenced" if line["amount"] is None else c.fmt_money(line["amount"])
                out.append(f"  - {month} {line['rate_id']}: {amount} ({line['basis']})")
        out += [f"- Warning: {w}" for w in e["warnings"]] + [""]
    if pull["uncontracted"]:
        out += ["## Client time with no contract", ""]
        out += [f"- {u['id']} ({u['client_key']}): {u['why']}" for u in pull["uncontracted"]] + [""]
    return "\n".join(out)


def write(pdir: Path, pull: dict) -> None:
    source = c.pull_path(pdir).parent
    source.mkdir(parents=True, exist_ok=True)
    c.pull_path(pdir).write_text(c.dump_json(pull), encoding="utf-8")
    (source / c.PULLED_MD).write_text(pulled_md(pull), encoding="utf-8")
    if not (pdir / "STATUS.md").exists():
        (pdir / "STATUS.md").write_text(f"# Billing {pull['period']}\n\nWhere it stands: pulled, not yet worked.\n\n"
                                        "## Open items\n\n## Waiting on\n\n## Next action\n", encoding="utf-8")
    if not (pdir / "LOG.md").exists():
        (pdir / "LOG.md").write_text(f"# Billing {pull['period']} log\n", encoding="utf-8")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="firm-billing-pull", description="Compute the period's billing pull.")
    p.add_argument("folder", nargs="?", default="", help="the firm's billing folder, with BILLING.yaml")
    p.add_argument("--period", default="", help="the month billed (yyyy-mm); blank: the month before today")
    p.add_argument("--as-of", default="", help="judge as of this date (yyyy-mm-dd); blank: today")
    p.add_argument("--run-dir", default="", help="the Run folder, for a dry run")
    p.add_argument("--dry-run-if", default="", help="true, 1, yes or on: write under --run-dir, never the billing folder")
    p.add_argument("--period-dir", default="", help="use this folder as the period folder")
    p.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)
    try:
        out = build(a)
    except c.Bad as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    for warning in (out.get("pull") or {}).get("time", {}).get("warnings") or []:
        print(f"WARNING {warning}", file=sys.stderr)
    if a.format == "json":
        print(json.dumps(out, indent=1, default=str))
        return 0
    lines = [out["line"]]
    if out["status"] == "FRESH":
        for e in out["pull"]["contracts"]:
            lines.append(f"  {e['id']}: {'billable' if e['billable'] else 'not billable'}; unbilled "
                         f"{', '.join(e['unbilled_months']) or 'none'}"
                         + (f"; {len(e['warnings'])} warning(s)" if e["warnings"] else ""))
        lines += [f"  {u['id']}: no contract; {u['why']}" for u in out["pull"]["uncontracted"]]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
