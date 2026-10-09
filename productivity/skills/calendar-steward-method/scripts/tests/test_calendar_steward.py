"""The calendar steward: calendar-steward-scan, calendar-apply and calendar-steward-check."""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _common as c  # noqa: E402
import calendar_apply as ca  # noqa: E402
import calendar_steward_check as chk  # noqa: E402
import calendar_steward_scan as sc  # noqa: E402
from cal_fixtures import (DAY, NOW, PROJECT, dp_state, ev, fake_task_stack, portal, proposals,  # noqa: E402,F401
                          ref)


def scan_into(run, home, portal, tmp_path, pass_="auto"):
    result = sc.build(portal, DAY, 2, pass_, work=((8, 0), (17, 30)), min_focus=60, focus_target=90, gap=10,
                      max_reads=50, focus_title=c.FOCUS_TITLE, internal=(), home=home, dp_state=dp_state(tmp_path),
                      now=NOW)
    c.write_json(run / "scan.json", result)
    return result


@pytest.fixture
def staged(tmp_path, portal):
    run, home = tmp_path / "run", tmp_path / "home"
    run.mkdir()
    scan = scan_into(run, home, portal, tmp_path)
    c.write_json(run / "proposals.json", proposals(scan))
    return run, home, scan


def cli(capsys, monkeypatch, module, *args):
    monkeypatch.setattr(sys, "argv", [module.__name__, *[str(a) for a in args]])
    try:
        module.main()
        code = 0
    except SystemExit as exc:
        code = exc.code or 0
    return code, capsys.readouterr()


def publish(capsys, monkeypatch, run, home, *extra):
    return cli(capsys, monkeypatch, ca, "publish", "--run", run, "--home", home, "--project", PROJECT, *extra)


# --------------------------------------------------------------------------- the scan

def test_scan_finds_each_kind_of_problem_with_stable_ids(tmp_path, portal):
    run, home = tmp_path / "run", tmp_path / "home"
    run.mkdir()
    scan = scan_into(run, home, portal, tmp_path)
    kinds = scan["finding_counts"]
    assert kinds["conflict"] == 1 and kinds["no-prep"] == 1 and kinds["focus-overlap"] == 1
    assert kinds["unanswered"] == 1 and kinds["daily-plan"] == 1 and kinds["no-agenda"] == 1
    assert all(f["id"].startswith(f["kind"] + ":") for f in scan["findings"])
    assert portal.writes() == []
    assert [f["id"] for f in scan_into(run, home, portal, tmp_path)["findings"]] == [f["id"] for f in scan["findings"]]


def test_back_to_back_needs_three_meetings_without_a_break():
    def m(s, e):
        return {"kind": "meeting", "start": s, "end": e, "ref": s, "title": s}
    runs = sc.back_to_back([m("09:00", "10:00"), m("10:05", "11:00"), m("11:00", "11:30"), m("13:00", "14:00")], 10)
    assert [(r["start"], r["end"], r["count"]) for r in runs] == [("09:00", "11:30", 3)]
    assert sc.back_to_back([m("09:00", "10:00"), m("10:30", "11:00"), m("11:00", "12:00")], 10) == []


def test_agenda_text_ignores_conferencing_boilerplate():
    assert sc.agenda_text("Microsoft Teams meeting\nJoin the meeting now\nMeeting ID: 123\nhttps://x.test/j") == ""
    assert sc.agenda_text("Review the second-quarter lanes\nJoin on your computer") == "Review the second-quarter lanes"


def test_scan_cli_accepts_a_blank_form_and_writes_stale_on_failure(tmp_path, monkeypatch, capsys):
    def broken(*a, **k):
        raise c.PortalError("unreachable")
    monkeypatch.setattr(c, "client", broken)
    out = tmp_path / "scan.json"
    code, res = cli(capsys, monkeypatch, sc, "--date=", "--pass=", "--out", out, "--home", tmp_path / "h", "--tz", "UTC")
    assert code == 0 and res.out.startswith("STALE: ") and json.loads(out.read_text())["stale"] is True
    code, _ = cli(capsys, monkeypatch, sc, "--pass=sometimes", "--out", out, "--home", tmp_path / "h")
    assert code == 2


