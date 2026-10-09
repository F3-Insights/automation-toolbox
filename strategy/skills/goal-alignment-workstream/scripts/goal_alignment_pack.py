#!/usr/bin/env python3
"""goal-alignment-pack: check the session's review and render the alignment note.

Reads RUN/review.json (the contract in _common.py), RUN/pass.json and RUN/inputs/ (both from
goal_alignment_gather.py), numbers the items in section order, fills each op's id and reason,
and writes RUN/NOTE.md (the month's facts, the session's notes, the pulse and one approval list) and
RUN/items.json (the numbered items with their ops). The session runs it last and fixes
review.json until it passes; the publish step renders the same note from the same files, so
the numbers the owner answers are the numbers that get applied.

Writes the Run folder only. Prints VALID or INVALID with every problem (or --format json).
Exit 0 when the review is valid, 1 when it is not, 2 on a bad argument.

Example:
  python3 goal_alignment_pack.py RUN
"""

import argparse
import json
import sys

import _common as c


def build(run):
    """The pass record, the numbered items, the problems and the note's text."""
    passed = c.read_json(run / "pass.json")
    if not isinstance(passed, dict) or passed.get("schema") != c.PASS_SCHEMA:
        raise c.Bad(f"{run / 'pass.json'} is not goal_alignment_gather.py's pass record")
    if passed.get("pass") != "pack":
        raise c.Bad(f"this Run is the {passed.get('pass')} pass; only the pack pass renders a note")
    month = passed["month"]
    if not (run / "review.json").is_file():
        return passed, [], [f"{run / 'review.json'} does not exist yet"], ""
    review = c.read_json(run / "review.json")
    items, problems = c.validate_review(review, month["month"])
    inputs = c.load_inputs(run / "inputs")
    if inputs.get("goals") is None:
        problems.append("inputs/goals.json is missing: the gather did not run")
    cad = inputs.get("cadence") or {}
    if isinstance(review, dict) and cad.get("cadence") and review.get("cadence") != cad["cadence"]:
        problems.append(f"cadence is {review.get('cadence')!r}; this Run is {cad['cadence']} (inputs/cadence.json)")
    text = c.render_note(review, items, inputs, month) if isinstance(review, dict) else ""
    return passed, items, problems, text


def main(argv=None):
    p = argparse.ArgumentParser(prog="goal_alignment_pack.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_dir", nargs="?", default="", help="The Run folder holding review.json, pass.json and inputs/")
    p.add_argument("--format", dest="fmt", choices=["text", "json"], default="text")
    args = p.parse_args(argv)
    try:
        if not args.run_dir.strip():
            raise c.Bad("RUN is required: the Run folder holding review.json, pass.json and inputs/")
        run = c.guard_run_path(args.run_dir)
        if not run.is_dir():
            raise c.Bad(f"no Run folder {run}")
        passed, items, problems, text = build(run)
    except c.Bad as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        sys.exit(2)
    if not problems:
        c.write_text(run / "NOTE.md", text)
        c.write_json(run / "items.json", {"month": passed["month"]["month"], "items": items})
    sections = {}
    for it in items:
        sections[it["section"]] = sections.get(it["section"], 0) + 1
    if args.fmt == "json":
        print(json.dumps({"valid": not problems, "items": len(items), "sections": sections, "problems": problems,
                          "note": str(run / "NOTE.md") if not problems else None}, indent=1))
    elif problems:
        print(f"INVALID: {len(problems)} problem(s) in review.json; NOTE.md not written")
        for prob in problems:
            print(f"  - {prob}")
    else:
        print(f"VALID: {len(items)} items (" + ", ".join(f"{k} {v}" for k, v in sections.items())
              + f"); wrote {run / 'NOTE.md'}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
