#!/usr/bin/env python3
"""Create the standard folder set for a client engagement.

    <root>/<Client> - General/                 kickoff and workshop materials, transcripts
    <root>/<Client> - YYYY-MM <Workstream>/    one per workstream, with the standard subfolders

The default workstream subfolders are From Client, Shared with Client, Transcripts,
Consultant Transcripts, Weekly Report and Kick off Material. "From Client" and "Shared with
Client" are the two directions of the client boundary, so "what have they seen" has one
answer. With --repo-root it also creates a sibling working repo, <prefix>-<client-slug>/,
with docs/, research/ and mock/ and a docs/RUNBOOK.md of the eight engagement steps.

Inputs: the client name, --root (default: the `engagements_dir` setting) and one
--workstream per workstream. The folder names can be replaced in the owner settings, table
[project-engagement-workstream]: general_subfolders, workstream_subfolders (lists of names)
and repo_prefix (default "f3i").

Safe to run twice: existing folders are left alone and reported. Nothing is ever deleted.
Prints what it created (or with --dry-run what it would create), as text or --format json.
A client, workstream or subfolder name must be one folder name (no slash, not "..").
Exit 0 ok, 2 on a bad argument or missing setting.

Example:
  python3 engagement_folders.py "Acme Components" --workstream "Proposal Workflow" --dry-run --format json
"""

import argparse
import json
import os
import re
import sys
import tomllib
from datetime import date
from pathlib import Path

GENERAL_SUBDIRS = ["Kick off and Workshop Materials", "Transcript"]
WORKSTREAM_SUBDIRS = ["From Client", "Shared with Client", "Transcripts", "Consultant Transcripts",
                      "Weekly Report", "Kick off Material"]
REPO_SUBDIRS = ["docs", "research", "mock"]

RUNBOOK = """# Engagement runbook: {client}

Generated {today} by `engagement-folders`. Tick each step as its deliverable lands.
The method and the maker for each step are in the `project-engagement-runbook` skill.

- [ ] 1. Sponsor prep: `collected-ideas.csv`, internal prep brief, hours Pareto if data arrives
- [ ] 2. Discovery workshop: facilitation plan, live impact/effort deck, summary within 3 business days
- [ ] 3. Contract: MSA, Exhibit A, SOW; red-teamed; thank-you note same day
- [ ] 4. Post-signature: IT one-to-one, sponsor framing note, all-staff announcement, interview invites
- [ ] 5. Kickoff deck per workstream plus build-method brief
- [ ] 6. Interviews collapsed and synthesized: Read-Out, Feedback by Topic, baseline, concept
- [ ] 7. Weekly client updates; findings readout to sponsors before executives
- [ ] 8. IT asks list, then build waves behind human approval

## Workstreams

{workstreams}
"""


def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def bad_name(name):
    """Why a client, workstream or subfolder name cannot be one folder inside root, or None."""
    if not isinstance(name, str) or not name.strip():
        return f"{name!r} is not a folder name"
    if "/" in name or "\\" in name or name.strip() in (".", ".."):
        return f"{name!r} is not a single folder name; it would place folders outside the root"
    return None


def plan(root, client, workstreams, month, repo_root=None, repo_prefix="f3i", general=None, per_workstream=None):
    """Every folder to exist, in order, and the runbook path (or None)."""
    general = general or GENERAL_SUBDIRS
    per_workstream = per_workstream or WORKSTREAM_SUBDIRS
    folders = [root / f"{client} - General" / s for s in general]
    for ws in workstreams:
        folders += [root / f"{client} - {month} {ws}" / s for s in per_workstream]
    runbook = None
    if repo_root:
        repo = Path(repo_root).expanduser() / f"{repo_prefix}-{slug(client)}"
        folders += [repo / s for s in REPO_SUBDIRS]
        runbook = repo / "docs" / "RUNBOOK.md"
    return folders, runbook


def create(folders, runbook, client, month, workstreams):
    made, existed = [], []
    for f in folders:
        (existed if f.exists() else made).append(str(f))
        f.mkdir(parents=True, exist_ok=True)
    if runbook:
        if runbook.exists():
            existed.append(str(runbook))
        else:
            lines = "\n".join(f"- {month} {w}" for w in workstreams) or "- (none yet)"
            runbook.write_text(RUNBOOK.format(client=client, today=date.today().isoformat(), workstreams=lines),
                               encoding="utf-8")
            made.append(str(runbook))
    return made, existed


def main(argv=None):
    ap = argparse.ArgumentParser(description="Create the standard engagement folder set.")
    ap.add_argument("client")
    ap.add_argument("--root", default="", help="parent folder (default: the engagements_dir setting)")
    ap.add_argument("--workstream", dest="workstreams", action="append", default=[],
                    help="workstream name; repeat for several")
    ap.add_argument("--month", default="", help="YYYY-MM for workstream folders (default: this month)")
    ap.add_argument("--repo-root", default="", help="also create <prefix>-<client-slug>/ here with a RUNBOOK.md")
    ap.add_argument("--repo-prefix", default="", help="prefix for the working repo (default: repo_prefix setting, else f3i)")
    ap.add_argument("--dry-run", action="store_true", help="print what would be created")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    args = ap.parse_args(argv)

    own = settings("project-engagement-workstream")
    root_text = args.root or settings().get("engagements_dir") or ""
    if not root_text:
        print("pass --root or set engagements_dir in the owner settings", file=sys.stderr)
        return 2
    root = Path(root_text).expanduser()
    if not root.is_dir():
        print(f"root is not a directory: {root}", file=sys.stderr)
        return 2
    month = args.month or date.today().strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        print("--month must be YYYY-MM", file=sys.stderr)
        return 2
    general, per_workstream = own.get("general_subfolders"), own.get("workstream_subfolders")
    for names in (general, per_workstream):
        if names is not None and not isinstance(names, list):
            print("general_subfolders and workstream_subfolders must be lists of folder names", file=sys.stderr)
            return 2
    for name in [args.client, *args.workstreams, *(general or []), *(per_workstream or [])]:
        if bad_name(name):
            print(bad_name(name), file=sys.stderr)
            return 2
    folders, runbook = plan(root, args.client, args.workstreams, month, args.repo_root or None,
                            args.repo_prefix or own.get("repo_prefix") or "f3i",
                            general, per_workstream)

    if args.dry_run:
        result = {"dry_run": True, "planned": [str(f) for f in folders], "runbook": str(runbook) if runbook else None}
        if args.format == "json":
            print(json.dumps(result, indent=1))
        else:
            print("Would create:")
            for f in result["planned"]:
                print(f"  {f}")
        return 0

    made, existed = create(folders, runbook, args.client, month, args.workstreams)
    result = {"client": args.client, "month": month, "workstreams": args.workstreams, "created": made,
              "already_existed": existed, "repo": str(runbook.parent.parent) if runbook else None,
              "runbook": str(runbook) if runbook else None}
    if args.format == "json":
        print(json.dumps(result, indent=1))
        return 0
    print(f"Created {len(made)}, already existed {len(existed)}.")
    for f in made:
        print(f"  + {f}")
    for f in existed:
        print(f"  = {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
