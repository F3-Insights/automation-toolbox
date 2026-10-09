"""The folder fixture for these tests; the builder lives in month_end_fixture.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from month_end_fixture import build_folder  # noqa: E402


@pytest.fixture
def folder(tmp_path):
    return build_folder(tmp_path)
