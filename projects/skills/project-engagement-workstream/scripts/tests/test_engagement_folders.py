import json

import engagement_folders as ef


def run(tmp_path, *args, capsys=None):
    return ef.main(["Acme Components", "--root", str(tmp_path), "--month", "2026-10", *args])


def test_dry_run_lists_the_plan_and_creates_nothing(tmp_path, capsys):
    assert run(tmp_path, "--workstream", "Proposal Workflow", "--dry-run", "--format", "json") == 0
    out = json.loads(capsys.readouterr().out)
    assert any(p.endswith("Acme Components - 2026-10 Proposal Workflow/Shared with Client") for p in out["planned"])
    assert len(out["planned"]) == 2 + 6
    assert not any(tmp_path.iterdir())


def test_creates_general_and_workstream_folders_and_is_idempotent(tmp_path, capsys):
    assert run(tmp_path, "--workstream", "Utilization") == 0
    ws = tmp_path / "Acme Components - 2026-10 Utilization"
    assert (ws / "From Client").is_dir() and (ws / "Consultant Transcripts").is_dir()
    assert (tmp_path / "Acme Components - General" / "Transcript").is_dir()
    capsys.readouterr()
    assert run(tmp_path, "--workstream", "Utilization", "--format", "json") == 0
    out = json.loads(capsys.readouterr().out)
    assert out["created"] == [] and len(out["already_existed"]) == 8


def test_repo_runbook_written_once(tmp_path, capsys):
    repos = tmp_path / "repos"
    root = tmp_path / "share"
    root.mkdir()
    args = ["Acme Components", "--root", str(root), "--workstream", "Close", "--repo-root", str(repos),
            "--repo-prefix", "lab"]
    assert ef.main(args) == 0
    runbook = repos / "lab-acme-components" / "docs" / "RUNBOOK.md"
    assert "- [ ] 8." in runbook.read_text() and (repos / "lab-acme-components" / "mock").is_dir()
    runbook.write_text("edited")
    assert ef.main(args) == 0
    assert runbook.read_text() == "edited"


def test_settings_supply_root_and_folder_names(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "settings.toml"
    root = tmp_path / "eng"
    root.mkdir()
    cfg.write_text(f'engagements_dir = "{root}"\n[project-engagement-workstream]\n'
                   'workstream_subfolders = ["Inbound", "Outbound"]\n')
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(cfg))
    assert ef.main(["Northwind Traders", "--workstream", "Audit", "--month", "2026-11"]) == 0
    assert sorted(p.name for p in (root / "Northwind Traders - 2026-11 Audit").iterdir()) == ["Inbound", "Outbound"]


def test_bad_month_missing_root_and_no_setting_exit_2(tmp_path, monkeypatch):
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "none.toml"))
    assert ef.main(["Acme", "--root", str(tmp_path), "--month", "2026-1"]) == 2
    assert ef.main(["Acme", "--root", str(tmp_path / "missing")]) == 2
    assert ef.main(["Acme"]) == 2


def test_a_name_that_would_leave_the_root_is_refused(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "none.toml"))
    for args in (["../Acme Components"], ["Acme/Components"], ["Acme", "--workstream", ".."],
                 ["Acme", "--workstream", "Close/../../x"]):
        assert ef.main([*args, "--root", str(root), "--month", "2026-10"]) == 2
    assert not any(tmp_path.glob("Acme*")) and not any(root.iterdir())
    cfg = tmp_path / "settings.toml"
    cfg.write_text('[project-engagement-workstream]\nworkstream_subfolders = ["../outside"]\n')
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(cfg))
    assert ef.main(["Acme", "--root", str(root), "--workstream", "Close"]) == 2
    cfg.write_text('[project-engagement-workstream]\nworkstream_subfolders = "Inbound"\n')
    assert ef.main(["Acme", "--root", str(root), "--workstream", "Close"]) == 2
    assert not any(root.iterdir())
