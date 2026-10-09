"""What the software factory's scripts share. SOFTWARE-FACTORY.md, beside this folder, is the contract.

- where a repository's clone, worktrees and ledger live (settings and environment);
- the factory's branch names and the repository's `.software-factory/` files;
- git with no route to GitHub, for the offline steps;
- the ledger: one CSV row per issue attempt, upserted by id, never deleted;
- the one door to `gh` and git for the GitHub-facing steps (`run`, which a test replaces);
- the reads of GitHub that sync and ship both make, and the merge rules they both apply.

Not a command; the scripts beside it import it.
"""

import csv
import fnmatch
import io
import json
import os
import re
import shlex
import subprocess
import tempfile
import tomllib
from datetime import datetime, timezone
from pathlib import Path

PROTECTED = frozenset({"main", "master", "prod", "production", "release", "live"})
BRANCH_PREFIX = "software-factory/"
ONBOARD_ISSUE = 0
ONBOARD_BRANCH = "software-factory/onboard"
BRANCH_RE = re.compile(r"^(?:software-factory/issue-([1-9]\d*)(?:-[a-z0-9][a-z0-9-]{0,39})?|software-factory/onboard)$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")

FACTORY_DIR = ".software-factory"
COMMANDS_FILE = ".software-factory/commands.yaml"
RULES_FILE = ".software-factory/SOFTWARE-FACTORY-RULES.md"
DEFAULT_INTEGRATION = "development"
STEP_ORDER = ("setup", "lint", "typecheck", "test", "build", "coverage")

LEDGER_NAME = "SOFTWARE-FACTORY-LEDGER.csv"
TITLES_NAME = "SOFTWARE-FACTORY-TITLES.json"
COLUMNS = ("id", "issue", "attempt", "state", "branch", "pr", "head_sha", "verify",
           "review", "risk", "note", "updated_at", "by")
STATES = ("triaged-build", "triaged-ask", "triaged-human", "skipped", "building", "verified",
          "failed", "reviewed", "pr-open", "merged", "released", "reopened", "abandoned")
VERIFY_VALUES = ("", "verified", "failed", "no-tests", "repro-not-shown")
REVIEW_VALUES = ("", "PASS", "FAIL")
RISK_VALUES = ("", "low", "normal", "one-way-door")

MARKER = "<!-- software-factory -->"   # every comment the factory posts carries it
FIRST_LINE = "From the software factory:"
PR_OPEN_LABEL = "software-factory:pr-open"
LABEL_PREFIX = "software-factory:"
SYNC_FILE = "SYNC.md"
SYNCED_PREFIX = "SYNCED:"
STALE_PREFIX = "STALE:"
EXCLUDED_LABELS = ("on-hold", "wontfix")
ISSUE_FIELDS = "number,title,labels,state,updatedAt,createdAt,assignees,author,comments,body"
PR_FIELDS = ("number,url,title,body,state,isDraft,headRefName,baseRefName,headRefOid,mergeable,"
             "mergeStateStatus,reviewDecision,statusCheckRollup,labels,author")
CHECK_OK = {"SUCCESS", "NEUTRAL", "SKIPPED"}


class FactoryError(Exception):
    """A repository the factory cannot work on, or a git command that failed (exit 1)."""


class UsageError(FactoryError):
    """A bad argument, a missing setting or an unreadable input (exit 2)."""


class GitHubError(Exception):
    """A gh or git command against GitHub failed; the message quotes the tail of its output."""


# ---------------------------------------------------------------------------------------------
# Settings and places


def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


def split_repo(repo):
    if not REPO_RE.match(repo or ""):
        raise UsageError(f"repo {repo!r} is not OWNER/NAME")
    return tuple(repo.split("/", 1))


def repos_dir():
    """Where the local clones live: $SOFTWARE_FACTORY_REPOS_DIR, else the setting repos_dir."""
    value = os.environ.get("SOFTWARE_FACTORY_REPOS_DIR") or settings("software-factory-workstream").get("repos_dir")
    if not value:
        raise UsageError("set repos_dir in [software-factory-workstream] (the folder holding the local clones)")
    return Path(value).expanduser()


def local_clone(repo):
    return repos_dir() / split_repo(repo)[1]


def worktree_path(repo, issue):
    owner, name = split_repo(repo)
    return repos_dir() / ".software-factory-worktrees" / f"{owner}__{name}" / f"issue-{int(issue)}"


