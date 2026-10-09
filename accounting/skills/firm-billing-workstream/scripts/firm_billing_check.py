#!/usr/bin/env python3
# /// script
# dependencies = ["pyyaml"]
# ///
"""Whether the period's billing is done, computed from the files, never claimed.

    python3 firm_billing_check.py FOLDER [--period P] [--period-dir DIR] [--as-of D] [--format text|json] [--precheck]

FOLDER is the firm's billing folder. The five tests (BILLING.md beside this skill, "Done"):

- pull: the pull exists and its billing_sha256 is BILLING.yaml's.
- contracts: every billable contract, and every contract with unbilled months, has a row in a
  final state; every uncontracted client key has a not-billable or question row.
- drafts: every drafted row's JSON exists, verifies, and its total is the row's amount; every
  earlier unbilled month is in the draft's months or named in the row's note.
- review: every drafted row is PASS and its review_sha256 is the draft's current content_sha256.
- reasons: every not-billable and question row has a note, every question row a question, and
  every drafted row on an unconfirmed contract a question.

--precheck prints one line for a scheduler: "NOTHING: a weekend ..." on a Saturday or Sunday,
"WORK: <reason>" while the period is not pulled or not done, "NOTHING: <reason>" when done.

Exit 0 whenever it ran, whatever it found; 2 on a bad argument or a missing folder.

Example:
    python3 firm_billing_check.py ~/Billing --period 2026-09 --format json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

import _common as c

TESTS = ("pull", "contracts", "drafts", "review", "reasons")


def check(folder, period=None, given_dir=None, as_of=None) -> dict:
    root = c.billing_folder(folder)
    per, today = c.resolve_period(period, as_of)
    pdir = c.period_dir(root, per, given_dir)
    gaps = {name: [] for name in TESTS}
    billing = None
    try:
        billing = c.load_billing(root)
    except c.Stale as exc:
        gaps["pull"].append(f"BILLING.yaml cannot be read: {exc}")
    pull = c.load_pull(pdir)
    if pull is None:
        gaps["pull"].append(f"no billing pull at {c.pull_path(pdir)}")
        gaps["contracts"].append("no pull, so the contracts owed are unknown")
    elif billing is not None and pull.get("billing_sha256") != billing.sha256:
        gaps["pull"].append("the pull is stale: BILLING.yaml changed since it was pulled")

    rows = {r["id"]: r for r in c.evidence_rows(c.evidence_path(pdir, per))}
    entries = {e.get("id"): e for e in (pull or {}).get("contracts") or []}
    for cid, e in entries.items():
        if not (e.get("billable") or e.get("unbilled_months")):
            continue
        row = rows.get(cid)
        if row is None:
            gaps["contracts"].append(f"{cid}: no row")
        elif row.get("state") not in c.FINAL_STATES:
            gaps["contracts"].append(f"{cid}: {row.get('state') or 'no state'}, not a final state")
    for u in (pull or {}).get("uncontracted") or []:
        row = rows.get(u.get("id"))
        if row is None:
            gaps["contracts"].append(f"{u.get('id')}: no row ({u.get('why')})")
        elif row.get("state") not in ("not-billable", "question"):
            gaps["contracts"].append(f"{u.get('id')}: {row.get('state') or 'no state'}, not a reason or a question")

    drafted = {cid: r for cid, r in rows.items() if r.get("state") == "drafted"}
    current = {}   # each draft's content hash recomputed now, so an edit after review shows
    for cid, row in drafted.items():
        current[cid] = None
        path = c.resolve_file(row.get("draft") or "", pdir, root)
        if path is None:
            gaps["drafts"].append(f"{cid}: the draft {row.get('draft') or '(none)'} does not exist")
            continue
        if billing is None:
            gaps["drafts"].append(f"{cid}: cannot verify without a readable BILLING.yaml")
            continue
        reasons, d = c.verify_draft(root, billing, pdir, per, path)
        gaps["drafts"] += [f"{cid}: {r}" for r in reasons]
        if d is None:
            continue
        current[cid] = c.content_sha256(d)
        try:
            same = c.cents(c.dec(row.get("amount"))) == c.cents(c.dec(d.get("total")))
        except ValueError:
            same = False
        if not same:
            gaps["drafts"].append(f"{cid}: the row's amount {row.get('amount') or '(none)'} is not the "
                                  f"draft's total {d.get('total')}")
        months = {str(m) for m in d.get("months") or []}
        for m in (entries.get(cid) or {}).get("unbilled_months") or []:
            if m < per and m not in months and m not in (row.get("note") or ""):
                gaps["drafts"].append(f"{cid}: the earlier unbilled month {m} is neither in the draft "
                                      "nor named in the row's note")
    for cid, row in drafted.items():
        if row.get("review") != "PASS":
            gaps["review"].append(f"{cid}: review {row.get('review') or 'not recorded'}, not PASS")
        elif not current[cid] or row.get("review_sha256") != current[cid]:
            gaps["review"].append(f"{cid}: the review is of another version of the draft")

    for cid, row in rows.items():
        state = row.get("state")
        if state in ("not-billable", "question") and not row.get("note"):
            gaps["reasons"].append(f"{cid}: {state} without a note")
        if state == "question" and not row.get("question"):
            gaps["reasons"].append(f"{cid}: question without a question")
        if state == "drafted" and not row.get("question"):
            contract = billing.contract(cid) if billing else None
            if contract is not None and not contract["confirmed"]:
                gaps["reasons"].append(f"{cid}: drafted on unconfirmed terms without a question")

    tests = {name: {"met": not gaps[name], "gaps": gaps[name]} for name in TESTS}
    met = sum(1 for t in tests.values() if t["met"])
    return {"folder": str(root), "period": per, "period_dir": str(pdir), "as_of": today.isoformat(),
            "pulled": pull is not None, "evidence": str(c.evidence_path(pdir, per)), "rows": len(rows),
            "tests": tests, "met": met, "of": len(TESTS), "done": met == len(TESTS)}


def precheck_line(result: dict) -> str:
    if date.fromisoformat(result["as_of"]).weekday() >= 5:
        return "NOTHING: a weekend; billing runs on business days"
    if not result["pulled"]:
        return f"WORK: {result['period']} is not pulled"
    if result["done"]:
        return f"NOTHING: {result['period']} billing is done ({result['of']} of {result['of']} tests met)"
    open_tests = [name for name, t in result["tests"].items() if not t["met"]]
    return f"WORK: {result['period']} has {len(open_tests)} of {result['of']} tests open ({', '.join(open_tests)})"


def render(result: dict) -> str:
    out = [f"{'DONE' if result['done'] else 'NOT DONE'}: firm billing {result['period']} "
           f"({result['met']} of {result['of']} tests met)"]
    for n, (name, test) in enumerate(result["tests"].items(), start=1):
        out.append(f"{n} {name}: {'MET' if test['met'] else 'NOT MET'}")
        out += [f"  - {gap}" for gap in test["gaps"]]
    return "\n".join(out)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="firm-billing-check", description="Whether the period's billing is done, test by test.")
    p.add_argument("folder", nargs="?", default="", help="the firm's billing folder, with BILLING.yaml")
    p.add_argument("--period", default="", help="the month billed (yyyy-mm); blank: the month before today")
    p.add_argument("--period-dir", default="", help="use this folder as the period folder")
    p.add_argument("--as-of", default="", help="judge as of this date (yyyy-mm-dd); blank: today")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--precheck", action="store_true", help="one line, WORK: or NOTHING:, for a scheduler")
    a = p.parse_args(argv)
    try:
        result = check(a.folder, a.period, a.period_dir, a.as_of)
    except (c.Bad, c.Refused) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    if a.precheck:
        print(precheck_line(result))
    else:
        print(json.dumps(result, indent=1) if a.format == "json" else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
