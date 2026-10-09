"""goal_alignment_gather.py, goal_alignment_pack.py and goal_alignment_check.py, on invented data."""

import json
from datetime import date

import pytest

import _common as c
import goal_alignment_check as chk
import goal_alignment_gather as ga
import goal_alignment_pack as pk
from conftest import CORPUS, G_SALES, P_OLD, RULES, TODAY, FakePortal, uid

STACK = {"tool": "task-stack-check", "as_of": TODAY,
         "overall": {"score": 74.0, "components": {"goals": {"flagged": 1}, "projects": {"flagged": 1}}},
         "findings": {"goals": [{"ref": f"portal://goal/{G_SALES}"}], "projects": []}}


def review(**kw):
    out = {"schema": c.REVIEW_SCHEMA, "month": "2030-02", "cadence": "monthly", "dry_run": False,
           "summary": ["Fleet took the month."], "notes": {"time": "Coverage was thin."},
           "pulse": [{"domain": "Family", "goal": "Family 1", "title": "Weekends", "status": "on track",
                      "line": "Kept every Saturday."}],
           "items": [
               {"section": "goals", "goal": f"portal://goal/{G_SALES}", "title": "Win two carriers: no project",
                "proposal": "Park the goal until April", "default": "park", "options": {}},
               {"section": "stop", "project": f"portal://project/{P_OLD}", "title": "Old depot study",
                "proposal": "Close it", "default": "close",
                "options": {"close": [{"op": "project_close", "project": f"portal://project/{P_OLD}",
                                       "status": "CANCELLED"}]}},
               {"section": "map", "map": {"goal": f"portal://goal/{uid(600)}", "telos": "Business 2"},
                "title": "Cut empty miles serves Business 2", "proposal": "Record the mapping",
                "options": {"ok": []}}]}
    out.update(kw)
    return out


def test_resolve_month_and_cadence_rotation(tmp_path):
    mo = c.resolve_month("", date(2030, 3, 2))
    assert mo["month"] == "2030-02" and mo["last"] == "2030-02-28" and mo["run_month"] == "2030-03"
    rules = tmp_path / "RULES.md"
    rules.write_text(RULES)
    settings = c.read_settings(rules)
    assert settings["starved hours"] == "4" and "ignored" not in settings
    cad = c.resolve_cadence(mo, settings)
    assert cad["cadence"] == "monthly" and cad["pulse_domains"] == ["Business", "Health"]
    assert cad["readable"] == ["Business"] and cad["owner_only"] == ["Health"]
    assert c.resolve_cadence(c.resolve_month("2030-03"), settings, "monthly")["pulse_domains"] == ["Family"]
    cad = c.resolve_cadence(c.resolve_month("2030-03"), settings)
    assert cad["cadence"] == "quarterly" and cad["pulse_domains"] == ["Business", "Health", "Family"]


def test_validate_adds_park_checks_maps_and_ops():
    items, problems = c.validate_review(review(), "2030-02")
    assert problems == []
    assert items[0]["options"]["park"][0] == {"op": "goal_edit", "goal": f"portal://goal/{G_SALES}",
                                             "set": {"status": "DEFERRED"}, "id": "a1-park-1",
                                             "reason": "Parked in the goal alignment for 2030-02; the owner approved it"}
    assert items[1]["options"]["park"][0]["set"] == {"status": "ON_HOLD"}
    assert "park" not in items[2]["options"]
    bad = review(cadence="quarterly")
    bad["items"][2]["map"] = {"goal": "nope"}
    _, problems = c.validate_review(bad, "2030-02")
    assert any("quarterly template" in p for p in problems) and any("map.goal" in p for p in problems)


def test_answers_record_mappings():
    items, _ = c.validate_review(review(), "2030-02")
    got = c.resolve(items, [{"source": "x", "text": "1) hold 2) retire 3) ok"}])
    assert [r["state"] for r in got["items"]] == ["approved", "approved", "recorded"]
    assert got["maps"] == [{"goal": f"portal://goal/{uid(600)}", "telos": "Business 2", "item": 3}]


