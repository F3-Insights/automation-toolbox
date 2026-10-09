"""Find notes in the owner's Obsidian vault by fuzzy title.

Answers "where is the note about X" in one call, including titles with spaces, brackets or
emoji that break shell globbing. Private folders (setting vault_private_dirs) are never
searched.

Input: a query, and optionally --vault (else the setting vault_dir), --limit, --format.
Prints a table of matches (title, path, why it matched, size), or JSON with each match's
frontmatter. Exit 1 when nothing matches; exit 2 when no vault is configured.

    python3 ~/.claude/skills/obsidian-workstream/scripts/vault_find.py "pricing ideas" --limit 3
"""

import argparse
import json

from _common import Vault


def main(argv=None):
    ap = argparse.ArgumentParser(description="Find Obsidian notes by fuzzy title.")
    ap.add_argument("query")
    ap.add_argument("--vault", help="vault root (default: setting vault_dir)")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--format", choices=["md", "json"], default="md")
    args = ap.parse_args(argv)

    v = Vault(args.vault)
    matches = []
    for note, why in v.find(args.query, args.limit):
        meta, body = v.read(note)
        matches.append({"title": note["stem"], "rel": note["rel"], "folder": note["folder"], "abs": str(note["path"]),
                        "matched_by": why, "frontmatter": meta, "body_chars": len(body)})
    if args.format == "json":
        print(json.dumps({"vault": str(v.root), "query": args.query, "count": len(matches), "matches": matches}, indent=1))
    elif not matches:
        print(f"No note matches {args.query!r}.")
    else:
        print(f"# {len(matches)} match(es) for {args.query!r}\n\n| Title | Path | Matched by | Size |\n|---|---|---|---|")
        for m in matches:
            print(f"| {m['title']} | {m['rel']} | {m['matched_by']} | {m['body_chars']} ch |")
    return 0 if matches else 1


if __name__ == "__main__":
    raise SystemExit(main())
