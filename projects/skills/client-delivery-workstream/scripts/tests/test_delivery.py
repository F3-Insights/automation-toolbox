"""Client delivery scripts against an invented engagement (Northwind Traders)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import _common as dc  # noqa: E402
import delivery_apply as ap  # noqa: E402
import delivery_check as ck  # noqa: E402
import delivery_pack as pk  # noqa: E402
import delivery_record as rec  # noqa: E402

NAME = "northwind-delivery"
TODAY = "2026-10-05"
DOMAIN = "11111111-1111-4111-8111-111111111111"
OWNER = "22222222-2222-4222-8222-222222222222"
TEAMMATE = "33333333-3333-4333-8333-333333333333"
STRANGER = "44444444-4444-4444-8444-444444444444"
PROJECT = "55555555-5555-4555-8555-555555555555"
OTHER_PROJECT = "66666666-6666-4666-8666-666666666666"
TASK_A = "77777777-7777-4777-8777-777777777777"
TASK_B = "88888888-8888-4888-8888-888888888888"
TASK_OUT = "99999999-9999-4999-8999-999999999999"

RULES = f"""# Northwind Traders delivery rules

## Delivery inputs

- Portal domain: {DOMAIN}
- SOW: {{sow}}
- Lead time days: 10
- RAID review days: 14
- Assignable: {TEAMMATE} (Priya, the build lead)
- Client email domains: example.com
- Source folders: Transcripts
- Never open: *.csv

## Scope baseline

| Id | Deliverable | Due | Acceptance |
|---|---|---|---|
| M1 | Freight costing model | 2026-10-09 | The controller signs off the model |
| M2 | Margin dashboard | 2026-11-13 | Used in the November review |
"""

PLAN = """# Plan

## Milestones

