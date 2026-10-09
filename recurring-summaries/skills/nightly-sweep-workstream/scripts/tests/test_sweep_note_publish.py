"""sweep_note_publish.py: one Daily Note a date, never overwriting anyone, and the ledger after it."""

import json
from datetime import datetime, timezone

import pytest

import _common as c
import sweep_note_publish as sp
from conftest import OWNER, TZ, set_settings

DAY = "2030-03-06"
AFTER = datetime(2030, 3, 7, 6, 40, tzinfo=timezone.utc)   # 00:40 local on 03-07: the date is over
DURING = datetime(2030, 3, 6, 18, 0, tzinfo=timezone.utc)  # noon local on 03-06: the date is open
NOTE = f"# Daily Note - {DAY}\n**Sweep ran**: 00:40\n\n## Quick Stats\n- Emails processed: 4\n"
TITLE = f"Daily Note - {DAY}"
MARKER = c.daily_note_marker(DAY)


def publish(portal, text=NOTE, dry=False, published=None, now=AFTER, private=False):
    return sp.publish(portal, DAY, text, dry, published, now, TZ, private)


def test_the_daily_note_is_created_once_tagged_and_attached(portal):
    out = publish(portal)
    assert out["status"] == "created" and out["verified"] is True
    [(tool, args)] = [x for x in portal.writes() if x[0] == "create_note"]
    assert args["title"] == TITLE and args["tag_names"] == ["nightly-sweep"] and args["is_pinned"] is False
    assert args["associations"] == [{"entity_type": "contact", "entity_id": OWNER}]
    assert args["content"].rstrip().endswith(MARKER)
    again = publish(portal, published={"note_id": out["id"], "updated_at": out["updated_at"]})
    assert again["status"] == "unchanged" and len(portal.notes) == 1


def test_this_jobs_untouched_note_is_rewritten_in_place(portal):
    out = publish(portal)
    again = publish(portal, text=NOTE + "- one more\n", published={"note_id": out["id"],
                                                                   "updated_at": out["updated_at"]})
    assert again["status"] == "updated" and "- one more" in portal.notes[out["id"]]["content"]


def test_a_note_someone_else_wrote_is_appended_to_not_replaced(portal):
    n = portal.add_note(TITLE, "Dana's own notes")
    out = publish(portal)
    content = portal.notes[n["id"]]["content"]
    assert out["status"] == "appended" and content.startswith("Dana's own notes")
    assert "## Re-sweep" in content and "### Quick Stats" in content and content.rstrip().endswith(MARKER)
    assert publish(portal)["status"] == "unchanged"


def test_a_note_edited_after_this_job_wrote_it_is_appended_to(portal):
    out = publish(portal)
    portal.notes[out["id"]]["updated_at"] = "2030-03-07T12:00:00Z"
    again = publish(portal, text=NOTE + "- later\n", published={"note_id": out["id"], "updated_at": out["updated_at"]})
    assert again["status"] == "appended"


def test_without_the_ledgers_record_a_note_changed_after_creation_is_appended_to(portal):
    n = portal.add_note(TITLE, NOTE + "\n" + MARKER, created_at="2030-03-07T06:41:00Z")
    n["updated_at"] = "2030-03-07T07:00:00Z"
    assert publish(portal, text=NOTE + "- x\n")["status"] == "appended"
    other = {"note_id": "another", "updated_at": "2030-03-07T08:00:00Z"}
    assert publish(portal, text=NOTE + "- y\n", published=other)["status"] == "appended"


def test_the_note_is_found_by_its_marker_when_its_title_changed(portal):
    out = publish(portal)
    portal.notes[out["id"]]["title"] = "Daily Note - Wednesday"
    again = publish(portal, published={"note_id": out["id"], "updated_at": out["updated_at"]})
    assert again["id"] == out["id"] and len(portal.notes) == 1


def test_two_notes_with_the_title_keep_the_oldest_and_flag_the_rest(portal):
    first = portal.add_note(TITLE, "a", created_at="2030-03-07T06:41:00Z")
    portal.add_note(TITLE, "b", created_at="2030-03-07T06:42:00Z")
    out = publish(portal)
    assert out["id"] == first["id"] and any("can be deleted" in f for f in out["flags"])


def test_re_sweep_section_drops_the_title_and_leaves_code_alone():
    text = "\n\n# Daily Note\n## A\n```\n# not a heading\n```\n"
    section = sp.resweep_section(text, DAY, AFTER)
    assert "# Daily Note" not in section.split("\n", 1)[1] and "### A" in section and "\n# not a heading" in section


