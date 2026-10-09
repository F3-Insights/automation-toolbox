"""youtube_transcript.py with a fake yt-dlp and invented captions; no network."""

import json
import sys

import pytest

import youtube_transcript as yt

INFO = {
    "id": "abcDEF12345", "title": "Inventory turns for small distributors", "channel": "Northwind Traders",
    "upload_date": "20300115", "webpage_url": "https://www.youtube.com/watch?v=abcDEF12345", "duration": 95,
    "chapters": [{"start_time": 0, "title": "Why turns matter"}, {"start_time": 60, "title": "Three fixes"}],
    "subtitles": {"fr": [{"ext": "vtt", "url": "https://captions.example.test/fr.vtt"}]},
    "automatic_captions": {"en-orig": [{"ext": "vtt", "url": "https://captions.example.test/en.vtt"},
                                       {"ext": "json3", "url": "https://captions.example.test/en.json3"}]},
}
JSON3 = {"events": [
    {"tStartMs": 0, "segs": [{"utf8": "Turns tell you"}, {"utf8": " how fast stock moves."}]},
    {"tStartMs": 2000, "aAppend": 1, "segs": [{"utf8": "\n"}]},
    {"tStartMs": 40000, "segs": [{"utf8": "Slow turns tie up cash."}]},
    {"tStartMs": 61000, "segs": [{"utf8": "First, count what you hold."}]},
]}
VTT = """WEBVTT

00:00:01.000 --> 00:00:03.000
<c>Hello</c> &amp; welcome

00:00:03.000 --> 00:00:05.000
Hello &amp; welcome

00:01:05.500 --> 00:01:07.000
Next line
"""


@pytest.fixture
def fake_ytdlp(tmp_path, monkeypatch):
    script = tmp_path / "fake_ytdlp.py"
    script.write_text(f"import json\nprint(json.dumps({INFO!r}))\n", encoding="utf-8")
    monkeypatch.setenv("YT_DLP", f"{sys.executable} {script}")
    monkeypatch.setattr(yt, "fetch", lambda url: json.dumps(JSON3) if url.endswith("json3") else VTT)


def test_bare_id_becomes_a_watch_url():
    assert yt.video_url("abcDEF12345") == "https://www.youtube.com/watch?v=abcDEF12345"
    assert yt.video_url("https://youtu.be/abcDEF12345") == "https://youtu.be/abcDEF12345"


def test_pick_prefers_uploader_then_orig_then_json3():
    assert yt.pick_track(INFO, "fr") == ({"code": "fr", "ext": "vtt", "url": "https://captions.example.test/fr.vtt"}, False)
    track, auto = yt.pick_track(INFO, "en")
    assert auto and track["code"] == "en-orig" and track["ext"] == "json3"
    assert yt.pick_track(INFO, "de") == (None, None)


def test_vtt_drops_tags_and_rolling_repeats():
    assert yt.parse_vtt(VTT) == [{"start": 1.0, "text": "Hello & welcome"}, {"start": 65.5, "text": "Next line"}]


def test_text_has_details_chapters_and_paragraphs(fake_ytdlp, capsys):
    assert yt.main(["abcDEF12345"]) == 0
    out = capsys.readouterr().out
    assert "Title: Inventory turns for small distributors" in out and "Published: 2030-01-15" in out
    assert "Captions: automatic (en-orig)" in out
    assert "## Why turns matter\n\n[00:00] Turns tell you how fast stock moves.\n\n[00:40] Slow turns tie up cash.\n\n## Three fixes\n\n[01:01] First, count what you hold." in out


def test_json_and_out_file(fake_ytdlp, tmp_path, capsys):
    out = tmp_path / "t.json"
    assert yt.main(["abcDEF12345", "--format", "json", "--out", str(out)]) == 0
    data = json.loads(out.read_text())
    assert data["video"]["channel"] == "Northwind Traders" and len(data["segments"]) == 3


def test_no_captions_exits_1(fake_ytdlp):
    with pytest.raises(SystemExit) as exc:
        yt.main(["abcDEF12345", "--language", "de"])
    assert exc.value.code == 1


def test_missing_ytdlp_exits_2(monkeypatch):
    monkeypatch.setenv("YT_DLP", "/nonexistent/yt-dlp")
    with pytest.raises(SystemExit) as exc:
        yt.main(["abcDEF12345"])
    assert exc.value.code == 2


def test_refuses_plain_http_caption_address():
    with pytest.raises(SystemExit) as exc:
        yt.fetch("http://captions.example.test/en.vtt")
    assert exc.value.code == 2


def test_url_is_passed_after_double_dash(tmp_path, monkeypatch):
    log = tmp_path / "args.json"
    script = tmp_path / "fake.py"
    script.write_text(f"import json, sys\nopen({str(log)!r}, 'w').write(json.dumps(sys.argv[1:]))\nprint(json.dumps({INFO!r}))\n", encoding="utf-8")
    monkeypatch.setenv("YT_DLP", f"{sys.executable} {script}")
    yt.video_info("--exec=touch-something")
    args = json.loads(log.read_text())
    assert args[-2:] == ["--", "--exec=touch-something"]


def test_redirects_are_refused():
    assert yt.NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://elsewhere.example.test/") is None
    assert any(isinstance(h, yt.NoRedirect) for h in yt.OPENER.handlers)


def test_out_inside_the_vault_is_refused(tmp_path, monkeypatch):
    vault = tmp_path / "Vault"
    vault.mkdir()
    conf = tmp_path / "settings.toml"
    conf.write_text(f'vault_dir = "{vault}"\n', encoding="utf-8")
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(conf))
    with pytest.raises(SystemExit) as exc:
        yt.main(["abcDEF12345", "--out", str(vault / "Inbox" / "t.txt")])
    assert exc.value.code == 2 and not (vault / "Inbox").exists()
