#!/usr/bin/env python3
# /// script
# dependencies = ["pyyaml"]
# ///
"""Record one contract's state for the period: the one writer of BILLING-EVIDENCE-{yyyy-mm}.csv.

    python3 firm_billing_record.py FOLDER --period P --contract ID [--period-dir DIR] --state S
        [--draft JSON] [--amount A] [--rate-basis IDS] [--months M,...] [--evidence E]
        [--question Q] [--note N] [--review PASS|FAIL --review-file F] [--by WHO] [--format text|json]

The file sits in the period folder, one row per contract id (or per "client:<slug>" from the
pull's uncontracted list, which takes only not-billable, question or open). Rows are upserted by
id and never deleted. What each state needs (BILLING.md beside this skill):

- drafted: --draft (on the row or given now); its content_sha256 and total are read from the
  file, and --amount, if given, must equal the total. On an unconfirmed contract, also --question.
- already-billed: --evidence naming the invoice file (a path, or an issued invoice the pull found).
- not-billable: --note.   question: --question and --note.   open: nothing.

--review PASS|FAIL --review-file F records the review of a drafted row with review_sha256, the
draft's content_sha256 now. A changed draft, hash, amount or state clears an earlier review.

Prints "RECORDED: <contract> <state> (created|updated)". Exit 0 recorded; 1 refused (nothing
written; "REFUSED: <reasons>" on stdout); 2 a bad argument.

Example:
    python3 firm_billing_record.py ~/Billing --period 2026-09 --contract acme-ops --state drafted \\
        --draft "invoices/acme-ops 2026-09 invoice DRAFT.json"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _common as c


def split(value) -> list[str]:
    return [p.strip() for p in (value or "").split(",") if p.strip()]


def relative(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path)


def record(a) -> dict:
    root = c.billing_folder(a.folder)
    period, _ = c.resolve_period(a.period)
    pdir = c.period_dir(root, period, a.period_dir)
    billing = c.billing_or_bad(root)
    cid = c.blank(a.contract)
    if not cid:
        raise c.Bad("--contract is required")
    state = (c.blank(a.state) or "").lower()
    if state not in c.STATES:
        raise c.Bad(f"--state must be one of {', '.join(c.STATES)}" + (f", not {state!r}" if state else ""))
    contract = billing.contract(cid)
    if contract is None and cid.startswith(c.CLIENT_PREFIX):
        # Client time with no contract: only a reason or a question, never a draft.
        found = {u.get("id"): u for u in (c.load_pull(pdir) or {}).get("uncontracted") or []}
        if cid not in found:
            raise c.Bad(f"{cid} is not in the pull's client keys with no contract")
        if state not in ("not-billable", "question", "open"):
            raise c.Bad(f"{cid} has no contract: its state is not-billable or question, not {state}")
        contract = {"id": cid, "client": found[cid].get("client_key") or cid, "rates": [], "confirmed": True}
    if contract is None:
        raise c.Bad(f"contract {cid} is not in BILLING.yaml")
    review = (c.blank(a.review) or "").upper() or None
    if review and review not in ("PASS", "FAIL"):
        raise c.Bad(f"--review must be PASS or FAIL, not {review!r}")
    for m in split(a.months):
        c.parse_month(m, "--months")
    unknown = [r for r in split(a.rate_basis) if r not in c.rates_by_id(contract)]
    if unknown:
        raise c.Bad(f"--rate-basis names rates {cid} does not have: {', '.join(unknown)}")
    if c.blank(a.amount):
        try:
            c.dec(c.blank(a.amount), "--amount")
        except ValueError as exc:
            raise c.Bad(str(exc)) from None

    path = c.evidence_path(pdir, period)
    old = next((r for r in c.evidence_rows(path) if r["id"] == cid), {})
    values = {"client": contract["client"], "state": state, "updated_at": c.now_utc(),
              "by": c.blank(a.by) or "firm-billing-record"}
    for key, value in (("amount", a.amount), ("rate_basis", ",".join(split(a.rate_basis))),
                       ("months", ",".join(split(a.months))), ("evidence", a.evidence),
                       ("question", a.question), ("note", a.note)):
        if c.blank(value):
            values[key] = c.blank(value)
    merged = {**old, **values}
    problems, draft_doc = [], None

    if state == "drafted":
        name = c.blank(a.draft) or old.get("draft")
        found = c.resolve_file(name or "", pdir, root) if name else None
        if not name:
            problems.append("drafted needs --draft, the draft invoice's JSON")
        elif found is None:
            problems.append(f"--draft {name} is not a file")
        else:
            try:
                draft_doc = json.loads(found.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                draft_doc = None
            if not isinstance(draft_doc, dict) or not draft_doc.get("content_sha256"):
                problems.append(f"{found} is not a draft invoice written by firm-billing-draft")
                draft_doc = None
        if draft_doc is not None:
            if draft_doc.get("contract") != cid:
                problems.append(f"the draft is for contract {draft_doc.get('contract')}, not {cid}")
            total = c.plain_money(draft_doc.get("total") or 0)
            if c.blank(a.amount) and c.plain_money(c.blank(a.amount)) != total:
                problems.append(f"--amount {a.amount} is not the draft's total {total}")
            values.update(draft=relative(found, pdir), content_sha256=str(draft_doc["content_sha256"]), amount=total)
            values.setdefault("rate_basis", ",".join(dict.fromkeys(str(l.get("rate_id")) for l in draft_doc.get("lines") or [])))
            values.setdefault("months", ",".join(str(m) for m in draft_doc.get("months") or []))
            merged = {**old, **values}
        if not contract["confirmed"] and not merged.get("question"):
            problems.append(f"{cid}'s terms are unconfirmed: a drafted row needs --question (the terms to confirm)")
    elif state == "already-billed":
        name = c.blank(a.evidence) or old.get("evidence")
        issued = set()
        for inv in (c.load_pull(pdir) or {}).get("invoices_found") or []:
            issued |= {Path(inv["file"]).name, inv["file"]}
        if not name:
            problems.append("already-billed needs --evidence naming the invoice file")
        elif name not in issued and c.resolve_file(name, pdir, root) is None:
            problems.append(f"--evidence {name} is neither a file nor an issued invoice the pull found")
    elif state == "not-billable" and not merged.get("note"):
        problems.append("not-billable needs --note with the reason")
    elif state == "question":
        if not merged.get("question"):
            problems.append("question needs --question (the comms-confirm id or the question)")
        if not merged.get("note"):
            problems.append("question needs --note")

    if review:
        review_path = c.resolve_file(c.blank(a.review_file) or "", pdir, root)
        if state != "drafted":
            problems.append("a review is recorded on a drafted row only")
        if not c.blank(a.review_file):
            problems.append("--review needs --review-file")
        elif review_path is None:
            problems.append(f"--review-file {a.review_file} is not a file")
        if draft_doc is not None:
            values.update(review=review, review_file=relative(review_path, pdir) if review_path else "",
                          review_sha256=str(draft_doc["content_sha256"]))
    elif c.blank(a.review_file):
        problems.append("--review-file needs --review PASS or FAIL")
    if problems:
        raise c.Refused("; ".join(problems))
    done = c.evidence_upsert(path, cid, values)
    return {"id": cid, "state": state, "action": done["action"], "review_cleared": done["review_cleared"],
            "row": done["row"], "evidence_file": str(path),
            "line": f"RECORDED: {cid} {state} ({done['action']})"
                    + ("; the earlier review was cleared (the draft changed)" if done["review_cleared"] else "")}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="firm-billing-record", description="Record one contract's state for the period.")
    p.add_argument("folder", nargs="?", default="", help="the firm's billing folder, with BILLING.yaml")
    p.add_argument("--period", default="", help="the month billed (yyyy-mm); blank: the month before today")
    p.add_argument("--contract", default="", help="the contract id in BILLING.yaml")
    p.add_argument("--period-dir", default="", help="use this folder as the period folder")
    p.add_argument("--state", default="", help="drafted, already-billed, not-billable, question or open")
    p.add_argument("--draft", default="", help="the draft invoice's JSON (drafted)")
    p.add_argument("--amount", default="", help="the amount; for a drafted row it must be the draft's total")
    p.add_argument("--rate-basis", default="", help="rate ids, comma separated")
    p.add_argument("--months", default="", help="months billed, comma separated yyyy-mm")
    p.add_argument("--evidence", default="", help="the issued invoice file (already-billed) or other evidence")
    p.add_argument("--question", default="", help="the comms-confirm id or the question for the owner")
    p.add_argument("--note", default="", help="the reason or a note")
    p.add_argument("--review", default="", help="PASS or FAIL")
    p.add_argument("--review-file", default="", help="the reviewer's note")
    p.add_argument("--by", default="", help="who records it")
    p.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)
    try:
        out = record(a)
    except c.Refused as exc:
        print(f"REFUSED: {exc}")
        return 1
    except (c.Bad, ValueError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    print(json.dumps(out, indent=1, default=str) if a.format == "json" else out["line"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
