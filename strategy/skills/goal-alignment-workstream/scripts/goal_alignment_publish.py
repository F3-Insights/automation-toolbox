#!/usr/bin/env python3
"""goal-alignment-publish: keep the month in the goal-alignment home and put the note in front
of the owner.

The Automation's last finish step, after task_stack_apply.py. It reads RUN/pass.json.

The pack pass:
1. Renders the note again from RUN/review.json and RUN/inputs/ (goal_alignment_pack.py's
   rules); an invalid review is exit 1 and nothing is written.
2. Refuses to replace a published note once the owner has answered it (ANSWERS.md, a comment
   of theirs on the alignment task, or an approval applied): a new note would renumber the
   items under their answers.
3. Keeps the month: inputs/, review.json, NOTE.md and items.json in the month's folder (an
   earlier unanswered note moves to superseded-<stamp>/), and one row per item in
   GOAL-ALIGNMENT-ITEMS-<month>.csv.
4. The alignment task "Approve the goal alignment for <month>", the owner's, due a week out,
   with the approval list as its description, in --alignment-project (or the catch-all of
   --alignment-domain). It is created once, through task-stack-workstream's
   task_stack_apply.py (a create keyed by the month, so a re-run finds it); a re-run that
   replaced the note posts the new list as a comment the same way.
5. The note, found by the month's marker or created once, on the alignment task, tagged
   goal-alignment, set PRIVATE and read back PRIVATE with its marker.
6. publish.json: the task and note refs, the note's hash, when.

The approve pass keeps changes.json, answers-final.json and the task_stack_apply.py result in
approve-<stamp>/, records the approved Portal-goal-to-strategic-goal mappings in
<home>/goal-map.json, writes applied.json, updates each item's row with its answer and outcome,
and appends the answers and outcomes to the note.

A dry run (--dry-run-if true) writes nothing outside the Run folder and nothing to the Portal:
it writes RUN/publish-dry-run.json, what it would have done. Prints one JSON object. Exit 0
when it published (or would have), 1 when it refused, 2 on a bad argument or a failed write.

Settings: portal_mcp_config (and portal_server); [goal-alignment-workstream]
alignment_project or alignment_domain (uuids) when the flags are not given.

Example:
  python3 goal_alignment_publish.py --run RUN --alignment-project 00000000-0000-4000-8000-000000000001
"""

import argparse
import json
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

import _common as c

ITEM_COLUMNS = ("id", "section", "target", "title", "proposal", "answer", "state", "ops", "outcome", "updated_at",
                "by")
NOTE_TAG = "goal-alignment"
BY = "goal-alignment-publish"


def build_note(run):
    """The note exactly as goal_alignment_pack.py renders it: (items, problems, text)."""
    passed = c.read_json(run / "pass.json")
    if not (run / "review.json").is_file():
        return [], [f"{run / 'review.json'} does not exist yet"], ""
    review = c.read_json(run / "review.json")
    items, problems = c.validate_review(review, passed["month"]["month"])
    inputs = c.load_inputs(run / "inputs")
    if inputs.get("goals") is None:
        problems.append("inputs/goals.json is missing: the gather did not run")
    cad = inputs.get("cadence") or {}
    if isinstance(review, dict) and cad.get("cadence") and review.get("cadence") != cad["cadence"]:
        problems.append(f"cadence is {review.get('cadence')!r}; this Run is {cad['cadence']} (inputs/cadence.json)")
    text = c.render_note(review, items, inputs, passed["month"]) if isinstance(review, dict) else ""
    return items, problems, text


def target(item):
    return item.get("goal") or item.get("project") or ((item.get("map") or {}).get("goal")) or ""


def task_text(items, label, mark):
    lines = [f"The goal alignment for {label} is ready: the private note \"Goal alignment {label}\" on this task "
             "holds the month's facts. Answer the list below in one comment here, for example \"1) ok 2) park "
             "3) no\" (\"rest ok\" answers the rest). Nothing you do not approve is changed.", ""]
    return "\n".join(lines + (c.approval_list(items) or ["Nothing to approve this month."])
                     + ["", f"goal-alignment-orchestrator via {BY}. Marker: {mark}"])


def task_ops(items, month, published, replaced, project, domain):
    """The alignment task's create (keyed by the month, so it is made once) and, when the note
    was prepared again, a comment carrying the new list."""
    mark = c.marker(month["month"])
    ops = [{"id": "a0-task", "op": "create", "title": f"Approve the goal alignment for {month['month']}",
            "description": task_text(items, month["month"], mark)[:3800],
            "due_date": (date.today() + timedelta(days=7)).isoformat(), "priority": 2,
            "source": f"goal-alignment:{month['month']}",
            "reason": f"The goal alignment for {month['month']} waits on the owner's answers",
            **({"project": project} if project else {"domain": domain})}]
    if replaced and published and published.get("task"):
        body = ("The note was prepared again; this list replaces the one above.\n\n"
                + "\n".join(c.approval_list(items)))[:3600]
        ops.append({"id": "a0-relist", "op": "comment", "task": published["task"], "body": body,
                    "reason": f"The goal alignment for {month['month']} was prepared again"})
    return ops


