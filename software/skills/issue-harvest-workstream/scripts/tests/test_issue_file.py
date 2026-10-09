"""issue_file.py: the one GitHub writer, its guards, its dry run and its exit codes."""

import json
import os
import subprocess
import sys
from pathlib import Path

import _common as c
import issue_file as ifile
from conftest import APP, BODY, LOCKED, OPS, harvest, new, run_folder

SCRIPTS = Path(__file__).resolve().parent.parent


def file_run(home, run, dry=False, cap=30):
    return ifile.run(run, home["settings"], home["repos"], dry, cap)


def test_creates_with_marker_labels_and_reads_back(home, github):
    run = run_folder(home, harvest(home), [new("portal-notes:n1", labels=["enhancement", "wontfix"])])
    out = file_run(home, run)
    r = out["results"][0]
    assert r["status"] == "filed" and r["verified"] is True and r["issue"] == 100
    assert r["labels"] == ["enhancement", "bug"] and r["labels_dropped"] == ["wontfix", "agent-filed"]
    body = github.issues[APP][-1]["body"]
    assert c.marker("portal-notes:n1") in body and "portal://note/n1" in body
    assert out["headline"].startswith("FILED: 1 issue(s), 0 comment(s)")


def test_never_files_twice(home, github):
    h = harvest(home)
    github.add(APP, 9, "Something", "x " + c.marker("portal-notes:n1"))
    github.add(APP, 10, "WA-20300316-DUPE: same title")
    out = file_run(home, run_folder(home, h, [new("portal-notes:n1"),
                                              new("portal-email:e1", title="WA-20300316-DUPE: same   title")]))
    assert [r["status"] for r in out["results"]] == ["already", "already"]
    assert "marker" in out["results"][0]["why"] and "title" in out["results"][1]["why"]
    assert github.writes == []


def test_refuses_what_the_rules_forbid(home, github):
    decisions = [
        new("portal-notes:n1", check="FAIL"),
        new("portal-notes:zzz"),
        new("portal-email:e1", repo=LOCKED),
        new("portal-tasks:t1", repo="example-org/unknown"),
        new("portal-notes:n3", title="no convention here"),
        new("portal-email:e1", title="WA-20300316-LEAK: leak", body="see " + "/ho" + "me/someone/notes.txt"),
        new("portal-tasks:t1", title="WA-20300316-KEY: key", body="api_key = abcdefghijkl"),
        new("portal-notes:n3", repo=OPS, title="Ops: wrong", body="Jordan Northwind said the ops tool is slow"),
    ]
    out = file_run(home, run_folder(home, harvest(home), decisions))
    whys = [r.get("why", "") for r in out["results"]]
    assert all(r["status"] == "refused" for r in out["results"]), out["results"]
    assert "checker" in whys[0] and "not queued" in whys[1]
    assert "repo map" in whys[2] and "repo map" in whys[3] and "convention" in whys[4]
    assert "home-directory" in whys[5] and "secret" in whys[6] and "private name" in whys[7]
    assert github.writes == []


def test_refuses_a_public_repository_without_a_names_list(home, github):
    home["settings"]["public_denylist_files"] = [str(home["tmp"] / "missing.txt")]
    out = file_run(home, run_folder(home, harvest(home), [new("portal-notes:n3", repo=OPS, title="Ops: slow")]))
    assert out["results"][0]["status"] == "refused" and "no private-names list" in out["results"][0]["why"]


def test_comments_once_and_reads_back(home, github):
    github.add(APP, 7, "WA-20300301-EXPORT: export fails")
    h = harvest(home)
    d = {"source": "portal-email:e1", "decision": "comment", "repo": APP, "issue": 7, "body": "Seen again today.",
         "check": "PASS"}
    out = file_run(home, run_folder(home, h, [d]))
    assert out["results"][0]["status"] == "commented" and out["results"][0]["verified"] is True
    assert file_run(home, run_folder(home, h, [d]))["results"][0]["status"] == "already"
    assert len(github.issues[APP][0]["comments"]) == 1


def test_dry_run_writes_nothing(home, github, capsys):
    run = run_folder(home, harvest(home), [new("portal-notes:n1")], dry=True)
    assert ifile.main(["--run", str(run)]) == 0
    assert capsys.readouterr().out.startswith("WOULD FILE: 1 issue(s)")
    assert github.writes == [] and (run / "filed-dry-run.json").is_file() and not (run / "filed.json").exists()
    run2 = run_folder(home, harvest(home), [new("portal-notes:n1")])
    assert ifile.main(["--run", str(run2), "--dry-run-if", "true"]) == 0
    assert github.writes == [] and not (run2 / "filing.json").exists()


