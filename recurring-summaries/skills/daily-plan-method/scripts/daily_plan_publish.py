#!/usr/bin/env python3
"""daily-plan-publish: write the day's plan note in the Insights Portal, once per pass, by marker.

Reads RUN/plan.json (the contract in _common.py), renders the pass's block to RUN/plan.md and
writes the day's note, "Daily Plan - <date>":
  - no note yet: one is created with the block, tagged briefing and daily-plan (default),
    attached to the owner's contact and, with --domain, that domain, then set PRIVATE. The
    Portal creates notes public, so a failure between the two calls is reported NOT_PRIVATE
    and the next run makes it private;
  - a note with no block for the pass: the block is added (the morning before the evening);
  - a block this script wrote and nobody changed since (its hash matches the state copy):
    replaced in place;
  - a block someone edited, or one with no record here: kept, and the new block is appended
    after it with the time in its heading, so nothing a person wrote is lost.
Every write is read back (title, day marker, the block's hash, PRIVATE). The state folder
(--state or <state_dir>/daily-plan) then keeps <date>/<pass>.json, a copy of the plan with
the note id and block hash, which the evening pull and the check read.

A dry run reads the Portal, writes RUN/plan.md and RUN/publish-dry-run.json, and writes
nothing to the Portal or the state folder. A plan saying "dry_run": true is refused DRY_RUN
without --dry-run.

Prints one JSON object. Exit 0 (created, added, replaced, appended, unchanged, or would_...
on a dry run), 3 when refused or not verified (NO_PLAN, DRY_RUN, NOT_VERIFIED, NOT_PRIVATE),
2 on an error.

Example:
  python3 daily_plan_publish.py --date 2030-03-04 --pass morning --run RUN
"""

import argparse
import re
import sys
from datetime import datetime

import _common as c

PRIVATE = "PRIVATE"


def truthy(value):
    text = c.blank(value).lower()
    if text in ("", "false", "0", "no", "off", "none"):
        return False
    if text in ("true", "1", "yes", "on"):
        return True
    raise c.Stop(f"--dry-run-if wants true or false, got {value!r}")


def block_text(pass_, section):
    return f"{c.open_marker(pass_)}\n{section.strip()}\n{c.close_marker(pass_)}"


def new_content(day, pass_, section):
    return f"# {c.title(day)}\n\n{block_text(pass_, section)}\n\n{c.day_marker(day)}\n"


def compose(content, day, pass_, section, last_hash, stamp):
    """(new content, action) for an existing note."""
    found = c.blocks(content, pass_)
    marker = c.day_marker(day)
    body = content.replace(marker, "").rstrip()
    if found:
        start, end, inner = found[-1]
        if c.digest(inner) == c.digest(section):
            return content, "unchanged"
        if last_hash and c.digest(inner) == last_hash:
            return content[:start] + block_text(pass_, section) + content[end:], "replaced"
        text = section.strip()
        heading = text.splitlines()[0] if text else ""
        if heading.startswith("## "):
            text = f"{heading} (re-run {stamp})" + text[len(heading):]
        return content[:end] + "\n\n" + block_text(pass_, text) + content[end:], "appended"
    if pass_ == "morning":
        evening = c.blocks(body, "evening")
        if evening:
            at = evening[0][0]
            out = body[:at] + block_text(pass_, section) + "\n\n" + body[at:]
            return out.rstrip() + f"\n\n{marker}\n", "added"
    return body + "\n\n" + block_text(pass_, section) + f"\n\n{marker}\n", "added"


def verify(note, day, pass_, section_hash):
    if note is None:
        return ["the note did not read back"]
    problems, content = [], str(note.get("content") or "")
    if str(note.get("title") or "").strip() != c.title(day):
        problems.append(f"title is {note.get('title')!r}")
    if c.day_marker(day) not in content:
        problems.append("the day's marker is missing")
    if not any(c.digest(inner) == section_hash for _, _, inner in c.blocks(content, pass_)):
        problems.append(f"the {pass_} block did not read back")
    return problems


