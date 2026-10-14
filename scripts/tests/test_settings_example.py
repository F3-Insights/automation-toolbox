"""settings.example.toml and library.yaml: the example holds every key docs/settings.md documents.

docs/settings.md is where a key is documented; settings.example.toml is what a runtime (or the
owner) starts the settings file from, and library.yaml points a runtime at both (ADR 0005).
These tests keep the three in step: every documented key is in the example and every key in
the example is documented, each with its one-line comment, and the example reads as TOML both
as it ships (all commented out) and with every key switched on.
"""
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "settings.md"
EXAMPLE = ROOT / "settings.example.toml"
DECLARATION = ROOT / "library.yaml"

ROW = re.compile(r"^\| `([^`]+)` \|")
KEY_LINE = re.compile(r"^#? ?([A-Za-z0-9_.-]+) = ")
TABLE_LINE = re.compile(r"^\[([A-Za-z0-9_.-]+)\]\s*$")


def documented() -> set[tuple[str, str]]:
    """(table, key) for every key the tables of docs/settings.md list; "" is the top level.
    The environment variables are not settings-file keys."""
    out, table, inside = set(), None, False
    for line in DOC.read_text().splitlines():
        if line.startswith("## "):
            inside = line.strip() in ("## Top-level keys", "## Per-skill tables")
            table = "" if line.strip() == "## Top-level keys" else None
        elif line.startswith("### [") and inside:
            table = line[4:].strip().strip("[]")
        elif inside and table is not None and (m := ROW.match(line)):
            out.add((table, m.group(1)))
    return out


def example_keys() -> list[tuple[str, str, int]]:
    """(table, key, line index) for every key line of the example, commented out or not."""
    out, table = [], ""
    lines = EXAMPLE.read_text().splitlines()
    for i, line in enumerate(lines):
        if m := TABLE_LINE.match(line):
            table = m.group(1)
        elif m := KEY_LINE.match(line):
            out.append((table, m.group(1), i))
    return out


def test_every_documented_key_is_in_the_example_and_back():
    doc = documented()
    example = {(t, k) for t, k, _ in example_keys()}
    assert len(doc) > 50
    assert sorted(doc - example) == [], "documented in docs/settings.md, missing from settings.example.toml"
    assert sorted(example - doc) == [], "in settings.example.toml, not documented in docs/settings.md"


def test_each_key_appears_once_with_a_one_line_comment_above_it():
    keys = example_keys()
    assert len(keys) == len({(t, k) for t, k, _ in keys})
    lines = EXAMPLE.read_text().splitlines()
    for table, key, i in keys:
        above = lines[i - 1]
        assert above.startswith("# ") and not KEY_LINE.match(above), f"[{table}] {key}: no comment line above it"
        assert "(" in above and ("required" in above or "optional" in above), \
            f"[{table}] {key}: the comment says what it is and whether it is required"


def test_the_example_reads_as_toml_as_shipped_and_switched_on():
    text = EXAMPLE.read_text()
    shipped = tomllib.loads(text)
    assert all(v == {} for v in shipped.values()), "the example ships with every key commented out"
    switched_on = tomllib.loads(re.sub(r"(?m)^# ([A-Za-z0-9_.-]+ = )", r"\1", text))
    assert "portal_mcp_config" in switched_on and "timezone" in switched_on["daily-plan-method"]


def test_the_example_holds_no_private_path():
    text = EXAMPLE.read_text()
    assert not re.search(r"/home/|/Users/|[A-Za-z]:\\\\|/mnt/", text)
    paths = re.findall(r'"(~?/[^"]*)"', text)
    assert paths and all(p.startswith(("~/path/to/", "~/.claude/", "~/.codex/")) for p in paths), paths


def test_library_yaml_names_the_example_the_variable_and_the_default():
    text = DECLARATION.read_text()
    fields = dict(re.findall(r"(?m)^  (env|default|example): (\S+)\s*$", text))
    assert re.search(r"(?m)^settings:\s*$", text)
    assert (ROOT / fields["example"]) == EXAMPLE
    doc = DOC.read_text()
    assert f"`{fields['env']}`" in doc and f"`{fields['default']}`" in doc
