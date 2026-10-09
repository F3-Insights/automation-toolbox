"""Run every skill's script tests, one skill at a time, then the setup tests.

Each skill's scripts share helper names such as `_common.py`, so the skills are tested
in separate pytest processes rather than one. Prints one line per skill and a total;
exits non-zero if any skill fails.

    .venv/bin/python scripts/run_tests.py            # every skill
    .venv/bin/python scripts/run_tests.py accounting # one department
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str]) -> int:
    pattern = f"{argv[0]}/skills/*/scripts/tests" if argv else "*/skills/*/scripts/tests"
    failed = []
    suites = sorted(ROOT.glob(pattern)) + ([] if argv else [ROOT / "setup" / "tests"])
    for tests in suites:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(tests)],
            cwd=tests.parent, capture_output=True, text=True,
        )
        last = (result.stdout.strip().splitlines() or ["no output"])[-1]
        owner = tests.parent.parent if tests.parent.name == "scripts" else tests.parent
        print(f"{owner.relative_to(ROOT)}: {last}")
        if result.returncode != 0:
            failed.append(tests)
    print(f"{len(failed)} skill(s) failing", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
