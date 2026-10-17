# Obsidian

Agents and skills that work with the owner's Obsidian vault: turning a YouTube video into a note shaped by why it mattered, proposing tidying for the vault without touching it, and tracking outside creators so their ideas are cited properly. The vault is the owner's most personal store, so every piece here reads it only through scripts that skip the private folders the owner names, and writes only new notes into one inbox folder, never over an existing note. The vault's location, its folder names, the owner's note conventions and the creators they follow are all the owner's settings and files, never part of this repository.

## Agents

| Agent | What it does | Needs |
|---|---|---|
| `content-scout` | Indexes the channels on the owner's watchlist, then fetches and distills only the items picked, with attribution | setting `[content-scout-workstream] research_dir`; yt-dlp for YouTube |

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `obsidian-workstream` | Reference: the vault settings, the privacy and write rules, note conventions, VAULT-RULES.md fields, and the find, read, links and inbox-write scripts | settings `vault_dir`, `vault_inbox` |
| `obsidian-video-note` | A YouTube video to an inbox note: transcript fetched, the owner's takeaway as the lens, themed summary with verbatim quotes | settings `vault_dir`, `vault_inbox`; yt-dlp, or a pasted transcript |
| `obsidian-vault-garden` | Proposes filing for loose root notes, fills for thin map notes and a list of dead checklists; files one review note and hands the owner `mv -n` lines to run | setting `vault_dir` (and `vault_inbox` for the review note) |
| `content-scout-workstream` | Reference for `content-scout`: watchlist, creator and channel folders, index then distill, formats, attribution | setting `research_dir` |

The skills that write to the vault load `obsidian-workstream` first.

## Scripts

Run each as `python3 ~/.claude/skills/<skill>/scripts/<script>.py`; all are standard library only.

**`obsidian-workstream`**
- `vault_config.py`: the vault settings and what is wrong with them; exit 2 when the vault or inbox is unusable.
- `vault_find.py`: notes by fuzzy title, best first.
- `vault_read.py`: one note with its frontmatter parsed and links listed.
- `vault_links.py`: a note's forward links (resolved, unresolved, ambiguous) and backlinks.
- `vault_inbox_write.py`: one new note into the inbox folder; never overwrites.

**`obsidian-vault-garden`**
- `vault_garden.py`: the three tidying lists, or `mv -n` lines for the proposed filings; writes nothing.

**`obsidian-video-note`**
- `youtube_transcript.py`: a video's transcript and details through yt-dlp, as timestamped text under its chapters or as JSON.

**`content-scout-workstream`**
- `youtube_channel_list.py`: a channel's videos as JSON through yt-dlp.

## Settings and environment

Top level: `vault_dir`, `vault_inbox`, `vault_private_dirs`, `vault_rules`. `[content-scout-workstream]`: `research_dir`, `watchlist`. Environment: `YT_DLP`, the command that runs yt-dlp. Every key and default is in [docs/settings.md](../docs/settings.md).

## Needs

No Insights Portal. The YouTube scripts need yt-dlp, an open-source program the owner installs (`pipx install yt-dlp`); the scripts run it and never import it. The owner keeps a `VAULT-RULES.md` (see `obsidian-workstream/references/vault-rules.example.md`) and a creator watchlist (see `content-scout-workstream/references/watchlist.example.md`) outside this repository. `marketing-content-orchestrator` (marketing) dispatches `content-scout` when it is installed.
