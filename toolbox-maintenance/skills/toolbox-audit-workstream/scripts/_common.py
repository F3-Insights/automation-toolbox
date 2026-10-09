"""What the toolbox-audit scripts share: the owner's settings, the private-name denylist, the
Run folder's files, frontmatter reading, and the fix rule.

The fix rule is the one kind of change the toolbox audit makes itself, on a branch for review,
never merged:

- only in `<department>/agents/<name>.md` and `<department>/skills/<name>/SKILL.md`, files that
  already exist;
- only the frontmatter's `name` and `description` values; every other key, the key order and the
  body stay byte for byte;
- the result parses as YAML, its `name` equals the file's (or the skill folder's) name, its
  description is non-empty and at most 700 characters, and it brings in no private name and no
  home path;
- every changed file belongs to a finding the session marked `fixed`.
"""

import json
import os
import re
import subprocess
import tomllib
from pathlib import Path

import yaml

SKILL = "toolbox-audit-workstream"
DESCRIPTION_LIMIT = 700
FIX_KEYS = ("name", "description")
LEVELS = ("error", "warning", "info")
STATES = ("proposed", "fixed", "task", "dismissed")
TOP_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:")
HOME_PATH = re.compile(r"(?:/home/|/Users/|/mnt/c/Users/)(?!<)[A-Za-z0-9._-]+")
DEFAULT_DENYLIST = Path("~/.config/f3i-toolbox/denylist.txt").expanduser()


class AuditError(Exception):
    """A bad argument or a Run folder the scripts cannot use: exit 2."""


def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


def toolbox_repo(given=None):
    """The toolbox checkout to audit: --repo, else the `repo` setting under [toolbox-audit-workstream]."""
    value = given or settings(SKILL).get("repo")
    if not value:
        raise AuditError(f"no toolbox checkout: pass --repo or set `repo` under [{SKILL}] in the settings file")
    path = Path(str(value)).expanduser().resolve()
    if not path.is_dir():
        raise AuditError(f"{path} is not a folder")
    return path


