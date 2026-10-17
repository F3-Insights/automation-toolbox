"""vault_find, vault_read, vault_links, vault_inbox_write and vault_config on an invented vault."""

import io
import json

import pytest

import _common as c
import vault_config
import vault_find
import vault_inbox_write
import vault_links
import vault_read


def run(module, argv, capsys):
    code = module.main(argv)
    return code, capsys.readouterr().out


def test_frontmatter_lists_and_scalars():
    meta, body = c.parse_frontmatter("---\ntags: [a, b]\nkind: note\nitems:\n  - x\n  - y\n---\nbody")
    assert meta == {"tags": ["a", "b"], "kind": "note", "items": ["x", "y"]}
    assert body == "body"


def test_links_strip_heading_alias_and_duplicates():
    assert c.extract_links("[[A]] [[B#h|b]] ![[C]] [[A]]") == ["A", "B", "C"]


def test_private_and_app_folders_are_never_indexed(vault):
    rels = [n["rel"] for n in c.Vault().notes]
    assert "Private/Diary.md" not in rels and not any(r.startswith(".obsidian") for r in rels)


def test_find_ranks_exact_first(vault, capsys):
    code, out = run(vault_find, ["loose note", "--format", "json"], capsys)
    data = json.loads(out)
    assert code == 0 and data["matches"][0]["matched_by"] == "exact title"
    assert data["matches"][0]["frontmatter"]["tags"] == ["ideas", "pricing"]


def test_find_nothing_exits_1(vault, capsys):
    assert run(vault_find, ["zzznope"], capsys)[0] == 1


def test_read_private_note_is_refused(vault):
    with pytest.raises(SystemExit) as exc:
        vault_read.main(["Diary"])
    assert exc.value.code == 1


def test_read_returns_body_and_links(vault, capsys):
    data = json.loads(run(vault_read, ["Loose Note", "--format", "json"], capsys)[1])
    assert data["links"] == ["Target", "Missing Note"] and data["frontmatter"]["status"] == "draft"


def test_links_flags_unresolved_ambiguous_and_backlinks(vault, capsys):
    data = json.loads(run(vault_links, ["Loose Note", "--format", "json"], capsys)[1])
    by_target = {o["target"]: o for o in data["outbound"]}
    assert by_target["Missing Note"]["unresolved"] and by_target["Target"]["ambiguous"]
    assert data["backlinks"] == ["Sub/Target.md"]


def test_inbox_write_never_overwrites(vault, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("first"))
    code, out = run(vault_inbox_write, ["--title", "Talk: pricing?"], capsys)
    path = vault / "Inbox" / "Talk - pricing.md"
    assert code == 0 and out.strip() == str(path) and path.read_text() == "first\n"
    monkeypatch.setattr("sys.stdin", io.StringIO("second"))
    with pytest.raises(SystemExit) as exc:
        vault_inbox_write.main(["--title", "Talk: pricing?"])
    assert exc.value.code == 1 and path.read_text() == "first\n"
    monkeypatch.setattr("sys.stdin", io.StringIO("second"))
    run(vault_inbox_write, ["--title", "Talk: pricing?", "--next-free"], capsys)
    assert (vault / "Inbox" / "Talk - pricing 2.md").read_text() == "second\n"


@pytest.mark.parametrize("inbox", ["../Outside", "Private", "."])
def test_inbox_must_be_inside_vault_and_not_private(vault, inbox, monkeypatch):
    (vault.parent / "Outside").mkdir()
    monkeypatch.setattr("sys.stdin", io.StringIO("text"))
    with pytest.raises(SystemExit) as exc:
        vault_inbox_write.main(["--title", "x", "--inbox", inbox])
    assert exc.value.code == 2


def test_config_reports_ready_vault(vault, capsys):
    code, out = run(vault_config, [], capsys)
    assert code == 0 and json.loads(out)["problems"] == []


def test_config_without_vault_dir_exits_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "none.toml"))
    code, out = run(vault_config, [], capsys)
    assert code == 2 and "vault_dir is not set" in json.loads(out)["problems"]


@pytest.mark.parametrize("written", ["./Private/", "Private\\", "private", "ABSOLUTE"])
def test_private_folder_however_written(vault, tmp_path, monkeypatch, written):
    entry = str(vault / "Private") if written == "ABSOLUTE" else written
    conf = tmp_path / "settings.toml"
    conf.write_text(f'vault_dir = "{vault}"\nvault_inbox = "Inbox"\nvault_private_dirs = [{json.dumps(entry)}]\n', encoding="utf-8")
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(conf))
    assert "Private/Diary.md" not in [n["rel"] for n in c.Vault().notes]


def test_symlinks_into_private_or_outside_are_skipped(vault, tmp_path):
    outside = tmp_path / "Elsewhere"
    outside.mkdir()
    (outside / "Secret.md").write_text("outside the vault\n", encoding="utf-8")
    (vault / "Link to diary.md").symlink_to(vault / "Private" / "Diary.md")
    (vault / "Linked folder").symlink_to(vault / "Private", target_is_directory=True)
    (vault / "Outside.md").symlink_to(outside / "Secret.md")
    rels = [n["rel"] for n in c.Vault().notes]
    assert not any(r.startswith(("Link to diary", "Linked folder", "Outside")) for r in rels)
    assert "Loose Note.md" in rels


@pytest.mark.parametrize("inbox", [".obsidian", ".trash/Inbox"])
def test_inbox_refuses_obsidian_folders(vault, inbox, monkeypatch):
    (vault / inbox).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("sys.stdin", io.StringIO("text"))
    with pytest.raises(SystemExit) as exc:
        vault_inbox_write.main(["--title", "x", "--inbox", inbox])
    assert exc.value.code == 2 and not (vault / inbox / "x.md").exists()