def state_dir(repo):
    """$SOFTWARE_FACTORY_STATE_DIR, else <state_dir setting>/software-factory, else ~/.local/state/software-factory."""
    owner, name = split_repo(repo)
    base = os.environ.get("SOFTWARE_FACTORY_STATE_DIR")
    if not base:
        top = settings().get("state_dir")
        base = str(Path(top) / "software-factory") if top else "~/.local/state/software-factory"
    return Path(base).expanduser() / f"{owner}__{name}"


def ledger_path(repo):
    return state_dir(repo) / LEDGER_NAME


# ---------------------------------------------------------------------------------------------
# Names and rules


def slugify(text):
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:40].rstrip("-") or "change"


def branch_name(issue, slug=""):
    """software-factory/issue-<n>-<slug>, or exactly software-factory/onboard for issue 0."""
    return ONBOARD_BRANCH if int(issue) == ONBOARD_ISSUE else f"{BRANCH_PREFIX}issue-{int(issue)}-{slugify(slug)}"


def issue_of_branch(branch):
    """The issue a factory branch is for (0 for onboarding); None for any other branch."""
    m = BRANCH_RE.match(branch or "")
    if not m:
        return None
    return int(m.group(1)) if m.group(1) is not None else ONBOARD_ISSUE


def bare_branch(branch):
    return (branch or "").removeprefix("refs/heads/").removeprefix("origin/")


def is_onboarding(branch):
    return bare_branch(branch) == ONBOARD_BRANCH


def is_protected(branch, default_branch=""):
    bare = bare_branch(branch)
    return bare in PROTECTED or (bool(default_branch) and bare == default_branch)


def issue_label(issue):
    """How output names an issue: #7, or onboarding for issue 0."""
    try:
        return "onboarding" if int(issue) == ONBOARD_ISSUE else f"#{int(issue)}"
    except (TypeError, ValueError):
        return f"#{issue}"


def rules_fields(text):
    """The `- Name: value` lines of the rules file, keys lowercased, a trailing # comment dropped."""
    out = {}
    for line in (text or "").splitlines():
        m = re.match(r"^\s*-\s+([A-Za-z][A-Za-z -]*?):\s*(.*?)\s*$", line)
        if m:
            out[m.group(1).strip().lower()] = m.group(2).split("  #")[0].split(" #")[0].strip()
    return out


def yes(value):
    return str(value or "").strip().lower() in ("yes", "true", "on", "y")


_PLACEHOLDER = re.compile(r"^(?:@?echo(?:\s.*)?|@?true|:|@?exit\s+0|@?printf(?:\s.*)?)$", re.I)


def is_placeholder(command):
    """A command that does nothing (empty, true, :, exit 0, echo ..., printf ...), alone or chained."""
    parts = [p.strip() for p in re.split(r"&&|\|\||;", str(command or "")) if p.strip()]
    return all(_PLACEHOLDER.match(p) for p in parts)


def parse_commands(text):
    """{step: [{run, cwd}]} from commands.yaml, placeholders dropped. ValueError for a bad shape."""
    import yaml   # pyyaml: only the scripts that read commands.yaml need it
    try:
        data = yaml.safe_load(text) if (text or "").strip() else None
    except yaml.YAMLError as exc:
        raise ValueError(str(exc))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("commands.yaml is not a mapping of step to commands")
    out = {}
    for key, value in data.items():
        if key not in STEP_ORDER:
            continue   # an unknown key is not ours to run
        entries = []
        for item in value if isinstance(value, list) else ([] if value is None else [value]):
            if isinstance(item, str):
                run, cwd = item, "."
            elif isinstance(item, dict) and isinstance(item.get("run"), str):
                run, cwd = item["run"], str(item.get("cwd") or ".")
            else:
                raise ValueError(f"commands.yaml {key}: each entry is a command or {{run, cwd}}, not {item!r}")
            if not is_placeholder(run):
                entries.append({"run": run.strip(), "cwd": cwd.strip() or "."})
        if entries:
            out[key] = entries
    return out


# ---------------------------------------------------------------------------------------------
# Offline git (worktree, verify)


def offline_env(base=None):
    """An environment with no route to GitHub: no tokens, no SSH agent, no credential helper."""
    env = dict(os.environ if base is None else base)
    for key in list(env):
        if key.startswith("GH_") or key in ("GITHUB_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "SSH_AUTH_SOCK",
                                            "SSH_AGENT_PID", "GIT_ASKPASS", "SSH_ASKPASS"):
            env.pop(key)
    env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "credential.helper",
                "GIT_CONFIG_VALUE_0": "", "GH_CONFIG_DIR": "/nonexistent-software-factory-gh-config"})
    return env