def load_denylist():
    """The private names, as (term, compiled pattern), from the same files the toolbox check reads:
    each file in F3I_TOOLBOX_DENYLIST (separated by ":") and ~/.config/f3i-toolbox/denylist.txt.
    One term per line, "#" a comment, "=" case-sensitive, "@" another list file to read."""
    paths = [Path(p).expanduser() for p in os.environ.get("F3I_TOOLBOX_DENYLIST", "").split(":") if p]
    if DEFAULT_DENYLIST.exists():
        paths.append(DEFAULT_DENYLIST)
    terms, seen = [], set()
    while paths:
        path = paths.pop(0)
        if not path.exists() or path.resolve() in seen:
            continue
        seen.add(path.resolve())
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("@"):
                paths.append(Path(line[1:]).expanduser())
                continue
            exact = line.startswith("=")
            term = line[1:] if exact else line
            terms.append((term, re.compile(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", 0 if exact else re.I)))
    return terms


def name_hits(text, denylist):
    """The denylist terms found in text (never printed: callers count them)."""
    return {term for term, rx in denylist if rx.search(text)}


def scrub(value, denylist):
    """value with every denylisted name replaced by "(withheld)", in every string of a dict or
    list too, so nothing a script prints or stores carries a private name."""
    if isinstance(value, str):
        for _term, rx in denylist:
            value = rx.sub("(withheld)", value)
        return value
    if isinstance(value, dict):
        return {scrub(k, denylist): scrub(v, denylist) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v, denylist) for v in value]
    return value


def read_json(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise AuditError(f"{path}: {exc}") from None
    return data if isinstance(data, dict) else None


def write_json(path, data):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


def run_folder(run):
    path = Path(run).expanduser()
    if not path.is_dir():
        raise AuditError(f"{path} is not a folder")
    return path


def truthy(value):
    """A launch value: '' or None is not given; true, yes, 1 and on are true."""
    return str(value or "").strip().lower() in ("true", "yes", "1", "on")


def findings_of(run):
    items = (read_json(Path(run) / "findings.json") or {}).get("findings")
    return [f for f in items if isinstance(f, dict)] if isinstance(items, list) else []


def one_line(text):
    return " ".join(str(text or "").split())


# --- frontmatter -------------------------------------------------------------------------

def split_text(text):
    """(the frontmatter's lines, the rest of the file), or (None, text) when there is none."""
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---", 4)
    if end < 0:
        return None, text
    return text[4:end].split("\n"), text[end:]


def key_blocks(lines):
    """The frontmatter as (top-level key, its lines' text) in order; indented lines and lines that
    start no key belong to the block above them."""
    blocks = []
    for line in lines:
        m = TOP_KEY.match(line)
        if m and not line[:1].isspace():
            blocks.append((m.group(1), [line]))
        elif blocks:
            blocks[-1][1].append(line)
        else:
            blocks.append(("", [line]))
    return [(k, "\n".join(v)) for k, v in blocks]


def parse_frontmatter(text):
    """(the mapping, None) or (None, why it does not parse)."""
    lines, _ = split_text(text)
    if lines is None:
        return None, "no frontmatter"
    try:
        meta = yaml.safe_load("\n".join(lines))
    except yaml.YAMLError as exc:
        first = str(exc).strip().splitlines()
        return None, f"frontmatter does not parse as YAML ({first[0] if first else 'error'})"
    if not isinstance(meta, dict):
        return None, "frontmatter is not a mapping"
    return meta, None


def expected_name(rel):
    """The name a fixable file must carry, or None when the path is outside the fix rule."""
    parts = Path(rel).parts
    if len(parts) == 3 and parts[1] == "agents" and rel.endswith(".md"):
        return Path(rel).stem
    if len(parts) == 4 and parts[1] == "skills" and parts[3] == "SKILL.md":
        return parts[2]
    return None


# --- git and the fix rule -----------------------------------------------------------------

def git(*args, cwd, check=True):
    done = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False)
    if check and done.returncode != 0:
        raise AuditError(f"git {' '.join(args[:3])}: {(done.stderr or done.stdout).strip()[:300]}")
    return done


def worktree_paths(repo):
    """Every working tree of the repository: the live checkout and each linked worktree."""
    out = git("worktree", "list", "--porcelain", cwd=repo).stdout
    return [Path(line[len("worktree "):]).resolve() for line in out.splitlines() if line.startswith("worktree ")]


def refuse_run_inside(run, repo):
    """A Run folder inside any working tree of the repository (the live checkout above all) is
    refused: the fix worktree, the scan and the Run's private files must never land in one."""
    top = Path(git("rev-parse", "--show-toplevel", cwd=repo).stdout.strip()).resolve()
    for tree in [top, *worktree_paths(repo)]:
        if run.resolve().is_relative_to(tree):
            raise AuditError(f"the Run folder is inside the repository's working tree ({tree}); use a Run folder outside it")
    return top


def changed_files(worktree):
    """(status, path) for every change in the worktree against its HEAD, untracked included."""
    rows = []
    for line in git("status", "--porcelain=v1", "-uall", cwd=worktree).stdout.splitlines():
        if len(line) > 3:
            rows.append((line[:2].strip() or "?", line[3:].strip().strip('"')))
    return rows


def check_file(rel, old, new, denylist):
    """Why changing `rel` from `old` to `new` breaks the fix rule (empty when it does not)."""
    want = expected_name(rel)
    if want is None:
        return [f"{rel}: outside the fix rule (only <department>/agents/<name>.md and <department>/skills/<name>/SKILL.md)"]
    old_lines, old_body = split_text(old)
    new_lines, new_body = split_text(new)
    if old_lines is None or new_lines is None:
        return [f"{rel}: has no frontmatter to fix"]
    problems = []
    if old_body != new_body:
        problems.append(f"{rel}: the body changed; only frontmatter name and description may")
    old_blocks, new_blocks = key_blocks(old_lines), key_blocks(new_lines)
    if [k for k, _ in old_blocks] != [k for k, _ in new_blocks]:
        problems.append(f"{rel}: the frontmatter keys changed ({[k for k, _ in old_blocks]} to {[k for k, _ in new_blocks]})")
    else:
        for (key, before), (_, after) in zip(old_blocks, new_blocks):
            if before != after and key not in FIX_KEYS:
                problems.append(f"{rel}: frontmatter '{key or '(unkeyed)'}' changed; only name and description may")
    meta, why = parse_frontmatter(new)
    if meta is None:
        problems.append(f"{rel}: {why}")
        return problems
    if meta.get("name") != want:
        problems.append(f"{rel}: name is '{meta.get('name')}', must be '{want}'")
    desc = one_line(meta.get("description"))
    if not desc:
        problems.append(f"{rel}: no description")
    elif len(desc) > DESCRIPTION_LIMIT:
        problems.append(f"{rel}: description is {len(desc)} characters, over {DESCRIPTION_LIMIT}")
    added = name_hits(desc, denylist) - name_hits(old, denylist)
    if added:
        problems.append(f"{rel}: the description brings in {len(added)} private name(s)")
    if HOME_PATH.search(desc):
        problems.append(f"{rel}: the description has a home-directory path")
    return problems


def verify_fix(run, worktree, denylist):
    """The worktree's changes against the fix rule and the Run's findings: (files, problems)."""
    files, problems = [], []
    if not Path(worktree).is_dir():
        return files, problems
    fixed_files = {str(p) for f in findings_of(run) if f.get("state") == "fixed" for p in (f.get("files") or [])}
    for status, rel in changed_files(worktree):
        files.append(rel)
        if status != "M":
            problems.append(f"{rel}: {'added' if status in ('?', 'A', '??') else 'status ' + status}; the fix rule only edits files that exist")
            continue
        old = git("show", f"HEAD:{rel}", cwd=worktree).stdout
        new = (Path(worktree) / rel).read_text(encoding="utf-8")
        problems.extend(check_file(rel, old, new, denylist))
        if rel not in fixed_files:
            problems.append(f"{rel}: changed, but no finding marked fixed names it in files")
    return files, problems
