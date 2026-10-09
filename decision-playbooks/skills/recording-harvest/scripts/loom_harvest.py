#!/usr/bin/env python3
"""Harvest Loom transcripts (never the video) into a local archive and the decision store.

Loom has no public transcript API. This asks Loom's web GraphQL endpoint for the
transcript and caption links, falls back to reading them from the share page, and
downloads only those small files. The endpoint is undocumented and changes with Loom's
releases, so always run a three-video check (--limit 3) before a full list.

Inputs:
  --videos FILE   one Loom share link or 32-character video id per line, "#" comments
                  allowed; else the setting `video_list` under [recording-harvest]
  --archive DIR   where each video's files go; else `archive_dir` under [recording-harvest]
  --cookies FILE  a Netscape-format cookies.txt exported from a logged-in Loom browser tab,
                  needed for private videos; else the environment variable LOOM_COOKIES_FILE.
                  The file is a credential: keep it out of every repository.
  --limit N, --delay SECONDS (default 3, to stay polite), --no-register

Writes, per video, ARCHIVE/<video_id>/: transcript.json and captions.vtt when Loom has
them, and meta.json (title, duration, status, content hash). Each harvested video is
registered as a `recording` source in the decision store (decision-case-mining's
decision_store.py) unless --no-register. Prints one line per video and a JSON summary.
Exit 0 when at least one video was harvested, 1 when every fetch failed or a harvested
video could not be registered (it stays archived; the run goes on), 2 when a setting is
missing. Only https addresses are fetched and redirects are never followed.

Example:
  python3 loom_harvest.py --videos loom-videos.txt --limit 3
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import MozillaCookieJar
from pathlib import Path

GRAPHQL_URL = "https://www.loom.com/graphql"
TRANSCRIPT_QUERY = """
query FetchVideoTranscript($videoId: ID!, $password: String) {
  fetchVideoTranscript(videoId: $videoId, password: $password) {
    ... on VideoTranscriptDetails { id source_url captions_source_url __typename }
    ... on GenericError { message __typename }
    __typename
  }
}
"""
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Referer": "https://www.loom.com/",
    # Loom checks a request-source header that changes across its releases; if every
    # request returns 403, copy the current value from a browser request.
    "x-loom-request-source": "loom_web_dc2BC1d",
}
STORE = Path.home() / ".claude" / "skills" / "decision-case-mining" / "scripts" / "decision_store.py"
ID_RE = re.compile(r"(?:loom\.com/(?:share|embed)/)?([0-9a-f]{32})")
SESSION_COOKIES = ("connect.sid", "connect.lpid")


def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


def video_id_from(line: str) -> str | None:
    m = ID_RE.search(line.strip())
    return m.group(1) if m else None


def load_cookies(path: str | None) -> MozillaCookieJar | None:
    if not path:
        return None
    jar = MozillaCookieJar(path)
    jar.load(ignore_discard=True, ignore_expires=True)
    # Python drops expired cookies again when it builds each request, so an exported
    # session cookie past its stated expiry would never be sent and private videos would
    # look missing. Loom's server keeps the session longer; let it decide.
    for cookie in jar:
        cookie.expires = None
        cookie.discard = False
    return jar


def has_session(jar) -> bool:
    return bool(jar) and any(c.name in SESSION_COOKIES for c in jar)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect: a redirected request comes back as its 3xx status."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def make_fetch(jar):
    """A fetch(url, data=None, headers=None) -> (status, bytes) that carries the cookies.

    HTTPS only, and redirects are never followed, so the cookies cannot be carried to
    another host or a plain-HTTP address."""
    handlers = [NoRedirect()] + ([urllib.request.HTTPCookieProcessor(jar)] if jar is not None else [])
    opener = urllib.request.build_opener(*handlers)

    def fetch(url, data=None, headers=None):
        if not str(url).startswith("https://"):
            return 0, b"refused: not an https address"
        req = urllib.request.Request(url, data=data, headers={**HEADERS, **(headers or {})})
        try:
            with opener.open(req, timeout=30) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as err:
            return err.code, b""
        except (urllib.error.URLError, TimeoutError) as err:
            return 0, str(err).encode()
    return fetch


def oembed(fetch, vid) -> dict:
    """Title and duration from Loom's public oEmbed, when it gives them."""
    query = urllib.parse.urlencode({"url": f"https://www.loom.com/share/{vid}"})
    status, body = fetch(f"https://www.loom.com/v1/oembed?{query}")
    try:
        return json.loads(body) if status == 200 else {}
    except ValueError:
        return {}


