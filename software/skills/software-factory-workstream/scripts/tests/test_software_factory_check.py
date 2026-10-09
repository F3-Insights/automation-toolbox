"""software_factory_check.py: stalled work, reopened issues and repeats from the ledger and a snapshot."""

import json

import _common
from sf_support import REPO
from software_factory_check import main, similar, title_tokens

NOW = "2026-03-10T12:00:00+00:00"
OLD = _common.parse_time("2026-03-01T09:00:00+00:00")


def snapshot(folder, issues=(), prs=(), first="SYNCED: 0 issues, 0 factory PRs, CI none"):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "repo.json").write_text(json.dumps({"owner": "acme", "name": "widgets"}))
    (folder / "issues.json").write_text(json.dumps(list(issues)))
    (folder / "prs.json").write_text(json.dumps(list(prs)))
    (folder / "SYNC.md").write_text(first + "\n")
    return folder


def run(capsys, *args):
    code = main([REPO, "--now", NOW, "--format", "json", *args])
    return code, (json.loads(capsys.readouterr().out) if code == 0 else None)


def test_stalled_kinds(env, capsys):
    _common.record(REPO, 1, "verified", "o", now=OLD)
    _common.record(REPO, 2, "building", "o", now=OLD)
    _common.record(REPO, 3, "triaged-ask", "o", now=OLD)
    _common.record(REPO, 4, "pr-open", "o", pr="40", head_sha="a" * 40, review="PASS", now=OLD)
    _common.record(REPO, 5, "pr-open", "o", pr="50", now=OLD)
    prs = [{"number": 40, "head": "software-factory/issue-4-x", "head_sha": "a" * 40, "ci": "success",
            "mergeable": "mergeable"},
           {"number": 50, "head": "software-factory/issue-5-y", "ci": "failure", "mergeable": "conflicting",
            "unanswered_comments": [{"author": "sam", "body": "why?", "created_at": "2026-03-02T00:00:00Z"}]}]
    sync = snapshot(env / "sync", issues=[{"number": 3, "comments": []}], prs=prs)
    code, out = run(capsys, "--sync", str(sync))
    kinds = {(s["issue"], s["kind"]) for s in out["stalled"]}
    assert kinds == {(1, "no-pr"), (2, "building-too-long"), (3, "ask-unanswered"), (4, "not-merged"),
                     (5, "ci-failing"), (5, "unanswered-comments")}
    assert out["counts"] == {"verified": 1, "building": 1, "triaged-ask": 1, "pr-open": 2}


def test_an_answered_question_is_not_stalled(env, capsys):
    _common.record(REPO, 3, "triaged-ask", "o", now=OLD)
    comments = [{"author": "bot", "body": "From the software factory: which date?\n<!-- software-factory -->",
                 "created_at": "2026-03-01T10:00:00Z"},
                {"author": "dana", "body": "ISO weeks", "created_at": "2026-03-02T10:00:00Z"}]
    code, out = run(capsys, "--sync", str(snapshot(env / "sync", issues=[{"number": 3, "comments": comments}])))
    assert out["stalled"] == []


def test_reopened_and_repeats(env, capsys):
    recent = _common.parse_time("2026-03-05T09:00:00+00:00")
    _common.record(REPO, 8, "merged", "o", title="Invoice export drops totals", now=recent)
    _common.record(REPO, 9, "failed", "o", now=recent)
    _common.record(REPO, 9, "building", "o", new_attempt=True, now=recent)
    issues = [{"number": 8, "title": "Invoice export drops totals"}, {"number": 12, "title": "Invoice totals export dropped"}]
    code, out = run(capsys, "--sync", str(snapshot(env / "sync", issues=issues)))
    assert out["reopened"][0]["issue"] == 8
    assert out["repeats"]["attempts"][0]["issue"] == 9
    assert [p["issue"] for p in out["repeats"]["similar_titles"]["pairs"]] == [12]


def test_onboarding_is_labelled(env, capsys):
    _common.record(REPO, 0, "building", "o", branch="software-factory/onboard")
    assert main([REPO, "--now", NOW]) == 0
    assert "Onboarding: building on software-factory/onboard" in capsys.readouterr().out


def test_stale_and_incomplete_snapshots(env, capsys):
    code, out = run(capsys, "--sync", str(snapshot(env / "a", first="STALE: GitHub unreachable")))
    assert out["sync"]["status"] == "stale: GitHub unreachable"
    (env / "b").mkdir()
    assert main([REPO, "--sync", str(env / "b")]) == 2
    other = snapshot(env / "c")
    (other / "repo.json").write_text(json.dumps({"owner": "northwind", "name": "site"}))
    assert main([REPO, "--sync", str(other)]) == 2
