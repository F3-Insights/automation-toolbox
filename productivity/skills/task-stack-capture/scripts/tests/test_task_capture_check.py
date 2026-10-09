import json
from datetime import date

import _common as c
import task_capture_check as k

TODAY = date(2026, 10, 1)


def gathered(sources):
    return c.gather(c.load_sources(str(sources))[0])


def test_before_any_run_is_work_but_not_late(sources):
    items, reports = gathered(sources)
    result = k.check(items, reports, {}, None, TODAY)
    assert result["tests"]["processed"]["met"] and len(result["new"]) == 3
    assert k.precheck_line(result).startswith("WORK: 3 source item(s)")


def test_a_deferred_item_older_than_the_last_run_is_late(sources):
    items, reports = gathered(sources)
    key = items[0]["key"]
    rows = {key: {"state": "seen", "first_seen": "2026-09-30T08:00:00+00:00"}}
    last = {"started_at": "2026-09-30T09:00:00+00:00"}
    result = k.check(items, reports, rows, last, TODAY)
    assert not result["tests"]["processed"]["met"] and not result["done"]


def test_done_when_every_item_is_final(sources):
    items, reports = gathered(sources)
    rows = {i["key"]: {"state": "skipped"} for i in items}
    result = k.check(items, reports, rows, {"started_at": "2026-09-30T09:00:00+00:00"}, TODAY)
    assert result["done"] and k.precheck_line(result).startswith("NOTHING")


def test_flags_a_task_created_twice_and_an_unreadable_source(sources, tmp_path):
    data = json.loads(sources.read_text())
    data["sources"].append({"name": "notes", "kind": "folder-inbox", "path": str(tmp_path / "missing")})
    sources.write_text(json.dumps(data))
    items, reports = gathered(sources)
    a, b = items[0]["key"], items[1]["key"]
    rows = {a: {"state": "created", "task": "portal://task/x", "marker": c.source_marker(a)},
            b: {"state": "created", "task": "portal://task/x", "marker": "tsk000000000000"}}
    result = k.check(items, reports, rows, None, TODAY)
    assert len(result["tests"]["no-duplicates"]["gaps"]) == 2
    assert not result["tests"]["sources"]["met"]
    assert "unreadable source notes" in k.precheck_line(result)


def test_command_runs_offline_and_a_blank_option_means_not_given(sources, tmp_path, capsys):
    assert k.main(["--sources", str(sources), "--state", str(tmp_path / "s"), "--horizon-days=",
                   "--as-of", "2026-10-01", "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["horizon_days"] == 14
