"""claim_ledger.py: building the ledger, adding claims and recording reviews."""

import json

from conftest import a_map, cl, fact_return, ids, rnd, run, run_reviews, stage, write_inventories, write_map, inventory


def test_build_makes_the_ledger_and_checks_quotes(nw, capsys):
    work = stage(nw, capsys)
    desk, bill = write_inventories(work)
    code, text = run(cl.main, "build", work, "--format", "json", capsys=capsys)
    assert code == 0, text
    out = json.loads(text)
    assert out["rows"] == 6 and out["quote_found"]["yes"] == 6
    rows = {r["id"]: r for r in cl.C.read_ledger(work)}
    assert rows[f"{desk}-C1"]["quote"].startswith("Orders arrive") and rows[f"{desk}-P2"]["kind"] == "pain"
    entry = ids(work)["order desk interview.txt"]
    assert entry["ledgered_sha"] == entry["sha256"]


def test_a_misquote_is_flagged_and_a_broken_inventory_is_refused(nw, capsys):
    work = stage(nw, capsys)
    desk, bill = write_inventories(work)
    (work / "inventories" / f"{bill}.md").write_text(inventory(bill, [("x", "We never send any bills at all", "0:02")]))
    assert run(cl.main, "build", work, capsys=capsys)[0] == 0
    assert {r["id"]: r for r in cl.C.read_ledger(work)}[f"{bill}-C1"]["quote_found"] == "no"
    (work / "inventories" / f"{bill}.md").write_text("no block here")
    code, text = run(cl.main, "build", work, capsys=capsys)
    assert code == 1 and "no fenced json block" in text


def test_add_takes_a_background_claim_only_with_its_verbatim_quote(nw, capsys):
    work = stage(nw, capsys)
    write_inventories(work)
    memo = ids(work)["company memo.md"]["id"]
    code, text = run(cl.main, "add", work, "--source", memo, "--text", "Terms are net 15", "--quote",
                     "paid in cash at the door", "--location", "line 3", capsys=capsys)
    assert code == 1 and "not in source" in text
    code, text = run(cl.main, "add", work, "--source", memo, "--text", "Terms are net 15", "--quote",
                     "to restaurants on net 15 terms", "--location", "line 3", "--format", "json", capsys=capsys)
    assert code == 0, text
    assert json.loads(text)["id"] == f"{memo}-C101"
    assert run(cl.main, "build", work, capsys=capsys)[0] == 0
    assert f"{memo}-C101" in {r["id"] for r in cl.C.read_ledger(work)}


def test_record_refuses_incomplete_or_cross_half_verdicts(nw, capsys):
    work = stage(nw, capsys)
    desk, bill = write_inventories(work)
    run(cl.main, "build", work, capsys=capsys)
    write_map(work, a_map(desk, bill))
    run(rnd.main, work, "--no-shot", capsys=capsys)
    assert run(cl.main, "brief", work, capsys=capsys)[0] == 0
    p = fact_return(work, "A")
    data = cl.last_json_block(p.read_text())
    data["verdicts"] = data["verdicts"][1:]
    other = [s["id"] for s in cl.halves(work)["B"]][0]
    data["verdicts"][0].update({"verdict": "VERIFIED", "source": other, "quote": "x"})
    p.write_text("```json\n" + json.dumps(data) + "\n```")
    code, text = run(cl.main, "record", work, "--kind", "factcheck-A", "--from", p, capsys=capsys)
    assert code == 1 and "no verdict for 1 assertion" in text and "must name a source of half A" in text
    assert not (work / "reviews" / "factcheck-A v1.json").exists()


def test_memo_lists_open_questions_and_omissions(nw, capsys):
    work = stage(nw, capsys)
    desk, bill = write_inventories(work)
    run(cl.main, "build", work, capsys=capsys)
    write_map(work, a_map(desk, bill))
    run(rnd.main, work, "--no-shot", capsys=capsys)
    memo = run_reviews(work, capsys)
    assert memo["completeness_listed"] == 1 and memo["verdicts"]["VERIFIED"] >= 1
    text = (work / "VERIFICATION v1.md").read_text()
    assert "## 5. Open questions" in text and "How are credit limits checked?" in text and "Terms are net 15" in text
    code, text = run(cl.main, "memo", work, capsys=capsys)
    assert code == 1 and "written once" in text


def test_a_folder_that_is_not_staged_is_exit_2(tmp_path, capsys):
    assert run(cl.main, "build", tmp_path, capsys=capsys)[0] == 2
