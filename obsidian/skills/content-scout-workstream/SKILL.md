---
name: content-scout-workstream
description: "Reference loaded by the content-scout agent, not for a user request. Holds the method for tracking outside creators from the owner's watchlist: creators and their channels as folders in the research folder, a cheap index pass first, then a transcript and distillation only for the items picked, the index and distillation formats, and the attribution rules. Also owns youtube_channel_list.py. To index or distill, dispatch content-scout; to put one video in the vault, use obsidian-video-note."
user-invocable: false
---

# Tracking outside creators

The content scout fetches, indexes and distills what outside creators publish, so the owner's own frameworks, seminars and posts can cite them properly. It produces raw material; it never writes the seminar, the framework or the strategy document built from it.

## Inputs

- **The research folder**: the setting `research_dir` in the `[content-scout-workstream]` table of the owner's settings file, or the folder the caller names. It is a working folder, not the vault: if it sits inside the setting `vault_dir`, stop and say so, because the vault takes only new inbox notes (see `obsidian-workstream`). To keep one distilled video in the vault, the owner runs `obsidian-video-note` on it.
- **The watchlist**: the owner's own file, at the setting `watchlist` in the same table, else `<research_dir>/_watchlist.md`. It names each creator, a folder slug, and each channel with its link. `references/watchlist.example.md` shows the shape with invented creators. The watchlist and the folders it creates stay out of this repository.

If neither the setting nor the caller gives a research folder, stop and say which setting is needed.

## Layout

- A **creator** is a person or organization. A **channel** is where they publish: YouTube, a newsletter, a blog or news page. Channels are subfolders of their creator, never top level.
- `<research_dir>/<creator-slug>/<channel>/_index.md` lists the channel's items.
- `<research_dir>/<creator-slug>/<channel>/<YYYY-MM-DD>-<item-slug>/` holds one distilled item: `transcript.txt` (or `source.md` for text) and `README.md`.

## Two passes

### Index (cheap, first)

For each creator and channel asked for:

1. List every item with its title, link or id, publish date and, where available, views and duration.
   - YouTube: `python3 ~/.claude/skills/content-scout-workstream/scripts/youtube_channel_list.py <@handle or URL> [--max N] --out <channel folder>/_raw.json`. Its fast mode leaves dates and views empty; add `--with-stats` for a short list (`--max 25` or so), since it makes one request per video.
   - Newsletter or blog: fetch the archive or news page and read the post list from it.
2. Write `_index.md` as a table, newest first. Keep the status of items already in the index; add new items as `Pending`.
3. Fetch no transcripts in this pass.

### Distill (per request)

For each item the owner or the caller picks:

1. Create `<YYYY-MM-DD>-<item-slug>/`.
2. Save the text: for a video, `python3 ~/.claude/skills/obsidian-video-note/scripts/youtube_transcript.py <url> --out <folder>/transcript.txt`; for a post, the fetched text as `source.md`. When a video has no captions (exit 1), mark it `Skipped` with the reason.
3. Write `README.md` in the format below.
4. Mark the item `Distilled` in `_index.md`, with the folder name.

## Formats

### `_index.md`

```markdown
# <Creator> - <channel>

Last indexed: YYYY-MM-DD by content-scout

| Publish | Title | Views | Duration | Status | Link |
|---------|-------|------:|---------:|--------|------|
| 2030-05-20 | Title here | 42,300 | 18:24 | Pending | [link](https://...) |
| 2030-05-15 | Another title | 28,100 | 12:03 | **Distilled** in `2030-05-15-slug/` | [link](https://...) |
```

Status values: `Pending`, `Distilled`, `Skipped`, `Stale`.

### The item's `README.md`

```markdown
# <Title>

**Creator:** <name>
**Channel:** <YouTube, newsletter, blog>
**Published:** YYYY-MM-DD
**URL:** <link>
**Views (at index time):** <count>
**Indexed:** YYYY-MM-DD
**Distilled:** YYYY-MM-DD

## One-sentence summary

## Key principles and frameworks
1. **Principle name**: a short explanation

## Verbatim quotes worth using
> "..." (<creator>, <title>)

## Where it could be used
- Only the owner's own frameworks, seminars or topics the watchlist file lists, each with the angle

## Attribution, ready to paste
> Framework from <creator> ([channel](link)). See: [<title>](<url>)

## Raw text
See `transcript.txt` (or `source.md`) in this folder.
```

## Attribution rules

1. Record the source URL of every distilled item.
2. Write the attribution snippet in the README, so a deck can cite it without re-deriving it.
3. Never present a creator's principle as the owner's own; name its origin plainly.

## Requests the scout takes

- "Index <creator> [<channel>]": the index pass for that creator, all its watchlist channels unless one is named.
- "Index everyone": the index pass for every creator on the watchlist.
- "Distill <creator>/<channel>/<item>", or "Distill the N latest from <creator>/<channel>".
- "Add <creator>": create the folder and ask the caller for the channel links; the owner adds the creator to the watchlist, since it is their file.

Report what was indexed and distilled, and every problem: a video with no captions, a paywalled post, a channel that would not list.

## Scripts

- `scripts/youtube_channel_list.py CHANNEL [--max N] [--with-stats] [--out FILE]`: a channel's videos as JSON through yt-dlp, which the owner installs; the environment variable `YT_DLP` names another command to run it. It refuses an `--out` inside the setting `vault_dir`. Standard library only.
