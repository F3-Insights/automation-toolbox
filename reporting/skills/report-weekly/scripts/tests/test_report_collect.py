"""report_collect.py: the three tiers write one contract. Invented data only."""

import json

from conftest import ledger, run


def test_the_manual_tier_folds_a_folder_into_a_valid_ledger(tmp_path, store):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "controller-week-46.md").write_text(
        "---\nkind: direct_report\nfrom: the financial controller\ndate: 2027-11-11\n"
        "title: Controller week 46\n---\n\n- The October close signed off on 2027-11-06.\n", encoding="utf-8")
    (incoming / "my-week.md").write_text("# Support queue\n\nThe queue rose to 41 tickets.\n", encoding="utf-8")
    (incoming / "photo.png").write_bytes(b"not text")
    out = tmp_path / "ledger.json"
    done = run("report_collect", "--tier", "manual", "--from-dir", incoming, "--domain", "Northwind Traders",
               "--since", "2027-11-08", "--until", "2027-11-13", "--outline-file", store / "profile.md",
               "--out", out)
    assert done.returncode == 0, done.stderr
    found = json.loads(out.read_text())
    assert {i["kind"] for i in found["items"]} == {"direct_report", "note"}
    assert found["author"]["seats"] == ["Finance", "Technology"]
    assert found["direct_reports"][0]["name"] == "the financial controller"
    assert "not Markdown or text" in done.stderr
    assert run("report_collect", "--validate", out).returncode == 0


def test_validate_names_a_duplicate_reference_and_fills_the_harvester_defaults(tmp_path):
    written = ledger()
    del written["tier"], written["model_driven"]
    written["items"].append(dict(written["items"][0]))
    path = tmp_path / "harvest.json"
    path.write_text(json.dumps(written))
    done = run("report_collect", "--validate", path)
    assert done.returncode == 2
    verdict = json.loads(done.stdout)
    assert verdict["tier"] == "harvester" and verdict["model_driven"] is True
    assert any("appears on 2 items" in e for e in verdict["errors"])


def test_the_portal_tier_reads_the_week_through_the_portal(tmp_path, portal):
    out = tmp_path / "ledger.json"
    done = run("report_collect", "--domain", "Northwind", "--since", "2027-11-08", "--until", "2027-11-13",
               "--out", out)
    assert done.returncode == 0, done.stderr
    found = json.loads(out.read_text())
    by_ref = {i["ref"]: i for i in found["items"]}
    assert found["outline"]["read_as"] == "profile" and found["outline"]["note_title"] == "Weekly report profile"
    assert set(by_ref["portal://task/t2"]["extra"]["lists"]) == {"overdue", "waiting"}
    assert by_ref["portal://task/t1"]["extra"]["lists"] == ["created_in_period", "due_in_lookahead"]
    assert by_ref["portal://email/e1"]["extra"]["awaiting_owner"] is True
    assert by_ref["portal://email/e1"]["text"] == "The queue rose to 41 tickets."
    meeting = by_ref["portal://calendar_event/c1"]
    assert meeting["hours"] == 1.5 and meeting["counterparties"] == ["northwind.test"]
    assert by_ref["portal://note/n1"]["projects"] == ["Month-end close", "p1"]
    assert found["prior_reports"][0]["bullets"][0]["label"] == "Credit hold"
    assert found["goals"][0]["title"] == "Cut debtor days"
    assert all(auth == "Bearer test-token" for _, _, auth in portal), "the token comes from the environment"


def test_a_pattern_that_is_not_a_regular_expression_is_matched_as_text():
    from report_collect import matches
    assert matches("(stock|plan", "Weekly (stock|plan update") is True
    assert matches("(stock|plan", "Something else") is False
    assert matches("stock|plan", "The PLAN for November") is True


def test_a_direct_report_file_is_cited_by_its_path_under_the_reports_folder(tmp_path):
    from report_collect import direct_reports
    reports, elsewhere = tmp_path / "reports", tmp_path / "elsewhere"
    for folder in (reports / "alice", reports / "bob", elsewhere / "carol"):
        folder.mkdir(parents=True)
        (folder / "update.md").write_text("the week")
    entries = [{"name": "Alice", "source": "file", "path_glob": "alice/*.md"},
               {"name": "Bob", "source": "file", "path_glob": str(reports / "bob" / "*.md")},
               {"name": "Carol", "source": "file", "path_glob": str(elsewhere / "carol" / "*.md")}]
    refs = [r["ref"] for r in direct_reports(None, None, entries, None, None, reports)]
    assert refs == ["file://alice/update.md", "file://bob/update.md",
                    f"file://{(elsewhere / 'carol' / 'update.md').resolve().as_posix()}"]
