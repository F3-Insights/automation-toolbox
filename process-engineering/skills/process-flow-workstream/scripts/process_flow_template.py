"""Stamp the swim-lane process-flow generator into an engagement folder, or run its demo.

The generator (swimlane_generator.py beside this script) is meant to be copied and edited: its
LANES and SECTIONS are the content, its render functions the engine, and the HTML it writes a
build artifact. This command makes the copy so the engagement owns its diagram, and can run the
shipped demo so you see the output before editing.

    process_flow_template.py --copy-to DIR [--name process_flow.py] [--force]
    process_flow_template.py --demo [--out DIR]

--copy-to writes DIR/<name> (DIR created if missing) and refuses to overwrite without --force.
--demo writes example-process-flow.html and example-process-flow-asis-only.html into --out
(default the current folder). Exit 0 on success, 2 on a bad argument or a refused overwrite.

Example:
    python3 process_flow_template.py --copy-to ./process-flows
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

GENERATOR = Path(__file__).resolve().parent / "swimlane_generator.py"


def main(argv=None):
    p = argparse.ArgumentParser(description="Stamp the process-flow generator into an engagement folder, or run the demo.")
    p.add_argument("--copy-to", dest="dest", default=None, help="Folder to stamp the generator into (created if missing)")
    p.add_argument("--name", default="process_flow.py", help="File name for the stamped copy")
    p.add_argument("--demo", action="store_true", help="Run the shipped demo and write its two HTML files")
    p.add_argument("--out", dest="out_dir", default=".", help="Where --demo writes")
    p.add_argument("--force", action="store_true", help="Overwrite an existing stamped copy")
    a = p.parse_args(argv)
    if not (a.dest or a.demo):
        print("Pass --copy-to <dir> or --demo.", file=sys.stderr)
        return 2
    if a.dest:
        target = Path(a.dest).expanduser() / a.name
        if target.exists() and not a.force:
            print(f"{target} exists; pass --force to overwrite.", file=sys.stderr)
            return 2
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(GENERATOR, target)
        print(f"Stamped {target}")
        print(f"Next: edit LANES and SECTIONS, then `python3 {target}` and open the HTML it writes.")
    if a.demo:
        out = Path(a.out_dir).expanduser()
        out.mkdir(parents=True, exist_ok=True)
        res = subprocess.run([sys.executable, str(GENERATOR), "--out", str(out)], capture_output=True, text=True)
        if res.returncode != 0:
            print(f"the demo failed: {res.stderr.strip()[-300:]}", file=sys.stderr)
            return 1
        written = sorted(p.name for p in out.glob("example-process-flow*.html"))
        print(f"Demo rendered into {out}: {', '.join(written) if written else 'nothing written'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
