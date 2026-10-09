"""task_stack_apply.py: the task stack's one writer, its rules, its journal and its undo."""

import json
from datetime import timedelta

import pytest

import task_stack_apply as ap
import task_stack_report as rp
from conftest import (D_OPS, D_SALES, EMAIL, EVENT_FUTURE, EVENT_PAST, G_GROW, NOTE, NOW, OTHER, OWNER,
                      P_AUDIT, P_BUCKET, P_ROUTES, FakePortal, ago, iso, task, uid)


def changes(*ops, dry_run=False, questions=None, orchestrator="task-reconcile-orchestrator"):
    return {"tool": "task-stack-changes", "version": 1, "orchestrator": orchestrator,
            "dry_run": dry_run, "ops": list(ops), "questions": questions or []}


def run(portal, data, tmp_path, dry_run=False, **kw):
    return ap.apply(portal, data, dry_run, tmp_path / "state", tmp_path / "undo.jsonl", now=NOW, **kw)


def by_id(result):
    return {r["id"]: r for r in result["results"]}


def complete(n, evidence=f"portal://email/{EMAIL}", op_id="c1"):
    return {"id": op_id, "op": "complete", "task": f"portal://task/{uid(n)}", "evidence": evidence,
            "reason": "Sent the new rate card"}


# --------------------------------------------------------------------------- complete and markers

def test_complete_comments_with_evidence_then_closes_logs_and_journals(tmp_path):
    portal = FakePortal([task(1, "Send the rate card")])
    result = run(portal, changes(complete(1)), tmp_path)
    r = by_id(result)["c1"]
    assert result["status"] == "applied" and r["outcome"] == "applied"
    assert portal.tasks[uid(1)]["status"] == "DONE"
    body = portal.comments[uid(1)][0]["body"]
    assert "Completed: Sent the new rate card" in body and f"portal://email/{EMAIL}" in body and r["marker"] in body
    log = [json.loads(x) for x in (tmp_path / "undo.jsonl").read_text().splitlines()]
    assert log[0]["before"] == {"status": "TODO"} and log[0]["after"] == {"status": "DONE"}
    assert (tmp_path / "state" / "writes.jsonl").is_file()


def test_a_rerun_writes_nothing_twice(tmp_path):
    portal = FakePortal([task(1, "Send the rate card")])
    run(portal, changes(complete(1)), tmp_path)
    count = len(portal.writes())
    again = by_id(run(portal, changes(complete(1, op_id="other-id")), tmp_path))["other-id"]
    assert again["outcome"] == "unchanged" and len(portal.writes()) == count


def test_marker_is_the_content_not_the_op_id_or_reason():
    a = ap.marker_for("x-orchestrator", dict(complete(1), id="a", reason="one"))
    b = ap.marker_for("x-orchestrator", dict(complete(1), id="b", reason="two"))
    assert a == b and a.startswith("tsk") and len(a) == 15
    assert a != ap.marker_for("y-orchestrator", complete(1))
    assert ap.source_marker("quick-capture:abc") == ap.marker_for(
        "any-orchestrator", {"op": "create", "title": "Call Sam", "source": "quick-capture:abc"})


@pytest.mark.parametrize("evidence,code", [
    (f"portal://email/{uid(555)}", "EVIDENCE"),             # does not exist
    (f"portal://calendar_event/{EVENT_FUTURE}", "EVIDENCE"),  # has not happened
])
def test_complete_without_good_evidence_is_refused(tmp_path, evidence, code):
    portal = FakePortal([task(1, "Send the rate card")])
    r = by_id(run(portal, changes(complete(1, evidence)), tmp_path))["c1"]
    assert (r["outcome"], r["code"]) == ("refused", code) and portal.writes() == []


def test_evidence_kinds_that_hold(tmp_path):
    portal = FakePortal([task(i, f"Send pack {i}") for i in (1, 2, 3, 4)])
    result = by_id(run(portal, changes(
        complete(1, f"portal://email/{EMAIL}", "a"), complete(2, f"portal://note/{NOTE}", "b"),
        complete(3, f"portal://calendar_event/{EVENT_PAST}", "c"),
        complete(4, "https://example.com/acme/repo/pull/7", "d")), tmp_path))
    assert {r["outcome"] for r in result.values()} == {"applied"}


