#!/usr/bin/env python3
"""chief-of-staff-records: the three writes to the owner's own records the receipt may make,
applied in code.

    apply CYCLE_DIR [--dry-run]

The receipt writer proposes them in receipt.json; this applies only these, each to a file a
setting names, and nothing else is reachable from here:
- The doer roster (setting doer_roster). For each doer dispatched this cycle (execution.json),
  the Health cell (the last column) of its one row in the "## Active doers" table is replaced,
  and the Trust cell (the column before it) only when a valid rung is given (OBSERVE,
  PROPOSE, TRUSTED). No rows are added or removed and no other section is touched. A doer that
  matches no row, or more than one, is reported and skipped.
- The event ledger (setting event_ledger). At most one line per cycle, in the ledger's
  format "- YYYY-MM-DD | <name> | event (ref)", <name> the display name, appended at the end.
  Existing lines are never edited, and a line already present is not written twice.
- The principles inbox (setting principles_inbox, a folder). At most one draft principle per
  cycle, as <date>-chief-of-staff-<slug>.md, written only when that file does not exist yet.

The owner's principles and profile are never written: only the owner ratifies a principle
or confirms a profile fact. A profile contradiction goes in the receipt as a question.

Each write is independent: one that fails, or whose setting is missing, is reported and the
others still run. A dry run (--dry-run, or a dry-run cycle) writes nothing; with
F3I_TOOLBOX_DRY_RUN set, a call without --dry-run is refused (exit 3). Writes records.json in
the cycle folder. Exit 0, or 2 when it could not run.

Example:
    python3 chief_of_staff_records.py apply ~/state/chief-of-staff/cycles/2030-03-04/061500
"""

import argparse
import re
from pathlib import Path

import _common as c

TRUST = ("OBSERVE", "PROPOSE", "TRUSTED")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{2,60}$")
_CELL_SPLIT = re.compile(r"(?<!\\)\|")


def journal_line(name):
    return re.compile(r"^- \d{4}-\d{2}-\d{2} \| " + re.escape(name) + r" \| \S.{4,600}$")


def _cells(line):
    return [x.strip() for x in _CELL_SPLIT.split(line.strip().strip("|"))]


def update_roster(text, doer, health, trust=None):
    """{"text": new_text} or {"error": why}. Only rows of the Active doers table count."""
    lines = text.split("\n")
    try:
        start = next(i for i, l in enumerate(lines) if l.strip().lower().startswith("## active doers"))
    except StopIteration:
        return {"error": "the roster has no Active doers section"}
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    header = next((i for i in range(start, end) if lines[i].lstrip().startswith("|")), None)
    if header is None:
        return {"error": "the Active doers section holds no table"}
    width = len(_cells(lines[header]))
    name = re.compile(rf"(?<![\w-]){re.escape(doer)}(?![\w-])", re.I)
    hits = [i for i in range(header + 2, end) if lines[i].lstrip().startswith("|") and name.search(_cells(lines[i])[0])]
    if len(hits) != 1:
        return {"error": f"{len(hits)} rows of the Active doers table name {doer!r}; expected exactly one"}
    row = _cells(lines[hits[0]])
    if len(row) != width:
        return {"error": f"the row for {doer!r} has {len(row)} cells, the table {width}"}
    row[-1] = c.flat(health, 400).replace("|", "/")
    if trust:
        row[-2] = trust
    lines[hits[0]] = "| " + " | ".join(row) + " |"
    return {"text": "\n".join(lines)}


def _file(key):
    value = c.setting(key)
    return Path(value).expanduser() if value else None


