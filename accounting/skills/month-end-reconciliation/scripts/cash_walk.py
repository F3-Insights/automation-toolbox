#!/usr/bin/env python3
"""Classify a month's cash movements by the account on the other side of each entry.

A bank memo rarely says what a payment was; the other side of the journal entry does. For
each journal entry that moved cash in the period, the offset is its largest non-cash line.
An offset whose account starts with a --financing prefix is financing, one with an
--investing prefix is investing, an offset that is itself cash is a transfer, and anything
else is operating. Which prefixes mean what belongs to the company's chart of accounts, so
they are options.

Inputs: --lines, a GL-line pull for the period (standard or Sage Intacct shape); the cash
accounts by --cash-prefix and/or exact --cash-account; the offset prefixes; --floor for
what counts as material; --opening balance to compute the closing figure.

Prints a summary with totals by classification and every movement at or above --floor, or
the whole result as JSON with --format json. Exit 0 always (it reports, it does not gate);
2 when the input is unusable.

    python3 cash_walk.py --period 2026-03 --lines gl-lines.json --cash-prefix 10 \
        --financing 25 --financing 3 --investing 15 --floor 25000 --opening 1250000
"""

import argparse
import json
import sys

from _common import field, load_rows, signed


def classify_offset(account, rules):
    """The first of financing, investing, operating whose prefixes match; else operating."""
    for name in ("financing", "investing", "operating"):
        prefixes = tuple(str(p) for p in rules.get(name) or ())
        if prefixes and account.startswith(prefixes):
            return name
    return "operating"


def walk(lines, period, cash_prefixes=(), cash_accounts=(), rules=None, floor=0.0, opening=0.0):
    cash_prefixes, cash_accounts, rules = tuple(cash_prefixes), set(cash_accounts), rules or {}
    if not cash_prefixes and not cash_accounts:
        raise ValueError("name the cash accounts: pass --cash-prefix and/or --cash-account")

    def in_walk(account):
        # Exact accounts, when given, decide what is explained; otherwise the prefixes do.
        return account in cash_accounts if cash_accounts else account.startswith(cash_prefixes)

    def cash_nature(account):
        # Any cash account, in the walk or not, makes the movement a transfer.
        return account in cash_accounts or (bool(cash_prefixes) and account.startswith(cash_prefixes))

    entries = {}
    for line in lines:
        if field(line, "date")[:7] == period:
            entries.setdefault(field(line, "je_id"), []).append(line)

    movements = []
    for je_id, group in sorted(entries.items()):
        cash = [ln for ln in group if in_walk(field(ln, "account"))]
        amount = round(sum(signed(ln) for ln in cash), 2)
        if not cash or not amount:
            continue
        others = [ln for ln in group if ln not in cash]
        offset = max(others, key=lambda ln: abs(signed(ln))) if others else {}
        account = field(offset, "account")
        kind = "transfer" if not offset or cash_nature(account) else classify_offset(account, rules)
        movements.append({
            "date": field(cash[0], "date"), "je_id": je_id, "amount": amount,
            "cash_account": field(cash[0], "account"), "offset_account": account,
            "offset_account_name": field(offset, "account_name"),
            "classification": kind, "cause": field(offset, "memo"),
        })

    movements.sort(key=lambda m: -abs(m["amount"]))
    totals = {}
    for m in movements:
        totals[m["classification"]] = round(totals.get(m["classification"], 0.0) + m["amount"], 2)
    net = round(sum(m["amount"] for m in movements), 2)
    material = [m for m in movements if abs(m["amount"]) >= floor] if floor else movements
    return {
        "period": period, "opening": opening, "closing": round(opening + net, 2), "net_change": net,
        "by_classification": totals, "movements": movements, "material": material, "floor": floor,
        "summary": (f"{period}: {len(movements)} cash movement(s), net ${net:,.0f}; "
                    f"{len(material)} at or above ${floor:,.0f}"),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Classify the period's cash movements by their offset account.")
    p.add_argument("--period", required=True, help="accounting period, YYYY-MM")
    p.add_argument("--lines", required=True, help="GL-line pull (JSON)")
    p.add_argument("--cash-prefix", dest="cash_prefixes", action="append", default=[],
                   help="account prefix that is cash; repeatable")
    p.add_argument("--cash-account", dest="cash_accounts", action="append", default=[],
                   help="exact cash account; repeatable; overrides the prefixes for what is in the walk")
    p.add_argument("--financing", action="append", default=[], help="offset prefix meaning financing; repeatable")
    p.add_argument("--investing", action="append", default=[], help="offset prefix meaning investing; repeatable")
    p.add_argument("--operating", action="append", default=[], help="offset prefix meaning operating; repeatable")
    p.add_argument("--floor", type=float, default=0.0, help="movements at or above this are listed as material")
    p.add_argument("--opening", type=float, default=0.0, help="opening cash balance")
    p.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)
    rules = {"financing": a.financing, "investing": a.investing, "operating": a.operating}
    try:
        result = walk(load_rows(a.lines), a.period, a.cash_prefixes, a.cash_accounts, rules, a.floor, a.opening)
    except (OSError, ValueError) as exc:
        print(f"cash-walk: {exc}", file=sys.stderr)
        return 2
    if a.format == "json":
        print(json.dumps(result, indent=1))
        return 0
    print(result["summary"])
    for kind, total in sorted(result["by_classification"].items()):
        print(f"  {kind:12} {total:>16,.2f}")
    for m in result["material"]:
        print(f"  {m['date']} JE{m['je_id']:<7} {m['amount']:>14,.2f} {m['classification']:10} "
              f"via {m['offset_account']} {m['offset_account_name'][:30]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
