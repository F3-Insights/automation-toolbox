"""drafts_deliver.py: only reviewed drafts go to email-deliver, with its guards, and nothing is sent."""

import json

import pytest

import drafts_deliver as dd

HASH = "sha256:" + "a" * 64
CONTACT = "00000902-1111-4111-8111-111111111111"


def uid(n):
    return f"{n:08d}-2222-4222-8222-222222222222"


@pytest.fixture
def run_dir(tmp_path):
    folder = tmp_path / "run"
    folder.mkdir()
    return folder


def entry(n=1, kind="delivery", verdict="PASS", **over):
    row = {"draft_id": uid(n), "kind": kind, "contact_id": CONTACT, "email_ref": f"portal://email/{uid(100 + n)}",
           "verdict": verdict, "content_hash": HASH, "task": f"portal://task/{uid(200 + n)}", "why": "promised Friday"}
    row.update(over)
    return row


def write(run_dir, *drafts, dry_run=False, tool="drafts-deliveries"):
    (run_dir / "deliveries.json").write_text(json.dumps(
        {"tool": tool, "version": 1, "dry_run": dry_run, "drafts": list(drafts)}))


class Runner:
    def __init__(self, status="delivered", code=0):
        self.calls, self.status, self.code = [], status, code

    def __call__(self, argv):
        self.calls.append(argv)
        return self.code, {"status": self.status, "refusals": [] if self.code == 0 else [{"code": "OUTBOUND_HOLD"}]}


def go(run_dir, *extra, runner=None):
    runner = runner or Runner()
    with pytest.raises(SystemExit) as done:
        dd.main(["--run", str(run_dir), *extra], runner=runner)
    return done.value.code, runner


def result(run_dir, name="deliver.json"):
    return json.loads((run_dir / name).read_text())


def test_nothing_to_deliver_without_the_file(run_dir):
    code, runner = go(run_dir)
    assert code == 0 and result(run_dir)["status"] == "nothing" and runner.calls == []


def test_each_kind_gets_exactly_the_overrides_it_may_have(run_dir):
    write(run_dir, entry(1, "delivery"), entry(2, "holding"), entry(3, "nudge"), entry(4, "reply"))
    code, runner = go(run_dir)
    delivery, holding, nudge, reply = runner.calls
    for argv in (delivery, holding):
        assert "--follow-up" in argv and "--allow-recent-contact" in argv
    assert "--follow-up" in nudge and "--allow-recent-contact" not in nudge     # a nudge keeps every hold
    assert "--follow-up" not in reply and "--allow-recent-contact" in reply      # a reply must still be current
    assert delivery[delivery.index("--draft") + 1] == uid(1) and "--dry-run" not in delivery
    check = json.loads((run_dir / "checks" / f"{uid(1)}.json").read_text())
    assert {"verdict", "draft_id", "content_hash", "contact_id", "email_ref"} <= set(check)
    assert check["verdict"] == "PASS" and check["content_hash"] == HASH
    assert code == 0 and result(run_dir)["counts"] == {"delivered": 4}


def test_needs_your_word_and_the_question_reach_the_result(run_dir):
    write(run_dir, entry(1, "reply", needs_your_word=True, question="Which date suits?"))
    go(run_dir)
    row = result(run_dir)["results"][0]
    assert row["needs_your_word"] is True and row["question"] == "Which date suits?"
    assert row["task"] == f"portal://task/{uid(201)}"


def test_a_draft_the_reviewer_did_not_pass_stays_in_the_portal(run_dir):
    write(run_dir, entry(1, verdict="FAIL"))
    code, runner = go(run_dir)
    assert runner.calls == [] and result(run_dir)["results"][0]["code"] == "NOT_PASSED"


def test_a_refusal_is_a_result_not_a_failure(run_dir):
    write(run_dir, entry(1))
    code, runner = go(run_dir, runner=Runner(status="refused", code=3))
    row = result(run_dir)["results"][0]
    assert code == 0 and row["status"] == "refused" and row["refusals"] == [{"code": "OUTBOUND_HOLD"}]


def test_a_dry_run_sessions_set_is_never_delivered_live(run_dir):
    write(run_dir, entry(1), dry_run=True)
    code, runner = go(run_dir)
    assert code == 3 and runner.calls == []
    code, runner = go(run_dir, "--dry-run")
    assert code == 0 and "--dry-run" in runner.calls[0] and (run_dir / "deliver-dry-run.json").is_file()


@pytest.mark.parametrize("value, dry", [("true", True), ("false", False)])
def test_the_schedulers_dry_run_placeholder(run_dir, value, dry):
    write(run_dir, entry(1))
    code, runner = go(run_dir, f"--dry-run-if={value}")
    assert code == 0 and ("--dry-run" in runner.calls[0]) is dry
    assert (run_dir / ("deliver-dry-run.json" if dry else "deliver.json")).is_file()


def test_an_unclear_dry_run_placeholder_delivers_nothing(run_dir):
    write(run_dir, entry(1))
    code, runner = go(run_dir, "--dry-run-if={dry_run}")
    assert code == 2 and runner.calls == []


def test_another_tools_file_is_refused_whole(run_dir):
    write(run_dir, entry(1), tool="task-keeper-deliveries")
    code, runner = go(run_dir)
    assert code == 3 and runner.calls == []


@pytest.mark.parametrize("bad", [{"draft_id": "d1"}, {"kind": "chase"}, {"contact_id": None},
                                 {"email_ref": "portal://note/x"}, {"content_hash": "abc"}])
def test_a_malformed_entry_is_refused_alone(run_dir, bad):
    write(run_dir, entry(1, **bad), entry(2))
    code, runner = go(run_dir)
    rows = result(run_dir)["results"]
    assert rows[0]["code"] == "INVALID_ENTRY" and rows[1]["status"] == "delivered" and len(runner.calls) == 1


def test_the_runaway_backstop_leaves_the_rest_in_the_portal(run_dir):
    write(run_dir, *(entry(n) for n in range(1, 5)))
    code, runner = go(run_dir, "--max-drafts", "2")
    assert len(runner.calls) == 2 and result(run_dir)["counts"] == {"delivered": 2, "left_in_portal": 2}


def test_a_draft_listed_twice_is_delivered_once(run_dir):
    write(run_dir, entry(1), entry(1))
    code, runner = go(run_dir)
    assert len(runner.calls) == 1 and result(run_dir)["results"][1]["code"] == "DUPLICATE_ENTRY"


def test_it_runs_the_email_deliver_beside_it():
    assert dd.EMAIL_DELIVER.is_file() and "--follow-up" in dd.EMAIL_DELIVER.read_text()


def test_this_script_never_pushes_or_sends_itself():
    source = (dd.EMAIL_DELIVER.parent / "drafts_deliver.py").read_text()
    assert ".call(" not in source and "draft_push" not in source
