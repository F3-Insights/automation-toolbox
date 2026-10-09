"""Check one day's slots.csv (and topics.csv) and count its hours by domain and topic.

The checks are the ones the time-study tool's build makes, so a worker finds a problem before
the build does:
- slots.csv: the header, exactly 144 contiguous ten-minute slots from 00:00 (the last ends
  24:00 or 00:00), every tier one of the five, every domain in the owner's domain list, every
  allocation's weights summing to 1, and the primary domain the largest share;
- topics.csv (with `--topics`): one row per slot per domain share and nothing else, every topic
  an id in the owner's topic list, confidence high, medium or low.

Inputs: DAY_DIR (`<window>/days/<date>`); `--domains` the owner's domain list, a CSV with a
`domain` column (default the setting `domains_csv` under [report-time-study]); `--topics` the
owner's topic list, a CSV with a `topic` column (given, topics.csv is checked too).

Prints `OK` or `FAIL: <n> problem(s)`, the problems, then the hours by domain (and by domain
and topic); a share is its weight times ten minutes. `--format json` prints the same as JSON.
Exit 0 when the day passes, 1 when it fails, 2 on a bad argument or a missing file.

Example:
    python3 time_study_day_lint.py H/data/raw/2030-09-01_to_2030-09-14/days/2030-09-03 \
        --domains H/domains.csv --topics H/topics.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

from _common import SKILL, Bad, fail, settings

SLOTS = 144
TOLERANCE = 1e-6
SLOT_HEADER = ["slot_start", "slot_end", "primary_activity", "primary_domain", "tier", "concurrent",
               "evidence", "allocation", "tags"]
TOPIC_HEADER = ["slot_start", "domain", "topic", "confidence", "basis"]
TIERS = ("verified", "corroborated", "owner-stated", "inferred", "unaccounted")
CONFIDENCE = ("high", "medium", "low")


def ids(path, column):
    """The non-blank values of one column of a CSV file."""
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            return {(r.get(column) or "").strip() for r in csv.DictReader(fh)} - {""}
    except OSError as exc:
        raise Bad(f"cannot read {path}: {exc}") from None


def minutes(hhmm):
    h, m = hhmm.strip().split(":")
    return int(h) * 60 + int(m)


def shares_of(row):
    """The slot's domain shares: the allocation `A:0.75;B:0.25`, or the primary domain at 1."""
    alloc = (row.get("allocation") or "").strip()
    if not alloc:
        return [((row.get("primary_domain") or "").strip(), 1.0)]
    out = []
    for piece in (p.strip() for p in alloc.split(";")):
        if not piece:
            continue
        if ":" not in piece:
            raise ValueError(f"allocation piece without a weight: {piece!r}")
        name, weight = piece.rsplit(":", 1)
        out.append((name.strip(), float(weight)))
    return out


def safe_shares(row):
    try:
        return shares_of(row)
    except ValueError:
        return []


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return [h.strip() for h in (reader.fieldnames or [])], list(reader)


