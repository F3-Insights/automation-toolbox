#!/usr/bin/env python3
"""chief-of-staff-receipt: the day's receipt note and the decision tasks, written by marker
and read back.

    read CYCLE_DIR                 the day's receipt note, if there is one
    publish CYCLE_DIR [--dry-run]  write the receipt (receipt.json) and its decisions
    verify CYCLE_DIR               is the note in the Portal; how many decisions were raised

The rules, enforced here rather than asked for:
- One receipt note a day, titled "<name> Receipt YYYY-MM-DD" however many cycles run, <name>
  the setting display_name (default Chief of Staff); a note already written today under a
  former name (setting former_names) is the one appended to. The first cycle creates it,
  anchored to the owner's own contact; every later cycle appends its block. Each cycle's
  text ends with a marker, <!-- chief-of-staff:cycle:<date>/<cycle> -->, found before anything
  is written, so a re-run writes nothing twice. The update carries the note's updated_at, so
  an edit made in between is not overwritten.
- The Portal is a shared surface: content holding an absolute local path or an em dash is
  refused, so the writer is asked again.
- Decision tasks only for genuine decisions, titled "[<name>] ...", owned by the token's own
  contact (from whoami), due the cycle's date. An open task with the same title, or with this
  decision's marker (chief-of-staff:decision:<date>:<key>), is reused. At most three a day
  across all cycles, counted in the token's own timezone. One task that fails never stops
  the rest; when the day's tasks cannot be listed, none is created.
- A proposed improvement (improve.json says proposed) is filed as one more decision task,
  inside the same ceiling.

`verify` is the check that counts: the model saying "created" is a claim; the Portal holding
the note is evidence. It finds the note by exact title and counts decision tasks created
since the cycle started, the only record a decision alert may be sent on.

Each command writes its result beside cycle.json (receipt-read.json, publish.json,
verify.json). A dry run (--dry-run, or a dry-run cycle) writes nothing to the Portal; with
F3I_TOOLBOX_DRY_RUN set, a publish without --dry-run is refused. Exit 0 to go on, 3 for a
refusal or a missing note, 2 when it could not run.

Example:
    python3 chief_of_staff_receipt.py verify ~/state/chief-of-staff/cycles/2030-03-04/061500
"""

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import _common as c

MAX_DECISIONS_PER_DAY = 3
EM_DASH = "\u2014"
TITLE_MAX = 200


def _cycle(folder):
    cycle = c.read_json(Path(folder) / "cycle.json")
    if not isinstance(cycle, dict) or not cycle.get("date"):
        raise c.Bad(f"{folder} holds no cycle.json")
    return cycle


def mark_for(cycle):
    return c.CYCLE_MARK.format(cycle_id=cycle["cycle_id"])


def load_receipt(folder):
    path = Path(folder) / "receipt.json"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        raise c.Bad(f"{path.name} is missing: save the writer's reply there first") from None
    value = c.load_object(text)
    if not value or not str(value.get("content") or "").strip():
        raise c.Bad("receipt.json holds no JSON object with content")
    return value


def content_problems(text):
    problems = []
    if EM_DASH in text:
        problems.append("EM_DASH: the receipt holds an em dash")
    path = c.local_path_in(text)
    if path:
        problems.append(f"LOCAL_PATH: the receipt names a local path ({path[:60]}); private paths stay in local files")
    return problems


def decision_key(title):
    """The title's key without its prefix, so it survives a change of display name."""
    bare = c.strip_decision_prefix(title).lower()
    return hashlib.sha256(" ".join(bare.split()).encode()).hexdigest()[:10]


def normal_title(title):
    return f"{c.decision_prefix()} {c.strip_decision_prefix(title)}"[:TITLE_MAX]


def _local_day(value, tz):
    when = c.parse_time(value)
    return when.astimezone(tz).date().isoformat() if when else ""


def _who(client):
    who = c.principal(client)
    if not who.get("contact_id"):
        raise c.Bad("whoami returned no contact_id for this token")
    try:
        tz = ZoneInfo(str(who.get("timezone") or "UTC"))
    except Exception:  # an unknown zone falls back to UTC
        tz = ZoneInfo("UTC")
    return {"contact_id": str(who["contact_id"]), "tz": tz}


def read(client, folder):
    cycle = _cycle(folder)
    note = c.find_receipt(client, cycle["date"])
    out = {"status": "found" if note else "absent", "title": (note or {}).get("title") or c.receipt_title(cycle["date"]),
           "note_id": (note or {}).get("id"), "content": (note or {}).get("content") or "",
           "this_cycle_written": bool(note) and mark_for(cycle) in str(note.get("content") or "")}
    c.atomic_json(Path(folder) / "receipt-read.json", out)
    return out


