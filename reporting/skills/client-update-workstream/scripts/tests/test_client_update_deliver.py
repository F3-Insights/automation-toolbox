"""client_update_deliver.py on an invented Northwind Traders memo, with the check and
email_deliver.py replaced by small fake scripts."""

import json
import subprocess
import sys

import pytest

import _common as cu
import client_update_deliver as cd
from conftest import NAME, SCRIPTS, WEEK, engagement, put

OUTLOOK = {"Email delivery": "outlook-drafts", "Recipients": "Dana <dana@northwind.test>"}


def fakes(tmp_path, monkeypatch, done=True, result=None, code=0):
    """A fake check that reports done or not, and a fake email_deliver.py that logs its argv and
    prints `result`."""
    check = tmp_path / "fake_check.py"
    check.write_text("import json\nprint(json.dumps({'done': %r, 'tests': {'claims': {'state': %r}}}))\n"
                     % (done, "pass" if done else "fail"), encoding="utf-8")
    deliver = tmp_path / "fake_deliver.py"
    log = tmp_path / "argv.json"
    deliver.write_text("import json, sys\nopen(%r, 'w').write(json.dumps(sys.argv[1:]))\n"
                       "print(json.dumps(%r))\nsys.exit(%d)\n" % (str(log), result or {"status": "delivered",
                                                                                      "web_link": "https://outlook.test/d1"}, code),
                       encoding="utf-8")
    monkeypatch.setattr(cd, "CHECK", check)
    monkeypatch.setattr(cd, "EMAIL_DELIVER", deliver)
    return log


def stage(paths):
    work = paths["week_dir"] / "work"
    put(work / "check.json", json.dumps({"verdict": "PASS"}))
    put(work / cu.DELIVERY_JSON, json.dumps({"draft_id": "d1", "check": "check.json", "contact_id": "c1",
                                             "email_ref": "portal://email/e1"}))
    return work


def run(paths, dry=False):
    return cd.deliver(NAME, WEEK, str(paths["week_dir"]), dry_run=dry)


@pytest.mark.parametrize("variant, extra, reason", [
    ("deck", OUTLOOK, "a deck has no cover email"),
    ("memo", {"Email delivery": "file"}, "the rules say file"),
    ("memo", {**OUTLOOK, "Recipients": "Dana <d@northwind.test>; Sam <s@northwind.test>"}, "2 recipients"),
    ("memo", OUTLOOK, "no staged Portal draft")])
def test_the_cover_email_stays_a_file(tmp_path, variant, extra, reason):
    paths = engagement(tmp_path, variant=variant, extra=extra)
    out = run(paths)
    assert out["outcome"] == "FILE" and reason in out["line"]


def test_held_until_the_check_is_done(tmp_path, monkeypatch):
    paths = engagement(tmp_path, extra=OUTLOOK)
    stage(paths)
    log = fakes(tmp_path, monkeypatch, done=False)
    out = run(paths)
    assert out["line"] == "HELD: client_update_check.py is not done (failing: claims)" and not log.exists()


def test_delivered_once_through_email_deliver_then_already(tmp_path, monkeypatch):
    paths = engagement(tmp_path, extra=OUTLOOK)
    work = stage(paths)
    log = fakes(tmp_path, monkeypatch)
    out = run(paths)
    assert out["line"] == "DELIVERED: https://outlook.test/d1"
    argv = json.loads(log.read_text())
    assert argv[argv.index("--draft") + 1] == "d1" and argv[argv.index("--check") + 1] == str(work / "check.json")
    assert "--dry-run" not in argv
    assert json.loads((work / cu.DELIVERY_RESULT_JSON).read_text())["week"] == WEEK
    assert run(paths)["outcome"] == "ALREADY"


def test_a_dry_run_and_a_refusal_write_nothing(tmp_path, monkeypatch):
    paths = engagement(tmp_path, extra=OUTLOOK)
    work = stage(paths)
    log = fakes(tmp_path, monkeypatch, result={"status": "would_deliver", "draft_id": "d1"})
    assert run(paths, dry=True)["line"].startswith("WOULD DELIVER: draft d1")
    assert "--dry-run" in json.loads(log.read_text())
    fakes(tmp_path, monkeypatch, code=3, result={"status": "refused", "refusals": [
        {"code": "CHANGED_SINCE_CHECK", "reason": "the draft changed"}, {"code": "OUTBOUND_HOLD", "reason": "x"}]})
    out = run(paths)
    assert out["line"] == "REFUSED: CHANGED_SINCE_CHECK the draft changed" and out["detail"] == ["OUTBOUND_HOLD x"]
    assert not (work / cu.DELIVERY_RESULT_JSON).exists()


def test_a_failed_push_exits_3_and_a_lost_result_reconciles(tmp_path, monkeypatch):
    paths = engagement(tmp_path, extra=OUTLOOK)
    work = stage(paths)
    fakes(tmp_path, monkeypatch, code=3, result={"status": "push_failed", "reason": "HTTP 502"})
    assert run(paths)["failed"]
    put(work / "delivery-intent.json", json.dumps({"draft_id": "d1"}))
    fakes(tmp_path, monkeypatch, code=3, result={"status": "refused", "refusals": [
        {"code": "ALREADY_DELIVERED", "reason": "already in Outlook"}]})
    out = run(paths)
    assert out["outcome"] == "ALREADY" and (work / cu.DELIVERY_RESULT_JSON).is_file()


def test_an_unreadable_delivery_file_is_exit_2(tmp_path):
    paths = engagement(tmp_path, extra=OUTLOOK)
    put(paths["week_dir"] / "work" / cu.DELIVERY_JSON, json.dumps({"draft_id": "d1"}))
    done = subprocess.run([sys.executable, str(SCRIPTS / "client_update_deliver.py"), NAME, "--week", WEEK,
                           "--week-dir", str(paths["week_dir"])], capture_output=True, text=True, cwd=SCRIPTS)
    assert done.returncode == 2 and "lacks check, contact_id, email_ref" in done.stderr