| Id | Milestone | Owner | Baseline due | Planned due | Client date | Acceptance | Source |
|---|---|---|---|---|---|---|---|
| M1 | Freight costing model | owner | 2026-10-09 | 2026-10-09 | yes | Controller sign-off | SOW 2 |
| M2 | Margin dashboard | Priya | 2026-11-13 | 2026-11-13 | yes | Used in the November review | SOW 3 |
"""


def northwind(tmp, sow="missing", plan=True):
    contexts, rules, working, general = (tmp / "contexts", tmp / "rules", tmp / "Northwind" / "Delivery",
                                         tmp / "Northwind" / "General")
    for folder in (contexts, rules, working, general / "Transcripts"):
        folder.mkdir(parents=True, exist_ok=True)
    (rules / "DELIVERY-RULES.md").write_text(RULES.replace("{sow}", sow), encoding="utf-8")
    if plan:
        (working / "PLAN.md").write_text(PLAN, encoding="utf-8")
    (contexts / f"{NAME}.yaml").write_text(
        f"name: {NAME}\nsources:\n  - {{name: rules, path: {rules}}}\n  - {{name: working, path: {working}}}\n"
        f"  - {{name: engagement-general, path: {general}}}\n", encoding="utf-8")
    return {"contexts": contexts, "rules": rules, "working": working, "general": general}


def record(paths, *args, as_of=TODAY):
    return rec.main([NAME, args[0], f"--contexts-dir={paths['contexts']}", f"--as-of={as_of}", *args[1:]])


def check(paths, *extra, capsys):
    capsys.readouterr()
    assert ck.main([NAME, f"--contexts-dir={paths['contexts']}", f"--as-of={TODAY}", "--format=json", *extra]) == 0
    return json.loads(capsys.readouterr().out)


def test_rules_and_a_missing_sow_is_an_owner_question(tmp_path, capsys):
    paths = northwind(tmp_path)
    eng = dc.load_engagement(NAME, str(paths["contexts"]))
    assert eng["rules"]["assignable"] == [TEAMMATE] and [b["id"] for b in eng["rules"]["baseline"]] == ["M1", "M2"]
    res = check(paths, capsys=capsys)
    assert not res["tests"]["sow"]["met"] and res["tests"]["sow"]["question"]


def test_contexts_dir_comes_from_the_setting(tmp_path, monkeypatch):
    paths = northwind(tmp_path)
    settings = tmp_path / "settings.toml"
    settings.write_text(f'contexts_dir = "{paths["contexts"]}"\n', encoding="utf-8")
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(settings))
    assert dc.load_engagement(NAME)["name"] == NAME
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "none.toml"))
    with pytest.raises(dc.Bad, match="contexts_dir"):
        dc.load_engagement(NAME)


def test_sow_on_disk_and_none(tmp_path, capsys):
    paths = northwind(tmp_path, sow="sow/SOW.txt")
    assert not check(paths, capsys=capsys)["tests"]["sow"]["met"]
    (paths["rules"] / "sow").mkdir()
    (paths["rules"] / "sow" / "SOW.txt").write_text("Scope", encoding="utf-8")
    assert check(paths, capsys=capsys)["tests"]["sow"]["met"]
    other = northwind(tmp_path / "b", sow="none (the owner confirmed)")
    assert check(other, capsys=capsys)["tests"]["sow"]["state"] == "none"


def test_plan_must_carry_every_baseline_milestone(tmp_path, capsys):
    paths = northwind(tmp_path)
    (paths["working"] / "PLAN.md").write_text("\n".join(l for l in PLAN.splitlines() if "| M2 |" not in l))
    assert any("baseline M2" in g for g in check(paths, capsys=capsys)["tests"]["plan"]["gaps"])


def test_lead_time_late_and_client_date_changes(tmp_path, capsys):
    paths = northwind(tmp_path)
    assert "M1" in check(paths, capsys=capsys)["tests"]["milestones"]["gaps"][0]
    assert record(paths, "milestone", "--id=M1", "--state=in-progress", "--evidence=portal://note/x") == 0
    assert check(paths, capsys=capsys)["tests"]["milestones"]["met"]
    late = check(paths, "--as-of=2026-10-12", capsys=capsys)
    assert any("was due 2026-10-09" in g for g in late["tests"]["milestones"]["gaps"])
    assert record(paths, "change", "--id=C1", "--milestone=M1", "--to=2026-10-23", "--state=proposed",
                  "--reason=The controller is away") == 0
    res = check(paths, "--as-of=2026-10-12", capsys=capsys)
    assert res["tests"]["milestones"]["met"] and res["tests"]["changes"]["waiting_on_owner"]
    (paths["working"] / "PLAN.md").write_text(PLAN.replace("| 2026-10-09 | 2026-10-09 |", "| 2026-10-09 | 2026-10-23 |"))
    assert not check(paths, "--as-of=2026-10-12", capsys=capsys)["tests"]["changes"]["met"]
    assert record(paths, "change", "--id=C1", "--milestone=M1", "--to=2026-10-23", "--state=approved",
                  "--reason=The controller is away", "--source=CONFIRMATIONS.md Q2") == 0
    assert check(paths, "--as-of=2026-10-12", capsys=capsys)["tests"]["changes"]["met"]
    rows = dc.evidence_ledger(paths["working"]).rows()
    assert [r for r in rows if r["id"] == "change:C1"][0]["note"].startswith("from 2026-10-09: ")


def test_record_refuses_what_breaks_the_contract(tmp_path):
    paths = northwind(tmp_path)
    assert record(paths, "milestone", "--id=M9", "--state=planned") == 1
    assert record(paths, "milestone", "--id=M1", "--state=delivered") == 1
    assert record(paths, "milestone", "--id=M1", "--state=accepted", "--evidence=x") == 1
    assert record(paths, "milestone", "--id=M1", "--state=approved", "--evidence=x") == 1
    assert record(paths, "change", "--id=C1", "--milestone=M1", "--to=2026-10-23", "--state=approved",
                  "--reason=late") == 1
    assert not (paths["working"] / "DELIVERY-EVIDENCE.csv").exists()


def test_raid_ids_review_dates_and_all_or_nothing(tmp_path, capsys):
    paths = northwind(tmp_path)
    good = tmp_path / "raid.json"
    good.write_text(json.dumps({"extra": {"raid": [
        {"type": "risk", "title": "Controller away", "owner": "owner", "source": "S004"},
        {"type": "dependency", "title": "ERP export", "owner": "Marcus", "source": "S007", "review_by": "2026-10-08"}]}}))
    assert record(paths, "raid", f"--from={good}") == 0
    rows = dc.raid_ledger(paths["working"]).rows()
    assert [r["id"] for r in rows] == ["R1", "D1"] and rows[0]["review_by"] == "2026-10-19"
    assert check(paths, capsys=capsys)["tests"]["raid"]["met"]
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([{"type": "risk", "title": "Fine", "owner": "o", "source": "S1"},
                               {"type": "risk", "title": "No owner", "source": "S2"}]))
    assert record(paths, "raid", f"--from={bad}") == 1
    assert len(dc.raid_ledger(paths["working"]).rows()) == 2


def test_ledger_keeps_other_rows_byte_for_byte(tmp_path):
    paths = northwind(tmp_path)
    ledger = paths["working"] / "RAID.csv"
    head = ",".join(dc.RAID_COLUMNS)
    ledger.write_bytes(("﻿" + head + "\r\nR1,risk,\"Two\nlines\",o,2026-10-01,2026-10-20,open,,S1,,,,\r\n").encode())
    original = ledger.read_bytes()
    raw = tmp_path / "r.json"
    raw.write_text(json.dumps([{"type": "issue", "title": "Late data", "owner": "Sam", "source": "S2"}]))
    assert record(paths, "raid", f"--from={raw}") == 0
    assert ledger.read_bytes().startswith(original)


def test_session_and_precheck(tmp_path, capsys):
    paths = northwind(tmp_path, plan=False)
    capsys.readouterr()
    ck.main([NAME, f"--contexts-dir={paths['contexts']}", f"--as-of={TODAY}", "--precheck"])
    assert capsys.readouterr().out.startswith("WORK:")
    paths = northwind(tmp_path / "b")
    record(paths, "milestone", "--id=M1", "--state=in-progress", "--evidence=portal://note/x")
    record(paths, "session", "--mode=plan")
    capsys.readouterr()
    ck.main([NAME, f"--contexts-dir={paths['contexts']}", f"--as-of={TODAY}", "--precheck"])
    assert capsys.readouterr().out.startswith("NOTHING:")
    ck.main([NAME, f"--contexts-dir={paths['contexts']}", "--as-of=2026-10-09", "--precheck"])
    assert "last session 2026-10-05" in capsys.readouterr().out


class FakePortal:
    def call(self, tool, args=None):
        if tool == "whoami":
            return {"principal": {"contact_id": OWNER}}
        filters = args["filters"]
        if args["entity_type"] == "project":
            items = [{"id": PROJECT, "name": "Freight costing", "status": "IN_PROGRESS"}]
        elif filters.get("project_id") == PROJECT:
            items = [{"id": TASK_A, "title": "Send the costing model", "status": "TODO", "owner_contact_id": OWNER}]
        elif filters.get("status") == "TODO":
            items = [{"id": TASK_B, "title": "Book the review", "status": "TODO", "due_date": "2026-10-07"}]
        else:
            items = []
        return {"items": items, "total": len(items), "has_more": False}


FAKE_COLLECT = """import json, sys
out = sys.argv[sys.argv.index("--out") + 1]
json.dump({"items": [
  {"kind": "meeting", "ref": "portal://note/m1", "title": "Weekly with the controller",
   "occurred_at": "2026-10-01", "text": "Model review moved", "counterparties": ["dana@example.com"]},
  {"kind": "mail", "ref": "portal://email/e1", "title": "Newsletter", "counterparties": ["x@mail.test"]}]},
  open(out, "w"))
