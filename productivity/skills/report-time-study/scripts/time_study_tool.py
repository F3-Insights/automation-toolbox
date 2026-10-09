"""Run one command of the time-study tool against a home folder.

The time-study tool is a separate checkout holding a `timestudy` Python package. This script
runs `python -m timestudy --home HOME COMMAND ARGS` from that checkout, so a session needs one
plain command instead of changing folders first.

Inputs: HOME (the tool's private home folder; default the setting `home` under
[report-time-study]), COMMAND (build, summary, dashboard, precheck or collect) and any ARGS,
passed through unchanged. The checkout is `--repo`, else the setting `repo` under
[report-time-study], else HOME's parent folder when it holds the `timestudy` package.

Prints what the tool printed. `--save FILE` also writes the tool's output to FILE when it
succeeds. The exit code is the tool's own; 2 on a bad argument, a missing home or no checkout.

Example:
    python3 time_study_tool.py --save ~/timestudy/private/out/summary-2030-09-01_to_2030-09-14.txt \
        ~/timestudy/private summary
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _common import TOOL_COMMANDS, Bad, fail, home_or_setting, run_tool


def main(argv=None):
    ap = argparse.ArgumentParser(prog="time-study-tool", description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", default="", help="the time-study checkout")
    ap.add_argument("--save", default="", help="also write the command's output to this file")
    ap.add_argument("home", help="the tool's home folder")
    ap.add_argument("command", help=" | ".join(TOOL_COMMANDS))
    ap.add_argument("args", nargs=argparse.REMAINDER, help="passed to the tool unchanged")
    a = ap.parse_args(argv)
    try:
        code, out, err = run_tool(home_or_setting(a.home), a.command.strip(), a.args, repo=a.repo.strip() or None)
    except Bad as exc:
        return fail(exc)
    sys.stdout.write(out)
    sys.stderr.write(err)
    if a.save.strip() and code == 0:
        Path(a.save.strip()).expanduser().write_text(out, encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main())
