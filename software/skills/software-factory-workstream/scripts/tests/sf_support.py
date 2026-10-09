"""Helpers the software-factory tests share: a fake for _common.run (the one door to gh and
git), and small git helpers. conftest.py puts this folder and the scripts on the import path."""

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import _common  # noqa: E402

REPO = "acme/widgets"
OWNER = "dana-acme"
OTHER = "sam-northwind"


class Fake:
    """Answers each command from routes (longest matching argv prefix wins) and records every call.
    With `passthrough_git`, git commands with no route run for real."""

    def __init__(self, real=None):
        self.calls, self.routes, self.real = [], [], real

    def on(self, *prefix, out="", code=0, fn=None):
        self.routes.append((tuple(prefix), out if isinstance(out, str) else json.dumps(out), code, fn))

    @staticmethod
    def key(argv):
        return ["git"] + argv[3:] if argv[:2] == ["git", "-C"] else argv

    def __call__(self, argv, input=None, timeout=0):
        argv = [str(a) for a in argv]
        self.calls.append(argv)
        key = self.key(argv)
        best = None
        for route in self.routes:
            if tuple(key[:len(route[0])]) == route[0] and (best is None or len(route[0]) >= len(best[0])):
                best = route
        if best is None:
            if self.real and key[0] == "git":
                return self.real(argv)
            return _common.Result(argv, 1, "", f"fake: no route for {' '.join(key)}")
        _, out, code, fn = best
        if fn is not None:
            got = fn(argv)
            if isinstance(got, _common.Result):
                return got
            out = got if isinstance(got, str) else json.dumps(got)
        return _common.Result(argv, code, out, "" if code == 0 else "fake failure")

    def find(self, *prefix):
        return [c for c in self.calls if tuple(self.key(c)[:len(prefix)]) == prefix]

    def writes(self):
        verbs = {("pr", "create"), ("pr", "edit"), ("pr", "merge"), ("pr", "comment"), ("issue", "comment"),
                 ("issue", "edit"), ("label", "create")}
        return [c for c in self.calls if (self.key(c)[:2] == ["git", "push"])
                or (c[0] == "gh" and tuple(c[1:3]) in verbs)]

def sh(*args, cwd):
    return subprocess.run(list(args), cwd=str(cwd), check=True, capture_output=True, text=True).stdout


def commit(root, files, message="change"):
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    sh("git", "add", "-A", cwd=root)
    sh("git", "commit", "-q", "-m", message, cwd=root)
    return sh("git", "rev-parse", "HEAD", cwd=root).strip()


def make_origin(tmp_path, files, branches=("main", "development")):
    """A bare origin seeded with `files` on each branch, and its clone at repos/widgets."""
    origin = tmp_path / "origin.git"
    sh("git", "init", "-q", "--bare", "-b", "main", str(origin), cwd=tmp_path)
    seed = tmp_path / "seed"
    sh("git", "init", "-q", "-b", "main", str(seed), cwd=tmp_path)
    commit(seed, files, "seed")
    sh("git", "remote", "add", "origin", str(origin), cwd=seed)
    sh("git", "push", "-q", "origin", *[f"main:{b}" for b in branches], cwd=seed)
    clone = tmp_path / "repos" / "widgets"
    clone.parent.mkdir(parents=True, exist_ok=True)
    sh("git", "clone", "-q", str(origin), str(clone), cwd=tmp_path)
    return origin, clone