def test_the_home_is_a_setting_and_its_absence_is_said(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "none.toml"))
    code, res = cli(capsys, monkeypatch, chk, "2030-03-04")
    assert code == 2 and "state_dir" in res.err
    (tmp_path / "s.toml").write_text(f'state_dir = "{tmp_path / "state"}"\n')
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "s.toml"))
    assert c.home_dir("") == tmp_path / "state" / "calendar-steward"


# --------------------------------------------------------------------------- proposals and answers

def test_a_focus_block_on_a_meeting_and_a_move_of_a_shared_meeting_are_refused(staged):
    run, home, scan = staged
    doc = proposals(scan)
    doc["proposals"][0].update(start="09:00", end="10:00")
    doc["proposals"][3].update(event=ref(1), date="2030-03-04", start="09:00", end="10:00")
    doc["proposals"][1]["draft"] = ""
    problems = " | ".join(c.proposals_problems(doc, scan))
    assert "p1: 2030-03-04 09:00-10:00 is not free" in problems
    assert "p4: 'Acme ops weekly' has other attendees" in problems
    assert "p2: draft is the reply" in problems
    assert c.proposals_problems(proposals(scan), scan) == []


def test_coverage_names_every_finding_without_a_proposal_or_dismissal(staged):
    run, home, scan = staged
    doc = proposals(scan)
    assert c.coverage_gaps(doc, scan) == []
    doc["findings"] = doc["findings"][:2]
    gaps = c.coverage_gaps(doc, scan)
    assert gaps and all(g.split(":")[0] in ("daily-plan", "focus-overlap", "no-agenda", "unanswered") for g in gaps)


def test_answers_only_ok_approves():
    items = [{"n": n, "id": f"p{n}"} for n in (1, 2, 3, 4, 5)]
    got = c.resolve_answers(items, [{"source": "x", "text": "1) ok 2) no 3) ok but at ten\n4) maybe"}])
    assert [r["state"] for r in got["items"]] == ["approved", "declined", "modified", "unclear", "unanswered"]
    got = c.resolve_answers(items, [{"source": "a", "text": "1) no"}, {"source": "b", "text": "1) yes rest no"}])
    assert [r["state"] for r in got["items"]] == ["approved", "declined", "declined", "declined", "declined"]


# --------------------------------------------------------------------------- publish

def test_a_dry_run_publishes_nothing(staged, portal, capsys, monkeypatch):
    run, home, scan = staged
    c.write_json(run / "proposals.json", proposals(scan, dry=True))
    code, _ = publish(capsys, monkeypatch, run, home, "--dry-run-if=true")
    assert code == 0 and json.loads((run / "publish-dry-run.json").read_text())["status"] == "would_publish"
    assert not home.exists() and portal.writes() == []
    code, res = publish(capsys, monkeypatch, run, home, "--dry-run-if=false")
    assert code == 1 and "dry-run session" in res.out


def test_publish_files_one_task_by_marker_and_never_twice(staged, portal, capsys, monkeypatch):
    run, home, scan = staged
    code, res = publish(capsys, monkeypatch, run, home)
    assert code == 0, res.err
    out = json.loads((run / "publish.json").read_text())
    assert out["status"] == "published" and out["items"] == 4
    task = portal.tasks[out["task"].rsplit("/", 1)[-1]]
    assert task["title"] == "Approve calendar changes for 2030-03-04" and task["owner_contact_id"]
    assert c.marker("2030-03-04") in task["description"]
    assert "1. Add a focus block Mon 03-04 14:00-15:30" in task["description"]
    code, res = publish(capsys, monkeypatch, run, home)
    assert json.loads(res.out)["status"] == "unchanged"
    assert sum(1 for x in portal.calls if x[0] == "create_task") == 1
    assert [r["state"] for r in c.Ledger(home).rows()] == ["proposed"] * 4


def test_a_new_list_replaces_an_unanswered_one_but_never_an_answered_one(staged, portal, capsys, monkeypatch):
    run, home, scan = staged
    publish(capsys, monkeypatch, run, home)
    doc = proposals(scan)
    doc["proposals"] = doc["proposals"][1:]
    doc["findings"][2] = {"ids": doc["findings"][2]["ids"], "dismissed": "the afternoon is taken"}
    c.write_json(run / "proposals.json", doc)
    code, res = publish(capsys, monkeypatch, run, home)
    assert json.loads(res.out)["status"] == "published"
    assert list((home / "2030-03-04").glob("superseded-*/items.json"))
    task_id = next(iter(portal.tasks))
    assert "replaces the one above" in portal.comments[task_id][-1]["body"]
    portal.owner_says(f"portal://task/{task_id}", "1) ok")
    c.write_json(run / "proposals.json", proposals(scan))
    code, res = publish(capsys, monkeypatch, run, home)
    assert code == 1 and "already being answered" in res.out


