"""report_organize.py: the week sorted into the profile's categories, and Gate 1 applied."""

import json

from conftest import ledger, run


PRIOR = [{"ref": "portal://note/n0", "title": "Weekly Highlights - Finance - 2027-11-05", "date": "2027-11-05",
          "bullets": [{"label": "Receivables", "text": "One overdue account is pending a decision by 2027-11-09."}]}]


def organize(tmp_path, store, *extra, week=None):
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(week or ledger(prior=PRIOR, goals=[{"id": "g1", "title": "Open a depot", "priority": "P1"}])))
    done = run("report_organize", "--ledger", path, "--outline-file", store / "profile.md",
               "--out", tmp_path / "pack.json", "--digest", tmp_path / "digest.md", *extra)
    assert done.returncode == 0, done.stderr
    return json.loads((tmp_path / "pack.json").read_text()), (tmp_path / "digest.md").read_text()


def refs(pack):
    return {c["name"]: [r["ref"] for r in c["evidence"]] for c in pack["categories"]}


def test_each_item_goes_to_at_most_one_category_and_the_rest_stays_unassigned(tmp_path, store):
    pack, digest = organize(tmp_path, store)
    filed = refs(pack)
    assert "portal://task/t1" in filed["Month-end close"]
    assert filed["Cash and collections"] == ["portal://task/t2"]
    assert filed["Systems and support"] == ["portal://email/e1"]
    assert filed["Other topics"] == [], "nothing is folded into the catch-all by the signals"
    assert {"portal://task/t7", "portal://email/e9"} <= {r["ref"] for r in pack["unassigned"]["items"]}
    assert all(m["status"] == "MISSING" for c in pack["categories"] for m in c["standing_metrics"])
    assert pack["outline"]["errors"] == []
    assert "### Cash and collections" in digest and "MISSING, expected from facts:cash_on_hand" in digest


def test_an_earlier_problem_comes_back_as_a_carry_over_and_the_ledger_adds_its_own(tmp_path, store):
    candidates = tmp_path / "candidates.json"
    candidates.write_text(json.dumps({"candidates": [
        {"id": "led-1", "topic": "Scanner renewal", "text": "Price due.", "category": "No such category",
         "kind": "dated_expectation", "reason": "the date it named has passed"}]}))
    pack, digest = organize(tmp_path, store, "--ledger-candidates", candidates)
    cash = next(c for c in pack["categories"] if c["name"] == "Cash and collections")
    assert [x["label"] for x in cash["carry_overs"]] == ["Receivables"]
    assert "the date it named, 2027-11-09, has passed" in cash["carry_overs"][0]["reason"]
    catch_all = pack["categories"][-1]
    assert catch_all["carry_overs"][0]["ref"] == "ledger://led-1", "an unplaced candidate goes to the catch-all"
    assert "CARRY-OVER **Receivables**" in digest
    assert pack["silent"]["goals"][0]["title"] == "Open a depot"


def test_gate_one_adds_drops_pulls_back_and_moves_for_this_week_only(tmp_path, store):
    gate1 = tmp_path / "gate1.json"
    gate1.write_text(json.dumps({
        "schema": "gate1-answers/1",
        "categories": {"add": [{"name": "Scanner contract", "seat": "Technology", "kind": "project",
                                "signals": {"keywords": ["scanner"]}}],
                       "drop": ["Systems and support"]},
        "items": {"pull_back": ["portal://email/e9"],
                  "move": [{"ref": "portal://task/t8", "category": "Cash and collections"}]}}))
    pack, digest = organize(tmp_path, store, "--gate1", gate1)
    filed = refs(pack)
    assert list(filed) == ["Month-end close", "Cash and collections", "Scanner contract", "Other topics"]
    assert filed["Scanner contract"] == ["portal://task/t7"]
    assert "portal://email/e9" in filed["Other topics"]
    assert "portal://task/t8" in filed["Cash and collections"] and "portal://task/t8" not in filed["Month-end close"]
    moved = next(r for r in pack["categories"][1]["evidence"] if r["ref"] == "portal://task/t8")
    assert moved["moved_from"] == "Month-end close"
    section = digest[digest.index("### Cash and collections"):digest.index("### Scanner contract")]
    assert "portal://task/t8" in section
    assert pack["gate1"]["unmatched"] == []


def test_a_facts_set_fills_the_standing_metrics(tmp_path, store):
    facts = tmp_path / "facts.json"
    facts.write_text(json.dumps({"schema": "report-facts/1", "period": "2027-11-12", "tables": {}, "figures": {
        "cash_on_hand": {"value": 1840000.0, "as_of": "2027-11-12", "source": "the bank portal", "unit": "usd",
                         "status": "final"}}}))
    pack, digest = organize(tmp_path, store, "--facts", facts)
    assert pack["facts"]["read_as"] == "facts-set"
    cash = next(m for c in pack["categories"] for m in c["standing_metrics"] if m["name"] == "Cash on hand")
    assert cash["status"] == "present" and cash["value"] == 1840000.0
    assert "[facts://cash_on_hand]" in digest


def test_an_unforeseen_bad_value_exits_2_with_one_line_not_a_traceback(tmp_path, store):
    week = ledger()
    week["items"] = [dict(week["items"][0], weight="high")] + week["items"][1:]
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(week))
    done = run("report_organize", "--ledger", path, "--outline-file", store / "profile.md", "--out", tmp_path / "pack.json")
    assert done.returncode == 2
    assert done.stderr.startswith("ERROR ") and "Traceback" not in done.stderr


def test_the_digest_says_when_the_sweep_ran(tmp_path, store, ledger_file):
    done = run("report_organize", "--ledger", ledger_file, "--outline-file", store / "profile.md",
               "--out", tmp_path / "pack.json", "--digest", tmp_path / "digest.md")
    assert done.returncode == 0, done.stderr
    assert json.loads((tmp_path / "pack.json").read_text())["provenance"]["collected_at"] == "2027-11-12T17:00:00Z"
    digest = (tmp_path / "digest.md").read_text()
    assert "The sweep ran at 2027-11-12T17:00:00Z" in digest and "Cadence: Weekly, Friday" in digest
