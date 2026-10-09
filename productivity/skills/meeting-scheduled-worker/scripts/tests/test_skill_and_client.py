"""Every result a script returns is named in SKILL.md, and the Portal client's guards hold.

The codes come from each script's declared tuple, and a second check reads the script's
source for every status, stage and refusal literal, so a code added without being declared
fails here, and a declared code the skill never names fails too.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _common as c  # noqa: E402
import meeting_acknowledge  # noqa: E402
import meeting_existing  # noqa: E402
import meeting_fetch  # noqa: E402
import meeting_pending  # noqa: E402
import meeting_publish  # noqa: E402
import meeting_validate  # noqa: E402

SCRIPTS = Path(__file__).resolve().parents[1]
SKILL = (SCRIPTS.parent / "SKILL.md").read_text(encoding="utf-8")
DECLARED = {
    meeting_pending: meeting_pending.STATUSES,
    meeting_existing: meeting_existing.STAGES,
    meeting_fetch: meeting_fetch.STATUSES,
    meeting_validate: meeting_validate.STATUSES,
    meeting_publish: meeting_publish.STATUSES + tuple(meeting_publish.REFUSALS),
    meeting_acknowledge: meeting_acknowledge.STATUSES + meeting_acknowledge.CODES,
}
NO_BRANCH = {"would_publish", "would_acknowledge", "refused"}


@pytest.mark.parametrize("module", list(DECLARED), ids=lambda m: m.__name__)
def test_each_declared_code_is_named_in_the_skill(module):
    missing = [code for code in DECLARED[module] if code not in NO_BRANCH and f"`{code}`" not in SKILL]
    assert not missing, f"SKILL.md never names {missing}"


@pytest.mark.parametrize("module", list(DECLARED), ids=lambda m: m.__name__)
def test_every_code_in_the_source_is_declared(module):
    source = Path(module.__file__).read_text(encoding="utf-8")
    if module is meeting_acknowledge:
        source = (SCRIPTS / "_common.py").read_text(encoding="utf-8").split("ACK_CODES = ", 1)[1]
    found = set(re.findall(r'"(?:status|stage)": "([a-z_]+)"', source))
    found |= set(re.findall(r'[Rr]efused\("([A-Z_]+)"', source))
    found |= set(re.findall(r'"code": "([A-Z_]+)"', source))
    assert found and found <= set(DECLARED[module]), sorted(found - set(DECLARED[module]))


@pytest.fixture
def mcp_config(tmp_path, monkeypatch):
    def make(url="https://portal.example.com/mcp", auth="Bearer ${PORTAL_TOKEN}"):
        cfg = tmp_path / "mcp.json"
        cfg.write_text(json.dumps({"mcpServers": {"insights-portal": {"url": url, "headers": {"Authorization": auth}}}}))
        settings = tmp_path / "settings.toml"
        settings.write_text(f'portal_mcp_config = "{cfg}"\n')
        monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(settings))
        monkeypatch.delenv(c.TOKEN_ENV, raising=False)
    return make


def test_the_endpoint_needs_its_setting(tmp_path, monkeypatch):
    monkeypatch.setenv("F3I_TOOLBOX_SETTINGS", str(tmp_path / "none.toml"))
    with pytest.raises(c.Stop, match="portal_mcp_config"):
        c.endpoint()


def test_the_token_comes_from_the_environment(mcp_config, monkeypatch):
    mcp_config()
    with pytest.raises(c.Stop, match="PORTAL_TOKEN"):
        c.endpoint()
    monkeypatch.setenv("PORTAL_TOKEN", "abc123")
    assert c.endpoint() == ("https://portal.example.com/mcp", "Bearer abc123")
    monkeypatch.setenv(c.TOKEN_ENV, "override")
    assert c.endpoint()[1] == "Bearer override"


@pytest.mark.parametrize("url", ["http://portal.example.com/mcp", "ftp://localhost/x"])
def test_plain_http_only_to_localhost(mcp_config, monkeypatch, url):
    mcp_config(url=url)
    monkeypatch.setenv("PORTAL_TOKEN", "abc123")
    with pytest.raises(c.Stop, match="HTTPS"):
        c.endpoint()
    mcp_config(url="http://localhost:8080/mcp")
    assert c.endpoint()[0] == "http://localhost:8080/mcp"


def test_a_token_is_never_printed():
    assert "abc123" not in c.safe("Authorization: Bearer abc123")


def test_a_dry_run_runner_refuses_a_real_publish(tmp_path, monkeypatch):
    monkeypatch.setenv(c.DRY_RUN_ENV, "1")
    folder = tmp_path / "recordings" / "a1000000-0000-4000-8000-00000000000a-0123456789abcdef"
    folder.mkdir(parents=True)
    out = meeting_publish.publish(None, folder)
    assert out["code"] == "DRY_RUN" and out["recording_id"] == "a1000000-0000-4000-8000-00000000000a"
    assert c.dry_run_refusal(True) is None
