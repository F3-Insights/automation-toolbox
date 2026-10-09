import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import register  # noqa: E402


def run(capsys, *args):
    code = register.main([str(a) for a in args])
    out = capsys.readouterr()
    return code, out.out, out.err


def test_add_assigns_ids_and_history(tmp_path, capsys):
    assert run(capsys, "--dir", tmp_path, "add", "open_items", "--by", "Dana", "--field", "description=Book the freight accrual",
               "--field", "amount=1250.50", "--field", "evidence=E-1, E-2") == (0, "OI-001\n", "")
    assert run(capsys, "--dir", tmp_path, "add", "open_items", "--by", "Dana", "--field", "description=second")[1] == "OI-002\n"
    assert run(capsys, "--dir", tmp_path, "add", "proposals", "--by", "Dana", "--field", "title=Automate the bank feed")[1] == "P1\n"
    rows = yaml.safe_load((tmp_path / "open_items.yaml").read_text())["rows"]
    assert rows[0]["amount"] == 1250.5 and rows[0]["evidence"] == ["E-1", "E-2"]
    assert rows[0]["history"][0]["by"] == "Dana" and rows[0]["history"][0]["text"] == "created"


def test_unknown_fields_bad_statuses_and_duplicate_ids_are_refused(tmp_path, capsys):
    assert run(capsys, "--dir", tmp_path, "add", "open_items", "--by", "Dana", "--field", "descripton=typo")[0] == 1
    assert run(capsys, "--dir", tmp_path, "add", "risk_register", "--by", "Dana", "--field", "severity=extreme")[0] == 1
    assert run(capsys, "--dir", tmp_path, "add", "rec_status", "--by", "Dana", "--field", "status=open")[0] == 1
    run(capsys, "--dir", tmp_path, "add", "open_items", "--by", "Dana", "--field", "id=OI-900")
    code, _, err = run(capsys, "--dir", tmp_path, "add", "open_items", "--by", "Dana", "--field", "id=OI-900")
    assert code == 1 and "already has id OI-900" in err
    assert run(capsys, "--dir", tmp_path, "add", "open_items", "--by", "Dana", "--field", "no-equals")[0] == 2


@pytest.mark.parametrize("who", ["tool", "claude", "agent", "", "Agent Sam"])
def test_a_tool_never_closes_a_row(tmp_path, capsys, who):
    run(capsys, "--dir", tmp_path, "add", "open_items", "--by", "Dana", "--field", "description=x")
    code, _, err = run(capsys, "--dir", tmp_path, "close", "open_items", "OI-001", "--by", who, "--status", "done",
                       "--reason", "fixed")
    assert code == 1 and "person" in err


def test_close_by_a_person_or_a_ledger_proof(tmp_path, capsys):
    run(capsys, "--dir", tmp_path, "add", "open_items", "--by", "Dana", "--field", "description=x")
    run(capsys, "--dir", tmp_path, "add", "owed_by_owner", "--by", "Dana", "--field", "title=Approve the write-off")
    run(capsys, "--dir", tmp_path, "add", "risk_register", "--by", "Dana", "--field", "description=Vendor dispute")
    assert run(capsys, "--dir", tmp_path, "close", "open_items", "OI-001", "--by", "gl:JE4410", "--status", "done",
               "--reason", "posted")[1] == "OI-001 -> done\n"
    run(capsys, "--dir", tmp_path, "close", "owed_by_owner", "OBO-001", "--by", "Marcus", "--status", "answered",
        "--reason", "Approved up to 2,000")
    run(capsys, "--dir", tmp_path, "close", "risk_register", "RR-001", "--by", "Priya", "--status", "closed",
        "--reason", "Settled")
    owed = yaml.safe_load((tmp_path / "owed_by_owner.yaml").read_text())["rows"][0]
    assert owed["answer"] == "Approved up to 2,000" and owed["closed_by"] == "Marcus" and owed["closed_at"]
    assert yaml.safe_load((tmp_path / "risk_register.yaml").read_text())["rows"][0]["resolution"] == "Settled"
    assert run(capsys, "--dir", tmp_path, "close", "open_items", "OI-404", "--by", "Dana", "--status", "done",
               "--reason", "x")[0] == 1
    assert run(capsys, "--dir", tmp_path, "close", "risk_register", "RR-001", "--by", "Dana", "--status", "closed",
               "--reason", "  ")[0] == 1


def test_list_summary_and_render(tmp_path, capsys, monkeypatch):
    settings = tmp_path / "settings.toml"
    settings.write_text('[review-register]\nowner_name = "Jordan"\n')
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(settings))
    reg = tmp_path / "register"
    run(capsys, "--dir", reg, "add", "open_items", "--by", "Dana", "--field", "description=Freight accrual",
        "--field", "amount=4200", "--field", "due=2027-08-05", "--field", "period=2027-07")
    run(capsys, "--dir", reg, "add", "open_items", "--by", "Dana", "--field", "description=Old item")
    run(capsys, "--dir", reg, "close", "open_items", "OI-002", "--by", "Dana", "--status", "dropped", "--reason", "n/a")
    run(capsys, "--dir", reg, "add", "rec_status", "--by", "Dana", "--field", "account=1010",
        "--field", "account_name=Operating cash", "--field", "period=2027-07", "--field", "status=reviewed", "--field", "difference=0")
    run(capsys, "--dir", reg, "close", "rec_status", "REC-001", "--by", "Dana", "--status", "tied", "--reason", "ties")
    run(capsys, "--dir", reg, "add", "owed_by_owner", "--by", "Dana", "--field", "title=Sign the lease memo",
        "--field", "handoff_no=3")
    listed = run(capsys, "--dir", reg, "list", "open_items")[1].splitlines()
    assert [json.loads(l)["id"] for l in listed] == ["OI-001"]
    assert len(run(capsys, "--dir", reg, "list", "open_items", "--all")[1].splitlines()) == 2
    assert [json.loads(l)["id"] for l in run(capsys, "--dir", reg, "list", "open_items", "--status", "dropped")[1].splitlines()] == ["OI-002"]
    counts = json.loads(run(capsys, "--dir", reg, "summary")[1])
    assert counts["open_items"] == {"open": 1, "dropped": 1} and counts["proposals"] == {}
    text = run(capsys, "--dir", reg, "render", "--period", "2027-07")[1]
    assert "## Open items (1)" in text and "Freight accrual $4,200, owner unassigned, due 2027-08-05" in text
    assert "- 1010 Operating cash: tied, difference $0.00" in text
    assert "## Owed by Jordan (1)" in text and "(3) Sign the lease memo" in text


@pytest.mark.parametrize("table,field", [
    ("open_items", "status=done"), ("open_items", "status=dropped"), ("risk_register", "status=closed"),
    ("rec_status", "status=tied"), ("owed_by_owner", "status=answered"), ("proposals", "status=applied"),
    ("open_items", "closed_by=Dana"), ("open_items", "closed_at=2030-01-01T00:00:00Z"),
])
def test_add_never_writes_a_closed_row(tmp_path, capsys, table, field):
    code, _, err = run(capsys, "--dir", tmp_path, "add", table, "--by", "Dana", "--field", field)
    assert code == 1 and "close" in err and len(err.strip().splitlines()) == 1
    assert register.load(tmp_path, table) == []
