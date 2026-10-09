"""sweep-note-publish: write one date's Daily Note, once, and record the date as swept.

The note writer returns the note's markdown, saved as RUN/<date>/daily-note.md; this script puts
it in the Portal in the Automation's finish step, after sweep_apply. With --run and no DAY it
publishes every date in RUN/dates.json that has a daily-note.md.

What it adds. Before the note's marker it appends a block written in code, "## What the sweep
wrote", from the date folder's applied-phase1, 2 and 4 files (the -dry-run ones in a dry run):
per phase, the counts by outcome and one line per failed or skipped write with its reason. The
note's counts of what was actually written therefore come from code, not from a model.

Exactly one Daily Note per date, titled `Daily Note - <date>`, its content ending with
`<!-- nightly-sweep:daily-note:<date> -->`. Notes with that title or marker are looked up first;
the oldest is kept and any others are flagged. It is rewritten in place only when this job wrote
it and nobody changed it since: it carries the marker, holds no "## Re-sweep" section, and its
updated_at is no later than the one this job read back after its own last write (the ledger's
`published`). Without that record, a note changed more than a minute after it was created counts
as possibly edited. Otherwise the new sweep is appended as a dated "## Re-sweep" section, so
nothing anyone wrote is lost. A new note is tagged nightly-sweep, not pinned, and attached to the
owner's contact. With the setting [nightly-sweep-workstream] daily_note_private true, the note is
made private and must read back private. Every write is read back.

Only after the note reads back with its title and marker is the date recorded in the ledger, and
only once the date is over in the owner's timezone (a daytime run of today leaves the ledger
alone: "skipped, day not over"). The entry says whether the sweep was complete, read from the
date folder: a missing emails.json, a missing or BLOCKED phase 1 (on a day with inbound mail) or
phase 2, an emails listing that stopped early, or an apply that was not `applied` or `nothing`
makes it incomplete (`complete` false, with `missing` and `failed`), and sweep_dates offers it
again, at most twice. Phases 3 and 4 are `warnings` only: a re-sweep would not redo them. The
in-progress mark is cleared.

Refusals: a live publish needs the run's dates.json with a boolean dry_run that lists the date
(else NO_RUN); a dry run marked there or by F3I_TOOLBOX_DRY_RUN needs --dry-run (else DRY_RUN).

Prints one JSON object. Exit 0 (`created`, `updated`, `appended`, `unchanged`, `would_create`,
`would_update`, `would_append`, and `no_note` in a --run), 3 when refused (EMPTY_NOTE,
NOT_VERIFIED, DRY_RUN, NO_RUN), 2 on an error.

Examples:
    python3 sweep_note_publish.py 2030-03-06 --note RUN/2030-03-06/daily-note.md --run RUN
    python3 sweep_note_publish.py --run RUN
"""

import argparse
from datetime import timedelta
from pathlib import Path

import _common as c

RESWEEP = "## Re-sweep"
WRITTEN = "## What the sweep wrote"
APPLY_OK = ("applied", "nothing")
PRIVATE = "PRIVATE"
OUTCOME_ORDER = ("created", "updated", "reused", "unchanged", "skipped", "failed",
                 "would_create", "would_update")


def body(text, day):
    """The note content with its marker as the last line, exactly once."""
    marker = c.daily_note_marker(day)
    lines = [ln for ln in text.rstrip().splitlines() if ln.strip() != marker]
    return "\n".join(lines).rstrip() + "\n\n" + marker + "\n"


def resweep_section(text, day, now_local):
    """The new note as a dated section: its title line dropped, its headings one level down
    (a # line inside a fenced code block is code, not a heading)."""
    marker = c.daily_note_marker(day)
    lines = [ln for ln in text.rstrip().splitlines() if ln.strip() != marker]
    while lines and not lines[0].strip():
        lines = lines[1:]
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    out, fence = [], ""
    for ln in lines:
        mark = ln.lstrip()[:3]
        if mark in ("```", "~~~") and (not fence or mark == fence):
            fence = "" if fence else mark
        out.append("#" + ln if ln.startswith("#") and not fence else ln)
    return f"{RESWEEP} {now_local.strftime('%Y-%m-%d %H:%M')}\n\n" + "\n".join(out).strip()


