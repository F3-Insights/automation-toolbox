"""loom_harvest.py against a fake Loom: nothing here touches the network. Video ids are invented."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import loom_harvest as lh  # noqa: E402

GOOD = "a" * 32
BARE = "b" * 32


@pytest.fixture(autouse=True)
def empty_settings(tmp_path, monkeypatch):
    path = tmp_path / "settings.toml"
    path.write_text("")
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(path))
    monkeypatch.delenv("LOOM_COOKIES_FILE", raising=False)
    monkeypatch.setattr(lh.time, "sleep", lambda s: None)
    return path


def fake_loom(calls):
    """GOOD has a transcript through GraphQL; BARE has none anywhere."""
    def fetch(url, data=None, headers=None):
        calls.append(url)
        if url.startswith("https://www.loom.com/v1/oembed"):
            return 200, json.dumps({"title": "How Acme approves vendor invoices", "duration": 312}).encode()
        if url == lh.GRAPHQL_URL:
            vid = json.loads(data)["variables"]["videoId"]
            if vid == GOOD:
                return 200, json.dumps({"data": {"fetchVideoTranscript": {
                    "__typename": "VideoTranscriptDetails", "source_url": "https://cdn.test/t.json",
                    "captions_source_url": "https://cdn.test/c.vtt"}}}).encode()
            return 200, json.dumps({"data": {"fetchVideoTranscript": {"__typename": "GenericError"}}}).encode()
        if url == "https://cdn.test/t.json":
            return 200, b'[{"ts": 0, "text": "so what you will want to do"}]'
        if url == "https://cdn.test/c.vtt":
            return 200, b"WEBVTT"
        if url.startswith("https://www.loom.com/share/"):
            return 200, b"<html><title>Weekly sync | Loom</title></html>"
        raise AssertionError(url)
    return fetch


def test_video_id_from_link_or_bare_id():
    assert lh.video_id_from(f"https://www.loom.com/share/{GOOD}?sid=x") == GOOD
    assert lh.video_id_from(BARE) == BARE
    assert lh.video_id_from("not a video") is None


def test_harvest_archives_transcript_and_reports_missing(tmp_path, capsys):
    videos = tmp_path / "videos.txt"
    videos.write_text(f"# the library\nhttps://www.loom.com/share/{GOOD}\n{BARE}\nnonsense\n")
    calls = []
    code = lh.main(["--videos", str(videos), "--archive", str(tmp_path / "arch"), "--no-register"],
                   fetch=fake_loom(calls))
    out = capsys.readouterr()
    assert code == 0
    meta = json.loads((tmp_path / "arch" / GOOD / "meta.json").read_text())
    assert meta["status"] == "OK" and meta["title"].startswith("How Acme")
    assert meta["raw_path"].endswith("transcript.json") and len(meta["content_hash"]) == 64
    assert (tmp_path / "arch" / GOOD / "captions.vtt").read_text() == "WEBVTT"
    assert json.loads((tmp_path / "arch" / BARE / "meta.json").read_text())["status"] == "NO_TRANSCRIPT_FOUND"
    assert '"OK": 1' in out.out and "skipped 1 line" in out.err


def test_registers_ok_videos_in_the_store(tmp_path, monkeypatch, capsys):
    videos = tmp_path / "videos.txt"
    videos.write_text(GOOD + "\n")
    seen = []
    monkeypatch.setattr(lh, "register", lambda meta: seen.append(meta["video_id"]))
    assert lh.main(["--videos", str(videos), "--archive", str(tmp_path / "a")], fetch=fake_loom([])) == 0
    assert seen == [GOOD]


def test_register_writes_a_recording_source(tmp_path, monkeypatch):
    sent = {}
    monkeypatch.setattr(lh.subprocess, "run", lambda cmd, **kw: sent.setdefault("cmd", cmd))
    lh.register({"video_id": GOOD, "url": "u", "title": "t", "content_hash": "h", "raw_path": "/r",
                 "fetched_at": "2030-01-01T00:00:00Z"}, store=Path("store.py"))
    source = json.loads(sent["cmd"][-1])
    assert sent["cmd"][2:4] == ["add-source", "--json"]
    assert source["type"] == "recording" and source["meta"]["platform"] == "loom"


def test_every_fetch_failing_exits_1(tmp_path, capsys):
    videos = tmp_path / "videos.txt"
    videos.write_text(BARE + "\n")
    assert lh.main(["--videos", str(videos), "--archive", str(tmp_path / "a")], fetch=fake_loom([])) == 1
    assert "no Loom sign-in cookie" in capsys.readouterr().err


def test_missing_settings_exit_2(capsys):
    with pytest.raises(SystemExit) as done:
        lh.main([])
    assert done.value.code == 2 and "video_list" in capsys.readouterr().err


def test_refuses_a_non_https_transcript_link(tmp_path):
    def fetch(url, data=None, headers=None):
        if url == lh.GRAPHQL_URL:
            return 200, json.dumps({"data": {"fetchVideoTranscript": {
                "__typename": "VideoTranscriptDetails", "source_url": "file:///etc/hosts"}}}).encode()
        if url.startswith("file:"):
            raise AssertionError("fetched a non-https link")
        return 404, b""
    meta = lh.harvest_one(fetch, GOOD, tmp_path)
    assert meta["status"] == "DOWNLOAD_FAILED" and "refused" in meta["transcript.json_error"]


def test_real_fetch_refuses_plain_http():
    assert lh.make_fetch(None)("http://example.test/x")[0] == 0


def test_register_failure_keeps_going_and_exits_1(tmp_path, monkeypatch, capsys):
    videos = tmp_path / "videos.txt"
    videos.write_text(GOOD + "\n")

    def broken(meta):
        raise lh.subprocess.CalledProcessError(2, "store", stderr=b"no database")
    monkeypatch.setattr(lh, "register", broken)
    assert lh.main(["--videos", str(videos), "--archive", str(tmp_path / "a")], fetch=fake_loom([])) == 1
    err = capsys.readouterr().err
    assert "archived but not registered: no database" in err
    assert (tmp_path / "a" / GOOD / "transcript.json").exists()