def pack_publish(run, passed, dry, client, project, domain, config, server):
    items, problems, text = build_note(run)
    if problems:
        raise c.Refuse(f"the review does not validate ({len(problems)} problem(s), first: {problems[0]})")
    month, folder = passed["month"], Path(passed["month_dir"])
    published = c.maybe_json(folder / "publish.json")
    published = published if isinstance(published, dict) and not published.get("dry_run") else None
    why = c.answered_already(folder, published, client)
    if why:
        raise c.Refuse(f"the published note for {month['month']} is already being answered ({why}); a new note "
                       "would renumber the items under the answers")
    plan = {"month": month["month"], "items": len(items), "note_sha": c.sha(text),
            "replaces_note": (folder / "review.json").is_file(), "month_dir": str(folder)}
    if dry:
        return dict(plan, dry_run=True, would=["keep the note in the month's folder",
                                               "find or create the alignment task through task_stack_apply.py",
                                               "find or create the PRIVATE note and read it back"])
    if not (project or domain):
        raise c.Bad("the alignment task needs a project or domain: pass --alignment-project or --alignment-domain, "
                    "or set alignment_project or alignment_domain in [goal-alignment-workstream]")
    if plan["replaces_note"]:
        old = c.new_dir(folder, "superseded")
        for name in ("review.json", "NOTE.md", "items.json", "inputs"):
            if (folder / name).exists():
                shutil.move(str(folder / name), str(old / name))
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copytree(run / "inputs", folder / "inputs")
    shutil.copyfile(run / "review.json", folder / "review.json")
    c.write_text(folder / "NOTE.md", text)
    c.write_json(folder / "items.json", {"month": month["month"], "items": items})
    c.upsert_items(folder / c.items_ledger_name(month["month"]), ITEM_COLUMNS, {it["n"]: {
        "section": it["section"], "target": target(it), "title": it["title"], "proposal": it["proposal"],
        "answer": "", "state": "proposed", "ops": "", "outcome": "", "updated_at": c.now_iso(), "by": BY}
        for it in items})
    ops = task_ops(items, month, published, plan["replaces_note"], project, domain)
    results = c.apply_tasks(run, "publish-task", ops, config, server)
    task_ref = results["a0-task"].get("task")
    if not c.task_uuid(task_ref):
        raise c.Bad("task_stack_apply.py did not name the alignment task")
    task = {"ref": task_ref, "outcome": "commented" if "a0-relist" in results else
            ("created" if results["a0-task"]["outcome"] == "applied" else "found")}
    note = c.ensure_note(client, f"Goal alignment {month['month']}", NOTE_TAG, text, c.marker(month["month"]),
                         (published or {}).get("note"), task["ref"])
    record = {"schema": "goal-alignment/publish@1", "month": month["month"], "dry_run": False, "task": task["ref"],
              "note": note["ref"], "visibility": note["visibility"], "note_sha": plan["note_sha"],
              "items": len(items), "published_at": c.now_iso()}
    c.write_json(folder / "publish.json", record)
    c.append_log(folder, "Goal alignment log", f"note published: {len(items)} items; task {task['ref']} "
                 f"({task['outcome']}); note {note['ref']} ({note['outcome']}, PRIVATE)")
    return dict(record, task_outcome=task["outcome"], note_outcome=note["outcome"])


def record_maps(home, maps, month, items):
    """The approved mappings into <home>/goal-map.json, one entry per Portal goal; a later
    approval for the same goal replaces the earlier one."""
    if not maps:
        return 0
    path = Path(home) / c.GOAL_MAP
    goals = dict((c.maybe_json(path) or {}).get("goals") or {})
    titles = {it["n"]: it["title"] for it in items}
    for m in maps:
        gid = c.goal_id(m.get("goal"))
        if gid:
            goals[gid] = {"telos": m.get("telos"), "item_title": titles.get(m.get("item")), "approved_in": month,
                          "approved_at": c.now_iso()}
    c.write_json(path, {"schema": "goal-alignment/goal-map@1", "goals": goals, "updated_at": c.now_iso()})
    return len(maps)


