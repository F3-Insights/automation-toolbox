"""Read one note from the owner's Obsidian vault, with its frontmatter parsed out.

Resolves the note by fuzzy title (an ambiguous title stops and lists the candidates), so a
file name with spaces, brackets or emoji never goes through shell quoting. A note in a
private folder (setting vault_private_dirs) cannot be read.

Input: a title or path, and optionally --vault (else the setting vault_dir) and --format.
Prints the note (frontmatter as a list, then the body), or JSON with frontmatter, links and
body. Exit 1 when no single note matches; exit 2 when no vault is configured.

    python3 ~/.claude/skills/obsidian-workstream/scripts/vault_read.py "Reading list" --format json
"""

import argparse
import json

from _common import Vault, extract_links


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read an Obsidian note by fuzzy title.")
    ap.add_argument("query")
    ap.add_argument("--vault", help="vault root (default: setting vault_dir)")
    ap.add_argument("--format", choices=["md", "json"], default="md")
    args = ap.parse_args(argv)

    v = Vault(args.vault)
    note = v.resolve_one(args.query)
    meta, body = v.read(note)
    if args.format == "json":
        print(json.dumps({"vault": str(v.root), "note": note["rel"], "title": note["stem"], "abs": str(note["path"]),
                          "frontmatter": meta, "links": extract_links(body), "body": body}, indent=1))
        return 0
    print(f"# {note['stem']}\n\n`{note['rel']}`\n")
    if meta:
        print("## Frontmatter\n")
        for key, value in meta.items():
            print(f"- **{key}**: {', '.join(value) if isinstance(value, list) else value}")
        print()
    print("---\n")
    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
