#!/usr/bin/env python3
"""weekly-review-check: whether a week's review is done, computed from the week's folder.

WEEK is 2030-W10, a date in it, or blank for the week of the latest Friday. The home is
--home, else <state_dir>/weekly-review (setting state_dir). Four tests of done, from the files
in <home>/<yyyy>/<week>/:
  1 pack       inputs/stack.json exists, review.json validates, and PACK.md is exactly the pack
               those files render, with one numbered approval list.
  2 published  publish.json names the review task and the note, not a dry run.
  3 answered   every item has a plain answer (ANSWERS.md; with --portal also the owner's
               comments on the review task). More than a verb, or unclear, is not answered.
  4 applied    applied.json exists, it applied exactly the approved ops of the answers, and
               the task-stack apply ended applied or nothing.

--precheck prints one line for a scheduler, WORK: or NOTHING:. --pass pack: WORK while the
week has no published pack; --pass approve: WORK when published answers are not yet applied;
auto (default): the first of the two. Read only; --portal makes one Portal read (setting
portal_mcp_config). Exit 0 whenever it ran, 2 on a bad argument.

Example:
  python3 weekly_review_check.py 2030-W10 --precheck --pass approve --portal
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import _common as c

TESTS = ("pack", "published", "answered", "applied")


def test(met, gaps, **extra):
    return dict({"met": met, "gaps": gaps}, **extra)


def check(week="", home="", as_of=None, client=None):
    today = date.fromisoformat(as_of) if as_of else date.today()
    wk = c.resolve_week(week, today)
    root = c.home_path(home)
    folder = c.week_dir(root, wk["week"])
    tests = {}

    gaps, items = [], []
    review = c.maybe_json(folder / "review.json")
    if not (folder / "inputs" / "stack.json").is_file():
        gaps.append("no gathered inputs (inputs/stack.json)")
    if review is None:
        gaps.append("no review.json")
    else:
        items, problems = c.validate_review(review, wk["week"])
        gaps += [f"review.json: {p}" for p in problems[:5]]
        if not problems and (folder / "PACK.md").is_file():
            if (folder / "PACK.md").read_text(encoding="utf-8") != c.render_pack(
                    review, items, c.load_inputs(folder / "inputs"), wk):
                gaps.append("PACK.md is not the pack review.json renders")
        elif not (folder / "PACK.md").is_file():
            gaps.append("no PACK.md")
    tests["pack"] = test(not gaps, gaps, items=len(items))

    published = c.maybe_json(folder / "publish.json")
    gaps = []
    if not isinstance(published, dict):
        gaps.append("not published (no publish.json)")
    else:
        if published.get("dry_run"):
            gaps.append("only a dry run was published")
        gaps += [f"publish.json names no review {k}" for k in ("task", "note")
                 if not str(published.get(k) or "").startswith("portal://")]
    tests["published"] = test(not gaps, gaps, task=(published or {}).get("task"), note=(published or {}).get("note"))

    gaps, resolved, portal_read = [], None, None
    if items:
        try:
            sources = c.answer_sources(folder, "", client, (published or {}).get("task") if client else None)
            portal_read = client is not None
        except Exception as exc:  # the Portal could not be read: say so
            sources = c.answer_sources(folder)
            portal_read = f"failed: {type(exc).__name__}"
        resolved = c.resolve(items, sources)
        by = {}
        for r in resolved["items"]:
            if r["state"] not in ("approved", "recorded", "declined"):
                by.setdefault(r["state"], []).append(str(r["n"]))
        gaps += [f"{state}: items {', '.join(ns)}" for state, ns in by.items()]
    else:
        gaps.append("no items to answer yet")
    tests["answered"] = test(not gaps, gaps, answers=(resolved or {}).get("counts"), portal=portal_read)

    gaps = []
    applied = c.maybe_json(folder / "applied.json")
    if not isinstance(applied, dict):
        gaps.append("no approval applied (no applied.json)")
    else:
        if applied.get("apply_status") not in ("applied", "nothing"):
            gaps.append(f"task-stack apply ended {applied.get('apply_status')!r}")
        kept = Path(str(applied.get("kept") or ""))
        changes = c.maybe_json(kept / "changes.json") if (kept / "changes.json").is_file() else None
        if resolved is not None and isinstance(changes, dict):
            want = {op["id"] for op in resolved["ops"]}
            got = {op.get("id") for op in changes.get("ops") or [] if op.get("id") != "w0-close"}
            if got - want:
                gaps.append(f"applied ops no answer approves: {', '.join(sorted(got - want))}")
            if want - got:
                gaps.append(f"approved ops not yet applied: {', '.join(sorted(want - got))}")
        elif resolved is not None:
            gaps.append("the applied change set is missing")
        gaps += [f"{applied['items'][s]} item(s) {s}" for s in ("refused", "partial", "deferred")
                 if (applied.get("items") or {}).get(s)]
    tests["applied"] = test(not gaps, gaps)

    met = sum(1 for t in tests.values() if t["met"])
    return {"week": wk["week"], "monday": wk["monday"], "sunday": wk["sunday"], "home": str(root),
            "week_dir": str(folder), "as_of": today.isoformat(), "tests": tests, "met": met, "of": len(TESTS),
            "done": met == len(TESTS)}


def precheck_line(result, wanted="auto"):
    t, week = result["tests"], result["week"]
    if wanted in ("auto", "pack") and not t["published"]["met"]:
        return f"WORK: no published pack for {week}"
    if wanted == "pack":
        return f"NOTHING: the pack for {week} is published"
    answers = t["answered"].get("answers") or {}
    approvable = sum(answers.get(k, 0) for k in ("approved", "recorded", "declined"))
    if not t["published"]["met"]:
        return f"NOTHING: no published pack for {week} to approve"
    if approvable and not t["applied"]["met"]:
        return f"WORK: {approvable} answered item(s) of {week} to apply ({c.answer_line(answers)})"
    if not t["answered"]["met"]:
        return f"NOTHING: waiting on the owner's answers for {week} ({c.answer_line(answers)})"
    return f"NOTHING: the review for {week} is applied"


def render(result):
    out = [f"weekly-review-check {result['week']} ({result['monday']} to {result['sunday']}) in {result['week_dir']}",
           f"{'DONE' if result['done'] else 'NOT DONE'} ({result['met']} of {result['of']} tests met)"]
    for number, (name, t) in enumerate(result["tests"].items(), start=1):
        out.append(f"{number} {name}: {'MET' if t['met'] else 'NOT MET'}")
        out += [f"  - {gap}" for gap in t["gaps"]]
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(prog="weekly_review_check.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("week", nargs="?", default="")
    p.add_argument("--home", default="", help="The weekly-review home (default <state_dir>/weekly-review)")
    p.add_argument("--pass", dest="wanted", default="auto", help="auto, pack or approve (for --precheck)")
    p.add_argument("--portal", action="store_true", help="Also read the owner's answers on the review task")
    p.add_argument("--as-of", default="", help="Judge as of this date (yyyy-mm-dd); blank: today")
    p.add_argument("--format", dest="fmt", choices=["text", "json"], default="text")
    p.add_argument("--precheck", action="store_true", help="One line, WORK: or NOTHING:, for a scheduler")
    p.add_argument("--config", default="", help="MCP config holding the Portal (default: setting portal_mcp_config)")
    p.add_argument("--server", default="", help="Server name in the MCP config (default: setting portal_server)")
    args = p.parse_args(argv)
    wanted = args.wanted.strip().lower() or "auto"
    try:
        if wanted not in c.PASSES:
            raise c.Bad(f"--pass is one of {', '.join(c.PASSES)}")
        as_of = args.as_of.strip()
        if as_of:
            date.fromisoformat(as_of)
        client = None
        if args.portal:
            try:
                client = c.Portal(args.config or None, args.server or None)
            except Exception:  # no Portal: the comments are not read, and the json says so
                client = None
        result = check(args.week, args.home, as_of or None, client)
    except (c.Bad, ValueError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        sys.exit(2)
    if args.precheck:
        print(precheck_line(result, wanted))
    elif args.fmt == "json":
        print(json.dumps(result, indent=1, default=str))
    else:
        print(render(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
