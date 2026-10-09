"""Produce-work, the improvement on a branch, the receipt, the records and the messages, against
a fake Portal, a throwaway git repository and a fake notify script."""

import json
import subprocess

import pytest

import _common as c
import chief_of_staff_cycle as cy
import chief_of_staff_improve as im
import chief_of_staff_produce_work as pw
import chief_of_staff_receipt as rc
import chief_of_staff_records as rd
from conftest import OWNER, TASK, FakePortal


@pytest.fixture
def cycle(root):
    return c.Path(cy.start(root, c.local_now().date().isoformat())["folder"])


@pytest.fixture
def dry_cycle(root):
    return c.Path(cy.start(root, c.local_now().date().isoformat(), dry_run=True)["folder"])


@pytest.fixture
def portal():
    p = FakePortal()
    p.records[TASK] = {"task": {"id": TASK, "title": "Send Lakeview Hardware the revised quote"}}
    return p


# --------------------------------------------------------------------------- produce-work

GOOD = {"status": "prepared", "title": "Reply to Lakeview Hardware", "artifact": "Hi Priya,\n\n" + "Draft text. " * 30,
        "source_refs": [f"portal://task/{TASK}"], "assumptions": [], "review_needed": ["Confirm the price"]}


def test_pack_refuses_free_text_and_an_echoed_miss(portal, root, cycle):
    with pytest.raises(c.Bad):
        pw.pack(portal, root, "task: the quote", cycle)
    with pytest.raises(c.Bad):
        pw.pack(portal, root, "task:00000999-1111-4111-8111-111111111111", cycle)


def test_pack_save_and_no_duplicate(portal, root, cycle):
    out = pw.pack(portal, root, f"task:{TASK}", cycle)
    assert out["status"] == "ok" and "setting:principles" in out["sources"]
    saved = pw.save(root, f"task:{TASK}", out["fingerprint"], json.dumps(GOOD), cycle)
    assert saved["status"] == "prepared" and c.Path(saved["local_path"]).read_text().startswith("Hi Priya")
    assert pw.pack(portal, root, f"task:{TASK}", cycle)["status"] == "already_prepared"


def test_save_refuses_unknown_sources_and_short_work_and_holds_a_block(portal, root, cycle):
    fp = pw.pack(portal, root, f"task:{TASK}", cycle)["fingerprint"]
    bad = dict(GOOD, source_refs=["portal://task/other"])
    assert pw.save(root, f"task:{TASK}", fp, json.dumps(bad), cycle)["status"] == "invalid"
    assert pw.save(root, f"task:{TASK}", fp, json.dumps(dict(GOOD, artifact="short")), cycle)["status"] == "invalid"
    blocked = pw.save(root, f"task:{TASK}", fp, '{"status": "blocked", "reason": "no price in the record"}', cycle)
    assert blocked["status"] == "blocked"
    assert pw.pack(portal, root, f"task:{TASK}", cycle)["status"] == "held"


def test_a_dry_run_cycle_packs_and_saves_nothing(portal, root, dry_cycle):
    out = pw.pack(portal, root, f"task:{TASK}", dry_cycle)
    assert out["status"] == "would_pack" and not (root / "artifacts").exists()
    assert pw.save(root, f"task:{TASK}", out["fingerprint"], json.dumps(GOOD), dry_cycle)["status"] == "would_save"


# --------------------------------------------------------------------------- the improvement

def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


@pytest.fixture
def repo(tmp_path, owner):
    r = tmp_path / "toolbox"
    (r / "productivity" / "skills" / "meeting-prep").mkdir(parents=True)
    (r / "productivity" / "skills" / "meeting-prep" / "SKILL.md").write_text(
        "# Meeting prep\n\nGather the attendees.\nWrite one note.\n")
    git("init", "-q", "-b", "main", cwd=r)
    git("-c", "user.name=Dana", "-c", "user.email=dana@example.test", "add", ".", cwd=r)
    git("-c", "user.name=Dana", "-c", "user.email=dana@example.test", "commit", "-q", "-m", "start", cwd=r)
    git("config", "user.name", "Dana", cwd=r)
    git("config", "user.email", "dana@example.test", cwd=r)
    settings = tmp_path / "settings.toml"
    settings.write_text(settings.read_text().replace(
        "[chief-of-staff-cycle]", f'[chief-of-staff-cycle]\nimprovements = "commit"\nimprove_repo = "{r}"'))
    return r


