#!/usr/bin/env python3
# /// script
# dependencies = ["pyyaml"]
# ///
"""Check that every standard month-end journal entry on the owner's ratified list is in the
period's ledger.

Two ways an entry is found, because neither alone is enough:
- by schedule key: an entry the ERP books from a recurring schedule carries its key
  (schedule_id; Intacct's scheduledOperationKey), and the list's match.scheduled_operation_key
  names it;
- by description: the list's match.description_contains is compared with each header's
  description after both are folded (upper case, month names to <M>, digit runs to <N>), so
  "To accrue rent FEB 2026" and "TO ACCRUE RENT MAR 2026" match. A reversal of last month's
  entry carries the same description and is never counted as this month's.

Each listed entry is present, missing or an explained exception: a conditional entry that is
absent, or a retired one, is an exception; only an unconditional absence is missing. An entry
found but not posted is present and flagged NOT POSTED.

Recurring descriptions in the manual journals (--manual-journal) seen in at least --min-months
of the --baseline-months before the period, and not on the list, come back as
unmatched_recurring so the list can grow.

The list (YAML or JSON) is {"entries": [...]} or a bare list, each entry like
    {"id": "1", "name": "Rent accrual", "journal": "GJ", "mechanism": "manual",
     "conditional": false, "match": {"description_contains": ["TO ACCRUE RENT"]}}
with optional retired, condition and typical_amount.

Inputs: --period, --headers (journal-entry headers) and --lines (GL lines), ledger pulls in the
standard or the Sage Intacct shape, and --standard-jes. Prints a summary, or with --format json:
entries, unmatched_recurring, missing, passed, summary.
Exit 0 when nothing is missing, 1 when an entry is missing, 2 on bad input.

Example:
    python3 recurring_je_scan.py --period 2026-08 --headers je-headers.json \\
        --lines gl-lines.json --standard-jes standard-je-list.yaml --manual-journal GJ
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from statistics import median

from _common import field, load_snapshot, month_of, shift_period, signed

MONTHS = ("JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER"
          "|JAN|FEB|MAR|APR|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC")


def hdr(row: dict, name: str) -> str:
    return field(row, name, "header")


def normalize_description(text) -> str:
    """Fold a description to its recurrence key: no reversal prefix, months as <M>, numbers as <N>."""
    body = re.sub(r"^REVERSED?\s*-\s*", "", str(text or ""), flags=re.I).upper()
    body = re.sub(rf"\b({MONTHS})\b", "<M>", body)
    body = re.sub(r"\d+([.,]\d+)*", "<N>", body)
    body = re.sub(r"[^A-Z0-9<>]+", " ", body)
    return re.sub(r"\s+", " ", body).strip()


def load_standard_jes(path: str) -> list:
    """The ratified list: JSON when the name ends .json, otherwise YAML (needs pyyaml)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"--standard-jes points at a file that does not exist: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        import yaml  # only a YAML list needs it
        data = yaml.safe_load(text)
    if isinstance(data, list):
        return [dict(e) for e in data]
    return [dict(e) for e in (dict(data or {}).get("entries") or [])]


def debit_totals(lines: list) -> dict:
    """Each entry's debit total, the amount the typical amounts are taken over."""
    totals = {}
    for line in lines:
        key = field(line, "je_id")
        totals[key] = round(totals.get(key, 0.0) + max(signed(line), 0.0), 2)
    return totals


def recurring_groups(headers, manual, baseline, period, totals) -> list:
    """Manual-journal headers grouped by journal and folded description."""
    buckets = {}
    for h in headers:
        journal = hdr(h, "journal")
        if (manual and journal not in manual) or hdr(h, "reversed_from"):
            continue
        pattern = normalize_description(hdr(h, "description"))
        if pattern:
            buckets.setdefault((journal, pattern), []).append(h)
    groups = []
    for (journal, pattern), members in sorted(buckets.items()):
        months = sorted({month_of(hdr(m, "date")) for m in members if month_of(hdr(m, "date"))})
        amounts = [a for a in (totals.get(hdr(m, "je_id"), 0.0) for m in members) if a]
        days = [int(hdr(m, "date")[8:10]) for m in members if re.match(r"^\d{4}-\d{2}-\d{2}", hdr(m, "date"))]
        groups.append({
            "key": f"{journal}:{pattern}", "journal": journal, "pattern": pattern,
            "example_description": hdr(members[0], "description"), "occurrences": len(members),
            "months_present": [m for m in months if m in baseline or m == period],
            "typical_amount": round(median(amounts), 2) if amounts else 0.0,
            "typical_day": max(days, default=0), "accounts": [],
            "present_in_period": any(month_of(hdr(m, "date")) == period for m in members),
        })
    return groups


