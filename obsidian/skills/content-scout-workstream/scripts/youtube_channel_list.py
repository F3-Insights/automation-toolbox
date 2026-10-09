"""List a YouTube channel's videos (titles, ids, links) without downloading any of them.

Asks yt-dlp (an open-source program the owner installs; it is never imported) for the
channel's video list. The fast mode reads the list page only, so publish dates and view
counts are usually empty; --with-stats asks for each video's details instead, which fills
them in and takes one request per video.

Input: a channel URL or @handle, and optionally --max N (newest N), --with-stats and
--out FILE (default: print). Prints or writes a JSON list of
{id, title, publish_date, view_count, duration, url}, newest first as the channel lists them.
Exit 2 when yt-dlp is missing or fails, or when --out points inside the owner's vault
(setting vault_dir). Environment: YT_DLP, the command to run yt-dlp
(default: yt-dlp on PATH, else python3 -m yt_dlp).

    python3 ~/.claude/skills/content-scout-workstream/scripts/youtube_channel_list.py @example-creator --max 25 --out research/example-creator/youtube/_raw.json
"""

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path


def fail(message, code):
    print(message, file=sys.stderr)
    sys.exit(code)


def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


def refuse_vault(out):
    """Stop when --out points inside the owner's vault: notes enter it only through vault_inbox_write.py."""
    vault = settings().get("vault_dir")
    if vault and out.expanduser().resolve().is_relative_to(Path(vault).expanduser().resolve()):
        fail("Refusing to write inside the vault (setting vault_dir); save elsewhere and file the note with vault_inbox_write.py.", 2)


def yt_dlp_command():
    if os.environ.get("YT_DLP"):
        return shlex.split(os.environ["YT_DLP"])
    return ["yt-dlp"] if shutil.which("yt-dlp") else [sys.executable, "-m", "yt_dlp"]


def channel_videos_url(handle_or_url):
    """The channel's /videos page for a URL or an @handle."""
    if handle_or_url.startswith("http"):
        url = handle_or_url.rstrip("/")
        return url if url.endswith("/videos") else url + "/videos"
    return f"https://www.youtube.com/@{handle_or_url.lstrip('@')}/videos"


def to_row(entry):
    vid, raw = entry.get("id"), entry.get("upload_date") or ""
    return {"id": vid, "title": entry.get("title"),
            "publish_date": f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}" if len(raw) == 8 else None,
            "view_count": entry.get("view_count"), "duration": entry.get("duration"),
            "url": f"https://www.youtube.com/watch?v={vid}" if vid else None}


def list_videos(url, max_count=None, with_stats=False):
    cmd = yt_dlp_command() + ["--dump-json", "--no-warnings", "--ignore-errors"]
    if not with_stats:
        cmd.append("--flat-playlist")
    if max_count:
        cmd += ["--playlist-end", str(max_count)]
    try:
        proc = subprocess.run(cmd + ["--", url], capture_output=True, text=True)
    except FileNotFoundError:
        fail("yt-dlp is not installed; install it or set YT_DLP to the command that runs it.", 2)
    if proc.returncode != 0 and not proc.stdout.strip():
        fail(f"yt-dlp failed: {proc.stderr.strip()[-500:]}", 2)
    return [to_row(json.loads(line)) for line in proc.stdout.splitlines() if line.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description="List a YouTube channel's videos through yt-dlp.")
    ap.add_argument("channel", help="channel URL or @handle")
    ap.add_argument("--max", type=int, help="newest N videos only (default: all)")
    ap.add_argument("--with-stats", action="store_true", help="fill dates and views (one request per video)")
    ap.add_argument("--out", type=Path, help="JSON file to write (default: print)")
    args = ap.parse_args(argv)
    if args.out:
        refuse_vault(args.out)

    videos = list_videos(channel_videos_url(args.channel), args.max, args.with_stats)
    text = json.dumps(videos, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"{len(videos)} videos written to {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
