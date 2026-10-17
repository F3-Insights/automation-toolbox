---
name: obsidian-write
description: "Reference only, loaded by every obsidian skill and agent that puts anything into the owner's Obsidian vault, not for a user request. Holds the write rules and the vault's only two writers: obsidian-vault-inbox-write (one new note into the inbox, never an overwrite) and obsidian-curate-apply (the curator's reviewed changes inside the curate scope and the inbox, with a hash check, a backup, a per-Run cap, a change log and an undo). Load obsidian-search first."
user-invocable: false
---

# Writing to the owner's Obsidian vault

Nothing changes in the vault except through the two commands below. Load `obsidian-search` first and keep its rules.

## Rules

1. **New notes go in the inbox.** `obsidian-vault-inbox-write` writes one new note into the inbox folder (setting `vault_inbox`); it refuses an existing name and any folder outside the inbox.
2. **Existing notes change only by the curator's reviewed changes.** `obsidian-curate-apply` makes the changes a curator Run decided and a fresh reviewer passed, within `vault_curate_dirs` and the inbox, after the session. Nothing else edits, renames, moves or deletes a note, and no file is written anywhere else in the vault. Any other change to an existing note is offered as a new inbox note or as text in your reply.
3. **Nothing is deleted and the owner's prose is not rewritten.** A splice only adds; a replace fixes a link, frontmatter, or a fact whose old text stays struck through; a merged inbox note is marked `merged-into:` and moved, not removed.

## obsidian-curate-apply's guards

- Only changes marked `"check": "PASS"` are made.
- The target is a note in a curate folder or the inbox, never a private or Obsidian folder; an inbox note is only moved or marked merged; a move lands in the scope or the inbox and never replaces a note.
- The note's sha256 must still be the `hash` the change names (or the one this Run left), so a note the owner edited since is refused.
- At most `vault_curate_max_changes` (default 25) changes per Run.
- Each original is copied to `<state_dir>/obsidian-curate/<run>/backup/` first and logged in `undo.jsonl` beside it; `--undo <run>` restores a Run, refusing a note changed since.
- Each Run appends one line per change, with a link to the note and its undo id, to the inbox note `Curator log`.
- `--dry-run` reads everything and writes nothing.

## Commands

- `obsidian-vault-inbox-write --title TITLE [--from FILE] [--next-free]`: one new note into the inbox from a file or stdin; prints its path. It turns `:` into ` -` and drops `\ / * ? " < > |` from the title.
- `obsidian-curate-apply --run RUN [--dry-run]`, `--undo RUN_ID [--id ID] [--dry-run]`: makes `RUN/proposals.json`'s passed changes (contract in its header), results to `RUN/apply.json`.

Settings: `vault_dir`, `vault_inbox`, `vault_private_dirs`, `vault_curate_dirs`, `vault_curate_max_changes`, `state_dir`.
