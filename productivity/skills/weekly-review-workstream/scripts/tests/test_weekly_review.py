"""weekly_review_gather.py, weekly_review_pack.py and weekly_review_check.py, on invented data."""

import json
from datetime import date

import pytest

import _common as c
import weekly_review_check as chk
import weekly_review_gather as ga
import weekly_review_pack as pk
from conftest import CORPUS, OWNER, STACK, TODAY, FakePortal, uid

TASK = f"portal://task/{uid(3)}"


def review(**kw):
    out = {"schema": c.REVIEW_SCHEMA, "week": "2030-W10", "dry_run": False, "summary": ["A quiet week."],
           "notes": {"overdue": "One old sign task."}, "reflection": "What would make next week lighter?",
           "items": [
               {"section": "overdue", "task": TASK, "task_title": "Draft the window sign",
                "title": "Draft the window sign", "proposal": "Move the due date to 2030-03-15", "default": "ok",
                "options": {"ok": [{"op": "edit", "task": TASK, "set": {"due_date": "2030-03-15"}}],
                            "done": [{"op": "complete", "task": TASK, "evidence": f"portal://email/{uid(500)}"}]}},
               {"section": "decisions", "title": "Supplier review has no next action",
                "proposal": "Choose a or b", "default": "a", "choices": {"a": "Add a next action", "b": "Park it"},
                "options": {"a": [{"op": "create", "title": "Draft the supplier list", "project": uid(701)}],
                            "b": []}}]}
    out.update(kw)
    return out


def test_resolve_week_defaults_to_the_latest_friday():
    wk = c.resolve_week("", date(2030, 3, 10))
    assert wk["week"] == "2030-W10" and wk["friday"] == "2030-03-08" and wk["previous"] == "2030-W09"
    assert c.resolve_week("2030-03-04")["week"] == "2030-W10"
    with pytest.raises(c.Bad):
        c.resolve_week("next week")


def test_validate_numbers_items_fills_ids_and_adds_park():
    items, problems = c.validate_review(review(), "2030-W10")
    assert problems == []
    assert [it["n"] for it in items] == [1, 2]
    assert items[0]["options"]["ok"][0]["id"] == "w1-ok-1"
    park = items[0]["options"]["park"][0]
    assert park["set"]["title"] == "[Someday] Draft the window sign" and park["set"]["due_date"] is None
    assert "park" not in items[1]["options"]


def test_validate_refuses_bad_ops_and_contract_breaks():
    bad = review(week="2030-W11")
    bad["items"][0]["options"]["ok"] = [{"op": "delete", "task": TASK}]
    bad["items"][1]["options"]["no"] = []
    _, problems = c.validate_review(bad, "2030-W10")
    text = "\n".join(problems)
    assert "week is '2030-W11'" in text and "op must be one of" in text and "'no' is always offered" in text


def test_answers_resolve_to_states_and_ops():
    items, _ = c.validate_review(review(), "2030-W10")
    got = c.resolve(items, [{"source": "a", "text": "1) park"}, {"source": "b", "text": "1) ok\n2) b"}])
    assert [r["state"] for r in got["items"]] == ["approved", "recorded"]
    assert [op["id"] for op in got["ops"]] == ["w1-ok-1"]
    got = c.resolve(items, [{"source": "a", "text": "1) ok but Friday, rest no"}])
    assert [r["state"] for r in got["items"]] == ["modified", "declined"]
    assert c.parse_answers("4-6) ok")[0] == {4: "ok", 5: "ok", 6: "ok"}


def test_derive_projects_waiting_and_someday():
    out = ga.derive(CORPUS, OWNER, date.fromisoformat(TODAY), c.resolve_week("2030-W10"))
    gaps = {p["name"]: p["gap"] for p in out["projects"]["projects"]}
    assert gaps == {"Spring store reset": None, "Supplier review": None, "Shelf order": "only WAITING tasks"}
    assert out["waiting"]["counts"]["follow_up_overdue"] == 1
    sign = next(t for t in out["tasks"]["tasks"] if t["title"] == "Draft the window sign")
    assert sign["someday_candidate"] and sign["queued"]
    assert all(t["title"] != "Review the lease" for t in out["tasks"]["tasks"])  # another person's task