def classify(spec: dict, period_headers: list, headers: list, period: str, totals: dict) -> dict:
    """One listed entry's status for the period."""
    match = spec.get("match") or {}
    key = match.get("scheduled_operation_key")
    hits, detection = [], "none"
    if key:
        hits = [h for h in headers if hdr(h, "schedule_id") == str(key)
                and month_of(hdr(h, "date")) == period and not hdr(h, "reversed_from")]
        detection = "scheduled_op" if hits else detection
    if not hits:
        tokens = [normalize_description(t) for t in (match.get("description_contains") or [])]
        for h in period_headers:
            if hdr(h, "reversed_from") or (spec.get("journal") and hdr(h, "journal") != spec["journal"]):
                continue
            pattern = normalize_description(hdr(h, "description"))
            if any(t and t in pattern for t in tokens):
                hits.append(h)
        detection = "description" if hits else detection

    mechanism = str(spec.get("mechanism") or ("scheduled" if key else "manual"))
    status = {
        "id": str(spec.get("id", "")), "name": str(spec.get("name", "")),
        "journal": str(spec.get("journal") or "GJ"),
        "mechanism": mechanism if mechanism in ("scheduled", "manual", "system") else "manual",
        "conditional": bool(spec.get("conditional")),
        "expected_amount": None if spec.get("typical_amount") in (None, "") else float(spec["typical_amount"]),
        "detection": detection, "je_ids": [hdr(h, "je_id") for h in hits],
        "amount": round(sum(totals.get(hdr(h, "je_id"), 0.0) for h in hits), 2) or None,
        "status": "missing", "note": f"no {period} entry matched",
    }
    if hits:
        status["status"], status["note"] = "present", f"{len(hits)} entry(ies) in {period}"
        unposted = sorted({hdr(h, "state").lower() for h in hits} - {"posted", ""})
        if unposted:
            status["note"] += f"; NOT POSTED ({', '.join(unposted)}), awaiting a person to post it"
    elif spec.get("retired"):
        status["status"], status["note"] = "exception", f"retired: {spec.get('condition') or 'no longer booked'}"
    elif spec.get("conditional"):
        status["status"] = "exception"
        status["note"] = f"conditional: {spec.get('condition') or 'book only when the condition holds'}"
    return status


def scan(headers: list, lines: list, specs: list, period: str, baseline_months: int = 6,
         manual_journals=(), min_months: int = 3) -> dict:
    manual = tuple(str(j) for j in manual_journals)
    baseline = [shift_period(period, -n) for n in range(baseline_months, 0, -1)]
    totals = debit_totals(lines)
    period_headers = [h for h in headers if month_of(hdr(h, "date")) == period]
    entries = [classify(s, period_headers, headers, period, totals) for s in specs]
    claimed = set()
    for s in specs:
        claimed.add(normalize_description(s.get("name", "")))
        claimed.update(normalize_description(t) for t in (s.get("match") or {}).get("description_contains") or [])
    unmatched = [g for g in recurring_groups(headers, manual, baseline, period, totals)
                 if len(g["months_present"]) >= min_months and not any(t and t in g["pattern"] for t in claimed)]
    missing = [e["id"] for e in entries if e["status"] == "missing"]
    return {
        "period": period, "baseline_months": baseline, "entries": entries,
        "unmatched_recurring": unmatched, "missing": missing, "passed": not missing,
        "summary": (f"{period}: {sum(1 for e in entries if e['status'] == 'present')}/{len(entries)} "
                    f"standard JEs present, {len(missing)} missing, "
                    f"{sum(1 for e in entries if e['status'] == 'exception')} explained"),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=__doc__.split("\n\n", 1)[1])
    parser.add_argument("--period", required=True, help="accounting period YYYY-MM")
    parser.add_argument("--headers", required=True, help="journal-entry headers pull")
    parser.add_argument("--lines", required=True, help="GL lines pull")
    parser.add_argument("--standard-jes", required=True, help="the ratified standard-entry list (YAML or JSON)")
    parser.add_argument("--baseline-months", type=int, default=6)
    parser.add_argument("--manual-journal", action="append", default=[], help="journal counted as manual; repeatable")
    parser.add_argument("--min-months", type=int, default=3,
                        help="months a description must recur in before it is reported as unlisted")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    try:
        result = scan(load_snapshot(args.headers), load_snapshot(args.lines), load_standard_jes(args.standard_jes),
                      args.period, args.baseline_months, args.manual_journal, args.min_months)
        result["list_path"] = args.standard_jes
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        print(f"recurring_je_scan: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(result, indent=1))
    else:
        print(result["summary"])
        for e in result["entries"]:
            print(f"  {e['status'].upper():9} {e['id']:4} {e['name'][:44]:45} {e['note']}")
        for g in result["unmatched_recurring"]:
            print(f"  UNLISTED  {g['journal']:4} {g['example_description'][:44]:45} "
                  f"{len(g['months_present'])} month(s), typical ${g['typical_amount']:,.0f}")
        print("PASS" if result["passed"] else f"FAIL: {len(result['missing'])} missing")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
