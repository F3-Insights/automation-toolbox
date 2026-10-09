"""portal-issue-file: file one GitHub issue on the Insights Portal's repository, and only there.

The finish step of the CRM hygiene pass files the pass's defect drafts with this, so the
session never runs `gh` itself. The model writes the title and the body; this script
decides where they go and whether they may go at all.

One repository: the setting `portal_issue_repo` in the [crm-hygiene-workstream] table
(owner/name). There is no flag that names another repository and none that reads a file:
the title and body arrive as text, so nothing on disk can be attached by path.

Nothing private leaves. Before GitHub is touched, the title and body are scanned and a match
refuses the whole issue: a home-directory or Windows user folder path, anything shaped like
a secret (bearer tokens, authorization headers, key and token query parameters, common token
formats, password or key assignments), and any of the owner's private terms (the setting
`private_terms`, a list, matched as whole words ignoring case). The refusal names the rule
that matched, never the matched text.

No duplicates: every open issue's title is read (a list that may be truncated is not
coverage, and nothing is filed) and an open issue with exactly this title answers
`duplicate` with its number. `--dry-run` scans and reads the open issues, then answers
`would_file` with every open issue's number and title, creating nothing.

`gh` runs with an argument list, never through a shell; the program is $GH when set, else
`gh` on PATH, and uses gh's own login.

Prints one JSON object. Exit 0 filed, would_file or duplicate; 3 refused (nothing read from
or written to GitHub); 2 could not run.

Example:
    python3 portal_issue_file.py --title "IR-20260105-sync: contacts flip inactive" \\
        --body "Evidence: ... Impact: ... Ask: ..." --label bug --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path

OK, STOP, ERROR = 0, 3, 2
SKILL = "crm-hygiene-workstream"
LABELS = ("bug", "enhancement")
LIST_LIMIT = 2000  # an answer this long might be truncated, so it is treated as incomplete
TITLE_MAX, BODY_MAX = 200, 60000

SECRETS = re.compile(r"(?i)(bearer\s+\S+|authorization[\"'\s:=]+(?:bearer\s+)?\S+"
                     r"|[?&](?:key|token|api_key|access_token)=[^\s&\"']+)")
PRIVATE = [  # (rule name, pattern), in the order a refusal reports them
    ("a Windows user folder", re.compile(r"(?i)(/mnt/c/Users/|\b[a-z]:\\+Users\\+)")),
    ("a home-directory path", re.compile(r"(/home/[a-z_][a-z0-9_-]*/|/Users/[A-Za-z][A-Za-z0-9._-]*/)")),
    ("a secret (redaction pattern)", SECRETS),
    ("a secret (token shape)", re.compile(
        r"(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|\bsk-[A-Za-z0-9_-]{20,}"
        r"|\bAKIA[0-9A-Z]{16}\b|\bxox[abprs]-[A-Za-z0-9-]{10,}"
        r"|-----BEGIN [A-Z ]*PRIVATE KEY-----|\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.)")),
    ("a secret (assignment)", re.compile(
        r"(?i)\b(password|passwd|secret|client_secret|api[_-]?key|access[_-]?token|auth[_-]?token)\b"
        r"\s*[:=]\s*[\"']?[^\s\"']{6,}")),
]


class Refusal(Exception):
    """A check said no; nothing was read from or written to GitHub."""


class Failed(Exception):
    """The script could not run (a setting missing, gh failing, an answer it cannot read)."""


def settings(section=None):
    """Owner settings from ~/.config/f3i-toolbox/settings.toml (or $F3I_TOOLBOX_SETTINGS)."""
    path = Path(os.environ.get("F3I_TOOLBOX_SETTINGS", "~/.config/f3i-toolbox/settings.toml")).expanduser()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return data.get(section, {}) if section else data


def repo() -> str:
    name = str(settings(SKILL).get("portal_issue_repo") or "").strip()
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", name):
        raise Failed(f"the setting [{SKILL}] portal_issue_repo (owner/name of the Portal's repository) is needed")
    return name


def scan(title: str, body: str) -> list:
    """The names of the private-content rules the title or body match, never the text."""
    text = f"{title}\n{body}"
    hits = [name for name, pattern in PRIVATE if pattern.search(text)]
    terms = [str(t) for t in settings(SKILL).get("private_terms") or [] if len(str(t).strip()) >= 3]
    if any(re.search(r"(?<![A-Za-z0-9])" + re.escape(t.strip()) + r"(?![A-Za-z0-9])", text, re.I) for t in terms):
        hits.append("a private term (setting private_terms)")
    return hits


def check(title: str, body: str) -> tuple:
    title, body = " ".join(str(title or "").split()), str(body or "").strip()
    if not title:
        raise Refusal("a title is required")
    if not body:
        raise Refusal("a body is required: evidence, impact and a specific ask")
    if len(title) > TITLE_MAX:
        raise Refusal(f"the title is longer than {TITLE_MAX} characters")
    if len(body) > BODY_MAX:
        raise Refusal(f"the body is longer than {BODY_MAX} characters")
    hits = scan(title, body)
    if hits:
        raise Refusal("private content: " + "; ".join(hits) + ". Remove it and file again.")
    return title, body


def gh(args: list) -> str:
    argv = shlex.split(os.environ.get("GH", "").strip() or "gh") + args
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Failed(f"could not run gh ({argv[0]}): {exc}")
    if out.returncode != 0:
        tail = (out.stderr or out.stdout).strip().splitlines()[-3:]
        raise Failed(f"gh {' '.join(args[:2])} failed: {' '.join(tail) or 'exit ' + str(out.returncode)}")
    return out.stdout


def open_issues(name: str) -> list:
    raw = gh(["issue", "list", "-R", name, "--state", "open", "--limit", str(LIST_LIMIT), "--json", "number,title,url"])
    try:
        data = json.loads(raw or "[]")
    except ValueError as exc:
        raise Failed(f"gh issue list returned something other than JSON: {exc}")
    if not isinstance(data, list):
        raise Failed("gh issue list returned JSON that is not a list")
    if len(data) >= LIST_LIMIT:
        raise Failed(f"{name} has {LIST_LIMIT} or more open issues; cannot establish duplicate coverage")
    return [d for d in data if isinstance(d, dict)]


def file_issue(title: str, body: str, label: str = "bug", dry_run: bool = False) -> dict:
    if label not in LABELS:
        raise Refusal(f"--label must be one of {', '.join(LABELS)}")
    name = repo()
    title, body = check(title, body)
    issues = open_issues(name)
    for issue in issues:
        if str(issue.get("title") or "").strip() == title:
            return {"status": "duplicate", "repo": name, "number": issue.get("number"), "url": issue.get("url"),
                    "title": title}
    if dry_run:  # the open titles let the caller spot the same defect filed under another title
        return {"status": "would_file", "repo": name, "title": title, "label": label, "body_chars": len(body),
                "dry_run": True, "open_issues": [[i.get("number"), str(i.get("title") or "")] for i in issues]}
    out = gh(["issue", "create", "-R", name, "--title", title, "--body", body, "--label", label])
    url = next((line.strip() for line in out.splitlines() if "/issues/" in line), "")
    found = re.search(r"/issues/(\d+)", url)
    if not found:
        raise Failed("gh issue create did not return an issue URL; check the repository before filing again")
    return {"status": "filed", "repo": name, "number": int(found.group(1)), "url": url, "title": title, "label": label}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="portal-issue-file", description=__doc__.split("\n\n")[0])
    p.add_argument("--title", required=True, help="the issue title, as text (IR-<date>-<slug>: summary)")
    p.add_argument("--body", required=True, help="the issue body, as text; no file is ever read")
    p.add_argument("--label", default="bug", choices=LABELS, help="bug for a defect, enhancement for a hardening request")
    p.add_argument("--dry-run", action="store_true", help="scan and check for duplicates; create nothing")
    a = p.parse_args(argv)
    try:
        out, code = file_issue(a.title, a.body, a.label, a.dry_run), OK
    except Refusal as exc:
        out, code = {"status": "refused", "reason": str(exc)}, STOP
    except Failed as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}, indent=1))
        print(str(exc), file=sys.stderr)
        return ERROR
    print(json.dumps(out, indent=1))
    return code


if __name__ == "__main__":
    sys.exit(main())
