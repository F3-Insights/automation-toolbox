"""task_asks_queue.py and task_asks_record.py against an invented Portal."""

import json

import pytest

import _common as c
import task_asks_queue as q
import task_asks_record as r
from conftest import BOARD, CEO, NOW, STAFF, FakePortal, ago, email, uid

AS_OF = NOW.isoformat()


def queue(tmp_path, domain_file, portal=None, *extra):
    out = tmp_path / f"run{len(list(tmp_path.glob('run*')))}" / "asks-queue.json"
    q.main(["--domain", "Northwind", "--domain-file", str(domain_file), "--as-of", AS_OF, "--out", str(out),
            *extra], client=portal or FakePortal())
    return out, json.loads(out.read_text())


def test_scope_keeps_the_domain_and_drops_the_rest(tmp_path, domain_file):
    _, data = queue(tmp_path, domain_file)
    keys = {i["key"] for i in data["items"]}
    assert keys == {f"asks:email:{uid(n)}" for n in (1, 2, 3, 6)} | {"asks:meeting:rec1"}
    n = data["counts"]
    assert (n["ignored"], n["out_of_scope"], n["unmatched_meetings"]) == (1, 2, 1)  # 4 ignored; 5 and rec2 out
    assert data["domain"]["catch_all_project"] and data["window"]["first_run"]


def test_vips_come_from_roles_and_titles_and_go_first(tmp_path, domain_file):
    _, data = queue(tmp_path, domain_file)
    assert {v["contact_id"] for v in data["vips"]} == {CEO, BOARD}  # not the controller, a past member or the owner
    order = [(i["key"].rsplit(":", 1)[1], i["vip"]) for i in data["items"]]
    assert [v for _, v in order] == [True, True, True, False, False]
    assert order[0][0] == uid(1) and order[3][0] == uid(2)  # VIPs newest first, then the rest newest first
    sent_to_board = next(i for i in data["items"] if i["key"].endswith(uid(6)))
    assert sent_to_board["vips"][0]["contact_id"] == BOARD
    assert sent_to_board["default_due"] == "2030-03-07"  # 3 business days for a VIP on sent mail
    to_kim = next(i for i in data["items"] if i["key"].endswith(uid(3)))
    assert to_kim["default_due"] == "2030-03-11" and STAFF in to_kim["counterparties"]["contact_ids"]


def test_a_vip_rule_matching_nobody_warns():
    rule = {"company": "Northwind Traders", "roles": ["investor"], "titles": []}
    _, warnings = q.resolve_vips(FakePortal(), [rule], uid(900))
    assert warnings and "nobody" in warnings[0]


def test_already_finds_the_key_and_its_later_asks(tmp_path, domain_file):
    key = f"asks:email:{uid(3)}"
    tasks = [{"id": uid(77), "title": "Collect the lease from Kim", "status": "WAITING",
              "description": f"Why: asked\nCaptured from: {key}:2\nMarker: x"},
             {"id": uid(78), "title": "Other", "status": "TODO",
              "description": f"Captured from: {key}0\n"}]
    _, data = queue(tmp_path, domain_file, FakePortal(tasks=tasks))
    item = next(i for i in data["items"] if i["key"] == key)
    assert [a["task"] for a in item["already"]] == [f"portal://task/{uid(77)}"]


def test_cap_defers_and_out_never_overwrites(tmp_path, domain_file):
    out, data = queue(tmp_path, domain_file, None, "--max", "2", "--batch-size", "1")
    assert len(data["items"]) == 2 and len(data["deferred"]) == 3 and data["batches"] == ["b1", "b2"]
    with pytest.raises(SystemExit):
        q.main(["--domain", "Northwind", "--domain-file", "x", "--out", str(out)], client=FakePortal())


def write_changes(run, asks, ops=(), results=()):
    (run / "changes.json").write_text(json.dumps({"tool": "task-stack-changes", "version": 1, "dry_run": False,
                                                  "ops": list(ops), "asks": asks}))
    (run / "apply.json").write_text(json.dumps({"results": list(results)}))


