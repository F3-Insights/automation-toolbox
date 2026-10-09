"""project-health-check against a made-up company, Acme Components, offline. Date pinned to 2026-10-04."""

import json
from datetime import date, datetime, timedelta, timezone

import project_health_check as chk

TODAY = date(2026, 10, 4)
NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
OWNER = "c-owner"


def ago(days):
    return (NOW - timedelta(days=days)).isoformat().replace("+00:00", "Z")


def project(pid, name, domain_id="d-ops", goal_id="g-ops", updated=200, created=400, **kw):
    row = {"id": pid, "name": name, "domain_id": domain_id, "goal_id": goal_id, "status": "IN_PROGRESS",
           "priority": "P3", "assignee_contact_id": None, "is_general": False, "is_archived": False,
           "created_at": ago(created), "updated_at": ago(updated)}
    row.update(kw)
    return row


def task(tid, title, project_id, status="TODO", updated=5, created=60, owner=OWNER, **kw):
    row = {"id": tid, "title": title, "project_id": project_id, "status": status, "priority": "P3",
           "owner_contact_id": owner, "created_at": ago(created), "updated_at": ago(updated),
           "due_date": None, "deadline": None}
    row.update(kw)
    return row


DOMAINS = [{"id": "d-ops", "name": "Acme Operations"}, {"id": "d-lab", "name": "Acme Labs"}]
GOALS = [{"id": "g-ops", "title": "Run lean operations"}]
PROJECTS = [
    project("p-ok", "Warehouse move", priority="P2"),
    project("p-nogoal", "Pricing study", goal_id=None),
    project("p-stall", "Vendor audit"),
    project("p-stall-p1", "Bank covenant", priority="P1"),
    project("p-dead", "Trade show", goal_id=None),
    project("p-dead-open", "Old migration", goal_id=None),
    project("p-bucket", "General Tasks", is_general=True),
    project("p-bucket-lab", "General Tasks", domain_id="d-lab", is_general=True),
    project("p-done", "Finished", status="COMPLETED"),
]
TASKS = [
    task("t1", "Book the movers", "p-ok"),
    task("t2", "Draft the price list", "p-nogoal"),
    task("t3", "Request the vendor list", "p-stall", updated=45, created=45),
    task("t4", "Send the covenant certificate", "p-stall-p1", updated=40, created=40),
    task("t5", "Ship the booth", "p-dead", status="DONE", updated=200, created=300),
    task("t6", "Map the old fields", "p-dead-open", updated=150, created=150),
    task("t7", "Call the insurer", "p-bucket", created=100, priority="P2"),
    task("t8", "File the receipt", "p-bucket", created=200),
    task("t9", "Their errand", "p-bucket", owner="c-other"),
    task("t10", "Lab chore", "p-bucket-lab"),
]


class FakePortal:
    """Open tasks in the plain listing; DONE and CANCELLED only when filtered by status."""

    def __init__(self, projects=PROJECTS, tasks=TASKS, fail=False):
        self.projects, self.tasks, self.fail, self.calls = projects, tasks, fail, 0

    def call(self, tool, arguments=None):
        self.calls += 1
        if self.fail:
            raise RuntimeError("no route")
        if tool == "whoami":
            return {"principal": {"contact_id": OWNER}}
        args = arguments or {}
        kind, want = args["entity_type"], (args.get("filters") or {}).get("status")
        rows = {"domain": DOMAINS, "goal": GOALS, "project": self.projects}.get(kind)
        if rows is None:
            rows = [t for t in self.tasks if (t["status"] == want if want else t["status"] not in ("DONE", "CANCELLED"))]
        return {"items": rows, "total": len(rows), "has_more": False}


def result(**kw):
    corpus, _ = chk.read_stack(FakePortal())
    return chk.build(corpus, TODAY, owner=OWNER, **kw)


def by_name(res):
    return {r["name"]: r for r in res["projects"]}


def test_states_and_gaps():
    r = by_name(result())
    assert r["Warehouse move"]["state"] == "healthy"
    assert r["Pricing study"]["state"] == "gaps" and r["Pricing study"]["gaps"] == ["no_goal"]
    assert r["Vendor audit"]["state"] == "stalled"
    assert r["Trade show"]["state"] == "dead" and r["Trade show"]["close_eligible"]
    assert r["Old migration"]["state"] == "dead" and not r["Old migration"]["close_eligible"]
    assert "Finished" not in r and "General Tasks" not in r


def test_worklist_order_and_the_lists_apart():
    res = result()
    assert res["worklist"] == ["portal://project/p-stall-p1", "portal://project/p-stall", "portal://project/p-nogoal"]
    assert res["close_eligible"] == ["portal://project/p-dead"]
    assert res["close_candidates"] == ["portal://project/p-dead-open"]
    assert result(max_projects=1)["deferred"] == 2


def test_buckets_counted_and_drained_only_where_a_real_project_exists():
    res = result()
    assert {b["domain"]: b["open_tasks"] for b in res["buckets"]} == {"Acme Operations": 3, "Acme Labs": 1}
    assert [t["ref"] for t in res["drain"]] == ["portal://task/t7", "portal://task/t8"]


def test_a_bulk_stamp_is_not_activity():
    stamp = ago(1)
    projects = [project(f"b{i}", f"Bulk {i}", updated=0, created=300, updated_at=stamp) for i in range(5)]
    corpus = {"domain": DOMAINS, "goal": GOALS, "project": projects, "task": []}
    res = chk.build(corpus, TODAY)
    assert all(r["idle_days"] == 300 for r in res["projects"]) and res["summary"]["bulk_minutes"]


def test_compare_and_precheck_line():
    before = result()
    fixed = [dict(p, goal_id="g-ops") if p["id"] == "p-nogoal" else p for p in PROJECTS]
    corpus, _ = chk.read_stack(FakePortal(projects=fixed))
    after = chk.build(corpus, TODAY, owner=OWNER)
    diff = chk.compare(after, before)
    assert diff["resolved"] == ["portal://project/p-nogoal"] and diff["no_worse"]
    assert chk.precheck_line(before).startswith("WORK: 5 of 6 active projects need attention (stalled 2, dead 2, gaps 1;")


def test_cli_out_baseline_and_never_overwrite(tmp_path, capsys):
    out = tmp_path / "health.json"
    assert chk.main(["--as-of", "2026-10-04", "--precheck", "--out", str(out)], client=FakePortal()) == 0
    assert capsys.readouterr().out.startswith("WORK: ")
    data = json.loads(out.read_text())
    assert data["tool"] == "project-health-check" and data["owner_contact_id"] == OWNER
    assert chk.main(["--as-of", "2026-10-04", "--out", str(out)], client=FakePortal()) == 2
    assert chk.main(["--as-of", "2026-10-04", "--precheck", "--baseline", str(out)], client=FakePortal()) == 0
    assert "since 2026-10-04: unhealthy 5 -> 5, 0 resolved" in capsys.readouterr().out


def test_blank_fields_default_bad_numbers_and_stale_portal(capsys):
    assert chk.main(["--max=", "--drain=", "--format", "json"], client=FakePortal()) == 0
    assert json.loads(capsys.readouterr().out)["params"]["max"] == chk.MAX_DEFAULT
    assert chk.main(["--max=lots"], client=FakePortal()) == 2
    assert chk.main(["--precheck"], client=FakePortal(fail=True)) == 0
    assert capsys.readouterr().out.startswith("STALE: ")


def test_last_run_reads_the_setting(tmp_path, monkeypatch, capsys):
    runs = tmp_path / "runs"
    for name in ("project-health-20261005-a", "project-health-20261012-b", "task-clarify-x"):
        (runs / name).mkdir(parents=True)
    (runs / "project-health-20261012-b" / "diagnoses.json").write_text("[]")
    cfg = tmp_path / "settings.toml"
    cfg.write_text(f'[project-health-diagnose]\nruns_dir = "{runs}"\n')
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(cfg))
    assert chk.main(["--last-run"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["run"].endswith("-b") and list(data["files"]) == ["diagnoses.json"]
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "none.toml"))
    assert chk.main(["--last-run"]) == 2


def test_an_unusable_portal_config_is_stale_not_a_crash(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps({"mcpServers": {"insights-portal": {
        "url": "http://portal.example.com/mcp", "headers": {"Authorization": "Bearer x"}}}}))
    settings = tmp_path / "settings.toml"
    settings.write_text(f'portal_mcp_config = "{cfg}"\n')
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(settings))
    monkeypatch.delenv("INSIGHTS_PORTAL_ASSISTANT_TOKEN", raising=False)
    assert chk.main(["--precheck"]) == 0
    assert capsys.readouterr().out.startswith("STALE: ")


def test_a_redirect_is_refused_and_the_token_goes_nowhere_else():
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    import _common as cm
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append((self.path, self.headers.get("Authorization")))
            self.send_response(302)
            self.send_header("Location", "/elsewhere")
            self.end_headers()

        def do_GET(self):
            self.do_POST()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        portal = cm.Portal(f"http://127.0.0.1:{server.server_port}/mcp", "Bearer secret-token")
        try:
            portal.call("whoami")
            raise AssertionError("a redirect was followed")
        except cm.PortalError as exc:
            assert "302" in str(exc) and "secret-token" not in str(exc)
    finally:
        server.shutdown()
    assert [path for path, _ in seen] == ["/mcp"]