def approve_publish(run, passed, dry, client):
    month, folder = passed["month"], Path(passed["month_dir"])
    changes = c.read_json(run / "changes.json")
    answers = c.read_json(run / "answers-final.json")
    applied = c.maybe_json(run / ("apply-dry-run.json" if dry else "apply.json")) or {}
    results = applied.get("results") or []
    outcomes = c.item_outcomes(answers, results)
    counts = {}
    for o in outcomes.values():
        counts[o["state"]] = counts.get(o["state"], 0) + 1
    summary = {"schema": "goal-alignment/applied@1", "month": month["month"], "dry_run": dry, "at": c.now_iso(),
               "apply_status": applied.get("status"), "ops": len(changes.get("ops") or []), "items": counts,
               "maps": len(answers.get("maps") or []), "questions": changes.get("questions") or [],
               "alignment_task_closed": any(r.get("id") == "a0-close" and r.get("outcome") == "applied"
                                            for r in results)}
    if dry:
        return dict(summary, would=["keep the answers and results in the month's folder",
                                    f"record {summary['maps']} mapping(s) in the goal map",
                                    "update each item's row", "append the outcomes to the note"])
    keep = c.new_dir(folder, "approve")
    for name in ("changes.json", "answers-final.json", "apply.json", "undo.jsonl"):
        if (run / name).is_file():
            shutil.copyfile(run / name, keep / name)
    summary["kept"] = str(keep)
    items = (c.maybe_json(folder / "items.json") or {}).get("items") or []
    summary["maps_recorded"] = record_maps(passed["home"], answers.get("maps") or [], month["month"], items)
    c.write_json(folder / "applied.json", summary)
    c.upsert_items(folder / c.items_ledger_name(month["month"]), ITEM_COLUMNS, {n: {
        "answer": o["answer"], "state": o["state"], "ops": o["ops"], "outcome": o["outcome"],
        "updated_at": c.now_iso(), "by": BY} for n, o in outcomes.items()})
    published = c.read_json(folder / "publish.json")
    note_text = (folder / "NOTE.md").read_text(encoding="utf-8")
    content = note_text.rstrip() + "\n\n" + "\n".join(c.outcome_table(outcomes, summary["questions"])) + "\n"
    note = c.ensure_note(client, f"Goal alignment {month['month']}", NOTE_TAG, content, c.marker(month["month"]),
                         published.get("note"), published.get("task"))
    c.append_log(folder, "Goal alignment log", f"approval applied: {c.answer_line(counts)}; apply "
                 f"{applied.get('status')}; {summary['maps_recorded']} mapping(s) recorded; note {note['outcome']}")
    return dict(summary, note=note["ref"])


def main(argv=None, client=None):
    p = argparse.ArgumentParser(prog="goal_alignment_publish.py", description=__doc__.split("\n\n")[0])
    p.add_argument("--run", dest="run_dir", required=True, help="The Run folder")
    p.add_argument("--dry-run-if", default="", help="true or false (a scheduler placeholder)")
    p.add_argument("--alignment-project", default="", help="The project the alignment task goes in (uuid)")
    p.add_argument("--alignment-domain", default="", help="Else the domain whose catch-all takes it (uuid)")
    p.add_argument("--config", default="", help="MCP config holding the Portal (default: setting portal_mcp_config)")
    p.add_argument("--server", default="", help="Server name in the MCP config (default: setting portal_server)")
    args = p.parse_args(argv)
    try:
        run = c.guard_run_path(args.run_dir)
        passed = c.read_json(run / "pass.json")
        if not isinstance(passed, dict) or passed.get("schema") != c.PASS_SCHEMA:
            raise c.Bad(f"{run / 'pass.json'} is not goal_alignment_gather.py's pass record")
        dry = c.truthy(args.dry_run_if)
        if client is None and not (dry and passed["pass"] == "approve"):
            client = c.Portal(args.config or None, args.server or None)
        mine = c.settings(c.SKILL)
        if passed["pass"] == "pack":
            result = pack_publish(run, passed, dry, client,
                                  args.alignment_project.strip() or mine.get("alignment_project", ""),
                                  args.alignment_domain.strip() or mine.get("alignment_domain", ""),
                                  args.config or None, args.server or None)
        else:
            result = approve_publish(run, passed, dry, client)
        if dry:
            c.write_json(run / "publish-dry-run.json", result)
    except c.Refuse as exc:
        print(c.safe(f"REFUSED: {exc}"))
        sys.exit(1)
    except (c.Bad, ValueError, KeyError) as exc:
        print(c.safe(f"ERROR {exc}"), file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # a Portal write that failed
        print(c.safe(f"ERROR the Portal write failed ({type(exc).__name__}: {exc})"), file=sys.stderr)
        sys.exit(2)
    print(c.safe(json.dumps(dict(result, tool="goal-alignment-publish", **{"pass": passed["pass"]}), indent=1,
                            default=str)))
    sys.exit(0)


if __name__ == "__main__":
    main()