def written_block(folder, dry_run=False):
    """What sweep_apply actually did with each phase's change set, from the applied files."""
    lines = [WRITTEN, ""]
    for n in (1, 2, 4):
        plan = c.json_or_none(Path(folder) / f"phase{n}.json")
        if plan is None:
            continue
        if isinstance(plan, dict) and plan.get("status") == "BLOCKED":
            lines.append(f"- Phase {n}: BLOCKED, nothing to apply ({plan.get('reason') or 'no reason'})")
            continue
        name = f"applied-phase{n}{'-dry-run' if dry_run else ''}.json"
        applied = c.json_or_none(Path(folder) / name)
        if not isinstance(applied, dict):
            lines.append(f"- Phase {n}: not applied (no {name})")
            continue
        counts = applied.get("counts") or {}
        keys = [k for k in OUTCOME_ORDER if counts.get(k)] + sorted(k for k in counts if k not in OUTCOME_ORDER)
        tally = ", ".join(f"{k} {counts[k]}" for k in keys) or "no writes"
        lines.append(f"- Phase {n} ({applied.get('status')}): {tally}")
        for r in applied.get("results") or []:
            if isinstance(r, dict) and r.get("outcome") in ("failed", "skipped"):
                what = r.get("title") or r.get("id") or r.get("key") or r.get("kind")
                lines.append(f"  - {r['outcome']}: {what}: {r.get('reason') or 'no reason given'}")
    if len(lines) == 2:
        lines.append("- No change set was applied for this date.")
    return "\n".join(lines)


def ours_and_untouched(current, day, published):
    """None when this job may rewrite the note whole; otherwise why it is appended to instead."""
    if published and str(published.get("note_id") or "") != str(current.get("id") or ""):
        published = None
    content = str(current.get("content") or "")
    if c.daily_note_marker(day) not in content:
        return "the note was not written by this job (no marker); the sweep was appended as a Re-sweep section"
    if any(ln.startswith(RESWEEP) for ln in content.splitlines()):
        return "the note already holds a Re-sweep section; this sweep was appended after it"
    edited, ours = c.parse_time(current.get("updated_at")), c.parse_time((published or {}).get("updated_at"))
    if edited and ours and edited > ours:
        return (f"the note was changed at {current.get('updated_at')}, after this job last wrote it; the sweep "
                "was appended as a Re-sweep section")
    created = c.parse_time(current.get("created_at"))
    if not ours and edited and created and edited > created + timedelta(minutes=1):
        return (f"the ledger has no record of this job's last write and the note was changed at "
                f"{current.get('updated_at')}, after it was created; it may have been edited, so the sweep was "
                "appended as a Re-sweep section")
    return None


def is_private(note):
    return str((note or {}).get("visibility") or "").upper() == PRIVATE


def publish(client, day, text, dry_run=False, published=None, now=None, tz_name="UTC", private=False):
    if not text.strip():
        return {"status": "refused", "code": "EMPTY_NOTE", "reason": "the Daily Note file is empty", "date": day}
    now = now or c.now_or(None)
    title, marker = c.daily_note_title(day), c.daily_note_marker(day)
    content = body(text, day)
    existing = c.notes_titled(client, title, marker)
    flags = []
    if len(existing) > 1:
        flags.append(f"{len(existing)} notes are titled {title!r} or carry its marker; the oldest, "
                     f"{existing[0]['id']}, is kept current and the others can be deleted: "
                     + ", ".join(n["id"] for n in existing[1:]))
    if existing:
        nid = str(existing[0]["id"])
        current = c.get_record(client, "note", nid)
        held = str(current.get("content") or "")
        needs_private = private and not is_private(current)
        why = ours_and_untouched(current, day, published)
        status = None
        if why:
            section = resweep_section(text, day, now.astimezone(c.zone(tz_name)))
            after_heading = section.split("\n", 1)[1].strip()
            if after_heading and after_heading in held:
                status = "unchanged"
            else:
                flags.append(why)
                if dry_run:
                    return {"status": "would_append", "date": day, "id": nid, "title": title, "flags": flags}
                content, status = body(held.rstrip() + "\n\n" + section, day), "appended"
        elif held == content:
            status = "unchanged"
        elif dry_run:
            return {"status": "would_update", "date": day, "id": nid, "title": title, "flags": flags}
        else:
            status = "updated"
        if status == "unchanged" and not needs_private:
            return {"status": "unchanged", "date": day, "id": nid, "title": title, "flags": flags,
                    "verified": True, "updated_at": current.get("updated_at")}
        if dry_run:
            return {"status": "unchanged", "date": day, "id": nid, "title": title, "flags": flags,
                    "would_make_private": True}
        fields = {} if status == "unchanged" else {"content": content}
        if needs_private:
            fields["visibility"] = PRIVATE
        client.call("update_note", {"id": nid, "fields": fields})
    else:
        if dry_run:
            return {"status": "would_create", "date": day, "title": title, "flags": flags}
        owner = c.owner_contact(client)
        created = client.call("create_note", {
            "title": title, "content": content, "tag_names": [c.SWEEP_TAG], "is_pinned": False,
            "associations": [{"entity_type": "contact", "entity_id": owner}]})
        nid = created.get("id") if isinstance(created, dict) else None
        if not c.is_uuid(nid) and isinstance(created, dict):
            nid = (created.get("note") or {}).get("id")
        if not c.is_uuid(nid):
            again = c.notes_titled(client, title, marker)
            if not again:
                return {"status": "refused", "code": "NOT_VERIFIED", "date": day, "title": title,
                        "reason": "create_note answered without an id and no note has the title"}
            nid = again[0]["id"]
        if private:
            client.call("update_note", {"id": nid, "fields": {"visibility": PRIVATE}})
        status = "created"
    note = c.get_record(client, "note", str(nid))
    if str(note.get("title") or "").strip() != title or marker not in str(note.get("content") or ""):
        return {"status": "refused", "code": "NOT_VERIFIED", "date": day, "id": nid, "title": title,
                "reason": "the note did not read back with its title and this date's marker"}
    if private and not is_private(note):
        return {"status": "refused", "code": "NOT_VERIFIED", "date": day, "id": nid, "title": title,
                "reason": f"the note reads back {note.get('visibility')!r}, not private"}
    return {"status": status, "date": day, "id": nid, "title": title, "flags": flags, "verified": True,
            "updated_at": note.get("updated_at")}


