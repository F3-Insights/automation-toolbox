"""curate_apply on an invented vault: scope, hashes, backups, undo, the cap, the change log."""

import hashlib
import json

import pytest

import curate_apply

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


def h(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_apply(tmp_path, changes, *extra):
    run = tmp_path / "run-1"
    run.mkdir(exist_ok=True)
    (run / "proposals.json").write_text(json.dumps({"tool": "obsidian-curate", "version": 1, "mode": "curate",
                                                    "changes": changes}), encoding="utf-8")
    assert curate_apply.main(["--run", str(run), *extra]) == 0
    name = "apply-dry-run.json" if "--dry-run" in extra else "apply.json"
    return {r["id"]: r for r in json.loads((run / name).read_text())["results"]}


def splice(vault, id_="c1", **kw):
    target = "Work/Areas/Pricing.md"
    return {"id": id_, "op": "splice", "target": target, "hash": h(vault / target), "heading": "## Rates",
            "text": "Added line.", "check": "PASS", "reason": "from the clip", **kw}


def test_splice_adds_under_the_heading_and_backs_up(vault, tmp_path):
    before = (vault / "Work/Areas/Pricing.md").read_text()
    r = run_apply(tmp_path, [splice(vault)])["c1"]
    assert r["status"] == "applied"
    after = (vault / "Work/Areas/Pricing.md").read_text()
    assert "Day rate is set yearly.\n\nAdded line.\n\n## History" in after
    backup = tmp_path / "state/obsidian-curate/run-1/backup/c1/Pricing.md"
    assert backup.read_text() == before
    assert "applied splice [[Work/Areas/Pricing]]" in (vault / "Inbox/Curator log.md").read_text()


def test_changed_target_is_refused(vault, tmp_path):
    ch = splice(vault)
    (vault / "Work/Areas/Pricing.md").write_text("edited by the owner\n")
    r = run_apply(tmp_path, [ch])["c1"]
    assert r["status"] == "refused" and "changed" in r["reason"]
    assert (vault / "Work/Areas/Pricing.md").read_text() == "edited by the owner\n"


def test_only_passed_changes_are_made(vault, tmp_path):
    rs = run_apply(tmp_path, [splice(vault, "c1", check="FAIL"), splice(vault, "c2", text="Second.")])
    assert rs["c1"]["status"] == "skipped" and rs["c2"]["status"] == "applied"
    assert "Added line." not in (vault / "Work/Areas/Pricing.md").read_text()


def test_two_changes_to_one_note_chain_their_hashes(vault, tmp_path):
    rs = run_apply(tmp_path, [splice(vault, "c1"), splice(vault, "c2", heading="## History", text="Later.")])
    assert rs["c1"]["status"] == rs["c2"]["status"] == "applied"


@pytest.mark.parametrize("target", ["Private/Diary.md", "Loose.md", "../outside.md"])
def test_out_of_scope_targets_are_refused(vault, tmp_path, target):
    (tmp_path / "outside.md").write_text("x\n")
    path = vault / target
    before = path.read_text()
    ch = {"id": "c1", "op": "splice", "target": target, "hash": h(path), "text": "x", "check": "PASS"}
    r = run_apply(tmp_path, [ch])["c1"]
    assert r["status"] == "refused" and "outside" in r["reason"]
    assert path.read_text() == before


def test_inbox_note_is_only_moved_or_marked(vault, tmp_path):
    clip = vault / "Inbox/Clip.md"
    rs = run_apply(tmp_path, [
        {"id": "c1", "op": "splice", "target": "Inbox/Clip.md", "hash": h(clip), "text": "x", "check": "PASS"},
        {"id": "c2", "op": "mark_merged", "target": "Inbox/Clip.md", "hash": h(clip), "into": "Pricing",
         "check": "PASS"}])
    assert rs["c1"]["status"] == "refused" and rs["c2"]["status"] == "applied"
    moved = vault / "Inbox/merged/Clip.md"
    assert not clip.exists() and moved.read_text().startswith('---\ntype: clip\nmerged-into: "[[Pricing]]"\n---\n')


def test_move_never_replaces_and_stays_in_scope(vault, tmp_path):
    note = vault / "Work/Areas/Rates.md"
    rs = run_apply(tmp_path, [
        {"id": "c1", "op": "move", "target": "Work/Areas/Rates.md", "hash": h(note), "to": "Private", "check": "PASS"},
        {"id": "c2", "op": "move", "target": "Work/Areas/Rates.md", "hash": h(note), "to": "Work/Other", "check": "PASS"}])
    assert rs["c1"]["status"] == "refused" and rs["c2"]["status"] == "applied"
    assert (vault / "Work/Other/Rates.md").exists() and not note.exists()


@pytest.mark.parametrize("kind,old,new,ok", [
    ("link", "[[Missing page]]", "[[Pricing]]", True),
    ("link", "See [[Pricing]]", "Read [[Pricing]]", False),
    ("fact", "Day rate is set yearly.", "~~Day rate is set yearly.~~ Day rate is set quarterly.", True),
    ("fact", "Day rate is set yearly.", "Day rate is set quarterly.", False),
    ("frontmatter", "type: reference", "type: pricing", True),
    ("frontmatter", "Day rate is set yearly.", "x", False),
    ("frontmatter", "See [[Pricing]]", "---\ntype: reference\n---\nSee [[Pricing]]", True),
    ("frontmatter", "See [[Pricing]]", "---\ntype: reference\n---\nRead [[Pricing]]", False),
])
def test_replace_changes_only_what_its_kind_allows(vault, tmp_path, kind, old, new, ok):
    target = "Work/Areas/Rates.md" if old.startswith(("[[", "See")) else "Work/Areas/Pricing.md"
    ch = {"id": "c1", "op": "replace", "kind": kind, "target": target, "hash": h(vault / target),
          "old": old, "new": new, "check": "PASS"}
    r = run_apply(tmp_path, [ch])["c1"]
    assert (r["status"] == "applied") is ok
    assert (new in (vault / target).read_text()) is ok


def test_cap_skips_the_rest(vault, tmp_path):
    changes = [splice(vault, f"c{i}", text=f"Line {i}.") for i in range(1, 6)]
    rs = run_apply(tmp_path, changes)
    assert [rs[f"c{i}"]["status"] for i in range(1, 6)] == ["applied"] * 3 + ["skipped"] * 2


def test_dry_run_writes_nothing(vault, tmp_path):
    before = (vault / "Work/Areas/Pricing.md").read_text()
    r = run_apply(tmp_path, [splice(vault)], "--dry-run")["c1"]
    assert r["status"] == "applied" and (vault / "Work/Areas/Pricing.md").read_text() == before
    assert not (tmp_path / "state").exists() and not (vault / "Inbox/Curator log.md").exists()


def test_undo_restores_and_refuses_a_note_changed_since(vault, tmp_path, capsys):
    pricing, clip = vault / "Work/Areas/Pricing.md", vault / "Inbox/Clip.md"
    p_before, c_before = pricing.read_text(), clip.read_text()
    run_apply(tmp_path, [splice(vault), splice(vault, "c2", heading="## History", text="Later."),
                         {"id": "c3", "op": "mark_merged", "target": "Inbox/Clip.md", "hash": h(clip),
                          "into": "Pricing", "check": "PASS"}])
    (vault / "Inbox/merged/Clip.md").write_text("owner edited it\n")
    capsys.readouterr()
    assert curate_apply.main(["--undo", "run-1"]) == 0
    res = {r["id"]: r["status"] for r in json.loads(capsys.readouterr().out)["results"]}
    assert res == {"c3": "refused", "c2": "applied", "c1": "applied"}
    assert pricing.read_text() == p_before and not clip.exists()
    assert curate_apply.main(["--undo", "run-1", "--id", "c1"]) == 0
    assert json.loads(capsys.readouterr().out)["results"][0]["status"] == "skipped"
    assert (vault / "Inbox/merged/Clip.md").read_text() == "owner edited it\n" and c_before


def test_missing_scope_setting_stops(vault, tmp_path, monkeypatch):
    conf = tmp_path / "bare.toml"
    conf.write_text(f'vault_dir = "{vault}"\nvault_inbox = "Inbox"\n', encoding="utf-8")
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(conf))
    with pytest.raises(SystemExit) as exc:
        curate_apply.main(["--run", str(tmp_path)])
    assert exc.value.code == 2


