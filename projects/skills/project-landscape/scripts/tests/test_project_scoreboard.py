"""The scoreboard's arithmetic against an in-memory Portal. No network; the date is pinned."""

import json
from datetime import datetime, timezone

import pytest

import _common as cm
import project_scoreboard as sb

NOW = datetime(2026, 9, 19, 12, tzinfo=timezone.utc)
DOMAINS = [{"id": "dom-acme", "name": "Acme Components"}, {"id": "dom-nw", "name": "Northwind Traders"}]
GOALS = [{"id": "goal-1", "title": "Close the books on time"}]


class FakePortal:
    def __init__(self, projects=(), tasks=(), poison=(), fail=None):
        self.rows = {"domain": DOMAINS, "goal": GOALS, "project": list(projects), "task": list(tasks)}
        self.poison, self.fail, self.calls = set(poison), fail, 0

    def call(self, tool, arguments=None):
        self.calls += 1
        if self.fail:
            raise self.fail
        args = arguments or {}
        offset, size = int(args.get("offset") or 0), int(args.get("limit") or 200)
        rows = self.rows[args["entity_type"]]
        window = rows[offset:offset + size]
        if args["entity_type"] == "task" and any(i in self.poison for i in range(offset, offset + len(window))):
            raise RuntimeError("validation error")
        return {"items": window, "total": len(rows), "has_more": offset + len(window) < len(rows),
                "next_offset": offset + len(window)}


def project(pid="p1", name="Board reporting", domain_id="dom-acme", **kw):
    row = {"id": pid, "name": name, "domain_id": domain_id, "goal_id": "goal-1", "status": "IN_PROGRESS",
           "priority": "P2", "is_archived": False, "is_general": False, "assignee_contact_id": None,
           "created_at": "2026-09-01T00:00:00Z", "updated_at": "2026-09-18T00:00:00Z"}
    row.update(kw)
    return row


def task(tid="t1", project_id="p1", **kw):
    row = {"id": tid, "project_id": project_id, "title": "Draft the deck", "status": "TODO", "priority": "P2",
           "due_date": None, "owner_contact_id": "c-1", "created_at": "2026-09-10T00:00:00Z",
           "updated_at": "2026-09-18T00:00:00Z", "completed_at": None, "is_archived": False}
    row.update(kw)
    return row


def board(projects, tasks=(), **kw):
    corpus, _ = sb.read_corpus(FakePortal(projects, tasks))
    return sb.build(corpus, NOW, **kw)


def only(result):
    assert len(result["projects"]) == 1
    return result["projects"][0]


def test_tasks_grouped_and_names_joined():
    r = only(board([project()], [task(), task("t2"), task("t3", project_id=None)]))
    assert r["mechanical"]["load"]["total_tasks"] == 2
    assert r["domain"] == "Acme Components" and r["goal"] == "Close the books on time"


def test_closed_and_general_projects_are_not_scored():
    r = board([project(), project("p2", status="COMPLETED"), project("p3", is_general=True)])
    assert [p["project_id"] for p in r["projects"]] == ["p1"]


def test_deadline_pressure_bands_and_overdue_p1():
    soon = [task(f"t{i}", due_date="2026-09-22") for i in range(2)]
    assert only(board([project()], soon))["components"]["deadline"] == 50
    late = [task("t1", due_date="2026-09-10", priority="P1")]
    r = only(board([project()], late))
    assert r["components"]["deadline"] == 100 and "OVERDUE" in r["flags"]


@pytest.mark.parametrize("updated,score", [("2026-09-18", 0), ("2026-09-08", 25), ("2026-08-25", 50),
                                           ("2026-08-01", 75), ("2026-06-01", 100)])
def test_staleness_bands(updated, score):
    p = project(updated_at=updated, created_at=updated)
    assert only(board([p]))["components"]["staleness"] == score


def test_risk_counts_cap_and_mechanical_score():
    tasks = [task(f"o{i}", due_date="2026-09-01", priority="P3") for i in range(4)]
    r = only(board([project()], tasks))
    assert r["mechanical"]["load"]["risk_from_counts"] == 100
    assert r["components"]["risk"] is None
    assert r["mechanical_score"] == round(0 * 0.2 + 0 * 0.2 + 100 * 0.15, 1)


def test_owner_from_tasks_and_flags():
    r = only(board([project(goal_id=None)], [task(owner_contact_id=None)]))
    assert {"NO_OWNER", "NO_GOAL", "NO_NEXT_TASK"} <= set(r["flags"])
    assert not only(board([project(assignee_contact_id="c-9")]))["flags"].count("NO_OWNER")


def test_sort_limit_and_domain_filter():
    ps = [project("a", "Alpha"), project("b", "Beta", domain_id="dom-nw", updated_at="2026-06-01",
                                         created_at="2026-06-01")]
    r = board(ps)
    assert [p["name"] for p in r["projects"]] == ["Beta", "Alpha"]
    assert board(ps, limit=1)["matched"] == 2
    assert [p["name"] for p in board(ps, domain="northwind")["projects"]] == ["Beta"]


def test_a_bad_row_costs_one_row_and_no_rows_is_an_error():
    tasks = [task(f"t{i}") for i in range(5)]
    corpus, unreadable = sb.read_corpus(FakePortal([project()], tasks, poison={2}))
    assert len(corpus["task"]) == 4 and unreadable == {"task": 1}
    with pytest.raises(cm.PortalError):
        sb.read_corpus(FakePortal(fail=RuntimeError("down")))


def test_cli_json_markdown_and_errors(capsys):
    fake = FakePortal([project()], [task()])
    assert sb.main(["--json", "--as-of", "2026-09-19"], client=fake) == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows[0]["project_id"] == "p1" and rows[0]["mechanical_score_max"] == 55
    assert sb.main(["--as-of", "2026-09-19", "--explain"], client=FakePortal([project()])) == 0
    out = capsys.readouterr()
    assert out.out.startswith("# Project scoreboard, 2026-09-19") and "keys seen on project" in out.err
    assert sb.main(["--as-of", "soon"], client=fake) == 2
    assert sb.main([], client=FakePortal(fail=RuntimeError("down"))) == 2


def test_missing_setting_exits_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "none.toml"))
    assert sb.main([]) == 2
    assert "portal_mcp_config" in capsys.readouterr().err


def test_endpoint_reads_config_and_never_prints_the_token(tmp_path, monkeypatch):
    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps({"mcpServers": {"insights-portal": {
        "url": "https://portal.example.com/mcp", "headers": {"Authorization": "Bearer ${PORTAL_TEST_TOKEN}"}}}}))
    monkeypatch.delenv("INSIGHTS_PORTAL_ASSISTANT_TOKEN", raising=False)
    monkeypatch.setenv("PORTAL_TEST_TOKEN", "abc123")
    assert cm.portal_endpoint(str(cfg)) == ("https://portal.example.com/mcp", "Bearer abc123")
    assert "abc123" not in cm.safe("failed with Bearer abc123")
    cfg.write_text(json.dumps({"mcpServers": {"insights-portal": {
        "url": "http://portal.example.com/mcp", "headers": {"Authorization": "Bearer x"}}}}))
    with pytest.raises(cm.PortalError):
        cm.portal_endpoint(str(cfg))


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
