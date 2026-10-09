#!/usr/bin/env python3
"""Record one row of a month's close evidence file, the only way that file is written.

    python3 month_end_record.py FOLDER --period yyyy-mm --test T --item I --state S --by WHO
        [--evidence E] [--amount N] [--pull-date yyyy-mm-dd] [--review PASS|FAIL]
        [--review-file F] [--note TEXT] [--format text|json]

FOLDER is the Month-End folder; the row goes into {yyyy}/{yyyy-mm}/MONTH-END-EVIDENCE-{yyyy-mm}.csv
under the id "<test>:<item>". --test is entries, reconciliations, flux or questions. --state is
open, waiting, drafted, booked, reconciled, explained, answered or not-needed (drafted and
booked fit only entries, reconciled only reconciliations, explained only flux, answered only
questions). --evidence is a path relative to the month folder or a ledger reference such as
"JE 8420"; --amount is what the work tied to, such as a reconciliation's GL balance.

The row is created, or updated in place; a field left out keeps its recorded value, and ''
clears it. A change of state, evidence or amount without a new --review clears the recorded
review, so a PASS never outlives the work it passed. Every other row is left exactly as it was.

Prints what it did and any warning (a named evidence file that does not exist, a cleared
review), or JSON. Exit 0 when recorded, 2 on a bad argument or folder.

    python3 month_end_record.py ~/close/acme --period 2026-03 --test reconciliations --item 10100 \
        --state reconciled --evidence reconciliations/10100-cash.xlsx --amount 251,330.18 --by month-end-cash
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from _common import (STATE_TEST, STATES, TESTS, Bad, check_period, evidence_path, first_date, money,
                     month_folder, open_month, upsert_evidence)


def validate(test, item, state, amount, pull_date, review, by):
    """The checked and normalised values of one call."""
    if test not in TESTS:
        raise Bad(f"--test {test!r} is not one of {', '.join(TESTS)}")
    if state not in STATES:
        raise Bad(f"--state {state!r} is not one of {', '.join(STATES)}")
    if STATE_TEST.get(state, test) != test:
        raise Bad(f"--state {state} belongs to the {STATE_TEST[state]} test, not {test}")
    item = (item or "").strip()
    if not item or "\n" in item or "\r" in item:
        raise Bad("--item must be one line of text")
    if not (by or "").strip():
        raise Bad("--by must name who recorded the row")
    out = {"item": item, "by": by.strip()}
    if amount is not None:
        try:
            value = money(amount)
        except ValueError:
            raise Bad(f"--amount {amount!r} is not a number")
        out["amount"] = "" if value is None else f"{value:.2f}"
    if pull_date is not None:
        text = pull_date.strip()
        if text and not (re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) and first_date(text)):
            raise Bad(f"--pull-date {pull_date!r} is not yyyy-mm-dd")
        out["pull_date"] = text
    if review is not None:
        if review.upper() not in ("", "PASS", "FAIL"):
            raise Bad(f"--review {review!r} is not PASS or FAIL")
        out["review"] = review.upper()
    return out


def record(folder, period, test, item, state, by, evidence=None, amount=None, pull_date=None,
           review=None, review_file=None, note=None, now=None):
    root, period, month = open_month(folder, check_period(period))
    values = validate(test, item, state, amount, pull_date, review, by)
    key = f"{test}:{values['item']}"
    given = {"test": test, "item": values["item"], "state": state, "by": values["by"],
             "updated_at": (now or datetime.now()).strftime("%Y-%m-%dT%H:%M:%S")}
    if evidence is not None:
        given["evidence"] = evidence.strip()
    for name in ("amount", "pull_date", "review"):
        if name in values:
            given[name] = values[name]
    if review_file is not None:
        given["review_file"] = review_file.strip()
    if note is not None:
        given["note"] = " ".join(note.split())
    path = evidence_path(root, period)
    action, row, cleared = upsert_evidence(path, key, given)
    warnings = []
    named = row["evidence"]
    # A ledger reference ("JE 8420") is not a file; anything else should exist in the month folder.
    if named and not re.match(r"^JE\b", named, re.I) and not (month_folder(root, period) / named).exists():
        warnings.append(f"the evidence file {named} does not exist in the month folder")
    if cleared:
        warnings.append("the review was cleared because the work changed; record the new review")
    return {"id": key, "action": action, "path": str(path), "row": row, "warnings": warnings}


def main(argv=None):
    p = argparse.ArgumentParser(description="Upsert one row of the month's evidence file. Exit 0 when recorded, 2 on a bad argument.")
    p.add_argument("folder", help="the Month-End folder")
    p.add_argument("--period", required=True, help="yyyy-mm")
    p.add_argument("--test", required=True, help=f"one of {', '.join(TESTS)}")
    p.add_argument("--item", required=True, help="what the row is about: an account, an entry name, a question id")
    p.add_argument("--state", required=True, help=f"one of {', '.join(STATES)}")
    p.add_argument("--evidence", help="a path relative to the month folder, or a ledger reference like 'JE 8420'")
    p.add_argument("--amount", help="the amount the work tied to (a reconciliation's GL balance)")
    p.add_argument("--pull-date", help="the date of the ledger pull the work used, yyyy-mm-dd")
    p.add_argument("--review", help="PASS or FAIL ('' clears it)")
    p.add_argument("--review-file", help="the review note, relative to the month folder")
    p.add_argument("--note", help="one line of note")
    p.add_argument("--by", required=True, help="who recorded the row")
    p.add_argument("--format", choices=["text", "json"], default="text")
    a = p.parse_args(argv)
    try:
        result = record(a.folder, a.period, a.test, a.item, a.state, a.by, evidence=a.evidence, amount=a.amount,
                        pull_date=a.pull_date, review=a.review, review_file=a.review_file, note=a.note)
    except (Bad, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if a.format == "json":
        print(json.dumps(result, indent=1))
    else:
        print(f"{result['action']} {result['id']} in {Path(result['path']).name}")
        for warning in result["warnings"]:
            print(f"  warning: {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
