"""vault_garden.py on an invented vault: proposals only, private folders unseen."""

import json

import _common as c
import vault_garden as g


def test_loose_notes_get_the_folder_their_links_point_to(vault):
    r = g.garden(c.Vault())
    props = {p["note"]: p["proposed_folder"] for p in r["proposals"]}
    assert props == {"Lakeview supplier call.md": "Suppliers", "Random thought.md": "unfiled"}
    assert r["proposals"][-1]["note"] == "Random thought.md"


def test_thin_map_note_lists_notes_to_fill_from(vault):
    stubs = g.garden(c.Vault())["placeholder_mocs"]
    assert [s["note"] for s in stubs] == ["Maps/Suppliers MOC.md"]
    assert stubs[0]["fill_from"] == ["Suppliers/Northwind Traders.md"]


def test_dead_checkboxes_skip_private_folders(vault):
    dead = g.garden(c.Vault())["dead_checkboxes"]
    assert [(d["note"], d["open_checkboxes"]) for d in dead] == [("Old/Chores.md", 2)]


def test_as_script_prints_safe_moves_only(vault, capsys):
    assert g.main(["--as-script"]) == 0
    out = capsys.readouterr().out
    assert "mv -n 'Lakeview supplier call.md' Suppliers/" in out and "Random thought" not in out


def test_writes_nothing(vault, capsys):
    before = sorted((p, p.stat().st_mtime) for p in vault.rglob("*"))
    g.main(["--format", "json"])
    assert json.loads(capsys.readouterr().out)["notes"] == 7
    assert sorted((p, p.stat().st_mtime) for p in vault.rglob("*")) == before


def test_skip_keeps_a_note_and_a_folder_out(vault):
    r = g.garden(c.Vault(), skip=["Suppliers", "Random thought"])
    assert [(p["note"], p["proposed_folder"]) for p in r["proposals"]] == [("Lakeview supplier call.md", "unfiled")]


def test_private_folder_written_loosely_is_still_private(vault, tmp_path, monkeypatch):
    conf = tmp_path / "settings.toml"
    conf.write_text(f'vault_dir = "{vault}"\nvault_private_dirs = ["./private/"]\n', encoding="utf-8")
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(conf))
    (vault / "Peek.md").symlink_to(vault / "Private" / "Journal.md")
    r = g.garden(c.Vault())
    seen = [p["note"] for p in r["proposals"]] + [d["note"] for d in r["dead_checkboxes"]]
    assert not any("Journal" in s or "Peek" in s for s in seen) and r["notes"] == 7
