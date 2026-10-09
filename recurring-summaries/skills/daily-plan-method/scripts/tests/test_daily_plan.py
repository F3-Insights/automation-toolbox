"""Tests for daily_plan_pull.py, daily_plan_publish.py and daily_plan_check.py.

No network: the Portal is an in-memory fake answering the calls the scripts make. The data is
invented: Northwind Traders, its owner Dana, Wednesday 2030-03-06 in UTC.
"""

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _common as c  # noqa: E402
import daily_plan_check as chk  # noqa: E402
import daily_plan_publish as pub  # noqa: E402
import daily_plan_pull as pl  # noqa: E402

DAY = date(2030, 3, 6)
TZ = ZoneInfo("UTC")
ME = "dana@example.com"


def uid(n):
    return f"{n:08d}-1111-4000-8000-000000000000"


OWNER, DOM, PROJ, GOAL = uid(900), uid(800), uid(700), uid(600)


def at(hm, day=DAY):
    return datetime(day.year, day.month, day.day, int(hm[:2]), int(hm[3:]), tzinfo=timezone.utc).isoformat()


def event(n, title, start, end, kind="meeting", people=()):
    return {"id": uid(n), "_ref": f"portal://calendar_event/{uid(n)}", "title": title, "start_time": at(start),
            "end_time": at(end), "is_all_day": False, "location": "", "event_kind": kind,
            "attendees": [{"email": e, "name": e.split("@")[0], "response_status": s} for e, s in people]}


EVENTS = [
    event(1, "Team huddle", "09:00", "09:30", people=[(ME, "accepted"), ("sam@example.com", "accepted")]),
    event(2, "Team huddle (Clone)", "09:00", "09:30", kind="availability_block"),
    event(9, "Busy (Org Clone)", "09:00", "09:30", kind="availability_block"),
    event(3, "Supplier review", "11:00", "12:00", people=[(ME, "accepted"), ("priya@example.org", "accepted")]),
    event(4, "Pricing sync", "11:30", "12:00", people=[(ME, "accepted"), ("sam@example.com", "accepted")]),
    event(5, "Focus time", "13:00", "14:30", people=[(ME, "accepted")]),
    event(6, "Errand hold", "15:00", "15:30", kind="availability_block"),
    event(7, "Canceled: Old sync", "16:00", "16:30", people=[(ME, "accepted")]),
    event(8, "Vendor demo", "16:30", "17:00", people=[(ME, "declined"), ("marcus@example.net", "accepted")]),
]


def task(n, title, status="TODO", due=None, priority="P3", **kw):
    row = {"id": uid(n), "title": title, "status": status, "due_date": due, "deadline": None, "priority": priority,
           "project_id": PROJ, "domain_id": DOM, "goal_id": None, "owner_contact_id": OWNER, "description": "",
           "completed_at": None, "waiting_on_name": None}
    row.update(kw)
    return row


TASKS = [
    task(10, "Send the supplier scorecard", due="2030-03-04", priority="P1"),
    task(11, "Approve the freight invoices", due="2030-03-06"),
    task(12, "Chase the customs broker", status="WAITING", due="2030-03-06"),
    task(13, "Tidy the share drive"),
    task(14, "Reply to the auditor", status="DONE", completed_at=at("15:10")),
]