def gather(home, tmp_path, monkeypatch, *extra):
    monkeypatch.setattr(c, "stack_check", lambda out, *a, **k: (out.write_text(json.dumps(STACK)), STACK)[1])
    monkeypatch.setattr(ga, "calendar", lambda *a: {"error": "no calendar in tests"})
    run = tmp_path / "run"
    with pytest.raises(SystemExit) as stop:
        ga.main(["2030-W10", "--run", str(run), "--as-of", TODAY, *extra], client=FakePortal())
    return run, stop.value.code


def test_gather_pack_pass_writes_the_inputs(home, tmp_path, monkeypatch, capsys):
    run, code = gather(home, tmp_path, monkeypatch)
    assert code == 0
    assert capsys.readouterr().out.startswith("PACK: 2030-W10: trust score 81.5 (no earlier score)")
    for name in ("stack", "projects", "waiting", "tasks", "calendar", "said", "cadence", "carried"):
        assert (run / "inputs" / f"{name}.json").is_file()
    assert json.loads((run / "pass.json").read_text())["pass"] == "pack"


def test_gather_needs_the_state_dir_setting(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "none.toml"))
    with pytest.raises(SystemExit) as stop:
        ga.main(["--run", str(tmp_path / "run")], client=FakePortal())
    assert stop.value.code == 2 and "state_dir" in capsys.readouterr().err


def test_pack_then_check_through_publish_answers_and_apply(home, tmp_path, monkeypatch, capsys):
    run, _ = gather(home, tmp_path, monkeypatch)
    capsys.readouterr()
    (run / "review.json").write_text(json.dumps(review()))
    with pytest.raises(SystemExit) as stop:
        pk.main([str(run)])
    assert stop.value.code == 0 and capsys.readouterr().out.startswith("VALID: 2 items")
    pack = (run / "PACK.md").read_text()
    assert "1. [Overdue and stale] Draft the window sign" in pack and "(ok | park | done | no)" in pack

    week = c.week_dir(home, "2030-W10")
    (week / "inputs").mkdir(parents=True)
    for f in (run / "inputs").iterdir():
        (week / "inputs" / f.name).write_text(f.read_text())
    for name in ("review.json", "PACK.md"):
        (week / name).write_text((run / name).read_text())
    result = chk.check("2030-W10", as_of=TODAY)
    assert result["tests"]["pack"]["met"] and not result["tests"]["published"]["met"]
    assert chk.precheck_line(result) == "WORK: no published pack for 2030-W10"

    (week / "publish.json").write_text(json.dumps({"task": f"portal://task/{uid(1)}", "note": "portal://note/x"}))
    (week / "ANSWERS.md").write_text("1) ok 2) b")
    result = chk.check("2030-W10", as_of=TODAY)
    assert result["tests"]["answered"]["met"]
    assert chk.precheck_line(result, "approve").startswith("WORK: 2 answered item(s)")

    kept = week / "approve-1"
    kept.mkdir()
    (kept / "changes.json").write_text(json.dumps({"ops": [{"id": "w1-ok-1"}]}))
    (week / "applied.json").write_text(json.dumps({"apply_status": "applied", "kept": str(kept)}))
    result = chk.check("2030-W10", as_of=TODAY)
    assert result["done"] and chk.precheck_line(result, "approve") == "NOTHING: the review for 2030-W10 is applied"


def test_pack_reports_an_invalid_review(home, tmp_path, monkeypatch, capsys):
    run, _ = gather(home, tmp_path, monkeypatch)
    (run / "review.json").write_text(json.dumps(review(summary=[])))
    with pytest.raises(SystemExit) as stop:
        pk.main([str(run)])
    assert stop.value.code == 1 and "summary must be a non-empty list" in capsys.readouterr().out
    assert not (run / "PACK.md").exists()