# --------------------------------------------------------------------------- completeness

def _phase(folder, n, missing, failed, dry_run=False):
    proposed = c.json_or_none(folder / f"phase{n}.json")
    if proposed is None:
        missing.append(f"phase {n}: no phase{n}.json")
        return
    if isinstance(proposed, dict) and proposed.get("status") == "BLOCKED":
        failed.append(f"phase {n}: BLOCKED ({proposed.get('reason') or 'no reason'})")
        return
    name = f"applied-phase{n}{'-dry-run' if dry_run else ''}.json"
    applied = c.json_or_none(folder / name)
    if not isinstance(applied, dict):
        failed.append(f"phase {n}: its writes were not applied (no {name})")
    elif applied.get("status") not in APPLY_OK + (("would_apply",) if dry_run else ()):
        failed.append(f"phase {n}: sweep_apply was {applied.get('status')!r}, failed "
                      f"{(applied.get('counts') or {}).get('failed', 0)}")


def completeness(folder, flags=None, dry_run=False):
    """Whether the date's sweep did everything a re-sweep could redo, from the date folder.
    Phases 3 and 4 are warnings, each naming what did not happen and why."""
    folder = Path(folder)
    missing, failed, warnings = [], [], []
    emails = c.json_or_none(folder / "emails.json")
    if not isinstance(emails, dict):
        missing.append("emails: no emails.json")
        missing.append("phase 1: the day's email was never listed")
    else:
        if emails.get("errors"):
            failed.append("emails: " + "; ".join(str(e) for e in emails["errors"]))
        if emails.get("inbound"):
            _phase(folder, 1, missing, failed, dry_run)
    _phase(folder, 2, missing, failed, dry_run)
    flags = flags or {}
    if flags.get("relationship_check"):
        p3 = c.json_or_none(folder / "phase3.json")
        if not isinstance(p3, dict):
            warnings.append("phase 3: the relationship check did not run (no phase3.json)")
        elif p3.get("status") == "BLOCKED":
            warnings.append(f"phase 3: the relationship check was BLOCKED ({p3.get('reason') or 'no reason'})")
    if flags.get("calendar_prep"):
        nxt = flags.get("next_day") or "the next day"
        p4, n4 = c.json_or_none(folder / "phase4.json"), []
        if isinstance(p4, dict) and p4.get("status") != "BLOCKED":
            _phase(folder, 4, n4, n4, dry_run)
        if not isinstance(p4, dict):
            warnings.append(f"phase 4: the meetings of {nxt} were not prepared (no phase4.json)")
        elif p4.get("status") == "BLOCKED":
            warnings.append(f"phase 4: the meetings of {nxt} were not prepared, calendar prep was BLOCKED "
                            f"({p4.get('reason') or 'no reason'})")
        elif n4:
            warnings.append(f"phase 4: the meetings of {nxt} were not all prepared: " + "; ".join(n4))
    return {"complete": not missing and not failed, "missing": missing, "failed": failed, "warnings": warnings}