def test_caps_writes_and_ignores_non_writes(home, github):
    decisions = [new("portal-notes:n1"), new("portal-email:e1", title="WA-20300316-TWO: second"),
                 {"source": "portal-tasks:t1", "decision": "not-software", "reason": "lunch"}]
    out = file_run(home, run_folder(home, harvest(home), decisions), cap=1)
    assert [r["status"] for r in out["results"]] == ["filed", "refused"] and "cap" in out["results"][1]["why"]


def test_without_decisions_says_nothing_and_a_missing_folder_exits_2(home, github, tmp_path, capsys):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert ifile.main(["--run", str(empty)]) == 0 and capsys.readouterr().out.startswith("NOTHING:")
    assert ifile.main(["--run", str(tmp_path / "nope")]) == 2


def test_has_no_edit_or_close_path():
    src = (SCRIPTS / "issue_file.py").read_text(encoding="utf-8")
    for verb in ('"edit"', '"close"', '"reopen"', '"delete"', '"transfer"', '"lock"'):
        assert verb not in src


def test_records_its_intent_first_and_exits_3_on_a_failed_write(home, github, monkeypatch):
    run = run_folder(home, harvest(home), [new("portal-notes:n1")])
    seen = {}
    real = ifile.create

    def create(repo, title, body, labels):
        seen["journal"] = json.loads((run / "filing.json").read_text())
        github.broken.add(APP)
        return real(repo, title, body, labels)

    monkeypatch.setattr(ifile, "create", create)
    assert ifile.main(["--run", str(run)]) == 3
    assert seen["journal"]["state"] == "filing" and seen["journal"]["results"] == []
    assert json.loads((run / "filing.json").read_text())["state"] == "done"
    assert json.loads((run / "filed.json").read_text())["results"][0]["status"] == "failed"


def test_exits_0_when_every_write_lands(home, github):
    run = run_folder(home, harvest(home), [new("portal-notes:n1")])
    assert ifile.main(["--run", str(run)]) == 0
    assert json.loads((run / "filing.json").read_text())["state"] == "done"


FAKE_GH = """import json, sys
args = sys.argv[1:]
log = open(sys.argv[0] + ".log", "a")
log.write(" ".join(args) + "\\n")
if args[:2] in (["label", "list"], ["issue", "list"]):
    print("[]")
elif args[:2] == ["issue", "create"]:
    print("https://github.com/example-org/widget-app/issues/1")
elif args[:2] == ["issue", "view"]:
    print(json.dumps({"number": 1, "url": "u", "body": sys.stdin.read() if False else "MARK", "comments": []}))
"""


def test_the_gh_program_comes_from_the_environment(home, tmp_path):
    """Run as a separate process with GH pointing at a fake: a dry run never calls `issue create`."""
    fake = tmp_path / "fake_gh.py"
    fake.write_text(FAKE_GH)
    run = run_folder(home, harvest_offline(home), [new("portal-notes:n1")], dry=True)
    env = dict(os.environ, GH=f"{sys.executable} {fake}", F3I_TOOLBOX_SETTINGS=str(home["settings_file"]))
    out = subprocess.run([sys.executable, str(SCRIPTS / "issue_file.py"), "--run", str(run)],
                         capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr
    assert out.stdout.startswith("WOULD FILE: 1 issue(s)")
    calls = Path(str(fake) + ".log").read_text()
    assert "issue list" in calls and "issue create" not in calls


def harvest_offline(home):
    import issue_harvest_sync as sync
    from conftest import NOW, FakePortal
    return sync.build(home["settings"], home["repos"], home["state"], FakePortal(), days=14, max_items=60,
                      batch=8, only=[], github=False, now=NOW)


def BODY_WITH(line):
    return BODY + "\n" + line + "\n"


def test_private_terms_are_refused_on_every_repository(home, github):
    home["settings"]["private_terms"] = ["Contoso", "Project Bluejay"]
    decisions = [
        new("portal-notes:n1", title="WA-20300316-PRIV: export fails", body=BODY_WITH("CONTOSO asked for it")),
        new("portal-email:e1", title="WA-20300316-BLUE: project bluejay export"),
        new("portal-notes:n3", repo=OPS, title="Ops: slow", body="the contoso import is slow"),
    ]
    out = file_run(home, run_folder(home, harvest(home), decisions))
    assert [r["status"] for r in out["results"]] == ["refused"] * 3, out["results"]
    assert all("private term" in r["why"] and "ontoso" not in r["why"] for r in out["results"])
    assert github.writes == []


def test_private_terms_match_whole_words_only(home, github):
    home["settings"]["private_terms"] = ["Contoso"]
    out = file_run(home, run_folder(home, harvest(home), [
        new("portal-notes:n1", title="WA-20300316-WORD: export fails", body=BODY_WITH("the contosoville batch"))]))
    assert out["results"][0]["status"] == "filed", out["results"]