class Fake:
    def __init__(self, notes=None, linked=None):
        self.notes = {n["id"]: n for n in notes or []}
        self.linked = linked or {}
        self.n = 1000

    def rows(self, kind, f):
        if kind == "calendar_event":
            return [e for e in EVENTS if f["since"] <= e["start_time"].replace("+00:00", "Z") < f["until"]]
        if kind == "task":
            rows = [t for t in TASKS if t["status"] == f["status"]] if "status" in f else \
                [t for t in TASKS if t["status"] in ("TODO", "IN_PROGRESS", "WAITING")]
            if "due_before" in f:
                rows = [t for t in rows if t["due_date"] and t["due_date"] <= f["due_before"]]
            if "priority" in f:
                rows = [t for t in rows if t["priority"] == f["priority"]]
            return rows
        if kind == "domain":
            return [{"id": DOM, "name": "Northwind Operations"}]
        if kind == "goal":
            return [{"id": GOAL, "title": "Lift margin", "domain_id": DOM, "status": "active"}]
        if kind == "project":
            return [{"id": PROJ, "name": "Supply", "domain_id": DOM, "goal_id": GOAL}]
        if kind == "note":
            if "entity_id" in f:
                return [{"id": x} for x in self.linked.get(f["entity_id"], [])]
            return []
        return []

    def call(self, tool, args=None):
        args = args or {}
        if tool == "whoami":
            return {"principal": {"contact_id": OWNER, "timezone": "UTC", "primary_email": ME},
                    "inboxes": [{"address": ME}]}
        if tool == "list_entities":
            rows = self.rows(args["entity_type"], args.get("filters") or {})
            off = args.get("offset", 0)
            page = rows[off: off + args.get("limit", 50)]
            return {"items": page, "total": len(rows), "has_more": off + len(page) < len(rows),
                    "next_offset": off + len(page)}
        if tool == "search":
            q = args["query"].strip('"')
            return {"notes": [{"id": n["id"], "title": n["title"]} for n in self.notes.values() if n["title"] == q]}
        if tool == "get":
            note = self.notes.get(args["id_or_query"])
            return dict(note) if note else {"error": "not found"}
        if tool == "create_note":
            self.n += 1
            nid = uid(self.n)
            self.notes[nid] = {"id": nid, "title": args["title"], "content": args["content"], "visibility": "PUBLIC",
                               "created_at": "2030-03-06T07:00:00Z", "updated_at": f"v{self.n}",
                               "tags": args["tag_names"]}
            return {"id": nid}
        if tool == "update_note":
            note = self.notes[args["id"]]
            if args.get("expected_updated_at") and args["expected_updated_at"] != note["updated_at"]:
                raise RuntimeError("stale")
            note.update(args["fields"])
            self.n += 1
            note["updated_at"] = f"v{self.n}"
            return {"id": note["id"]}
        raise AssertionError(tool)


OWNER_INFO = {"contact_id": OWNER, "timezone": "UTC", "addresses": [ME], "internal_domains": ["example.com"]}


def morning_plan(**kw):
    plan = {"tool": "daily-plan", "version": 1, "date": DAY.isoformat(), "pass": "morning", "dry_run": False,
            "summary": "A supplier day.",
            "top_three": [{"rank": 1, "title": "Send the supplier scorecard", "ref": f"portal://task/{uid(10)}",
                           "reason": "Overdue and P1", "slot": {"start": "09:30", "end": "11:00"}}],
            "conflicts": [{"a": f"portal://calendar_event/{uid(3)}", "b": f"portal://calendar_event/{uid(4)}",
                           "when": "11:30-12:00", "suggest": "Move the sync"}],
            "prep": [{"ref": f"portal://calendar_event/{uid(3)}", "title": "Supplier review", "when": "11:00",
                      "state": "needs prep", "suggest": "Read last quarter's scorecard"}]}
    plan.update(kw)
    return plan


@pytest.fixture(autouse=True)
def no_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "none.toml"))


# --------------------------------------------------------------------------- pull

def test_calendar_cleanup_conflicts_and_free_time():
    cal = pl.day_calendar(EVENTS, DAY, TZ, OWNER_INFO, ((8, 0), (17, 30)), 60, pl.FOCUS_TITLE)
    assert cal["dropped"] == {"cancelled": 1, "declined": 1, "duplicate": 1, "clone": 1}
    kinds = {e["title"]: e["kind"] for e in cal["events"]}
    assert kinds["Focus time"] == "focus" and kinds["Errand hold"] == "hold"
    assert [(x["a_title"], x["b_title"]) for x in cal["conflicts"]] == [("Supplier review", "Pricing sync")]
    review = next(e for e in cal["events"] if e["title"] == "Supplier review")
    assert review["external"] and review["external_domains"] == ["example.org"]
    assert [(f["start"], f["end"]) for f in cal["free"]] == [("08:00", "09:00"), ("09:30", "11:00"), ("12:00", "15:00"), ("15:30", "17:30")]
    assert cal["free"][2]["focus_blocks"] == ["Focus time"]


