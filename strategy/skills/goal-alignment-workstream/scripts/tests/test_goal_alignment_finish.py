"""goal_alignment_changes.py and goal_alignment_publish.py on invented data, with an in-memory
Portal for the note and a fake task_stack_apply.py that records what it was asked to write."""

import json

import pytest

import _common as c
import goal_alignment_changes as gc
import goal_alignment_check as chk
import goal_alignment_gather as ga
import goal_alignment_pack as pk
import goal_alignment_publish as gp
from conftest import RULES, TODAY, FakePortal, uid
from test_goal_alignment import STACK, review

DOMAIN, NEW_TASK = uid(800), uid(77)


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
            self.notes[nid] = {"id": nid, "content": args["content"], "visibility": "TEAM"}
            return {"id": nid}
        if tool == "update_note":
            self.notes[args["id"]].update(args["fields"])
            return {"ok": True}
        return super().call(tool, args)


@pytest.fixture
def fake_apply(tmp_path, monkeypatch):
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


def packed_run(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "stack_check", lambda out, *a, **k: (out.write_text(json.dumps(STACK)), STACK)[1])
    rules = tmp_path / "RULES.md"
    rules.write_text(RULES)
    run = tmp_path / "run"
    assert code_of(ga.main, ["2030-02", "--run", str(run), "--as-of", TODAY, "--rules", str(rules)],
                   client=FakePortal()) == 0
    (run / "review.json").write_text(json.dumps(review()))
    assert code_of(pk.main, [str(run)]) == 0
    return run, rules


def test_publish_answer_change_apply_and_record_the_mapping(home, tmp_path, monkeypatch, fake_apply):
    run, rules = packed_run(tmp_path, monkeypatch)
    portal = NotePortal()
    settings = tmp_path / "settings.toml"
    settings.write_text(settings.read_text() + f'\n[goal-alignment-workstream]\nalignment_domain = "{DOMAIN}"\n')
    assert code_of(gp.main, ["--run", str(run)], client=portal) == 0
    month = c.month_dir(home, "2030-02")
    published = json.loads((month / "publish.json").read_text())
    assert published["task"] == f"portal://task/{NEW_TASK}" and published["visibility"] == "PRIVATE"
    create = json.loads(fake_apply.read_text().splitlines()[0])["ops"][0]
    assert create["domain"] == DOMAIN and create["source"] == "goal-alignment:2030-02"
    assert create["title"] == "Approve the goal alignment for 2030-02"

    (month / "ANSWERS.md").write_text("1) park 2) close 3) ok")
    run2 = tmp_path / "run2"
    assert code_of(ga.main, ["2030-02", "--run", str(run2), "--as-of", TODAY, "--rules", str(rules)],
                   client=portal) == 0
    assert code_of(gc.main, ["--run", str(run2)], client=portal) == 0
    changes = json.loads((run2 / "changes.json").read_text())
    ops = [op["op"] for op in changes["ops"]]
    assert ops.index("project_close") < ops.index("goal_edit") and changes["ops"][-1]["id"] == "a0-close"
    assert "1 mapping(s) to record" in changes["notes"][0]

    (run2 / "apply.json").write_text(json.dumps({"status": "applied", "results": [
        {"id": op["id"], "outcome": "applied"} for op in changes["ops"]]}))
    assert code_of(gp.main, ["--run", str(run2)], client=portal) == 0
    assert uid(600) in json.loads((home / c.GOAL_MAP).read_text())["goals"]
    assert json.loads((month / "applied.json").read_text())["alignment_task_closed"]
    assert chk.check("2030-02", as_of=TODAY)["done"]


def test_an_answered_note_is_not_replaced(home, tmp_path, monkeypatch, fake_apply, capsys):
    run, _ = packed_run(tmp_path, monkeypatch)
    portal = NotePortal()
    assert code_of(gp.main, ["--run", str(run), "--alignment-domain", DOMAIN], client=portal) == 0
    (c.month_dir(home, "2030-02") / "ANSWERS.md").write_text("rest ok")
    capsys.readouterr()
    assert code_of(gp.main, ["--run", str(run), "--alignment-domain", DOMAIN], client=portal) == 1
    assert "already being answered" in capsys.readouterr().out


def test_a_bad_answer_is_a_question_and_nothing_else(home, tmp_path, monkeypatch, fake_apply):
    run, rules = packed_run(tmp_path, monkeypatch)
    portal = NotePortal()
    assert code_of(gp.main, ["--run", str(run), "--alignment-domain", DOMAIN], client=portal) == 0
    run2 = tmp_path / "run2"
    assert code_of(ga.main, ["2030-02", "--run", str(run2), "--as-of", TODAY, "--rules", str(rules)],
                   client=portal) == 0
    assert code_of(gc.main, ["--run", str(run2), "--answers", "1) park it next week 2) no"], client=portal) == 0
    changes = json.loads((run2 / "changes.json").read_text())
    assert changes["ops"] == [] and "says more than its verb" in changes["questions"][0]["ask"]


def test_the_trust_score_check_has_a_timeout(tmp_path, monkeypatch):
    slow = tmp_path / "task_stack_check.py"
    slow.write_text("import time\ntime.sleep(10)\n")
    monkeypatch.setattr(c, "TASK_STACK_CHECK", slow)
    monkeypatch.setattr(c, "STACK_CHECK_TIMEOUT", 1)
    with pytest.raises(c.PortalError, match="within 1 seconds"):
        c.stack_check(tmp_path / "s.json", TODAY)
