"""Tests for month_end_record.py."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.modules.pop("_common", None)  # another skill's _common may be loaded in the same run
from month_end_fixture import PERIOD

import month_end_record as mer
from _common import COLUMNS, evidence_path, read_evidence

SCRIPT = Path(mer.__file__)


def rec(root, test, item, state, by="month-end-reviewer", **kw):
    return mer.record(root, PERIOD, test, item, state, by, **kw)


def test_creates_the_file_with_its_header(folder):
    result = rec(folder, "reconciliations", "10200", "reconciled", evidence="reconciliations/10200 cash.xlsx",
                 amount="$80,000", pull_date="2026-04-02", note="tied  to the   statement", by="month-end-cash")
    assert result["action"] == "created" and result["id"] == "reconciliations:10200" and not result["warnings"]
    path = evidence_path(folder, PERIOD)
    assert path.read_text().splitlines()[0] == ",".join(COLUMNS)
    row = read_evidence(path)["reconciliations:10200"]
    assert (row["amount"], row["pull_date"], row["note"], row["by"]) == (
        "80000.00", "2026-04-02", "tied to the statement", "month-end-cash")


def test_other_rows_keep_their_exact_text(folder):
    path = evidence_path(folder, PERIOD)
    odd = ('"entries:card","entries","card","booked","JE 301","","","PASS","","said ""ok"", twice",'
           '"2026-04-01T09:00:00","Sam"\r\n')
    path.write_bytes(("﻿" + ",".join(COLUMNS) + "\r\n" + odd
                      + 'flux:pl,flux,pl,open,,,,,,"two\r\nlines",x,y\r\n').encode())
    rec(folder, "flux", "pl", "explained", evidence="reporting/x.md")
    rec(folder, "questions", "Q1", "answered")
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf") and odd.encode() in raw
    text = raw.decode("utf-8").removeprefix("\ufeff")
    assert "\n" not in text.replace("\r\n", "")
    rows = read_evidence(path)
    assert set(rows) == {"entries:card", "flux:pl", "questions:Q1"}
    assert rows["flux:pl"]["state"] == "explained" and rows["flux:pl"]["note"] == "two\r\nlines"
    assert not list(path.parent.glob(".*.tmp"))


def test_omitted_fields_kept_and_stale_review_cleared(folder):
    rec(folder, "reconciliations", "10200", "reconciled", evidence="reconciliations/10200 cash.xlsx",
        amount="80000", review="pass", review_file="reporting/review.md", note="first")
    rec(folder, "reconciliations", "10200", "reconciled", note="second")
    row = read_evidence(evidence_path(folder, PERIOD))["reconciliations:10200"]
    assert (row["review"], row["amount"], row["note"]) == ("PASS", "80000.00", "second")
    result = rec(folder, "reconciliations", "10200", "reconciled", amount="(81,000)")
    row = read_evidence(evidence_path(folder, PERIOD))["reconciliations:10200"]
    assert (row["review"], row["review_file"], row["amount"]) == ("", "", "-81000.00")
    assert any("review was cleared" in w for w in result["warnings"])


def test_missing_evidence_file_warns(folder):
    assert any("does not exist" in w for w in rec(folder, "reconciliations", "10200", "reconciled",
                                                   evidence="reconciliations/nope.xlsx")["warnings"])
    assert not rec(folder, "entries", "card", "booked", evidence="JE 301")["warnings"]


@pytest.mark.parametrize("change, message", [
    (("--test", "cash"), "--test"), (("--state", "done"), "--state"),
    (("--state", "booked"), "belongs to the entries test"), (("--review", "OK"), "--review"),
    (("--amount", "lots"), "--amount"), (("--pull-date", "04/02/2026"), "--pull-date"),
    (("--period", "2026-13"), "--period"), (("--period", "2025-11"), "month folder does not exist"),
])
def test_cli_rejects_bad_values(folder, change, message):
    args = {"--period": PERIOD, "--test": "reconciliations", "--item": "10200", "--state": "reconciled",
            "--by": "month-end-cash"}
    args[change[0]] = change[1]
    run = subprocess.run([sys.executable, str(SCRIPT), str(folder), *[x for kv in args.items() for x in kv]],
                         capture_output=True, text=True)
    assert run.returncode == 2 and message in run.stderr
    assert not evidence_path(folder, PERIOD).exists()


def test_cli_prints_what_it_did(folder):
    run = subprocess.run([sys.executable, str(SCRIPT), str(folder), "--period", PERIOD, "--test", "entries",
                          "--item", "card", "--state", "booked", "--evidence", "JE 301", "--by", "month-end-accruals"],
                         capture_output=True, text=True)
    assert run.returncode == 0 and "created entries:card" in run.stdout
