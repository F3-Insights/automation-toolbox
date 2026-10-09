"""process_flow_template.py and the swim-lane generator it stamps."""

import importlib.util

from conftest import SCRIPTS, run
import process_flow_template as tpl


def generator():
    spec = importlib.util.spec_from_file_location("gen", SCRIPTS / "swimlane_generator.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_generator_builds_both_pages_and_escapes_text():
    g = generator()
    assert g.build().startswith("<!doctype html>") and "TO-BE" in g.build()
    assert "setAll" not in g.build_asis_only()
    node = g.N("x1", g.CUST, 0, "step", "A & B <tag>", "sub")
    node["_row"] = 0
    assert "&amp;" in g.render_node(node) and "<tag>" not in g.render_node(node)


def test_copy_to_stamps_and_refuses_to_overwrite_without_force(tmp_path, capsys):
    assert run(tpl.main, capsys=capsys)[0] == 2
    assert run(tpl.main, "--copy-to", tmp_path, capsys=capsys)[0] == 0
    target = tmp_path / "process_flow.py"
    assert target.read_text() == (SCRIPTS / "swimlane_generator.py").read_text()
    target.write_text("edited")
    code, text = run(tpl.main, "--copy-to", tmp_path, capsys=capsys)
    assert code == 2 and "--force" in text and target.read_text() == "edited"
    assert run(tpl.main, "--copy-to", tmp_path, "--force", capsys=capsys)[0] == 0
    assert target.read_text() != "edited"


def test_demo_writes_both_html_files(tmp_path, capsys):
    code, text = run(tpl.main, "--demo", "--out", tmp_path, capsys=capsys)
    assert code == 0, text
    assert sorted(p.name for p in tmp_path.glob("*.html")) == ["example-process-flow-asis-only.html",
                                                                "example-process-flow.html"]
    assert not (tmp_path / "_process_flow_demo.py").exists()


def test_the_generator_alone_writes_nothing_without_an_output_folder(tmp_path):
    import subprocess, sys
    from pathlib import Path
    script = Path(__file__).resolve().parent.parent / "swimlane_generator.py"
    before = set(script.parent.iterdir())
    help_run = subprocess.run([sys.executable, str(script), "--help"], cwd=tmp_path, capture_output=True, text=True)
    bare_run = subprocess.run([sys.executable, str(script)], cwd=tmp_path, capture_output=True, text=True)
    assert help_run.returncode == 0 and bare_run.returncode == 2
    assert set(script.parent.iterdir()) == before and not list(tmp_path.iterdir())
    subprocess.run([sys.executable, str(script), "--out", str(tmp_path)], check=True, capture_output=True)
    assert sorted(p.name for p in tmp_path.glob("*.html")) == ["example-process-flow-asis-only.html", "example-process-flow.html"]
