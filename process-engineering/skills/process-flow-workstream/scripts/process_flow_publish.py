"""Write a session's staged process folder back to the engagement, and its drafts to the
delivery folder, never overwriting anyone's file.

    process_flow_publish.py WORK [--dry-run-if true|false] [--format text|json]

WORK is the staged folder process_flow_prepare.py wrote and the session worked in; this runs
after the session. engagement.json says where the process folder and the delivery folder are,
and what each staged state file hashed to when it was staged.

Into the process folder (process-flows/<process>/ in the working folder):
- a file the session created is copied in; if a file of that name appeared there meanwhile, the
  session's copy goes in beside it as 'name (2).ext';
- the kept state files (sources.json, CLAIM-LEDGER.csv, STATUS.md, LOG.md, inventories/ and
  sources/) are replaced only when the folder's copy is still the one that was staged; if a
  person changed it meanwhile, the session's copy goes in beside it;
- any other staged file the session changed (a map, a render, a review: written once) is held
  back and reported;
- the rules file, BACKGROUND.md, REFERENCE-MODEL.md, engagement.json, returns/ and scratch/ stay
  in the Run folder.

Into the delivery folder: the current map version's renders, narrative and verification memo,
each only when no file of that name holds the same content there (a different file of that
name gets 'name (2).ext'). Folders below the delivery anchor are created as needed; the anchor
itself never is, and when it has gone the drafts are held back. Nothing is deleted anywhere.

--dry-run-if true writes nothing outside WORK and writes publish-dry-run.json; otherwise
publish.json records what was done. Exit 0 when everything was written, 1 when something was
held back (listed), 2 on a bad argument.

Example:
    python3 process_flow_publish.py runs/2026-10-06/work --dry-run-if true
"""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import _common as C

STATE_FILES = {C.SOURCES_FILE, C.LEDGER_FILE, "STATUS.md", "LOG.md", "inventories/added.json"}
STAY = {C.STAGED_MARKER, C.RULES_FILE, C.BACKGROUND_FILE, "REFERENCE-MODEL.md", "publish.json", "publish-dry-run.json"}
STAY_DIRS = ("returns", "scratch")


def plan(work):
    meta = C.read_json(work / C.STAGED_MARKER, {}) or {}
    if not meta.get("process_dir"):
        raise C.EngagementError("engagement.json names no process folder")
    pdir = Path(meta["process_dir"])
    state = meta.get("state") or {}
    writes, held, deliver = [], [], []
    for p in sorted(work.rglob("*")):
        rel = p.relative_to(work).as_posix()
        if not p.is_file() or rel in STAY or rel.split("/")[0] in STAY_DIRS or rel.endswith(".tmp"):
            continue
        sha, dest = C.sha256_file(p), pdir / rel
        if rel not in state:
            if not dest.exists():
                writes.append({"from": rel, "to": str(dest), "why": "new"})
            elif C.sha256_file(dest) != sha:
                writes.append({"from": rel, "to": str(C.free_name(dest)), "why": "new; a file of that name appeared meanwhile"})
        elif sha != state[rel]:
            if rel in STATE_FILES or rel.startswith(("sources/", "inventories/")):
                if not dest.exists() or C.sha256_file(dest) == state[rel]:
                    writes.append({"from": rel, "to": str(dest), "why": "updated state file"})
                else:
                    writes.append({"from": rel, "to": str(C.free_name(dest)), "why": "a person changed it meanwhile; written beside"})
            else:
                held.append({"file": rel, "why": "a written-once file was changed in the session; write a new version instead"})
    delivery, anchor = meta.get("delivery"), meta.get("delivery_anchor")
    v, _ = C.latest(work / "maps", "map v{v}.json")
    if delivery and v and anchor and not Path(anchor).is_dir():
        held.append({"file": f"map v{v} drafts", "why": f"the delivery anchor {anchor} does not exist; "
                     "no folder is created in its place"})
    elif delivery and v:
        process = meta.get("process") or "process"
        picks = sorted((work / "renders").glob(f"{process} v{v} *")) if (work / "renders").is_dir() else []
        if (work / f"VERIFICATION v{v}.md").is_file():
            picks.append(work / f"VERIFICATION v{v}.md")
        for p in picks:
            dest = Path(delivery) / (p.name if p.parent.name == "renders" else f"{process} {p.name}")
            if dest.exists():
                if C.sha256_file(dest) == C.sha256_file(p):
                    continue
                dest = C.free_name(dest)
            deliver.append({"from": p.relative_to(work).as_posix(), "to": str(dest)})
    return {"process_dir": str(pdir), "delivery": delivery, "delivery_basis": meta.get("delivery_basis"),
            "map_version": v, "writes": writes, "held": held, "deliver": deliver}


def publish(work, dry_run):
    p = plan(work)
    p["dry_run"] = dry_run
    p["at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if not dry_run:
        for w in p["writes"] + p["deliver"]:
            dest = Path(w["to"])
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".tmp")
            shutil.copy2(work / w["from"], tmp)
            tmp.replace(dest)
    C.write_json(work / ("publish-dry-run.json" if dry_run else "publish.json"), p)
    return p


def main(argv=None):
    p = argparse.ArgumentParser(description="Write the session's process folder back and its drafts to the delivery folder.")
    p.add_argument("work", help="The staged process folder")
    p.add_argument("--dry-run-if", dest="dry_run_if", default="", help="true: write nothing outside WORK")
    p.add_argument("--format", dest="fmt", choices=["text", "json"], default="text")
    a = p.parse_args(argv)
    work = Path(a.work).expanduser()
    try:
        if not C.is_staged(work):
            raise C.EngagementError(f"{work} is not a staged process folder (no {C.STAGED_MARKER})")
        r = publish(work, a.dry_run_if.strip().lower() in ("1", "true", "yes", "on"))
    except C.EngagementError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    if a.fmt == "json":
        print(json.dumps(r, indent=1))
    else:
        print(f"{'WOULD WRITE' if r['dry_run'] else 'WROTE'} {len(r['writes'])} file(s) to {r['process_dir']}, "
              f"{len(r['deliver'])} draft(s) to {r['delivery'] or 'no delivery folder'}; held back {len(r['held'])}")
        for x in r["writes"] + r["deliver"]:
            print(f"  {x['from']} -> {x['to']}")
        for h in r["held"]:
            print(f"  HELD {h['file']}: {h['why']}")
    return 1 if r["held"] else 0


if __name__ == "__main__":
    sys.exit(main())