def _publish_note(client, cycle, content, who, dry):
    title, mark = c.receipt_title(cycle["date"]), mark_for(cycle)
    block = content.strip() + "\n\n" + mark
    note = c.find_receipt(client, cycle["date"])
    if note and mark in str(note.get("content") or ""):
        return {"action": "already", "note_id": note.get("id")}
    if dry:
        return {"action": "would_append" if note else "would_create", "note_id": (note or {}).get("id"),
                "title": title, "chars": len(block)}
    if not note:
        made = client.call("create_note", {
            "title": title, "content": block,
            "associations": [{"entity_type": "contact", "entity_id": who["contact_id"], "is_primary": True}]})
        if not isinstance(made, dict) or not made.get("id"):
            raise c.Bad(f"create_note returned no id ({c.flat(made, 160)})")
        return {"action": "created", "note_id": made["id"]}
    args = {"id": note["id"], "fields": {"content": str(note.get("content") or "").rstrip() + "\n\n" + block}}
    if note.get("updated_at"):
        args["expected_updated_at"] = note["updated_at"]
    out = client.call("update_note", args)
    if isinstance(out, dict) and out.get("success") is False:
        raise c.Bad(f"update_note refused ({c.flat(out, 160)})")
    return {"action": "appended", "note_id": note["id"]}


def _create_task(client, fields, domain):
    args = {k: v for k, v in fields.items() if v is not None}
    try:
        made = client.call("create_task", {**args, **({"domain_id_or_name": domain} if domain else {})})
    except c.Bad:
        if not domain:
            raise
        made = client.call("create_task", args)  # an unknown domain name files it unfiled, not lost
    return made if isinstance(made, dict) else {}


def _publish_decisions(client, cycle, decisions, who, dry):
    day, results = cycle["date"], []
    if not decisions:
        return results
    try:
        all_rows = c.decision_tasks(client, include_completed=True)
    except c.Bad as exc:
        why = f"could not count the day's tasks, so none was created ({c.safe(exc)[:120]})"
        return [{"action": "failed", "title": normal_title(item["title"]) if isinstance(item, dict)
                 and str(item.get("title") or "").strip() else "", "reason": why} for item in decisions[:10]]
    open_rows = [r for r in all_rows if str(r.get("status") or "").upper() not in ("DONE", "CANCELLED", "CANCELED")]
    today = sum(1 for r in all_rows if _local_day(r.get("created_at"), who["tz"]) == day)
    for item in decisions[:10]:
        if not isinstance(item, dict) or not str(item.get("title") or "").strip():
            results.append({"action": "invalid", "reason": "a decision needs a title"})
            continue
        title = normal_title(item["title"])
        marker = c.DECISION_MARKER.format(date=day, key=decision_key(title))
        same = [r for r in open_rows if r.get("source_reference") == marker
                or normal_title(r.get("title") or "").lower() == title.lower()]
        if same:
            results.append({"action": "reused", "title": title, "task_id": same[0].get("id")})
            continue
        if today >= MAX_DECISIONS_PER_DAY:
            results.append({"action": "capped", "title": title,
                            "reason": f"{today} decision tasks already raised on {day}; the ceiling is "
                                      f"{MAX_DECISIONS_PER_DAY} a day across all cycles"})
            continue
        if dry:
            results.append({"action": "would_create", "title": title, "marker": marker})
            today += 1
            continue
        desc = c.flat(item.get("description"), 3000)
        fields = {"title": title, "description": f"{desc}\n\nMarker: {marker}".strip(),
                  "priority": item.get("priority") if item.get("priority") in (1, 2, 3, 4) else 2,
                  "owner_contact_id": who["contact_id"], "due_date": day, "source_reference": marker}
        try:
            made = _create_task(client, fields, c.flat(item.get("domain"), 120))
            if not made.get("id"):
                raise c.Bad(f"create_task returned no id ({c.flat(made, 160)})")
            results.append({"action": "created", "title": title, "task_id": made["id"], "marker": marker})
            open_rows.append({"id": made["id"], "title": title, "source_reference": marker})
            today += 1
        except c.Bad as exc:
            results.append({"action": "failed", "title": title, "reason": c.safe(exc)[:200]})
    return results


