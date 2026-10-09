"""weekly_review_changes.py and weekly_review_publish.py on invented data, with an in-memory
Portal for the note and a fake task_stack_apply.py that records what it was asked to write."""

import json

import pytest

import _common as c
import weekly_review_changes as wc
import weekly_review_check as chk
import weekly_review_gather as ga
import weekly_review_pack as pk
import weekly_review_publish as wp
from conftest import STACK, TODAY, FakePortal, uid
from test_weekly_review import review

PROJECT, NEW_TASK = uid(700), uid(77)


class NotePortal(FakePortal):
    """FakePortal plus the note calls the publish step makes."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.notes = {}

    def call(self, tool, args=None):
        args = args or {}
        if tool == "search":
            return {"notes": [{"id": i} for i, n in self.notes.items() if args["query"] in n["content"]]}
        if tool == "get" and args.get("entity_type") == "note":
            return {"note": dict(self.notes.get(args["id_or_query"], {}))}
        if tool == "create_note":
            nid = uid(500 + len(self.notes))
            self.notes[nid] = {"id": nid, "content": args["content"], "visibility": "TEAM", "args": args}
            return {"note": {"id": nid}}
        if tool == "update_note":
            self.notes[args["id"]].update(args["fields"])
            return {"ok": True}
        return super().call(tool, args)


@pytest.fixture
def fake_apply(tmp_path, monkeypatch):
    """A task_stack_apply.py that applies every op and logs each change set it was given."""
    log = tmp_path / "apply-log.jsonl"
    script = tmp_path / "task_stack_apply.py"
    script.write_text(
        "import json, sys\nch = json.load(open(sys.argv[1]))\nopen(%r, 'a').write(json.dumps(ch) + '\\n')\n"
        "res = [dict(id=o['id'], op=o['op'], outcome='applied', **({'task': 'portal://task/%s'} if o['op'] == 'create' "
        "else {})) for o in ch['ops']]\nprint(json.dumps({'status': 'applied', 'results': res}))\n" % (str(log), NEW_TASK))
    monkeypatch.setattr(c, "TASK_STACK_APPLY", script)
    return log


def code_of(fn, argv, **kw):
    with pytest.raises(SystemExit) as stop:
        fn(argv, **kw)
    return stop.value.code


def packed_run(home, tmp_path, monkeypatch):
    monkeypatch.setattr(c, "stack_check", lambda out, *a, **k: (out.write_text(json.dumps(STACK)), STACK)[1])
    monkeypatch.setattr(ga, "calendar", lambda *a: {"error": "no calendar in tests"})
    run = tmp_path / "run"
    assert code_of(ga.main, ["2030-W10", "--run", str(run), "--as-of", TODAY], client=FakePortal()) == 0
    (run / "review.json").write_text(json.dumps(review()))
    assert code_of(pk.main, [str(run)]) == 0
    return run


def test_publish_answer_change_and_apply_through_to_done(home, tmp_path, monkeypatch, capsys, fake_apply):
    run = packed_run(home, tmp_path, monkeypatch)
    portal = NotePortal()
    assert code_of(wp.main, ["--run", str(run), "--review-project", PROJECT], client=portal) == 0
    week = c.week_dir(home, "2030-W10")
    published = json.loads((week / "publish.json").read_text())
    assert published["task"] == f"portal://task/{NEW_TASK}"
    note = portal.notes[c.task_uuid(published["note"])]
    assert note["visibility"] == "PRIVATE" and c.marker("2030-W10") in note["content"]
    assert note["args"]["associations"][0] == {"entity_type": "task", "entity_id": NEW_TASK, "is_primary": True}
    create = json.loads(fake_apply.read_text().splitlines()[0])["ops"][0]
    assert create["op"] == "create" and create["source"] == "weekly-review:2030-W10" and create["project"] == PROJECT
    assert create["due_date"] == "2030-03-11" and "1. [Overdue and stale]" in create["description"]
    assert chk.check("2030-W10", as_of=TODAY)["tests"]["published"]["met"]

    capsys.readouterr()
    assert code_of(wc.main, ["--run", str(run)], client=portal) == 1     # the pack Run, now published
    assert "the prepare step chose the pack pass" in capsys.readouterr().out

    (week / "ANSWERS.md").write_text("1) ok 2) b")
    run2 = tmp_path / "run2"
    assert code_of(ga.main, ["2030-W10", "--run", str(run2), "--as-of", TODAY], client=portal) == 0
    assert code_of(wc.main, ["--run", str(run2)], client=portal) == 0
    changes = json.loads((run2 / "changes.json").read_text())
    assert [op["id"] for op in changes["ops"]] == ["w1-ok-1", "w0-close"]
    assert changes["orchestrator"] == "weekly-review-orchestrator" and not changes["questions"]

    (run2 / "apply.json").write_text(json.dumps({"status": "applied", "results": [
        {"id": "w1-ok-1", "outcome": "applied"}, {"id": "w0-close", "outcome": "applied"}]}))
    assert code_of(wp.main, ["--run", str(run2)], client=portal) == 0
    applied = json.loads((week / "applied.json").read_text())
    assert applied["items"] == {"applied": 1, "recorded": 1} and applied["review_task_closed"]
    rows = {r["id"]: r for r in c.ledger_rows(week / c.items_ledger_name("2030-W10"))}
    assert rows["1"]["state"] == "applied" and rows["2"]["answer"] == "b"
    assert "## Answers and outcomes" in note["content"]
    assert chk.check("2030-W10", as_of=TODAY)["done"]


def test_an_answered_pack_is_not_replaced_and_a_replaced_one_relists(home, tmp_path, monkeypatch, fake_apply):
    run = packed_run(home, tmp_path, monkeypatch)
    portal = NotePortal()
    assert code_of(wp.main, ["--run", str(run), "--review-project", PROJECT], client=portal) == 0
    assert code_of(wp.main, ["--run", str(run), "--review-project", PROJECT], client=portal) == 0
    second = json.loads(fake_apply.read_text().splitlines()[1])["ops"]
    assert [op["op"] for op in second] == ["create", "comment"] and second[1]["task"] == f"portal://task/{NEW_TASK}"
    assert len(portal.notes) == 1 and any(c.week_dir(home, "2030-W10").glob("superseded-*"))
    (c.week_dir(home, "2030-W10") / "ANSWERS.md").write_text("1) ok")
    assert code_of(wp.main, ["--run", str(run), "--review-project", PROJECT], client=portal) == 1


def test_a_dry_run_writes_only_the_run_and_a_missing_project_is_exit_2(home, tmp_path, monkeypatch, fake_apply):
    run = packed_run(home, tmp_path, monkeypatch)
    portal = NotePortal()
    assert code_of(wp.main, ["--run", str(run), "--dry-run-if", "true"], client=portal) == 0
    assert json.loads((run / "publish-dry-run.json").read_text())["dry_run"]
    assert not c.week_dir(home, "2030-W10").exists() and not portal.notes and not fake_apply.exists()
    assert code_of(wp.main, ["--run", str(run)], client=portal) == 2


def test_the_pack_pass_change_set_is_empty(home, tmp_path, monkeypatch):
    run = packed_run(home, tmp_path, monkeypatch)
    assert code_of(wc.main, ["--run", str(run), "--dry-run-if", "true"]) == 0
    changes = json.loads((run / "changes.json").read_text())
    assert changes["ops"] == [] and changes["dry_run"] is True


def test_the_trust_score_check_has_a_timeout(tmp_path, monkeypatch):
    slow = tmp_path / "task_stack_check.py"
    slow.write_text("import time\ntime.sleep(10)\n")
    monkeypatch.setattr(c, "TASK_STACK_CHECK", slow)
    monkeypatch.setattr(c, "STACK_CHECK_TIMEOUT", 1)
    with pytest.raises(c.PortalError, match="within 1 seconds"):
        c.stack_check(tmp_path / "s.json", TODAY)
