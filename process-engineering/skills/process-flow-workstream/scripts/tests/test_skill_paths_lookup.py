"""process_flow_prepare finds its default reference models through _skill_paths: in a plugin
the reference-process-models skill sits beside this one, in the same department."""

from pathlib import Path

import _skill_paths  # conftest puts scripts/ on the path

SCRIPTS = Path(__file__).resolve().parent.parent
DEPARTMENT = SCRIPTS.parent.parent.parent


def test_reference_model_found_in_this_department():
    found = _skill_paths.skill_file("reference-process-models", "order-to-cash.md")
    assert found.is_file()
    assert found.resolve().parent.parent.parent == DEPARTMENT


def test_missing_file_names_the_last_place_looked():
    found = _skill_paths.skill_file("reference-process-models", "no-such-model.md")
    assert not found.exists()
    assert found.name == "no-such-model.md"
