"""report_pack.py: collect and organise in one command, through the invented Portal."""

import json

from conftest import PORTAL_PROFILE, run


def test_report_pack_collects_and_organises_in_one_command(tmp_path, store, portal):
    profile = tmp_path / "profile.md"
    profile.write_text(PORTAL_PROFILE)
    done = run("report_pack", "--domain", "Northwind", "--since", "2027-11-08", "--until", "2027-11-13",
               "--outline-file", profile, "--out", tmp_path / "pack.json", "--digest", tmp_path / "digest.md",
               "--ledger-out", tmp_path / "ledger.json")
    assert done.returncode == 0, done.stderr
    pack = json.loads((tmp_path / "pack.json").read_text())
    filed = {c["name"]: [r["ref"] for r in c["evidence"]] for c in pack["categories"]}
    assert "portal://task/t1" in filed["Month-end close"] and "portal://email/e1" in filed["Systems and support"]
    assert (tmp_path / "ledger.json").is_file() and "### Month-end close" in (tmp_path / "digest.md").read_text()


def test_report_pack_needs_a_domain():
    done = run("report_pack")
    assert done.returncode == 2 and "--domain is required" in done.stderr
