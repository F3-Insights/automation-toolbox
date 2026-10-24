"""follow_up_check.py on an invented owner at Northwind Traders, today pinned to Thursday 2030-03-07."""

import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _common as c  # noqa: E402
import follow_up_check as fc  # noqa: E402

TODAY = date(2030, 3, 7)
OWNER, OTHER = "00000900-1111-4111-8111-111111111111", "00000901-1111-4111-8111-111111111111"


def uid(n):
    return f"{n:08d}-2222-4222-8222-222222222222"


def task(n, **kw):
    row = {"id": uid(n), "title": f"Task {n}", "status": "TODO", "owner_contact_id": OWNER,
           "created_at": "2030-03-01T10:00:00Z", "updated_at": "2030-03-06T10:00:00Z"}
    row.update(kw)
    return row


def mail(n, when, direction, thread, to=("dana@northwind.test",)):
    return {"id": uid(n), "subject": f"Mail {n}", "direction": direction, "thread_id": thread,
            "received_at": when, "to_addresses": list(to), "from_address": "owner@owner.test"}


class FakePortal:
    def __init__(self, tasks=(), emails=(), page=200, fail=False):
        self.tasks, self.emails, self.page, self.fail, self.calls = list(tasks), list(emails), page, fail, []

    def call(self, tool, args=None):
        args = args or {}
        self.calls.append((tool, args))
        if tool == "whoami":
            return {"principal": {"contact_id": OWNER, "timezone": "America/Los_Angeles"},
                    "inboxes": [{"address": "owner@owner.test"}]}
        if tool != "list_entities":
            raise AssertionError(f"the check called {tool}, which it never should")
        if self.fail:
            return {"error": "the listing failed"}
        if args["entity_type"] == "task":
            rows = self.tasks
        else:
            f = args["filters"]
            rows = [e for e in self.emails if e["direction"] == f["direction"] and e["received_at"] >= f["since"]]
        offset, limit = int(args.get("offset") or 0), min(args["limit"], self.page)
        window = rows[offset:offset + limit]
        more = offset + len(window) < len(rows)
        return {"items": window, "has_more": more, "next_offset": offset + len(window) if more else None}


def run(portal, *extra, capsys=None):
    with pytest.raises(SystemExit) as done:
        fc.main(["--as-of", str(TODAY), *extra], portal=portal)
    return done.value.code, capsys.readouterr() if capsys else None


def test_a_quiet_morning_is_nothing(capsys):
    portal = FakePortal(tasks=[task(1, due_date="2030-03-20"), task(2, status="DONE", due_date="2030-03-01")],
                        emails=[mail(10, "2030-03-06T17:00:00Z", "sent", "t1")])
    code, out = run(portal, "--precheck", capsys=capsys)
    assert code == 0 and out.out.startswith("NOTHING:")
    assert {t for t, _ in portal.calls} == {"whoami", "list_entities"}


def test_each_kind_of_work_is_counted(capsys):
    tasks = [task(1, status="WAITING", due_date="2030-03-07"),                       # follow-up due today
             task(2, status="WAITING", due_date="2030-03-12"),                       # not yet
             task(3, owner_contact_id=OTHER, updated_at="2030-02-20T10:00:00Z"),      # delegated, stale
             task(4, owner_contact_id=OTHER, due_date="2030-03-08"),                  # delegated, fresh
             task(5, due_date="2030-03-09", description="Why: x\nCaptured from: promise:abc"),  # promise in 2 days
             task(6, due_date="2030-03-09")]                                         # not a promise
    emails = [mail(10, "2030-02-28T17:00:00Z", "sent", "t1"),                        # Thu -> Thu: 5 business days
              mail(11, "2030-03-05T17:00:00Z", "sent", "t2"),                        # 2 business days: not yet
              mail(12, "2030-02-27T17:00:00Z", "sent", "t3"), mail(13, "2030-03-01T17:00:00Z", "received", "t3"),
              mail(14, "2030-02-26T17:00:00Z", "sent", "t4", to=("owner@owner.test",))]  # to himself
    code, out = run(FakePortal(tasks, emails), capsys=capsys)
    result = json.loads(out.out)
    assert code == 0 and result["counts"] == {"waiting": 1, "delegated": 1, "silent": 1, "promises": 1}
    assert result["items"]["silent"][0]["ref"] == f"portal://email/{uid(10)}"
    assert result["items"]["silent"][0]["business_days"] == 5
    code, out = run(FakePortal(tasks, emails), "--precheck", capsys=capsys)
    assert out.out.startswith("WORK: 1 WAITING follow-ups due")


def test_every_page_is_read(capsys):
    tasks = [task(n, due_date="2030-04-01") for n in range(1, 6)] + [task(9, status="WAITING", due_date="2030-03-01")]
    code, out = run(FakePortal(tasks, page=2), "--precheck", capsys=capsys)
    assert out.out.startswith("WORK:")


def test_a_portal_that_cannot_be_read_is_never_a_quiet_day(capsys):
    code, out = run(FakePortal(fail=True), "--precheck", capsys=capsys)
    assert code == 2 and out.out == "" and "failed" in out.err


def test_out_writes_the_json_outside_the_toolbox(tmp_path, capsys):
    target = tmp_path / "run" / "check.json"
    code, out = run(FakePortal(), "--out", str(target), capsys=capsys)
    assert code == 0 and json.loads(target.read_text())["work"] is False


def test_business_days_count_weekdays_only():
    assert c.business_days_between(date(2030, 3, 1), date(2030, 3, 4)) == 1      # Fri -> Mon
    assert c.business_days_between(date(2030, 3, 4), date(2030, 3, 4)) == 0
