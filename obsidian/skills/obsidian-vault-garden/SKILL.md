---
name: obsidian-vault-garden
description: "Propose tidying for the owner's Obsidian vault without changing it: loose notes at the root with the folder their links point to, thin map-of-content notes with the existing notes that could fill them, and checklists nobody has touched in a year. vault_garden.py computes the lists; you check each proposal, then file one review note in the vault's inbox and hand the owner the move commands to run themselves. Use when the owner asks to garden, tidy or health-check the vault. Not for writing a new note from a source; use obsidian-video-note."
argument-hint: "[optional: how many loose notes to propose]"
---

# Vault gardening proposal

Load `obsidian-workstream` first (at `~/.claude/skills/obsidian-workstream/SKILL.md` if it is not loaded) and follow its rules: run `vault_config.py`, stop on exit 2, read only through its scripts, write only through `vault_inbox_write.py`.

The gardener proposes and never acts. A move, an edit to a map note or a ticked checkbox is the owner's to make, because a wrong move breaks links and the vault holds what they cannot recreate.

## Steps

### 1. Compute the lists

Run `python3 ~/.claude/skills/obsidian-vault-garden/scripts/vault_garden.py --format json`, adding from the owner's `VAULT-RULES.md` when it has them: `--moc-suffix` (its `map_suffix`), `--placeholder`, and one `--skip` per `never_file` entry. Add `--limit N` when the owner gave a number. The script reads every note outside the private folders and writes nothing.

### 2. Check each proposal

- **Loose notes.** For each proposed folder, read the note with `vault_read.py` and confirm the folder fits what the note is about, not just where its links happen to point. Keep, change (to a folder that exists, with the reason) or drop each one. An "unfiled" note stays listed with no folder; never guess one.
- **Thin map notes.** Read the map note and its `fill_from` notes. Draft the links and one-line descriptions the map could hold, using only notes that exist. The draft goes in the review note, never into the map note itself.
- **Dead checkboxes.** List each note with its count and months untouched. Do not judge whether a task still matters; that is the owner's call.

### 3. File the review note

Write one note, titled `Vault garden <YYYY-MM-DD>`, through `vault_inbox_write.py` (add `--next-free` if the day's note exists). It has three sections, one per list, each a lead sentence and then the items: the note, the proposal and one line of why. Under the thin map notes, put the drafted links ready to paste.

### 4. Hand over the moves

Run the script again with `--as-script` (and the same `--skip` and `--limit`), drop the lines for proposals you changed or dropped, add lines for folders you changed, and give the owner the script in your reply with the note's path. Every line is `mv -n`, which never replaces a note. Tell the owner to read it before running it from the vault folder. Never run it yourself.

## Scripts

- `scripts/vault_garden.py [--limit 15] [--stale-months 12] [--moc-suffix MOC] [--placeholder TEXT] [--skip NAME]... [--format text|json] [--as-script]`: the three lists, or `mv -n` lines for the proposed filings. Reads the settings `vault_dir` and `vault_private_dirs`; standard library only; writes nothing.
