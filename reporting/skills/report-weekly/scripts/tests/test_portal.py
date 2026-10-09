"""_portal.py: a malformed Portal answer is a failed call, never a crash."""

import pytest

from _common import Fail
from _portal import Portal


@pytest.mark.parametrize("raw", ["{not json", "[1, 2]", '{"result": {"content": ["text"]}}'])
def test_an_unreadable_response_is_a_fail(raw, monkeypatch):
    portal = Portal(url="https://portal.example.test/mcp", auth="Bearer x")

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return raw.encode()

    monkeypatch.setattr("_portal.OPENER.open", lambda *a, **k: Response())
    with pytest.raises(Fail):
        portal.call("update_task", {"id": "t1"})
    assert portal.safe_call("update_task", {"id": "t1"}) is None