"""


@pytest.fixture
def run(tmp_path, monkeypatch):
    fake = tmp_path / "fake_collect.py"
    fake.write_text(FAKE_COLLECT)
    monkeypatch.setattr(pk, "REPORT_COLLECT", fake)
    paths = northwind(tmp_path)
    (paths["general"] / "Transcripts" / "call 2026-10-01.txt").write_text("call")
    (paths["general"] / "Transcripts" / "numbers.csv").write_text("a,b")
    record(paths, "session", "--mode=check", as_of="2026-09-28")
    run_dir = tmp_path / "run"
    assert pk.main([NAME, f"--run-dir={run_dir}", f"--contexts-dir={paths['contexts']}", f"--as-of={TODAY}",
                    "--mode=", "--dry-run-if=true"], portal=FakePortal()) == 0
    return paths, run_dir


def test_pack_gathers_the_engagement_on_a_dry_run_copy(run, capsys):
    paths, run_dir = run
    pack = json.loads((run_dir / "delivery" / "pack.json").read_text())
    assert pk.render(pack).startswith("FRESH: 2 sources, 2 open tasks")
    assert pack["mode"] == "plan" and pack["since"] == "2026-09-28" and pack["dry_run"]
    assert (run_dir / "delivery" / "working" / "PLAN.md").is_file()
    assert [s["role"] for s in pack["sources"]] == ["folder", "portal"]
    assert {g["id"] for g in pack["tasks"]["gaps"]} == {TASK_A, TASK_B} and pack["owner_contact"] == OWNER
    assert (run_dir / "delivery" / "check-before.json").is_file() and pack["check_before"]["of"] == 8
    record(paths, "session", "--mode=plan", f"--working={pack['folders']['working']}")
    assert dc.latest_session(dc.evidence_ledger(paths["working"]).rows()).isoformat() == "2026-09-28"


def test_milestone_review_needs_a_milestone(tmp_path):
    paths = northwind(tmp_path)
    assert pk.main([NAME, f"--run-dir={tmp_path / 'r'}", f"--contexts-dir={paths['contexts']}",
                    "--mode=milestone-review", "--no-portal"]) == 2


CHANGES = {"tool": "task-stack-changes", "version": 1, "dry_run": True, "questions": [], "ops": [
    {"id": "e1", "op": "edit", "task": f"portal://task/{TASK_A}", "set": {"due_date": "2026-10-08"}, "reason": "r"},
    {"id": "e2", "op": "edit", "task": TASK_B, "set": {"owner_contact_id": TEAMMATE}, "reason": "Priya books it"},
    {"id": "n1", "op": "create", "title": "Draft the spec", "project": PROJECT, "owner": STRANGER, "reason": "r"},
    {"id": "n2", "op": "create", "title": "File the invoice", "project": OTHER_PROJECT, "reason": "r"},
    {"id": "x1", "op": "cancel", "task": TASK_OUT, "reason": "r"},
    {"id": "p1", "op": "project_close", "project": PROJECT, "status": "COMPLETED", "reason": "r"}]}


def test_authority_gaps(run, capsys):
    paths, run_dir = run
    (run_dir / "changes.json").write_text(json.dumps(CHANGES))
    res = check(paths, f"--pack={run_dir}", capsys=capsys)
    assert sorted(g.split(":")[0] for g in res["tests"]["authority"]["gaps"]) == ["n1", "n2", "p1", "x1"]
    assert res["tests"]["tasks"]["met"]


FAKE_APPLY = """import json, sys
args = sys.argv[1:]
data = json.load(open(args[0]))
out = args[args.index("--out") + 1]
json.dump({"tool": "task-stack-apply", "status": "would_apply", "seen": [o["id"] for o in data["ops"]],
           "questions": len(data["questions"]), "domain": args[args.index("--domain") + 1],
           "dry": "--dry-run" in args}, open(out, "w"))
