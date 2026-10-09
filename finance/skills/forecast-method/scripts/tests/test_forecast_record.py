import forecast_bridge
import forecast_check
import forecast_record
from conftest import open_vintage, write_hypotheses


def test_hypotheses_cannot_be_recorded_after_the_bridge(folder, capsys):
    vdir = open_vintage(folder)
    forecast_bridge.main([str(folder), "--vintage", "rev5"])
    write_hypotheses(vdir)
    assert forecast_record.main([str(folder), "--vintage", "rev5", "--test", "hypotheses", "--item", "set",
                                 "--state", "written", "--by", "Sam"]) == 2
    assert "before" in capsys.readouterr().err


def test_a_question_carries_its_fallback(folder, capsys):
    open_vintage(folder)
    assert forecast_record.main([str(folder), "--vintage", "rev5", "--test", "questions", "--item", "Q-001",
                                 "--state", "asked", "--by", "Sam"]) == 2
    assert "fallback" in capsys.readouterr().err


def test_a_state_of_another_test_is_refused(folder, capsys):
    open_vintage(folder)
    assert forecast_record.main([str(folder), "--vintage", "rev5", "--test", "messages", "--item", "2027-07-20",
                                 "--state", "answered", "--by", "Sam"]) == 2
    assert "belongs to the questions test" in capsys.readouterr().err


def test_one_batched_message_a_week(folder):
    open_vintage(folder)
    for item in ("2027-07-20", "2027-07-21"):
        assert forecast_record.main([str(folder), "--vintage", "rev5", "--test", "messages", "--item", item,
                                     "--state", "asked", "--by", "forecast-orchestrator"]) == 0
    test = forecast_check.check(folder)["tests"]["messages"]
    assert not test["met"] and "more than 1" in test["gaps"][0]


def test_upsert_keeps_other_rows_byte_for_byte_and_clears_a_stale_review(folder, capsys):
    vdir = open_vintage(folder)
    ledger = vdir / "FORECAST-EVIDENCE-rev5.csv"
    header = "id,test,item,state,evidence,amount,review,review_file,note,updated_at,by\r\n"
    kept = 'questions:Q-009,questions,Q-009,answered,"reply, with a comma",,,,,2027-07-01T00:00:00+00:00,Priya\r\n'
    reviewed = "delivered:vintage,delivered,vintage,delivered,old.md,,PASS,r.md,,2027-07-01T00:00:00+00:00,Jordan\r\n"
    ledger.write_bytes(("﻿" + header + kept + reviewed).encode("utf-8"))
    assert forecast_record.main([str(folder), "--vintage", "rev5", "--test", "delivered", "--item", "vintage",
                                 "--state", "delivered", "--by", "Jordan", "--evidence", "new.md"]) == 0
    assert "review cleared" in capsys.readouterr().out
    text = ledger.read_bytes().decode("utf-8")
    assert text.startswith("﻿" + header + kept)
    row = forecast_check.ledger_rows(vdir, "rev5")["delivered:vintage"]
    assert row["evidence"] == "new.md" and row["review"] == "" and row["review_file"] == ""