def date_flags(run, day):
    for row in (c.run_dates(run) or {}).get("dates") or []:
        if isinstance(row, dict) and row.get("date") == day:
            return row
    return {}


# --------------------------------------------------------------------------- one date

def publish_date(get_client, day, source, run, root, dry_run, tz_name, now):
    """Publish one date's note and record it, exactly as the single-date form does."""
    parsed = c.parse_date(day)
    refusal = c.run_refusal(run, dry_run, day)
    if refusal:
        return {"status": "refused", "code": refusal[0], "date": day, "reason": refusal[1]}
    text = Path(source).read_text(encoding="utf-8") if Path(source).is_file() else ""
    if not text.strip():
        return {"status": "refused", "code": "EMPTY_NOTE", "date": day, "reason": f"{source} is missing or empty"}
    folder = Path(source).parent if Path(source).parent.name == day else Path(run) / day
    text = text.rstrip() + "\n\n" + written_block(folder, dry_run)
    published = c.load_state(root)["published"].get(day)
    result = publish(get_client(), day, text, dry_run, published, now, tz_name, c.note_private())
    result.update(completeness(folder, date_flags(run, day), dry_run))
    if not dry_run:
        if result["status"] in ("created", "updated", "appended", "unchanged"):
            c.record_published(root, day, str(result["id"]), result.get("updated_at"))
            if not c.is_closed(parsed, c.zone(tz_name), now):
                result["ledger"] = "skipped, day not over"
                c.clear_in_progress(root, day)
            else:
                result["ledger"] = c.record_date(
                    root, day, note_id=result["id"], note_status=result["status"], run=str(run),
                    complete=result["complete"], missing=result["missing"], failed=result["failed"],
                    warnings=result["warnings"])
        else:
            c.clear_in_progress(root, day)
    return result


def main(argv=None, client=None):
    ap = argparse.ArgumentParser(description="Create or update a date's Daily Note, read it back, then record the "
                                             "date once it is over. Exit 0 written, 3 refused, 2 error.")
    ap.add_argument("day", nargs="?", help="the date, YYYY-MM-DD (or use --run alone)")
    ap.add_argument("--note", help="the Daily Note markdown, with DAY")
    ap.add_argument("--dry-run", action="store_true", help="write neither the note nor the ledger")
    ap.add_argument("--run", help="the run folder (default: two levels above the note); alone, every date")
    ap.add_argument("--state", help="state folder (default: the settings)")
    ap.add_argument("--tz", help="the owner's IANA timezone (default: the settings)")
    ap.add_argument("--now", help="pretend it is this ISO instant (tests, rehearsals)")
    args = ap.parse_args(argv)
    result = {}
    holder = []

    def get_client():
        if not holder:
            holder.append(client or c.Portal())
        return holder[0]

    def body():
        now = c.now_or(args.now)
        tz_name = c.timezone_name(args.tz)
        if not args.day:
            if not args.run or args.note:
                raise c.Stop("give DAY --note PATH, or --run RUN alone")
            run = c.guard_run_path(args.run)
            rows = c.run_date_rows(run)
            root = c.state_root(args.state)
            dates = []
            for row in rows:
                day = row["date"]
                source = Path(run) / day / "daily-note.md"
                if not source.is_file():
                    if not args.dry_run:
                        c.clear_in_progress(root, day)
                    dates.append({"status": "no_note", "date": day})
                    continue
                try:
                    dates.append(publish_date(get_client, day, source, run, root, args.dry_run, tz_name, now))
                except Exception as exc:  # noqa: BLE001 - one date failing is that date's result
                    dates.append({"status": "error", "date": day, "reason": c.safe(f"{type(exc).__name__}: {exc}")})
            bad = any(d["status"] in ("refused", "error") for d in dates)
            result.update({"status": "partial" if bad else "ok", "run": str(run), "dry_run": args.dry_run,
                           "dates": dates})
            return
        if not args.note:
            raise c.Stop("--note is required with DAY")
        c.parse_date(args.day)
        source = c.guard_run_path(args.note)
        run = c.guard_run_path(args.run) if args.run else Path(source).parent.parent
        root = c.state_root(args.state)
        result.update(publish_date(get_client, args.day, source, run, root, args.dry_run, tz_name, now))

    c.run_main(body, "sweep_note_publish")
    c.emit(result, c.STOP if result.get("status") in ("refused", "partial") else c.OK)


if __name__ == "__main__":
    main()
