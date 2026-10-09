"""process_flow_check.py: the six tests of done, from nothing to done."""

import json

from conftest import C, a_map, cl, rnd, run, run_reviews, stage, write_inventories, write_map
import process_flow_check as chk
import process_flow_publish as pub


def test_the_check_walks_from_nothing_to_done(nw, capsys):
    work = stage(nw, capsys)
    first = chk.check(str(work))
    assert first["done"] is False and "no inventory" in " ".join(first["tests"]["sources"]["gaps"])
    desk, bill = write_inventories(work)
    run(cl.main, "build", work, capsys=capsys)
    r = chk.check(str(work))
    assert r["tests"]["sources"]["met"] and r["tests"]["map"]["gaps"] == ["no map yet"]
    write_map(work, a_map(desk, bill))
    run(rnd.main, work, "--no-shot", capsys=capsys)
    r = chk.check(str(work))
    assert r["tests"]["map"]["met"] and r["tests"]["render"]["met"] and not r["tests"]["factcheck"]["met"]
    run_reviews(work, capsys, grade="C+")
    r = chk.check(str(work))
    assert r["tests"]["factcheck"]["met"] and r["tests"]["completeness"]["met"]
    assert "under the bar B" in r["tests"]["redteam"]["gaps"][0]
    code, text = run(chk.main, work, "--precheck", capsys=capsys)
    assert code == 0 and text.startswith("WORK: 1 of 6 tests open (redteam)")
    write_map(work, a_map(desk, bill, version=2))
    run(rnd.main, work, "--no-shot", capsys=capsys)
    assert chk.check(str(work))["tests"]["factcheck"]["met"] is False      # reviews are per version
    run_reviews(work, capsys, grade="A-")
    assert chk.check(str(work))["done"] is True
    assert run(chk.main, work, "--precheck", capsys=capsys)[1].startswith("NOTHING: map v2")


def test_a_screenshot_is_required_unless_the_rules_say_no(nw, capsys):
    work = stage(nw, capsys)
    desk, bill = write_inventories(work)
    run(cl.main, "build", work, capsys=capsys)
    write_map(work, a_map(desk, bill))
    run(rnd.main, work, "--no-shot", capsys=capsys)
    meta = json.loads((work / C.STAGED_MARKER).read_text())
    meta["rules"]["screenshot"] = "yes"
    (work / C.STAGED_MARKER).write_text(json.dumps(meta))
    assert chk.check(str(work))["tests"]["render"]["gaps"] == ["no screenshot of the as-is render of map v1"]


def test_check_by_context_sees_a_new_transcript(nw, capsys):
    work = stage(nw, capsys)
    write_inventories(work)
    run(cl.main, "build", work, capsys=capsys)
    assert run(pub.main, work, capsys=capsys)[0] == 0
    r = chk.check("northwind-o2d")
    assert r["tests"]["sources"]["met"] and r["process"] == "order-to-delivery"
    (nw["transcripts"] / "driver interview.txt").write_text("[0:01] Driver: I hand the note in on Fridays.\n")
    r = chk.check("northwind-o2d")
    assert "new since the last session" in r["tests"]["sources"]["gaps"][0]
    code, text = run(chk.main, "northwind-o2d", "--process=", "--as-of=", "--precheck", capsys=capsys)
    assert code == 0 and text.startswith("WORK: ")


def test_a_bad_argument_is_exit_2(nw, capsys):
    assert run(chk.main, capsys=capsys)[0] == 2
    assert run(chk.main, "nobody", capsys=capsys)[0] == 2
    assert run(chk.main, "northwind-o2d", "--as-of", "someday", capsys=capsys)[0] == 2


def test_the_done_gate_catches_a_changed_source_a_leak_and_an_unchecked_assertion(nw, capsys):
    work = stage(nw, capsys)
    desk, bill = write_inventories(work)
    run(cl.main, "build", work, capsys=capsys)
    write_map(work, a_map(desk, bill))
    run(rnd.main, work, "--no-shot", capsys=capsys)
    run_reviews(work, capsys, grade="A-")
    assert chk.check(str(work))["done"] is True

    # a source edited after its inventory was built into the ledger
    reg = json.loads((work / C.SOURCES_FILE).read_text())
    next(e for e in reg["sources"] if e["id"] == desk)["sha256"] = "0" * 64
    (work / C.SOURCES_FILE).write_text(json.dumps(reg))
    gaps = chk.check(str(work))["tests"]["sources"]["gaps"]
    assert gaps and "changed after its inventory was built" in gaps[0]

    # to-be content leaked into the as-is page
    asis = work / "renders" / "order-to-delivery v1 as-is.html"
    asis.write_text(asis.read_text() + "<span>NEW</span><b>>TBD<</b>")
    assert "carries to-be content" in chk.check(str(work))["tests"]["render"]["gaps"][0]

    # an assertion one half never gave a verdict on
    fa = work / "reviews" / "factcheck-A v1.json"
    data = json.loads(fa.read_text())
    data["verdicts"] = [v for v in data["verdicts"] if v["key"] != "01/asis/a1"]
    fa.write_text(json.dumps(data))
    fb = work / "reviews" / "factcheck-B v1.json"
    data = json.loads(fb.read_text())
    data["verdicts"] = [v for v in data["verdicts"] if v["key"] != "01/asis/a1"]
    fb.write_text(json.dumps(data))
    r = chk.check(str(work))
    assert "assertion(s) with no verdict: 01/asis/a1" in r["tests"]["factcheck"]["gaps"][0]
    assert r["done"] is False

    # a map file that is not a JSON object fails the map test
    (work / "maps" / "map v2.json").write_text("[1, 2]")
    assert chk.check(str(work))["tests"]["map"]["gaps"] == ["map v2.json is not a JSON object"]
