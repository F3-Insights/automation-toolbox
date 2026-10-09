"""client_update_pack.py on an invented Northwind Traders engagement."""

import json
import subprocess
import sys

import _common as cu
import client_update_pack as cp
from conftest import NAME, SCRIPTS, WEEK, engagement, put


def pack(paths, **kw):
    kw.setdefault("no_portal", True)
    return cp.build(NAME, WEEK, week_dir=str(paths["week_dir"]), **kw)


def fake_collect(tmp_path, monkeypatch, body):
    script = tmp_path / "report_collect.py"
    script.write_text(body, encoding="utf-8")
    monkeypatch.setattr(cp, "REPORT_COLLECT", script)


def test_offline_pack_lists_the_window_from_both_client_folders(tmp_path):
    paths = engagement(tmp_path, extra={"Never open": "Private*"})
    put(paths["general"] / "pricing model.xlsx", day="2026-09-29")
    put(paths["proposal"] / "notes" / "call notes.md", day="2026-09-30")
    put(paths["general"] / "old plan.docx", day="2026-08-01")
    put(paths["general"] / "minutes 2026-09-28.md", day="2026-01-01")            # dated by name
    put(paths["general"] / "Private" / "salaries.xlsx", day="2026-09-29")       # a never-open folder
    put(paths["general"] / "~$lock.xlsx", day="2026-09-29")
    got = pack(paths)
    titles = [s["title"] for s in got["sources"]]
    assert got["since"] == "2026-09-25" and got["until"] == "2026-10-02" and got["window"]["kind"] == "since-previous"
    assert titles[0].startswith("previous update:")
    assert {"pricing model.xlsx", "notes/call notes.md", "minutes 2026-09-28.md"} <= set(titles)
    assert not any("old plan" in t or "salaries" in t or "~$" in t for t in titles)
    assert [s["id"] for s in got["sources"]] == [f"S{n:03d}" for n in range(1, len(titles) + 1)]
    work = paths["week_dir"] / "work"
    for name in ("sources.json", "sources.md", "sources-a.md", "sources-b.md"):
        assert (work / name).is_file()
    assert cp.render(got).startswith(f"FRESH: 4 sources for {NAME} {WEEK} (2026-09-25 to 2026-10-02)")


def test_halves_are_disjoint_and_neither_is_empty(tmp_path):
    paths = engagement(tmp_path)
    for n in range(5):
        put(paths["general"] / f"file {n}.md", "x" * (n + 1) * 100, day="2026-09-29")
    got = pack(paths)
    halves = {s["half"] for s in got["sources"]}
    assert halves == {"a", "b"}
    assert all(s["half"] == "a" for s in got["sources"] if s["role"] in ("context", "previous"))


def test_a_long_gap_is_a_catch_up_and_no_previous_is_a_first_window(tmp_path):
    paths = engagement(tmp_path, previous="2026-07-31")
    got = pack(paths)
    assert got["window"]["kind"] == "catch-up" and got["since"] == "2026-09-02"
    assert cp.render(got).startswith("FRESH: catch-up, ")
    other = engagement(tmp_path / "b", previous=None, extra={"Lookback days": "10"})
    first = cp.build(NAME, WEEK, week_dir=str(other["week_dir"]), no_portal=True)
    assert first["window"]["kind"] == "first" and first["since"] == "2026-09-22"


def test_a_dot_source_folder_is_the_top_level_only(tmp_path):
    paths = engagement(tmp_path, extra={"Source folders": "., Missing"})
    put(paths["general"] / "top.md", day="2026-09-29")
    put(paths["general"] / "deep" / "inner.md", day="2026-09-29")
    titles = [s["title"] for s in pack(paths)["sources"]]
    assert "top.md" in titles and not any("inner" in t for t in titles)


def test_portal_sweep_keeps_client_mail_and_writes_each_item(tmp_path, monkeypatch):
    paths = engagement(tmp_path, extra={"Portal domain": "Northwind"})
    ledger = {"items": [
        {"kind": "meeting", "ref": "portal://calendar_event/m1", "title": "Weekly sync", "occurred_at": "2026-09-30",
         "counterparties": ["dana@northwind.test"], "text": "Agreed the pricing model."},
        {"kind": "mail", "ref": "portal://email/e1", "title": "Plant list", "counterparties": ["sam@northwind.test"]},
        {"kind": "mail", "ref": "portal://email/e2", "title": "Newsletter", "counterparties": ["news@fabrikam.test"]},
        {"kind": "direct_report", "ref": "x", "title": "ignored"}]}
    fake_collect(tmp_path, monkeypatch, f"import json, sys\nassert '--domain' in sys.argv\nprint(json.dumps({ledger!r}))\n")
    got = pack(paths, no_portal=False)
    portal = [s for s in got["sources"] if s["role"] == "portal"]
    assert [s["title"] for s in portal] == ["Weekly sync", "Plant list"]
    assert got["portal"]["counts"] == {"meeting_read": 1, "meeting": 1, "mail_read": 2, "mail": 1}
    assert "Agreed the pricing model." in (paths["week_dir"] / "work" / "sources" / f"{portal[0]['id']}.md").read_text()


