"""curate_scan on an invented vault: the lists, and nothing private or outside the scope."""

import json

import pytest

import curate_scan

NOTES = {
    "Work/Areas/Pricing.md": "---\ntype: reference\n---\n# Pricing\n\n## Rates\n\nDay rate is set yearly.\n\n## History\n\nStatus as of 2020-01: under review.\n",
    "Work/Areas/Rates.md": "See [[Pricing]] and [[Missing page]].\n",
    "Work/Areas/Pricing notes.md": "Links [[Rates]].\n",
    "Work/Other/Elsewhere.md": "[[Pricing]] [[Rates]] [[Pricing notes]]\n",
    "Work/Areas/Price list.md": "One.\n",
    "Work/Other/Price lists.md": "Two.\n",
    "Work/Bad.md": "---\ntitle: x\nno colon here\n---\nbody\n",
    "Inbox/Clip.md": "---\ntype: clip\n---\nA new point about [[Pricing]].\n",
    "Private/Diary.md": "Never read. [[Pricing]]\n",
    "Loose.md": "Outside the scope. [[Pricing]]\n",
}


@pytest.fixture
def vault(tmp_path, monkeypatch):
    root = tmp_path / "Vault"
    for rel, text in NOTES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    conf = tmp_path / "settings.toml"
    conf.write_text(f'vault_dir = "{root}"\nvault_inbox = "Inbox"\nvault_private_dirs = ["Private"]\n'
                    f'vault_curate_dirs = ["Work"]\nstate_dir = "{tmp_path / "state"}"\n'
                    f'vault_curate_max_changes = 3\n', encoding="utf-8")
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(conf))
    return root


def test_scan_lists_and_keeps_private_and_outside_out(vault, capsys):
    out = curate_scan.scan(curate_scan.Vault(), ["Work"], "Inbox")
    assert {b["target"] for b in out["broken_links"]} == {"Missing page"}
    assert any(set(d["notes"]) == {"Work/Areas/Price list.md", "Work/Other/Price lists.md"} for d in out["duplicate_titles"])
    assert {"note": "Work/Other/Elsewhere.md"} in out["orphans"]
    assert {f["note"] for f in out["frontmatter"]} >= {"Work/Bad.md", "Work/Areas/Rates.md"}
    assert out["dated_lines"][0]["note"] == "Work/Areas/Pricing.md"
    assert [n["rel"] for n in out["inbox_notes"]] == ["Inbox/Clip.md"]
    assert out["inbox_notes"][0]["candidates"][0]["rel"].startswith("Work/")
    text = json.dumps(out)
    assert "Diary" not in text and "Loose.md" not in text