def propose(cycle, target="meeting-prep"):
    c.atomic_json(cycle / "decision.json", {"improvement": {"target": target, "change": "Name the agenda",
                                                            "rationale": "two notes had none"}})


def reply(old="Write one note.", new="Write one note with the agenda first.", result="APPLIED: the note names the agenda"):
    return json.dumps({"result": result, "old": old, "new": new})


def test_the_default_is_propose_and_nothing_is_edited(cycle, portal):
    propose(cycle)
    out = im.check(cycle, c.root_of(cycle))
    assert out["status"] == "proposed"
    (cycle / "receipt.json").write_text(json.dumps({"content": "Ran: nothing."}))
    published = rc.publish(portal, cycle)
    assert any(t["title"].startswith("[Chief of Staff] Improve meeting-prep") for t in published["tasks"])


def test_commit_lands_on_the_branch_and_never_in_the_checkout(cycle, repo):
    propose(cycle)
    out = im.check(cycle, c.root_of(cycle))
    assert out["status"] == "ok" and out["branch"] == "chief-of-staff/improvements"
    done = im.apply(cycle, reply())
    assert done["status"] == "committed"
    assert "agenda first" not in (repo / "productivity/skills/meeting-prep/SKILL.md").read_text()
    assert git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo).strip() == "main"
    log = git("log", "-1", "--format=%B", "chief-of-staff/improvements", cwd=repo)
    assert log.startswith("chief-of-staff: the note names the agenda") and "Chief-of-Staff-Cycle:" in log


def test_the_live_checkout_is_never_the_worktree_and_nothing_is_pushed(cycle, repo, tmp_path):
    # A remote the repository could push to: after a commit it must still lack the branch.
    remote = tmp_path / "remote.git"
    git("init", "-q", "--bare", str(remote), cwd=tmp_path)
    git("remote", "add", "origin", str(remote), cwd=repo)
    propose(cycle)
    assert im.check(cycle, c.root_of(cycle))["status"] == "ok"
    assert im.apply(cycle, reply())["status"] == "committed"
    assert git("branch", "--list", cwd=remote).strip() == ""
    # A state folder whose improvement worktree is really the live checkout is refused.
    wt = c.root_of(cycle) / "improve-worktree"
    git("worktree", "remove", "--force", str(wt), cwd=repo)
    wt.symlink_to(repo, target_is_directory=True)
    propose(cycle)
    out = im.check(cycle, c.root_of(cycle))
    assert out["status"] == "refused" and "own checkout" in out["reason"]
    assert "agenda first" not in (repo / "productivity/skills/meeting-prep/SKILL.md").read_text()


def test_apply_refuses_a_worktree_swapped_for_the_checkout(cycle, repo):
    propose(cycle)
    state = im.check(cycle, c.root_of(cycle))
    assert state["status"] == "ok"
    state.update(worktree=str(repo), path=str(repo / state["relative"]))
    c.atomic_json(cycle / "improve.json", state)
    out = im.apply(cycle, reply())
    assert out["status"] == "refused" and out["code"] == "NOT_A_WORKTREE"
    assert "agenda first" not in (repo / "productivity/skills/meeting-prep/SKILL.md").read_text()


