"""Shared fixtures for the time-study script tests: an invented owner at Northwind Traders.

A fake `timestudy` package stands in for the tool's checkout; nothing reads a real home.
"""

import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

DOMAINS = ["Northwind Traders", "Fabrikam Logistics", "Personal", "Sleep", "Unaccounted"]
TOPICS = ["sales", "finance", "none", "family"]
SAID_SCHEMA = "time-study/said-not-seen@1"
PROVISIONAL = "provisional: questions open"

# The fake tool logs each call and fakes `collect` (failing for any January 2031 window).
FAKE_MAIN = '''import sys, pathlib
args = sys.argv[1:]
home = pathlib.Path(args[args.index("--home") + 1])
cmd = args[args.index("--home") + 2]
log = home / "calls.log"
log.write_text((log.read_text() if log.exists() else "") + " ".join(args[2:]) + "\\n")
if cmd == "collect":
    name = args[args.index("--window") + 1]
    if name.startswith("2031-01-0"):
        print("error: the calendar source timed out", file=sys.stderr); sys.exit(1)
    w = home / "data" / "raw" / name
    w.mkdir(parents=True, exist_ok=True)
    (w / "coverage.json").write_text("{}")
    print("Window: " + name)
elif cmd == "summary":
    print("Summary: 9 days studied")
'''

DAY_MD = """# {d}
## Done
- nothing
## Said but not seen
1. 10:20:05 | meetings/rec-a.md | "I'll send the price list Friday" | Send the price list | to: Dana | by: {d} | domain: Northwind Traders | no sent mail after the call
2. 15:30 Pipeline call: "let me check the freight quote" and nothing later (Loom 9f8e7d6c).
## Questions
"""


@pytest.fixture(autouse=True)
def no_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "no-settings.toml"))


@pytest.fixture
def home(tmp_path):
    repo = tmp_path / "timestudy-checkout"
    (repo / "timestudy").mkdir(parents=True)
    (repo / "timestudy" / "__init__.py").write_text("")
    (repo / "timestudy" / "__main__.py").write_text(FAKE_MAIN)
    h = repo / "private"
    (h / "data" / "raw").mkdir(parents=True)
    (h / "out").mkdir()
    (h / "domains.csv").write_text("domain,domain_group\n" + "".join(f'"{d}",x\n' for d in DOMAINS))
    (h / "topics.csv").write_text("topic,label\n" + "".join(f"{t},{t}\n" for t in TOPICS))
    return h


def hhmm(i):
    return f"{i * 10 // 60:02d}:{i * 10 % 60:02d}"


def slot_rows(split_at=None):
    rows = []
    for i in range(144):
        end = "24:00" if i == 143 else hhmm(i + 1)
        d, alloc = ("Sleep", "") if i < 42 else ("Northwind Traders", "")
        if i == split_at:
            d, alloc = "Northwind Traders", "Northwind Traders:0.75;Fabrikam Logistics:0.25"
        rows.append(f"{hhmm(i)},{end},work,{d},verified,,calendar,{alloc},")
    return ("slot_start,slot_end,primary_activity,primary_domain,tier,concurrent,evidence,allocation,tags\n"
            + "\n".join(rows) + "\n")


def topic_rows(split_at=None):
    out = ["slot_start,domain,topic,confidence,basis"]
    for i in range(144):
        if i < 42:
            out.append(f"{hhmm(i)},Sleep,none,high,asleep")
        elif i == split_at:
            out += [f"{hhmm(i)},Northwind Traders,sales,high,call", f"{hhmm(i)},Fabrikam Logistics,finance,medium,mail"]
        else:
            out.append(f"{hhmm(i)},Northwind Traders,sales,high,call")
    return "\n".join(out) + "\n"


def make_window(h, name, *, collected=True, recordings=("rec-a",), segmented=True, days=True,
                checked=True, report=True, said=True, provisional=False):
    a, b = (date.fromisoformat(x) for x in name.split("_to_"))
    w = h / "data" / "raw" / name
    w.mkdir(parents=True, exist_ok=True)
    if collected:
        (w / "coverage.json").write_text("{}")
    (w / "recordings.json").write_text(json.dumps([{"recording_id": r} for r in recordings]))
    if segmented:
        (w / "meetings").mkdir(exist_ok=True)
        for r in recordings:
            (w / "meetings" / f"{r}.md").write_text("# segment")
    if days:
        d = a
        while d <= b:
            dd = w / "days" / d.isoformat()
            dd.mkdir(parents=True, exist_ok=True)
            (dd / "slots.csv").write_text(slot_rows())
            (dd / "topics.csv").write_text(topic_rows())
            (dd / "day.md").write_text(DAY_MD.format(d=d.isoformat()))
            d += timedelta(days=1)
    if checked:
        (w / "check.json").write_text("{}")
    later = time.time() + 5
    if report:
        r = h / "out" / f"report-{name}.md"
        r.write_text("# report\n" + (PROVISIONAL + "\n" if provisional else ""))
        os.utime(r, (later, later))
    if said:
        (h / "out" / f"said-not-seen-{name}.json").write_text(
            json.dumps({"schema": SAID_SCHEMA, "window": name, "items": []}))
    return w
