"""sweep_emails.py and sweep_tasks.py: the day's mail and the open tasks, written before the session."""

import json
from datetime import date

import pytest

import _common as c
import sweep_emails as se
import sweep_tasks as st
from conftest import OWNER, PRIYA, FakePortal

DAY = "2030-03-06"
WINDOW = {"since": "2030-03-06T06:00:00Z", "until": "2030-03-07T06:00:00Z"}


def test_archived_mail_is_read_and_never_filtered(portal):
    portal.add_email("2030-03-06T15:00:00Z", archived=True)
    portal.add_email("2030-03-06T16:00:00Z")
    out = se.collect(portal, DAY, WINDOW)
    assert out["counts"]["inbound"] == 2 and out["counts"]["archived"] == 1


def test_exactly_the_local_day_is_kept(portal):
    portal.add_email("2030-03-06T05:59:59Z")
    inside = portal.add_email("2030-03-06T06:00:00Z")
    portal.add_email("2030-03-07T06:00:00Z")  # the listing returns it; the script drops it
    out = se.collect(portal, DAY, WINDOW)
    assert [r["id"] for r in out["inbound"]] == [inside["id"]]
    assert out["counts"]["outside_window_dropped"] == 1


def test_the_assistant_first_and_flagged_and_the_portal_brief_flagged(portal):
    portal.add_email("2030-03-06T08:00:00Z")
    portal.add_email("2030-03-06T09:00:00Z", sender="Sam <sam@example.com>")
    portal.add_email("2030-03-06T10:00:00Z", sender="brief@example.org")
    out = se.collect(portal, DAY, WINDOW)
    assert out["inbound"][0]["from_assistant"] is True
    assert sum(r["portal_brief"] for r in out["inbound"]) == 1
    assert out["counts"]["from_assistant"] == 1


def test_without_settings_no_mail_is_flagged(portal, settings_file):
    settings_file.write_text('[nightly-sweep-workstream]\ntimezone = "UTC"\n')
    portal.add_email("2030-03-06T09:00:00Z", sender="sam@example.com")
    out = se.collect(portal, DAY, WINDOW)
    assert out["counts"]["from_assistant"] == 0


def test_every_page_is_read_and_an_overflow_is_reported(portal):
    portal.page = 2
    for h in range(10, 15):
        portal.add_email(f"2030-03-06T{h}:00:00Z")
    assert se.collect(portal, DAY, WINDOW)["counts"]["inbound"] == 5
    out = se.collect(portal, DAY, WINDOW, max_pages=2)
    assert out["errors"] and out["counts"]["inbound"] == 4


def test_sent_mail_is_listed_separately(portal):
    portal.add_email("2030-03-06T12:00:00Z", direction="sent", recipients=[PRIYA])
    out = se.collect(portal, DAY, WINDOW)
    assert out["counts"] == dict(out["counts"], inbound=0, sent=1)
    assert out["sent"][0]["_ref"].startswith("portal://email/")


def test_emails_cli_one_date_and_the_skill_folder_refused(portal, tmp_path, capsys):
    with pytest.raises(SystemExit) as code:
        se.main([DAY, "--out", str(tmp_path / DAY / "emails.json")], client=portal)
    assert code.value.code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "empty"
    with pytest.raises(SystemExit) as code:
        se.main([DAY, "--out", str(c.SKILL_DIR / "emails.json")], client=portal)
    assert code.value.code == 2


def write_dates(run, days, dry_run=False):
    rows = [{"date": d, "email_window": {"since": f"{d}T06:00:00Z",
                                         "until": f"{date.fromisoformat(d).replace(day=int(d[-2:]) + 1)}T06:00:00Z"}}
            for d in days]
    run.mkdir(parents=True, exist_ok=True)
    (run / "dates.json").write_text(json.dumps({"dry_run": dry_run, "dates": rows}))