def test_morning_pull_lenses_and_prep():
    out = pl.build(Fake(), DAY, "morning", ((8, 0), (17, 30)), 60, pl.FOCUS_TITLE, 7, 150, [], None)
    lenses = {t["title"]: t["lenses"] for t in out["tasks"]}
    assert lenses["Send the supplier scorecard"] == ["overdue", "p1"]
    assert lenses["Approve the freight invoices"] == ["due_today"]
    assert lenses["Chase the customs broker"] == ["waiting_due"]
    assert "Tidy the share drive" not in lenses
    assert [m["title"] for m in out["calendar"]["needs_prep"]] == ["Supplier review"]
    assert out["note"] == {"exists": False}


def test_evening_pull_reads_the_morning_plan_from_state(tmp_path):
    (tmp_path / DAY.isoformat()).mkdir()
    (tmp_path / DAY.isoformat() / "morning.json").write_text(json.dumps(morning_plan()))
    out = pl.build(Fake(), DAY, "evening", ((8, 0), (17, 30)), 60, pl.FOCUS_TITLE, 7, 150, [], tmp_path)
    assert out["morning_plan"]["source"] == "state"
    assert [t["title"] for t in out["done_today"]] == ["Reply to the auditor"]
    assert out["tomorrow"]["date"] == "2030-03-07"


def test_pull_cli_is_stale_when_the_portal_is_down(capsys):
    with pytest.raises(SystemExit) as e:
        pl.main(["--date", "2030-03-06", "--pass", "morning"])
    assert e.value.code == 0 and capsys.readouterr().out.startswith("STALE:")


def test_pull_cli_refuses_bad_arguments():
    for argv in (["--work-start", "9am"], ["--pass", "noon"], ["--min-focus", "x"]):
        with pytest.raises(SystemExit) as e:
            pl.main(argv)
        assert e.value.code == 2


def test_pull_cli_writes_the_pull(tmp_path, capsys):
    with pytest.raises(SystemExit) as e:
        pl.main(["--date", "2030-03-06", "--pass", "morning", "--out", str(tmp_path / "pull.json")], client=Fake())
    assert e.value.code == 0 and capsys.readouterr().out.startswith("FRESH: 2030-03-06 morning")
    assert json.loads((tmp_path / "pull.json").read_text())["tool"] == "daily-plan-pull"


# --------------------------------------------------------------------------- publish

def run_publish(tmp_path, fake, plan, *extra):
    run = tmp_path / "run"
    run.mkdir(exist_ok=True)
    (run / "plan.json").write_text(json.dumps(plan))
    with pytest.raises(SystemExit) as e:
        pub.main(["--run", str(run), "--state", str(tmp_path / "state"), *extra], client=fake)
    return e.value.code, run


def test_publish_creates_a_private_note_and_keeps_state(tmp_path, capsys):
    fake = Fake()
    code, run = run_publish(tmp_path, fake, morning_plan())
    result = json.loads(capsys.readouterr().out)
    assert code == 0 and result["status"] == "created"
    note = next(iter(fake.notes.values()))
    assert note["visibility"] == "PRIVATE" and note["tags"] == ["briefing", "daily-plan"]
    assert c.day_marker(DAY) in note["content"] and (run / "plan.md").exists()
    saved = json.loads((tmp_path / "state" / DAY.isoformat() / "morning.json").read_text())
    assert saved["published"]["block_hash"] == result["block_hash"]


