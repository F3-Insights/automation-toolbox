"""Write one new note into the vault's inbox folder, and never over an existing note.

This is the only way the obsidian skills put anything into the owner's vault. The note goes
to <vault_dir>/<vault_inbox>/<title>.md. The title is cleaned of characters a Windows or
synced filesystem refuses. An existing note of that name is never replaced: the script stops,
or with --next-free writes "<title> 2.md", "<title> 3.md" and so on. The inbox folder must
already exist and sit inside the vault (symlinks followed), outside every private folder and
outside Obsidian's own folders and the trash.

Input: --title, the note's text on stdin or from --from FILE, and optionally --vault and
--inbox (else the settings vault_dir and vault_inbox). Prints the path written.
Exit 1 when the note exists (without --next-free) or the text is empty; exit 2 when a
setting is missing or the inbox is not a folder inside the vault.

    python3 ~/.claude/skills/obsidian-workstream/scripts/vault_inbox_write.py --title "Video - Pricing talk" --from /tmp/run/note.md
"""

import argparse
import re
import sys
from pathlib import Path

from _common import ALWAYS_SKIPPED, Vault, fail, settings

ILLEGAL = re.compile(r'[\\/*?"<>|\x00-\x1f]')


def clean_title(title):
    """A file-system-safe note title: ':' becomes ' -', other illegal characters go."""
    text = ILLEGAL.sub("", title.replace(":", " -"))
    text = re.sub(r"\s+", " ", text).strip().strip(".").strip()
    return text[:150].rstrip()


def inbox_folder(vault, inbox):
    if not inbox:
        fail("No inbox configured: set vault_inbox in the owner's settings or pass --inbox.", 2)
    folder = (vault.root / inbox).resolve()
    rel = folder.relative_to(vault.root).as_posix() if folder.is_relative_to(vault.root) else None
    if rel in (None, ".") or vault.is_private(rel) or set(Path(rel).parts) & ALWAYS_SKIPPED:
        fail(f"The inbox {inbox!r} must be a folder inside the vault, outside its private folders and Obsidian's own.", 2)
    if not folder.is_dir():
        fail(f"The inbox folder {folder} does not exist; create it in the vault first.", 2)
    return folder


def write_new(folder, title, text, next_free):
    """Create the note with exclusive mode, so a note that appears meanwhile is not replaced."""
    n = 1
    while True:
        path = folder / (f"{title}.md" if n == 1 else f"{title} {n}.md")
        try:
            with open(path, "x", encoding="utf-8") as fh:
                fh.write(text if text.endswith("\n") else text + "\n")
            return path
        except FileExistsError:
            if not next_free:
                fail(f"A note already exists at {path}; nothing was written. Use --next-free or another title.")
            n += 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write a new note into the vault inbox, never overwriting.")
    ap.add_argument("--title", required=True)
    ap.add_argument("--from", dest="source", help="file holding the note's text (default: stdin)")
    ap.add_argument("--vault", help="vault root (default: setting vault_dir)")
    ap.add_argument("--inbox", help="inbox folder inside the vault (default: setting vault_inbox)")
    ap.add_argument("--next-free", action="store_true", help='add " 2", " 3" to the title instead of stopping')
    args = ap.parse_args(argv)

    text = Path(args.source).read_text(encoding="utf-8") if args.source else sys.stdin.read()
    if not text.strip():
        fail("The note is empty; nothing was written.")
    title = clean_title(args.title)
    if not title:
        fail("The title is empty once cleaned; nothing was written.")
    vault = Vault(args.vault)
    folder = inbox_folder(vault, args.inbox or settings().get("vault_inbox"))
    print(write_new(folder, title, text, args.next_free))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
