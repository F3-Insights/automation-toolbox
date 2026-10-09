"""sweep_apply.py: each phase writes only its own kinds, with evidence, once, and only the owner's tasks."""

import json

import pytest

import sweep_apply as sa
from conftest import NORTHWIND, OWNER, PRIYA, TZ

DAY = "2030-03-06"
IN_A = "30000000-0000-4000-8000-000000000001"
IN_B = "30000000-0000-4000-8000-000000000002"
SENT = "30000000-0000-4000-8000-000000000003"
EMAILS = {"inbound": [{"id": IN_A}, {"id": IN_B}],
          "sent": [{"id": SENT, "subject": "Price list", "recipient_contact_ids": [OWNER, PRIYA]}], "errors": []}


def task_write(item=1, email=IN_A, **kw):
    w = {"kind": "create_task", "email_id": email, "item": item, "title": f"Review the Northwind quote {item}",
         "domain": "Acme Components", "priority": "P2", "due_date": "2030-03-08",
         "description": "From: Priya (2030-03-06)\nAsks for a review."}
    w.update(kw)
    return w


def plan(phase, *writes):
    return {"phase": phase, "date": DAY, "writes": list(writes)}


def run(portal, p, dry=False, emails=EMAILS):
    return sa.apply(portal, p, DAY, dry, emails, None, TZ)


def done(task_id, ref=f"portal://email/{SENT}", handle="contact Priya"):
    return {"kind": "set_status", "task_id": task_id, "status": "DONE", "evidence": "sent the list",
            "evidence_ref": ref, "handle": handle}


def test_a_task_is_created_with_its_marker_the_owner_and_the_source_email(portal):
    out = run(portal, plan(1, task_write()))
    assert out["status"] == "applied" and out["results"][0]["outcome"] == "created"
    [(tool, args)] = [x for x in portal.writes() if x[0] == "create_task"]
    marker = f"nightly-sweep:email:{IN_A}:1"
    assert args["owner_contact_id"] == OWNER and args["source_reference"] == marker
    assert args["description"].splitlines()[-1] == marker and f"Source: portal://email/{IN_A}" in args["description"]
    assert args["priority"] == 2 and args["source_email_id"] == IN_A


def test_a_rerun_writes_nothing_twice_even_when_the_task_is_done(portal):
    run(portal, plan(1, task_write()))
    for t in portal.tasks.values():
        t["status"] = "DONE"
    out = run(portal, plan(1, task_write()))
    assert out["results"][0]["outcome"] == "reused" and len(portal.tasks) == 1


def test_one_task_per_item_of_a_task_list(portal):
    out = run(portal, plan(1, task_write(1), task_write(2), task_write(3)))
    assert out["counts"] == {"created": 3}


def test_a_dry_run_writes_nothing(portal):
    out = run(portal, plan(1, task_write()), dry=True)
    assert out["status"] == "would_apply" and out["results"][0]["outcome"] == "would_create"
    assert portal.writes() == []


@pytest.mark.parametrize("phase,write", [
    (1, {"kind": "set_status", "task_id": IN_A, "status": "DONE", "evidence": "x",
         "evidence_ref": f"portal://email/{SENT}", "handle": "x"}),
    (2, task_write()),
    (4, task_write()),
    (2, {"kind": "set_status", "task_id": IN_A, "status": "CANCELLED", "evidence": "x",
         "evidence_ref": f"portal://email/{SENT}"}),
])
def test_each_phase_writes_only_its_own_kinds(portal, phase, write):
    with pytest.raises(sa.Refused) as exc:
        run(portal, plan(phase, write))
    assert exc.value.code == "INVALID_PLAN" and portal.writes() == []


def test_a_phase_that_does_not_write_or_the_wrong_file_is_refused(portal, tmp_path):
    with pytest.raises(sa.Refused) as exc:
        run(portal, plan(3))
    assert exc.value.code == "WRONG_PHASE"
    with pytest.raises(sa.Refused) as exc:
        sa.apply(portal, plan(1), DAY, False, EMAILS, tmp_path / "phase2.json", TZ)
    assert exc.value.code == "WRONG_PHASE"


def test_a_plan_for_another_date_or_with_one_bad_write_is_refused_whole(portal):
    with pytest.raises(sa.Refused) as exc:
        sa.apply(portal, dict(plan(1, task_write()), date="2030-03-05"), DAY, False, EMAILS, None, TZ)
    assert exc.value.code == "WRONG_DATE"
    with pytest.raises(sa.Refused):
        run(portal, plan(1, task_write(1), task_write(2, title="")))
    assert portal.writes() == []