def test_publish_rerun_replaces_own_block_and_appends_after_a_hand_edit(tmp_path, capsys):
    fake = Fake()
    run_publish(tmp_path, fake, morning_plan())
    capsys.readouterr()
    run_publish(tmp_path, fake, morning_plan(summary="Changed."))
    assert json.loads(capsys.readouterr().out)["status"] == "replaced"
    note = next(iter(fake.notes.values()))
    note["content"] = note["content"].replace("Changed.", "Dana's own words.")
    run_publish(tmp_path, fake, morning_plan(summary="Again."))
    assert json.loads(capsys.readouterr().out)["status"] == "appended"
    assert "Dana's own words." in note["content"] and len(c.blocks(note["content"], "morning")) == 2


def test_dry_run_writes_nothing_and_a_dry_plan_is_never_live(tmp_path, capsys):
    fake = Fake()
    code, _ = run_publish(tmp_path, fake, morning_plan(), "--dry-run")
    assert code == 0 and json.loads(capsys.readouterr().out)["status"] == "would_created" and not fake.notes
    code, _ = run_publish(tmp_path, fake, morning_plan(dry_run=True))
    assert code == 3 and json.loads(capsys.readouterr().out)["code"] == "DRY_RUN"


def test_compose_puts_a_morning_before_an_existing_evening():
    content = pub.new_content(DAY, "evening", "## Evening close\n\nDone.")
    out, action = pub.compose(content, DAY, "morning", "## Morning plan\n\nPlan.", None, "08:00")
    assert action == "added" and out.index("daily-plan:morning") < out.index("daily-plan:evening")


# --------------------------------------------------------------------------- check

def write_run(tmp_path, plan, pull=None, changes=None):
    run = tmp_path / "run"
    run.mkdir(exist_ok=True)
    (run / "plan.json").write_text(json.dumps(plan))
    if pull is not None:
        (run / "pull.json").write_text(json.dumps(pull))
    if changes is not None:
        (run / "changes.json").write_text(json.dumps(changes))
    return run


def morning_pull():
    return pl.build(Fake(), DAY, "morning", ((8, 0), (17, 30)), 60, pl.FOCUS_TITLE, 7, 150, [], None)


def test_morning_check_passes_a_complete_plan(tmp_path):
    run = write_run(tmp_path, morning_plan(), morning_pull())
    result = chk.check(DAY, "morning", run, None, None, True)
    assert result["done"], result["tests"]


def test_morning_check_finds_the_gaps(tmp_path):
    plan = morning_plan(top_three=[{"title": "Send", "ref": "x", "slot": {"start": "11:00", "end": "11:45"}}],
                        conflicts=[], prep=[])
    result = chk.check(DAY, "morning", write_run(tmp_path, plan, morning_pull()), None, None, True)
    gaps = result["tests"]["top-three"]["gaps"] + result["tests"]["conflicts"]["gaps"]
    assert any("no reason" in g for g in gaps) and any("overlaps Supplier review" in g for g in gaps)
    assert any("conflict 11:30-12:00 not listed" in g for g in gaps)
    assert any("without prep not listed" in g for g in gaps)


def test_evening_check_wants_outcomes_evidence_ops_and_tomorrow(tmp_path):
    pull = {"morning_plan": {"top_three": morning_plan()["top_three"]}}
    plan = {"tool": "daily-plan", "version": 1, "date": DAY.isoformat(), "pass": "evening", "dry_run": False,
            "close": {"items": [{"ref": f"portal://task/{uid(10)}", "title": "Send the supplier scorecard",
                                 "outcome": "moved", "new_date": "2030-03-07", "op": "e1"}], "tomorrow": []}}
    result = chk.check(DAY, "evening", write_run(tmp_path, plan, pull, {"ops": []}), None, None, True)
    gaps = result["tests"]["close"]["gaps"]
    assert any("no edit op setting that due date" in g for g in gaps)
    assert "tomorrow's three are not named" in gaps
    plan["close"]["tomorrow"] = [{"title": "Approve the freight invoices"}]
    changes = {"ops": [{"id": "e1", "op": "edit", "task": f"portal://task/{uid(10)}", "set": {"due_date": "2030-03-07"}}]}
    result = chk.check(DAY, "evening", write_run(tmp_path, plan, pull, changes), None, None, True)
    assert result["done"], result["tests"]


