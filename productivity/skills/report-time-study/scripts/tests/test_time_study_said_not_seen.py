import json

from conftest import SAID_SCHEMA, make_window

import time_study_said_not_seen as sns


def said(home, w):
    return json.loads((home / "out" / f"said-not-seen-{w.name}.json").read_text())


def test_structured_free_text_and_table_lines_are_all_read(home):
    w = make_window(home, "2030-09-01_to_2030-09-02")
    (w / "days" / "2030-09-02" / "day.md").write_text(
        "# x\n## Said but not seen\n\n| # | Commitment | Later evidence |\n|---|---|---|\n"
        "| 1 | Book the warehouse visit (11:40) | none seen |\n## Questions\n")
    assert sns.main([str(w)]) == 0
    data = said(home, w)
    assert data["schema"] == SAID_SCHEMA and data["counts"]["items"] == 3
    first, second, third = data["items"]
    assert first["structured"] and first["commitment"] == "Send the price list" and first["to"] == "Dana"
    assert first["recording_id"] == "rec-a" and first["quote"] == "I'll send the price list Friday"
    assert not second["structured"] and second["time"] == "15:30" and second["recording_id"] == "9f8e7d6c"
    assert third["text"].startswith("Book the warehouse visit") and third["status"] == "open"


def test_the_review_marks_items_by_id_or_ref_and_ids_are_stable(home, tmp_path):
    w = make_window(home, "2030-09-01_to_2030-09-01")
    sns.main([str(w)])
    items = said(home, w)["items"]
    review = tmp_path / "review.json"
    review.write_text(json.dumps({items[0]["id"]: {"status": "seen", "evidence": "sent mail 17:02"},
                                  "2030-09-01#2": {"status": "dropped", "note": "not a commitment"}}))
    sns.main([str(w), "--review", str(review)])
    again = said(home, w)["items"]
    assert [i["status"] for i in again] == ["seen", "dropped"] and again[0]["id"] == items[0]["id"]
    review.write_text(json.dumps({items[0]["id"]: {"status": "perhaps"}}))
    assert sns.main([str(w), "--review", str(review)]) == 2


def test_a_foreign_file_is_not_replaced_and_a_missing_section_exits_1(home, capsys):
    w = make_window(home, "2030-09-01_to_2030-09-01", said=False)
    target = home / "out" / f"said-not-seen-{w.name}.json"
    target.write_text('{"something": "else"}')
    assert sns.main([str(w)]) == 2
    target.unlink()
    (w / "days" / "2030-09-01" / "day.md").write_text("# x\n## Done\n")
    assert sns.main([str(w)]) == 1
    assert "days without the section: 2030-09-01" in capsys.readouterr().out