def offline_git(*args, cwd, check=True):
    """git in `cwd` with no route to GitHub. With `check`, a failure raises FactoryError."""
    proc = subprocess.run(["git", *args], cwd=str(cwd), env=offline_env(), stdin=subprocess.DEVNULL,
                          capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise FactoryError(f"git {' '.join(args)} failed: {(proc.stderr or proc.stdout).strip()}")
    return proc


# ---------------------------------------------------------------------------------------------
# Time


def now_local():
    return datetime.now().astimezone().replace(microsecond=0)


def parse_time(value):
    """An ISO time as an aware datetime (a naive one is local time); None when unreadable."""
    value = str(value or "").strip()
    if not value:
        return None
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.astimezone()


def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------------------------
# The ledger


def atomic_write(path, text):
    """Write through a synced temporary file and a rename, keeping an existing file's permissions."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp",
                                         delete=False, encoding="utf-8", newline="")
    try:
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(handle.name, path.stat().st_mode & 0o777)
        os.replace(handle.name, path)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise


def _records(path):
    """The ledger's records, each (cells, the exact text it came from). Checks the header."""
    # A byte-order mark (as a spreadsheet saves CSV) is dropped; line endings are kept as written.
    text = path.read_bytes().decode("utf-8").removeprefix("\ufeff") if path.is_file() else ""
    if not text.strip():
        return []
    lines = text.splitlines(keepends=True)
    reader = csv.reader(iter(lines))
    out, used = [], 0
    for row in reader:
        out.append((row, "".join(lines[used:reader.line_num])))
        used = reader.line_num
    if [c.strip() for c in out[0][0]] != list(COLUMNS):
        raise UsageError(f"{path.name} does not start with the header {','.join(COLUMNS)}")
    return out


def read_ledger(repo):
    """The rows in file order, each a dict of the columns; the first row of an id wins."""
    rows, seen = [], set()
    for cells, _ in _records(ledger_path(repo))[1:]:
        row = {c: (v or "").strip() for c, v in zip(COLUMNS, list(cells) + [""] * len(COLUMNS))}
        if row["id"] and row["id"] not in seen:
            seen.add(row["id"])
            rows.append(row)
    return rows


def attempts(rows):
    """Rows grouped by issue, each list in attempt order."""
    out = {}
    for row in rows:
        if str(row.get("issue") or "").isdigit():
            out.setdefault(int(row["issue"]), []).append(row)
    for group in out.values():
        group.sort(key=lambda r: to_int(r["attempt"]))
    return out


def latest(rows):
    """Each issue's latest attempt: its current state."""
    return {issue: group[-1] for issue, group in attempts(rows).items()}


def read_titles(repo):
    try:
        data = json.loads((state_dir(repo) / TITLES_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {to_int(k): str(v) for k, v in (data or {}).items() if to_int(k) > 0 and v}


def _validate(issue, state, by, attempt, new_attempt, fields):
    """The checked values of one record call; UsageError names the bad one."""
    try:
        issue_n = int(str(issue).strip().lstrip("#"))
    except (TypeError, ValueError):
        raise UsageError(f"--issue {issue!r} is not an issue number")
    if issue_n < 0:
        raise UsageError(f"--issue {issue!r} is not an issue number (0 is onboarding)")
    if state not in STATES:
        raise UsageError(f"--state {state!r} is not one of {', '.join(STATES)}")
    if not (by or "").strip() or "\n" in by or "\r" in by:
        raise UsageError("--by must name who recorded the row")
    if attempt is not None and new_attempt:
        raise UsageError("give --attempt or --new-attempt, not both")
    if attempt is not None and (not str(attempt).strip().isdigit() or int(attempt) <= 0):
        raise UsageError(f"--attempt {attempt!r} must be a number, 1 or more")
    out = {}
    for name, value in fields.items():
        if value is None:
            continue
        value = " ".join(str(value).split()) if name == "note" else str(value).strip()
        if name == "branch" and any(c.isspace() for c in str(fields["branch"]).strip()):
            raise UsageError(f"--branch {fields['branch']!r} has whitespace in it")
        if name == "pr":
            value = value.lstrip("#")
            if value and not value.isdigit():
                raise UsageError(f"--pr {fields['pr']!r} is not a pull request number")
        if name == "head_sha":
            value = value.lower()
            if value and not SHA_RE.match(value):
                raise UsageError(f"--head-sha {fields['head_sha']!r} is not a commit SHA")
        if name == "review":
            value = value.upper()
        allowed = {"verify": VERIFY_VALUES, "review": REVIEW_VALUES, "risk": RISK_VALUES}.get(name)
        if allowed and value not in allowed:
            raise UsageError(f"--{name.replace('_', '-')} {fields[name]!r} is not one of "
                             f"{', '.join(v for v in allowed if v)} or ''")
        out[name] = value
    return issue_n, " ".join(by.split()), out


def record(repo, issue, state, by, attempt=None, new_attempt=False, title=None, now=None, **fields):
    """Upsert one ledger row, id <issue>:<attempt>; every other row keeps its exact text.

    `fields` are branch, pr, head_sha, verify, review, risk and note; one left out keeps its
    recorded value, '' clears it. A new head_sha without a new review clears the review, so a
    PASS never outlives the code it passed. Returns {id, action, path, row, warnings}.
    """
    split_repo(repo)
    issue_n, by, given = _validate(issue, state, by, attempt, new_attempt, fields)
    path = ledger_path(repo)
    records = _records(path)
    top = max((to_int(cells[2]) for cells, _ in records[1:] if len(cells) > 2 and to_int(cells[1]) == issue_n
               and str(cells[1]).strip().isdigit()), default=0)
    if new_attempt:
        number = top + 1
    elif attempt is not None:
        number = int(attempt)
        if number > top + 1:
            raise UsageError(f"--attempt {number} skips ahead: issue {issue_n}'s latest attempt is {top}")
    else:
        number = top or 1
    key = f"{issue_n}:{number}"

    index = next((i for i, (cells, _) in enumerate(records) if i and cells and cells[0].strip() == key), None)
    old = dict(zip(COLUMNS, [c.strip() for c in records[index][0]] + [""] * len(COLUMNS))) if index else {}
    row = {c: old.get(c, "") for c in COLUMNS}
    row.update(given)
    row.update(id=key, issue=str(issue_n), attempt=str(number), state=state, by=by,
               updated_at=(now or now_local()).isoformat(timespec="seconds"))
    review_cleared = bool(old.get("review")) and "review" not in given and \
        "head_sha" in given and given["head_sha"] != old.get("head_sha", "")
    if review_cleared:
        row["review"] = ""

    buffer = io.StringIO()
    terminator = "\r\n" if records and records[0][1].endswith("\r\n") else "\n"
    csv.writer(buffer, lineterminator=terminator).writerow([row[c] for c in COLUMNS])
    if not records:
        header = io.StringIO()
        csv.writer(header, lineterminator=terminator).writerow(COLUMNS)
        records = [(list(COLUMNS), header.getvalue())]
    if index:
        records[index] = (records[index][0], buffer.getvalue())
    else:
        if not records[-1][1].endswith(("\n", "\r")):
            records[-1] = (records[-1][0], records[-1][1] + terminator)
        records.append(([], buffer.getvalue()))
    atomic_write(path, "".join(text for _, text in records))

    if title is not None and title.strip():
        titles = {str(k): v for k, v in read_titles(repo).items()}
        titles[str(issue_n)] = " ".join(title.split())
        atomic_write(state_dir(repo) / TITLES_NAME,
                     json.dumps(dict(sorted(titles.items(), key=lambda kv: int(kv[0]))), indent=1) + "\n")

    warnings = []
    if review_cleared:
        warnings.append("the review was cleared because the head SHA changed; record the new review")
    if new_attempt and top == 0:
        warnings.append(f"issue {issue_n} had no earlier attempt; this is attempt 1")
    return {"id": key, "action": "updated" if index else "created", "path": str(path), "row": row,
            "warnings": warnings}


# ---------------------------------------------------------------------------------------------
# The door to GitHub (sync, ship). Tests replace `run`.


class Result:
    def __init__(self, argv, code, stdout="", stderr=""):
        self.argv, self.code, self.stdout, self.stderr = list(argv), code, stdout, stderr

    @property
    def ok(self):
        return self.code == 0

    def tail(self, lines=3):
        return " ".join((self.stderr or self.stdout or "").strip().splitlines()[-lines:]) or f"exit {self.code}"


def run(argv, input=None, timeout=900):
    """Run one command; the only place the GitHub-facing scripts start a process."""
    argv = [str(a) for a in argv]
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, input=input)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return Result(argv, 127, "", f"could not run {argv[0]}: {exc}")
    return Result(argv, out.returncode, out.stdout or "", out.stderr or "")


def gh(*args, timeout=300):
    """`gh ...`; $GH may name another executable (split as a shell would)."""
    return run(shlex.split(os.environ.get("GH", "").strip() or "gh") + [str(a) for a in args], timeout=timeout)


def git(path, *args, timeout=1800):
    """`git -C <path> ...` through the same door, with the caller's credentials."""
    return run(["git", "-C", str(path)] + [str(a) for a in args], timeout=timeout)


def need(result, what):
    if not result.ok:
        raise GitHubError(f"{what} failed: {result.tail()}")
    return result


def parse_json(text, what):
    """JSON from gh; `gh api --paginate` prints one array per page, which are joined."""
    text = (text or "").strip()
    if not text:
        return None
    decoder, values, pos = json.JSONDecoder(), [], 0
    try:
        while pos < len(text):
            value, pos = decoder.raw_decode(text, pos)
            values.append(value)
            while pos < len(text) and text[pos].isspace():
                pos += 1
    except json.JSONDecodeError as exc:
        raise GitHubError(f"{what} returned something other than JSON: {exc}")
    if len(values) == 1:
        return values[0]
    if all(isinstance(v, list) for v in values):
        return [item for v in values for item in v]
    raise GitHubError(f"{what} returned several JSON values")


def gh_json(what, *args):
    return parse_json(need(gh(*args), what).stdout, what)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def utc_time(value):
    """A GitHub time as an aware datetime (GitHub's naive times are UTC); None when unreadable."""
    try:
        when = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def login_of(value):
    return str(value.get("login") or "") if isinstance(value, dict) else str(value or "")


def is_bot(value):
    if isinstance(value, dict) and (value.get("is_bot") or value.get("type") == "Bot"):
        return True
    return login_of(value).lower().endswith("[bot]")


def names(items, key="name"):
    return sorted(str(i.get(key) if isinstance(i, dict) else i) for i in items or [] if i)


def marked(body):
    """A comment as the factory posts it: says where it is from and carries the marker."""
    text = (body or "").strip()
    if not text.startswith(FIRST_LINE):
        text = f"{FIRST_LINE}\n\n{text}"
    if MARKER not in text:
        text = f"{text}\n\n{MARKER}"
    return text + "\n"


def default_branch(repo):
    data = gh_json("gh repo view", "repo", "view", repo, "--json", "defaultBranchRef,nameWithOwner") or {}
    name = ((data.get("defaultBranchRef") or {}).get("name") or "").strip()
    if not name:
        raise GitHubError(f"gh repo view {repo} named no default branch")
    return name


def owner_login():
    result = gh("api", "user", "--jq", ".login")
    login = result.stdout.strip()
    if not result.ok or not login or len(login.split()) != 1:
        raise GitHubError(f"gh api user returned no login ({result.tail()}); pass --owner LOGIN")
    return login


def normalise_issue(raw):
    author = raw.get("author")
    return {"number": int(raw.get("number") or 0), "title": str(raw.get("title") or ""),
            "labels": names(raw.get("labels")), "assignees": names(raw.get("assignees"), "login"),
            "author": author.get("login") if isinstance(author, dict) else author,
            "created_at": raw.get("createdAt"), "updated_at": raw.get("updatedAt")}


def exclusion_reasons(issue, owner):
    """Why the owner policy keeps the factory off this issue: assigned to someone else,
    labelled on-hold or wontfix, or opened by someone other than the owner. Empty: it may."""
    reasons = []
    others = [a for a in issue.get("assignees", []) if a.lower() != owner.lower()]
    if others:
        reasons.append(f"assigned to {', '.join(others)}")
    held = [l for l in issue.get("labels", []) if l.lower() in EXCLUDED_LABELS]
    if held:
        reasons.append(f"labelled {', '.join(held)}")
    author = issue.get("author")
    if not author:
        reasons.append("author unknown")
    elif author.lower() != owner.lower():
        reasons.append(f"opened by {author}")
    return reasons


def rollup_state(rollup):
    """(success|failure|pending|none, the failing checks) from a statusCheckRollup."""
    items = [i for i in rollup if isinstance(i, dict)] if isinstance(rollup, list) else []
    if not items:
        return "none", []
    failing, pending = [], False
    for item in items:
        name = str(item.get("name") or item.get("context") or "check")
        url = str(item.get("detailsUrl") or item.get("targetUrl") or "")
        if "conclusion" in item or ("status" in item and "state" not in item):   # a check run
            status, conclusion = str(item.get("status") or "").upper(), str(item.get("conclusion") or "").upper()
            if status and status != "COMPLETED":
                pending = True
            elif conclusion not in CHECK_OK:
                failing.append({"name": name, "conclusion": conclusion.lower() or "none", "url": url})
        else:                                                                    # a status context
            state = str(item.get("state") or "").upper()
            if state in ("PENDING", "EXPECTED"):
                pending = True
            elif state not in CHECK_OK:
                failing.append({"name": name, "conclusion": state.lower() or "none", "url": url})
    if failing:
        return "failure", failing
    return ("pending" if pending else "success"), []


def log_tail(repo, run_id):
    """The last 40 lines (at most 3000 characters) of a failed CI run's log, or None."""
    result = gh("run", "view", str(run_id), "-R", repo, "--log-failed", timeout=180)
    return "\n".join(result.stdout.rstrip().splitlines()[-40:])[-3000:] if result.ok else None


def pr_comments(repo, number):
    """Issue comments, review bodies and inline review comments of a PR, oldest first."""
    owner, name = split_repo(repo)
    data = gh_json("gh pr view", "pr", "view", str(number), "-R", repo, "--json", "comments,reviews") or {}
    out = [{"kind": "issue", "author": login_of(c.get("author")), "bot": is_bot(c.get("author")),
            "body": str(c.get("body") or ""), "created_at": c.get("createdAt"), "url": c.get("url")}
           for c in data.get("comments") or []]
    out += [{"kind": "review", "author": login_of(r.get("author")), "bot": is_bot(r.get("author")),
             "body": str(r.get("body") or ""), "created_at": r.get("submittedAt") or r.get("createdAt")}
            for r in data.get("reviews") or [] if str(r.get("body") or "").strip()]
    inline = gh_json("gh api pulls comments", "api", f"repos/{owner}/{name}/pulls/{number}/comments", "--paginate")
    out += [{"kind": "review-comment", "author": login_of(c.get("user")), "bot": is_bot(c.get("user")),
             "body": str(c.get("body") or ""), "created_at": c.get("created_at"), "path": c.get("path"),
             "url": c.get("html_url")} for c in inline or []]
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    out.sort(key=lambda c: utc_time(c.get("created_at")) or epoch)
    return out


def unanswered(comments):
    """(people's comments after the factory's last marked comment, that comment's time)."""
    times = [utc_time(c.get("created_at")) for c in comments if MARKER in (c.get("body") or "")]
    last = max((t for t in times if t), default=None)
    out = []
    for c in comments:
        body = c.get("body") or ""
        if MARKER in body or c.get("bot") or not body.strip():
            continue
        when = utc_time(c.get("created_at"))
        if last is None or (when is not None and when > last):
            out.append({k: c.get(k) for k in ("kind", "author", "body", "created_at", "path", "url") if c.get(k)})
    return out, last.isoformat() if last else None


def issue_of_pr(head, body):
    number = issue_of_branch(head)
    if number is not None:
        return number
    m = re.search(r"\b(?:refs|closes|close|closed|fixes|fix|fixed|resolves|resolve|resolved)\s+#(\d+)",
                  body or "", re.I)
    return int(m.group(1)) if m else None


def factory_pr(repo, raw, logs=True, cache=None):
    """One open factory pull request in the shape of prs.json."""
    number = int(raw.get("number") or 0)
    head = str(raw.get("headRefName") or "")
    ci, failing = rollup_state(raw.get("statusCheckRollup"))
    cache = {} if cache is None else cache
    for check in failing if logs else []:
        m = re.search(r"/actions/runs/(\d+)", check.get("url") or "")
        if m and m.group(1) not in cache:
            cache[m.group(1)] = log_tail(repo, m.group(1))
        check["log_tail"] = cache.get(m.group(1)) if m else None
    pending, last = unanswered(pr_comments(repo, number))
    return {"number": number, "url": raw.get("url"), "title": raw.get("title"), "head": head,
            "base": raw.get("baseRefName"), "issue": issue_of_pr(head, str(raw.get("body") or "")),
            "head_sha": raw.get("headRefOid"), "state": str(raw.get("state") or "OPEN").lower(),
            "is_draft": bool(raw.get("isDraft")), "mergeable": str(raw.get("mergeable") or "UNKNOWN").lower(),
            "merge_state": str(raw.get("mergeStateStatus") or "").lower() or None, "ci": ci,
            "failing_checks": failing, "review_state": raw.get("reviewDecision") or None,
            "unanswered_comments": pending, "last_factory_comment_at": last,
            "labels": names(raw.get("labels")), "author": login_of(raw.get("author")) or None}


# ---------------------------------------------------------------------------------------------
# The merge rules sync's precheck and ship both apply


def protected_paths(rules):
    """The rules' `- Protected paths:` list, split on ; or ,."""
    return [p.strip() for p in re.split(r"[;,]", rules.get("protected paths") or "") if p.strip()]


def touches(paths, patterns):
    """The paths a protected pattern covers: `dir/` is a folder, a glob is a glob, else a file or folder."""
    hits = []
    for path in paths:
        path = path.strip().removeprefix("./")
        for pat in patterns:
            if pat.endswith("/"):
                hit = path.startswith(pat)
            elif any(ch in pat for ch in "*?["):
                hit = fnmatch.fnmatch(path, pat)
            else:
                hit = path == pat or path.startswith(pat.rstrip("/") + "/")
            if hit:
                hits.append(path)
                break
    return hits


def same_sha(a, b):
    a, b = str(a or "").strip().lower(), str(b or "").strip().lower()
    return len(a) >= 7 and len(b) >= 7 and (a.startswith(b) or b.startswith(a))


def review_passed(row, head_sha):
    """The ledger row records a reviewer's PASS for exactly this commit."""
    return bool(row) and str(row.get("review") or "").upper() == "PASS" and same_sha(row.get("head_sha"), head_sha)


def attention(pr):
    """Why an open factory PR goes back to its builder first."""
    out = []
    if pr.get("ci") == "failure":
        failing = ", ".join(c.get("name", "check") for c in pr.get("failing_checks") or []) or "a check"
        out.append(f"PR #{pr['number']} CI failing ({failing})")
    n = len(pr.get("unanswered_comments") or [])
    if n:
        out.append(f"PR #{pr['number']} has {n} unanswered comment{'s' if n != 1 else ''}")
    if pr.get("mergeable") == "conflicting":
        out.append(f"PR #{pr['number']} has merge conflicts")
    return out


def merge_blockers(pr, rules, integration, default, row, one_way_door=False, protected_hits=None):
    """Every reason the factory may not squash-merge this PR now; empty means it may."""
    out = []
    base, head = str(pr.get("base") or ""), str(pr.get("head") or "")
    if not yes(rules.get("auto-merge")):
        out.append("the rules do not say Auto-merge: yes")
    if not BRANCH_RE.match(head):
        out.append(f"head {head!r} is not a factory branch")
    if not integration or integration == default or is_protected(integration, default):
        out.append("the repo has no integration branch; a person merges into the default branch")
    elif base != integration:
        out.append(f"base {base!r} is not the integration branch {integration!r}")
    if is_protected(base, default):
        out.append(f"base {base!r} is the default or a protected branch")
    if str(pr.get("state") or "open").lower() != "open":
        out.append(f"the PR is {pr.get('state')}")
    if pr.get("is_draft"):
        out.append("the PR is a draft")
    if pr.get("ci") != "success":
        out.append(f"CI is {pr.get('ci') or 'unknown'}, not success")
    if not review_passed(row, pr.get("head_sha")):
        out.append(f"the ledger has no review PASS for head {str(pr.get('head_sha') or '')[:12]}")
    if pr.get("mergeable") != "mergeable":
        out.append(f"GitHub says mergeable is {pr.get('mergeable') or 'unknown'}")
    if is_onboarding(head):
        out.append("the onboarding pull request: a person merges a repo's first rules")
    elif one_way_door or (row and row.get("risk") == "one-way-door"):
        out.append("a one-way door: a person merges it")
    if protected_hits:
        out.append("touches protected paths: " + ", ".join(protected_hits[:5]))
    n = len(pr.get("unanswered_comments") or [])
    if n:
        out.append(f"{n} comment{'s' if n != 1 else ''} not answered by the factory")
    return out