def test_splice_under_a_new_heading_adds_a_section(vault, tmp_path):
    r = run_apply(tmp_path, [splice(vault, heading="## Draws", text="New line.")])["c1"]
    assert r["status"] == "applied"
    assert (vault / "Work/Areas/Pricing.md").read_text().endswith("\n\n## Draws\n\nNew line.\n")


def test_a_note_is_not_marked_merged_when_its_splice_failed(vault, tmp_path):
    clip = vault / "Inbox/Clip.md"
    rs = run_apply(tmp_path, [
        splice(vault, "c1", heading="Not a heading", source="Inbox/Clip.md"),
        {"id": "c2", "op": "mark_merged", "target": "Inbox/Clip.md", "hash": h(clip), "into": "Pricing",
         "check": "PASS"}])
    assert rs["c1"]["status"] == "refused" and rs["c2"]["status"] == "refused"
    assert clip.exists()


def test_a_note_is_marked_merged_after_its_splice(vault, tmp_path):
    clip = vault / "Inbox/Clip.md"
    rs = run_apply(tmp_path, [
        splice(vault, "c1", source="Inbox/Clip.md"),
        {"id": "c2", "op": "mark_merged", "target": "Inbox/Clip.md", "hash": h(clip), "into": "Pricing",
         "check": "PASS"}])
    assert rs["c1"]["status"] == rs["c2"]["status"] == "applied"
