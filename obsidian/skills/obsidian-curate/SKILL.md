---
name: obsidian-curate
description: "Curate the owner's chosen part of the Obsidian vault, run by obsidian-worker as the main session of a curator Run. Two modes over the folders the owner names as the curate scope: curate (fix links and frontmatter, file misfiled notes, index orphans, mark contradictions and stale facts) and inbox (splice each inbox note into the note it belongs in, merge it into a duplicate, or file it as a new note). Covers the Steps, the change set obsidian-curate-apply makes after the session, and the hand-off to a fresh reviewer on obsidian-review. Not for proposing a tidy of the whole vault; use obsidian-vault-garden."
user-invocable: false
---

# Curating the vault

Keep one part of the vault true and tidy, and empty the inbox into it, without creating work for the owner. The session decides the changes, a fresh reviewer checks each against the notes themselves, and `obsidian-curate-apply` makes the passed ones after the session, with a backup and an undo each. The owner reads the `Curator log` note in the inbox; nothing waits on them.

The Run is the main session, because only a session can dispatch the reviewer; the finish step only applies. Load `obsidian-search` and `obsidian-write` first and keep their rules. The owner's `VAULT-RULES.md` (setting `vault_rules`) and vault map come before this file.

## Inputs

- **Run folder** (`RUN`): where `scan.json`, `proposals.json`, `review.json` and the report go.
- **Mode**: `curate` or `inbox`.
- **Vault map** (optional, `vault_map`): the owner's file saying what each scope folder is for and what to leave alone.
- **Max changes**: the cap (setting `vault_curate_max_changes`, default 25). Fewer is fine.
- **Dry run**: write `proposals.json` with `"dry_run": true`.

## Steps

1. [script] Run `obsidian-vault-config`.
   → exit 2: stop
2. [script] Unless the prepare step wrote it, run `obsidian-curate-scan --out RUN/scan.json`.
   → exit 2: stop
3. [judgment] Read the vault rules, the vault map and `RUN/scan.json`. Decide the mode's changes (section Curate or section File the inbox), reading every note you change with `obsidian-vault-read NOTE --format json` and taking its `sha256` as the change's `hash`. Write `RUN/proposals.json` (section The change set).
   → no changes: step 6
4. [hand-off: obsidian-worker] Review. Dispatch a fresh `obsidian-worker` (with the `Agent` tool), told to follow `obsidian-review`, given only the paths of `RUN/proposals.json` and the vault map: the changes and, through them, the target and source notes. Never your reasoning or this skill's notes; its independence is the point.
5. [judgment] Write each verdict into its change as `"check": "PASS"` or `"FAIL"`, and the reviewer's block to `RUN/review.json`. A FAIL is not fixed or retried this Run; a change with no verdict is not PASS.
6. [judgment] Report (section Report).
   → reported: done

## Curate

Work through the scan's lists, most certain first, up to the cap. A list's item needs no change when the vault map says it is meant that way.

- **Broken link** with one clear target (a `suggest` title, or one `obsidian-vault-find` hit that is plainly the note meant): `replace`, kind `link`. No clear target: leave it.
- **Ambiguous link**: `replace`, kind `link`, to the path form `[[folder/Note|Note]]` of the note the context means.
- **Duplicate titles** that hold the same subject: `splice` into the note that stays any lines only the other holds, and `splice` onto the other `> [!note] Merged into [[kept note]]`. Same title by design (a log per folder): leave.
- **Orphan**: `splice` a `- [[Note]]: one line on what it is` into its folder's index note, under the heading it fits. No index note: leave.
- **Frontmatter** malformed, or missing where the vault rules want it: `replace`, kind `frontmatter`, with the keys and values the rules and the note's content give. Never invent a value.
- **Misfiled**: `move` to the folder its links point to, only when its content fits that folder by the vault map and no link names it by path (`obsidian-vault-links` backlinks).
- **Oversized**: leave; splitting rewrites prose. Name it in the report.
- **Stale line** (`dated_lines`): `replace`, kind `fact`, only when a newer note states the current fact; the new text keeps `~~old~~` and names the newer note. Otherwise leave it.
- **Contradiction** (read each `related_pairs` pair): when a newer dated note settles it, a `fact` replace on the stale one. When the record does not, `splice` onto both notes `> [!question] Conflicts with [[other note]]: <the two claims, quoted short>`. Never ask the owner.

## File the inbox

For each inbox note (skip what the vault map says to leave), read it and its `candidates`, then decide one:

- **Splice**: its content belongs in an existing note. `splice` the inbox note's text, verbatim and without its frontmatter, under the heading it fits (or appended, under a new `## Heading` line when none fits), ending with `(from [[inbox note]])`. Then `mark_merged` the inbox note with `into` that note.
- **Merge**: it duplicates an existing note. `splice` only the lines the existing note lacks, then `mark_merged` as above.
- **File**: it stands alone. `move` it to the scope folder it fits.
- **Leave**: no folder or note clearly fits. Say why in the report.

Content split across two notes is two splices before one `mark_merged`. `mark_merged` moves the note to the inbox's `merged` folder unless the vault rules name a `merged_dir` (then set `to`).

## The change set

`RUN/proposals.json`; `obsidian-curate-apply` holds the full contract and refuses anything else.

```json
{"tool": "obsidian-curate", "version": 1, "mode": "inbox", "dry_run": false,
 "changes": [
  {"id": "c1", "op": "splice", "target": "<vault path>", "hash": "<sha256>", "heading": "## <exact heading line>",
   "text": "<lines to add>", "source": "<vault path of the note the text came from>", "reason": "<one line>"},
  {"id": "c2", "op": "mark_merged", "target": "<inbox path>", "hash": "<sha256>", "into": "<note title>", "reason": "..."},
  {"id": "c3", "op": "replace", "kind": "link|frontmatter|fact", "target": "...", "hash": "...", "old": "<exact text, once>", "new": "...", "reason": "..."},
  {"id": "c4", "op": "move", "target": "...", "hash": "...", "to": "<scope folder>", "reason": "..."}]}
```

- `splice` adds only. `replace` changes only a link, frontmatter, or a fact with the old text struck through. Nothing is deleted. `obsidian-write` lists the guards apply enforces.
- Changes to one note are listed in the order they apply; a `move` of a note comes after every other change to it.

## Report

Five lines at most: the mode, changes passed and failed, what the passed ones do (by list or inbox decision), what was left and why (oversized notes, broken links with no clear target, inbox notes left), and that `obsidian-curate-apply` makes them after the session. Never claim a change was made.
