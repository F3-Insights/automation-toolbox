"""What the time-study scripts share: the owner's settings, the Run's scope, and where each
window stands.

The home folder H is the time-study tool's private home. Its layout is the tool's own:

    H/data/raw/<D1>_to_<D2>/      one window, both dates inclusive (W)
      coverage.json               written by the tool's `collect`
      recordings.json             the window's recordings
      meetings/<recording_id>.md  one segment file per recording
      days/<date>/slots.csv, day.md, topics.csv
      check.json                  the independent checker's result
      questions.md, answers-<date>.md
    H/out/report-<window>.md      the window's report
    H/out/said-not-seen-<window>.json

A date sits in at most one window, and a window is at most WINDOW_DAYS days. Nothing here
writes.
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import tomllib
from datetime import date, timedelta
from pathlib import Path

WINDOW_DAYS = 14
MAX_DAYS = 45
WINDOW_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})$")
PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
PROVISIONAL = "provisional: questions open"
SAID_SCHEMA = "time-study/said-not-seen@1"
TESTS = ("collected", "segmented", "attributed", "checked", "reported", "answered")
TOOL_COMMANDS = ("build", "summary", "dashboard", "precheck", "collect")
SKILL = "report-time-study"


class Bad(Exception):
    """A bad argument, a missing setting or a missing folder: the script exits 2."""


def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


def home_or_setting(home):
    """The home folder given on the command line, else the setting [report-time-study] home."""
    value = (home or "").strip() or str(settings(SKILL).get("home") or "")
    if not value:
        raise Bad("HOME is required: pass it, or set `home` under [report-time-study] in the settings file")
    return value


def fail(message, code=2):
    print(f"ERROR {message}", file=sys.stderr)
    return code


# ------------------------------------------------------------------------------ windows and periods

def window_name(since, until):
    return f"{since.isoformat()}_to_{until.isoformat()}"


def parse_window(name):
    m = WINDOW_RE.match(name or "")
    if not m:
        raise Bad(f"window '{name}' is not first-date_to_last-date (2030-09-14_to_2030-09-20)")
    a, b = date.fromisoformat(m.group(1)), date.fromisoformat(m.group(2))
    if b < a:
        raise Bad(f"window '{name}' ends before it starts")
    return a, b


def days_between(a, b):
    return [a + timedelta(days=i) for i in range((b - a).days + 1)]


def windows(home):
    """Every window folder under H/data/raw, by name."""
    raw = home / "data" / "raw"
    out = {}
    if raw.is_dir():
        for p in sorted(raw.iterdir()):
            if p.is_dir() and WINDOW_RE.match(p.name):
                try:
                    out[p.name] = parse_window(p.name)
                except (Bad, ValueError):
                    continue
    return out


def last_full_month(today):
    prev = today.replace(day=1) - timedelta(days=1)
    return f"{prev.year:04d}-{prev.month:02d}"


def month_span(period):
    if not PERIOD_RE.match(period or ""):
        raise Bad(f"period '{period}' is not yyyy-mm")
    y, m = int(period[:4]), int(period[5:])
    nxt = date(y + (m == 12), m % 12 + 1, 1)
    return date(y, m, 1), nxt - timedelta(days=1)


def split(days, window_days=WINDOW_DAYS):
    """Contiguous runs of days, each cut into near-equal windows of at most window_days."""
    runs = []
    for d in sorted(days):
        if runs and (d - runs[-1][-1]).days == 1:
            runs[-1].append(d)
        else:
            runs.append([d])
    out = []
    for run in runs:
        parts = math.ceil(len(run) / window_days)
        size, extra = divmod(len(run), parts)
        i = 0
        for k in range(parts):
            n = size + (1 if k < extra else 0)
            out.append((run[i], run[i + n - 1]))
            i += n
    return out


def plan(home, today, period=None, window=None, max_days=MAX_DAYS, window_days=WINDOW_DAYS):
    """The Run's scope: the existing windows in it, the new windows to collect, and notes.

    With `window`, that window alone (new when its folder does not exist yet). Otherwise the
    period (default the last full month), widened back to the day after the latest window when
    that window ended before the period began, never past yesterday. The days of the span no
    window holds become new windows, the newest `max_days` of them.
    """
    if not home.is_dir():
        raise Bad(f"no home folder {home}")
    existing = windows(home)
    notes = []
    yesterday = today - timedelta(days=1)
    if window:
        a, b = parse_window(window)
        span = [a.isoformat(), b.isoformat()]
        if window in existing:
            return {"period": None, "span": span, "existing": [window], "new": [], "skipped": [], "notes": notes}
        for other, (x, y) in existing.items():
            if x <= b and a <= y:
                raise Bad(f"window {window} overlaps {other}; a date may sit in only one window")
        if b > yesterday:
            raise Bad(f"window {window} runs past yesterday ({yesterday})")
        return {"period": None, "span": span, "existing": [], "new": [window], "skipped": [], "notes": notes}

    period = period or last_full_month(today)
    first, last = month_span(period)
    if last > yesterday:
        last = yesterday
        notes.append(f"{period} is not over; the span stops at yesterday, {yesterday}")
    start = first
    if existing:
        latest = max(b for _, b in existing.values())
        if latest + timedelta(days=1) < first:
            start = latest + timedelta(days=1)
            notes.append(f"the latest window ended {latest}; the days from {start} are studied too")
    if last < start:
        return {"period": period, "span": [first.isoformat(), last.isoformat()], "existing": [],
                "new": [], "skipped": [], "notes": notes + [f"{period} has no day up to yesterday"]}
    held = {d for a, b in existing.values() for d in days_between(a, b)}
    free = [d for d in days_between(start, last) if d not in held]
    skipped = []
    if len(free) > max_days:
        skipped = [d.isoformat() for d in free[:-max_days]]
        free = free[-max_days:]
        notes.append(f"{len(skipped)} day(s) from {skipped[0]} to {skipped[-1]} are past the "
                     f"{max_days}-day limit of one Run and are left out")
    in_scope = sorted(n for n, (a, b) in existing.items() if a <= last and start <= b)
    return {"period": period, "span": [start.isoformat(), last.isoformat()], "existing": in_scope,
            "new": [window_name(a, b) for a, b in split(free, window_days)], "skipped": skipped,
            "notes": notes}


# ------------------------------------------------------------------------------ one window's state

def mtime(p):
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def report_path(home, name):
    return home / "out" / f"report-{name}.md"


def said_path(home, name):
    return home / "out" / f"said-not-seen-{name}.json"


def window_state(home, name):
    """Each test of done for one existing window: met, and the gaps that keep it open."""
    w = home / "data" / "raw" / name
    a, b = parse_window(name)
    dates = [d.isoformat() for d in days_between(a, b)]
    gaps = {t: [] for t in TESTS}

    if not (w / "coverage.json").is_file():
        gaps["collected"].append("no coverage.json: the local signals are not collected")

    recordings = []
    if (w / "recordings.json").is_file():
        try:
            data = json.loads((w / "recordings.json").read_text(encoding="utf-8"))
            recordings = [str(r["recording_id"]) for r in data if isinstance(r, dict) and r.get("recording_id")]
        except (ValueError, OSError) as exc:
            gaps["segmented"].append(f"recordings.json unreadable: {exc}")
    missing = [r for r in recordings if not (w / "meetings" / f"{r}.md").is_file()]
    if missing:
        gaps["segmented"].append(f"{len(missing)} of {len(recordings)} recording(s) have no segment file"
                                 f" ({', '.join(missing[:3])}{', ...' if len(missing) > 3 else ''})")

    # The report must be newer than every slots.csv and topics.csv of the window.
    newest_day = 0.0
    lacking = {}
    for d in dates:
        for f in ("slots.csv", "day.md", "topics.csv"):
            p = w / "days" / d / f
            if p.is_file():
                if f != "day.md":
                    newest_day = max(newest_day, mtime(p))
            else:
                lacking.setdefault(f, []).append(d)
    for f, ds in lacking.items():
        gaps["attributed"].append(f"{len(ds)} day(s) without {f} ({ds[0]}{' ...' if len(ds) > 1 else ''})")

    if not (w / "check.json").is_file():
        gaps["checked"].append("no check.json from the checker")

    report = report_path(home, name)
    provisional = False
    if not report.is_file():
        gaps["reported"].append(f"no report out/{report.name}")
    else:
        if mtime(report) < newest_day:
            gaps["reported"].append("the report is older than the window's slots or topics")
        try:
            provisional = PROVISIONAL in report.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
    said = said_path(home, name)
    if not said.is_file():
        gaps["reported"].append(f"no out/{said.name}")
    else:
        try:
            data = json.loads(said.read_text(encoding="utf-8"))
            if data.get("schema") != SAID_SCHEMA or data.get("window") != name:
                gaps["reported"].append(f"out/{said.name} is not this window's {SAID_SCHEMA}")
        except (ValueError, OSError, AttributeError):
            gaps["reported"].append(f"out/{said.name} is not valid JSON")

    # Answers newer than the report are waiting to be applied.
    fresh = [p.name for p in sorted(w.glob("answers-*.md")) if mtime(p) > mtime(report)]
    if fresh:
        gaps["answered"].append(f"answers wait to be applied ({', '.join(fresh)})")
    return {"window": name, "days": len(dates), "recordings": len(recordings),
            "tests": {t: {"met": not g, "gaps": g} for t, g in gaps.items()},
            "done": not any(gaps.values()), "waiting_on_owner": provisional and not fresh}


# ------------------------------------------------------------------------------ the time-study tool

def find_repo(home, repo=None):
    """The tool's checkout: --repo, else the setting [report-time-study] repo, else the home's
    parent folder when it holds the `timestudy` package."""
    configured = str(settings(SKILL).get("repo") or "")
    for candidate, why in ((repo, "--repo"), (configured, "the setting repo"), (str(home.parent), "parent")):
        if not candidate:
            continue
        p = Path(candidate).expanduser()
        if (p / "timestudy" / "__main__.py").is_file():
            return p
        if why != "parent":
            raise Bad(f"{why} {p} holds no timestudy package")
    raise Bad("no time-study checkout: pass --repo or set `repo` under [report-time-study] in the settings file")


def run_tool(home, command, args, repo=None):
    """Run `python -m timestudy --home H COMMAND ARGS` from the checkout; (exit code, stdout, stderr)."""
    if command not in TOOL_COMMANDS:
        raise Bad(f"command '{command}' is not one of {', '.join(TOOL_COMMANDS)}")
    root = Path(home).expanduser()
    if not root.is_dir():
        raise Bad(f"no home folder {root}")
    checkout = find_repo(root, repo)
    argv = [sys.executable, "-m", "timestudy", "--home", str(root.resolve()), command, *args]
    proc = subprocess.run(argv, cwd=str(checkout), capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr
