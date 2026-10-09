"""process_flow_prepare.py: staging an engagement process into a Run folder."""

import json

from conftest import C, ids, prep, run, stage, write_toml


def test_prepare_stages_sources_with_ids_halves_and_duplicates(nw, capsys):
    work = stage(nw, capsys)
    s = ids(work)
    assert "~$lock interview.txt" not in s                       # an Office lock file is never read
    assert s["order desk interview.txt"]["kind"] == "transcript"
    assert s["company memo.md"]["kind"] == "background" and s["company memo.md"]["id"].startswith("B")
    srt, txt = s["billing.srt"], s["billing interview.txt"]
    assert srt.get("duplicate_of") == txt["id"] and not txt.get("duplicate_of")   # the clean text is kept
    usable = [e for e in s.values() if not e.get("duplicate_of")]
    assert {e["half"] for e in usable} == {"A", "B"}
    assert not any(e.get("half") for e in s.values() if e.get("duplicate_of"))
    assert (work / C.RULES_FILE).is_file() and (work / "REFERENCE-MODEL.md").is_file()
    meta = json.loads((work / C.STAGED_MARKER).read_text())
    assert meta["process"] == "order-to-delivery" and meta["scope"] == "as-is-and-to-be"
    assert meta["delivery"] == str(nw["delivery"]) and meta["delivery_basis"] == "the Context's delivery Source"
    assert (work / s["order desk interview.txt"]["staged"]).read_text().startswith("[0:01] Interviewer")
    assert (work / srt["staged"]).read_text().startswith("00:01 Interviewer: When do you bill?")


def test_prepare_refuses_a_non_empty_out_an_unknown_context_and_no_process(nw, capsys):
    work = stage(nw, capsys)
    code, text = run(prep.main, "northwind-o2d", "--out", work, capsys=capsys)
    assert code == 2 and "not empty" in text
    assert run(prep.main, "nobody", "--out", nw["root"] / "x", capsys=capsys)[0] == 2
    (nw["working"] / C.RULES_FILE).write_text("# rules\n\n- Scope: as-is\n")
    code, text = run(prep.main, "northwind-o2d", "--out", nw["root"] / "y", capsys=capsys)
    assert code == 2 and "Default process" in text


def test_a_context_name_needs_the_contexts_dir_setting(nw, capsys):
    write_toml(nw["settings"], "")
    code, text = run(prep.main, "northwind-o2d", "--out", nw["root"] / "x", capsys=capsys)
    assert code == 2 and "contexts_dir" in text
    code, text = run(prep.main, nw["ctx"] / "northwind-o2d.yaml", "--out", nw["root"] / "x", capsys=capsys)
    assert code == 0, text


def recontext(nw, clients=()):
    sources = [{"name": "engagement", "kind": "folder", "path": str(nw["working"])},
               {"name": "transcripts", "kind": "folder", "path": str(nw["transcripts"])}]
    sources += [{"name": f"engagement-{n}", "kind": "folder", "path": str(p)} for n, p in clients]
    (nw["ctx"] / "northwind-o2d.yaml").write_text(json.dumps({"name": "northwind-o2d", "sources": sources}))


def settings(nw, **own):
    lines = "".join(f'{k} = "{v}"\n' for k, v in own.items())
    write_toml(nw["settings"], f'contexts_dir = "{nw["ctx"]}"\n\n[process-flow-workstream]\n{lines}')


def test_a_client_folder_gets_the_drafts_under_the_subfolder_setting(nw, capsys):
    client = nw["root"] / "Northwind Client"
    client.mkdir()
    recontext(nw, clients=[("old", nw["root"] / "gone"), ("client", client)])
    settings(nw, client_subfolder="Our Work/Process Flows", delivery_dir=str(nw["root"]))
    code, text = run(prep.main, "northwind-o2d", "--out", nw["root"] / "w", capsys=capsys)
    assert code == 0, text
    assert f"drafts deliver to {client / 'Our Work' / 'Process Flows' / 'order-to-delivery'} (the client's folder)" in text


def test_a_missing_client_folder_or_delivery_dir_is_never_guessed(nw, capsys):
    recontext(nw, clients=[("client", nw["root"] / "No Such Client")])
    code, text = run(prep.main, "northwind-o2d", "--out", nw["root"] / "w", capsys=capsys)
    assert code == 2 and "none exists" in text and not (nw["root"] / "w").exists()
    recontext(nw)
    settings(nw, delivery_dir=str(nw["root"] / "missing"))
    code, text = run(prep.main, "northwind-o2d", "--out", nw["root"] / "w", capsys=capsys)
    assert code == 2 and "does not exist" in text


def test_no_client_goes_to_the_owner_folder_and_nothing_set_goes_nowhere(nw, capsys):
    firm = nw["root"] / "Firm"
    firm.mkdir()
    recontext(nw)
    settings(nw, delivery_dir=str(firm))
    work = stage(nw, capsys)
    meta = json.loads((work / C.STAGED_MARKER).read_text())
    assert meta["delivery"] == str(firm / "northwind-o2d" / "order-to-delivery")
    assert meta["delivery_anchor"] == str(firm) and "Northwind Traders" in meta["delivery_basis"]
    settings(nw)
    meta = json.loads((stage(nw, capsys, "run2") / C.STAGED_MARKER).read_text())
    assert meta["delivery"] is None and meta["delivery_basis"].startswith("none")
