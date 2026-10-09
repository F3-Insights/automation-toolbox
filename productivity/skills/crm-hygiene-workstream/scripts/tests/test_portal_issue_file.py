"""portal-issue-file against a fake `gh` (a Python script named by GH); no network.

The repository is the setting, the title and body are text only, private content and
secrets are refused before GitHub is touched, an open issue with the same title is a
duplicate, a dry run creates nothing, and `gh issue create` gets an argument list.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import portal_issue_file as pif  # noqa: E402

REPO = "northwind-traders/portal"
FAKE_GH = r'''
import json, os, sys
path = os.environ["FAKE_GH_STATE"]
st = json.load(open(path))
args = sys.argv[1:]
st["calls"].append(args)
def opt(name):
    return args[args.index(name) + 1] if name in args else None
if args[:2] == ["issue", "list"]:
    json.dump(st, open(path, "w"))
    print(json.dumps(st["issues"]))
    sys.exit(0)
if args[:2] == ["issue", "create"]:
    n = 100 + len(st["issues"])
    st["issues"].append({"number": n, "title": opt("--title"), "url": "https://github.com/%s/issues/%d" % (opt("-R"), n)})
    json.dump(st, open(path, "w"))
    print("Creating issue in %s\n\nhttps://github.com/%s/issues/%d" % (opt("-R"), opt("-R"), n))
    sys.exit(0)
json.dump(st, open(path, "w"))
sys.stderr.write("fake gh: unexpected " + " ".join(args) + "\n")
sys.exit(2)
'''

TITLE = "IR-20260105-sync: contacts flip inactive when a reply arrives"
BODY = "Evidence: list_entities(contact, is_active=false) shows 3 flips at 09:00 UTC.\nImpact: the list shrinks.\nAsk: fix."


@pytest.fixture
def gh(tmp_path, monkeypatch):
    script, state = tmp_path / "fake_gh.py", tmp_path / "state.json"
    script.write_text(FAKE_GH)
    settings = tmp_path / "settings.toml"
    settings.write_text(f'[crm-hygiene-workstream]\nportal_issue_repo = "{REPO}"\nprivate_terms = ["Fabrikam"]\n')
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(settings))
    monkeypatch.setenv("GH", f"{sys.executable} {script}")
    monkeypatch.setenv("FAKE_GH_STATE", str(state))

    class Fake:
        def set(self, issues=()):
            state.write_text(json.dumps({"issues": list(issues), "calls": []}))

        def state(self):
            return json.loads(state.read_text())

        def creates(self):
            return [c for c in self.state()["calls"] if c[:2] == ["issue", "create"]]

    fake = Fake()
    fake.set()
    return fake


def run(capsys, *args):
    code = pif.main(list(args))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_files_one_issue_on_the_set_repository_with_an_argv_list(gh):
    out = pif.file_issue(TITLE, BODY)
    assert out["status"] == "filed" and out["repo"] == REPO and out["number"] == 100
    calls = gh.state()["calls"]
    assert [c[:2] for c in calls] == [["issue", "list"], ["issue", "create"]]
    create = gh.creates()[0]
    assert create[create.index("-R") + 1] == REPO and create[create.index("--title") + 1] == TITLE
    assert create[create.index("--body") + 1] == BODY and create[create.index("--label") + 1] == "bug"
    assert "--body-file" not in create


def test_the_repository_setting_is_required(gh, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "missing.toml"))
    code, out, err = run(capsys, "--title", TITLE, "--body", BODY)
    assert code == 2 and "portal_issue_repo" in err and gh.state()["calls"] == []


def test_no_flag_names_another_repository_or_a_file(gh):
    for flag in (["--repo", "x/y"], ["-R", "x/y"], ["--body-file", "notes.txt"]):
        with pytest.raises(SystemExit) as exc:
            pif.main(["--title", TITLE, "--body", BODY, *flag])
        assert exc.value.code == 2, flag
    assert gh.state()["calls"] == []


def test_an_open_issue_with_the_exact_title_is_a_duplicate(gh):
    gh.set([{"number": 7, "title": TITLE, "url": f"https://github.com/{REPO}/issues/7"},
            {"number": 8, "title": TITLE + " (2)", "url": "u"}])
    out = pif.file_issue("  " + TITLE + " ", BODY)
    assert out == {"status": "duplicate", "repo": REPO, "number": 7,
                   "url": f"https://github.com/{REPO}/issues/7", "title": TITLE}
    assert not gh.creates()
    assert pif.file_issue(TITLE[:-1], BODY)["status"] == "filed"  # a near title is not a duplicate


def test_a_dry_run_reads_but_creates_nothing(gh, capsys):
    code, out, _ = run(capsys, "--title", TITLE, "--body", BODY, "--dry-run")
    assert code == 0 and json.loads(out)["status"] == "would_file" and json.loads(out)["open_issues"] == []
    gh.set([{"number": 9, "title": "Contacts go inactive on inbound mail", "url": "u"}])
    assert pif.file_issue(TITLE, BODY, dry_run=True)["open_issues"] == [[9, "Contacts go inactive on inbound mail"]]
    assert not gh.creates()


@pytest.mark.parametrize("text,rule", [
    ("file at /mnt/c/Us" + "ers/someone/a.xlsx", "Windows user folder"),
    ("file at C:\\Us" + "ers\\someone\\Desktop", "Windows user folder"),
    ("see /ho" + "me/someone/notes.txt", "home-directory path"),
    ("header was Bearer abc.def.ghi", "redaction pattern"),
    ("GET /api?token=abc123 failed", "redaction pattern"),
    ("token ghp_" + "a" * 36, "token shape"),
    ("AKIA" + "ABCDEFGHIJKLMNOP", "token shape"),
    ("password: hunter22", "assignment"),
    ("the fabrikam import broke", "private term"),
])
def test_private_content_and_secrets_are_refused_before_github(gh, text, rule):
    for title, body in ((TITLE, BODY + "\n" + text), (TITLE + " " + text, BODY)):
        with pytest.raises(pif.Refusal, match="private content") as exc:
            pif.file_issue(title, body)
        assert rule in str(exc.value) and "hunter22" not in str(exc.value) and "abric" not in str(exc.value)
    assert gh.state()["calls"] == []


def test_a_refusal_exits_three_without_echoing_the_match(gh, capsys):
    code, out, _ = run(capsys, "--title", TITLE, "--body", BODY + " pass" + "word=hunter22")
    assert code == 3 and json.loads(out)["status"] == "refused" and "hunter22" not in out


@pytest.mark.parametrize("title,body,why", [
    ("", BODY, "title is required"), (TITLE, "  ", "body is required"),
    ("x" * 201, BODY, "title is longer"), (TITLE, "x" * 60001, "body is longer")])
def test_empty_or_oversized_text_is_refused(gh, title, body, why):
    with pytest.raises(pif.Refusal, match=why):
        pif.file_issue(title, body)
    assert gh.state()["calls"] == []


def test_only_bug_or_enhancement_labels(gh):
    with pytest.raises(SystemExit):
        pif.main(["--title", TITLE, "--body", BODY, "--label", "wontfix"])
    assert pif.file_issue(TITLE, BODY, label="enhancement")["label"] == "enhancement"


def test_a_truncated_issue_list_is_not_coverage(gh, monkeypatch, capsys):
    monkeypatch.setattr(pif, "LIST_LIMIT", 2)
    gh.set([{"number": 1, "title": "a", "url": "u"}, {"number": 2, "title": "b", "url": "u"}])
    code, out, _ = run(capsys, "--title", TITLE, "--body", BODY)
    assert code == 2 and "coverage" in json.loads(out)["reason"] and not gh.creates()


def test_gh_failing_is_an_error_not_a_filing(gh, monkeypatch, capsys):
    monkeypatch.setenv("GH", f"{sys.executable} -c \"import sys; sys.exit(1)\"")
    code, out, _ = run(capsys, "--title", TITLE, "--body", BODY)
    assert code == 2 and json.loads(out)["status"] == "error"


@pytest.mark.parametrize("text,refused", [
    ("FABRIKAM records vanish", True), ("the Fabrikam. import", True), ("fabrikam-ops broke", True),
    ("the fabrikamco import", False), ("prefabrikam batch", False),
])
def test_private_terms_are_whole_words_in_any_case(gh, text, refused):
    for title, body in ((TITLE, BODY + "\n" + text), (TITLE + " " + text, BODY)):
        if refused:
            with pytest.raises(pif.Refusal, match="private term"):
                pif.check(title, body)
        else:
            assert pif.check(title, body)
    assert gh.creates() == []
