# Obsidian

A Claude Code plugin (`.claude-plugin/plugin.json`) for the owner's Obsidian vault: turning a YouTube video into a note shaped by why it mattered, proposing tidying for the vault without touching it, curating one part of the vault and filing the inbox into it, and tracking outside creators so their ideas are cited properly. The vault is the owner's most personal store, so every piece here reads it only through commands that skip the private folders the owner names, and writes only new notes into one inbox folder, never over an existing note. The one exception is the curator: its reviewed changes, inside the folders the owner names as its scope and the inbox, are made by `obsidian-curate-apply` after the session, each backed up outside the vault and undoable. The vault's location, its folder names, the owner's note conventions and the creators they follow are all the owner's settings and files, never part of this repository.

## Agents

| Agent | What it does | Needs |
|---|---|---|
| `obsidian-worker` | The plugin's one agent: runs the skill its brief or Automation names. As a curator Run's main session it follows `obsidian-curate` and dispatches a fresh `obsidian-worker` on `obsidian-review` to check every change | settings `vault_dir`, `vault_inbox`; for the curator also `vault_curate_dirs`, `state_dir` |
| `content-scout` | Indexes the channels on the owner's watchlist, then fetches and distills only the items picked, with attribution | setting `[content-scout-workstream] research_dir`; yt-dlp for YouTube |

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `obsidian-search` | Reference: the vault settings, the privacy rules, note conventions, VAULT-RULES.md fields, and the config, find, read, links and curate-scan commands | setting `vault_dir` |
| `obsidian-write` | Reference: the write rules and the vault's only two writers, inbox-write and curate-apply (hash check, scope, backup, cap, change log, undo, dry run) | settings `vault_dir`, `vault_inbox` |
| `obsidian-curate` | A curator Run: mode `curate` fixes links and frontmatter, files misfiled notes, indexes orphans, marks contradictions and stale facts in the curate scope; mode `inbox` splices, merges or files each inbox note. A fresh reviewer checks every change; `obsidian-curate-apply` makes the passed ones after the session | settings `vault_curate_dirs`, `state_dir` |
| `obsidian-review` | The fresh reviewer's checklist: each change judged from the notes alone, PASS or FAIL | as `obsidian-curate` |
| `obsidian-video-note` | A YouTube video to an inbox note: transcript fetched, the owner's takeaway as the lens, themed summary with verbatim quotes | settings `vault_dir`, `vault_inbox`; yt-dlp, or a pasted transcript |
| `obsidian-vault-garden` | Proposes filing for loose root notes, fills for thin map notes and a list of dead checklists; files one review note and hands the owner `mv -n` lines to run | setting `vault_dir` (and `vault_inbox` for the review note) |
| `content-scout-workstream` | Reference for `content-scout`: watchlist, creator and channel folders, index then distill, formats, attribution | setting `research_dir` |

Every skill that reads the vault loads `obsidian-search` first; every one that writes also loads `obsidian-write`.

## Commands

Each script runs as a named command from the plugin's `bin/` (`obsidian-<script name>`, underscores as hyphens); all are standard library only.

**`obsidian-search`** (none writes in the vault)
- `obsidian-vault-config`: the vault settings and what is wrong with them; exit 2 when the vault or inbox is unusable.
- `obsidian-vault-find`: notes by fuzzy title, best first.
- `obsidian-vault-read`: one note with its frontmatter parsed, links listed and its sha256.
- `obsidian-vault-links`: a note's forward links (resolved, unresolved, ambiguous) and backlinks.
- `obsidian-curate-scan`: the curator's computed lists (duplicates, broken and ambiguous links, orphans, oversized notes, bad frontmatter, misfiled notes, dated status lines, related pairs, inbox candidates).

**`obsidian-write`**
- `obsidian-vault-inbox-write`: one new note into the inbox folder; never overwrites.
- `obsidian-curate-apply`: makes a Run's reviewed changes (refusing a note changed since it was read or outside the scope), backs each note up outside the vault, appends to the `Curator log` inbox note, and undoes a Run with `--undo`.

**`obsidian-vault-garden`**
- `obsidian-vault-garden`: the three tidying lists, or `mv -n` lines for the proposed filings; writes nothing.

**`obsidian-video-note`**
- `obsidian-youtube-transcript`: a video's transcript and details through yt-dlp, as timestamped text under its chapters or as JSON.

**`content-scout-workstream`**
- `obsidian-youtube-channel-list`: a channel's videos as JSON through yt-dlp.

## The curator Run

One phase, run unattended: the prepare step runs `obsidian-curate-scan --out RUN/scan.json`; the session (`obsidian-worker` on `obsidian-curate`, mode `curate` or `inbox`) decides the changes and has a fresh worker review them; the finish step runs `obsidian-curate-apply --run RUN`. The owner reads the `Curator log` note and undoes any Run with `obsidian-curate-apply --undo <run>`.

## Settings and environment

Top level: `vault_dir`, `vault_inbox`, `vault_private_dirs`, `vault_rules`, `vault_curate_dirs`, `vault_curate_max_changes`, `state_dir`. `[content-scout-workstream]`: `research_dir`, `watchlist`. Environment: `YT_DLP`, the command that runs yt-dlp. Every key and default is in [docs/settings.md](../docs/settings.md).

## Needs

No Insights Portal. The YouTube scripts need yt-dlp, an open-source program the owner installs (`pipx install yt-dlp`); the scripts run it and never import it. The owner keeps a `VAULT-RULES.md` (see `obsidian-search/references/vault-rules.example.md`) and a creator watchlist (see `content-scout-workstream/references/watchlist.example.md`) outside this repository. `marketing-content-orchestrator` (marketing) dispatches `content-scout` when it is installed.
