"""confirm-portal: the request's task is found or made once, on the owner's own list; answers are
read from the task and the mail; finishing comments and closes only the request's own task."""

import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import _common as c  # noqa: E402
import confirm_portal as cp  # noqa: E402

OWNER = "00000000-0000-4000-8000-000000000001"
CONTACT = "00000000-0000-4000-8000-000000000002"
TASK = "00000000-0000-4000-8000-000000000003"
EMAIL = "00000000-0000-4000-8000-000000000004"
AT = "2030-03-04T12:00:00+00:00"
QUESTION = "Is the March freight invoice for March or February?"
RID = "CR-3fa91b2c7d"


class FakeClient:
    def __init__(self, tasks=None, emails=None, comments=None):
        self.tasks = {t["id"]: t for t in tasks or []}
        self.emails, self.comments, self.calls = emails or [], comments or [], []

    def call(self, name, args=None):
        args = args or {}
        self.calls.append((name, args))
        if name == "whoami":
            return {"principal": {"contact_id": OWNER}}
        if name == "list_entities" and args["entity_type"] == "task":
            needle = args["filters"]["search"]
            return {"items": [t for t in self.tasks.values() if needle in t.get("description", "")], "has_more": False}
        if name == "list_entities" and args["entity_type"] == "email":
            return {"items": self.emails, "has_more": False}
        if name == "create_task":
            self.tasks[TASK] = dict(args, id=TASK, status="TODO")
            return {"id": TASK}
        if name == "update_task":
            self.tasks[args["id"]]["status"] = args["status"]
            return {"id": args["id"]}
        if name == "create_task_comment":
            return {"ok": True}
        if name == "get":
            return {"task": self.tasks.get(args["id_or_query"], {}), "comments": self.comments}
        raise AssertionError(f"unexpected call {name}")

    def created(self):
        return next(a for n, a in self.calls if n == "create_task")


def request(**kw):
    out = {"id": RID, "question": QUESTION, "asked_of": "AP lead", "person": "Jordan Lee <jordan@acme.test>",
           "contact_id": CONTACT, "due": "2030-03-06", "context": "the invoice", "fallback": "escalate"}
    out.update(kw)
    return out


def test_the_task_waits_on_the_person_carries_its_marker_and_sits_on_the_owners_list():
    client = FakeClient()
    out = cp.ensure_task(client, request())
    assert out["outcome"] == "created" and out["status"] == "WAITING"
    created = client.created()
    assert created["description"].splitlines()[-1] == f"confirmation-request:{RID}"
    assert created["owner_contact_id"] == OWNER and created["waiting_on_contact_id"] == CONTACT
    assert created["title"] == f"Confirm with Jordan Lee: {QUESTION}" and "assignees" not in created


def test_a_relayed_task_asks_the_owner_to_put_the_question():
    client = FakeClient()
    cp.ensure_task(client, request(relayed=True))
    assert "Please put this question to Jordan Lee" in client.created()["description"]
    assert client.created()["waiting_reason"] == "confirmation relayed through the owner"


def test_a_question_to_the_owner_waits_on_no_one():
    client = FakeClient()
    out = cp.ensure_task(client, request(asked_of="owner", person="", contact_id=None))
    assert client.created()["title"] == f"Confirm: {QUESTION}" and "waiting_on_contact_id" not in client.created()
    assert out["status"] == "TODO" and not any(n == "update_task" for n, _ in client.calls)


def test_a_task_found_by_marker_is_never_duplicated_and_a_dry_run_writes_nothing():
    client = FakeClient(tasks=[{"id": TASK, "status": "WAITING", "description": f"Question: x\nconfirmation-request:{RID}"}])
    assert cp.ensure_task(client, request())["outcome"] == "found"
    client = FakeClient()
    assert cp.ensure_task(client, request(dry_run=True))["outcome"] == "would_create"
    assert not any(n in ("create_task", "update_task") for n, _ in client.calls)