def transcript_links(fetch, vid) -> dict:
    """The transcript and caption links, from GraphQL first and the share page second."""
    payload = json.dumps({"operationName": "FetchVideoTranscript",
                          "variables": {"videoId": vid, "password": None},
                          "query": TRANSCRIPT_QUERY}).encode()
    status, body = fetch(GRAPHQL_URL, payload, {"Content-Type": "application/json",
                                                "apollographql-client-name": "web"})
    if status == 200:
        try:
            data = (json.loads(body).get("data") or {}).get("fetchVideoTranscript") or {}
        except ValueError:
            data = {}
        if data.get("__typename") == "VideoTranscriptDetails":
            links = {k: data.get(k) for k in ("source_url", "captions_source_url") if data.get(k)}
            if links:
                return links
    status, body = fetch(f"https://www.loom.com/share/{vid}")
    if status != 200:
        return {}
    page, links = body.decode("utf-8", "replace"), {}
    for key in ("source_url", "captions_source_url"):
        m = re.search(rf'"{key}"\s*:\s*"([^"]+)"', page)
        if m:
            links[key] = m.group(1).encode().decode("unicode_escape")
    return links


def page_title(fetch, url) -> str | None:
    """oEmbed hides a private video's title; the share page, signed in, shows it."""
    status, body = fetch(url)
    if status != 200:
        return None
    page = body.decode("utf-8", "replace")
    m = (re.search(r'<meta property="og:title" content="([^"]*)"', page)
         or re.search(r"<title>([^<]*?)(?:\s*\|\s*Loom)?</title>", page))
    return m.group(1).strip() if m and m.group(1).strip() else None


