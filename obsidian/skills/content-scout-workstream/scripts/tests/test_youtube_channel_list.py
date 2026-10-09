"""youtube_channel_list.py with a fake yt-dlp that records its arguments; no network."""

import json
import sys

import pytest

import youtube_channel_list as ycl

FAKE = """import json, sys
open(sys.argv[1], "w").write(json.dumps(sys.argv[2:]))
print(json.dumps({"id": "vid00000001", "title": "Cash cycle basics", "upload_date": "20300301", "view_count": 1200, "duration": 640}))
print(json.dumps({"id": "vid00000002", "title": "Pricing a service", "upload_date": None}))
"""


@pytest.fixture
def fake(tmp_path, monkeypatch):
    script, log = tmp_path / "fake.py", tmp_path / "args.json"
    script.write_text(FAKE, encoding="utf-8")
    monkeypatch.setenv("YT_DLP", f"{sys.executable} {script} {log}")
    return log


def test_channel_url_forms():
    assert ycl.channel_videos_url("@example-creator") == "https://www.youtube.com/@example-creator/videos"
    assert ycl.channel_videos_url("https://www.youtube.com/@example-creator/") == "https://www.youtube.com/@example-creator/videos"
    assert ycl.channel_videos_url("https://www.youtube.com/@example-creator/videos") == "https://www.youtube.com/@example-creator/videos"


def test_lists_rows_flat_by_default(fake, capsys):
    assert ycl.main(["@example-creator", "--max", "2"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows[0] == {"id": "vid00000001", "title": "Cash cycle basics", "publish_date": "2030-03-01",
                       "view_count": 1200, "duration": 640, "url": "https://www.youtube.com/watch?v=vid00000001"}
    assert rows[1]["publish_date"] is None
    args = json.loads(fake.read_text())
    assert "--flat-playlist" in args and args[args.index("--playlist-end") + 1] == "2"


def test_with_stats_and_out_file(fake, tmp_path, capsys):
    out = tmp_path / "x" / "_raw.json"
    ycl.main(["@example-creator", "--with-stats", "--out", str(out)])
    assert "--flat-playlist" not in json.loads(fake.read_text())
    assert len(json.loads(out.read_text())) == 2


def test_missing_ytdlp_exits_2(monkeypatch):
    monkeypatch.setenv("YT_DLP", "/nonexistent/yt-dlp")
    with pytest.raises(SystemExit) as exc:
        ycl.main(["@example-creator"])
    assert exc.value.code == 2


def test_url_is_passed_after_double_dash(fake):
    ycl.main(["@example-creator"])
    args = json.loads(fake.read_text())
    assert args[-2:] == ["--", "https://www.youtube.com/@example-creator/videos"]


def test_out_inside_the_vault_is_refused(fake, tmp_path, monkeypatch):
    vault = tmp_path / "Vault"
    vault.mkdir()
    conf = tmp_path / "settings.toml"
    conf.write_text(f'vault_dir = "{vault}"\n', encoding="utf-8")
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(conf))
    with pytest.raises(SystemExit) as exc:
        ycl.main(["@example-creator", "--out", str(vault / "research" / "_raw.json")])
    assert exc.value.code == 2 and not fake.exists()
