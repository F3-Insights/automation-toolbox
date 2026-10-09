"""issue_harvest_record.py: decisions and issue-file results become ledger states."""

import _common as c
import issue_file as ifile
import issue_harvest_record as rec
from conftest import APP, harvest, new, run_folder


def file_into(home, run):
    c.write_new(run / "filed.json", ifile.run(run, home["settings"], home["repos"], False, 30))


def test_maps_outcomes_to_ledger_states(home, github, capsys):
    github.add(APP, 7, "WA-20300301-EXPORT: export fails")
    decisions = [new("portal-notes:n1", also=["portal-tasks:t1"]),
                 {"source": "portal-email:e1", "decision": "duplicate", "repo": APP, "issue": 7, "reason": "same"},
                 {"source": "portal-notes:n3", "decision": "ask", "question": "Which repository?"}]
    run = run_folder(home, harvest(home), decisions)
    file_into(home, run)
    assert rec.main(["--run", str(run)]) == 0
    assert capsys.readouterr().out.startswith("RECORDED: 2 filed, 0 commented, 1 duplicate, 0 not-software, 1 asked")
    book = c.ledger_book(home["state"])
    assert book["portal-notes:n1"]["state"] == "filed" and book["portal-notes:n1"]["verified"] == "yes"
    assert book["portal-tasks:t1"]["state"] == "filed" and "carried by" in book["portal-tasks:t1"]["note"]
    assert book["portal-email:e1"]["state"] == "duplicate" and book["portal-notes:n3"]["state"] == "asked"
    assert len(c.runs(home["state"])) == 1


def test_counts_attempts_to_stuck(home, github):
    h = harvest(home)
    for _ in range(3):
        assert rec.main(["--run", str(run_folder(home, h, []))]) == 0
    book = c.ledger_book(home["state"])
    assert {r["state"] for r in book.values()} == {"stuck"} and book["portal-notes:n1"]["attempts"] == "3"


def test_dry_run_writes_no_ledger(home, github, capsys):
    run = run_folder(home, harvest(home), [new("portal-notes:n1")])
    assert rec.main(["--run", str(run), "--dry-run-if", "true"]) == 0
    assert capsys.readouterr().out.startswith("WOULD RECORD:")
    assert not c.ledger_path(home["state"]).exists() and (run / "record-dry-run.json").is_file()


def test_one_item_in_parts_and_a_failed_part_leaves_it_open(home, github):
    h = harvest(home)
    ok = [new("portal-email:e1", part="1", title="WA-20300316-ONE: first bug"),
          new("portal-email:e1", part="2", title="WA-20300316-TWO: second bug")]
    run = run_folder(home, h, ok)
    file_into(home, run)
    assert rec.main(["--run", str(run)]) == 0
    row = c.ledger_book(home["state"])["portal-email:e1"]
    assert row["state"] == "filed" and row["issue"] == "100 101" and len(row["marker"].split(",")) == 2

    bad = [new("portal-tasks:t1", part="1", title="WA-20300316-ONE: third bug"),
           new("portal-tasks:t1", part="2", title="not the convention")]
    run = run_folder(home, h, bad)
    file_into(home, run)
    assert rec.main(["--run", str(run)]) == 0
    row = c.ledger_book(home["state"])["portal-tasks:t1"]
    assert row["state"] == "seen" and row["attempts"] == "2"  # undecided last Run, failed this one


def test_no_harvest_is_stale_and_a_missing_folder_exits_2(home, tmp_path, capsys):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert rec.main(["--run", str(empty)]) == 0 and capsys.readouterr().out.startswith("STALE:")
    assert rec.main(["--run", str(tmp_path / "nope")]) == 2