def test_an_unreadable_portal_is_stale_but_the_pack_is_written(tmp_path, monkeypatch):
    paths = engagement(tmp_path, extra={"Portal domain": "Northwind"})
    fake_collect(tmp_path, monkeypatch, "import sys\nprint('ERROR no token', file=sys.stderr)\nsys.exit(2)\n")
    got = pack(paths, no_portal=False)
    assert got["stale"] and cp.render(got).startswith("STALE: the Portal could not be read")
    assert (paths["week_dir"] / "work" / "sources.json").is_file()


def test_a_second_pack_supersedes_the_first_and_keeps_the_evidence(tmp_path):
    paths = engagement(tmp_path)
    pack(paths)
    evidence = put(paths["week_dir"] / "work" / cu.EVIDENCE_CSV, "id,kind\n")
    got = pack(paths)
    assert got["superseded"] and (tmp_path / "week" / "work" / "sources.json").is_file()
    assert evidence.read_text() == "id,kind\n"


def test_dry_run_writes_only_under_the_run_dir(tmp_path):
    paths = engagement(tmp_path)
    got = cp.build(NAME, WEEK, run_dir=str(tmp_path / "run"), dry_run_if="true", no_portal=True)
    assert got["dry_run"] and (tmp_path / "run" / "client-update" / WEEK / "work" / "sources.json").is_file()
    assert not any(paths["updates"].glob("Drafts/*"))


def test_open_ledger_rows_are_carried(tmp_path):
    paths = engagement(tmp_path)
    put(paths["updates"] / cu.UPDATES_LEDGER_CSV, ",".join(cu.LEDGER_COLUMNS) + "\n"
        "OI-1,Send the plant list,Priya,2026-10-09,open,2026-W39,2026-W39,,,\n"
        "OI-2,Old item,Sam,,done,2026-W38,2026-W39,,,\n")
    assert [c["id"] for c in pack(paths)["carry"]] == ["OI-1"]


def test_the_engagement_context_comes_first_from_a_file_or_the_portal(tmp_path, monkeypatch):
    paths = engagement(tmp_path)
    put(paths["rules"] / "ENGAGEMENT-CONTEXT.md", "# Northwind background")
    got = pack(paths)
    assert got["sources"][0]["role"] == "context" and got["sources"][0]["half"] == "a"

    other = engagement(tmp_path / "p", sources=[{"name": "background", "path": "portal://note/n-1"}])
    monkeypatch.setattr(cp, "portal_get", lambda kind, ident, config=None: {"note": {"content": "Northwind context"}})
    got = cp.build(NAME, WEEK, week_dir=str(other["week_dir"]), no_portal=False)
    first = got["sources"][0]
    assert first["kind"] == "portal-note" and "Northwind context" in open(first["path"]).read()
    assert got["context"]["from"] == "portal"


def test_a_missing_context_is_a_warning_and_a_bad_engagement_is_exit_2(tmp_path):
    paths = engagement(tmp_path)
    assert any("no engagement context" in w for w in pack(paths)["warnings"])
    done = subprocess.run([sys.executable, str(SCRIPTS / "client_update_pack.py"), "nobody", "--no-portal"],
                          capture_output=True, text=True, cwd=SCRIPTS)
    assert done.returncode == 2 and "nobody" in done.stderr
    done = subprocess.run([sys.executable, str(SCRIPTS / "client_update_pack.py"), NAME, "--week", WEEK,
                           "--week-dir", str(paths["week_dir"]), "--no-portal", "--format", "json"],
                          capture_output=True, text=True, cwd=SCRIPTS)
    assert done.returncode == 0 and json.loads(done.stdout)["week"] == WEEK


def test_the_check_reads_the_pack_this_script_writes(tmp_path):
    paths = engagement(tmp_path)
    put(paths["general"] / "pricing model.xlsx", day="2026-09-29")
    pack(paths)
    done = subprocess.run([sys.executable, str(SCRIPTS / "client_update_check.py"), NAME, WEEK, "--week-dir",
                           str(paths["week_dir"]), "--format", "json"], capture_output=True, text=True, cwd=SCRIPTS)
    assert json.loads(done.stdout)["tests"]["sources"]["state"] == "pass"
