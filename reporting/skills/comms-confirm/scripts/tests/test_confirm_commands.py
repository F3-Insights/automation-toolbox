"""How confirm.py reaches the Portal and the owner: plain scripts by owning skill, never PATH,
with CONFIRM_PORTAL_CMD and CONFIRM_NOTIFY_CMD still replacing them."""

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import confirm  # noqa: E402


def test_portal_runs_the_sibling_script(monkeypatch):
    monkeypatch.delenv("CONFIRM_PORTAL_CMD", raising=False)
    argv = confirm.portal_argv()
    assert argv[-1] == str(SCRIPTS / "confirm_portal.py")


def test_portal_call_reaches_the_script_with_nothing_on_path(monkeypatch):
    monkeypatch.delenv("CONFIRM_PORTAL_CMD", raising=False)
    monkeypatch.setenv("PATH", "")
    with pytest.raises(confirm.Bad) as err:
        confirm.portal("no-such-subcommand", {})
    # argparse inside confirm_portal.py answered, so the script itself ran
    assert "invalid choice" in str(err.value)
    assert "not on PATH" not in str(err.value)


def test_notify_runs_comms_reply_to_email_script(monkeypatch, tmp_path):
    """The script comes from this toolbox checkout, not from ~/.claude/skills."""
    monkeypatch.delenv("CONFIRM_NOTIFY_CMD", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    out = confirm.notify("Title", ["one"], dry_run=True)
    # A copy in a department finds its neighbour beside it; the shared source finds the
    # department that holds it. Either way it is this checkout's file.
    found = Path(out["argv"][1])
    assert found.parts[-3:] == ("comms-reply-to-email", "scripts", "notify_owner.py")
    assert found.is_relative_to(SCRIPTS.parents[3]) and found.is_file()
    assert out["argv"][2:] == ["--title", "Title", "--bullet", "one"]


def test_notify_says_where_the_script_should_be(monkeypatch, tmp_path):
    monkeypatch.delenv("CONFIRM_NOTIFY_CMD", raising=False)
    monkeypatch.setattr(confirm, "skill_file", lambda skill, *parts: tmp_path.joinpath(skill, *parts))
    with pytest.raises(confirm.Bad) as err:
        confirm.notify("Title", ["one"])
    assert "comms-reply-to-email/scripts/notify_owner.py" in str(err.value)


def test_overrides_still_replace_both(monkeypatch):
    monkeypatch.setenv("CONFIRM_PORTAL_CMD", "fake-portal --x")
    monkeypatch.setenv("CONFIRM_NOTIFY_CMD", "fake-notify")
    assert confirm.portal_argv() == ["fake-portal", "--x"]
    assert confirm.notify("T", [], dry_run=True)["argv"][:1] == ["fake-notify"]