def test_evidence_must_be_the_days_own_mail(portal):
    t = portal.add_task()
    with pytest.raises(sa.Refused):  # DONE on a received email
        run(portal, plan(2, done(t["id"], ref=f"portal://email/{IN_A}")))
    with pytest.raises(sa.Refused):  # WAITING on a sent email
        run(portal, plan(1, {"kind": "set_status", "task_id": t["id"], "status": "WAITING", "evidence": "x",
                             "evidence_ref": f"portal://email/{SENT}"}))
    with pytest.raises(sa.Refused):  # DONE without a handle
        run(portal, plan(2, done(t["id"], handle="")))


def test_without_the_days_emails_nothing_naming_an_email_is_written(portal):
    with pytest.raises(sa.Refused) as exc:
        run(portal, plan(1, task_write()), emails=None)
    assert "emails.json was not found" in exc.value.reason


def test_waiting_moves_an_open_task_and_never_one_already_closed(portal):
    t = portal.add_task()
    closed = portal.add_task(status="DONE")
    wait = {"kind": "set_status", "status": "WAITING", "evidence": "Priya said she will",
            "evidence_ref": f"portal://email/{IN_A}"}
    out = run(portal, plan(1, dict(wait, task_id=t["id"]), dict(wait, task_id=closed["id"])))
    assert [r["outcome"] for r in out["results"]] == ["updated", "skipped"]
    assert portal.tasks[t["id"]]["status"] == "WAITING" and portal.tasks[closed["id"]]["status"] == "DONE"


def test_only_the_owners_own_tasks_move(portal):
    t = portal.add_task(owner_contact_id=PRIYA, owner_name="Priya", task_contact_id=PRIYA)
    out = run(portal, plan(2, done(t["id"])))
    assert out["results"][0]["outcome"] == "skipped" and portal.tasks[t["id"]]["status"] == "TODO"


def test_done_on_a_sent_email_needs_the_tasks_contact_among_the_recipients(portal):
    t = portal.add_task(title="Send Priya the price list", task_contact_id=PRIYA, task_contact_name="Priya")
    other = portal.add_task(title="Send Marcus the price list", task_contact_id="someone-else")
    out = run(portal, plan(2, done(t["id"]), done(other["id"])))
    assert [r["outcome"] for r in out["results"]] == ["updated", "skipped"]
    assert "title words do not stand in" in out["results"][1]["reason"]


def test_a_company_handle_counts_through_a_recipients_company(portal):
    portal.contacts[PRIYA] = {"id": PRIYA, "company_id": NORTHWIND}
    t = portal.add_task(title="Quote", company_id=NORTHWIND, company_name="Northwind Traders")
    out = run(portal, plan(2, done(t["id"], handle="company Northwind Traders")))
    assert out["results"][0]["outcome"] == "updated" and "company" in out["results"][0]["handle"]


def test_the_owners_own_contact_is_never_a_handle(portal):
    t = portal.add_task(title="Something", task_contact_id=OWNER)
    portal.emails = []
    emails = {"inbound": [], "sent": [{"id": SENT, "subject": "Re: x", "recipient_contact_ids": [OWNER]}]}
    out = run(portal, plan(2, done(t["id"], handle="contact Dana")), emails=emails)
    assert out["results"][0]["outcome"] == "skipped"


def test_a_task_with_neither_needs_two_distinctive_words_of_the_email_its_own(portal):
    t = portal.add_task(title="Finalize the warehouse lease renewal")
    emails = {"inbound": [], "sent": [{"id": SENT, "subject": "Warehouse lease", "recipient_contact_ids": []}]}
    out = run(portal, plan(2, done(t["id"], handle="title words warehouse, lease")), emails=emails)
    assert out["results"][0]["outcome"] == "updated" and out["results"][0]["handle"] == "title words warehouse, lease"


def test_a_reply_subject_and_a_quoted_thread_lend_no_words(portal):
    t = portal.add_task(title="Finalize the warehouse lease renewal")
    emails = {"inbound": [], "sent": [{"id": SENT, "subject": "Re: Warehouse lease renewal",
                                       "recipient_contact_ids": []}]}
    portal.bodies[SENT] = "Sounds good.\n\nOn Tue, Priya wrote:\n> the warehouse lease renewal is attached"
    out = run(portal, plan(2, done(t["id"], handle="title words warehouse, lease")), emails=emails)
    assert out["results"][0]["outcome"] == "skipped"


