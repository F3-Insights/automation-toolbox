#!/usr/bin/env python3
"""goal-alignment-check: whether a month's goal alignment is done, computed from its folder.

MONTH is 2030-02, a date in it, or blank for the last full month. The home is --home, else
<state_dir>/goal-alignment (setting state_dir). Four tests of done, from the files in
<home>/<yyyy>/<yyyy-mm>/:
  1 pack       inputs/goals.json exists, review.json validates, and NOTE.md is exactly the note
               those files render, with one numbered approval list.
  2 published  publish.json names the alignment task and the note, not a dry run, and says the
               note read back PRIVATE.
  3 answered   every item has a plain answer (ANSWERS.md, the last approval's launch form, and
               with --portal the owner's comments on the alignment task).
  4 applied    applied.json exists, it applied exactly the approved ops, the task-stack apply
               ended applied or nothing, and every approved mapping is in <home>/goal-map.json.

--precheck prints one line for a scheduler, WORK: or NOTHING:. --pass pack: WORK while the
month has no published note; --pass approve: WORK when published answers are not yet applied;
auto (default): the first of the two. Read only; --portal makes one Portal read (setting
portal_mcp_config). Exit 0 whenever it ran, 2 on a bad argument.

Example:
  python3 goal_alignment_check.py 2030-02 --format json
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


def form_answers(applied):
    """The answers the last approval took from its launch form, read back from its record."""
    if not isinstance(applied, dict) or not applied.get("kept"):
        return []
    final = c.maybe_json(Path(str(applied["kept"])) / "answers-final.json") or {}
    lines = [f"{r['n']}) {r['answer']}" for r in final.get("items") or []
             if r.get("source") == "the launch form" and r.get("answer") and not r.get("by_rest")]
    return [{"source": "the last approval's launch form", "text": "\n".join(lines)}] if lines else []


def check(month="", home="", as_of=None, client=None):
    today = date.fromisoformat(as_of) if as_of else date.today()
    mo = c.resolve_month(month, today)
    root = c.home_path(home)
    folder = c.month_dir(root, mo["month"])
    tests = {}

    gaps, items = [], []
    review = c.maybe_json(folder / "review.json")
    if not (folder / "inputs" / "goals.json").is_file():
        gaps.append("no gathered inputs (inputs/goals.json)")
    if review is None:
        gaps.append("no review.json")
    else:
        items, problems = c.validate_review(review, mo["month"])
        gaps += [f"review.json: {p}" for p in problems[:5]]
        if not problems and (folder / "NOTE.md").is_file():
            if (folder / "NOTE.md").read_text(encoding="utf-8") != c.render_note(
                    review, items, c.load_inputs(folder / "inputs"), mo):
                gaps.append("NOTE.md is not the note review.json renders")
        elif not (folder / "NOTE.md").is_file():
            gaps.append("no NOTE.md")
    tests["pack"] = test(not gaps, gaps, items=len(items))

    published = c.maybe_json(folder / "publish.json")
    gaps = []
    if not isinstance(published, dict):
        gaps.append("not published (no publish.json)")
    else:
        if published.get("dry_run"):
            gaps.append("only a dry run was published")
        gaps += [f"publish.json names no alignment {k}" for k in ("task", "note")
                 if not str(published.get(k) or "").startswith("portal://")]
        if str(published.get("visibility") or "").upper() != "PRIVATE":
            gaps.append("the note was not read back PRIVATE")
    tests["published"] = test(not gaps, gaps, task=(published or {}).get("task"), note=(published or {}).get("note"))

    gaps, resolved, portal_read = [], None, None
    applied = c.maybe_json(folder / "applied.json")
    if items:
        try:
            sources = c.answer_sources(folder, "", client, (published or {}).get("task") if client else None)
            sources = form_answers(applied) + sources
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
    elif review is None:
        gaps.append("no items to answer yet")
    tests["answered"] = test(not gaps, gaps, answers=(resolved or {}).get("counts"), portal=portal_read)

    gaps = []
    if not isinstance(applied, dict):
        if items:
            gaps.append("no approval applied (no applied.json)")
        elif review is None:
            gaps.append("nothing to apply yet")
    else:
        if applied.get("apply_status") not in ("applied", "nothing"):
            gaps.append(f"task-stack apply ended {applied.get('apply_status')!r}")
        kept = Path(str(applied.get("kept") or ""))
        changes = c.maybe_json(kept / "changes.json") if (kept / "changes.json").is_file() else None
        if resolved is not None and isinstance(changes, dict):
            want = {op["id"] for op in resolved["ops"]}
            got = {op.get("id") for op in changes.get("ops") or [] if op.get("id") != "a0-close"}
            if got - want:
                gaps.append(f"applied ops no answer approves: {', '.join(sorted(got - want))}")
            if want - got:
                gaps.append(f"approved ops not yet applied: {', '.join(sorted(want - got))}")
        elif resolved is not None:
            gaps.append("the applied change set is missing")
        gaps += [f"{applied['items'][s]} item(s) {s}" for s in ("refused", "partial", "deferred")
                 if (applied.get("items") or {}).get(s)]
        if resolved is not None and resolved["maps"]:
            recorded = (c.maybe_json(root / c.GOAL_MAP) or {}).get("goals") or {}
            missing = [m["goal"] for m in resolved["maps"] if c.goal_id(m["goal"]) not in recorded]
            if missing:
                gaps.append(f"{len(missing)} approved mapping(s) not in {c.GOAL_MAP}")
    tests["applied"] = test(not gaps, gaps)

    met = sum(1 for t in tests.values() if t["met"])
    return {"month": mo["month"], "first": mo["first"], "last": mo["last"], "home": str(root),
            "month_dir": str(folder), "as_of": today.isoformat(), "tests": tests, "met": met, "of": len(TESTS),
            "done": met == len(TESTS)}


def precheck_line(result, wanted="auto"):
    t, month = result["tests"], result["month"]
    if wanted in ("auto", "pack") and not t["published"]["met"]:
        return f"WORK: no published goal alignment for {month}"
    if wanted == "pack":
        return f"NOTHING: the goal alignment for {month} is published"
    answers = t["answered"].get("answers") or {}
    approvable = sum(answers.get(k, 0) for k in ("approved", "recorded", "declined"))
    if not t["published"]["met"]:
        return f"NOTHING: no published goal alignment for {month} to approve"
    if approvable and not t["applied"]["met"]:
        return f"WORK: {approvable} answered item(s) of {month} to apply ({c.answer_line(answers)})"
    if not t["answered"]["met"]:
        return f"NOTHING: waiting on the owner's answers for {month} ({c.answer_line(answers)})"
    return f"NOTHING: the goal alignment for {month} is applied"


def render(result):
    out = [f"goal-alignment-check {result['month']} ({result['first']} to {result['last']}) in {result['month_dir']}",
           f"{'DONE' if result['done'] else 'NOT DONE'} ({result['met']} of {result['of']} tests met)"]
    for number, (name, t) in enumerate(result["tests"].items(), start=1):
        out.append(f"{number} {name}: {'MET' if t['met'] else 'NOT MET'}")
        out += [f"  - {gap}" for gap in t["gaps"]]
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(prog="goal_alignment_check.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("month", nargs="?", default="")
    p.add_argument("--home", default="", help="The goal-alignment home (default <state_dir>/goal-alignment)")
    p.add_argument("--pass", dest="wanted", default="auto", help="auto, pack or approve (for --precheck)")
    p.add_argument("--portal", action="store_true", help="Also read the owner's answers on the alignment task")
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
        result = check(args.month, args.home, as_of or None, client)
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
