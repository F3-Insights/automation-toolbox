import json
import time

import forecast_bridge
import forecast_check
import forecast_record
import forecast_score
import forecast_sense_check
from conftest import amounts, open_vintage, write_book, write_hypotheses

SUMMARY = """# Northwind forecast rev5

FY2027 pre-bonus EBITDA moves from $288.0k to $316.0k, up $28.0k.

## Top drivers
- $40.0k: wholesale volume from the new retail chain, August on.
- $(12.0)k: consulting for the system migration in Q4.
- $0.0k: staff unchanged.

## What would change it
- The retail chain's first orders slip a quarter.
- The migration finishes early.

## Anticipated questions
1. Is the retail chain signed? Yes, in July.
2. Is the consulting one-off? Yes, Q4 only.
3. Why no cost of goods with the volume? The chain buys on consignment.
"""


def ok(main, *args):
    assert main([str(a) for a in args]) == 0


def test_a_vintage_is_done_only_when_every_test_holds(folder):
    vdir = open_vintage(folder)
    first = forecast_check.check(folder)
    assert first["vintage"] == "rev5" and not first["done"] and first["tests"]["extracts"]["met"]

    write_hypotheses(vdir)
    ok(forecast_record.main, folder, "--vintage", "rev5", "--test", "hypotheses", "--item", "set", "--state", "written",
       "--by", "forecast-drivers-analyst")
    time.sleep(1.1)   # the bridge must be built after the hypotheses were recorded
    for main in (forecast_bridge.main, forecast_sense_check.main, forecast_score.main):
        ok(main, folder, "--vintage", "rev5")
    (vdir / "reasons.json").write_text(json.dumps({"lines": {
        "2027:revenue": {"driver": "New retail chain from August", "kind": "business", "evidence": ["E-002"],
                         "detail": [{"text": "Chain volume", "amount": 40000.0}]},
        "2027:outside": {"driver": "System migration in Q4", "kind": "business", "evidence": ["E-003"]}}}))
    for main in (forecast_bridge.main, forecast_sense_check.main, forecast_score.main):
        ok(main, folder, "--vintage", "rev5")
    flags = json.loads((vdir / "flags.json").read_text())
    (vdir / "flags-resolved.json").write_text(json.dumps(
        {f["id"]: {"resolution": "explained", "text": "Planned step change", "evidence": ["E-002"]}
         for f in flags["flags"] if f["severity"] == "material"}))
    (vdir / "summary.md").write_text(SUMMARY)
    ok(forecast_record.main, folder, "--vintage", "rev5", "--test", "questions", "--item", "Q-001", "--state", "asked",
       "--by", "forecast-orchestrator", "--note", "If unanswered, assume the chain starts in August.")
    assert not forecast_check.check(folder)["tests"]["questions"]["met"]
    ok(forecast_record.main, folder, "--vintage", "rev5", "--test", "questions", "--item", "Q-001", "--state", "answered",
       "--by", "Sales director", "--evidence", "reply 2027-07-20")
    ok(forecast_record.main, folder, "--vintage", "rev5", "--test", "review", "--item", "vintage", "--state", "reviewed",
       "--review", "PASS", "--by", "forecast-reviewer", "--review-file", "reviews/review rev5.md")
    done = forecast_check.check(folder)
    assert done["done"], {k: v["gaps"] for k, v in done["tests"].items() if not v["met"]}
    assert forecast_check.precheck(folder).startswith("NOTHING: vintage rev5 is done")

    (vdir / "summary.md").write_text(SUMMARY + "\nOne more line.\n")
    after = forecast_check.check(folder)["tests"]["review"]
    assert not after["met"] and any("changed after the review" in g for g in after["gaps"])


def test_editing_hypotheses_after_recording_them_is_caught(folder):
    vdir = open_vintage(folder)
    write_hypotheses(vdir)
    ok(forecast_record.main, folder, "--vintage", "rev5", "--test", "hypotheses", "--item", "set", "--state", "written",
       "--by", "Dana")
    write_hypotheses(vdir, revenue=40000.0)
    assert any("never edited" in g for g in forecast_check.check(folder)["tests"]["hypotheses"]["gaps"])


def test_summary_figures_must_come_from_the_bridge_and_skip_the_machinery(folder):
    vdir = open_vintage(folder)
    ok(forecast_bridge.main, folder, "--vintage", "rev5")
    (vdir / "summary.md").write_text(SUMMARY.replace("$28.0k", "$31.0k") + "\nThe agent ran the pipeline.\n")
    gaps = forecast_check.check(folder)["tests"]["summary"]["gaps"]
    assert any("$31.0k" in g for g in gaps)
    assert any("'agent'" in g for g in gaps) and any("'pipeline'" in g for g in gaps)


def test_reasons_need_citations_that_exist_and_details_that_sum(folder):
    vdir = open_vintage(folder)
    ok(forecast_bridge.main, folder, "--vintage", "rev5")
    (vdir / "reasons.json").write_text(json.dumps({"lines": {
        "2027:revenue": {"driver": "Retail chain", "kind": "business", "evidence": ["E-077"],
                         "detail": [{"text": "part", "amount": 35000.0}]}}}))
    gaps = forecast_check.check(folder)["tests"]["reasons"]["gaps"]
    assert any("E-077" in g for g in gaps)
    assert any("detail sums to 35,000.00" in g for g in gaps)
    assert any("2027:outside" in g and "no reason" in g for g in gaps)


def test_precheck_sees_a_new_revision_and_a_changed_workbook(folder):
    assert forecast_check.precheck(folder).startswith("WORK: Northwind forecast rev5.xlsx has been issued")
    vdir = open_vintage(folder)
    (vdir / "LOG.md").write_text("## session\n")
    assert forecast_check.precheck(folder).startswith("NOTHING: vintage rev5 is open")
    write_book(folder / "delivery" / "Northwind forecast rev5.xlsx", amounts(5), changes=[["x", "changed", "y"]])
    assert forecast_check.precheck(folder).startswith("WORK: a workbook of vintage rev5 changed")
    write_book(folder / "delivery" / "Northwind forecast rev6.xlsx", amounts(5))
    assert forecast_check.precheck(folder).startswith("WORK: Northwind forecast rev6.xlsx has been issued")


def test_exit_codes_and_json(folder, capsys):
    assert forecast_check.main([]) == 2
    assert forecast_check.main([str(folder / "missing")]) == 2
    assert forecast_check.main([str(folder), "--precheck"]) == 0
    assert capsys.readouterr().out.startswith("WORK:")
    open_vintage(folder)
    assert forecast_check.main([str(folder), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["vintage"] == "rev5"