def proposed_improvement(folder):
    """The cycle's improvement as a decision, when it was proposed rather than applied."""
    imp = c.read_json(Path(folder) / "improve.json") or {}
    if imp.get("status") != "proposed" or not imp.get("target"):
        return None
    change = c.flat(str(imp.get("change") or "").replace(EM_DASH, "-"), 600)
    why = c.flat(str(imp.get("rationale") or "").replace(EM_DASH, "-"), 300)
    desc = (f"Proposed change to the {imp['target']} skill's SKILL.md: {change}\nWhy: {why}\n"
            "Apply it, or mark this task done to drop it.")
    if c.local_path_in(desc):
        desc = f"Proposed change to the {imp['target']} skill's SKILL.md; the details are in the cycle's improve.json."
    return {"title": f"Improve {imp['target']}: {change[:80]}", "description": desc, "priority": 3}


def publish(client, folder, dry_run=False):
    cycle = _cycle(folder)
    dry = dry_run or bool(cycle.get("dry_run"))
    forced = c.dry_run_forced(dry)
    if forced:
        return {"status": "refused", "reason": forced, "dry_run": True}
    receipt = load_receipt(folder)
    content = str(receipt["content"])
    problems = content_problems(content + "\n" + json.dumps(receipt.get("decisions") or [], ensure_ascii=False))
    if problems:
        out = {"status": "refused", "codes": [p.split(":", 1)[0] for p in problems], "problems": problems}
        c.atomic_json(Path(folder) / "publish.json", out)
        return out
    who = _who(client)
    note = _publish_note(client, cycle, content, who, dry)
    decisions = list(receipt.get("decisions")) if isinstance(receipt.get("decisions"), list) else []
    proposal = proposed_improvement(folder)
    if proposal:
        decisions.append(proposal)
    tasks = _publish_decisions(client, cycle, decisions, who, dry)
    verified = None
    if not dry:
        back = c.find_receipt(client, cycle["date"])
        verified = bool(back) and mark_for(cycle) in str(back.get("content") or "")
    out = {"status": "dry_run" if dry else ("published" if verified else "unverified"), "note": note,
           "tasks": tasks, "verified": verified, "dry_run": dry}
    c.atomic_json(Path(folder) / "publish.json", out)
    return out


def verify(client, folder):
    cycle = _cycle(folder)
    since = c.parse_time(cycle.get("started_at"))
    try:
        note = c.find_receipt(client, cycle["date"])
        rows = c.decision_tasks(client, include_completed=False)
    except c.Bad as exc:
        out = {"status": "unverified", "reason": f"could not verify against the Portal ({c.safe(exc)[:120]})"}
        c.atomic_json(Path(folder) / "verify.json", out)
        return out
    floor = datetime.min.replace(tzinfo=since.tzinfo) if since else None
    new = [r for r in rows if since and (c.parse_time(r.get("created_at")) or floor) >= since]
    out = {"status": "found" if note else "missing", "note_id": (note or {}).get("id"),
           "title": (note or {}).get("title") or c.receipt_title(cycle["date"]),
           "this_cycle_written": bool(note) and mark_for(cycle) in str((note or {}).get("content") or ""),
           "decisions_created": len(new), "first_decision": (new[0].get("title") if new else ""),
           "decision_ids": [r.get("id") for r in new],
           "open_decisions": [{"task_id": r.get("id"), "title": r.get("title")} for r in rows]}
    if not note:
        out["reason"] = f"receipt note {c.receipt_title(cycle['date'])!r} is not in the Portal"
    c.atomic_json(Path(folder) / "verify.json", out)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description="The day's receipt note and decision tasks. One JSON object out.")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("read", "publish", "verify"):
        s = sub.add_parser(name)
        s.add_argument("cycle_dir")
        s.add_argument("--config", default=None, help="MCP config holding the Portal (default: setting portal_mcp_config)")
        s.add_argument("--server", default=None)
        if name == "publish":
            s.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    try:
        folder = c.cycle_dir(args.cycle_dir)  # the inputs first, the Portal after
        client = c.Portal(args.config, args.server)
        if args.cmd == "read":
            c.emit(read(client, folder), c.OK)
        if args.cmd == "publish":
            out = publish(client, folder, args.dry_run)
            c.emit(out, c.STOP if out["status"] in ("refused", "unverified") else c.OK)
        out = verify(client, folder)
    except c.Bad as exc:
        c.fail(str(exc))
    c.emit(out, {"found": c.OK, "missing": c.STOP}.get(out["status"], c.ERROR))


if __name__ == "__main__":
    main()
