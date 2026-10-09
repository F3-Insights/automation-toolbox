#!/usr/bin/env python3
"""weekly-review-changes: write the Run's task change set from the owner's answers only.

The Automation's first finish step, before task-stack-workstream's task_stack_apply.py --run
RUN. It writes RUN/changes.json and replaces any file the session left there: the change set
is computed here, never taken from the session.

- The pack pass writes an empty change set. Preparing the review changes no task.
- The approve pass reads the PUBLISHED review (review.json in the week's folder, which only
  weekly_review_publish.py writes) and the owner's answers from their sources (the review
  task's comments, ANSWERS.md in the week's folder, --answers), and puts in the change set
  exactly the ops of each item's approved verb. An item answered no, unanswered, unclear,
  answered with more than its verb, or with a verb it does not offer contributes nothing; each
  of those but no and unanswered becomes a question. When every item has a clean answer, the
  review task itself is completed, with the review note as its evidence. It also writes
  RUN/answers-final.json, the resolution the change set came from.

The pass is resolved as weekly_review_gather.py resolved it and must agree with RUN/pass.json.
Prints one JSON object. Exit 0 when it wrote the change set, 1 when it refused (the passes
disagree, the published review does not validate), 2 on a bad argument or an unreadable Portal.

Settings: portal_mcp_config (and portal_server); state_dir, or --home.

Example:
  python3 weekly_review_changes.py --run RUN --answers "1) ok 2) park"
"""

import argparse
import json
import sys
from datetime import date

import _common as c


def main(argv=None, client=None):
    p = argparse.ArgumentParser(prog="weekly_review_changes.py", description=__doc__.split("\n\n")[0])
    p.add_argument("week", nargs="?", default="", help="2030-W10, a date in the week, or blank")
    p.add_argument("--run", dest="run_dir", required=True, help="The Run folder")
    p.add_argument("--home", default="", help="The weekly-review home (default <state_dir>/weekly-review)")
    p.add_argument("--pass", dest="wanted", default="auto", help="auto, pack or approve")
    p.add_argument("--answers", default="", help="The owner's answers from the launch form")
    p.add_argument("--dry-run-if", default="", help="true or false (a scheduler placeholder)")
    p.add_argument("--as-of", default="", help="The date the week is judged from (yyyy-mm-dd); blank: the gather's")
    p.add_argument("--config", default="", help="MCP config holding the Portal (default: setting portal_mcp_config)")
    p.add_argument("--server", default="", help="Server name in the MCP config (default: setting portal_server)")
    args = p.parse_args(argv)
    try:
        run = c.guard_run_path(args.run_dir)
        passed = c.read_json(run / "pass.json")
        if not isinstance(passed, dict) or passed.get("schema") != c.PASS_SCHEMA:
            raise c.Bad(f"{run / 'pass.json'} is not weekly_review_gather.py's pass record")
        today = date.fromisoformat(args.as_of.strip() or passed["as_of"])
        wk = c.resolve_week(args.week, today)
        folder = c.week_dir(c.home_path(args.home), wk["week"])
        if wk["week"] != passed["week"]["week"]:
            raise c.Refuse(f"this Run gathered {passed['week']['week']}, not {wk['week']}")
        chosen, published = c.resolve_pass(args.wanted, folder)
        if chosen != passed.get("pass"):
            raise c.Refuse(f"the prepare step chose the {passed.get('pass')} pass, and now it is {chosen}")
        dry = c.truthy(args.dry_run_if)
        counts = {}
        if chosen == "pack":
            changes = c.change_set([], notes=[f"weekly review {wk['week']}: the pack pass changes no task"], dry_run=dry)
        else:
            client = client or c.Portal(args.config or None, args.server or None)
            ops, questions, answers = c.approve_change_set(folder, wk["week"], published, args.answers, client,
                                                           "w0-close", f"weekly review {wk['week']}")
            answers["week"] = wk["week"]
            counts = answers["counts"]
            changes = c.change_set(ops, questions, [f"weekly review {wk['week']}: {c.answer_line(counts)}"], dry)
            c.write_json(run / "answers-final.json", answers)
        c.write_json(run / "changes.json", changes)
    except c.Refuse as exc:
        print(c.safe(f"REFUSED: {exc}; no change set written"))
        sys.exit(1)
    except (c.Bad, ValueError, KeyError) as exc:
        print(c.safe(f"ERROR {exc}"), file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # the Portal could not be read
        print(c.safe(f"ERROR the Portal could not be read ({type(exc).__name__}: {exc})"), file=sys.stderr)
        sys.exit(2)
    print(json.dumps({"tool": "weekly-review-changes", "week": wk["week"], "pass": chosen, "dry_run": dry,
                      "ops": len(changes["ops"]), "questions": len(changes["questions"]), "answers": counts,
                      "changes": str(run / "changes.json")}, indent=1))
    sys.exit(0)


if __name__ == "__main__":
    main()