def harvest_one(fetch, vid, archive: Path) -> dict:
    folder = archive / vid
    folder.mkdir(parents=True, exist_ok=True)
    meta = {"video_id": vid, "url": f"https://www.loom.com/share/{vid}",
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    meta.update({k: v for k, v in oembed(fetch, vid).items() if k in ("title", "duration")})
    if meta.get("title") in (None, "", "Private Video"):
        meta["title"] = page_title(fetch, meta["url"]) or meta.get("title")

    links = transcript_links(fetch, vid)
    first = None
    for key, name in (("source_url", "transcript.json"), ("captions_source_url", "captions.vtt")):
        if links.get(key) and not str(links[key]).startswith("https://"):
            meta[f"{name}_error"] = "refused: not an https address"
        elif links.get(key):
            status, body = fetch(links[key])
            if status == 200 and body:
                (folder / name).write_bytes(body)
                first = first or folder / name
            else:
                meta[f"{name}_error"] = f"HTTP {status}"
    if not links:
        meta["status"] = "NO_TRANSCRIPT_FOUND"
    elif first is None:
        meta["status"] = "DOWNLOAD_FAILED"
    else:
        meta["status"] = "OK"
        meta["content_hash"] = hashlib.sha256(first.read_bytes()).hexdigest()
        meta["raw_path"] = str(first.resolve())
    (folder / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def register(meta: dict, store: Path = STORE) -> None:
    """Upsert the video as a `recording` source in the decision store."""
    source = {"type": "recording", "external_ref": meta["video_id"], "url": meta["url"],
              "title": meta.get("title"), "content_hash": meta["content_hash"], "raw_path": meta["raw_path"],
              "meta": {"platform": "loom", "duration": meta.get("duration"), "fetched_at": meta["fetched_at"]}}
    subprocess.run([sys.executable, str(store), "add-source", "--json", json.dumps(source)],
                   check=True, capture_output=True)


def need(value, key, flag):
    if value:
        return value
    print(f"loom_harvest: set `{key}` under [recording-harvest] in the owner settings, or pass {flag}",
          file=sys.stderr)
    sys.exit(2)


def main(argv=None, fetch=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--videos", help="file of Loom share links or video ids")
    ap.add_argument("--archive", help="archive folder")
    ap.add_argument("--cookies", help="cookies.txt from a logged-in browser (else LOOM_COOKIES_FILE)")
    ap.add_argument("--limit", type=int, help="harvest at most N videos (the check run)")
    ap.add_argument("--delay", type=float, default=3.0, help="seconds between videos (default 3)")
    ap.add_argument("--no-register", action="store_true", help="archive only; add nothing to the decision store")
    args = ap.parse_args(argv)

    own = settings("recording-harvest")
    videos = Path(need(args.videos or own.get("video_list"), "video_list", "--videos")).expanduser()
    archive = Path(need(args.archive or own.get("archive_dir"), "archive_dir", "--archive")).expanduser()
    cookies = args.cookies or os.environ.get("LOOM_COOKIES_FILE")

    lines = [x for x in videos.read_text(encoding="utf-8").splitlines()
             if x.strip() and not x.strip().startswith("#")]
    vids = [v for v in (video_id_from(x) for x in lines) if v]
    if len(vids) < len(lines):
        print(f"loom_harvest: skipped {len(lines) - len(vids)} line(s) with no video id", file=sys.stderr)
    if args.limit:
        vids = vids[: args.limit]

    jar = load_cookies(cookies)
    if cookies and not has_session(jar):
        print("loom_harvest: the cookies file holds no Loom sign-in cookie; private videos will "
              "come back NO_TRANSCRIPT_FOUND. Export it again from a signed-in tab.", file=sys.stderr)
    fetch = fetch or make_fetch(jar)

    counts: dict[str, int] = {}
    for i, vid in enumerate(vids):
        meta = harvest_one(fetch, vid, archive)
        if meta["status"] == "OK" and not args.no_register:
            try:
                register(meta)
            except (subprocess.CalledProcessError, OSError) as err:
                # The transcript is archived; keep going and say which videos to register again.
                meta["status"] = "REGISTER_FAILED"
                stderr = getattr(err, "stderr", b"") or b""
                print(f"loom_harvest: {vid} archived but not registered: "
                      f"{stderr.decode('utf-8', 'replace').strip() or err}", file=sys.stderr)
        counts[meta["status"]] = counts.get(meta["status"], 0) + 1
        print(f"[{i + 1}/{len(vids)}] {vid} {meta['status']} {meta.get('title') or ''}")
        if i < len(vids) - 1:
            time.sleep(args.delay)
    print(json.dumps({"summary": counts, "archive": str(archive)}, indent=2))

    if counts.get("REGISTER_FAILED"):
        print("loom_harvest: some videos were archived but not registered; run decision_store.py "
              "init if there is no database, then harvest them again.", file=sys.stderr)
        return 1
    if vids and not counts.get("OK"):
        # A missing sign-in is the usual cause and looks like an endpoint change, because
        # Loom answers an anonymous transcript request with a warning, not an error.
        if not has_session(jar):
            print("loom_harvest: every fetch failed and no Loom sign-in cookie was sent; pass --cookies "
                  "before assuming Loom changed.", file=sys.stderr)
        else:
            print("loom_harvest: every fetch failed with a sign-in cookie; it may be revoked, or Loom's "
                  "endpoint changed. Open a share page in that browser, then compare its requests "
                  "with transcript_links().", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