def test_skipped_unchanged_and_wrong_text_commit_nothing(cycle, repo):
    propose(cycle)
    im.check(cycle, c.root_of(cycle))
    assert im.apply(cycle, json.dumps({"result": "SKIPPED: already there"}))["status"] == "not_applied"
    im.check(cycle, c.root_of(cycle))
    assert im.apply(cycle, reply(old="not in the file"))["code"] == "NOT_FOUND"
    im.check(cycle, c.root_of(cycle))
    assert im.apply(cycle, reply(new="Write one note."))["status"] == "unchanged"


def test_a_large_edit_is_refused_before_anything_is_written(cycle, repo):
    propose(cycle)
    out = im.check(cycle, c.root_of(cycle))
    done = im.apply(cycle, reply(new="\n".join(f"line {i}" for i in range(40))))
    assert done["code"] == "TOO_LARGE" and "line 3" not in c.Path(out["path"]).read_text()


def test_a_dirty_worktree_or_a_dry_run_applies_nothing(cycle, dry_cycle, repo):
    propose(cycle)
    out = im.check(cycle, c.root_of(cycle))
    (c.Path(out["worktree"]) / "stray.txt").write_text("someone else's work")
    assert im.apply(cycle, reply())["code"] == "DIRTY"
    assert im.check(cycle, c.root_of(cycle))["status"] == "refused"
    propose(dry_cycle)
    assert im.check(dry_cycle, c.root_of(dry_cycle))["status"] == "would_apply"
    assert im.apply(dry_cycle, reply())["status"] == "would_commit"


def test_no_improvement_is_none(cycle):
    c.atomic_json(cycle / "decision.json", {})
    assert im.check(cycle, c.root_of(cycle))["status"] == "none"


# --------------------------------------------------------------------------- the receipt

def write_receipt(cycle, content="**Ran**: meeting-prep - one prep note", decisions=None):
    (cycle / "receipt.json").write_text(json.dumps({"content": content, "decisions": decisions or []}))


def test_one_note_a_day_and_one_block_per_cycle(portal, root, cycle):
    write_receipt(cycle)
    first = rc.publish(portal, cycle)
    assert first["status"] == "published" and first["note"]["action"] == "created"
    assert rc.publish(portal, cycle)["note"]["action"] == "already"
    second = c.Path(cy.start(root, c.local_now().date().isoformat())["folder"])
    write_receipt(second, "### 10:00\nRan: nothing")
    assert rc.publish(portal, second)["note"]["action"] == "appended"
    assert len(portal.notes) == 1 and rc.verify(portal, second)["this_cycle_written"]


def test_the_receipt_refuses_local_paths_and_em_dashes(portal, cycle):
    write_receipt(cycle, "Draft at ~/state/artifact.md " + chr(0x2014) + " ready")
    out = rc.publish(portal, cycle)
    assert out["status"] == "refused" and set(out["codes"]) == {"EM_DASH", "LOCAL_PATH"} and not portal.notes


def test_decisions_are_capped_at_three_a_day_and_reused(portal, cycle):
    decisions = [{"title": f"Choose option {n}", "domain": "Sales"} for n in range(4)]
    decisions.append({"title": "[Chief of Staff] Choose option 0"})
    write_receipt(cycle, decisions=decisions)
    actions = [t["action"] for t in rc.publish(portal, cycle)["tasks"]]
    assert actions == ["created", "created", "created", "capped", "reused"]
    assert all(t["owner_contact_id"] == OWNER for t in portal.tasks)


def test_a_failed_count_creates_none_and_an_unknown_domain_files_unfiled(portal, cycle):
    write_receipt(cycle, decisions=[{"title": "Pick a vendor", "domain": "Unknown"}])
    portal.fail_tasks = True
    assert rc.publish(portal, cycle)["tasks"][0]["action"] == "failed" and not portal.tasks
    portal.fail_tasks = False
    assert rc.publish(portal, cycle)["tasks"][0]["action"] == "created"


def test_a_dry_run_publishes_nothing_and_the_runner_switch_refuses(portal, cycle, dry_cycle, monkeypatch):
    write_receipt(dry_cycle)
    assert rc.publish(portal, dry_cycle)["status"] == "dry_run" and not portal.notes
    write_receipt(cycle)
    monkeypatch.setenv("F3I_TOOLBOX_DRY_RUN", "1")
    assert rc.publish(portal, cycle)["status"] == "refused" and not portal.notes


