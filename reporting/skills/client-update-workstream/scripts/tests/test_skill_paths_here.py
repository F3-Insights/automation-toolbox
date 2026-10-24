"""_skill_paths finds another skill's file through this toolbox checkout."""

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("client_update_workstream_skill_paths", SCRIPTS / "_skill_paths.py")
sp = sys.modules["client_update_workstream_skill_paths"] = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sp)


def test_the_toolbox_root_is_this_checkout():
    assert sp.toolbox_root(SCRIPTS / "_skill_paths.py") == SCRIPTS.parents[3]


def test_a_skill_in_another_department_is_found_in_the_checkout():
    found = sp.skill_file("comms-reply-to-email", "SKILL.md", start=SCRIPTS / "_skill_paths.py")
    assert found.is_file() and SCRIPTS.parents[3] in found.parents