def test_a_closed_task_or_another_persons_task_is_not_touched(tmp_path):
    portal = FakePortal([task(1, "Send pack", status="DONE"), task(2, "Send pack", owner_contact_id=OTHER),
                         task(3, "Send pack", status="CANCELLED")])
    result = by_id(run(portal, changes(complete(2, op_id="b"), complete(3, op_id="c")), tmp_path))
    assert result["b"]["code"] == "NOT_OWNER" and result["c"]["code"] == "CLOSED"
    assert portal.writes() == []


# --------------------------------------------------------------------------- the set and dry runs

def test_dry_run_writes_nothing_anywhere(tmp_path):
    portal = FakePortal([task(1, "Send the rate card")])
    result = run(portal, changes(complete(1)), tmp_path, dry_run=True)
    assert result["status"] == "would_apply" and by_id(result)["c1"]["outcome"] == "would_apply"
    assert portal.writes() == [] and not (tmp_path / "undo.jsonl").exists()
    assert not (tmp_path / "state" / "writes.jsonl").exists()


def test_a_dry_run_change_set_is_never_applied_live(tmp_path):
    portal = FakePortal([task(1, "Send the rate card")])
    with pytest.raises(ap.Refused) as err:
        run(portal, changes(complete(1), dry_run=True), tmp_path)
    assert err.value.code == "DRY_RUN" and portal.writes() == []


@pytest.mark.parametrize("data", [
    [], {"tool": "other", "version": 1, "dry_run": False, "ops": []},
    {"tool": "task-stack-changes", "version": 2, "dry_run": False, "ops": []},
    {"tool": "task-stack-changes", "version": 1, "dry_run": "false", "ops": []},
    {"tool": "task-stack-changes", "version": 1, "dry_run": False, "ops": [{"id": "a"}, {"id": "a"}]},
])
def test_a_malformed_set_is_refused_whole(tmp_path, data):
    with pytest.raises(ap.Refused) as err:
        run(FakePortal([]), data, tmp_path)
    assert err.value.code == "INVALID_SET"


def test_an_op_needs_a_reason_and_a_producer(tmp_path):
    portal = FakePortal([task(1, "Send the rate card")])
    data = changes(dict(complete(1), reason=""), orchestrator=None)
    data["ops"].append(dict(complete(1), id="c2"))
    result = by_id(run(portal, data, tmp_path))
    assert "reason is required" in result["c1"]["reason"]
    assert result["c2"]["code"] == "INVALID_OP" and "producing orchestrator" in result["c2"]["reason"]


def test_max_changes_defers_the_rest(tmp_path):
    portal = FakePortal([task(i, f"Send pack {i}") for i in (1, 2, 3)])
    result = by_id(run(portal, changes(*(complete(i, op_id=f"c{i}") for i in (1, 2, 3))), tmp_path, max_changes=2))
    assert [result[f"c{i}"]["outcome"] for i in (1, 2, 3)] == ["applied", "applied", "deferred"]


def test_domain_scope(tmp_path):
    portal = FakePortal([task(1, "Send pack"), task(2, "Send audit list", project_id=P_AUDIT, domain_id=D_OPS)])
    result = by_id(run(portal, changes(complete(1, op_id="a"), complete(2, op_id="b")), tmp_path,
                       domain="operations"))
    assert result["a"]["code"] == "OUT_OF_SCOPE" and result["b"]["outcome"] == "applied"


# --------------------------------------------------------------------------- hand edits

def test_a_task_changed_inside_the_window_by_someone_else_is_protected(tmp_path):
    portal = FakePortal([task(1, "Send the rate card", created=40, updated=2)])
    r = by_id(run(portal, changes(complete(1)), tmp_path))["c1"]
    assert (r["outcome"], r["code"]) == ("refused", "HAND_EDIT") and "never written" in r["reason"]


def test_never_edited_or_outside_the_window_is_free(tmp_path):
    portal = FakePortal([task(1, "Send pack", created=2, updated=2), task(2, "Send deck", created=40, updated=8)])
    result = run(portal, changes(complete(1, op_id="a"), complete(2, op_id="b")), tmp_path)
    assert {r["outcome"] for r in result["results"]} == {"applied"}


