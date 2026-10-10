"""Print a GitHub repository's open work as one compact page for the issue loop's lead.

Reads through the gh CLI (signed in): the default branch, open pull requests with their base,
head, check state and review decision, and open issues grouped by status label, each with the
status marker of its latest status comment (<!-- f3i: status=... -->). Issues opened by someone
outside --trusted that carry no status label are listed under "untrusted" (F3-AGENT-1).

    python3 ~/.claude/skills/software-issue-loop/scripts/repo_status.py OWNER/REPO [--trusted a,b] [--limit 50]

Exit 2 when gh is missing or a gh call fails.
"""

import argparse
import json
import re
import subprocess
import sys

STATUSES = ["in-progress", "in-review", "ready", "plan-review", "needs-info", "blocked", "triage"]
MARKER = re.compile(r"<!--\s*f3i:\s*(.*?)\s*-->")


def gh(*args):
    try:
        out = subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
    except FileNotFoundError:
        sys.exit("gh is not installed")
    except subprocess.CalledProcessError as exc:
        print(exc.stderr.strip(), file=sys.stderr)
        sys.exit(2)
    return json.loads(out.stdout) if out.stdout.strip() else None


def checks_state(rollup):
    states = {(c.get("conclusion") or c.get("state") or c.get("status") or "").upper() for c in rollup or []}
    if not states:
        return "no checks"
    if states & {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"}:
        return "FAILING"
    if states & {"PENDING", "IN_PROGRESS", "QUEUED", "EXPECTED"}:
        return "pending"
    return "passing"


def latest_marker(comments):
    for c in reversed(comments or []):
        m = MARKER.search(c.get("body") or "")
        if m:
            return m.group(1)
    return ""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("repo", help="OWNER/REPO")
    ap.add_argument("--trusted", default="", help="comma-separated logins whose issues may be worked")
    ap.add_argument("--limit", type=int, default=50)
    a = ap.parse_args(argv)

    info = gh("repo", "view", a.repo, "--json", "defaultBranchRef,owner")
    me = gh("api", "user") or {}
    trusted = {t for t in a.trusted.split(",") if t} or {info["owner"]["login"], me.get("login", "")}

    prs = gh("pr", "list", "-R", a.repo, "--state", "open", "--limit", str(a.limit), "--json",
             "number,title,baseRefName,headRefName,isDraft,reviewDecision,statusCheckRollup")
    issues = gh("issue", "list", "-R", a.repo, "--state", "open", "--limit", str(a.limit), "--json",
                "number,title,labels,author,comments,updatedAt")

    print(f"# {a.repo} (default branch: {info['defaultBranchRef']['name']})\n")
    print(f"## Open pull requests ({len(prs)})")
    for p in prs:
        draft = " draft" if p["isDraft"] else ""
        review = (p.get("reviewDecision") or "no review").lower()
        print(f"- PR #{p['number']} {p['headRefName']} -> {p['baseRefName']}{draft}: "
              f"checks {checks_state(p.get('statusCheckRollup'))}, {review}. {p['title']}")
    if not prs:
        print("- none")

    groups = {s: [] for s in STATUSES + ["unlabeled", "untrusted"]}
    for i in issues:
        labels = {lb["name"] for lb in i["labels"]}
        status = next((s for s in STATUSES if s in labels), None)
        kind = next((t for t in ("bug", "feature", "enhancement") if t in labels), "")
        line = f"- #{i['number']} {kind + ': ' if kind else ''}{i['title']}"
        marker = latest_marker(i.get("comments"))
        if marker:
            line += f"  [{marker}]"
        if status:
            groups[status].append(line)
        elif i["author"]["login"] in trusted:
            groups["unlabeled"].append(line)
        else:
            groups["untrusted"].append(line + f"  (by {i['author']['login']})")

    print(f"\n## Open issues ({len(issues)})")
    for name, lines in groups.items():
        if lines:
            print(f"\n### {name} ({len(lines)})")
            print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
