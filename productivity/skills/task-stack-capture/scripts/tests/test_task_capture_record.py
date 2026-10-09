import json

import _common as c
import task_capture_queue as q
import task_capture_record as r

TASK = "portal://task/11111111-2222-3333-4444-555555555555"
OTHER = "portal://task/66666666-7777-8888-9999-000000000000"


def make_run(tmp_path, sources, apply_results, captures, ops):
    run = tmp_path / "run"
    run.mkdir(exist_ok=True)
    q.main(["--sources", str(sources), "--offline", "--as-of", "2026-10-01",
            "--out", str(run / "capture-queue.json")])
    queue = json.loads((run / "capture-queue.json").read_text())
    keys = {i["text"]: i["key"] for i in queue["items"]}
    (run / "changes.json").write_text(json.dumps({"ops": ops(keys), "captures": captures(keys)}))
    (run / "apply.json").write_text(json.dumps({"results": apply_results}))
    return run, keys


def test_record_writes_one_row_per_item_and_the_run(tmp_path, sources, capsys):
    run, keys = make_run(
        tmp_path, sources,
        [{"id": "n1", "outcome": "applied", "task": TASK}],
        lambda k: [{"source": k["Book the Lakeview workshop room"], "decision": "skip", "reason": "done"},
                   {"source": k["Draft the Fabrikam renewal note"], "decision": "exists", "task": OTHER}],
        lambda k: [{"id": "n1", "op": "create", "source": k["Send Dana the freight summary"]}])
    state = tmp_path / "state"
    assert r.main(["--run", str(run), "--state", str(state)]) == 0
    line = capsys.readouterr().out.splitlines()[-1]
    assert line.startswith("RECORDED: 1 created, 1 exists, 1 skipped, 0 asked, 1 expired, 2 closed")
    rows = c.read_ledger(state / "capture")
    dana = rows[keys["Send Dana the freight summary"]]
    assert dana["state"] == "created" and dana["task"] == TASK and dana["marker"] == c.source_marker(dana["id"])
    assert (state / "capture" / "runs.jsonl").read_text().count("\n") == 1
    assert (run / "capture-record.json").is_file()


def test_a_dry_run_records_nothing(tmp_path, sources):
    run, _ = make_run(tmp_path, sources, [], lambda k: [], lambda k: [])
    state = tmp_path / "state"
    assert r.main(["--run", str(run), "--state", str(state), "--dry-run-if", "true"]) == 0
    assert not (state / "capture" / "CAPTURE-LEDGER.csv").exists()
    assert (run / "capture-record-dry-run.json").is_file()


def test_refused_creates_retry_then_stick_and_duplicates_exist(tmp_path, sources):
    run, keys = make_run(
        tmp_path, sources,
        [{"id": "n1", "outcome": "refused", "code": "NOT_NEXT_ACTION", "reason": "no verb"},
         {"id": "n2", "outcome": "refused", "code": "DUPLICATE", "reason": f"same as {TASK}"}],
        lambda k: [],
        lambda k: [{"id": "n1", "op": "create", "source": k["Send Dana the freight summary"]},
                   {"id": "n2", "op": "create", "source": k["Book the Lakeview workshop room"]}])
    state = tmp_path / "state"
    for _ in range(3):
        r.main(["--run", str(run), "--state", str(state)])
    rows = c.read_ledger(state / "capture")
    assert rows[keys["Send Dana the freight summary"]]["state"] == "stuck"
    assert rows[keys["Book the Lakeview workshop room"]]["state"] == "exists"
    assert rows[keys["Book the Lakeview workshop room"]]["task"] == TASK


def test_record_without_a_queue_is_stale(tmp_path, capsys):
    run = tmp_path / "run"
    run.mkdir()
    assert r.main(["--run", str(run), "--state", str(tmp_path / "state")]) == 0
    assert capsys.readouterr().out.startswith("STALE")
    assert not (run / "capture-record.json").exists()


def test_a_bad_dry_run_flag_and_a_missing_run_exit_2(tmp_path):
    import pytest
    for args in (["--run", str(tmp_path), "--dry-run-if", "maybe"], ["--run", str(tmp_path / "nope")]):
        with pytest.raises(SystemExit) as exc:
            r.main(args)
        assert exc.value.code == 2


def test_source_marker_is_the_one_task_stack_apply_gives_a_capture():
    # task_stack_apply.py keeps its own copy of this formula; both must give the same marker,
    # or a captured item's task is never found again and the item is captured twice.
    assert c.source_marker("inbox:abc123") == "tska76da721302c"
    assert c.source_marker(" inbox:abc123 ") == "tska76da721302c"
