"""playbook_index.py over an invented playbook folder."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import playbook_index as pi  # noqa: E402


@pytest.fixture(autouse=True)
def empty_settings(tmp_path, monkeypatch):
    path = tmp_path / "settings.toml"
    path.write_text("")
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(path))
    return path


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def folder(tmp_path):
    root = tmp_path / "playbooks"
    write(root / "finance" / "playbooks" / "spend-approvals.md",
          "---\nname: spend-approvals\ntriggers: [invoice, early payment]\nprofiles: [finance]\n"
          "policy-refs: [spend-limits]\n---\nbody\n")
    write(root / "finance" / "drafts" / "vendor-onboarding-playbook-draft.md", "no frontmatter here\n")
    write(root / "sales" / "briefs" / "northwind.md",
          "---\nname: northwind-calibration\nprofile: sales\ncalibration: per-client\n---\n")
    write(root / "policies" / "spend-limits.md", "---\nname: spend-limits\ntriggers: [spend]\n---\n")
    write(root / "_inbox" / "2030-01-01-proposal.md", "---\nname: ignored\n---\n")
    write(root / "finance" / "playbooks" / "README.md", "prose\n")
    return root


def test_index_orders_sections_and_skips_pipeline(folder, capsys):
    assert pi.main([str(folder)]) == 0
    text = (folder / "INDEX.md").read_text()
    order = [text.index(h) for h in ("## Ratified playbooks", "## Policies", "## Drafts", "## Briefs")]
    assert order == sorted(order)
    assert "- **spend-approvals** [finance]: invoice, early payment (refs: spend-limits)" in text
    assert "vendor-onboarding-playbook-draft (no frontmatter)" in text
    assert "load client calibration" in text
    assert "ignored" not in text and "prose" not in text
    assert "(4 entries)" in capsys.readouterr().out


def test_labels_order_functions_and_footer_is_appended(folder, empty_settings):
    empty_settings.write_text('playbooks_dir = "%s"\n[playbook-ratification.function_labels]\n'
                              'sales = "Sales: pursuits and pricing"\n' % folder)
    write(folder / "sales" / "playbooks" / "discounts.md", "---\nname: discounts\n---\n")
    write(folder / "meta" / "INDEX-FOOTER.md", "## Elsewhere\n\n- Engineering standards live in their own repository.\n")
    assert pi.main([]) == 0
    text = (folder / "INDEX.md").read_text()
    ratified = text.split("## Policies")[0]
    assert ratified.index("### Sales: pursuits and pricing") < ratified.index("### finance")
    assert text.rstrip().endswith("own repository.")


def test_refuses_a_folder_that_is_not_a_playbook_folder(tmp_path, capsys):
    other = tmp_path / "project"
    write(other / "INDEX.md", "a hand-written index\n")
    assert pi.main([str(other)]) == 1
    assert (other / "INDEX.md").read_text() == "a hand-written index\n"
    assert "refusing" in capsys.readouterr().err


def test_missing_folder(tmp_path, capsys):
    assert pi.main([str(tmp_path / "nope")]) == 1
    assert pi.main([]) == 2