def test_verify_matches_the_title_structurally(portal, cycle):
    portal.notes.append({"id": "n9", "title": "Notes about the Chief of Staff Receipt process", "content": ""})
    assert rc.verify(portal, cycle)["status"] == "missing"


# --------------------------------------------------------------------------- records

def receipt_with(cycle, **kw):
    (cycle / "receipt.json").write_text(json.dumps({"content": "x", **kw}))


def test_roster_health_only_for_dispatched_doers(cycle, owner):
    cy.record(cycle, "meeting-prep", "Fabrikam", "dispatched", "one note")
    receipt_with(cycle, team_updates=[{"doer": "meeting-prep", "health": "Ran clean.", "trust": "TRUSTED"},
                                      {"doer": "produce-work", "health": "x"}])
    out = rd.apply(cycle)
    assert [r["action"] for r in out["roster"]] == ["updated", "skipped"]
    assert "| meeting-prep | TRUSTED | Ran clean. |" in (owner / "roster.md").read_text()


def test_ledger_one_line_once_in_format_and_a_principle_once(cycle, owner):
    line = "- 2030-03-04 | Chief of Staff | meeting-prep promoted to TRUSTED (receipt)"
    receipt_with(cycle, journal=line, doctrine={"slug": "agenda-first", "body": "# Draft principle: agenda first"})
    assert rd.apply(cycle)["ledger"]["action"] == "appended"
    out = rd.apply(cycle)
    assert out["ledger"]["action"] == "already" and out["principle"]["action"] == "already"
    assert (owner / "ledger.md").read_text().count(line) == 1
    receipt_with(cycle, journal="something else")
    assert rd.apply(cycle)["ledger"]["action"] == "refused"


def test_a_dry_run_changes_no_record(dry_cycle, owner):
    before = (owner / "ledger.md").read_text()
    receipt_with(dry_cycle, journal="- 2030-03-04 | Chief of Staff | an event (ref)")
    assert rd.apply(dry_cycle)["ledger"]["action"] == "would_append"
    assert (owner / "ledger.md").read_text() == before


# --------------------------------------------------------------------------- messages

class Sender:
    def __init__(self, sent=True):
        self.sent, self.calls = sent, []

    def __call__(self, argv, timeout=180):
        self.calls.append(argv)
        return (0 if self.sent else 1), json.dumps({"sent": self.sent, "channel": "teams", "reason": "blocked"}), ""


def test_the_receipt_link_goes_once_a_day_and_only_when_verified(cycle, monkeypatch):
    sender = Sender()
    monkeypatch.setattr(c, "run_script", sender)
    assert c.notify(cycle, "receipt", c.root_of(cycle))["status"] == "skipped"
    c.atomic_json(cycle / "verify.json", {"status": "found", "note_id": "n1", "this_cycle_written": True})
    assert c.notify(cycle, "receipt", c.root_of(cycle))["status"] == "sent"
    assert "https://portal.example.test/notes/n1" in sender.calls[0]
    assert c.notify(cycle, "receipt", c.root_of(cycle))["status"] == "held"


def test_a_refused_send_is_not_counted_and_off_sends_nothing(cycle, monkeypatch):
    c.atomic_json(cycle / "verify.json", {"status": "found", "decisions_created": 1, "decision_ids": ["t1"],
                                          "first_decision": "[Chief of Staff] Pick a vendor"})
    monkeypatch.setattr(c, "run_script", Sender(sent=False))
    assert c.notify(cycle, "decision", c.root_of(cycle))["status"] == "not_sent"
    monkeypatch.setenv("NOTIFY_OWNER_MODE", "off")
    assert c.notify(cycle, "decision", c.root_of(cycle))["status"] == "skipped"
