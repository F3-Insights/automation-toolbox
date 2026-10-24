#!/usr/bin/env python3
"""One staged cover-email draft as the reviewer reads it, with its content hash. Read only.

The reviewer's command for the client update's section Check the cover email. It runs
comms-reply-to-email's email_draft_show.py (productivity), found through this toolbox
checkout, so the content hash is computed by the same code client_update_deliver.py's
email_deliver.py compares at delivery: a draft changed after it was checked is refused there.

Prints that script's one JSON object (subject, body, recipients, the contact and email the
draft is tied to, its status and `content_hash`) and exits with its exit code: 0, or 2 on an
error. It needs the setting portal_mcp_config, as that script does.

    python3 client_update_draft_show.py 7d4e2a10-0000-4000-8000-000000000002
"""

import os
import sys

from _skill_paths import skill_file

DRAFT_SHOW = skill_file("comms-reply-to-email", "scripts", "email_draft_show.py")


def argv(args: list[str]) -> list[str]:
    return [sys.executable, str(DRAFT_SHOW), *args]


def main() -> int:
    args = sys.argv[1:]
    if args[:1] in (["-h"], ["--help"]):
        print(__doc__.strip())
        return 0
    if not DRAFT_SHOW.is_file():
        print(f"email_draft_show.py (comms-reply-to-email) is not in this toolbox checkout: {DRAFT_SHOW}",
              file=sys.stderr)
        return 2
    os.execv(sys.executable, argv(args))
    return 2  # not reached


if __name__ == "__main__":
    sys.exit(main())
