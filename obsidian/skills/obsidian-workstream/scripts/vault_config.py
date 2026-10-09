"""Print the owner's vault settings and whether each one points at something real.

Skills run this first so they know where the vault, the inbox and the owner's vault rules
are, and stop with a plain message when one is missing, instead of guessing a path.

Input: nothing (reads vault_dir, vault_inbox, vault_private_dirs and vault_rules from the
owner's settings). Prints JSON with each value, its resolved path and a list of problems.
Exit 0 when the vault and inbox are usable; exit 2 otherwise.

    python3 ~/.claude/skills/obsidian-workstream/scripts/vault_config.py
"""

import argparse
import json
from pathlib import Path

from _common import settings


def check():
    conf = settings()
    out = {"vault_dir": conf.get("vault_dir"), "vault_inbox": conf.get("vault_inbox"),
           "vault_private_dirs": conf.get("vault_private_dirs", []), "vault_rules": conf.get("vault_rules"),
           "inbox_path": None, "problems": []}
    if not out["vault_dir"]:
        out["problems"].append("vault_dir is not set")
    else:
        root = Path(out["vault_dir"]).expanduser()
        if not root.is_dir():
            out["problems"].append(f"vault_dir {root} is not a folder")
        elif not out["vault_inbox"]:
            out["problems"].append("vault_inbox is not set, so nothing may be written to the vault")
        else:
            inbox = root / out["vault_inbox"]
            out["inbox_path"] = str(inbox)
            if not inbox.is_dir():
                out["problems"].append(f"the inbox folder {inbox} does not exist")
    if out["vault_rules"] and not Path(out["vault_rules"]).expanduser().is_file():
        out["problems"].append(f"vault_rules {out['vault_rules']} is not a file")
    return out


def main(argv=None):
    argparse.ArgumentParser(description="Show the owner's vault settings and their problems.").parse_args(argv)
    out = check()
    print(json.dumps(out, indent=1))
    blocking = [p for p in out["problems"] if not p.startswith("vault_rules")]
    return 2 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