def lint(day_dir, domains, topics=None):
    problems = []
    slots = day_dir / "slots.csv"
    if not slots.is_file():
        raise Bad(f"no {slots}")
    header, rows = read_csv(slots)
    if header != SLOT_HEADER:
        problems.append(f"slots.csv header is {','.join(header)}; expected {','.join(SLOT_HEADER)}")
    if len(rows) != SLOTS:
        problems.append(f"slots.csv has {len(rows)} rows, not {SLOTS}")
    hours = defaultdict(float)
    tiers = defaultdict(int)
    expected = set()  # every (slot_start, domain) pair the day's shares make
    for i, r in enumerate(rows):
        where = f"slots.csv row {i + 2} ({(r.get('slot_start') or '').strip()})"
        try:
            start, end = minutes(r.get("slot_start") or ""), minutes(r.get("slot_end") or "")
        except ValueError:
            problems.append(f"{where}: times are not HH:MM")
            continue
        if end == 0 and start == 24 * 60 - 10:
            end = 24 * 60
        if start != i * 10 or end != start + 10:
            problems.append(f"{where}: not the {i * 10 // 60:02d}:{i * 10 % 60:02d} slot")
        tier = (r.get("tier") or "").strip()
        tiers[tier] += 1
        if tier not in TIERS:
            problems.append(f"{where}: tier '{tier}' is not one of {', '.join(TIERS)}")
        try:
            shares = shares_of(r)
        except ValueError as exc:
            problems.append(f"{where}: {exc}")
            continue
        total = sum(w for _, w in shares)
        if abs(total - 1) > TOLERANCE:
            problems.append(f"{where}: shares sum to {total:g}, not 1")
        for name, weight in shares:
            if name not in domains:
                problems.append(f"{where}: domain '{name}' is not in domains.csv")
            hours[name] += weight / 6
            expected.add(((r.get("slot_start") or "").strip(), name))
        primary = (r.get("primary_domain") or "").strip()
        biggest = max(w for _, w in shares) if shares else 0
        if len(shares) > 1 and biggest - dict(shares).get(primary, 0) > TOLERANCE:
            problems.append(f"{where}: primary domain '{primary}' is not the largest share")
    result = {"day": day_dir.name, "slots": len(rows),
              "hours_by_domain": {k: round(v, 2) for k, v in sorted(hours.items())},
              "slots_by_tier": dict(sorted(tiers.items()))}

    if topics is not None:
        by_topic = defaultdict(float)
        weights = {((r.get("slot_start") or "").strip(), n): w for r in rows for n, w in safe_shares(r)}
        tpath = day_dir / "topics.csv"
        if not tpath.is_file():
            problems.append("no topics.csv")
        else:
            theader, trows = read_csv(tpath)
            if theader[:3] != TOPIC_HEADER[:3]:
                problems.append(f"topics.csv header is {','.join(theader)}; expected {','.join(TOPIC_HEADER)}")
            seen = set()
            for n, r in enumerate(trows, start=2):
                key = ((r.get("slot_start") or "").strip(), (r.get("domain") or "").strip())
                topic, conf = (r.get("topic") or "").strip(), (r.get("confidence") or "").strip()
                if key in seen:
                    problems.append(f"topics.csv row {n}: {key[0]} '{key[1]}' appears twice")
                elif key not in expected:
                    problems.append(f"topics.csv row {n}: {key[0]} '{key[1]}' is not a slot-domain of this day")
                elif topic not in topics:
                    problems.append(f"topics.csv row {n}: topic '{topic}' is not in topics.csv")
                else:
                    by_topic[f"{key[1]} / {topic}"] += weights.get(key, 0) / 6
                if conf and conf not in CONFIDENCE:
                    problems.append(f"topics.csv row {n}: confidence '{conf}' is not high, medium or low")
                seen.add(key)
            gaps = sorted(expected - seen)
            if gaps:
                problems.append(f"topics.csv: {len(gaps)} slot-domain row(s) have no topic, "
                                f"for example {gaps[0][0]} '{gaps[0][1]}'")
        result["hours_by_domain_topic"] = {k: round(v, 2) for k, v in sorted(by_topic.items())}
    result["problems"] = problems
    result["ok"] = not problems
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(prog="time-study-day-lint", description=__doc__.split("\n\n")[0])
    ap.add_argument("day_dir", help="<window>/days/<date>")
    ap.add_argument("--domains", default="", help="the owner's domains.csv")
    ap.add_argument("--topics", default="", help="the owner's topics.csv; given, topics.csv is checked too")
    ap.add_argument("--format", dest="fmt", choices=["text", "json"], default="text")
    a = ap.parse_args(argv)
    try:
        domains = a.domains.strip() or str(settings(SKILL).get("domains_csv") or "")
        if not domains:
            raise Bad("--domains is required, or set `domains_csv` under [report-time-study] in the settings file")
        result = lint(Path(a.day_dir).expanduser(), ids(Path(domains).expanduser(), "domain"),
                      ids(Path(a.topics.strip()).expanduser(), "topic") if a.topics.strip() else None)
    except Bad as exc:
        return fail(exc)
    if a.fmt == "json":
        print(json.dumps(result, indent=1))
    else:
        problems = result["problems"]
        print("OK" if not problems else f"FAIL: {len(problems)} problem(s)")
        for p in problems[:40]:
            print(f"  - {p}")
        if len(problems) > 40:
            print(f"  - and {len(problems) - 40} more")
        print("hours by domain: " + "; ".join(f"{k} {v}" for k, v in result["hours_by_domain"].items()))
        if "hours_by_domain_topic" in result:
            print("hours by domain and topic: " + "; ".join(
                f"{k} {v}" for k, v in result["hours_by_domain_topic"].items()))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
