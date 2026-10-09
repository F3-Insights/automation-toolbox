"""process_flow_publish.py: filing the session's work back without overwriting anything."""

import json
import shutil

from conftest import drafted, ids, run, stage, write_toml
import process_flow_publish as pub


def test_publish_files_new_work_and_never_overwrites(nw, capsys):
    work = drafted(nw, capsys)
    (work / "STATUS.md").write_text("v1 drafted\n")
    pdir = nw["working"] / "process-flows" / "order-to-delivery"
    code, _ = run(pub.main, work, "--dry-run-if", "true", capsys=capsys)
    assert code == 0 and not pdir.exists() and not any(nw["delivery"].iterdir())
    assert (work / "publish-dry-run.json").is_file()
    code, text = run(pub.main, work, capsys=capsys)
    assert code == 0, text
    assert (pdir / "maps" / "map v1.json").is_file() and (pdir / "CLAIM-LEDGER.csv").is_file()
    assert not (pdir / "engagement.json").exists() and not (pdir / "returns").exists()
    delivered = {p.name for p in nw["delivery"].iterdir()}
    assert "order-to-delivery v1 as-is.html" in delivered and "order-to-delivery VERIFICATION v1.md" in delivered

    # the next session: a person edits STATUS.md meanwhile, the session edits a written-once map
    work2 = stage(nw, capsys, "run2")
    assert ids(work2)["order desk interview.txt"]["id"] == ids(work)["order desk interview.txt"]["id"]
    (pdir / "STATUS.md").write_text("the owner's note\n")
    (work2 / "STATUS.md").write_text("v1 reviewed\n")
    (work2 / "maps" / "map v1.json").write_text("{}")
    (work2 / "LOG.md").write_text("session 2\n")
    code, text = run(pub.main, work2, capsys=capsys)
    assert code == 1 and "HELD maps/map v1.json" in text
    assert (pdir / "STATUS.md").read_text() == "the owner's note\n"
    assert (pdir / "STATUS (2).md").read_text() == "v1 reviewed\n"
    assert json.loads((pdir / "maps" / "map v1.json").read_text())["version"] == 1
    assert (pdir / "LOG.md").read_text() == "session 2\n"
    # a delivered draft changed by hand is never overwritten
    (nw["delivery"] / "order-to-delivery v1 narrative.md").write_text("edited by the owner")
    shutil.rmtree(nw["root"] / "run2")
    run(pub.main, stage(nw, capsys, "run3"), capsys=capsys)
    assert (nw["delivery"] / "order-to-delivery v1 narrative.md").read_text() == "edited by the owner"
    assert (nw["delivery"] / "order-to-delivery v1 narrative (2).md").is_file()


def test_a_lost_delivery_anchor_holds_the_drafts(nw, capsys):
    firm = nw["root"] / "firm"
    firm.mkdir()
    sources = [{"name": "engagement", "kind": "folder", "path": str(nw["working"])},
               {"name": "transcripts", "kind": "folder", "path": str(nw["transcripts"])}]
    (nw["ctx"] / "northwind-o2d.yaml").write_text(json.dumps({"name": "northwind-o2d", "sources": sources}))
    write_toml(nw["settings"], f'contexts_dir = "{nw["ctx"]}"\n[process-flow-workstream]\ndelivery_dir = "{firm}"\n'
               f'reference_models_dir = "{nw["models"]}"\n')
    work = drafted(nw, capsys)
    firm.rmdir()
    code, text = run(pub.main, work, capsys=capsys)
    assert code == 1 and "HELD map v1 drafts" in text and not firm.exists()


def test_a_folder_that_is_not_staged_is_exit_2(tmp_path, capsys):
    assert run(pub.main, tmp_path, capsys=capsys)[0] == 2
