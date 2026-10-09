"""report_weekly_prepare.py: the week collected and organised in code before the session."""

import json

from conftest import PERIOD, run


def test_prepare_collects_the_week_into_the_week_folder(store, week):
    assert week["status"] == "FRESH" and week["tier"] == "manual"
    folder = store / "work" / PERIOD
    assert {"ledger.json", "pack.json", "digest.md", "facts.json", "prepare.json"} <= {p.name for p in folder.iterdir()}
    assert json.loads((store / "workorder" / f"{PERIOD}.json").read_text())["stage"] == "organize"


def test_a_profile_that_does_not_validate_stops_the_week(store):
    (store / "profile.md").write_text("# Weekly report profile\n\n## Seats\n")
    done = run("report_weekly_prepare", store, "--period", PERIOD, "--format", "json")
    found = json.loads(done.stdout)
    assert done.returncode == 0 and found["status"] == "STALE" and found["blocked"] == "profile"