def test_precheck_lines():
    monday = date(2030, 3, 4)
    late = datetime(2030, 3, 4, 7, 0, tzinfo=TZ)
    assert chk.precheck(date(2030, 3, 9), "morning", late, (6, 30), (18, 0), None).startswith("NOTHING")
    assert chk.precheck(monday, "evening", late, (6, 30), (18, 0), None).startswith("NOTHING: the evening")
    assert chk.precheck(monday, "morning", late, (6, 30), (18, 0), {"has_morning": True, "ref": "r"}).startswith("NOTHING")
    assert chk.precheck(monday, "morning", late, (6, 30), (18, 0), {"has_morning": False}).startswith("WORK")


def test_check_cli_offline_with_a_run_takes_its_date_and_pass(tmp_path, capsys):
    run = write_run(tmp_path, morning_plan(), morning_pull())
    with pytest.raises(SystemExit) as e:
        chk.main(["--run", str(run), "--offline", "--tz", "UTC", "--format", "json"])
    out = json.loads(capsys.readouterr().out)
    assert e.value.code == 0 and out["date"] == DAY.isoformat() and out["pass"] == "morning" and out["done"]


def test_a_run_inside_the_skill_folder_is_refused():
    with pytest.raises(c.Stop):
        c.guard_run_path(str(c.SKILL_DIR / "scripts"))


# --------------------------------------------------------------------------- guards

class StaysPublic(Fake):
    """A Portal that accepts the visibility change but keeps the note public."""

    def call(self, tool, args=None):
        if tool == "update_note":
            args = dict(args, fields={k: v for k, v in args["fields"].items() if k != "visibility"})
        return super().call(tool, args)


def test_a_note_that_reads_back_public_is_refused_and_no_state_is_kept(tmp_path, capsys):
    code, _ = run_publish(tmp_path, StaysPublic(), morning_plan())
    result = json.loads(capsys.readouterr().out)
    assert code == 3 and result["code"] == "NOT_PRIVATE"
    assert not (tmp_path / "state" / DAY.isoformat() / "morning.json").exists()


def portal_config(tmp_path, url, auth="Bearer abc"):
    path = tmp_path / "mcp.json"
    path.write_text(json.dumps({"mcpServers": {"insights-portal": {"url": url, "headers": {"Authorization": auth}}}}))
    return str(path)


def test_the_portal_must_be_https_except_on_localhost(tmp_path, monkeypatch):
    monkeypatch.delenv("INSIGHTS_PORTAL_ASSISTANT_TOKEN", raising=False)
    with pytest.raises(c.PortalError, match="HTTPS"):
        c.portal_endpoint(portal_config(tmp_path, "http://portal.example.com/mcp"))
    assert c.portal_endpoint(portal_config(tmp_path, "http://127.0.0.1:9/mcp"))[0].startswith("http://127.0.0.1")
    with pytest.raises(c.PortalError, match="bearer"):
        c.portal_endpoint(portal_config(tmp_path, "https://portal.example.com/mcp", auth=""))


def test_a_redirect_is_refused_so_the_token_never_leaves(tmp_path, monkeypatch):
    import http.server
    import threading

    seen = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append((self.path, self.headers.get("Authorization")))
            self.send_response(307)
            self.send_header("Location", "/elsewhere")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        monkeypatch.delenv("INSIGHTS_PORTAL_ASSISTANT_TOKEN", raising=False)
        client = c.Portal(portal_config(tmp_path, f"http://127.0.0.1:{server.server_port}/mcp"))
        with pytest.raises(c.PortalError, match="307"):
            client.call("whoami")
    finally:
        server.shutdown()
    assert seen == [("/mcp", "Bearer abc")]