def apply(folder, dry_run=False):
    folder = Path(folder)
    cycle = c.read_json(folder / "cycle.json") or {}
    dry = dry_run or bool(cycle.get("dry_run"))
    forced = c.dry_run_forced(dry)
    if forced:
        return {"status": "refused", "reason": forced, "dry_run": True}
    raw = (folder / "receipt.json").read_text(encoding="utf-8", errors="replace") if (folder / "receipt.json").exists() else ""
    receipt = c.load_object(raw)
    if not receipt:
        raise c.Bad("receipt.json holds no JSON object")
    dispatched = {r.get("doer") for r in c.read_json(folder / "execution.json", default=[]) or []
                  if isinstance(r, dict) and r.get("status") not in ("dry-run", "skipped")}
    out = {"roster": [], "ledger": None, "principle": None, "dry_run": dry}

    updates = receipt.get("team_updates") if isinstance(receipt.get("team_updates"), list) else []
    roster = _file("doer_roster")
    if updates:
        text = roster.read_text(encoding="utf-8") if roster and roster.is_file() else None
        for u in updates:
            doer = c.flat((u or {}).get("doer"), 80) if isinstance(u, dict) else ""
            if doer not in dispatched:
                out["roster"].append({"doer": doer, "action": "skipped",
                                      "reason": "not dispatched this cycle; only dispatched doers are re-rated"})
                continue
            if text is None:
                out["roster"].append({"doer": doer, "action": "failed",
                                      "reason": "no doer roster (setting doer_roster) or it was not found"})
                continue
            trust = str(u.get("trust") or "").upper() or None
            trust = trust if trust in TRUST else None
            res = update_roster(text, doer, str(u.get("health") or ""), trust)
            if "error" in res or not str(u.get("health") or "").strip():
                out["roster"].append({"doer": doer, "action": "failed", "reason": res.get("error") or "no health text"})
                continue
            text = res["text"]
            out["roster"].append({"doer": doer, "action": "would_update" if dry else "updated",
                                  **({"trust": trust} if trust else {})})
        if not dry and text is not None and any(t["action"] == "updated" for t in out["roster"]):
            try:
                roster.write_text(text, encoding="utf-8")
            except OSError as exc:
                for t in out["roster"]:
                    if t["action"] == "updated":
                        t.update(action="failed", reason=str(exc))

    line = c.flat(receipt.get("journal"), 700) if receipt.get("journal") else ""
    if line:
        ledger = _file("event_ledger")
        name = c.display_name()
        try:
            if not journal_line(name).match(line):
                out["ledger"] = {"action": "refused", "reason": f"not in the ledger's format: - YYYY-MM-DD | {name} | event"}
            elif not ledger or not ledger.is_file():
                out["ledger"] = {"action": "failed", "reason": "no event ledger (setting event_ledger) or it was not found"}
            elif line in ledger.read_text(encoding="utf-8").split("\n"):
                out["ledger"] = {"action": "already"}
            elif dry:
                out["ledger"] = {"action": "would_append"}
            else:
                body = ledger.read_text(encoding="utf-8")
                ledger.write_text(body.rstrip("\n") + "\n" + line + "\n", encoding="utf-8")
                out["ledger"] = {"action": "appended"}
        except OSError as exc:
            out["ledger"] = {"action": "failed", "reason": str(exc)}

    draft = receipt.get("doctrine")
    if isinstance(draft, dict) and draft.get("body"):
        slug = str(draft.get("slug") or "").strip().lower()
        inbox = _file("principles_inbox")
        try:
            if not SLUG.match(slug):
                out["principle"] = {"action": "refused", "reason": "the slug is lowercase words joined by hyphens"}
            elif not inbox or not inbox.is_dir():
                out["principle"] = {"action": "failed", "reason": "no principles inbox (setting principles_inbox) or it was not found"}
            else:
                target = inbox / f"{cycle.get('date')}-chief-of-staff-{slug}.md"
                if target.exists():
                    out["principle"] = {"action": "already", "file": target.name}
                elif dry:
                    out["principle"] = {"action": "would_write", "file": target.name}
                else:
                    target.write_text(str(draft["body"]).strip() + "\n", encoding="utf-8")
                    out["principle"] = {"action": "written", "file": target.name}
        except OSError as exc:
            out["principle"] = {"action": "failed", "reason": str(exc)}

    c.atomic_json(folder / "records.json", out)
    return {"status": "applied" if not dry else "dry_run", **out}


def main(argv=None):
    p = argparse.ArgumentParser(description="The receipt's writes to the owner's roster, ledger and principles inbox.")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("apply")
    s.add_argument("cycle_dir")
    s.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    try:
        out = apply(c.cycle_dir(args.cycle_dir), args.dry_run)
    except (c.Bad, OSError) as exc:
        c.fail(str(exc))
    c.emit(out, c.STOP if out.get("status") == "refused" else c.OK)


if __name__ == "__main__":
    main()