def test_the_journal_tells_its_own_writes_from_a_hand_edit(tmp_path):
    portal = FakePortal([task(1, "Send the rate card", created=40, updated=40)])
    edit = {"id": "e1", "op": "edit", "task": uid(1), "set": {"due_date": "2030-03-20"}, "reason": "promised"}
    run(portal, changes(edit), tmp_path)
    second = {"id": "e2", "op": "edit", "task": uid(1), "set": {"priority": 2}, "reason": "client asked"}
    assert by_id(run(portal, changes(second), tmp_path))["e2"]["outcome"] == "applied"
    portal.tasks[uid(1)].update(due_date="2030-04-01", updated_at=iso(NOW - timedelta(hours=3)))
    result = by_id(run(portal, changes(
        {"id": "e3", "op": "edit", "task": uid(1), "set": {"due_date": "2030-03-25"}, "reason": "x"},
        {"id": "e4", "op": "edit", "task": uid(1), "set": {"title": "Send the spring rate card"}, "reason": "y"}),
        tmp_path))
    assert result["e3"]["code"] == "HAND_EDIT" and "due_date" in result["e3"]["reason"]
    assert result["e4"]["outcome"] == "applied" and portal.tasks[uid(1)]["due_date"] == "2030-04-01"


def test_a_change_between_the_read_and_the_write_is_not_overwritten(tmp_path):
    portal = FakePortal([task(1, "Send the rate card")])
    original = portal.call

    def racing(tool, args=None):
        out = original(tool, args)
        if tool == "create_task_comment":
            portal.tasks[uid(1)]["title"] = "Send the rate card today"
        return out

    portal.call = racing
    r = by_id(run(portal, changes(complete(1)), tmp_path))["c1"]
    assert r["outcome"] == "failed" and "title changed while this ran" in r["reason"]
    assert portal.tasks[uid(1)]["status"] == "TODO"


# --------------------------------------------------------------------------- edit, merge, cancel

def test_edit_rules(tmp_path):
    portal = FakePortal([task(1, "Chase the carrier"), task(2, "Chase the bank")])
    result = by_id(run(portal, changes(
        {"id": "w1", "op": "edit", "task": uid(1), "set": {"status": "WAITING"}, "reason": "theirs"},
        {"id": "w2", "op": "edit", "task": uid(2), "set": {"status": "WAITING", "due_date": "2030-03-11"},
         "reason": "theirs"},
        {"id": "t1", "op": "edit", "task": uid(1), "set": {"title": "Carrier invoice"}, "reason": "clearer"},
        {"id": "s1", "op": "edit", "task": uid(1), "set": {"status": "DONE"}, "reason": "no"},
        {"id": "d1", "op": "edit", "task": uid(1), "set": {"description": "x"}, "reason": "no"},
        {"id": "p1", "op": "edit", "task": uid(1), "set": {"project_id": P_AUDIT, "domain_id": D_SALES},
         "reason": "file it"},
        {"id": "ok", "op": "edit", "task": uid(1), "set": {"status": "WAITING", "due_date": "2030-03-11",
                                                          "waiting_on_contact_id": OTHER}, "reason": "theirs"},
    ), tmp_path))
    assert result["w1"]["code"] == "WAITING_NO_FOLLOW_UP"
    assert result["w2"]["code"] == "WAITING_NO_PARTY"
    assert result["t1"]["code"] == "NOT_NEXT_ACTION"
    assert result["s1"]["code"] == result["d1"]["code"] == "INVALID_OP"
    assert result["p1"]["code"] == "DOMAIN_MISMATCH"
    assert result["ok"]["outcome"] == "applied" and portal.tasks[uid(1)]["status"] == "WAITING"


def test_merge_keeps_the_older_task_and_completes_the_duplicate(tmp_path):
    portal = FakePortal([task(1, "Book the van", created=60), task(2, "Book the van", created=30, due_date="2030-03-09",
                                                                     description="for the Lakeview run")])
    r = by_id(run(portal, changes({"id": "m1", "op": "merge", "task": uid(2), "into": uid(1),
                                   "reason": "same commitment"}), tmp_path))["m1"]
    assert r["outcome"] == "applied"
    assert portal.tasks[uid(2)]["status"] == "DONE" and portal.tasks[uid(1)]["due_date"] == "2030-03-09"
    assert "for the Lakeview run" in portal.comments[uid(1)][0]["body"]
    assert "Duplicate of" in portal.comments[uid(2)][0]["body"]