def publish(client, plan, day, pass_, dry_run, state, domain, tags, stamp):
    section = c.render(plan)
    me = client.call("whoami")
    owner = ((me.get("principal") or {}) if isinstance(me, dict) else {}).get("contact_id")
    if not owner:
        raise c.Stop("whoami named no contact for the owner")
    found = c.find_notes(client, day)
    note = found[0] if found else None
    saved = c.read_json(c.state_file(state, day, pass_))
    last_hash = (saved.get("published") or {}).get("block_hash") if isinstance(saved, dict) else None
    result = {"tool": "daily-plan-publish", "date": day.isoformat(), "pass": pass_, "dry_run": dry_run,
              "duplicates": max(0, len(found) - 1)}
    if note is None:
        content, action = new_content(day, pass_, section), "created"
    else:
        content, action = compose(str(note.get("content") or ""), day, pass_, section, last_hash, stamp)
        result["note"] = f"portal://note/{note.get('id')}"
    newest = c.blocks(content, pass_)
    result["block_hash"] = c.digest(newest[-1][2] if newest else section)
    private_already = note is not None and str(note.get("visibility") or "").upper() == PRIVATE
    if dry_run:
        result["status"] = f"would_{action}" if action != "unchanged" else "unchanged"
        if note is not None and not private_already:
            result["would_make_private"] = True
        return result
    if action == "created":
        out = client.call("create_note", {
            "title": c.title(day), "content": content, "tag_names": tags,
            "associations": [{"entity_type": "contact", "entity_id": owner, "is_primary": True}]
            + ([{"entity_type": "domain", "entity_id": domain}] if domain else [])})
        note_id = out.get("id") if isinstance(out, dict) else None
        if not note_id:
            raise c.Stop(f"create_note gave no id: {c.safe(out)[:200]}")
        result["note"] = f"portal://note/{note_id}"
        client.call("update_note", {"id": note_id, "fields": {"visibility": PRIVATE}})
    else:
        note_id = str(note.get("id"))
        fields = {}
        if action != "unchanged":
            fields["content"] = content
        if not private_already:
            fields["visibility"] = PRIVATE
        if fields:
            args = {"id": note_id, "fields": fields}
            if "content" in fields and note.get("updated_at"):
                args["expected_updated_at"] = note.get("updated_at")
            client.call("update_note", args)
    back = c.read_note(client, note_id)
    problems = verify(back, day, pass_, result["block_hash"])
    if back is not None and str(back.get("visibility") or "").upper() != PRIVATE:
        result.update({"status": "refused", "code": "NOT_PRIVATE",
                       "reason": f"the note reads back {back.get('visibility')!r}; the next run makes it private"})
        return result
    if problems:
        result.update({"status": "refused", "code": "NOT_VERIFIED", "reason": "; ".join(problems)})
        return result
    result["status"] = action
    result["updated_at"] = back.get("updated_at")
    copy = dict(plan, published={"note_id": note_id, "block_hash": result["block_hash"],
                                 "updated_at": result["updated_at"], "at": stamp})
    c.write_json(c.state_file(state, day, pass_), copy)
    return result


def main(argv=None, client=None):
    p = argparse.ArgumentParser(prog="daily_plan_publish.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--date", dest="day", default="", help="The day, yyyy-mm-dd (blank: the plan's, else today)")
    p.add_argument("--pass", dest="pass_", default="", help="morning or evening (blank: the plan's, else by the clock)")
    p.add_argument("--run", dest="run_dir", required=True, help="The Run folder: reads plan.json, writes plan.md and publish.json")
    p.add_argument("--dry-run", action="store_true", help="Read and render, write nothing to the Portal or the state")
    p.add_argument("--dry-run-if", default=None, help="true or false (a scheduler placeholder); true is --dry-run")
    p.add_argument("--domain", default="", help="A domain id the note is also attached to")
    p.add_argument("--tag", dest="tags", action="append", default=[], help="Tag names (default briefing, daily-plan)")
    p.add_argument("--tz", dest="tz_name", default="", help="IANA timezone (default the owner's, from whoami)")
    p.add_argument("--state", dest="state_path", default="", help="The state folder (default <state_dir>/daily-plan)")
    p.add_argument("--config", default=None, help="MCP config holding the Portal (default: setting portal_mcp_config)")
    p.add_argument("--server", default=None, help="Server name in the MCP config (default: setting portal_server)")
    args = p.parse_args(argv)
    try:
        dry_run = args.dry_run or (truthy(args.dry_run_if) if args.dry_run_if is not None else False)
        run = c.guard_run_path(args.run_dir)
        raw = c.read_json(run / "plan.json")
        if raw is None:
            c.emit({"tool": "daily-plan-publish", "status": "refused", "code": "NO_PLAN",
                    "reason": f"{run / 'plan.json'} does not exist; nothing was written"}, 3)
        domain = c.blank(args.domain)
        if domain and not re.fullmatch(r"[0-9a-fA-F-]{36}", domain):
            raise c.Stop(f"--domain wants a domain id, got {domain!r}")
        state = c.state_root(args.state_path)
        client = client or c.Portal(args.config, args.server)
        tz = c.zone(c.blank(args.tz_name) or c.owner_timezone(client))
        plan_day = raw.get("date") if isinstance(raw, dict) else None
        plan_pass = raw.get("pass") if isinstance(raw, dict) else None
        the_day, the_pass = c.resolve(c.blank(args.day) or plan_day, c.blank(args.pass_) or plan_pass, tz)
        plan = c.load_plan(run / "plan.json", the_day, the_pass)
        if plan["dry_run"] and not dry_run:
            c.emit({"tool": "daily-plan-publish", "status": "refused", "code": "DRY_RUN",
                    "reason": "the plan is a dry run's; publish it only with --dry-run"}, 3)
        (run / "plan.md").write_text(c.render(plan) + "\n", encoding="utf-8")
        tags = [t for t in (c.blank(t) for t in args.tags) if t] or list(c.TAGS)
        result = publish(client, plan, the_day, the_pass, dry_run, state, domain, tags,
                         datetime.now(tz).strftime("%H:%M"))
        c.write_json(run / ("publish-dry-run.json" if dry_run else "publish.json"), result)
    except (c.Stop, c.PortalError) as exc:
        c.emit({"status": "error", "reason": str(exc)}, 2)
    c.emit(result, 3 if result.get("status") == "refused" else 0)


if __name__ == "__main__":
    main()
