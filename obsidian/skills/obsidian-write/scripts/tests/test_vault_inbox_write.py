"""vault_inbox_write on an invented vault: never overwrites, only into the inbox."""

import io

import pytest

import vault_inbox_write


def run(module, argv, capsys):
    code = module.main(argv)
    return code, capsys.readouterr().out


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

@pytest.mark.parametrize("inbox", [".obsidian", ".trash/Inbox"])
def test_inbox_refuses_obsidian_folders(vault, inbox, monkeypatch):
    (vault / inbox).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("sys.stdin", io.StringIO("text"))
    with pytest.raises(SystemExit) as exc:
        vault_inbox_write.main(["--title", "x", "--inbox", inbox])
    assert exc.value.code == 2 and not (vault / inbox / "x.md").exists()
