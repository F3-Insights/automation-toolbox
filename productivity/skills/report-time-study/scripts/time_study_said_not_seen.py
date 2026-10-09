"""Write a time-study window's said-but-not-seen list as JSON, for other orchestrators.

Reads the said-but-not-seen section (a `## ` heading naming it) of every `days/<date>/day.md`
in the window: the owner's spoken commitments that nothing later shows were kept. The day
assembler writes each as one numbered line with ` | ` between fields:

    1. HH:MM:SS | <source> | "<quote>" | <what> | to: <whom> | by: <when> | domain: <domain> | <why not seen>

A line in an older free-text shape, or a numbered row of a table, is kept too, with
`structured: false`, its time and quote found where they can be, and the whole line in `text`.

Inputs: WINDOW_DIR (`<home>/data/raw/<D1>_to_<D2>`); `--review FILE`, the orchestrator's
judgment across the window, a JSON object keyed by an item's `id` or `ref`:
`{"<id>": {"status": "seen" | "dropped" | "open", "evidence": "...", "note": "..."}}`;
`--out FILE` (default `<home>/out/said-not-seen-<window>.json`, the home being three folders
up from the window), which is replaced only when it already carries this schema.

Prints a one-line count (JSON with `--format json`). Each item's `id` is a short hash of its
date, time and quote, stable across re-runs that renumber the list. Exit 0 when it wrote, 1 when
a day's section is missing (the file is still written), 2 on a bad argument.

Example:
    python3 time_study_said_not_seen.py H/data/raw/2030-09-01_to_2030-09-14 \
        --review H/data/raw/2030-09-01_to_2030-09-14/said-not-seen-review.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from _common import SAID_SCHEMA, Bad, fail, parse_window

ITEM_RE = re.compile(r"^\s*(\d+)\.\s+(.*)$")
TIME_RE = re.compile(r"\b(\d{1,2}:\d{2}(?::\d{2})?)\b")
QUOTE_RE = re.compile(r'"([^"]+)"|“([^”]+)”')
REC_RE = re.compile(r"meetings/([^\s|.]+)\.md|recording ([0-9A-Za-z_-]+)|Loom ([0-9a-f]{6,})")
STATUSES = ("open", "seen", "dropped")


def section(text):
    """The lines of the said-but-not-seen section, or None when the day has none."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("## ") and "said but not seen" in line.lower():
            body = []
            for nxt in lines[i + 1:]:
                if nxt.startswith("## "):
                    break
                body.append(nxt)
            return body
    return None


def items_of(lines):
    """Numbered items (or numbered table rows), each with its continuation lines folded in."""
    out = []
    for line in lines:
        m = ITEM_RE.match(line)
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.lstrip().startswith("|") else []
        if m:
            out.append(m.group(2).strip())
        elif cells and cells[0].isdigit():
            out.append("; ".join(c for c in cells[1:] if c))
        elif cells:
            continue  # a table header or separator row
        elif out and line.strip() and not line.lstrip().startswith(("- ", "#")):
            out[-1] += " " + line.strip()
    return out


def field(value, label):
    v = value.strip()
    if v.lower().startswith(label + ":"):
        v = v[len(label) + 1:].strip()
    return None if v.lower() in ("", "none", "not said", "-") else v


def parse_item(day, n, text):
    parts = [p.strip() for p in text.split(" | ")]
    item = {"ref": f"{day}#{n}", "date": day, "text": text}
    if (len(parts) >= 8 and TIME_RE.fullmatch(parts[0]) and parts[4].lower().startswith("to:")
            and parts[5].lower().startswith("by:") and parts[6].lower().startswith("domain:")):
        item.update(structured=True, time=parts[0], source=parts[1], quote=parts[2].strip('"“”'),
                    commitment=parts[3], to=field(parts[4], "to"), by=field(parts[5], "by"),
                    domain=field(parts[6], "domain"), why_not_seen=" | ".join(parts[7:]))
    else:
        t, q = TIME_RE.search(text), QUOTE_RE.search(text)
        item.update(structured=False, time=t.group(1) if t else None, source=None,
                    quote=(q.group(1) or q.group(2)) if q else None, commitment=None, to=None, by=None,
                    domain=None, why_not_seen=None)
    rec = REC_RE.search(item.get("source") or text)
    item["recording_id"] = next((g for g in rec.groups() if g), None) if rec else None
    key = f"{day}|{item['time'] or ''}|{(item['quote'] or text).strip().lower()}"
    item["id"] = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return item


