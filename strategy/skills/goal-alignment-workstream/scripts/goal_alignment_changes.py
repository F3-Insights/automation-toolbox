#!/usr/bin/env python3
"""goal-alignment-changes: write the Run's change set from the owner's answers only.

The Automation's first finish step, before task-stack-workstream's task_stack_apply.py --run
RUN. It writes RUN/changes.json and replaces any file the session left there: the change set
is computed here, never taken from the session.

- The pack pass writes an empty change set. Preparing the note changes nothing.
- The approve pass reads the PUBLISHED review (review.json in the month's folder, which only
  goal_alignment_publish.py writes) and the owner's answers from their sources (the alignment
  task's comments, ANSWERS.md, --answers), and puts in the change set exactly the ops of each
  item's approved verb, project ops before goal ops (a goal closes only once the projects
  serving it are closed or relinked). An item answered no, unanswered, unclear, answered with
  more than its verb, or with a verb it does not offer contributes nothing; each of those but
  no and unanswered becomes a question. When every item has a clean answer, the alignment task
  itself is completed, with the note as its evidence. It also writes RUN/answers-final.json,
  the resolution the change set came from (its maps are the approved mappings
  goal_alignment_publish.py records in the home).

Prints one JSON object. Exit 0 when it wrote the change set, 1 when it refused (the passes
disagree, the published review does not validate), 2 on a bad argument or an unreadable Portal.

Settings: portal_mcp_config (and portal_server); state_dir, or --home.

Example:
  python3 goal_alignment_changes.py --run RUN --answers "1) ok 2) close 3) no"
"""

import argparse
import json
import sys
from datetime import date

import _common as c

ORDER = {"project_edit": 0, "project_close": 1, "goal_edit": 3, "goal_close": 4}


def main(argv=None, client=None):
    p = argparse.ArgumentParser(prog="goal_alignment_changes.py", description=__doc__.split("\n\n")[0])
    p.add_argument("month", nargs="?", default="", help="2030-02, a date in the month, or blank")
    p.add_argument("--run", dest="run_dir", required=True, help="The Run folder")
    p.add_argument("--home", default="", help="The goal-alignment home (default <state_dir>/goal-alignment)")
    p.add_argument("--pass", dest="wanted", default="auto", help="auto, pack or approve")
    p.add_argument("--answers", default="", help="The owner's answers from the launch form")
    p.add_argument("--dry-run-if", default="", help="true or false (a scheduler placeholder)")
    p.add_argument("--config", default="", help="MCP config holding the Portal (default: setting portal_mcp_config)")
    p.add_argument("--server", default="", help="Server name in the MCP config (default: setting portal_server)")
    args = p.parse_args(argv)
    try:
        run = c.guard_run_path(args.run_dir)
        passed = c.read_json(run / "pass.json")
        if not isinstance(passed, dict) or passed.get("schema") != c.PASS_SCHEMA:
            raise c.Bad(f"{run / 'pass.json'} is not goal_alignment_gather.py's pass record")
        mo = c.resolve_month(args.month, date.fromisoformat(passed["as_of"]))
        folder = c.month_dir(c.home_path(args.home), mo["month"])
        if mo["month"] != passed["month"]["month"]:
            raise c.Refuse(f"this Run gathered {passed['month']['month']}, not {mo['month']}")
        chosen, published = c.resolve_pass(args.wanted, folder)
        if chosen != passed.get("pass"):
            raise c.Refuse(f"the prepare step chose the {passed.get('pass')} pass, and now it is {chosen}")
        dry = c.truthy(args.dry_run_if)
        counts = {}
        if chosen == "pack":
            changes = c.change_set([], notes=[f"goal alignment {mo['month']}: the pack pass changes nothing"], dry_run=dry)
        else:
            client = client or c.Portal(args.config or None, args.server or None)
            ops, questions, answers = c.approve_change_set(folder, mo["month"], published, args.answers, client,
                                                           "a0-close", f"goal alignment for {mo['month']}", ORDER)
            answers["month"] = mo["month"]
            counts = answers["counts"]
            changes = c.change_set(ops, questions, [f"goal alignment {mo['month']}: {c.answer_line(counts)}; "
                                                    f"{len(answers['maps'])} mapping(s) to record"], dry)
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
    print(json.dumps({"tool": "goal-alignment-changes", "month": mo["month"], "pass": chosen, "dry_run": dry,
                      "ops": len(changes["ops"]), "questions": len(changes["questions"]), "answers": counts,
                      "changes": str(run / "changes.json")}, indent=1))
    sys.exit(0)


if __name__ == "__main__":
    main()
