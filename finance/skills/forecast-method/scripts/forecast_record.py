# /// script
# dependencies = ["pyyaml"]
# ///
"""Record one row of a forecast vintage's evidence ledger, FORECAST-EVIDENCE-<vintage>.csv.

The ledger is the only record forecast-check takes on trust, so this is its only writer. One
row per test and item, keyed "<test>:<item>": a new key adds a row, a known key updates it (a
field not given keeps its value). Rows are never deleted, and every other row keeps its exact
text. When the state, evidence or amount of a reviewed row changes without a new review, the
review is cleared and the output says so.

Tests and items: hypotheses (item `set`, state written), questions (Q-nnn: asked, answered,
expired, withdrawn), messages (a date or id: asked), review (item `vintage`, state reviewed,
--review PASS or FAIL), delivered (item `vintage`, state delivered, --evidence the filed path).
For hypotheses and review the evidence is computed here, the SHA-256 of the files the row vouches
for, so a row cannot claim a file it did not see. Hypotheses are refused once a bridge exists,
and an asked or expired question must carry its fallback assumption in --note.

Prints "created <id>" or "updated <id>". Exit 0 on success, 2 on a refusal or bad argument.

Example:
    python3 forecast_record.py ~/Forecast --vintage rev3 --test questions --item Q-001 \\
        --state asked --by forecast-orchestrator --note "If unanswered, assume a January start."
"""

import argparse
import csv
import io
import os
import sys
import tempfile
from pathlib import Path

from _common import LEDGER_COLUMNS, ForecastError, file_sha, forecast_folder, ledger_path, load_vintage, now, work_shas

RECORD_TESTS = ("hypotheses", "questions", "messages", "review", "delivered")
STATES = ("written", "asked", "answered", "expired", "withdrawn", "reviewed", "delivered")
# A state that belongs to one test only; asked fits questions and messages.
STATE_TEST = {"written": "hypotheses", "answered": "questions", "expired": "questions", "withdrawn": "questions",
              "reviewed": "review", "delivered": "delivered"}
WORK_FIELDS = ("state", "evidence", "amount")
REVIEW_FIELDS = ("review", "review_file")


def records(text):
    """The CSV's records, each with the exact text it came from (a cell may span lines)."""
    lines = text.splitlines(keepends=True)
    reader = csv.reader(iter(lines))
    out, consumed = [], 0
    for row in reader:
        out.append((row, "".join(lines[consumed:reader.line_num])))
        consumed = reader.line_num
    return out


def csv_line(values, terminator):
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator=terminator).writerow(values)
    return buffer.getvalue()


def upsert(path, key, values):
    """Create or update the row with id `key`, keeping every other row's exact text, the file's
    line endings and any byte-order mark. Returns (action, review_cleared)."""
    raw = path.read_bytes() if path.is_file() else b""
    bom = "﻿" if raw.startswith(b"\xef\xbb\xbf") else ""
    text = raw.decode("utf-8").lstrip("\ufeff")
    found = records(text) if text.strip() else []
    terminator = "\r\n" if found and found[0][1].endswith("\r\n") else "\n"
    if found and [c.strip() for c in found[0][0]] != LEDGER_COLUMNS:
        raise ForecastError(f"{path.name} does not start with the header {','.join(LEDGER_COLUMNS)}")
    if not found:
        found = [(LEDGER_COLUMNS, csv_line(LEDGER_COLUMNS, terminator))]
    index = next((i for i, (cells, _) in enumerate(found) if i and cells and cells[0].strip() == key), None)
    old = dict(zip(LEDGER_COLUMNS, [c.strip() for c in found[index][0]] + [""] * len(LEDGER_COLUMNS))) if index else {}
    row = {c: old.get(c, "") for c in LEDGER_COLUMNS}
    row.update(values, id=key)
    # A review never outlives the work it passed.
    work_changed = any(name in values and row[name] != old.get(name, "") for name in WORK_FIELDS)
    cleared = bool(old.get("review")) and work_changed and "review" not in values
    if cleared:
        for name in REVIEW_FIELDS:
            if name not in values:
                row[name] = ""
    if row["state"] not in STATES:
        raise ForecastError(f"--state {row['state']!r} is not one of {', '.join(STATES)}")
    owner = STATE_TEST.get(row["state"])
    if owner and owner != row["test"]:
        raise ForecastError(f"--state {row['state']} belongs to the {owner} test, not {row['test']}")
    line = csv_line([row[c] for c in LEDGER_COLUMNS], terminator)
    if index:
        found[index] = (found[index][0], line)
    else:
        if not found[-1][1].endswith(("\n", "\r")):
            found[-1] = (found[-1][0], found[-1][1] + terminator)
        found.append(([], line))
    # Write beside the old file and rename over it, keeping its permissions.
    handle = tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp",
                                         delete=False, encoding="utf-8", newline="")
    try:
        with handle:
            handle.write(bom + "".join(chunk for _, chunk in found))
        if path.exists():
            os.chmod(handle.name, path.stat().st_mode & 0o777)
        os.replace(handle.name, path)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise
    return ("updated" if index else "created"), cleared


def record(folder, vintage, test, item, state, by, evidence=None, amount=None, review=None, review_file=None,
           note=None):
    if not by.strip():
        raise ForecastError("--by names who did it")
    root = forecast_folder(folder)
    vdir = Path(load_vintage(root, vintage)["_dir"])
    values = {"test": test, "item": item, "state": state, "by": by, "updated_at": now()}
    if test == "hypotheses":
        if not (vdir / "hypotheses.json").is_file():
            raise ForecastError("hypotheses.json is not in the vintage folder")
        if (vdir / "bridge.json").is_file():
            raise ForecastError("the bridge is already built: hypotheses are written and recorded before it")
        values["evidence"] = f"sha256:{file_sha(vdir / 'hypotheses.json')}"
    elif test == "review":
        if review not in ("PASS", "FAIL"):
            raise ForecastError("--review PASS or FAIL")
        values["evidence"] = work_shas(vdir)
    elif evidence is not None:
        values["evidence"] = evidence
    if test == "questions" and state in ("asked", "expired") and not (note or "").strip():
        raise ForecastError("a question carries its fallback assumption in --note")
    for name, value in (("amount", amount), ("review", review), ("review_file", review_file), ("note", note)):
        if value is not None:
            values[name] = value
    key = f"{test}:{item}"
    action, cleared = upsert(ledger_path(vdir, vintage), key, values)
    return {"id": key, "action": action, "review_cleared": cleared}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Record one row of the vintage's evidence ledger.")
    parser.add_argument("folder", help="the Forecast folder")
    parser.add_argument("--vintage", required=True)
    parser.add_argument("--test", required=True, choices=RECORD_TESTS)
    parser.add_argument("--item", required=True,
                        help="hypotheses: set; questions: Q-001; messages: a date or id; review and delivered: vintage")
    parser.add_argument("--state", required=True, choices=STATES)
    parser.add_argument("--by", required=True, help="who did it (the agent's or the person's role)")
    parser.add_argument("--evidence")
    parser.add_argument("--amount")
    parser.add_argument("--review", choices=["PASS", "FAIL"])
    parser.add_argument("--review-file")
    parser.add_argument("--note")
    args = parser.parse_args(argv)
    try:
        done = record(args.folder, args.vintage, args.test, args.item, args.state, args.by, args.evidence,
                      args.amount, args.review, args.review_file, args.note)
    except ForecastError as exc:
        print(f"forecast-record: {exc}", file=sys.stderr)
        return 2
    print(f"{done['action']} {done['id']}" + (" (review cleared: the work changed)" if done["review_cleared"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
