"""process_flow_render.py: drawing a map version, and refusing what cannot be drawn."""

from conftest import C, a_map, cl, rnd, run, stage, write_inventories, write_map, write_toml


def test_validate_finds_what_makes_a_map_uncitable():
    m = a_map("T01", "T02")
    ledger = {"T01-C1", "T01-C2", "T01-P1", "T01-P2", "T02-C1", "T02-P1"}
    assert C.validate(m, ledger, "as-is-and-to-be")[0] == []
    sec = m["sections"][0]
    sec["asis"]["nodes"][0]["claims"] = []
    sec["asis"]["nodes"][1]["badge"] = "NEW"
    sec["asis"]["nodes"][2]["systems"] = ["PORTAL"]
    sec["tobe"]["nodes"][0]["answers"] = []
    m["lanes"].append({"id": "WH", "label": "Warehouse"})
    text = " | ".join(C.validate(m, None, "as-is-and-to-be")[0])
    assert "a1 'Key faxed order' cites no claim" in text
    assert "a to-be marker on the as-is map" in text
    assert "proposed system PORTAL on the as-is map" in text
    assert "(the pain it answers) cites no claim" in text
    assert "lane WH is orphaned" in text
    assert any("not in the claim ledger" in e for e in C.validate(a_map("T01", "T02"), {"T01-C1"}, "as-is-and-to-be")[0])
    assert any("lane 'Billing' is not one the rules file allows" in e
               for e in C.validate(a_map("T01", "T02"), None, "as-is-and-to-be", ["Customer", "Order desk"])[0])


def test_render_draws_both_pages_and_never_overwrites(nw, capsys):
    work = stage(nw, capsys)
    desk, bill = write_inventories(work)
    run(cl.main, "build", work, capsys=capsys)
    write_map(work, a_map(desk, bill))
    code, text = run(rnd.main, work, "--no-shot", capsys=capsys)
    assert code == 0, text
    asis = (work / "renders" / "order-to-delivery v1 as-is.html").read_text()
    dual = (work / "renders" / "order-to-delivery v1 as-is and to-be.html").read_text()
    assert "Key faxed order" in asis and C.as_is_leaks(asis) == []
    assert "NORTHWIND TRADERS" in asis and "POD: proof of delivery" in asis
    assert "Review portal order" in dual and "TO-BE" in dual
    narr = (work / "renders" / "order-to-delivery v1 narrative.md").read_text()
    assert "Review portal order" in narr and "Where it breaks today" in narr
    code, text = run(rnd.main, work, "--no-shot", capsys=capsys)
    assert code == 1 and "already rendered" in text


def test_render_refuses_a_map_with_errors(nw, capsys):
    work = stage(nw, capsys)
    write_inventories(work)
    run(cl.main, "build", work, capsys=capsys)
    write_map(work, a_map("T09", "T08"))
    code, text = run(rnd.main, work, "--no-shot", capsys=capsys)
    assert code == 1 and "not in the claim ledger" in text and not (work / "renders").exists()


def test_the_screenshot_runs_the_command_setting(nw, capsys, tmp_path):
    work = stage(nw, capsys)
    desk, bill = write_inventories(work)
    run(cl.main, "build", work, capsys=capsys)
    write_map(work, a_map(desk, bill))
    fake = tmp_path / "shot.py"
    fake.write_text("import sys\nopen(sys.argv[1], 'wb').write(b'x' * 3000)\n")
    write_toml(nw["settings"], f'[process-flow-workstream]\nscreenshot_command = "python3 {fake} {{out}}"\n')
    code, text = run(rnd.main, work, "--format", "json", capsys=capsys)
    assert code == 0, text
    assert '"ok": true' in text and (work / "renders" / "order-to-delivery v1 as-is.png").stat().st_size == 3000


def test_a_folder_that_is_not_staged_is_exit_2(tmp_path, capsys):
    assert run(rnd.main, tmp_path, capsys=capsys)[0] == 2