"""


def test_apply_gates_then_hands_the_rest_to_task_stack_apply(run, tmp_path, monkeypatch, capsys):
    paths, run_dir = run
    fake = tmp_path / "fake_apply.py"
    fake.write_text(FAKE_APPLY)
    monkeypatch.setattr(ap, "TASK_STACK_APPLY", fake)
    (run_dir / "changes.json").write_text(json.dumps(CHANGES))
    assert ap.main([NAME, f"--run-dir={run_dir}", f"--contexts-dir={paths['contexts']}",
                    "--dry-run-if=true", "--max-changes="]) == 0
    written = json.loads((run_dir / "apply-dry-run.json").read_text())
    assert written["seen"] == ["e1", "e2"] and written["questions"] == 4
    assert written["domain"] == DOMAIN and written["dry"]
    assert [g["id"] for g in written["gated"]] == ["n1", "n2", "x1", "p1"]


def test_apply_with_no_change_set_is_nothing(run, capsys):
    paths, run_dir = run
    capsys.readouterr()
    assert ap.main([NAME, f"--run-dir={run_dir}", f"--contexts-dir={paths['contexts']}", "--dry-run"]) == 0
    assert '"nothing"' in capsys.readouterr().out


# --------------------------------------------------------------------------- the Portal guards

def portal_settings(tmp_path, monkeypatch, url, header="Bearer config-secret-token"):
    conf = tmp_path / "mcp.json"
    conf.write_text(json.dumps({"mcpServers": {"insights-portal": {
        "url": url, "headers": {"Authorization": header}}}}), encoding="utf-8")
    settings = tmp_path / "settings.toml"
    settings.write_text(f'portal_mcp_config = "{conf}"\n', encoding="utf-8")
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(settings))
    monkeypatch.delenv("INSIGHTS_PORTAL_ASSISTANT_TOKEN", raising=False)


def test_portal_refuses_plain_http_off_localhost(tmp_path, monkeypatch):
    portal_settings(tmp_path, monkeypatch, "http://portal.example.com/mcp")
    with pytest.raises(dc.Bad, match="HTTPS"):
        pk.Portal()


def test_portal_never_follows_a_redirect(tmp_path, monkeypatch):
    import http.server
    import threading

    hits = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            hits.append(self.path)
            self.send_response(302)
            self.send_header("Location", "/elsewhere")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        portal_settings(tmp_path, monkeypatch, f"http://127.0.0.1:{server.server_port}/mcp")
        with pytest.raises(RuntimeError) as err:
            pk.Portal().call("whoami")
    finally:
        server.shutdown()
    assert hits == ["/mcp"] and "302" in str(err.value) and "config-secret-token" not in str(err.value)


def test_error_text_is_redacted_of_every_credential_shape():
    for leak in ("Authorization: Bearer abc123secret", "authorization=abc123secret",
                 "https://portal.example.com/mcp?token=abc123secret", "Bearer abc123secret"):
        assert "abc123secret" not in pk.safe(RuntimeError(leak))


def test_one_unreadable_folder_entry_is_skipped_not_fatal(tmp_path, monkeypatch):
    folder = tmp_path / "client"
    folder.mkdir()
    (folder / "good 2026-10-01.md").write_text("x", encoding="utf-8")
    (folder / "bad 2026-10-01.md").write_text("x", encoding="utf-8")
    real = pk.os.scandir

    class Flaky:
        def __init__(self, entry):
            self._entry, self.name, self.path = entry, entry.name, entry.path

        def is_dir(self, follow_symlinks=True):
            return self._entry.is_dir(follow_symlinks=follow_symlinks)

        def stat(self, follow_symlinks=True):
            if self.name.startswith("bad"):
                raise PermissionError("denied")
            return self._entry.stat(follow_symlinks=follow_symlinks)

    monkeypatch.setattr(pk.os, "scandir", lambda p: [Flaky(e) for e in real(p)])
    from datetime import date
    found, _ = pk.scan_folders([folder], date(2026, 9, 28), date(2026, 10, 5), [], [], [])
    assert [s["title"] for s in found] == ["good 2026-10-01.md"]


FAKE_APPLY_ERROR = """import json, sys
print(json.dumps({"status": "error", "reason": "no Portal config"}))
sys.exit(2)
"""


def test_apply_reports_task_stack_apply_failing_as_an_error(run, tmp_path, monkeypatch, capsys):
    paths, run_dir = run
    fake = tmp_path / "fake_apply_error.py"
    fake.write_text(FAKE_APPLY_ERROR)
    monkeypatch.setattr(ap, "TASK_STACK_APPLY", fake)
    (run_dir / "changes.json").write_text(json.dumps(CHANGES))
    assert ap.main([NAME, f"--run-dir={run_dir}", f"--contexts-dir={paths['contexts']}"]) == 2
    assert "no Portal config" in capsys.readouterr().err


def test_apply_refuses_a_run_folder_inside_the_skill(run, capsys):
    paths, _ = run
    inside = ap.SKILL_DIR / "scripts" / "run"
    assert ap.main([NAME, f"--run-dir={inside}", f"--contexts-dir={paths['contexts']}", "--dry-run"]) == 2
    assert not inside.exists()
