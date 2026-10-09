"""Opening, recording and closing a cycle."""

import json
import subprocess
import sys

import pytest

import _common as c
import chief_of_staff_cycle as cy
from conftest import SCRIPTS


def start(root, day=None, **kw):
    return cy.start(root, day or c.local_now().date().isoformat(), **kw)


def test_the_owner_documents_come_from_settings_with_no_default_path(owner):
    out = cy.resolve_paths({"goals": str(owner / "principles.md")})
    assert out["paths"]["goals"].endswith("principles.md")
    assert out["paths"]["profile"] == "" and any("owner_profile" in n for n in out["notes"])
    assert any("charter not found" in n for n in out["notes"])


def test_start_writes_the_cycle_with_the_registry(root):
    out = start(root, paths=cy.resolve_paths())
    assert out["status"] == "ok" and out["display_name"] == "Chief of Staff"
    assert "kind" not in out and c.Path(out["folder"]).name.isdigit()
    assert {d["doer"] for d in out["doers"]} == {"produce-work", "meeting-prep", "person-brief"}
    assert any("orchestrator is launched" in n for n in out["notes"])
    assert out["retired_doers"]["relationship-check"].startswith("replaced")


def test_a_dry_run_folder_is_marked(root):
    out = start(root, dry_run=True)
    assert out["folder"].endswith("-dry-run") and out["dry_run"] is True


def test_a_backfill_is_labelled_midnight_and_monday_synthesis_is_due_once(root):
    out = start(root, day="2030-03-04")
    assert out["cycle_time"] == "00:00" and out["monday_synthesis_due"]
    (c.Path(out["folder"]) / "receipt.json").write_text(json.dumps({"content": "Week in review: steady."}))
    assert start(root, day="2030-03-04")["monday_synthesis_due"] is False


def test_record_keeps_one_row_per_dispatch(root):
    folder = start(root)["folder"]
    cy.record(folder, "meeting-prep", "Fabrikam review", "dispatched", "first")
    out = cy.record(folder, "meeting-prep", "Fabrikam review", "failed", "second")
    assert out["dispatches"] == 1 and out["row"]["outcome"] == "second"
    with pytest.raises(c.Bad):
        cy.record(folder, "x", "", "made-up", "y")


def verified(folder, written=True):
    c.atomic_json(c.Path(folder) / "verify.json", {"status": "found", "this_cycle_written": written, "note_id": "n1"})


def test_finish_reports_a_verified_receipt_once(root):
    folder = start(root)["folder"]
    verified(folder)
    out = cy.finish(folder, "ok")
    assert out["status"] == "finished" and out["receipt"] == "verified"
    assert cy.finish(folder, "ok")["status"] == "already_finished"


def test_a_found_note_without_this_cycles_block_is_a_receipt_failure(root):
    folder = start(root)["folder"]
    verified(folder, written=False)
    out = cy.finish(folder, "ok")
    assert out["receipt"].startswith("RECEIPT-FAILED") and "block is not in it" in out["receipt"]


def test_the_command_line_has_no_kind_or_trigger():
    done = subprocess.run([sys.executable, str(SCRIPTS / "chief_of_staff_cycle.py"), "start", "--kind", "triggered"],
                          capture_output=True, text=True)
    assert done.returncode == 2 and "unrecognized arguments" in done.stderr


def test_the_command_line_refuses_a_folder_inside_the_skill(tmp_path):
    done = subprocess.run([sys.executable, str(SCRIPTS / "chief_of_staff_cycle.py"), "record", str(SCRIPTS),
                           "--doer", "x", "--status", "failed", "--outcome", "y"], capture_output=True, text=True)
    assert done.returncode == 2 and "inside the skill" in done.stdout


ITEMS = [{"key": "vip-mail:mail-1", "summary": "VIP mail from Dana Whitfield: Contoso renewal"},
         {"key": "overdue:task-3", "summary": "Newly overdue:\n Approve the Tailspin invoice"}]


def test_a_cycle_woken_by_a_monitor_keeps_its_trigger_items(root):
    out = start(root, trigger_items=json.dumps(ITEMS))
    assert out["trigger_items"][0] == ITEMS[0]
    assert out["trigger_items"][1]["summary"] == "Newly overdue: Approve the Tailspin invoice"
    assert c.read_json(c.Path(out["folder"]) / "cycle.json")["trigger_items"] == out["trigger_items"]
    assert start(root)["trigger_items"] == []


@pytest.mark.parametrize("bad", ["not json", '{"key": "x"}', '[{"summary": "no key"}]'])
def test_unreadable_trigger_items_are_named_and_the_cycle_still_starts(root, bad):
    out = start(root, trigger_items=bad)
    assert out["status"] == "ok" and out["trigger_items"] == []
    assert any(n.startswith("trigger_items could not be read") for n in out["notes"])


def test_trigger_items_come_on_stdin(tmp_path):
    done = subprocess.run([sys.executable, str(SCRIPTS / "chief_of_staff_cycle.py"), "start", "--dry-run",
                           "--state", str(tmp_path / "state"), "--trigger-items", "-"],
                          input=json.dumps(ITEMS), capture_output=True, text=True)
    assert done.returncode == 0, done.stdout
    assert [i["key"] for i in json.loads(done.stdout)["trigger_items"]] == ["vip-mail:mail-1", "overdue:task-3"]


def test_trigger_items_can_come_from_a_file(tmp_path):
    f = tmp_path / "trigger-items.json"
    f.write_text(json.dumps(ITEMS), encoding="utf-8")
    assert json.loads(cy.read_items_arg(f"@{f}")) == ITEMS
    assert cy.read_items_arg(f"@{tmp_path / 'missing.json'}") == "@unreadable"
    assert cy.read_items_arg("[]") == "[]"
