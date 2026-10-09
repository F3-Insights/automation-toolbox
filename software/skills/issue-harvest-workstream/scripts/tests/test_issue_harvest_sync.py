"""issue_harvest_sync.py: matching source items to repositories, the queue, and the GitHub snapshot."""

import json
from datetime import datetime

import _common as c
import issue_harvest_sync as sync
from conftest import APP, LOCKED, OPS, FakePortal, ago, harvest


def test_matches_items_to_repositories_and_skips_noise(home, github):
    h = harvest(home)
    keys = {i["key"]: i for i in h["items"]}
    assert set(keys) == {"portal-notes:n1", "portal-notes:n3", "portal-email:e1", "portal-tasks:t1"}
    assert keys["portal-notes:n1"]["repo_hints"] == [{"repo": APP, "why": ["term: Widget app"]}]
    assert keys["portal-email:e1"]["repo_hints"][0]["why"] == ["reporter"]
    assert keys["portal-tasks:t1"]["repo_hints"][0]["why"] == ["project: proj-widget"]
    assert keys["portal-notes:n3"]["repo_hints"] == [{"repo": OPS, "why": ["search: ops tool"]}]
    assert all(i["marker"] == c.marker(i["key"]) for i in h["items"])
    assert h["other_repos"] == [LOCKED]
    assert [r["repo"] for r in h["repos"]] == [APP, OPS]
    assert h["counts"]["queued"] == 4 and h["window"]["first_run"] is True


def test_snapshots_open_and_recent_issues_with_markers(home, github):
    github.add(APP, 7, "WA-20300301-EXPORT: export fails", "text\n" + c.marker("portal-notes:old"))
    github.add(APP, 8, "Closed one", state="CLOSED", closed_at=ago(3))
    app = harvest(home)["repos"][0]
    assert [i["number"] for i in app["open"]] == [7]
    assert app["open"][0]["harvest_markers"] == [f"issue-harvest:{c.key_hash('portal-notes:old')}"]
    assert app["existing_labels"] == ["bug", "enhancement"]


def test_leaves_out_decided_items_and_caps_the_queue(home, github):
    c.ledger_upsert(home["state"], [{"id": "portal-notes:n1", "state": "filed", "source": "portal-notes"},
                                    {"id": "portal-email:e1", "state": "seen", "source": "portal-email", "attempts": "1"}])
    h = harvest(home, max_items=2, batch=1)
    keys = [i["key"] for i in h["items"]]
    assert "portal-notes:n1" not in keys and h["counts"]["already_decided"] == 1
    assert len(keys) == 2 and len(h["deferred"]) == 1 and list(h["batches"]) == ["b1", "b2"]


def test_reads_from_the_last_live_run(home, github):
    home["state"].mkdir(parents=True)
    (home["state"] / "runs.jsonl").write_text(json.dumps({"run": "r1", "started_at": ago(1.5)}) + "\n"
                                              + json.dumps({"run": "dry", "started_at": ago(0.1), "dry_run": True}) + "\n")
    h = harvest(home)
    assert h["window"]["first_run"] is False
    assert h["window"]["since"] == datetime.fromisoformat(ago(1.5)).isoformat(timespec="seconds")
    assert {i["key"] for i in h["items"]} == {"portal-notes:n1", "portal-email:e1"}


def test_reads_said_not_seen(home, github):
    (home["said"] / "said-not-seen-2030-03.json").write_text(json.dumps({
        "schema": "time-study/said-not-seen@1", "window": "2030-03",
        "items": [{"id": "abc123", "date": "2030-03-14", "commitment": "Fix the Widget app login loop", "status": "open"},
                  {"id": "def456", "date": "2030-03-14", "commitment": "Widget app thing done", "status": "seen"}]}))
    assert [i["key"] for i in harvest(home)["items"] if i["source"] == "said-not-seen"] == ["said-not-seen:abc123"]


def test_a_commitment_closed_in_a_later_file_is_not_queued(home, github):
    for window, status in (("2030-03-a", "open"), ("2030-03-b", "seen")):
        (home["said"] / f"said-not-seen-{window}.json").write_text(json.dumps({
            "schema": "time-study/said-not-seen@1", "window": window,
            "items": [{"id": "abc123", "date": "2030-03-14", "commitment": "Fix the Widget app login loop",
                       "status": status}]}))
    assert [i for i in harvest(home)["items"] if i["source"] == "said-not-seen"] == []


def test_reports_unreadable_sources_and_repositories_as_stale(home, github):
    github.broken.add(OPS)

    class Broken(FakePortal):
        def list_entities(self, kind, filters=None):
            if kind == "email":
                raise RuntimeError("portal email: HTTP 500")
            return super().list_entities(kind, filters)

    h = harvest(home, portal=Broken())
    assert sync.headline(h).startswith(f"STALE: could not read portal-email, {OPS}. QUEUE: ")
    assert h["repos"][1]["github"]["readable"] is False


def test_reads_each_emails_body_not_just_the_listing_summary(home, github):
    portal = FakePortal()
    for row in portal.emails:
        row["summary"] = ""
    portal.bodies = {"e1": "The Widget app export screen is blank after the update."}
    item = next(i for i in harvest(home, portal)["items"] if i["key"] == "portal-email:e1")
    assert item["text"].startswith("The Widget app export screen") and item["text_source"] == "body"


def test_cli_refuses_unknown_repos_bad_numbers_and_overwrites(home, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(c, "open_client", lambda: (FakePortal(), None))
    assert sync.main(["--repos", "example-org/nope", "--no-github"]) == 2
    assert "does not list" in capsys.readouterr().err
    assert sync.main(["--max", "lots", "--no-github"]) == 2
    out = tmp_path / "h.json"
    assert sync.main(["--window-days=", "--max=", "--repos=", "--no-github", "--out", str(out)]) == 0
    assert capsys.readouterr().out.startswith(("QUEUE: ", "NOTHING: "))
    assert json.loads(out.read_text())["schema"] == sync.SCHEMA
    assert sync.main(["--no-github", "--out", str(out)]) == 2  # a Run's evidence is never overwritten


def test_a_missing_repo_map_setting_exits_2(tmp_path, monkeypatch, capsys):
    empty = tmp_path / "settings.toml"
    empty.write_text("[issue-harvest-workstream]\n")
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(empty))
    assert sync.main(["--no-github"]) == 2
    assert "repos_file" in capsys.readouterr().err