def test_cursor_moves_only_past_what_was_decided(tmp_path, domain_file):
    out, data = queue(tmp_path, domain_file, None, "--max", "4")
    run = out.parent
    items = data["items"]
    asks = [{"source": items[0]["key"], "decision": "create", "ops": ["n1"]},
            {"source": items[1]["key"], "decision": "skip"},
            {"source": items[2]["key"], "decision": "create", "ops": ["n2"]},
            {"source": items[3]["key"], "decision": "exists"}]
    write_changes(run, asks, results=[{"id": "n1", "outcome": "applied"},
                                      {"id": "n2", "outcome": "refused", "code": "NOT_ASSIGNABLE"}])
    assert r.main(["--run", str(run), "--dry-run-if=true"]) == 0
    assert not c.cursor_path("Northwind").exists() and (run / "asks-record-dry-run.json").is_file()
    assert r.main(["--run", str(run), "--dry-run-if=false"]) == 0
    cursor = c.read_cursor(c.cursor_path("Northwind"))
    undecided = [items[2]["date"], data["deferred"][0]["date"]]
    assert c.parse_time(cursor["since"]) < min(c.parse_time(d) for d in undecided)
    assert items[2]["key"] not in cursor["decided"] and items[0]["key"] in cursor["decided"]

    _, again = queue(tmp_path, domain_file)
    keys = {i["key"] for i in again["items"]}
    assert items[2]["key"] in keys and data["deferred"][0]["key"] in keys
    assert not keys & {items[0]["key"], items[1]["key"], items[3]["key"]}
    assert not again["window"]["first_run"]


def test_cursor_reaches_until_when_everything_is_decided(tmp_path, domain_file):
    out, data = queue(tmp_path, domain_file)
    write_changes(out.parent, [{"source": i["key"], "decision": "skip"} for i in data["items"]])
    r.main(["--run", str(out.parent)])
    cursor = c.read_cursor(c.cursor_path("Northwind"))
    assert cursor["since"] == data["window"]["until"]
    assert set(cursor["decided"]) == {i["key"] for i in data["items"]}  # all inside the overlap, so kept
    _, again = queue(tmp_path, domain_file)
    assert again["items"] == [] and again["window"]["since"] == c.iso(c.parse_time(cursor["since"]) - c.OVERLAP)


def test_mail_synced_late_is_read_inside_the_overlap_and_old_keys_are_pruned(tmp_path, domain_file):
    out, data = queue(tmp_path, domain_file)
    write_changes(out.parent, [{"source": i["key"], "decision": "skip"} for i in data["items"]])
    path = c.cursor_path("Northwind")
    r.main(["--run", str(out.parent)])
    stale = dict(c.read_cursor(path), decided={**c.read_cursor(path)["decided"], "asks:email:old": ago(24 * 5)})
    c.write_cursor(path, stale)
    portal = FakePortal()
    portal.emails.append(email(8, "received", 30, "kim@northwind.test", ["dana@northwind.test"], STAFF, [], "Late"))
    out2, again = queue(tmp_path, domain_file, portal)
    assert [i["key"] for i in again["items"]] == [f"asks:email:{uid(8)}"]  # dated before the cursor, synced after
    write_changes(out2.parent, [{"source": again["items"][0]["key"], "decision": "skip"}])
    r.main(["--run", str(out2.parent)])
    assert "asks:email:old" not in c.read_cursor(path)["decided"]


def test_a_meeting_names_its_attendees_contacts_and_the_delegated_follow_up(tmp_path, domain_file):
    _, data = queue(tmp_path, domain_file)
    meeting = next(i for i in data["items"] if i["direction"] == "meeting")
    people = {p["address"]: p["contact_id"] for p in meeting["counterparties"]["people"]}
    assert people == {"board@northwind.test": BOARD, "kim@northwind.test": STAFF, "guest@northwind.test": None}
    assert meeting["counterparties"]["contact_ids"] == [BOARD, STAFF] and meeting["owner_attended"]
    assert (meeting["default_due"], meeting["delegated_due"]) == ("2030-03-06", "2030-03-07")  # VIP: 2 and 3 days


def test_the_domain_file_needs_its_yaml_block(tmp_path):
    bad = tmp_path / "bad.md"
    bad.write_text("# no block\n")
    with pytest.raises(c.Bad):
        c.load_scope(bad)


def test_received_scope_reads_cc_and_ignore_is_case_insensitive(domain_file):
    scope, owner = c.load_scope(domain_file), uid(900)
    row = {"id": uid(50), "received_at": NOW.isoformat(), "from_address": "Kim@Fabrikam.test",
           "to_addresses": ["pat@fabrikam.test"], "cc_addresses": ["Dana@Northwind.test"]}
    item, _ = q.email_item(row, "received", owner, ["dana@northwind.test"], scope, {}, {})
    assert item and item["counterparties"]["addresses"] == ["kim@fabrikam.test", "pat@fabrikam.test"]
    loud = dict(row, from_address="ALERTS@NOTIFY.Northwind.test")
    assert q.email_item(loud, "received", owner, ["dana@northwind.test"], scope, {}, {}) == (None, "ignored")
