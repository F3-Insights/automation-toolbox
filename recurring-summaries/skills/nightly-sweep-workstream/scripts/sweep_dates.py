"""sweep-dates: which dates this nightly-sweep run processes, oldest first, and their windows.

The first command of a sweep Run (the Automation's prepare step). It writes RUN/dates.json and,
outside a dry run, marks the dates it hands out as in progress in the ledger, under the
ledger's lock, so a second run started meanwhile takes other dates. It reads the Portal only on
an empty ledger, to find the newest Daily Note.

Which dates:
- A date can be swept once its local day is over: a run shortly after midnight sweeps yesterday.
- A night nobody swept is in no ledger entry, so the next run picks it up, oldest first, at most
  --cap dates a run; the rest wait (`waiting_for_next_run`).
- A date recorded incomplete is offered again, at most 2 more times, then listed under
  `incomplete_gave_up`.
- An unswept date more than --lookback days back is listed under `beyond_lookback`, never swept
  on its own (sweep it with --date).
- With an empty ledger (a first run, or a lost ledger) the newest `Daily Note - <date>` found in
  the Portal from the last 7 days is the starting point: every closed date from the day before
  it to yesterday is taken, at most 3, the newest kept. With none found, the newest closed date
  and the one before it are taken.
- A date another run marked in progress less than 3 hours ago is skipped
  (`in_progress_elsewhere`); a --date naming one is refused (`IN_PROGRESS`).
- --date may name today: its mail so far is swept, but the date is not recorded as swept.

Each date carries `email_window` (its local day as UTC instants, since inclusive, until
exclusive), `next_day` and its `calendar_window`, `calendar_prep` (true while the next day is not
over) and `relationship_check` (true on the newest date of the run only). With dates, the result
carries `vip_stale_days` from the settings.

Inputs: settings [nightly-sweep-workstream] timezone and state (or --tz, --state).
Prints one JSON object. Exit 0 with dates (`ok`), 3 with none (`nothing`) or refused
(`IN_PROGRESS`), 2 on an error.

Example:
    python3 sweep_dates.py --run ~/runs/nightly-sweep/2030-03-07-0040
"""

import argparse
from datetime import timedelta, timezone
from pathlib import Path

import _common as c


def newest_closed(now_local):
    """The newest date whose local day is over: yesterday."""
    return now_local.date() - timedelta(days=1)


def describe(day, tz, now_local, newest):
    nxt = day + timedelta(days=1)
    return {"date": day.isoformat(), "weekday": day.strftime("%A"),
            "email_window": c.local_day(day, tz),
            "next_day": nxt.isoformat(), "next_day_weekday": nxt.strftime("%A"),
            "calendar_window": c.local_day(nxt, tz),
            "calendar_prep": nxt >= now_local.date(),
            "relationship_check": newest}


def first_run(newest, cap, last_note, notes):
    """An empty ledger: the dates from the day before the newest Daily Note found, and the older gap."""
    limit = max(min(cap, c.RECOVERY_DATES), 1)
    if not last_note:
        chosen = [newest - timedelta(days=n) for n in range(min(c.FIRST_RUN_DATES, limit) - 1, -1, -1)]
        notes.append(f"the ledger is empty and no Daily Note was found in the last {c.LOOKBACK_DAYS} days, so "
                     f"the newest {len(chosen)} closed date(s) are swept; earlier nights are not (sweep one "
                     "with --date)")
        return chosen, []
    start = min(c.parse_date(last_note) - timedelta(days=1), newest)
    span = [start + timedelta(days=n) for n in range((newest - start).days + 1)]
    chosen, older = span[-limit:], [d.isoformat() for d in span[:-limit]]
    notes.append(f"the ledger is empty; the newest Daily Note found in the Portal is for {last_note}, so "
                 f"{len(chosen)} closed date(s) from {chosen[0]} are swept")
    if older:
        notes.append(f"{len(older)} older date(s) since that Daily Note are past the cap of {limit} and are "
                     "not swept automatically (sweep one with --date): " + ", ".join(older))
    return chosen, older