# --------------------------------------------------------------------------- apply

def published(staged, portal, capsys, monkeypatch):
    run, home, scan = staged
    publish(capsys, monkeypatch, run, home)
    return run, home, json.loads((run / "publish.json").read_text())["task"]


def apply_now(run, home, portal, answers="", dry=False, now=NOW):
    return ca.apply(run, home, "auto", answers, dry, portal, PROJECT, "", now=now, runner=fake_task_stack(portal)[0])


def test_apply_makes_exactly_the_approved_changes(staged, portal, capsys, monkeypatch):
    run, home, task = published(staged, portal, capsys, monkeypatch)
    portal.owner_says(task, "1) ok 2) no 3) ok but the day before 4) ok")
    out = apply_now(run, home, portal)
    results = out["lists"][0]["results"]
    assert results["1"]["outcome"] == "applied" and results["4"]["outcome"] == "applied"
    assert results["2"]["outcome"] == "declined" and results["3"]["outcome"] == "modified"
    made = sorted(t["title"] for t in portal.tasks.values() if not t["title"].startswith("Approve"))
    assert made == ["Book focus block Mon 03-04 14:00-15:30: Focus: freight quote",
                    "Move Admin hold from Tue 03-05 14:00-15:00 to Tue 03-05 16:00-17:00"]
    work = next((home / "2030-03-04").glob("approve-*"))
    ics = (work / "events.ics").read_text()
    assert "DTSTART:20300304T190000Z" in ics and "DTEND:20300304T203000Z" in ics and "DTSTART:20300305T210000Z" in ics
    changes = json.loads((work / "changes.json").read_text())
    assert changes["tool"] == "task-stack-changes" and {o["op"] for o in changes["ops"]} == {"create"}
    rows = {r["id"]: r for r in c.Ledger(home).rows()}
    assert rows["2030-03-04:1"]["state"] == "applied" and rows["2030-03-04:2"]["state"] == "declined"
    assert len((home / "journal.jsonl").read_text().splitlines()) == 2
    assert "1) applied" in portal.comments[task.rsplit("/", 1)[-1]][-1]["body"]
    before = len(portal.tasks)
    apply_now(run, home, portal)
    assert len(portal.tasks) == before   # applied items are final; nothing is made twice


def test_a_decline_is_a_draft_on_a_task_and_nothing_is_sent_or_deleted(staged, portal, capsys, monkeypatch):
    run, home, task = published(staged, portal, capsys, monkeypatch)
    portal.owner_says(task, "2) ok")
    apply_now(run, home, portal)
    made = [t for t in portal.tasks.values() if t["title"].startswith("Send the decline")]
    assert len(made) == 1 and "nothing has been sent" in made[0]["description"]
    assert not [x for x in portal.calls if "delete" in x[0] or "send" in x[0] or x[0] == "draft_push"]


def test_apply_refuses_a_slot_no_longer_free_and_expires_the_past(staged, portal, capsys, monkeypatch):
    run, home, task = published(staged, portal, capsys, monkeypatch)
    portal.events.append(ev(9, "Surprise board call", "2030-03-04T19:00:00Z", "2030-03-04T20:00:00Z",
                            people=("dana@acme.test",)))
    portal.owner_says(task, "1) ok 3) ok")
    results = apply_now(run, home, portal, now=NOW + timedelta(hours=3))["lists"][0]["results"]   # 10:00 local
    assert results["1"]["outcome"] == "refused" and "no longer free" in results["1"]["reason"]
    assert results["3"]["outcome"] == "expired"
    assert len(portal.tasks) == 1


def test_a_dry_apply_writes_nothing(staged, portal, capsys, monkeypatch):
    run, home, task = published(staged, portal, capsys, monkeypatch)
    portal.owner_says(task, "rest ok")
    writes, ledger = len(portal.writes()), (home / "CALENDAR-STEWARD-ITEMS.csv").read_text()
    out = apply_now(run, home, portal, dry=True)
    assert out["status"] == "would_apply"
    assert {r["outcome"] for r in out["lists"][0]["results"].values()} == {"would_apply"}
    assert len(portal.writes()) == writes and (home / "CALENDAR-STEWARD-ITEMS.csv").read_text() == ledger
    assert not list((home / "2030-03-04").glob("approve-*"))