def test_an_address_or_domain_lends_no_words_and_one_word_is_not_enough(portal):
    t = portal.add_task(title="Northwind warehouse quote")
    emails = {"inbound": [], "sent": [{"id": SENT, "subject": "Hello", "recipient_contact_ids": []}]}
    portal.bodies[SENT] = "Sent to northwind@example.com, see northwind.com. About the warehouse."
    out = run(portal, plan(2, done(t["id"], handle="title words")), emails=emails)
    assert out["results"][0]["outcome"] == "skipped" and "1 distinctive word" in out["results"][0]["reason"]


def test_distinctive_words_and_own_words():
    assert sa.distinctive("Follow up with Dana at Acme about the 2030 Northwind follow-up review") == ["northwind"]
    body = "Here is the plan.\nThanks\nDana\n\nFrom: Priya\nold text"
    assert sa.own_words(body) == "Here is the plan."


def meeting_note(portal, event_start, **kw):
    ev = portal.add_event(event_start)
    fields = {"associations": [{"entity_type": "calendar_event", "entity_id": ev["id"]},
                               {"entity_type": "contact", "entity_id": PRIYA}]}
    fields.update(kw)
    title = fields.pop("title", "Supplier review recap")
    return portal.add_note(title, "Discussed the quote", created_at="2030-03-06T20:00:00Z", **fields)


def test_done_on_a_meeting_note_needs_a_meeting_of_the_day(portal):
    t = portal.add_task(title="Agree the quote", task_contact_id=PRIYA)
    today = meeting_note(portal, "2030-03-06T18:00:00Z")
    earlier = meeting_note(portal, "2030-03-02T18:00:00Z")
    t2 = portal.add_task(title="Agree the terms", task_contact_id=PRIYA)
    out = run(portal, plan(2, done(t["id"], ref=f"portal://note/{today['id']}"),
                           done(t2["id"], ref=f"portal://note/{earlier['id']}")))
    assert [r["outcome"] for r in out["results"]] == ["updated", "skipped"]


@pytest.mark.parametrize("fields", [{"tags": ["nightly-sweep"]}, {"title": "Meeting Prep: Supplier review - x"},
                                    {"title": "Daily Note - 2030-03-06"}])
def test_a_note_the_sweep_wrote_or_a_prep_note_is_never_evidence(portal, fields):
    t = portal.add_task(title="Agree the quote", task_contact_id=PRIYA)
    note = meeting_note(portal, "2030-03-06T18:00:00Z", **fields)
    out = run(portal, plan(2, done(t["id"], ref=f"portal://note/{note['id']}")))
    assert out["results"][0]["outcome"] == "skipped"


def test_a_lost_create_answer_is_recovered_by_marker(portal):
    portal.fail["create_task"] = "lost"
    out = run(portal, plan(1, task_write()))
    assert out["results"][0]["outcome"] == "created" and out["results"][0]["recovered"] is True


def test_a_failed_write_is_that_writes_result_and_the_rest_go_on(portal):
    portal.fail["update_task"] = "error"
    t = portal.add_task(title="Send Priya the list", task_contact_id=PRIYA)
    out = run(portal, plan(1, task_write(), {"kind": "set_status", "task_id": t["id"], "status": "WAITING",
                                             "evidence": "x", "evidence_ref": f"portal://email/{IN_B}"}))
    assert [r["outcome"] for r in out["results"]] == ["created", "failed"] and out["status"] == "partial"


def note_write(**kw):
    w = {"kind": "create_note", "key": f"{IN_A}:fyi", "title": "FYI: New prices - 2030-03-06",
         "content": "- prices rise in April", "note_type": "background",
         "associations": [{"entity_type": "contact", "entity_id": PRIYA}]}
    w.update(kw)
    return w


def test_a_note_with_an_existing_title_or_marker_is_reused_and_needs_an_association(portal):
    portal.add_note("FYI: New prices - 2030-03-06")
    assert run(portal, plan(1, note_write()))["results"][0]["outcome"] == "reused"
    with pytest.raises(sa.Refused):
        run(portal, plan(4, note_write(associations=[])))


def test_a_note_is_found_by_its_marker_when_its_title_changed(portal):
    run(portal, plan(4, note_write()))
    [n] = portal.notes.values()
    n["title"] = "Renamed by Dana"
    out = run(portal, plan(4, note_write()))
    assert out["results"][0]["outcome"] == "reused" and "marker" in out["results"][0]["reason"]


def test_a_rejected_note_type_is_retried_without_one(portal):
    portal.fail["create_note"] = "note_type"
    out = run(portal, plan(4, note_write()))
    assert out["results"][0]["outcome"] == "created" and out["results"][0]["flags"]


