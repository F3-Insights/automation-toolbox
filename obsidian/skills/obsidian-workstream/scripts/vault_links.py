"""Report the link neighbourhood of one note in the owner's Obsidian vault.

Forward links, each marked resolved, unresolved (a dead link) or ambiguous, and the notes
that link back to it, so an agent can walk the graph without reading every note. Notes in
private folders are not part of the graph.

Input: a title or path, and optionally --vault (else the setting vault_dir), --no-backlinks
(skips the full scan backlinks need) and --format. Prints a table, or JSON.
Exit 1 when no single note matches; exit 2 when no vault is configured.

    python3 ~/.claude/skills/obsidian-workstream/scripts/vault_links.py "Projects MOC" --no-backlinks
"""

import argparse
import json

from _common import Vault


def main(argv=None):
    ap = argparse.ArgumentParser(description="Forward links and backlinks of an Obsidian note.")
    ap.add_argument("query")
    ap.add_argument("--vault", help="vault root (default: setting vault_dir)")
    ap.add_argument("--no-backlinks", action="store_true", help="skip backlinks (avoids a full-vault scan)")
    ap.add_argument("--format", choices=["md", "json"], default="md")
    args = ap.parse_args(argv)

    v = Vault(args.vault)
    note = v.resolve_one(args.query)
    outbound = []
    for target in v.links_of(note):
        hits = [c["rel"] for c in v.resolve(target)]
        outbound.append({"target": target, "resolved": hits, "unresolved": not hits, "ambiguous": len(hits) > 1})
    result = {"vault": str(v.root), "note": note["rel"], "title": note["stem"], "outbound_count": len(outbound),
              "unresolved_count": sum(o["unresolved"] for o in outbound), "outbound": outbound}
    if not args.no_backlinks:
        back = [b["rel"] for b in v.backlinks(note)]
        result.update(backlink_count=len(back), backlinks=back)

    if args.format == "json":
        print(json.dumps(result, indent=1))
        return 0
    print(f"# {result['title']}\n\n`{result['note']}`\n")
    print(f"## Forward links ({result['outbound_count']}, {result['unresolved_count']} unresolved)\n")
    if outbound:
        print("| Target | Resolves to |\n|---|---|")
        for o in outbound:
            dest = "**UNRESOLVED**" if o["unresolved"] else (
                "AMBIGUOUS: " + ", ".join(o["resolved"]) if o["ambiguous"] else o["resolved"][0])
            print(f"| {o['target']} | {dest} |")
    else:
        print("None.")
    if "backlinks" in result:
        print(f"\n## Backlinks ({result['backlink_count']})\n")
        print("\n".join(f"- {b}" for b in result["backlinks"]) or "None.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