def test_a_note_that_does_not_read_back_is_refused(portal):
    portal._create_note_orig = portal._create_note

    def broken(args, mode):
        out = portal._create_note_orig(args, mode)
        portal.notes[out["id"]]["content"] = "mangled"
        return out
    portal._create_note = broken
    assert publish(portal)["code"] == "NOT_VERIFIED"


def test_daily_note_private_makes_and_checks_it_private(portal):
    out = publish(portal, private=True)
    assert out["status"] == "created" and portal.notes[out["id"]]["visibility"] == "PRIVATE"
    portal.notes[out["id"]]["visibility"] = "PUBLIC"
    again = publish(portal, private=True, published={"note_id": out["id"], "updated_at": out["updated_at"]})
    assert again["status"] == "unchanged" and portal.notes[out["id"]]["visibility"] == "PRIVATE"


def test_written_block_comes_from_the_applied_files(tmp_path):
    folder = tmp_path / DAY
    folder.mkdir()
    (folder / "phase1.json").write_text("{}")
    (folder / "applied-phase1.json").write_text(json.dumps({
        "status": "partial", "counts": {"created": 2, "failed": 1, "skipped": 1},
        "results": [{"outcome": "created", "title": "A"},
                    {"outcome": "failed", "title": "Sign the lease", "reason": "create_task failed"},
                    {"outcome": "skipped", "id": "t1", "reason": "not the owner's"}]}))
    (folder / "phase2.json").write_text("{}")
    (folder / "phase4.json").write_text(json.dumps({"status": "BLOCKED", "reason": "no calendar"}))
    block = sp.written_block(folder)
    assert block.startswith("## What the sweep wrote")
    assert "- Phase 1 (partial): created 2, skipped 1, failed 1" in block
    assert "  - failed: Sign the lease: create_task failed" in block and "  - skipped: t1: not the owner's" in block
    assert "- Phase 2: not applied (no applied-phase2.json)" in block
    assert "- Phase 4: BLOCKED" in block
    assert sp.written_block(tmp_path / "empty").endswith("No change set was applied for this date.")


# --------------------------------------------------------------------------- the CLI and the ledger

def make_run(tmp_path, dry_run=False, inbound=True, phases=(1, 2), flags=None):
    run = tmp_path / "run"
    folder = run / DAY
    folder.mkdir(parents=True)
    row = {"date": DAY, "next_day": "2030-03-07"}
    row.update(flags or {})
    (run / "dates.json").write_text(json.dumps({"dry_run": dry_run, "dates": [row]}))
    (folder / "emails.json").write_text(json.dumps({"inbound": [{"id": "x"}] if inbound else [], "sent": [],
                                                    "errors": []}))
    suffix = "-dry-run" if dry_run else ""
    for n in phases:
        (folder / f"phase{n}.json").write_text(json.dumps({"phase": n, "date": DAY, "writes": []}))
        (folder / f"applied-phase{n}{suffix}.json").write_text(json.dumps({"status": "would_apply" if dry_run
                                                                           else "nothing", "counts": {}}))
    (folder / "daily-note.md").write_text(NOTE)
    return run


def cli(portal, run, *extra, now=AFTER, capsys=None):
    with pytest.raises(SystemExit) as code:
        sp.main([DAY, "--note", str(run / DAY / "daily-note.md"), "--now", now.isoformat(), *extra], client=portal)
    return code.value.code, json.loads(capsys.readouterr().out)


def ledger(tmp_path):
    return json.loads((tmp_path / "state" / "ledger.json").read_text())


def test_a_complete_sweep_records_the_date_and_the_note_carries_the_written_block(portal, tmp_path, capsys):
    run = make_run(tmp_path)
    code, out = cli(portal, run, capsys=capsys)
    assert code == 0 and out["status"] == "created" and out["complete"] is True
    assert ledger(tmp_path)["dates"][DAY]["complete"] is True
    [note] = portal.notes.values()
    assert "## What the sweep wrote" in note["content"] and "- Phase 1 (nothing): no writes" in note["content"]
    assert note["content"].index("What the sweep wrote") < note["content"].index(MARKER)