def test_approve_pass_reads_comments_and_carries_the_ledger(home, tmp_path, monkeypatch, capsys):
    week = c.week_dir(home, "2030-W10")
    week.mkdir(parents=True)
    (week / "review.json").write_text(json.dumps(review()))
    (week / "publish.json").write_text(json.dumps({"task": f"portal://task/{uid(1)}", "note": "portal://note/x"}))
    portal = FakePortal(comments={uid(1): [{"id": "k1", "body": "1) done 2) a", "created_at": "2030-03-08"},
                                           {"id": "k2", "body": "2) b (posted by Priya, an agent)"}]})
    run = tmp_path / "run2"
    with pytest.raises(SystemExit) as stop:
        ga.main(["2030-W10", "--run", str(run), "--as-of", TODAY], client=portal)
    assert stop.value.code == 0 and "APPROVE: 2030-W10: 2 items; 2 approved" in capsys.readouterr().out
    answers = json.loads((run / "answers.json").read_text())
    assert [op["id"] for op in answers["ops"]] == ["w1-done-1", "w2-a-1"]

    prev = c.week_dir(home, "2030-W09")
    prev.mkdir(parents=True)
    (prev / c.items_ledger_name("2030-W09")).write_text(
        "﻿id,section,task,title,proposal,answer,state\n1,overdue,,Old,Move,,unanswered\n2,said,,Done,Ok,ok,applied\n")
    assert [r["id"] for r in ga.carried(home, c.resolve_week("2030-W10"))["items"]] == ["1"]


def test_shape_copy_matches_the_writer_on_goal_and_project_ops():
    assert c.shape_problems({"id": "a", "op": "goal_close", "goal": uid(1), "status": "ACHIEVED", "reason": "r"}) \
        == ["goal_close to ACHIEVED needs evidence that the goal was met"]
    assert c.shape_problems({"id": "a", "op": "project_edit", "project": uid(1), "reason": "r",
                             "set": {"status": "ON_HOLD"}}) == []


def test_calendar_and_score_come_from_the_owning_skills_scripts(tmp_path, monkeypatch):
    cal = tmp_path / "calendar_time.py"
    items = [{"day": "2030-03-11", "start_local": "2030-03-11T09:00", "end_local": "2030-03-11T10:00",
              "title": "Stand-up", "hours": 1},
             {"day": "2030-03-11", "start_local": "2030-03-11T09:30", "end_local": "2030-03-11T11:00",
              "title": "Vendor call", "hours": 1.5}]
    res = {"period": {}, "totals": {"hours_union": 2.0}, "in_scope": {"meetings": 2, "by_day": {}, "items": items}}
    cal.write_text(f"import json, sys\nassert '--json' in sys.argv\nprint(json.dumps({res!r}))\n")
    monkeypatch.setattr(ga, "CALENDAR_TIME", cal)
    out = ga.calendar(c.resolve_week("2030-W10"))
    assert out["meetings"] == 2 and out["conflicts"][0]["minutes"] == 30
    monkeypatch.setattr(ga, "CALENDAR_TIME", tmp_path / "missing.py")
    assert "error" in ga.calendar(c.resolve_week("2030-W10"))

    check = tmp_path / "task_stack_check.py"
    check.write_text("import json, sys\nout = sys.argv[sys.argv.index('--out') + 1]\n"
                     f"open(out, 'w').write(json.dumps({STACK!r}))\n")
    monkeypatch.setattr(c, "TASK_STACK_CHECK", check)
    assert c.stack_check(tmp_path / "s.json", TODAY)["overall"]["score"] == 81.5
    check.write_text("print('STALE: the Portal could not be read')\n")
    with pytest.raises(c.PortalError, match="STALE"):
        c.stack_check(tmp_path / "t.json", TODAY)