def plan(ledger, now, tz_name, cap=c.DATES_PER_RUN, lookback=c.LOOKBACK_DAYS, explicit=None,
         in_progress=None, run=None, last_note=None):
    tz = c.zone(tz_name)
    now_local = now.astimezone(tz)
    today = now_local.date()
    newest = newest_closed(now_local)
    busy = {d for d, e in (in_progress or {}).items() if c.in_progress_fresh(e, now, run)}
    done = sorted(d for d in ledger if c.DATE_RE.match(str(d)))
    notes, beyond, waiting, gave_up, elsewhere = [], [], [], [], []

    if explicit:
        day = c.parse_date(explicit)
        if day > today:
            raise c.Stop(f"{day} has not happened yet in {tz_name}")
        if day.isoformat() in busy:
            return {"status": "refused", "code": "IN_PROGRESS", "date": day.isoformat(),
                    "reason": f"another run started sweeping {day} at "
                              f"{(in_progress or {})[day.isoformat()].get('started_at')}; the mark expires "
                              f"{c.IN_PROGRESS_HOURS} hours after that"}
        if day > newest:
            notes.append(f"{day} is not over in {tz_name}; mail after now is not swept, and the date is not "
                         "recorded as swept, so the night's run sweeps the whole day")
        if day.isoformat() in ledger:
            notes.append(f"{day} was already swept at {ledger[day.isoformat()].get('completed_at')}; "
                         "re-running it finds what that sweep wrote by marker and writes nothing twice")
        chosen = [day]
    elif not done:
        chosen, beyond = first_run(newest, cap, last_note, notes)
        for d in list(chosen):
            if d.isoformat() in busy:
                chosen.remove(d)
                elsewhere.append(d.isoformat())
        if elsewhere:
            notes.append(f"{len(elsewhere)} date(s) are being swept by another run: " + ", ".join(elsewhere))
    else:
        first_done = c.parse_date(done[0])
        floor = max(first_done, newest - timedelta(days=max(lookback, 1) - 1))
        pending, day = [], first_done
        while day <= newest:
            iso = day.isoformat()
            entry = ledger.get(iso)
            retry = entry is not None and not c.is_done(entry)
            if retry and int(entry.get("attempts") or 1) > c.RETRIES:
                gave_up.append(iso)
            elif entry is None or retry:
                if iso in busy:
                    elsewhere.append(iso)
                elif day >= floor:
                    pending.append(day)
                else:
                    beyond.append(iso)
            day += timedelta(days=1)
        chosen = pending[:max(cap, 1)]
        waiting = [d.isoformat() for d in pending[max(cap, 1):]]
        if waiting:
            notes.append(f"{len(waiting)} more unswept date(s) wait for the next run (cap {cap} a run)")
        if beyond:
            notes.append(f"{len(beyond)} unswept date(s) are older than the {lookback}-day lookback and are "
                         "not swept automatically")
        if gave_up:
            notes.append(f"{len(gave_up)} date(s) stayed incomplete after {c.RETRIES} retries and are not "
                         "offered again (sweep one with --date): " + ", ".join(gave_up))
        if elsewhere:
            notes.append(f"{len(elsewhere)} date(s) are being swept by another run: " + ", ".join(elsewhere))
        retried = [d.isoformat() for d in chosen if d.isoformat() in ledger]
        if retried:
            notes.append("swept again because the last sweep was incomplete: " + ", ".join(retried))

    dates = [describe(d, tz, now_local, i == len(chosen) - 1) for i, d in enumerate(chosen)]
    return {"status": "ok" if dates else "nothing", "timezone": tz_name,
            "now_local": now_local.isoformat(timespec="seconds"),
            "dates": dates, "waiting_for_next_run": waiting, "beyond_lookback": beyond,
            "incomplete_gave_up": gave_up, "in_progress_elsewhere": elsewhere,
            "last_swept": done[-1] if done else None, "notes": notes}


def take(root, now, tz_name, cap, lookback, explicit, run, dry_run, last_note=None):
    """Plan under the ledger's lock and, outside a dry run, mark the chosen dates in progress
    before the lock is released, so two runs never take the same date."""
    with c.locked(root / "ledger.lock"):
        state = c.load_state(root)
        result = plan(state["dates"], now, tz_name, cap, lookback, explicit,
                      None if dry_run else state["in_progress"], run, last_note)
        if not dry_run and result["status"] == "ok":
            for d in result["dates"]:
                state["in_progress"][d["date"]] = {"started_at": now.astimezone(timezone.utc).isoformat(),
                                                   "run": run}
            c.save_state(root, state)
    return result


def main(argv=None, client=None):
    ap = argparse.ArgumentParser(description="The dates this nightly-sweep run sweeps, oldest first, with their "
                                             "local-day windows. Exit 0 ok, 3 nothing or refused, 2 error.")
    ap.add_argument("--date", dest="explicit", help="sweep exactly this date (YYYY-MM-DD)")
    ap.add_argument("--run", help="the run folder; dates.json is written there")
    ap.add_argument("--dry-run", action="store_true", help="mark dates.json a dry run; set no in-progress mark")
    ap.add_argument("--state", help="state folder (default: the settings)")
    ap.add_argument("--tz", help="the owner's IANA timezone (default: the settings)")
    ap.add_argument("--cap", type=int, default=c.DATES_PER_RUN, help="dates per run (default 3)")
    ap.add_argument("--lookback", type=int, default=c.LOOKBACK_DAYS, help="days a catch-up reaches back (default 7)")
    ap.add_argument("--now", help="pretend it is this ISO instant (tests, rehearsals)")
    args = ap.parse_args(argv)
    result = {}

    def body():
        now = c.now_or(args.now)
        tz_name = c.timezone_name(args.tz)
        root = c.state_root(args.state)
        run = str(c.guard_run_path(args.run)) if args.run else None
        last_note, lookup = None, None
        if not args.explicit and not any(c.DATE_RE.match(str(d)) for d in c.load_state(root)["dates"]):
            newest = newest_closed(now.astimezone(c.zone(tz_name)))
            try:
                last_note = c.newest_daily_note(client or c.Portal(), newest)
            except Exception as exc:  # noqa: BLE001 - the fixed two dates are the fallback
                lookup = (f"the Daily Note lookup failed ({type(exc).__name__}: {c.safe(exc)}); the fixed "
                          f"{c.FIRST_RUN_DATES} dates were taken")
        result.update(take(root, now, tz_name, args.cap, args.lookback, args.explicit, run, args.dry_run,
                           last_note))
        if lookup:
            result.setdefault("notes", []).append(lookup)
        if result["status"] == "ok":
            result["vip_stale_days"], unusable = c.vip_stale_days()
            if unusable:
                result["notes"].append(unusable)
        result["dry_run"] = args.dry_run
        result["ledger"] = str(root / "ledger.json")
        if run:
            result["run"] = run
            c.atomic_json(Path(run) / "dates.json", result)

    c.run_main(body, "sweep_dates")
    c.emit(result, c.OK if result["status"] == "ok" else c.STOP)


if __name__ == "__main__":
    main()