def test_read_time_and_derive(time_home):
    mo = c.resolve_month("2030-02")
    time = ga.read_time(str(time_home), mo)
    assert time["days_covered"] == 2 and time["work_hours"] == 16 and time["topics"][0]["label"] == "Routing"
    out = ga.derive(CORPUS, mo, time, date.fromisoformat(TODAY), {"goals": {uid(600): {"telos": "Business 2"}}})
    goals = {g["title"]: g for g in out["goals"]["goals"]}
    assert not goals["Cut empty miles"]["no_project"]  # served through its sub-goal's project
    assert goals["Win two carriers"]["no_project"] and goals["Win two carriers"]["starved"]
    old = next(p for p in out["projects"]["projects"] if p["name"] == "Old depot study")
    assert old["stop_candidate"] and old["candidate_goals"][0]["title"] == "Win two carriers"
    assert [u["name"] for u in out["domains"]["unserved"]] == ["Research"]
    assert [m["goal"] for m in out["goalmap"]["mapped"]] == [f"portal://goal/{uid(600)}"]
    assert ga.read_time("", mo)["present"] is False


def gather(tmp_path, monkeypatch, *extra):
    monkeypatch.setattr(c, "stack_check", lambda out, *a, **k: (out.write_text(json.dumps(STACK)), STACK)[1])
    run = tmp_path / "run"
    with pytest.raises(SystemExit) as stop:
        ga.main(["2030-02", "--run", str(run), "--as-of", TODAY, *extra], client=FakePortal())
    return run, stop.value.code


def test_gather_needs_the_rules_file(home, tmp_path, monkeypatch, capsys):
    _, code = gather(tmp_path, monkeypatch)
    assert code == 2 and "rules_file" in capsys.readouterr().err


def test_gather_pack_pack_and_check(home, tmp_path, monkeypatch, capsys, time_home):
    rules = tmp_path / "RULES.md"
    rules.write_text(RULES)
    run, code = gather(tmp_path, monkeypatch, "--rules", str(rules), "--time-home", str(time_home))
    assert code == 0 and capsys.readouterr().out.startswith("PACK: 2030-02 (monthly): 3 active goals (1 with no project, 1 starved")
    assert json.loads((run / "inputs" / "stack.json").read_text())["score"] == 74.0
    assert not (run / "inputs" / "stack-full.json").exists()
    (run / "review.json").write_text(json.dumps(review()))
    with pytest.raises(SystemExit) as stop:
        pk.main([str(run)])
    assert stop.value.code == 0 and capsys.readouterr().out.startswith("VALID: 3 items")
    note = (run / "NOTE.md").read_text()
    assert "1. [Goals with no active project] Win two carriers: no project" in note and "(park | no)" in note

    month = c.month_dir(home, "2030-02")
    (month / "inputs").mkdir(parents=True)
    for f in (run / "inputs").iterdir():
        (month / "inputs" / f.name).write_text(f.read_text())
    for name in ("review.json", "NOTE.md"):
        (month / name).write_text((run / name).read_text())
    (month / "publish.json").write_text(json.dumps({"task": f"portal://task/{uid(1)}", "note": "portal://note/n",
                                                    "visibility": "PRIVATE"}))
    (month / "ANSWERS.md").write_text("rest ok")
    kept = month / "approve-1"
    kept.mkdir()
    (kept / "changes.json").write_text(json.dumps({"ops": [{"id": "a1-park-1"}]}))
    (month / "applied.json").write_text(json.dumps({"apply_status": "applied", "kept": str(kept)}))
    result = chk.check("2030-02", as_of=TODAY)
    assert result["tests"]["answered"]["met"] and not result["done"]
    assert "1 approved mapping(s) not in goal-map.json" in result["tests"]["applied"]["gaps"]
    (home / c.GOAL_MAP).write_text(json.dumps({"goals": {uid(600): {"telos": "Business 2"}}}))
    (kept / "changes.json").write_text(json.dumps({"ops": [{"id": "a1-park-1"}, {"id": "a2-close-1"}]}))
    assert chk.check("2030-02", as_of=TODAY)["done"]


def test_pack_refuses_a_cadence_the_gather_did_not_choose(home, tmp_path, monkeypatch, capsys):
    rules = tmp_path / "RULES.md"
    rules.write_text(RULES)
    run, _ = gather(tmp_path, monkeypatch, "--rules", str(rules))
    capsys.readouterr()
    q = review(cadence="quarterly", quarterly={"balance": ["Fleet heavy"]})
    (run / "review.json").write_text(json.dumps(q))
    with pytest.raises(SystemExit) as stop:
        pk.main([str(run)])
    assert stop.value.code == 1 and "this Run is monthly" in capsys.readouterr().out


def test_check_precheck_without_a_published_note(home):
    result = chk.check("2030-02", as_of=TODAY)
    assert chk.precheck_line(result) == "WORK: no published goal alignment for 2030-02"
    assert chk.precheck_line(result, "approve") == "NOTHING: no published goal alignment for 2030-02 to approve"
