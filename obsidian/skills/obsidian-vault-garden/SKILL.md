---
name: obsidian-vault-garden
description: "Propose tidying for the owner's Obsidian vault without changing it: loose notes at the root with the folder their links point to, thin map-of-content notes with the existing notes that could fill them, and checklists nobody has touched in a year. obsidian-vault-garden (the command) computes the lists; you check each proposal, then file one review note in the vault's inbox and hand the owner the move commands to run themselves. Use when the owner asks to garden, tidy or health-check the vault. Not for writing a new note from a source; use obsidian-video-note."
argument-hint: "[optional: how many loose notes to propose]"
---

# Vault gardening proposal

Load `obsidian-workstream` first and follow its rules: run `obsidian-vault-config`, stop on exit 2, read only through its commands, write only through `obsidian-vault-inbox-write`.

The gardener proposes and never acts. A move, an edit to a map note or a ticked checkbox is the owner's to make, because a wrong move breaks links and the vault holds what they cannot recreate.

## Steps

1. [script] Compute the lists: `obsidian-vault-garden --format json`, adding from the owner's `VAULT-RULES.md` when it has them `--moc-suffix` (its `map_suffix`), `--placeholder`, and one `--skip` per `never_file` entry, and `--limit N` when the owner gave a number. The command reads every note outside the private folders and writes nothing.
   → `obsidian-vault-config` exits 2: stop
2. [judgment] Check each proposal, by section Checking each proposal: keep, change or drop each filing; draft the map-note links; list the dead checklists.
3. [script] File one review note, titled `Vault garden <YYYY-MM-DD>`, through `obsidian-vault-inbox-write` (add `--next-free` if the day's note exists): three sections, one per list, each a lead sentence and then the items (the note, the proposal and one line of why), with the drafted links under the thin map notes, ready to paste.
4. [script] Write the moves: `obsidian-vault-garden --as-script` with the same `--skip` and `--limit`; drop the lines for proposals you changed or dropped and add lines for folders you changed. Every line is `mv -n`, which never replaces a note.
5. [judgment] Hand the owner the script in your reply with the review note's path, and tell them to read it before running it from the vault folder. Never run it yourself.
   → handed over: done

## Checking each proposal

- **Loose notes.** For each proposed folder, read the note with `obsidian-vault-read` and confirm the folder fits what the note is about, not just where its links happen to point. Keep, change (to a folder that exists, with the reason) or drop each one. An "unfiled" note stays listed with no folder; never guess one.
- **Thin map notes.** Read the map note and its `fill_from` notes. Draft the links and one-line descriptions the map could hold, using only notes that exist. The draft goes in the review note, never into the map note itself.
- **Dead checkboxes.** List each note with its count and months untouched. Do not judge whether a task still matters; that is the owner's call.

## Commands

- `obsidian-vault-garden [--limit 15] [--stale-months 12] [--moc-suffix MOC] [--placeholder TEXT] [--skip NAME]... [--format text|json] [--as-script]`: the three lists, or `mv -n` lines for the proposed filings. Reads the settings `vault_dir` and `vault_private_dirs`; standard library only; writes nothing.
