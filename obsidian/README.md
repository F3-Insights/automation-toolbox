# Obsidian

Skills that work with the owner's Obsidian vault: turning a YouTube video into a note shaped by why it mattered, and proposing tidying for the vault without touching it. The vault is the owner's most personal store, so every piece here reads it only through commands that skip the private folders the owner names, and writes only new notes into one inbox folder, never over an existing note. The vault's location, its folder names and the owner's note conventions are all the owner's settings and files, never part of this repository.

## The plugin

This folder is a standalone Claude Code plugin named `obsidian` (`.claude-plugin/plugin.json`) that holds skills only: no main agent, no worker, no reviewer, because both jobs are the owner's own interactive sessions and nothing here runs unattended. Every script is a named command in `bin/` (`python3 scripts/build_bins.py obsidian`). Switch it on in a vault session and use a skill by name:

```bash
claude --plugin-dir ~/coding-projects/automation-toolbox/obsidian
# then: /obsidian:obsidian-video-note <YouTube URL>
```

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `obsidian-workstream` | Reference: the vault settings, the privacy and write rules, note conventions, VAULT-RULES.md fields, and the find, read, links and inbox-write commands | settings `vault_dir`, `vault_inbox` |
| `obsidian-video-note` | A YouTube video to an inbox note: transcript fetched, the owner's takeaway as the lens, themed summary with verbatim quotes | settings `vault_dir`, `vault_inbox`; yt-dlp, or a pasted transcript |
| `obsidian-vault-garden` | Proposes filing for loose root notes, fills for thin map notes and a list of dead checklists; files one review note and hands the owner `mv -n` lines to run | setting `vault_dir` (and `vault_inbox` for the review note) |
| `youtube-transcript` | Shared copy: a video's transcript through yt-dlp | yt-dlp |

The skills that write to the vault load `obsidian-workstream` first.

## Commands

In `bin/`; all are standard library only and print `--help`.

- `obsidian-vault-config`: the vault settings and what is wrong with them; exit 2 when the vault or inbox is unusable.
- `obsidian-vault-find`: notes by fuzzy title, best first.
- `obsidian-vault-read`: one note with its frontmatter parsed and links listed.
- `obsidian-vault-links`: a note's forward links (resolved, unresolved, ambiguous) and backlinks.
- `obsidian-vault-inbox-write`: one new note into the inbox folder; never overwrites.
- `obsidian-vault-garden`: the three tidying lists, or `mv -n` lines for the proposed filings; writes nothing.
- `youtube-transcript` (the shared copy's, unprefixed): a video's transcript and details through yt-dlp, as timestamped text under its chapters or as JSON.

## What moved out

The outside-creator scout (`content-scout` and `content-scout-workstream`) moved to [marketing](../marketing/) on 2026-10-23: it is not vault work (it refuses a research folder inside the vault), and its only unattended caller is marketing's post writer, which runs it as a section on `marketing-worker`. The `[content-scout-workstream]` settings keep their table name. `youtube_transcript.py`, which both departments run, became the shared `youtube-transcript` skill, copied into each.

## Settings and environment

Top level: `vault_dir`, `vault_inbox`, `vault_private_dirs`, `vault_rules`. Environment: `YT_DLP`, the command that runs yt-dlp. Every key and default is in [docs/settings.md](../docs/settings.md).

## Needs

No Insights Portal. The YouTube command needs yt-dlp, an open-source program the owner installs (`pipx install yt-dlp`); the command runs it and never imports it. The owner keeps a `VAULT-RULES.md` (see `obsidian-workstream/references/vault-rules.example.md`) outside this repository.
