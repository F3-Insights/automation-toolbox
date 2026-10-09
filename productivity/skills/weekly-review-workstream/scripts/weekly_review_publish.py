#!/usr/bin/env python3
"""weekly-review-publish: keep the week in the review home and put the pack in front of the owner.

The Automation's last finish step, after task_stack_apply.py. It reads RUN/pass.json.

The pack pass:
1. Renders the pack again from RUN/review.json and RUN/inputs/ (weekly_review_pack.py's
   rules); an invalid review is exit 1 and nothing is written.
2. Refuses to replace a published pack once the owner has answered it (ANSWERS.md, a comment
   of theirs on the review task, or an approval applied): a new pack would renumber the items
   under their answers.
3. Keeps the week: inputs/, review.json, PACK.md and items.json in the week's folder (an
   earlier unanswered pack moves to superseded-<stamp>/), and one row per item in
   WEEKLY-REVIEW-ITEMS-<week>.csv.
4. The review task "Approve the weekly review for <week>", the owner's, due the Monday after,
   with the approval list as its description, in --review-project (or the catch-all of
   --review-domain). It is created once, through task-stack-workstream's task_stack_apply.py
   (a create keyed by the week, so a re-run finds it); a re-run that replaced the pack posts
   the new list as a comment the same way.
5. The pack as a note, found by the week's marker or created once, on the review task, tagged
   weekly-review, set PRIVATE and read back PRIVATE with its marker.
6. publish.json: the task and note refs, the pack's hash, when.

The approve pass keeps changes.json, answers-final.json and the task_stack_apply.py result in
approve-<stamp>/, writes applied.json, updates each item's row with its answer and outcome, and
appends the answers and outcomes to the review note.

A dry run (--dry-run-if true) writes nothing outside the Run folder and nothing to the Portal:
it writes RUN/publish-dry-run.json, what it would have done. Prints one JSON object. Exit 0
when it published (or would have), 1 when it refused, 2 on a bad argument or a failed write.

Settings: portal_mcp_config (and portal_server); [weekly-review-workstream] review_project or
review_domain (uuids) when the flags are not given.

Example:
  python3 weekly_review_publish.py --run RUN --review-project 00000000-0000-4000-8000-000000000001
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

import _common as c

ITEM_COLUMNS = ("id", "section", "task", "title", "proposal", "answer", "state", "ops", "outcome", "updated_at", "by")
NOTE_TAG = "weekly-review"
BY = "weekly-review-publish"


def build_pack(run):
    """The pack exactly as weekly_review_pack.py renders it: (items, problems, text)."""
    passed = c.read_json(run / "pass.json")
    if not (run / "review.json").is_file():
        return [], [f"{run / 'review.json'} does not exist yet"], ""
    review = c.read_json(run / "review.json")
    items, problems = c.validate_review(review, passed["week"]["week"])
    inputs = c.load_inputs(run / "inputs")
    if inputs.get("stack") is None:
        problems.append("inputs/stack.json is missing: the gather did not run")
    text = c.render_pack(review, items, inputs, passed["week"]) if isinstance(review, dict) else ""
    return items, problems, text


def task_text(items, label, mark):
    lines = [f"The weekly review for {label} is ready: the private note \"Weekly review {label}\" on this task "
             "holds the pack. Answer the list below in one comment here, for example \"1) ok 2) park 3) no\" "
             "(\"rest ok\" answers the rest). Nothing you do not approve is changed.", ""]
    return "\n".join(lines + c.approval_list(items) + ["", f"weekly-review-orchestrator via {BY}. Marker: {mark}"])


def task_ops(items, week, published, replaced, project, domain):
    """The review task's create (keyed by the week, so it is made once) and, when the pack was
    prepared again, a comment carrying the new list."""
    mark = c.marker(week["week"])
    ops = [{"id": "w0-task", "op": "create", "title": f"Approve the weekly review for {week['week']}",
            "description": task_text(items, week["week"], mark)[:3800], "due_date": week["next_monday"],
            "priority": 2, "source": f"weekly-review:{week['week']}",
            "reason": f"The weekly review {week['week']} waits on the owner's answers",
            **({"project": project} if project else {"domain": domain})}]
    if replaced and published and published.get("task"):
        body = ("The pack was prepared again; this list replaces the one above.\n\n"
                + "\n".join(c.approval_list(items)))[:3600]
        ops.append({"id": "w0-relist", "op": "comment", "task": published["task"], "body": body,
                    "reason": f"The weekly review {week['week']} was prepared again"})
    return ops


def pack_publish(run, passed, dry, client, project, domain, config, server):
    items, problems, text = build_pack(run)
    if problems:
        raise c.Refuse(f"the review does not validate ({len(problems)} problem(s), first: {problems[0]})")
    week, folder = passed["week"], Path(passed["week_dir"])
    published = c.maybe_json(folder / "publish.json")
    published = published if isinstance(published, dict) and not published.get("dry_run") else None
    why = c.answered_already(folder, published, client)
    if why:
        raise c.Refuse(f"the published pack for {week['week']} is already being answered ({why}); a new pack "
                       "would renumber the items under the answers")
    plan = {"week": week["week"], "items": len(items), "pack_sha": c.sha(text),
            "replaces_pack": (folder / "review.json").is_file(), "week_dir": str(folder)}
    if dry:
        return dict(plan, dry_run=True, would=["keep the pack in the week's folder",
                                               "find or create the review task through task_stack_apply.py",
                                               "find or create the private note"])
    if not (project or domain):
        raise c.Bad("the review task needs a project or domain: pass --review-project or --review-domain, or set "
                    "review_project or review_domain in [weekly-review-workstream]")
    if plan["replaces_pack"]:
        old = c.new_dir(folder, "superseded")
        for name in ("review.json", "PACK.md", "items.json", "inputs"):
            if (folder / name).exists():
                shutil.move(str(folder / name), str(old / name))
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copytree(run / "inputs", folder / "inputs")
    shutil.copyfile(run / "review.json", folder / "review.json")
    c.write_text(folder / "PACK.md", text)
    c.write_json(folder / "items.json", {"week": week["week"], "items": items})
    c.upsert_items(folder / c.items_ledger_name(week["week"]), ITEM_COLUMNS, {it["n"]: {
        "section": it["section"], "task": it.get("task") or "", "title": it["title"], "proposal": it["proposal"],
        "answer": "", "state": "proposed", "ops": "", "outcome": "", "updated_at": c.now_iso(), "by": BY}
        for it in items})
    ops = task_ops(items, week, published, plan["replaces_pack"], project, domain)
    results = c.apply_tasks(run, "publish-task", ops, config, server)
    task_ref = results["w0-task"].get("task")
    if not c.task_uuid(task_ref):
        raise c.Bad("task_stack_apply.py did not name the review task")
    task = {"ref": task_ref, "outcome": "commented" if "w0-relist" in results else
            ("created" if results["w0-task"]["outcome"] == "applied" else "found")}
    note = c.ensure_note(client, f"Weekly review {week['week']}", NOTE_TAG, text, c.marker(week["week"]),
                         (published or {}).get("note"), task["ref"])
    record = {"schema": "weekly-review/publish@1", "week": week["week"], "dry_run": False, "task": task["ref"],
              "note": note["ref"], "pack_sha": plan["pack_sha"], "items": len(items), "published_at": c.now_iso()}
    c.write_json(folder / "publish.json", record)
    c.append_log(folder, "Weekly review log", f"pack published: {len(items)} items; task {task['ref']} "
                 f"({task['outcome']}); note {note['ref']} ({note['outcome']})")
    return dict(record, task_outcome=task["outcome"], note_outcome=note["outcome"])


def approve_publish(run, passed, dry, client):
    week, folder = passed["week"], Path(passed["week_dir"])
    changes = c.read_json(run / "changes.json")
    answers = c.read_json(run / "answers-final.json")
    applied = c.maybe_json(run / ("apply-dry-run.json" if dry else "apply.json")) or {}
    results = applied.get("results") or []
    outcomes = c.item_outcomes(answers, results)
    counts = {}
    for o in outcomes.values():
        counts[o["state"]] = counts.get(o["state"], 0) + 1
    summary = {"schema": "weekly-review/applied@1", "week": week["week"], "dry_run": dry, "at": c.now_iso(),
               "apply_status": applied.get("status"), "ops": len(changes.get("ops") or []), "items": counts,
               "questions": changes.get("questions") or [],
               "review_task_closed": any(r.get("id") == "w0-close" and r.get("outcome") == "applied" for r in results)}
    if dry:
        return dict(summary, would=["keep the answers and results in the week's folder", "update each item's row",
                                    "append the outcomes to the review note"])
    keep = c.new_dir(folder, "approve")
    for name in ("changes.json", "answers-final.json", "apply.json", "undo.jsonl"):
        if (run / name).is_file():
            shutil.copyfile(run / name, keep / name)
    summary["kept"] = str(keep)
    c.write_json(folder / "applied.json", summary)
    c.upsert_items(folder / c.items_ledger_name(week["week"]), ITEM_COLUMNS, {n: {
        "answer": o["answer"], "state": o["state"], "ops": o["ops"], "outcome": o["outcome"],
        "updated_at": c.now_iso(), "by": BY} for n, o in outcomes.items()})
    published = c.read_json(folder / "publish.json")
    pack = (folder / "PACK.md").read_text(encoding="utf-8")
    content = pack.rstrip() + "\n\n" + "\n".join(c.outcome_table(outcomes, summary["questions"])) + "\n"
    note = c.ensure_note(client, f"Weekly review {week['week']}", NOTE_TAG, content, c.marker(week["week"]),
                         published.get("note"), published.get("task"))
    c.append_log(folder, "Weekly review log", f"approval applied: {c.answer_line(counts)}; apply "
                 f"{applied.get('status')}; note {note['outcome']}")
    return dict(summary, note=note["ref"])


def main(argv=None, client=None):
    p = argparse.ArgumentParser(prog="weekly_review_publish.py", description=__doc__.split("\n\n")[0])
    p.add_argument("--run", dest="run_dir", required=True, help="The Run folder")
    p.add_argument("--dry-run-if", default="", help="true or false (a scheduler placeholder)")
    p.add_argument("--review-project", default="", help="The project the review task goes in (uuid)")
    p.add_argument("--review-domain", default="", help="Else the domain whose catch-all takes it (uuid)")
    p.add_argument("--config", default="", help="MCP config holding the Portal (default: setting portal_mcp_config)")
    p.add_argument("--server", default="", help="Server name in the MCP config (default: setting portal_server)")
    args = p.parse_args(argv)
    try:
        run = c.guard_run_path(args.run_dir)
        passed = c.read_json(run / "pass.json")
        if not isinstance(passed, dict) or passed.get("schema") != c.PASS_SCHEMA:
            raise c.Bad(f"{run / 'pass.json'} is not weekly_review_gather.py's pass record")
        dry = c.truthy(args.dry_run_if)
        if client is None and not (dry and passed["pass"] == "approve"):
            client = c.Portal(args.config or None, args.server or None)
        mine = c.settings("weekly-review-workstream")
        if passed["pass"] == "pack":
            result = pack_publish(run, passed, dry, client, args.review_project.strip() or mine.get("review_project", ""),
                                  args.review_domain.strip() or mine.get("review_domain", ""),
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
    print(c.safe(json.dumps(dict(result, tool="weekly-review-publish", **{"pass": passed["pass"]}), indent=1,
                            default=str)))
    sys.exit(0)


if __name__ == "__main__":
    main()
