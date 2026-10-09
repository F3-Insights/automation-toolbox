"""detect_project_type.sh: one JSON object describing the project's stack."""

import json
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "detect_project_type.sh"


def detect(folder):
    out = subprocess.run(["bash", str(SCRIPT), str(folder)], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_python_project(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    meta = detect(tmp_path)
    assert meta["language"] == "python" and meta["test_runner"] == "pytest"
    assert meta["has_ci"] is True and meta["has_docker"] is False


def test_next_project_with_pnpm(tmp_path):
    (tmp_path / "package.json").write_text('{"dependencies": {"next": "1"}, "devDependencies": {"vitest": "1"}}')
    (tmp_path / "tsconfig.json").write_text("{}")
    (tmp_path / "pnpm-lock.yaml").write_text("")
    meta = detect(tmp_path)
    assert (meta["language"], meta["framework"], meta["package_manager"]) == ("typescript", "nextjs", "pnpm")
    assert meta["test_command"] == "pnpm run test"


def test_dotnet_project(tmp_path):
    (tmp_path / "Lakeview.csproj").write_text("<Project/>")
    assert detect(tmp_path)["language"] == "csharp"


def test_unknown_and_bad_directory(tmp_path):
    assert detect(tmp_path)["language"] == "unknown"
    out = subprocess.run(["bash", str(SCRIPT), str(tmp_path / "missing")], capture_output=True, text=True)
    assert out.returncode == 1