def build(window_dir, review=None):
    name = window_dir.name
    a, b = parse_window(name)
    review = review or {}
    items, missing = [], []
    days = sorted((window_dir / "days").glob("*/day.md")) if (window_dir / "days").is_dir() else []
    for p in days:
        day = p.parent.name
        body = section(p.read_text(encoding="utf-8", errors="replace"))
        if body is None:
            missing.append(day)
            continue
        for n, text in enumerate(items_of(body), start=1):
            item = parse_item(day, n, text)
            r = review.get(item["id"]) or review.get(item["ref"]) or {}
            status = str(r.get("status") or "open")
            if status not in STATUSES:
                raise Bad(f"review for {item['id']}: status '{status}' is not one of {', '.join(STATUSES)}")
            item.update(status=status, review_evidence=r.get("evidence"), review_note=r.get("note"))
            items.append(item)
    counts = {s: sum(1 for i in items if i["status"] == s) for s in STATUSES}
    counts.update(items=len(items), structured=sum(1 for i in items if i["structured"]),
                  days_read=len(days) - len(missing))
    return {"schema": SAID_SCHEMA, "window": name, "since": a.isoformat(), "until": b.isoformat(),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "report": f"report-{name}.md", "counts": counts, "days_without_section": missing,
            "items": items}


def write(path, data):
    """Write atomically, refusing to replace a file that is not one of these lists."""
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            old = None
        if not isinstance(old, dict) or old.get("schema") != SAID_SCHEMA:
            raise Bad(f"{path} exists and is not a {SAID_SCHEMA} file; refusing to replace it")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="time-study-said-not-seen", description=__doc__.split("\n\n")[0])
    ap.add_argument("window_dir", help="<home>/data/raw/<D1>_to_<D2>")
    ap.add_argument("--review", default="", help="the orchestrator's review JSON, keyed by id or ref")
    ap.add_argument("--out", default="", help="where to write; blank: <home>/out/said-not-seen-<window>.json")
    ap.add_argument("--format", dest="fmt", choices=["text", "json"], default="text")
    a = ap.parse_args(argv)
    try:
        w = Path(a.window_dir).expanduser()
        if not w.is_dir():
            raise Bad(f"no window folder {w}")
        review = {}
        if a.review.strip():
            try:
                review = json.loads(Path(a.review.strip()).expanduser().read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise Bad(f"review file unreadable: {exc}") from None
            if not isinstance(review, dict):
                raise Bad("the review file must be a JSON object keyed by id or ref")
        data = build(w, review)
        target = Path(a.out.strip()).expanduser() if a.out.strip() else \
            w.parent.parent.parent / "out" / f"said-not-seen-{w.name}.json"
        write(target, data)
    except Bad as exc:
        return fail(exc)
    c = data["counts"]
    if a.fmt == "json":
        print(json.dumps({"file": str(target), "counts": c,
                          "days_without_section": data["days_without_section"]}, indent=1))
    else:
        print(f"WROTE: {target} ({c['items']} item(s): {c['open']} open, {c['seen']} seen, "
              f"{c['dropped']} dropped; {c['structured']} structured)")
        if data["days_without_section"]:
            print("  days without the section: " + ", ".join(data["days_without_section"]))
    return 1 if data["days_without_section"] else 0


if __name__ == "__main__":
    sys.exit(main())
