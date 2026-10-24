---
name: youtube-transcript
description: "Reference for the youtube-transcript command, not for a user request on its own: a YouTube video's transcript and details through yt-dlp, as timestamped text under its chapters or as JSON. Copied into obsidian (obsidian-video-note) and marketing (the content scout). Not for listing a channel's videos; use marketing-youtube-channel-list."
---

# YouTube transcript

`youtube-transcript VIDEO [--language en] [--format text|json] [--paragraph-seconds 30] [--out FILE]` writes a video's title, channel, publish date, URL and caption kind, then timestamped paragraphs under the video's chapters (or the same as JSON).

- yt-dlp is an open-source program the owner installs (`pipx install yt-dlp`); the command runs it and never imports it. The environment variable `YT_DLP` names another command to run it.
- Exit 1: the video has no captions in that language (try `--language`). Exit 2: yt-dlp is missing or failed, or a refused path or caption address.
- It refuses an `--out` inside the setting `vault_dir` and any caption download that is not https or is redirected.
- Standard library only. `--help` prints the full contract.