@pytest.mark.parametrize("change,expect", [
    (lambda f: (f / "phase2.json").unlink(), "phase 2: no phase2.json"),
    (lambda f: (f / "phase1.json").write_text(json.dumps({"status": "BLOCKED", "reason": "x"})), "phase 1: BLOCKED"),
    (lambda f: (f / "applied-phase2.json").write_text(json.dumps({"status": "partial", "counts": {"failed": 1}})),
     "phase 2: sweep_apply was 'partial'"),
    (lambda f: (f / "emails.json").unlink(), "emails: no emails.json"),
])
def test_an_incomplete_sweep_is_recorded_so(portal, tmp_path, capsys, change, expect):
    run = make_run(tmp_path)
    change(run / DAY)
    code, out = cli(portal, run, capsys=capsys)
    entry = ledger(tmp_path)["dates"][DAY]
    assert entry["complete"] is False and entry["attempts"] == 1
    assert any(x.startswith(expect) for x in out["missing"] + out["failed"])


def test_a_day_without_inbound_mail_needs_no_phase_one(tmp_path):
    run = make_run(tmp_path, inbound=False, phases=(2,))
    assert sp.completeness(run / DAY)["complete"] is True


def test_phases_three_and_four_are_warnings_with_their_reason(tmp_path):
    run = make_run(tmp_path)
    (run / DAY / "phase4.json").write_text(json.dumps({"status": "BLOCKED", "reason": "the calendar was empty"}))
    out = sp.completeness(run / DAY, {"relationship_check": True, "calendar_prep": True, "next_day": "2030-03-07"})
    assert out["complete"] is True and len(out["warnings"]) == 2
    assert "the calendar was empty" in out["warnings"][1]


def test_a_dry_run_reads_the_dry_run_files_and_writes_nothing(portal, tmp_path, capsys):
    run = make_run(tmp_path, dry_run=True)
    code, out = cli(portal, run, "--dry-run", capsys=capsys)
    assert code == 0 and out["status"] == "would_create" and out["complete"] is True
    assert portal.writes() == [] and not (tmp_path / "state" / "ledger.json").exists()


def test_a_dry_run_is_kept_when_the_flag_is_forgotten(portal, tmp_path, capsys):
    run = make_run(tmp_path, dry_run=True)
    code, out = cli(portal, run, capsys=capsys)
    assert code == 3 and out["code"] == "DRY_RUN" and portal.writes() == []


def test_without_dates_json_nothing_is_written_live(portal, tmp_path, capsys):
    run = make_run(tmp_path)
    (run / "dates.json").unlink()
    code, out = cli(portal, run, capsys=capsys)
    assert code == 3 and out["code"] == "NO_RUN" and portal.writes() == []


def test_a_daytime_run_writes_the_note_but_never_records_the_date(portal, tmp_path, capsys):
    run = make_run(tmp_path)
    code, out = cli(portal, run, now=DURING, capsys=capsys)
    assert out["status"] == "created" and out["ledger"] == "skipped, day not over"
    assert DAY not in ledger(tmp_path)["dates"] and DAY in ledger(tmp_path)["published"]


def test_an_empty_note_is_refused(portal, tmp_path, capsys):
    run = make_run(tmp_path)
    (run / DAY / "daily-note.md").write_text("  \n")
    code, out = cli(portal, run, capsys=capsys)
    assert code == 3 and out["code"] == "EMPTY_NOTE"


def test_run_mode_publishes_every_date_with_a_note(portal, tmp_path, capsys):
    run = make_run(tmp_path)
    data = json.loads((run / "dates.json").read_text())
    data["dates"].append({"date": "2030-03-05"})
    (run / "dates.json").write_text(json.dumps(data))
    state = c.load_state(tmp_path / "state")
    state["in_progress"]["2030-03-05"] = {"started_at": AFTER.isoformat(), "run": str(run)}
    c.save_state(tmp_path / "state", state)
    with pytest.raises(SystemExit) as code:
        sp.main(["--run", str(run), "--now", AFTER.isoformat()], client=portal)
    out = json.loads(capsys.readouterr().out)
    assert code.value.code == 0 and [d["status"] for d in out["dates"]] == ["created", "no_note"]
    assert "2030-03-05" not in ledger(tmp_path)["in_progress"]


def test_the_setting_turns_privacy_on_through_the_cli(portal, tmp_path, capsys, settings_file):
    set_settings(settings_file, "daily_note_private = true")
    run = make_run(tmp_path)
    code, out = cli(portal, run, capsys=capsys)
    assert code == 0 and list(portal.notes.values())[0]["visibility"] == "PRIVATE"


def test_published_record_is_kept_for_the_next_sweep(portal, tmp_path, capsys):
    run = make_run(tmp_path)
    cli(portal, run, capsys=capsys)
    code, out = cli(portal, run, capsys=capsys)
    assert out["status"] == "unchanged" and len(portal.notes) == 1