def test_merge_refusals(tmp_path):
    portal = FakePortal([task(1, "Book the van", created=60), task(2, "Book the van", created=30),
                         task(3, "Book the van", created=20, owner_contact_id=None)])
    result = by_id(run(portal, changes(
        {"id": "a", "op": "merge", "task": uid(1), "into": uid(2), "reason": "x"},
        {"id": "b", "op": "merge", "task": uid(3), "into": uid(1), "reason": "x"}), tmp_path))
    assert result["a"]["code"] == "KEEP_OLDER" and result["b"]["code"] == "NOT_SAME_OWNER"


def test_cancel_rules(tmp_path):
    portal = FakePortal([task(1, "Call the old supplier", updated=90), task(2, "Call the broker", updated=10),
                         task(3, "Audit the stock", project_id=P_AUDIT, domain_id=D_OPS, updated=90),
                         task(4, "Call the bank", updated=10)])
    result = by_id(run(portal, changes(
        {"id": "a", "op": "cancel", "task": uid(1), "reason": "stale", "check": "PASS"},
        {"id": "b", "op": "cancel", "task": uid(2), "reason": "stale", "check": "PASS"},
        {"id": "c", "op": "cancel", "task": uid(3), "reason": "stale", "check": "PASS"},
        {"id": "d", "op": "cancel", "task": uid(4), "reason": "overtaken", "check": "PASS",
         "evidence": f"portal://note/{NOTE}"},
        {"id": "e", "op": "cancel", "task": uid(1), "reason": "unchecked"}), tmp_path))
    assert result["a"]["outcome"] == "applied" and result["d"]["outcome"] == "applied"
    assert result["b"]["code"] == "NOT_STALE" and result["c"]["code"] == "GOAL_LINKED"


def test_a_reconcile_cancel_needs_the_checkers_pass(tmp_path):
    portal = FakePortal([task(1, "Call the old supplier", updated=90)])
    r = by_id(run(portal, changes({"id": "s1", "op": "cancel", "task": uid(1), "reason": "stale"}), tmp_path))["s1"]
    assert r["code"] == "UNCHECKED" and portal.tasks[uid(1)]["status"] == "TODO"


def test_this_script_never_deletes():
    from pathlib import Path
    text = Path(ap.__file__).read_text()
    assert "delete_" not in text and '"delete"' not in text


# --------------------------------------------------------------------------- create and comment

def test_create_files_dedupes_and_is_found_by_marker(tmp_path):
    portal = FakePortal([task(1, "Send the rate card")])
    new = {"id": "n1", "op": "create", "title": "Renew the forklift lease", "domain": D_SALES, "reason": "agreed"}
    r = by_id(run(portal, changes(new), tmp_path))["n1"]
    assert r["outcome"] == "applied"
    created = portal.tasks[r["task"].rsplit("/", 1)[1]]
    assert created["project_id"] == P_BUCKET and created["owner_contact_id"] == OWNER
    assert by_id(run(portal, changes(new), tmp_path))["n1"]["outcome"] == "unchanged"
    dup = {"id": "n2", "op": "create", "title": "Send the rate card", "project": P_ROUTES, "reason": "again"}
    noun = {"id": "n3", "op": "create", "title": "Rate card", "project": P_ROUTES, "reason": "x"}
    result = by_id(run(portal, changes(dup, noun), tmp_path))
    assert result["n2"]["code"] == "DUPLICATE" and result["n3"]["code"] == "NOT_NEXT_ACTION"


def test_a_capture_create_is_marked_by_its_source_key_alone(tmp_path):
    portal = FakePortal([])
    first = {"id": "n1", "op": "create", "title": "Call Priya about the invoice", "domain": D_SALES,
             "source": "quick-capture:a1b2", "reason": "captured"}
    r = by_id(run(portal, changes(first), tmp_path))["n1"]
    assert r["marker"] == ap.source_marker("quick-capture:a1b2")
    reworded = dict(first, title="Email Priya regarding the invoice", id="n9")
    assert by_id(run(portal, changes(reworded, orchestrator="task-capture-orchestrator"), tmp_path))["n9"][
        "outcome"] == "unchanged"


def test_source_is_shaped_and_only_on_a_create():
    assert ap.shape_problems({"id": "a", "op": "create", "title": "Call Sam", "domain": D_SALES, "reason": "x",
                              "source": "Bad Key"})
    assert ap.shape_problems(dict(complete(1), source="quick-capture:x")) == ["source belongs only on a create"]


