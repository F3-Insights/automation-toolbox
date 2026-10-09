"""Fetch a YouTube video's transcript and details, so nobody has to paste it by hand.

Asks yt-dlp (an open-source program the owner installs; it is never imported) for the
video's details, including its caption tracks, then downloads the caption track in the
requested language: a track the uploader wrote first, YouTube's automatic captions second.
Nothing about the video is downloaded but its text.

Input: a video URL or 11-character id, and optionally --language (default en), --format
text|json, --paragraph-seconds (how much speech goes in one timestamped paragraph, default
30) and --out FILE (default: print). The text format starts with the title, channel,
publish date, URL and caption kind, then timestamped paragraphs under the video's chapter
headings when it has chapters. The json format holds the same details and every caption
segment.

Exit 1 when the video has no captions in that language; exit 2 when yt-dlp is missing or
fails, a caption download is redirected, or --out points inside the owner's vault (setting
vault_dir). Environment: YT_DLP, the command to run yt-dlp (default: yt-dlp on PATH, else
python3 -m yt_dlp).

    python3 ~/.claude/skills/obsidian-video-note/scripts/youtube_transcript.py https://www.youtube.com/watch?v=VIDEO_ID --out /tmp/run/transcript.txt
"""

import argparse
import html
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


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


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect, so a caption address cannot hand the request to another host."""

    def redirect_request(self, *args, **kwargs):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def yt_dlp_command():
    if os.environ.get("YT_DLP"):
        return shlex.split(os.environ["YT_DLP"])
    return ["yt-dlp"] if shutil.which("yt-dlp") else [sys.executable, "-m", "yt_dlp"]


def video_url(arg):
    return f"https://www.youtube.com/watch?v={arg}" if ID_RE.match(arg) else arg


def video_info(url):
    """yt-dlp's details for one video, without downloading it."""
    cmd = yt_dlp_command() + ["--dump-single-json", "--skip-download", "--no-warnings", "--no-playlist", "--", url]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        fail("yt-dlp is not installed; install it or set YT_DLP to the command that runs it.", 2)
    if proc.returncode != 0:
        fail(f"yt-dlp failed: {proc.stderr.strip()[-500:]}", 2)
    return json.loads(proc.stdout)


def pick_track(info, language):
    """(track, auto_generated) for the language: the uploader's captions first, then automatic.

    Within each, an exact language code wins, then "<lang>-orig", then any "<lang>-..." code;
    json3 is preferred over vtt because it has no repeated rolling lines.
    """
    for key, auto in (("subtitles", False), ("automatic_captions", True)):
        tracks = info.get(key) or {}
        codes = [language, f"{language}-orig"] + sorted(c for c in tracks if c.startswith(language + "-"))
        for code in codes:
            by_ext = {t.get("ext"): t for t in tracks.get(code, []) if t.get("url")}
            for ext in ("json3", "vtt"):
                if ext in by_ext:
                    return {"code": code, "ext": ext, "url": by_ext[ext]["url"]}, auto
    return None, None


def fetch(url):
    if not url.startswith("https://"):
        fail(f"Refusing a caption address that is not https: {url[:60]}", 2)
    try:
        with OPENER.open(url, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as err:
        fail(f"The caption download failed or was redirected (HTTP {err.code}); nothing was followed.", 2)
    except urllib.error.URLError as err:
        fail(f"The caption download failed: {err.reason}", 2)


def parse_json3(text):
    """Caption segments [{start, text}] from YouTube's json3 caption format."""
    segments = []
    for event in json.loads(text).get("events", []):
        words = "".join(seg.get("utf8", "") for seg in event.get("segs") or [])
        words = " ".join(words.split())
        if words:
            segments.append({"start": event.get("tStartMs", 0) / 1000, "text": words})
    return segments


def vtt_seconds(stamp):
    parts = [float(p) for p in stamp.replace(",", ".").split(":")]
    return sum(p * 60 ** i for i, p in enumerate(reversed(parts)))


def parse_vtt(text):
    """Caption segments from WebVTT, without the inline tags and the rolling repeats of auto captions."""
    segments, start, seen_last = [], None, None
    for line in text.splitlines():
        if "-->" in line:
            start = vtt_seconds(line.split("-->")[0].strip())
            continue
        clean = html.unescape(re.sub(r"<[^>]+>", "", line)).strip()
        if start is None or not clean or clean == seen_last:
            continue
        segments.append({"start": start, "text": clean})
        seen_last = clean
    return segments


def stamp(seconds):
    s = int(seconds)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


def paragraphs(segments, chapters, every):
    """Text with a [mm:ss] paragraph every `every` seconds and a heading at each chapter."""
    starts = sorted((c.get("start_time", 0), c.get("title", "")) for c in chapters or [])
    out, para, para_start, next_chapter = [], [], None, 0
    for seg in segments:
        while next_chapter < len(starts) and seg["start"] >= starts[next_chapter][0]:
            if para:
                out.append(f"[{stamp(para_start)}] " + " ".join(para))
                para = []
            out.append(f"## {starts[next_chapter][1]}")
            next_chapter += 1
        if para and seg["start"] - para_start >= every:
            out.append(f"[{stamp(para_start)}] " + " ".join(para))
            para = []
        if not para:
            para_start = seg["start"]
        para.append(seg["text"])
    if para:
        out.append(f"[{stamp(para_start)}] " + " ".join(para))
    return "\n\n".join(out)


def details(info):
    raw = info.get("upload_date") or ""
    return {"id": info.get("id"), "title": info.get("title"), "channel": info.get("channel") or info.get("uploader"),
            "published": f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}" if len(raw) == 8 else None,
            "url": info.get("webpage_url") or video_url(info.get("id") or ""), "duration_seconds": info.get("duration"),
            "chapters": [{"start_time": c.get("start_time", 0), "title": c.get("title", "")} for c in info.get("chapters") or []]}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Fetch a YouTube video's transcript through yt-dlp.")
    ap.add_argument("video", help="video URL or 11-character id")
    ap.add_argument("--language", default="en")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--paragraph-seconds", type=int, default=30)
    ap.add_argument("--out", type=Path, help="file to write (default: print)")
    args = ap.parse_args(argv)
    if args.out:
        refuse_vault(args.out)

    info = video_info(video_url(args.video))
    track, auto = pick_track(info, args.language)
    if not track:
        fail(f"No {args.language} captions for this video; ask the owner to paste the transcript.", 1)
    raw = fetch(track["url"])
    segments = parse_json3(raw) if track["ext"] == "json3" else parse_vtt(raw)
    meta = details(info)
    kind = "automatic" if auto else "uploader"
    if args.format == "json":
        text = json.dumps({"video": meta, "language": track["code"], "captions": kind, "segments": segments}, indent=1)
    else:
        head = [f"Title: {meta['title']}", f"Channel: {meta['channel']}", f"Published: {meta['published']}",
                f"URL: {meta['url']}", f"Captions: {kind} ({track['code']})"]
        text = "\n".join(head) + "\n\n" + paragraphs(segments, meta["chapters"], args.paragraph_seconds)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
        print(args.out)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