def test_emails_run_mode_writes_every_date(portal, tmp_path, capsys):
    portal.add_email("2030-03-05T12:00:00Z")
    portal.add_email("2030-03-06T12:00:00Z")
    run = tmp_path / "run"
    write_dates(run, ["2030-03-05", DAY])
    with pytest.raises(SystemExit) as code:
        se.main(["--run", str(run)], client=portal)
    assert code.value.code == 0
    out = json.loads(capsys.readouterr().out)
    assert [d["status"] for d in out["dates"]] == ["ok", "ok"]
    assert json.loads((run / DAY / "emails.json").read_text())["counts"]["inbound"] == 1


def test_emails_run_mode_without_dates_json_stops(portal, tmp_path):
    with pytest.raises(SystemExit) as code:
        se.main(["--run", str(tmp_path / "none")], client=portal)
    assert code.value.code == 2


def tasks_portal():
    portal = FakePortal()
    portal.domains = [{"id": "d1", "name": "Acme Components Admin"}, {"id": "d2", "name": "Old", "is_active": False}]
    portal.projects = [{"id": "p1", "name": "Supplier onboarding", "domain_id": "d2"}]
    portal.add_task(title="Send the Northwind price list", priority="P3", due_date="2030-02-20", project_id="p1",
                    task_contact_id=PRIYA, task_contact_name="Priya")
    portal.add_task(title="Sign the lease", priority="P1", domain_id="d1")
    portal.add_task(title="Jordan's review", priority="P2", owner_contact_id="someone", owner_name="Jordan")
    portal.add_task(title="Closed one", status="DONE")
    return portal


def test_tasks_are_compact_ordered_and_name_the_owner():
    out = st.build(DAY, st.pull(tasks_portal()))
    rows = out["tasks"]
    assert [r["title"] for r in rows] == ["Sign the lease", "Jordan's review", "Send the Northwind price list"]
    assert rows[0]["owner"] == "self" and rows[0]["domain"] == "Acme Components Admin"
    assert rows[1]["owner"] == "someone" and rows[1]["owner_name"] == "Jordan"
    late = rows[2]
    assert late["overdue_days"] == 14 and late["domain"] == "Old" and late["project"] == "Supplier onboarding"
    assert "waiting_on" not in late
    assert out["owner_contact_id"] == OWNER and out["counts"]["past_due_7_or_more"] == 1


def test_every_page_of_open_tasks_is_read():
    portal = tasks_portal()
    portal.page = 1
    assert st.build(DAY, st.pull(portal))["counts"]["open"] == 3


def test_the_tasks_file_is_one_task_per_line_and_valid_json(tmp_path):
    out = st.write(DAY, st.pull(tasks_portal()), tmp_path / "tasks.json")
    text = (tmp_path / "tasks.json").read_text()
    assert json.loads(text)["counts"]["open"] == 3
    assert sum(1 for ln in text.splitlines() if ln.startswith('{"id"')) == 3
    assert out["status"] == "ok"


def test_without_whoami_no_task_is_marked_the_owners():
    portal = tasks_portal()
    portal.whoami_ok = False
    out = st.build(DAY, st.pull(portal))
    assert not any(r.get("owner") == "self" for r in out["tasks"]) and out["errors"]


def test_tasks_cli_empty_and_run_mode(tmp_path, capsys):
    with pytest.raises(SystemExit) as code:
        st.main([DAY, "--out", str(tmp_path / "t.json")], client=FakePortal())
    assert code.value.code == 0 and json.loads(capsys.readouterr().out)["status"] == "empty"
    run = tmp_path / "run"
    write_dates(run, ["2030-03-05", DAY])
    portal = tasks_portal()
    with pytest.raises(SystemExit) as code:
        st.main(["--run", str(run)], client=portal)
    assert code.value.code == 0
    first = json.loads((run / "2030-03-05" / "tasks.json").read_text())
    second = json.loads((run / DAY / "tasks.json").read_text())
    late = [r for r in first["tasks"] if r["title"].startswith("Send")][0]
    assert late["overdue_days"] == 13
    assert [r for r in second["tasks"] if r["title"].startswith("Send")][0]["overdue_days"] == 14
    assert sum(1 for x in portal.calls if x[0] == "whoami") == 1
