"""report_workorder.py: the week as a resumable work order, mirrored to the Portal when it can be."""

import json

from conftest import PERIOD, run


def call(store, *args):
    done = run("report_workorder", *args, "--period", PERIOD, "--store", store)
    return done.returncode, (json.loads(done.stdout) if done.stdout.strip() else {}), done.stderr


def test_the_state_file_carries_the_run_without_a_portal(store):
    code, found, err = call(store, "open", "--author", "finance", "--agent", "weekly-reporter")
    assert code == 0 and "the Portal was not used" in err, "an unconfigured Portal is a finding, not a failure"
    assert found["next"].startswith("no stage has been recorded")
    call(store, "stage", "--stage", "organize", "--file", "pack.json", "--no-portal")
    call(store, "wait", "--gate", "gate1", "--questions", "4", "--no-portal")
    code, found, _ = call(store, "resume")
    assert found["stopped_at"] == "the gate gate1" and found["files"] == ["pack.json"]
    code, found, _ = call(store, "stage", "--stage", "gate1", "--no-portal")
    assert found["gate_cleared"] is True and found["next"] == "'gate1' is done; the next stage is 'gate2'"
    code, found, _ = call(store, "close", "--file", "weekly.pdf", "--no-portal")
    assert code == 0 and found["closed_at"]


def test_close_with_no_file_is_refused(store):
    call(store, "open", "--author", "finance", "--agent", "weekly-reporter", "--no-portal")
    code, _, err = call(store, "close", "--no-portal")
    assert code == 3 and "names no file" in err


def test_open_creates_and_mirrors_the_task_on_the_portal(store, portal):
    code, found, err = call(store, "open", "--author", "finance", "--agent", "weekly-reporter")
    assert code == 0, err
    assert found["task_id"] == "task-wo" and found["portal"]["in_use"] is True
    created = next(args for tool, args, _ in portal if tool == "create_task")
    assert created["source_reference"] == f"weekly-report:finance:{PERIOD}" and created["assignees"] == ["weekly-reporter"]
    call(store, "stage", "--stage", "collect")
    updates = [args for tool, args, _ in portal if tool == "update_task"]
    assert updates[-1] == {"id": "task-wo", "status": "IN_PROGRESS"}
    assert all("assignees" not in u for u in updates), "a mirror never replaces the assignees"
