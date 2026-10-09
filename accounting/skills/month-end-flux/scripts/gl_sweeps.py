#!/usr/bin/env python3
"""Ten detection sweeps over one month's general ledger. Each sweep flags; a person confirms.

    python3 gl_sweeps.py --period 2026-03 --lines gl-lines.json --headers je-headers.json \
        [--accounts accounts.json] [--ap-lines ap-bills.json ...] [--config sweeps.json] [--format json]

Inputs are pulls in the standard ledger shape or as Sage Intacct lands them: the GL lines
(the period and the months before it, for the baselines), the journal-entry headers, the
chart of accounts (optional; rows with id, accountType and normalBalance), and the AP bill
lines for the reclass check. --config is a JSON object of thresholds; any key left out
keeps the default in DEFAULTS below. No company's accounts, journals or vendors are built in.

The sweeps:
- run_rate: an expense account well below its trailing median (a missing accrual looks
  like a saving). Entries named in run_rate_exclude_jes are left out of both sides.
- negative_expense: an expense account netting a credit for the month.
- entity_balance: debits do not equal credits within one location.
- stuck_drafts: an entry header in any state but posted.
- late_postings: a line dated before the period but created after that month closed.
- reclass_date: a reclass naming an invoice whose AP bill posted in another month.
- reversal_integrity: a reversal not on the expected day or with no matching parent, or
  an entry stuck pending reversal.
- duplicates: the same account, amount, side and vendor on two entries a few days apart.
- swings: a P&L account far from its trailing median, measured by median absolute deviation.
- journal_shape: a journal that went quiet this month, or appeared for the first time.

Every finding has a stable key so a register can be updated rather than duplicated. Prints
the findings, or JSON. Exit 1 when any high-severity finding exists, 2 on unusable input.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date

from _common import (DOC, HEADER, amount_key, debit, field, load_pull, mad_z, median_of, money,
                     month_of, normalize_description, side, signed, trailing_periods)

DEFAULTS = {
    "expense_prefixes": ["5", "6", "7"],
    "run_rate_floor": 0.60,
    "run_rate_months": 5,
    "run_rate_min_amount": 1000.0,
    "run_rate_exclude_jes": [],
    "negative_expense_floor": 500.0,
    "prior_period_floor": 1000.0,
    "prior_period_created_after": "",
    "reclass_vendors": [],
    "reversal_post_day": 1,
    "pending_states": ["reversalpending"],
    "duplicate_floor": 1000.0,
    "duplicate_journals": [],
    "duplicate_window_days": 7,
    "swing_z": 3.0,
    "swing_floor": 10000.0,
    "baseline_months": 6,
    "journal_shape_min_months": 5,
}


def finding(check, key, severity, description, amount=None, evidence=None):
    return {"check": check, "key": key, "severity": severity, "description": description,
            "amount": amount, "evidence": evidence or [], "owner_hint": ""}


def names_of(lines):
    return {field(ln, "account"): field(ln, "account_name") for ln in lines}


def monthly_net(lines):
    """{account: {period: net}}."""
    out = {}
    for ln in lines:
        account, month = field(ln, "account"), month_of(field(ln, "date"))
        if account and month:
            out.setdefault(account, {})
            out[account][month] = round(out[account].get(month, 0.0) + signed(ln), 2)
    return out


def excluded_keys(wanted, headers):
    """An entry named by its key or its number excludes both, since lines carry the key."""
    wanted = {str(v).strip() for v in wanted} - {""}
    keys = set(wanted)
    for h in headers if wanted else ():
        identity = {field(h, "je_id", HEADER), field(h, "je_number", HEADER)}
        if identity & wanted:
            keys |= {v for v in identity if v}
    return keys


def sweep_run_rate(lines, headers, period, cfg):
    excluded = excluded_keys(cfg["run_rate_exclude_jes"], headers)
    kept = [ln for ln in lines if field(ln, "je_id") not in excluded]
    prefixes = tuple(str(p) for p in cfg["expense_prefixes"])
    names, baseline = names_of(kept), trailing_periods(period, int(cfg["run_rate_months"]))
    out = []
    for account, by_period in sorted(monthly_net(kept).items()):
        if not account.startswith(prefixes):
            continue
        history = [v for v in (by_period.get(m, 0.0) for m in baseline) if v]
        med, current = median_of(history), by_period.get(period, 0.0)
        if med <= 0:
            continue
        shortfall = round(med - current, 2)
        if current < float(cfg["run_rate_floor"]) * med and shortfall >= float(cfg["run_rate_min_amount"]):
            out.append(finding(
                "run_rate", f"run_rate:{account}:{period}", "medium",
                f"{account} {names.get(account, '')} is ${current:,.0f} in {period} vs a trailing "
                f"{len(history)}-month median of ${med:,.0f} ({current / med:.0%}): ${shortfall:,.0f} short",
                shortfall))
    return sorted(out, key=lambda f: -(f["amount"] or 0))


def sweep_negative_expense(period_lines, names, period, cfg):
    prefixes = tuple(str(p) for p in cfg["expense_prefixes"])
    net = defaultdict(float)
    for ln in period_lines:
        if field(ln, "account").startswith(prefixes):
            net[field(ln, "account")] += signed(ln)
    return [finding("negative_expense", f"negative_expense:{a}:{period}", "medium",
                    f"{a} {names.get(a, '')} nets credit ${-v:,.0f} in {period}: "
                    "reversal without replacement, refund, or miscoding", round(v, 2))
            for a, v in sorted(net.items()) if v < -float(cfg["negative_expense_floor"])]


def sweep_entity_balance(period_lines, period):
    balance = defaultdict(float)
    for ln in period_lines:
        balance[field(ln, "location") or "?"] += signed(ln)
    return [finding("entity_balance", f"entity_balance:{loc}:{period}", "high",
                    f"Entity/location {loc} does not balance in {period}: debits minus credits ${d:,.2f}",
                    round(d, 2))
            for loc, d in sorted(balance.items()) if abs(d) > 0.005]


def sweep_stuck_drafts(headers):
    out = []
    for h in headers:
        state = field(h, "state", HEADER).lower()
        if state and state != "posted":
            key = field(h, "je_id", HEADER) or field(h, "je_number", HEADER)
            out.append(finding("stuck_drafts", f"stuck_drafts:JE{key}", "medium",
                               f"JE{key} {field(h, 'journal', HEADER)} dated {field(h, 'date', HEADER)} is {state}, "
                               f"not posted: {field(h, 'description', HEADER)[:80]}", evidence=[f"JE{key}"]))
    return out


def sweep_late_postings(lines, period, cfg):
    start = f"{period}-01"
    # Lines dated before the period and created once the period itself is over (on or after the
    # first of the next month, or the configured date) changed a month already closed.
    created_after = str(cfg["prior_period_created_after"] or "") or f"{_next(period)}-01"
    entries = {}
    for ln in lines:
        created, day = field(ln, "created_at"), field(ln, "date")
        if day and day < start and created[:10] >= created_after:
            e = entries.setdefault(field(ln, "je_id"), {"date": day, "created": created[:10], "debits": 0.0,
                                                         "journal": field(ln, "journal"), "desc": field(ln, "memo")})
            e["debits"] += debit(ln)
    out = []
    for key, e in sorted(entries.items(), key=lambda kv: -kv[1]["debits"]):
        if e["debits"] >= float(cfg["prior_period_floor"]):
            out.append(finding("late_postings", f"late_postings:JE{key}", "medium" if e["debits"] >= 10000 else "low",
                               f"JE{key} {e['journal']} dated {e['date']} was created {e['created']}, after that "
                               f"month closed: ${e['debits']:,.0f} debits, {e['desc'][:60]}",
                               round(e["debits"], 2), [f"JE{key}"]))
    return out


def _next(period):
    year, month = (int(p) for p in period.split("-"))
    return f"{year + month // 12:04d}-{month % 12 + 1:02d}"


def sweep_reclass_date(headers, ap_rows, period, cfg):
    vendors = [str(v).upper() for v in cfg["reclass_vendors"]]
    if not vendors:
        return []
    bills = defaultdict(list)
    for row in ap_rows:
        bills[field(row, "counterparty", DOC).upper()].append(row)
    out = []
    for h in headers:
        desc = field(h, "description", HEADER).upper()
        if month_of(field(h, "date", HEADER)) != period or "RECLASS" not in desc:
            continue
        vendor = next((v for v in vendors if v in desc), None)
        if not vendor:
            continue
        for ref in re.findall(r"\d{3,}", desc):
            hits = [r for name, rows in bills.items() if vendor in name for r in rows
                    if ref in field(r, "memo", DOC) or ref in field(r, "doc_id", DOC)]
            months = sorted({month_of(field(r, "posting_date", DOC)) for r in hits})
            if hits and months != [period]:
                key = field(h, "je_id", HEADER)
                out.append(finding(
                    "reclass_date", f"reclass_date:JE{key}", "medium",
                    f"JE{key} '{field(h, 'description', HEADER)[:50]}' dated {field(h, 'date', HEADER)} reclasses "
                    f"invoice {ref} whose bill posted in {', '.join(months)}: reclass date must equal bill date",
                    evidence=[f"JE{key}"] + [f"bill {field(r, 'doc_id', DOC)} {field(r, 'posting_date', DOC)}"
                                             for r in hits[:3]]))
                break
    return out


def sweep_reversal_integrity(headers, period, cfg):
    post_day = int(cfg["reversal_post_day"])
    pending = tuple(str(s).lower() for s in cfg["pending_states"])
    parents = {(field(h, "date", HEADER), normalize_description(field(h, "description", HEADER))): h for h in headers}
    out = []
    for child in headers:
        reversed_from, day = field(child, "reversed_from", HEADER), field(child, "date", HEADER)
        if not reversed_from or month_of(day) != period:
            continue
        notes = []
        if (reversed_from, normalize_description(field(child, "description", HEADER))) not in parents:
            notes.append("no parent header matches reversedFromDate + description")
        day_no = int(day[8:10]) if re.match(r"^\d{4}-\d{2}-\d{2}", day) else 0
        if day_no != post_day:
            notes.append(f"posted on day {day_no}, expected {post_day}")
        if notes:
            key = field(child, "je_id", HEADER)
            out.append(finding("reversal_integrity", f"reversal_integrity:JE{key}", "medium",
                               f"JE{key} reverses {reversed_from}: " + "; ".join(notes), evidence=[f"JE{key}"]))
    for h in headers:
        if field(h, "state", HEADER).lower() in pending:
            key = field(h, "je_id", HEADER)
            out.append(finding("reversal_integrity", f"reversal_integrity:pending:JE{key}", "high",
                               f"JE{key} dated {field(h, 'date', HEADER)} is stuck in {field(h, 'state', HEADER)}: "
                               "the reversal never completed", evidence=[f"JE{key}"]))
    return out


def sweep_duplicates(period_lines, names, cfg):
    journals = {str(j) for j in cfg["duplicate_journals"]}
    groups = defaultdict(list)
    for ln in period_lines:
        if journals and field(ln, "journal") not in journals:
            continue
        if abs(signed(ln)) < float(cfg["duplicate_floor"]):
            continue
        groups[(field(ln, "account"), side(ln), amount_key(ln), field(ln, "vendor"))].append(ln)
    out = []
    for (account, side_, amount, vendor), group in sorted(groups.items()):
        entries = sorted({field(ln, "je_id") for ln in group})
        if len(entries) < 2:
            continue
        dates = sorted(field(ln, "date") for ln in group)
        try:
            span = (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days
        except ValueError:
            continue
        if span <= int(cfg["duplicate_window_days"]):
            out.append(finding(
                "duplicates", f"duplicates:{account}:{amount}:{','.join(entries)}", "medium",
                f"{account} {names.get(account, '')} {side_} ${money(amount):,.0f} vendor {vendor or '-'} appears "
                f"on JE {', '.join(entries)} within {span} day(s) ({', '.join(dates)})",
                money(amount), [f"JE{e}" for e in entries]))
    return out


def sweep_swings(lines, accounts, names, period, cfg):
    baseline = trailing_periods(period, int(cfg["baseline_months"]))
    by_account = defaultdict(lambda: defaultdict(float))
    for ln in lines:
        account = field(ln, "account")
        info = accounts.get(account, {})
        if accounts and info.get("accountType") != "incomeStatement":
            continue
        month = month_of(field(ln, "date"))
        if month:
            # Natural sign: revenue and expense both positive. An account not in the chart is debit-normal.
            sign = 1 if str(info.get("normalBalance", "debit")) == "debit" else -1
            by_account[account][month] += sign * signed(ln)
    out = []
    for account in sorted(by_account):
        history = [round(by_account[account].get(m, 0.0), 2) for m in baseline]
        current = round(by_account[account].get(period, 0.0), 2)
        z, med = mad_z(current, history)
        delta = round(current - med, 2)
        if abs(z) >= float(cfg["swing_z"]) and abs(delta) >= float(cfg["swing_floor"]):
            out.append(finding("swings", f"swings:{account}:{period}", "medium",
                               f"{account} {names.get(account, '')} is ${current:,.0f} in {period} vs a trailing "
                               f"median of ${med:,.0f} (delta ${delta:,.0f}, z={z:.1f})", delta))
    return out


def sweep_journal_shape(lines, period, cfg):
    baseline = trailing_periods(period, int(cfg["baseline_months"]))
    by_journal = defaultdict(lambda: defaultdict(set))
    for ln in lines:
        journal, month = field(ln, "journal"), month_of(field(ln, "date"))
        if journal and month:
            by_journal[journal][month].add(field(ln, "je_id"))
    out = []
    for journal in sorted(by_journal):
        active = [m for m in baseline if by_journal[journal].get(m)]
        current = len(by_journal[journal].get(period, set()))
        if len(active) >= int(cfg["journal_shape_min_months"]) and current == 0:
            typical = median_of([float(len(by_journal[journal][m])) for m in active])
            out.append(finding("journal_shape", f"journal_shape:{journal}:{period}", "high",
                               f"Journal {journal} carried entries in {len(active)} of the last {len(baseline)} "
                               f"months (typically {typical:,.0f} per month) and none in {period}"))
        elif not active and current:
            out.append(finding("journal_shape", f"journal_shape:new:{journal}:{period}", "low",
                               f"Journal {journal} has its first entries in {period} ({current} JE(s)) "
                               f"after {len(baseline)} quiet months"))
    return out


def run_sweeps(lines, headers, accounts, ap_rows, period, config=None):
    cfg = {**DEFAULTS, **(config or {})}
    period_lines = [ln for ln in lines if month_of(field(ln, "date")) == period]
    names = names_of(lines)
    findings = (sweep_run_rate(lines, headers, period, cfg)
                + sweep_negative_expense(period_lines, names, period, cfg)
                + sweep_entity_balance(period_lines, period)
                + sweep_stuck_drafts(headers)
                + sweep_late_postings(lines, period, cfg)
                + sweep_reclass_date(headers, ap_rows, period, cfg)
                + sweep_reversal_integrity(headers, period, cfg)
                + sweep_duplicates(period_lines, names, cfg)
                + sweep_swings(lines, accounts, names, period, cfg)
                + sweep_journal_shape(lines, period, cfg))
    counts = defaultdict(int)
    for f in findings:
        counts[f["check"]] += 1
    high = sum(1 for f in findings if f["severity"] == "high")
    return {"period": period, "findings": findings, "counts": dict(counts), "high": high, "passed": high == 0,
            "summary": f"{period}: {len(findings)} finding(s) " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))}


def main(argv=None):
    p = argparse.ArgumentParser(description="Run the ten GL sweeps for one period. Exit 1 on any high-severity finding.")
    p.add_argument("--period", required=True, help="accounting period, YYYY-MM")
    p.add_argument("--lines", required=True, help="GL-line pull covering the period and its baseline months")
    p.add_argument("--headers", required=True, help="journal-entry header pull")
    p.add_argument("--accounts", default="", help="chart of accounts; without it the swings sweep screens every account")
    p.add_argument("--ap-lines", action="append", default=[], help="AP bill-line pull for the reclass sweep; repeatable")
    p.add_argument("--config", default="", help="JSON object of thresholds, prefixes, journals and vendor tokens")
    p.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)
    try:
        config = json.loads(open(a.config, encoding="utf-8").read()) if a.config else {}
        if not isinstance(config, dict):
            raise ValueError(f"{a.config}: config must be a JSON object")
        accounts = {str(r["id"]): r for r in load_pull(a.accounts)} if a.accounts else {}
        ap_rows = [r for path in a.ap_lines if path for r in load_pull(path)]
        result = run_sweeps(load_pull(a.lines), load_pull(a.headers), accounts, ap_rows, a.period, config)
    except (OSError, ValueError, KeyError) as exc:
        print(f"gl-sweeps: {exc}", file=sys.stderr)
        return 2
    if a.format == "json":
        print(json.dumps(result, indent=1))
    else:
        print(result["summary"])
        for f in result["findings"]:
            print(f"  {f['severity'].upper():7} {f['check']:20} {f['description']}")
        print("PASS" if result["passed"] else f"FAIL: {result['high']} high-severity finding(s)")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