def test_undo_cancels_what_an_apply_made(staged, portal, capsys, monkeypatch):
    run, home, task = published(staged, portal, capsys, monkeypatch)
    portal.owner_says(task, "1) ok")
    apply_now(run, home, portal)
    made = next(t for t in portal.tasks.values() if t["title"].startswith("Book focus block"))
    out = ca.undo(home, "2030-03-04", 1, False, runner=fake_task_stack(portal)[1])
    assert out["status"] == "undone" and made["status"] == "CANCELLED"
    assert {r["id"]: r for r in c.Ledger(home).rows()}["2030-03-04:1"]["state"] == "undone"


def test_an_undo_that_errors_is_not_recorded_as_undone(staged, portal, capsys, monkeypatch):
    run, home, task = published(staged, portal, capsys, monkeypatch)
    portal.owner_says(task, "1) ok")
    apply_now(run, home, portal)
    with pytest.raises(c.Failure, match="could not undo"):
        ca.undo(home, "2030-03-04", 1, False, runner=lambda *a: {"status": "error", "reason": "the Portal said no"})
    assert {r["id"]: r for r in c.Ledger(home).rows()}["2030-03-04:1"]["state"] != "undone"


def test_the_change_set_goes_to_task_stack_apply_by_its_documented_interface(tmp_path, monkeypatch):
    seen = {}

    class Done:
        returncode, stdout, stderr = 0, json.dumps({"status": "applied", "results": []}), ""

    def fake_run(argv, **kw):
        seen["argv"] = argv
        return Done()
    monkeypatch.setattr(ca.subprocess, "run", fake_run)
    ca.task_stack_apply(tmp_path / "changes.json", tmp_path / "undo.jsonl", True)
    argv = seen["argv"]
    assert argv[1].endswith("task-stack-workstream/scripts/task_stack_apply.py")
    assert argv[2:] == [str(tmp_path / "changes.json"), "--log", str(tmp_path / "undo.jsonl"), "--max-changes", "100",
                        "--dry-run"]


# --------------------------------------------------------------------------- the check

def test_check_is_done_after_publish_and_apply(staged, portal, capsys, monkeypatch):
    run, home, task = published(staged, portal, capsys, monkeypatch)
    portal.owner_says(task, "1) ok")
    apply_now(run, home, portal)
    result = chk.check(DAY, home, run, portal)
    assert result["done"], json.dumps(result["tests"], indent=1)


def test_check_flags_a_change_without_an_ok_and_a_missing_list(staged):
    run, home, scan = staged
    assert not chk.check(DAY, home, run)["tests"]["published"]["met"]
    c.Ledger(home).upsert("2030-03-04:1", {"date": "2030-03-04", "n": "1", "state": "applied", "answer": "no"})
    assert "without an ok" in chk.check(DAY, home, run)["tests"]["applied"]["gaps"][0]


def test_precheck_work_until_published_then_on_new_answers(staged, portal, capsys, monkeypatch):
    run, home, scan = staged
    assert chk.precheck(home, DAY, None).startswith("WORK: the calendar list for 2030-03-04 is not published")
    publish(capsys, monkeypatch, run, home)
    assert chk.precheck(home, DAY, None).startswith("NOTHING: ")
    assert chk.precheck(home, date(2030, 3, 9), None).startswith("NOTHING: Saturday")
    (home / "2030-03-04" / "ANSWERS.md").write_text("1) ok 2) ok but later\n")
    assert chk.precheck(home, DAY, None) == "WORK: answers to apply (2030-03-04: item(s) 1)"
    code, res = cli(capsys, monkeypatch, chk, "--precheck", "--home", home, "2030-03-04")
    assert code == 0 and res.out.startswith("WORK: ")


def test_the_ledger_refuses_a_file_with_other_columns(tmp_path):
    (tmp_path / "CALENDAR-STEWARD-ITEMS.csv").write_text("id,something\n1,x\n")
    with pytest.raises(c.Bad):
        c.Ledger(tmp_path).rows()