def test_comment_once(tmp_path):
    portal = FakePortal([task(1, "Send the rate card")])
    op = {"id": "k1", "op": "comment", "task": uid(1), "body": "Sam has the draft", "reason": "note"}
    assert by_id(run(portal, changes(op), tmp_path))["k1"]["outcome"] == "applied"
    assert by_id(run(portal, changes(op), tmp_path))["k1"]["outcome"] == "unchanged"
    assert len(portal.comments[uid(1)]) == 1


def test_work_is_assigned_only_to_the_owner_or_the_assignable_list(tmp_path, no_owner_settings):
    portal = FakePortal([task(1, "Chase the carrier")])
    op = {"id": "e1", "op": "edit", "task": uid(1), "set": {"owner_contact_id": OTHER}, "reason": "hand over"}
    assert by_id(run(portal, changes(op), tmp_path))["e1"]["code"] == "NOT_ASSIGNABLE"
    no_owner_settings.write_text(f'[task-stack-workstream]\nassignable_contacts = ["{OTHER}"]\n')
    assert by_id(run(portal, changes(op), tmp_path))["e1"]["outcome"] == "applied"


# --------------------------------------------------------------------------- projects and goals

def test_project_edit_links_a_goal_and_refuses_a_bucket(tmp_path):
    portal = FakePortal([task(1, "Plan the routes")])
    result = by_id(run(portal, changes(
        {"id": "p1", "op": "project_edit", "project": f"portal://project/{P_ROUTES}", "set": {"goal_id": G_GROW},
         "reason": "serves growth"},
        {"id": "p2", "op": "project_edit", "project": P_BUCKET, "set": {"priority": 2}, "reason": "x"}), tmp_path))
    assert result["p1"]["code"] == "DOMAIN_MISMATCH"   # the goal is in another domain
    assert result["p2"]["code"] == "BUCKET"
    portal.goals[G_GROW]["domain_id"] = D_SALES
    again = by_id(run(portal, changes({"id": "p3", "op": "project_edit", "project": P_ROUTES,
                                       "set": {"goal_id": G_GROW}, "reason": "serves growth"}), tmp_path))["p3"]
    assert again["outcome"] == "applied" and portal.projects[P_ROUTES]["goal_id"] == G_GROW


def test_close_a_dead_project_after_cancelling_its_last_task_in_the_same_set(tmp_path):
    portal = FakePortal([task(1, "Plan the routes", created=200, updated=200)])
    result = by_id(run(portal, changes(
        {"id": "x1", "op": "cancel", "task": uid(1), "reason": "dead", "check": "PASS"},
        {"id": "pc", "op": "project_close", "project": P_ROUTES, "reason": "nothing left"}), tmp_path))
    assert result["x1"]["outcome"] == "applied" and result["pc"]["outcome"] == "applied"
    assert portal.projects[P_ROUTES]["status"] == "CANCELLED"


def test_project_close_refusals(tmp_path):
    portal = FakePortal([task(1, "Plan the routes", updated=5), task(2, "Audit stock", project_id=P_AUDIT,
                                                                      domain_id=D_OPS, status="DONE")])
    result = by_id(run(portal, changes(
        {"id": "a", "op": "project_close", "project": P_ROUTES, "reason": "x"},
        {"id": "b", "op": "project_close", "project": P_AUDIT, "reason": "x"}), tmp_path))
    assert result["a"]["code"] == "OPEN_TASKS" and result["b"]["code"] == "GOAL_LINKED"


def test_goal_edit_and_close(tmp_path):
    portal = FakePortal([])
    result = by_id(run(portal, changes(
        {"id": "g1", "op": "goal_edit", "goal": f"portal://goal/{G_GROW}", "set": {"priority": 1}, "reason": "up"},
        {"id": "g2", "op": "goal_close", "goal": G_GROW, "status": "CANCELLED", "reason": "retired"}), tmp_path))
    assert result["g1"]["outcome"] == "applied" and portal.goals[G_GROW]["priority"] == "P1"
    assert result["g2"]["code"] == "ACTIVE_PROJECTS"
    closing = by_id(run(portal, changes(
        {"id": "p", "op": "project_close", "project": P_AUDIT, "status": "COMPLETED",
         "evidence": f"portal://note/{NOTE}", "reason": "done"},
        {"id": "g3", "op": "goal_close", "goal": G_GROW, "status": "CANCELLED", "reason": "retired"}), tmp_path))
    assert closing["g3"]["outcome"] == "applied" and portal.goals[G_GROW]["status"] == "CANCELLED"


