"""issue_harvest_check.py: the three tests of done and the precheck line."""

import json
from datetime import timedelta

import _common as c
import issue_file as ifile
import issue_harvest_check as chk
import issue_harvest_record as rec
from conftest import APP, NOW, FakePortal, ago, harvest, new, run_folder


def filed_and_recorded(home, decisions):
    run = run_folder(home, harvest(home), decisions)
    c.write_new(run / "filed.json", ifile.run(run, home["settings"], home["repos"], False, 30))
    assert rec.main(["--run", str(run)]) == 0
    return run


def test_before_any_run_is_work(home, github):
    result = chk.check(home["settings"], home["repos"], home["state"], client=FakePortal(), github=False, now=NOW)
    assert result["done"] is False
    assert chk.precheck_line(result) == "WORK: no live issue-harvest Run recorded yet"


def test_after_a_full_run_is_done(home, github):
    filed_and_recorded(home, [new("portal-notes:n1")] + [
        {"source": k, "decision": "not-software", "reason": "x"}
        for k in ("portal-email:e1", "portal-tasks:t1", "portal-notes:n3")])
    result = chk.check(home["settings"], home["repos"], home["state"], client=FakePortal(), now=NOW + timedelta(minutes=5))
    assert result["tests"]["found"]["checked_on_github"] is True
    assert result["done"] is True, json.dumps(result["tests"], indent=1)
    assert chk.precheck_line(result).startswith("NOTHING: ")


def test_finds_a_missing_marker_and_new_items(home, github):
    filed_and_recorded(home, [new("portal-notes:n1")])
    github.issues[APP][-1]["body"] = "edited by a person"
    portal = FakePortal()
    portal.notes.append({"id": "n9", "title": "Widget app crash", "updated_at": (NOW + timedelta(hours=1)).isoformat()})
    result = chk.check(home["settings"], home["repos"], home["state"], client=portal, now=NOW + timedelta(hours=2))
    assert result["tests"]["found"]["met"] is False
    assert "does not carry the marker on GitHub" in result["tests"]["found"]["gaps"][0]
    assert result["tests"]["decided"]["new"]["count"] >= 1
    line = chk.precheck_line(result)
    assert line.startswith("WORK: ") and "not decided yet" in line and "new candidate" in line
    assert "get" not in portal.calls  # the cheap pass never fetches a note in full


def test_items_in_parts_are_found_part_by_part(home, github):
    filed_and_recorded(home, [new("portal-email:e1", part="1", title="WA-20300316-ONE: first bug"),
                              new("portal-email:e1", part="2", title="WA-20300316-TWO: second bug")])
    args = (home["settings"], home["repos"], home["state"])
    assert chk.check(*args, client=FakePortal(), now=NOW + timedelta(minutes=5))["tests"]["found"]["met"] is True
    github.issues[APP][1]["body"] = "a person rewrote it"
    assert chk.check(*args, client=FakePortal(), now=NOW + timedelta(minutes=5))["tests"]["found"]["met"] is False


def test_sources_reports_the_last_runs_unread_source(home):
    home["state"].mkdir(parents=True)
    (home["state"] / "runs.jsonl").write_text(json.dumps({
        "run": "r1", "started_at": ago(1), "sources": [{"name": "portal-email", "readable": False, "error": "500"}],
        "repos": [{"repo": APP, "github": {"readable": True}}]}) + "\n")
    result = chk.check(home["settings"], home["repos"], home["state"], portal=False, github=False, now=NOW)
    assert result["tests"]["sources"]["gaps"] == ["source portal-email: 500"]


def test_cli_offline_and_bad_settings(home, tmp_path, monkeypatch, capsys):
    assert chk.main(["--offline", "--precheck"]) == 0 and capsys.readouterr().out.startswith("WORK: ")
    assert chk.main(["--offline", "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["of"] == 3
    bad = tmp_path / "bad.toml"
    bad.write_text('[issue-harvest-workstream]\nrepos_file = "/nowhere/repos.yaml"\n')
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(bad))
    assert chk.main(["--offline"]) == 2


def test_repo_map_validation(tmp_path):
    import pytest

    def load(text):
        path = tmp_path / "r.json"
        path.write_text(json.dumps({"repos": text}))
        return c.load_repos({}, str(path))

    for broken in ([], [{"repo": "not a repo"}], [{"repo": APP}, {"repo": APP.upper()}],
                   [{"repo": APP, "title": {"pattern": "("}}]):
        with pytest.raises(c.ConfigError):
            load(broken)
    repos = load([{"repo": APP}])
    assert repos[0]["harvest"] is False and repos[0]["public"] is False
