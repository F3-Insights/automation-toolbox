"""firm_billing_deliver against a stand-in for the comms-reply-to-email skill's email_deliver.py."""

import json
import sys
import textwrap
from pathlib import Path

from billing_fixtures import PERIOD, SCRIPTS, billing_folder, done_folder, pdir_of, pull, record

sys.path.insert(0, str(SCRIPTS))
import firm_billing_deliver as dl  # noqa: E402


def fake_email_deliver(tmp: Path, result: dict) -> Path:
    """A script that records its arguments and prints the given result; --dry-run turns a
    delivery into would_deliver, as the real one does."""
    path = tmp / "email_deliver.py"
    path.write_text(textwrap.dedent(f"""
        import json, sys
        from pathlib import Path
        log = Path({str(tmp / 'calls.jsonl')!r})
        with log.open("a") as fh:
            fh.write(json.dumps(sys.argv[1:]) + "\\n")
        result = {result!r}
        if "--dry-run" in sys.argv and result["status"] == "delivered":
            result["status"] = "would_deliver"
        print(json.dumps(result))
        sys.exit(0 if result["status"] in ("delivered", "would_deliver") else 3)
    """))
    return path


def stage(folder: Path) -> None:
    (pdir_of(folder) / "work" / "delivery-acme-ops.json").write_text(json.dumps(
        {"draft_id": "d-1", "check": "check.json", "contact_id": "c-1", "email_ref": "portal://email/e-1"}))


def calls(tmp: Path) -> list:
    log = tmp / "calls.jsonl"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def lines(folder, tmp, result, **kw):
    out = dl.deliver(str(folder), PERIOD, email_deliver=fake_email_deliver(tmp, result), **kw)
    return out["lines"], out


def test_none_and_file(tmp_path):
    folder = billing_folder(tmp_path)
    pull(folder)
    assert lines(folder, tmp_path, {"status": "delivered"})[0] == [f"NONE: no drafted, reviewed contract for {PERIOD}"]
    folder = done_folder(tmp_path / "b")
    assert lines(folder, tmp_path, {"status": "delivered"})[0][0].endswith("(no staged Portal draft)")
    assert calls(tmp_path) == []


def test_held_until_the_check_is_done(tmp_path):
    folder = done_folder(tmp_path)
    stage(folder)
    record(folder, "fabrikam-qtr", "open")
    assert lines(folder, tmp_path, {"status": "delivered"})[0] == [
        "HELD: acme-ops firm-billing-check is not done (open: contracts)"]
    assert calls(tmp_path) == []


def test_delivered_once_then_already(tmp_path):
    folder = done_folder(tmp_path)
    stage(folder)
    got, _ = lines(folder, tmp_path, {"status": "delivered", "web_link": "https://mail.example.com/d-1"})
    assert got == ["DELIVERED: acme-ops https://mail.example.com/d-1"]
    assert calls(tmp_path)[0][:2] == ["--draft", "d-1"]
    result = json.loads((pdir_of(folder) / "work" / "delivery-result-acme-ops.json").read_text())
    assert result["contract"] == "acme-ops" and result["delivered_at"]
    assert lines(folder, tmp_path, {"status": "delivered"})[0][0].startswith("ALREADY: acme-ops delivered at ")
    assert len(calls(tmp_path)) == 1


def test_dry_run_refusal_and_failed_push(tmp_path):
    folder = done_folder(tmp_path)
    stage(folder)
    got, _ = lines(folder, tmp_path, {"status": "delivered", "draft_id": "d-1", "delivered_to": "owner@example.com"},
                   dry_run=True)
    assert got == ["WOULD DELIVER: acme-ops draft d-1 to owner@example.com"]
    assert "--dry-run" in calls(tmp_path)[0]
    got, _ = lines(folder, tmp_path, {"status": "refused", "refusals": [{"code": "CHECK_FAILED", "reason": "FAIL"}]})
    assert got == ["REFUSED: acme-ops CHECK_FAILED FAIL"]
    _, out = lines(folder, tmp_path, {"status": "push_failed", "reason": "timeout"})
    assert out["contracts"][0]["failed"] and (pdir_of(folder) / "work" / "delivery-intent-acme-ops.json").exists()
    assert not (pdir_of(folder) / "work" / "delivery-result-acme-ops.json").exists()


def test_reconciles_a_lost_result_from_its_intent(tmp_path):
    folder = done_folder(tmp_path)
    stage(folder)
    (pdir_of(folder) / "work" / "delivery-intent-acme-ops.json").write_text("{}")
    got, _ = lines(folder, tmp_path, {"status": "refused", "refusals": [{"code": "ALREADY_DELIVERED", "reason": "x"}]})
    assert got[0].startswith("ALREADY: acme-ops delivered by an earlier run")
    assert (pdir_of(folder) / "work" / "delivery-result-acme-ops.json").exists()


def test_missing_email_deliver_and_bad_arguments(tmp_path):
    folder = done_folder(tmp_path)
    stage(folder)
    try:
        dl.deliver(str(folder), PERIOD, email_deliver=tmp_path / "absent.py")
    except dl.c.Bad as exc:
        assert "email_deliver.py is not installed" in str(exc)
    else:
        raise AssertionError("expected Bad")
    assert dl.main([]) == 2 and dl.main([str(tmp_path / "nowhere")]) == 2
