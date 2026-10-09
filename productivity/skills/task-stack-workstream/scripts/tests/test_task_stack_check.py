"""task_stack_check.py: the trust score, its components and its command line."""

import json
from datetime import date

import pytest

import _common as c
import task_stack_check as ck
from conftest import (D_OPS, D_SALES, DOMAINS, G_GROW, G_SUB, OTHER, OWNER, P_AUDIT, P_BUCKET, P_ROUTES,
                      FakePortal, goals, projects, task, uid)

TODAY = date(2030, 3, 4)


def corpus(tasks, goal_rows=None, project_rows=None):
    return {"domain": DOMAINS, "goal": goal_rows if goal_rows is not None else goals(),
            "project": project_rows if project_rows is not None else projects(), "task": tasks}


def flagged(result, component):
    return {f["ref"].rsplit("/", 1)[1]: f["reason"] for f in result["findings"][component]}


@pytest.mark.parametrize("title,ok", [
    ("Send the rate card", True), ("[Ops] Re: call Sam", True), ("please review the deck", True),
    ("Northwind: send the pack", True), ("Re-run the forecast", True), ("Rate card", False), ("Budget", False),
])
def test_next_action_heuristic(title, ok):
    assert c.is_next_action(title) is ok


def test_the_owners_lead_words_come_from_the_settings(no_owner_settings):
    assert not c.is_next_action("Dana to call the bank")
    no_owner_settings.write_text('[task-stack-workstream]\nlead_words = ["Dana"]\n')
    assert c.is_next_action("Dana to call the bank")


def test_reads_every_status_and_pages_to_the_end():
    many = [task(i, f"Send pack {i}") for i in range(1, 251)] + [task(300, "Send it", status="DONE")]
    got, unreadable = ck.read_stack(FakePortal(many))
    assert len(got["task"]) == 251 and unreadable == {}


def test_components_flag_what_they_say():
    result = ck.build(corpus([
        task(1, "Send pack", project_id=None),
        task(2, "Rate card"),
        task(3, "Send deck", due_date="2030-03-01", updated=1),
        task(4, "Chase Sam", status="WAITING", updated=1),
        task(5, "Book the van", created=60, updated=1), task(6, "Book the van", created=30, updated=1),
        task(7, "Review Q1 numbers", updated=1), task(8, "Review Q2 numbers", updated=1),
    ]), TODAY)
    assert flagged(result, "filing") == {uid(1): "no project"}
    assert uid(2) in flagged(result, "next_action")
    assert flagged(result, "overdue")[uid(3)].startswith("due 2030-03-01")
    assert flagged(result, "waiting")[uid(4)] == "no follow-up date; no named party"
    assert set(flagged(result, "duplicates")) == {uid(6)}          # the older one is kept, Q1 and Q2 differ
    assert uid(1) in flagged(result, "stale") and uid(3) not in flagged(result, "stale")


def test_projects_and_goals_and_the_catch_all_exemption():
    result = ck.build(corpus([task(1, "Audit the stock", project_id=P_AUDIT, domain_id=D_OPS, updated=1)],
                             goal_rows=goals() + [{"id": G_SUB, "title": "Open a depot", "parent_goal_id": G_GROW,
                                                  "status": "NOT_STARTED", "domain_id": D_OPS}]), TODAY)
    projects_flagged = flagged(result, "projects")
    assert P_BUCKET not in projects_flagged and P_AUDIT not in projects_flagged
    assert projects_flagged[P_ROUTES] == "no open task; no goal; no owner; no activity for 200 days"
    assert flagged(result, "goals") == {G_SUB: "no active project"}


def test_score_is_the_weighted_clean_share_and_points_add_up():
    result = ck.build(corpus([task(1, "Send pack", updated=1), task(2, "Rate card", updated=1)], goal_rows=[],
                             project_rows=[]), TODAY)
    comps = result["overall"]["components"]
    pools = {k: v for k, v in comps.items() if v["pool"]}
    wsum = sum(ck.WEIGHTS[k] for k in pools)
    expected = round(100 * sum(ck.WEIGHTS[k] * v["clean_share"] for k, v in pools.items()) / wsum, 1)
    assert result["overall"]["score"] == expected
    assert round(sum(v["points_lost"] for v in comps.values()), 1) == round(100 - expected, 1)


def test_scope_filters_and_baseline_compare():
    rows = [task(1, "Send pack", updated=1), task(2, "Rate card", project_id=P_AUDIT, domain_id=D_OPS, updated=1)]
    sales = ck.build(corpus(rows), TODAY, domain="sales")
    assert {d["name"] for d in sales["domains"]} == {"Northwind Sales"}
    before = ck.build(corpus(rows), TODAY)
    after = ck.build(corpus([rows[0]]), TODAY)
    delta = ck.compare(after, before)
    assert delta["components"]["next_action"]["resolved_items"] == 1
    assert delta["components"]["next_action"]["direction"] == "n/a" or delta["score_delta"] is not None


def run_cli(capsys, *argv, portal=None):
    with pytest.raises(SystemExit) as done:
        ck.main(list(argv), client=portal or FakePortal([task(1, "Rate card", updated=1)]))
    return done.value.code, capsys.readouterr()


def test_cli_text_json_out_and_precheck(capsys, tmp_path):
    code, out = run_cli(capsys, "--as-of", "2030-03-04")
    assert code == 0 and out.out.startswith("Task stack trust score")
    target = tmp_path / "before.json"
    code, out = run_cli(capsys, "--as-of", "2030-03-04", "--format", "json", "--out", str(target))
    data = json.loads(target.read_text())
    assert code == 0 and data["owner_contact_id"] == OWNER and json.loads(out.out)["tool"] == "task-stack-check"
    code, out = run_cli(capsys, "--out", str(target))
    assert code == 2 and "never overwrites" in out.err
    code, out = run_cli(capsys, "--as-of", "2030-03-04", "--precheck", "--components", "next_action")
    assert out.out.startswith("WORK: 1 items")
    code, out = run_cli(capsys, "--as-of", "2030-03-04", "--precheck", "--components", "waiting")
    assert out.out.startswith("NOTHING:")
    code, out = run_cli(capsys, "--as-of", "2030-03-04", "--baseline", str(target))
    assert code == 0 and "Since 2030-03-04" in out.out


@pytest.mark.parametrize("args", [["--as-of", "March"], ["--components", "nope"], ["--stale-days", "0"]])
def test_cli_bad_arguments_exit_2(capsys, args):
    assert run_cli(capsys, *args)[0] == 2


def test_cli_unreadable_portal_is_stale_and_exit_0(capsys):
    class Down:
        def call(self, tool, args=None):
            raise c.PortalError("portal list_entities: HTTP 502")

    code, out = run_cli(capsys, portal=Down())
    assert code == 0 and out.out.startswith("STALE:")


def test_no_portal_setting_is_stale_not_a_crash(capsys):
    with pytest.raises(SystemExit) as done:
        ck.main([])
    assert done.value.code == 0 and "portal_mcp_config" in capsys.readouterr().out