def test_look_reads_a_persons_newer_comment_and_ignores_agents_and_older_ones():
    comments = [{"author_name": "Jordan Lee", "body": "old", "created_at": "2030-03-01T10:00:00Z"},
                {"author_name": "Owner", "body": "Chasing.\n(posted by close, an agent)", "created_at": "2030-03-05T10:00:00Z"},
                {"author_name": "Jordan Lee", "body": "Yes, February.", "created_at": "2030-03-05T18:00:00Z"}]
    out = cp.look(FakeClient(tasks=[{"id": TASK, "status": "WAITING"}], comments=comments),
                  {"requests": [{"id": RID, "task": f"portal://task/{TASK}", "asked_at": AT}]})
    (found,) = out["findings"]
    assert found["kind"] == "comment" and found["text"] == "Yes, February." and found["by"] == "Jordan Lee"


def test_look_reports_done_and_cancelled_tasks():
    for status, kind in (("DONE", "task_done"), ("CANCELLED", "task_cancelled")):
        out = cp.look(FakeClient(tasks=[{"id": TASK, "status": status}]),
                      {"requests": [{"id": RID, "task": TASK, "asked_at": AT}]})
        assert out["findings"][0]["kind"] == kind


def test_look_matches_an_email_reply_by_subject_after_the_request_and_skips_what_was_seen():
    emails = [{"id": "00000000-0000-4000-8000-0000000000aa", "subject": "RE: March freight invoice",
               "received_at": "2030-03-01T10:00:00Z", "from_address": "jordan@acme.test"},
              {"id": EMAIL, "subject": "RE: March freight invoice", "received_at": "2030-03-05T16:00:00Z",
               "from_address": "jordan@acme.test", "snippet": "February."},
              {"id": "00000000-0000-4000-8000-0000000000bb", "subject": "Lunch?", "received_at": "2030-03-05T17:00:00Z",
               "from_address": "jordan@acme.test"}]
    req = {"id": RID, "contact_id": CONTACT, "subject": "March freight invoice", "asked_at": AT}
    (found,) = cp.look(FakeClient(emails=emails), {"requests": [req]})["findings"]
    assert found["kind"] == "email_reply" and found["evidence"] == f"portal://email/{EMAIL}"
    assert cp.look(FakeClient(emails=emails), {"requests": [dict(req, seen=[f"portal://email/{EMAIL}"])]})["findings"] == []


def test_finish_comments_then_closes_and_leaves_a_closed_task_alone():
    client = FakeClient(tasks=[{"id": TASK, "status": "WAITING", "description": f"confirmation-request:{RID}"}])
    out = cp.finish(client, {"task_id": TASK, "status": "DONE", "comment": "Closed: yes.", "id": RID})
    assert out["outcome"] == "DONE" and [n for n, _ in client.calls].count("create_task_comment") == 1
    assert cp.finish(client, {"task_id": TASK, "status": "DONE", "id": RID})["outcome"] == "already DONE"


def test_finish_refuses_a_task_that_is_not_the_requests():
    client = FakeClient(tasks=[{"id": TASK, "status": "WAITING", "description": "someone else's task"}])
    with pytest.raises(c.Failure, match="not this request's task"):
        cp.finish(client, {"task_id": TASK, "status": "DONE", "id": RID})


def test_the_command_reads_stdin_and_prints_json(monkeypatch, capsys):
    monkeypatch.setattr(c, "client", lambda: FakeClient(tasks=[{"id": TASK, "status": "DONE"}]))
    monkeypatch.setattr(sys, "argv", ["confirm_portal.py", "look"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"requests": [{"id": RID, "task": TASK, "asked_at": AT}]})))
    cp.main()
    assert json.loads(capsys.readouterr().out)["findings"][0]["kind"] == "task_done"
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
    with pytest.raises(SystemExit) as exc:
        cp.main()
    assert exc.value.code == 2 and json.loads(capsys.readouterr().out)["status"] == "error"