# --------------------------------------------------------------------------- undo and the command line

def test_undo_puts_old_values_back_and_keeps_later_changes(tmp_path):
    portal = FakePortal([task(1, "Send the rate card"), task(2, "Send the deck")])
    run(portal, changes(complete(1, op_id="a"),
                        {"id": "b", "op": "edit", "task": uid(2), "set": {"due_date": "2030-03-20"}, "reason": "x"}),
        tmp_path)
    portal.tasks[uid(2)]["due_date"] = "2030-05-01"
    rows = ap.read_jsonl(tmp_path / "undo.jsonl")
    result = ap.undo(portal, rows, False, tmp_path / "state", now=NOW)
    outcomes = {r["op_id"]: r["outcome"] for r in result["results"]}
    assert outcomes == {"a": "undone", "b": "refused"}
    assert portal.tasks[uid(1)]["status"] == "TODO" and portal.tasks[uid(2)]["due_date"] == "2030-05-01"


def test_cli_run_folder_dry_run_if_report_and_undo(tmp_path, capsys):
    portal = FakePortal([task(1, "Send the rate card", created=300, updated=300)])
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "changes.json").write_text(json.dumps(changes(complete(1), questions=[
        {"ask": "Merge the two freight tasks?", "task": f"portal://task/{uid(1)}", "why": "titles differ"}])))
    state = str(tmp_path / "state")

    def cli(*argv):
        with pytest.raises(SystemExit) as done:
            ap.main(list(argv), client=portal)
        return done.value.code, capsys.readouterr().out

    code, _ = cli("--run", str(run_dir), "--dry-run-if=maybe", "--state", state)
    assert code == 2 and portal.writes() == []
    code, out = cli("--run", str(run_dir), "--dry-run-if=True", "--state", state)
    assert code == 0 and json.loads(out)["status"] == "would_apply" and portal.writes() == []
    assert (run_dir / "apply-dry-run.json").is_file() and not (run_dir / "undo.jsonl").exists()
    (run_dir / "apply-dry-run.json").unlink()
    code, out = cli("--run", str(run_dir), "--state", state)
    assert code == 0 and json.loads((run_dir / "apply.json").read_text())["status"] == "applied"
    assert portal.tasks[uid(1)]["status"] == "DONE"

    with pytest.raises(SystemExit) as done:
        rp.main(["--run", str(run_dir)])
    assert done.value.code == 0
    out = capsys.readouterr().out
    assert out.startswith("REPORT: 1 applied; missing before.json, after.json")
    text = (run_dir / "REPORT.md").read_text()
    assert "Merge the two freight tasks?" in text and "--undo" in text

    code, _ = cli("--undo", str(run_dir / "undo.jsonl"), "--state", state)
    assert code == 0 and portal.tasks[uid(1)]["status"] == "TODO"


def test_cli_needs_a_state_folder(tmp_path, capsys):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "changes.json").write_text(json.dumps(changes()))
    with pytest.raises(SystemExit) as done:
        ap.main(["--run", str(run_dir)], client=FakePortal([]))
    assert done.value.code == 2 and "state_dir" in capsys.readouterr().out


def test_cli_state_folder_from_the_setting(tmp_path, capsys, no_owner_settings):
    no_owner_settings.write_text(f'state_dir = "{tmp_path / "st"}"\n')
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "changes.json").write_text(json.dumps(changes(complete(1))))
    with pytest.raises(SystemExit) as done:
        ap.main(["--run", str(run_dir)], client=FakePortal([task(1, "Send the rate card")]))
    assert done.value.code == 0 and (tmp_path / "st" / "task-stack" / "writes.jsonl").is_file()


def test_markers_are_pinned_so_earlier_writes_are_found_again():
    # The same values the earlier writer produced: a changed formula would re-create every
    # captured task and re-post every comment already in the Portal.
    assert ap.source_marker("inbox:abc123") == "tska76da721302c"
    op = {"id": "c1", "op": "complete", "task": f"portal://task/{uid(1)}", "evidence": f"portal://email/{EMAIL}",
          "reason": "Sent the new rate card"}
    assert ap.marker_for("task-reconcile-orchestrator", op) == PINNED_COMPLETE


PINNED_COMPLETE = "tsk1ccc57820952"   # computed by the earlier writer on the same op
