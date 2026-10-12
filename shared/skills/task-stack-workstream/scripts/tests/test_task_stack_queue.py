"""task_stack_queue.py: the owner's flagged tasks, worst domain first, capped and batched."""

import json
from datetime import date

import pytest

import task_stack_check as ck
import task_stack_queue as tq
from conftest import D_OPS, DOMAINS, OTHER, OWNER, P_AUDIT, goals, projects, task, uid


def check_json():
    tasks = [task(1, "Rate card", priority="P1", updated=1), task(2, "Budget", priority="P3", created=200, updated=1),
             task(3, "Pricing", priority="P3", created=100, updated=1),
             task(4, "Stock count", project_id=P_AUDIT, domain_id=D_OPS, updated=1),
             task(5, "Freight", owner_contact_id=OTHER, updated=1)]
    data = ck.build({"domain": DOMAINS, "goal": goals(), "project": projects(), "task": tasks}, date(2030, 3, 4))
    data["owner_contact_id"] = OWNER
    return data


def test_queue_is_the_owners_tasks_worst_domain_first_then_priority_then_oldest():
    result = tq.build(check_json())
    assert [r["ref"].rsplit("/", 1)[1] for r in result["tasks"]] == [uid(1), uid(2), uid(3), uid(4)]
    assert result["others"] == 1 and result["queued"] == 4


def test_queue_caps_and_batches():
    result = tq.build(check_json(), max_tasks=3, batch_size=2)
    assert [r["batch"] for r in result["tasks"]] == ["b1", "b1", "b2"] and result["deferred"] == 1


def test_queue_domain_filter_and_nothing_line():
    result = tq.build(check_json(), domain="operations")
    assert result["queued"] == 1
    assert tq.first_line(tq.build(check_json(), components=["waiting"])).startswith("NOTHING:")


def test_cli(tmp_path, capsys):
    source = tmp_path / "before.json"
    source.write_text(json.dumps(check_json()))
    out = tmp_path / "queue.json"
    with pytest.raises(SystemExit) as done:
        tq.main([str(source), "--max", "2", "--format", "json", "--out", str(out)])
    assert done.value.code == 0 and json.loads(out.read_text())["queued"] == 2
    with pytest.raises(SystemExit) as done:
        tq.main([str(source), "--components", "projects"])
    assert done.value.code == 2 and "not tasks" in capsys.readouterr().err
    with pytest.raises(SystemExit) as done:
        tq.main([str(tmp_path / "missing.json")])
    assert done.value.code == 0 and capsys.readouterr().out.startswith("STALE:")
