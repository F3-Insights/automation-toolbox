# /// script
# dependencies = ["pyyaml"]
# ///
"""Record a review or an owner-approved exception in a board-package period's evidence file.

The evidence file is work/BOARD-EVIDENCE-<yyyy-mm>.csv in the period folder, columns
id,kind,item,state,evidence,review_file,note,updated_at,by. This script is its only writer.

  review      review:finance or review:redteam, passed or failed, with the review note's path
              (it must exist). The check counts a review only when it is newer than every
              package file and the figure ledger.
  exception   exception:F12, approved or withdrawn. A figure that does not tie counts as tied
              only with an approved exception, and only the owner approves one: --evidence
              names the comms-confirm request (CR- and 10 hex) in work/CONFIRMATIONS.md that
              carried the owner's answer.
  show        print the evidence file.

Exit 0 recorded, 1 refused (no such review file, figure or request), 2 on a bad argument or a
missing Context.

    python3 board_package_record.py acme-board review --kind finance --state passed --file work/finance-review.md --period 2026-09
    python3 board_package_record.py acme-board exception --figure F12 --evidence CR-0123456789 --note "the owner keeps (51)"
"""

import argparse
import json
import re
from pathlib import Path

import _common as bc

CR_RE = re.compile(r"^CR-[0-9a-f]{10}$")


def record(per, by: str, key: str, values: dict) -> str:
    per.work.mkdir(parents=True, exist_ok=True)
    return bc.upsert_row(per.evidence_file, bc.EVIDENCE_COLUMNS, key,
                         {**values, "updated_at": bc.now_utc(), "by": by})


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a review or an owner-approved exception in COMPANY's "
                                                 "period evidence file.")
    parser.add_argument("company", nargs="?", default="", metavar="COMPANY")
    common = argparse.ArgumentParser(add_help=False)
    bc.add_period_options(common)
    common.add_argument("--by", default="", help="Who records (default board-package-record)")
    sub = parser.add_subparsers(dest="action", required=True)
    review = sub.add_parser("review", parents=[common], help="Record the finance review or the red team's verdict")
    review.add_argument("--kind", choices=bc.REVIEW_KINDS, required=True)
    review.add_argument("--state", choices=bc.REVIEW_STATES, required=True)
    review.add_argument("--file", required=True, help="The review note (relative to the period folder or absolute)")
    review.add_argument("--note", default="")
    exc = sub.add_parser("exception", parents=[common], help="Record the owner's approval of a figure that does not tie")
    exc.add_argument("--figure", required=True, help="The figure's id in the figure ledger (F12)")
    exc.add_argument("--evidence", required=True, help="The comms-confirm request that carried the owner's answer")
    exc.add_argument("--note", required=True, help="What the owner approved and why")
    exc.add_argument("--state", choices=bc.EXCEPTION_STATES, default="approved")
    show = sub.add_parser("show", parents=[common], help="Print the evidence file")
    show.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    per = bc.resolve(args)
    by = bc.blank(args.by) or "board-package-record"
    if args.action == "review":
        path = Path(args.file).expanduser()
        if not path.is_absolute():
            path = per.period_dir / path
        if not path.is_file():
            raise bc.Refused(f"no review note at {path}")
        action = record(per, by, f"review:{args.kind}", {"kind": "review", "item": args.kind, "state": args.state,
                                                         "evidence": "", "review_file": str(path), "note": args.note})
        print(f"{action.upper()} review:{args.kind} {args.state} in {per.evidence_file}")
    elif args.action == "exception":
        fid = args.figure.strip()
        if not re.fullmatch(r"F\d+", fid):
            raise bc.Bad(f"--figure {args.figure!r} is not a figure id like F12")
        if fid not in {r.get("id") for r in bc.read_csv(per.work / bc.PACKAGE_FIGURES_CSV)}:
            raise bc.Refused(f"no figure {fid} in {bc.PACKAGE_FIGURES_CSV}")
        cr = args.evidence.strip()
        if not CR_RE.match(cr):
            raise bc.Bad(f"--evidence {args.evidence!r} is not a comms-confirm request id (CR- and 10 hex)")
        store = per.work / bc.CONFIRMATIONS_MD
        if not re.search(rf"^## {re.escape(cr)}\s*$", store.read_text(encoding="utf-8") if store.is_file() else "", re.M):
            raise bc.Refused(f"{cr} is not in {store}: only the owner's answer approves an exception")
        if not bc.blank(args.note):
            raise bc.Bad("--note is required: what the owner approved and why")
        action = record(per, by, f"exception:{fid}", {"kind": "exception", "item": fid, "state": args.state,
                                                      "evidence": cr, "review_file": "", "note": args.note})
        print(f"{action.upper()} exception:{fid} {args.state} in {per.evidence_file}")
    else:
        rows = list(bc.evidence_rows(per.evidence_file).values())
        if args.format == "json":
            print(json.dumps(rows, indent=1, ensure_ascii=False))
        else:
            print(f"{per.evidence_file} ({len(rows)} rows)")
            for r in rows:
                print(f"  {r['id']:16} {r.get('state', ''):9} {r.get('updated_at', '')}  "
                      f"{r.get('review_file') or r.get('evidence', '')}  {r.get('note', '')}")
    return 0


if __name__ == "__main__":
    bc.run_main(main)
