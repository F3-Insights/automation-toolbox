import json
from datetime import date

import pytest

import _common as c
import task_capture_queue as q

TODAY = date(2026, 10, 1)


def test_sources_read_every_kind_and_report_the_future_one(sources):
    srcs, _ = c.load_sources(str(sources))
    items, reports = c.gather(srcs)
    by = {r["name"]: r for r in reports}
    assert by["said-not-seen"]["items"] == 3 and by["said-not-seen"]["open"] == 2
    assert by["quick-capture"]["items"] == 3 and by["quick-capture"]["open"] == 2
    assert by["chat"]["readable"] is None
    draft = next(i for i in items if "Fabrikam" in i["text"])
    assert draft["date"] == "2026-09-27"
    assert draft["marker"] == c.source_marker(draft["key"])


def test_marker_matches_the_apply_format():
    # task-stack-apply finds a captured item's task by this exact marker.
    import hashlib
    expected = "tsk" + hashlib.sha256(b"source:quick-capture:abc").hexdigest()[:12]
    assert c.source_marker("quick-capture:abc") == expected


def test_item_keys_are_stable_when_other_lines_change(sources, tmp_path):
    srcs, _ = c.load_sources(str(sources))
    before = {i["text"]: i["key"] for i in c.gather(srcs)[0]}
    inbox = tmp_path / "inbox.md"
    inbox.write_text("# Notes\n- Something new\n" + inbox.read_text(), encoding="utf-8")
    after = {i["text"]: i["key"] for i in c.gather(srcs)[0]}
    assert after["Book the Lakeview workshop room"] == before["Book the Lakeview workshop room"]


def test_an_unreadable_source_is_reported_and_others_still_read(sources, tmp_path):
    data = json.loads(sources.read_text())
    data["sources"].append({"name": "notes", "kind": "folder-inbox", "path": str(tmp_path / "missing")})
    sources.write_text(json.dumps(data))
    items, reports = c.gather(c.load_sources(str(sources))[0])
    assert next(r for r in reports if r["name"] == "notes")["readable"] is False
    assert len(items) == 6


def test_sources_come_from_settings_when_no_file_is_given(no_owner_settings, tmp_path):
    no_owner_settings.write_text(f'[task-stack-capture]\nsources = [{{name = "inbox", kind = "markdown-inbox", '
                                 f'path = "{tmp_path / "x.md"}", optional = true}}]\n')
    srcs, origin = c.load_sources("")
    assert srcs[0]["name"] == "inbox" and "settings" in origin
    assert c.gather(srcs)[0] == []


def test_missing_and_bad_sources_are_refused(tmp_path):
    with pytest.raises(c.Bad, match="no capture sources"):
        c.load_sources("")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"sources": [{"name": "Bad Name", "kind": "markdown-inbox", "path": "x"}]}))
    with pytest.raises(c.Bad, match="kebab"):
        c.load_sources(str(bad))


def test_queue_sorts_newest_first_and_sets_aside_old_and_closed(sources):
    items, reports = c.gather(c.load_sources(str(sources))[0])
    result = q.build(items, reports, {}, today=TODAY, max_items=2, batch_size=1)
    n = result["counts"]
    assert (n["closed"], n["expired"], n["queued"], n["deferred"]) == (2, 1, 2, 1)
    assert [i["text"] for i in result["items"]] == ["Book the Lakeview workshop room", "Send Dana the freight summary"]
    assert result["batches"] == ["b1", "b2"]
    assert result["deferred"][0]["date"] == "2026-09-27"
    assert q.first_line(result).startswith("QUEUE: 2 item(s) queued")


def test_queue_leaves_out_final_rows_and_keeps_seen_ones(sources):
    items, reports = c.gather(c.load_sources(str(sources))[0])
    done = next(i for i in items if "Dana" in i["text"])["key"]
    old = next(i for i in items if "Acme" in i["text"])["key"]
    recorded = {done: {"state": "created"}, old: {"state": "seen", "attempts": "1", "first_seen": "x"}}
    result = q.build(items, reports, recorded, today=TODAY)
    keys = [i["key"] for i in result["items"]]
    assert done not in keys and old in keys
    assert result["counts"]["processed"] == 1


def test_queue_hints_markers_duplicates_and_the_domain(sources):
    items, reports = c.gather(c.load_sources(str(sources))[0])
    dana = next(i for i in items if "Dana" in i["text"])
    corpus = {
        "domain": [{"id": "D1", "name": "Northwind Traders"}],
        "project": [{"id": "P1", "name": "General", "domain_id": "D1", "is_general": True}],
        "task": [
            {"id": "T1", "title": "Send Dana freight summary", "status": "TODO", "project_id": "P1",
             "owner_contact_id": "me"},
            {"id": "T2", "title": "Book room", "status": "TODO", "source_reference": c.source_marker(
                next(i for i in items if "Lakeview" in i["text"])["key"])},
            {"id": "T3", "title": "Send Dana the freight summary", "status": "TODO", "owner_contact_id": "other"},
            {"id": "T4", "title": "Send Dana the freight summary", "status": "DONE", "updated_at": "2026-01-01"},
        ]}
    ctx = q.portal_context(corpus, "me", TODAY)
    result = q.build(items, reports, {}, today=TODAY, ctx=ctx, owner="me", portal="read")
    got = {i["key"]: i for i in result["items"]}
    assert [x["ref"] for x in got[dana["key"]]["candidates"]] == ["portal://task/t1"]
    assert got[dana["key"]]["domain_hint"]["catch_all_project"] == "p1"
    lake = next(i for i in result["items"] if "Lakeview" in i["text"])
    assert lake["already"] == "portal://task/t2"


def test_similarity_keeps_different_periods_apart():
    assert q.similarity(q.normalise_title("Send the August pack"), q.normalise_title("Send the September pack")) == 0.0


def test_command_offline_writes_a_new_file_and_never_overwrites(sources, tmp_path, capsys):
    out = tmp_path / "run" / "capture-queue.json"
    args = ["--sources", str(sources), "--offline", "--as-of", "2026-10-01", "--out", str(out), "--max="]
    assert q.main(args) == 0
    assert json.loads(out.read_text())["counts"]["queued"] == 3
    assert capsys.readouterr().out.startswith("QUEUE: 3 item(s)")
    with pytest.raises(SystemExit) as exc:
        q.main(args)
    assert exc.value.code == 2


def test_portal_missing_setting_makes_the_queue_stale_not_fatal(sources, capsys):
    assert q.main(["--sources", str(sources), "--as-of", "2026-10-01"]) == 0
    assert "STALE" in capsys.readouterr().out
