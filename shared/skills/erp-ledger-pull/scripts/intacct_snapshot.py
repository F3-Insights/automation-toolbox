#!/usr/bin/env python3
"""Pull one period plus a trailing baseline from Sage Intacct into gated JSON snapshots.

Use it for a pull outside a Month-End folder; inside one, month_end_pull.py does the same and
keeps the folder in order.

Inputs: --period, --out, and either --live (query Intacct, read only) or --snapshot-dir (read
files a person exported, offline). --config names a JSON file of settings: "objects" (field
list overrides per object), "fetch_objects", "baseline_months" (default 6), "max_skew_hours",
"known_creators", "known_journals", "snapshot_files", "require_server_counts", "environment",
"client" (a label written into the manifest).

Objects: JE headers, JE lines, AP bill lines, next-month AP bill lines, AR invoice lines,
budget detail. An object exported as several files is merged into one, deduplicated on its
`id`, and its pull time is the oldest of the parts.

Gates, each a finding with a severity: counts_tie (rows equal the server's total; no total is
"unverifiable"), one_vintage (every object pulled within max_skew_hours), lines_have_headers
(every JE line has a header, unless its creator or journal is a known integration).

Writes the snapshots and manifest.json into --out and prints a summary, or the manifest with
--format json. Exit 0 when every gate passes, 1 when one fails, 2 on a bad argument or
missing credentials.

Example:
    python3 intacct_snapshot.py --period 2026-08 --out ./snap --snapshot-dir ./export
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _common import (OBJECTS, IntacctError, IntacctSession, NoCredentials, credentials, gate_snapshot,
                     load_snapshot, pull_live, resolve_sources, server_total, shift_period,
                     write_snapshot)


def merge_sources(spec, paths):
    """Several extracts of one object as one snapshot: rows deduplicated on `id`, the pull
    time the oldest of the parts (the stalest row is the one that matters)."""
    rows, seen, pulled, totals, duplicates = [], set(), [], [], 0
    for path in paths:
        part, meta = load_snapshot(path)
        if meta.get("pulled-at"):
            pulled.append(str(meta["pulled-at"]))
        totals.append(server_total(meta))
        for row in part:
            key = str(row.get("id") or "")
            if key and key in seen:
                duplicates += 1
                continue
            seen.add(key)
            rows.append(row)
    meta = {"pulled-at": min(pulled) if pulled else "", "object": spec["object"], "row-count": len(rows),
            "merged-from": [str(p) for p in paths], "duplicates-dropped": duplicates, "dedupe-key": "id"}
    if totals and None not in totals:
        meta["server-total-count"] = sum(totals) - duplicates
    return rows, meta


def read_snapshot_dir(directory, out_dir, specs, named):
    if not directory.is_dir():
        raise ValueError(f"--snapshot-dir must be an existing folder of JSON snapshots (got '{directory}')")
    found = []
    for name, spec in specs.items():
        paths = resolve_sources(directory, name, named)
        if not paths:
            continue
        if len(paths) == 1:
            rows, meta = load_snapshot(paths[0])
            source = paths[0]
        else:
            rows, meta = merge_sources(spec, paths)
            source = write_snapshot(out_dir / f"{name.replace('_', '-')}-merged.json", rows, meta)
        found.append({"name": name, "object": str(meta.get("object") or spec["object"]), "source": str(source),
                      "sources": [str(p) for p in paths], "rows": len(rows), "server_total": server_total(meta),
                      "pulled_at": str(meta.get("pulled-at") or "")})
    if not found:
        raise ValueError(f"no snapshots found in {directory}")
    return found


def snapshot(period, out, snapshot_dir="", live=False, config=None, session=None):
    """Pull or read the objects, gate them, write manifest.json. Returns the manifest."""
    cfg = dict(config or {})
    out_dir = Path(out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    specs = {name: {**spec, **dict((cfg.get("objects") or {}).get(name) or {})} for name, spec in OBJECTS.items()}
    baseline = int(cfg.get("baseline_months", 6))
    if live:
        objects = pull_live(session, period, baseline, out_dir, specs, cfg.get("fetch_objects"),
                            str(cfg.get("environment", "PROD")))
        counts_required, mode = bool(cfg.get("require_server_counts", True)), "live"
    else:
        objects = read_snapshot_dir(Path(snapshot_dir).expanduser(), out_dir, specs,
                                    dict(cfg.get("snapshot_files") or {}))
        counts_required, mode = bool(cfg.get("require_server_counts", False)), "snapshot"
    findings = gate_snapshot(objects, float(cfg.get("max_skew_hours", 1.0)), counts_required,
                             cfg.get("known_creators") or (), cfg.get("known_journals") or ())
    errors = sum(1 for f in findings if f["severity"] == "error")
    manifest = {
        "client": str(cfg.get("client", "")), "period": period, "prior_period": shift_period(period, -1),
        "mode": mode, "snapshot_dir": snapshot_dir, "baseline_months": baseline, "objects": objects,
        "findings": findings, "errors": errors, "passed": errors == 0,
        "summary": f"{period} {mode} fetch: " + ", ".join(f"{o['name']} {o['rows']:,}" for o in objects),
    }
    path = out_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    manifest["manifest_path"] = str(path)
    return manifest


def main(argv=None):
    p = argparse.ArgumentParser(description="Pull a period from Intacct into gated JSON snapshots.")
    p.add_argument("--period", required=True, help="yyyy-mm")
    p.add_argument("--out", required=True, help="folder the snapshots and manifest are written to")
    p.add_argument("--snapshot-dir", default="", help="read existing snapshots from here instead of querying")
    p.add_argument("--live", action="store_true", help="query Intacct, read only (needs credentials)")
    p.add_argument("--config", default="", help="JSON file of settings (see the docstring)")
    p.add_argument("--format", default="text", choices=["text", "json"])
    args = p.parse_args(argv)
    if not args.live and not args.snapshot_dir:
        print("ERROR: pass --snapshot-dir (offline) or --live", file=sys.stderr)
        return 2
    try:
        cfg = json.loads(Path(args.config).read_text(encoding="utf-8")) if args.config else {}
        if not isinstance(cfg, dict):
            raise ValueError(f"{args.config}: the config must be a JSON object")
        session = None
        if args.live:
            session = IntacctSession(*credentials(str(cfg.get("environment", "PROD"))))
        result = snapshot(args.period, args.out, args.snapshot_dir, args.live, cfg, session)
    except NoCredentials as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError, IntacctError) as exc:
        print(f"ERROR: {str(exc).splitlines()[0]}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(result, indent=1))
    else:
        print(result["summary"])
        for o in result["objects"]:
            print(f"  {o['name']:20} {o['rows']:>8,} rows  server={o['server_total']}  {o['pulled_at'][:19]}")
        for f in result["findings"]:
            print(f"  {f['severity'].upper():7} {f['gate']:20} {f['object']:16} {f['detail']}")
        print("PASS" if result["passed"] else "FAIL")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