def write_run(tmp_path, dry_run=False, days=(DAY,)):
    run_dir = tmp_path / "run"
    (run_dir / DAY).mkdir(parents=True)
    (run_dir / "dates.json").write_text(json.dumps({"dry_run": dry_run, "dates": [{"date": d} for d in days]}))
    (run_dir / DAY / "emails.json").write_text(json.dumps(EMAILS))
    return run_dir


def test_cli_writes_its_results_beside_the_plan(portal, tmp_path, capsys):
    run_dir = write_run(tmp_path)
    (run_dir / DAY / "phase1.json").write_text(json.dumps(plan(1, task_write())))
    with pytest.raises(SystemExit) as code:
        sa.main([str(run_dir / DAY / "phase1.json"), "--date", DAY], client=portal)
    assert code.value.code == 0
    assert json.loads((run_dir / DAY / "applied-phase1.json").read_text())["counts"] == {"created": 1}


@pytest.mark.parametrize("dates_json", [None, {"dates": [{"date": DAY}]}, {"dry_run": False, "dates": []}])
def test_without_the_runs_dates_nothing_is_written_live(portal, tmp_path, capsys, dates_json):
    run_dir = tmp_path / "run"
    (run_dir / DAY).mkdir(parents=True)
    if dates_json is not None:
        (run_dir / "dates.json").write_text(json.dumps(dates_json))
    (run_dir / DAY / "phase1.json").write_text(json.dumps(plan(1, task_write())))
    with pytest.raises(SystemExit) as code:
        sa.main([str(run_dir / DAY / "phase1.json"), "--date", DAY], client=portal)
    out = json.loads(capsys.readouterr().out)
    assert code.value.code == 3 and out["code"] == "NO_RUN" and portal.writes() == []


def test_a_dry_run_is_kept_when_the_flag_is_forgotten(portal, tmp_path, capsys, monkeypatch):
    run_dir = write_run(tmp_path, dry_run=True)
    (run_dir / DAY / "phase1.json").write_text(json.dumps(plan(1, task_write())))
    with pytest.raises(SystemExit) as code:
        sa.main([str(run_dir / DAY / "phase1.json"), "--date", DAY], client=portal)
    assert code.value.code == 3 and json.loads(capsys.readouterr().out)["code"] == "DRY_RUN"
    run_dir = write_run(tmp_path / "live")
    (run_dir / DAY / "phase1.json").write_text(json.dumps(plan(1, task_write())))
    monkeypatch.setenv("F3I_TOOLBOX_DRY_RUN", "1")
    with pytest.raises(SystemExit) as code:
        sa.main([str(run_dir / DAY / "phase1.json"), "--date", DAY], client=portal)
    assert code.value.code == 3 and json.loads(capsys.readouterr().out)["code"] == "DRY_RUN"
    assert portal.writes() == []


def test_run_mode_applies_every_dates_phases_in_order(portal, tmp_path, capsys):
    run_dir = write_run(tmp_path, days=(DAY, "2030-03-05"))
    t = portal.add_task(title="Send Priya the list", task_contact_id=PRIYA)
    (run_dir / DAY / "phase1.json").write_text(json.dumps(plan(1, task_write())))
    (run_dir / DAY / "phase2.json").write_text(json.dumps(plan(2, done(t["id"]))))
    with pytest.raises(SystemExit) as code:
        sa.main(["--run", str(run_dir)], client=portal)
    out = json.loads(capsys.readouterr().out)
    assert code.value.code == 0 and out["status"] == "applied"
    day = [d for d in out["dates"] if d["date"] == DAY][0]
    assert day["phases"]["1"]["status"] == "applied" and day["phases"]["2"]["status"] == "applied"
    assert day["phases"]["4"]["status"] == "absent"
    assert [x[0] for x in portal.writes()] == ["create_task", "update_task"]
    assert (run_dir / DAY / "applied-phase2.json").is_file()


def test_run_mode_reports_a_refused_phase(portal, tmp_path, capsys):
    run_dir = write_run(tmp_path)
    (run_dir / DAY / "phase2.json").write_text(json.dumps(plan(2, task_write())))
    with pytest.raises(SystemExit) as code:
        sa.main(["--run", str(run_dir), "--dry-run"], client=portal)
    out = json.loads(capsys.readouterr().out)
    assert code.value.code == 3 and out["dates"][0]["phases"]["2"]["code"] == "INVALID_PLAN"
