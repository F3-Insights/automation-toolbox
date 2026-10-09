# /// script
# dependencies = ["pyyaml"]
# ///
"""Take the software factory's snapshot of one repository before a session, or precheck it.

The prepare phase (SOFTWARE-FACTORY.md, "Written by software-factory-sync"). It fetches the
local clone (`git fetch origin --prune`; `gh repo clone` when there is none), reads the
repository's .software-factory/SOFTWARE-FACTORY-RULES.md from the default branch, and writes into
--out: repo.json, issues.json (open issues, each marked `excluded` with the owner policy's
reasons), prs.json (open factory pull requests with CI, failing checks and log tails,
mergeability, review state, and people's comments after the factory's last one), ci.json (the
default and integration branches' latest runs) and SYNC.md, last.

The integration branch is the rules' `Integration branch:`, else development; either only when it
exists on origin and is not a protected name, else the default branch. The owner policy excludes
an issue assigned to someone other than the owner, labelled on-hold or wontfix, or opened by
anyone else; the owner is --owner LOGIN, else the login `gh api user` returns.

--topic keeps issues whose title, body or labels contain every word of TEXT; --issue (or issue
numbers after OWNER/NAME: `7 12`, `#7`, `7,12`) keeps only those. Both narrow the issues, never
the pull requests.

The first line of SYNC.md and of the output is `SYNCED: <n> issues, <m> factory PRs, CI <state>`,
or `STALE: <reason>` when GitHub could not be read (then only SYNC.md is written, exit still 0).

--precheck writes nothing and does not fetch. It prints `WORK: <reasons>` when there are open
eligible issues with no ledger row (a reopened one counts as unseen), factory PRs with failing
CI, unanswered comments, conflicts or ready to merge, or the repository needs onboarding (no
commands file with a real test command on the integration branch and no onboarding PR open);
otherwise `NOTHING: <what it saw>`.

Inputs: OWNER/NAME, --out or --precheck, filters, --owner. Needs `gh` signed in ($GH may name
another executable) and the setting repos_dir in [software-factory-workstream].
Exit 0 when it ran (SYNCED, STALE, WORK or NOTHING), 2 on a bad argument.

Example: python3 software_factory_sync.py acme/widgets --out RUN/sync
"""

import argparse
import json
import re
import sys
from pathlib import Path

import _common as c


def matches_topic(issue, topic):
    hay = " ".join([issue.get("title") or "", issue.get("body") or "", " ".join(issue.get("labels") or [])]).lower()
    return all(re.search(r"\b" + re.escape(w), hay) for w in re.findall(r"\w+", topic.lower()))


def read_commands(clone, branch):
    """(the commands file on origin/<branch> or None, whether it declares a real test command)."""
    shown = c.git(clone, "show", f"refs/remotes/origin/{branch}:{c.COMMANDS_FILE}")
    if not shown.ok:
        return None, False
    try:
        return c.COMMANDS_FILE, "test" in c.parse_commands(shown.stdout)
    except ValueError:   # a file that does not parse declares no test command
        return c.COMMANDS_FILE, False


def read_repo(repo, fetch):
    """repo.json: the branches, the clone, the rules. With `fetch` it clones or fetches first."""
    owner, name = c.split_repo(repo)
    default = c.default_branch(repo)
    clone = c.local_clone(repo)
    notes = []
    is_clone = (clone / ".git").exists()
    if fetch:
        if is_clone:
            c.need(c.git(clone, "fetch", "origin", "--prune"), f"git fetch in {clone.name}")
        elif clone.exists() and any(clone.iterdir()):
            raise c.GitHubError(f"{clone} exists but is not a git clone")
        else:
            clone.parent.mkdir(parents=True, exist_ok=True)
            c.need(c.gh("repo", "clone", repo, str(clone), timeout=1800), "gh repo clone")
            is_clone = True
    rules_text, factory_dir = "", False
    if is_clone:
        shown = c.git(clone, "show", f"origin/{default}:{c.RULES_FILE}")
        rules_text = shown.stdout if shown.ok else ""
        factory_dir = c.git(clone, "cat-file", "-e", f"origin/{default}:{c.FACTORY_DIR}").ok
    else:
        notes.append(f"no local clone at {clone}; rules and the integration branch were not read")
    rules = c.rules_fields(rules_text)
    named = rules.get("integration branch") or ""
    wanted = named or c.DEFAULT_INTEGRATION
    integration = default
    if wanted != default and is_clone:
        if c.is_protected(wanted, default):
            notes.append(f"the rules name {wanted!r} as the integration branch, a protected name; PRs target {default}")
        elif c.git(clone, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{wanted}").ok:
            integration = wanted
        elif named:
            notes.append(f"integration branch {wanted!r} is not on origin; PRs target {default}")
    head, commands_file, test_command = None, None, None
    if is_clone:
        rev = c.git(clone, "rev-parse", f"refs/remotes/origin/{integration}")
        head = (rev.stdout.strip() or None) if rev.ok else None
        commands_file, test_command = read_commands(clone, integration)
        if not test_command:
            notes.append(f"no {c.COMMANDS_FILE} with a test command on {integration}: the repo needs onboarding")
    return {"owner": owner, "name": name, "default_branch": default, "integration_branch": integration,
            "has_integration_branch": integration != default, "local_clone": str(clone) if is_clone else None,
            "fetched_at": c.now_iso(), "head_sha_integration": head, "factory_dir_present": factory_dir,
            "rules_present": bool(rules_text.strip()), "rules": rules, "protected_paths": c.protected_paths(rules),
            "notes": notes, "commands_file": commands_file, "test_command": test_command,
            "needs_onboarding": test_command is False}


def read_issues(repo, login, numbers, topic):
    raw = c.gh_json("gh issue list", "issue", "list", "-R", repo, "--state", "open", "--limit", "500",
                    "--json", c.ISSUE_FIELDS) or []
    out = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        base = c.normalise_issue(r)
        comments = r.get("comments") if isinstance(r.get("comments"), list) else []
        issue = {**base, "body": str(r.get("body") or ""),
                 "comments": [{"author": c.login_of(x.get("author")), "body": str(x.get("body") or ""),
                               "created_at": x.get("createdAt")} for x in comments],
                 "excluded": "; ".join(c.exclusion_reasons(base, login)) or None}
        if (numbers and issue["number"] not in numbers) or (topic and not matches_topic(issue, topic)):
            continue
        out.append(issue)
    return sorted(out, key=lambda i: i["number"])


def branch_ci(repo, branch, logs=True):
    """The latest CI runs on a branch: one per workflow, for the newest commit that has runs."""
    rows = c.gh_json("gh run list", "run", "list", "-R", repo, "--branch", branch, "--limit", "30", "--json",
                     "databaseId,workflowName,status,conclusion,headSha,createdAt,url,event") or []
    rows = sorted((r for r in rows if isinstance(r, dict)), key=lambda r: str(r.get("createdAt") or ""), reverse=True)
    if not rows:
        return {"branch": branch, "state": "none", "head_sha": None, "runs": [], "failures": []}
    head = rows[0].get("headSha")
    latest = {}
    for r in rows:
        if r.get("headSha") == head:
            latest.setdefault(str(r.get("workflowName") or "workflow"), r)
    runs, failures, pending = [], [], False
    for wf, r in sorted(latest.items()):
        status, conclusion = str(r.get("status") or "").lower(), str(r.get("conclusion") or "").lower()
        runs.append({"workflow": wf, "run_id": r.get("databaseId"), "status": status, "conclusion": conclusion,
                     "url": r.get("url"), "created_at": r.get("createdAt")})
        if status != "completed":
            pending = True
        elif conclusion.upper() not in c.CHECK_OK:
            failure = {"workflow": wf, "run_id": r.get("databaseId"), "conclusion": conclusion, "url": r.get("url")}
            if logs and r.get("databaseId") is not None:
                failure["log_tail"] = c.log_tail(repo, r["databaseId"])
            failures.append(failure)
    state = "failure" if failures else ("pending" if pending else "success")
    return {"branch": branch, "state": state, "head_sha": head, "runs": runs, "failures": failures}


def collect(repo, numbers=(), topic=None, owner=None, fetch=True, logs=True):
    """Everything sync reads. GitHubError when GitHub or the clone cannot be read."""
    info = read_repo(repo, fetch)
    login = owner or c.owner_login()
    info["owner_login"] = login
    info["filter"] = {"issues": sorted(numbers) or None, "topic": topic or None}
    issues = read_issues(repo, login, numbers, topic)
    rows = c.gh_json("gh pr list", "pr", "list", "-R", repo, "--state", "open", "--limit", "200",
                     "--json", c.PR_FIELDS) or []
    cache = {}
    prs = sorted((c.factory_pr(repo, r, logs=logs, cache=cache) for r in rows
                  if isinstance(r, dict) and c.BRANCH_RE.match(str(r.get("headRefName") or ""))),
                 key=lambda p: p["number"])
    ci = {"default": branch_ci(repo, info["default_branch"], logs)}
    ci["integration"] = (branch_ci(repo, info["integration_branch"], logs)
                         if info["integration_branch"] != info["default_branch"] else ci["default"])
    missing = sorted(set(numbers) - {i["number"] for i in issues})
    if missing:
        info["notes"].append("not open (or not found): " + ", ".join(f"#{n}" for n in missing))
    return {"repo": info, "issues": issues, "prs": prs, "ci": ci}


def synced_line(state):
    return (f"{c.SYNCED_PREFIX} {len(state['issues'])} issues, {len(state['prs'])} factory PRs, "
            f"CI {state['ci']['integration']['state']}")


def sync_md(state):
    info, issues, prs, ci = state["repo"], state["issues"], state["prs"], state["ci"]
    rules = info["rules"]
    eligible = [i for i in issues if not i["excluded"]]
    head = f" at `{info['head_sha_integration'][:12]}`" if info.get("head_sha_integration") else ""
    lines = [synced_line(state), "",
             f"Repository {info['owner']}/{info['name']}: default branch `{info['default_branch']}`, "
             f"integration branch `{info['integration_branch']}`{head}.",
             f"Rules: {'present' if info['rules_present'] else 'none'}; auto-merge {rules.get('auto-merge') or 'not set'}; "
             f"release PR {rules.get('release pr') or 'not set'}; protected paths "
             f"{', '.join(info['protected_paths']) or 'none'}.",
             f"Fetched {info['fetched_at']}. Owner login {info['owner_login']}."]
    if info["filter"]["issues"] or info["filter"]["topic"]:
        lines.append(f"Filter: issues {info['filter']['issues'] or 'all'}, topic {info['filter']['topic'] or 'none'}.")
    lines += [f"Note: {note}." for note in info["notes"]]
    lines += ["", f"## Issues ({len(issues)} open, {len(eligible)} eligible)", ""]
    lines += [f"- #{i['number']} {i['title']}" + (f" (excluded: {i['excluded']})" if i["excluded"] else "")
              for i in issues] or ["- none"]
    lines += ["", f"## Factory pull requests ({len(prs)})", ""]
    for p in prs:
        bits = [f"CI {p['ci']}", p["mergeable"]]
        if p["failing_checks"]:
            bits.append("failing " + ", ".join(x["name"] for x in p["failing_checks"]))
        if p["unanswered_comments"]:
            bits.append(f"{len(p['unanswered_comments'])} unanswered comment(s)")
        if p["review_state"]:
            bits.append(f"review {p['review_state'].lower()}")
        what = "onboarding" if c.is_onboarding(p["head"]) else f"issue #{p['issue']}"
        lines.append(f"- #{p['number']} `{p['head']}` -> `{p['base']}` ({what}): " + "; ".join(bits))
    if not prs:
        lines.append("- none")
    lines += ["", "## CI", ""]
    for key in ("default", "integration"):
        fails = ", ".join(f["workflow"] for f in ci[key]["failures"])
        lines.append(f"- {key} `{ci[key]['branch']}`: {ci[key]['state']}" + (f" ({fails})" if fails else ""))
    return "\n".join(lines) + "\n"


def write_file(path, text):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def write_out(out, state):
    """The snapshot files, SYNC.md last so a folder without it is an incomplete snapshot."""
    out.mkdir(parents=True, exist_ok=True)
    for name, key in (("repo.json", "repo"), ("issues.json", "issues"), ("prs.json", "prs"), ("ci.json", "ci")):
        write_file(out / name, json.dumps(state[key], indent=1) + "\n")
    write_file(out / c.SYNC_FILE, sync_md(state))


def precheck(repo, state):
    rows = c.latest(c.read_ledger(repo))
    info = state["repo"]
    unseen = [i["number"] for i in state["issues"]
              if not i["excluded"] and (i["number"] not in rows or rows[i["number"]].get("state") == "reopened")]
    reasons = []
    if unseen:
        reasons.append(f"{len(unseen)} eligible issue{'s' if len(unseen) != 1 else ''} not in the ledger ("
                       + ", ".join(f"#{n}" for n in unseen) + ")")
    if info.get("needs_onboarding") and not any(c.is_onboarding(str(p.get("head") or "")) for p in state["prs"]):
        reasons.append(f"onboarding: {info['integration_branch']} has no {c.COMMANDS_FILE} with a test command "
                       f"and no {c.ONBOARD_BRANCH} pull request is open")
    for pr in state["prs"]:
        reasons += c.attention(pr)
        row = rows.get(pr["issue"] if pr["issue"] is not None else -1)
        if not c.merge_blockers(pr, info["rules"], info["integration_branch"], info["default_branch"], row):
            reasons.append(f"PR #{pr['number']} ready to merge")
    if reasons:
        return {"result": "WORK", "line": "WORK: " + "; ".join(reasons), "reasons": reasons}
    excluded = sum(1 for i in state["issues"] if i["excluded"])
    return {"result": "NOTHING", "reasons": [],
            "line": f"NOTHING: {len(state['issues'])} open issues ({excluded} excluded, the rest in the ledger), "
                    f"{len(state['prs'])} factory PRs needing nothing"}


def issue_numbers(args):
    """Issue numbers given as `7`, `#7` or `7,12`."""
    out = []
    for arg in args:
        for part in str(arg).split(","):
            part = part.strip().lstrip("#")
            if part and not part.isdigit():
                raise c.UsageError(f"{arg!r} is not an issue number")
            if part:
                out.append(int(part))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Snapshot OWNER/NAME for a factory session, or --precheck for work.")
    ap.add_argument("repo", help="OWNER/NAME")
    ap.add_argument("numbers", nargs="*", help="issue numbers, as --issue")
    ap.add_argument("--out", help="the Run's sync folder")
    ap.add_argument("--issue", type=int, action="append", default=[], help="only this issue (repeatable)")
    ap.add_argument("--topic", help="only issues whose title, body or labels carry these words")
    ap.add_argument("--precheck", action="store_true", help="print WORK or NOTHING; write nothing")
    ap.add_argument("--owner", help="the owner's GitHub login (default: gh api user)")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args(argv)
    try:
        c.split_repo(args.repo)
        issues = sorted(set(args.issue + issue_numbers(args.numbers)))
        if args.precheck and args.out:
            raise c.UsageError("--precheck writes nothing; drop --out")
        if not args.precheck and not args.out:
            raise c.UsageError("--out DIR is required (or --precheck)")
        if any(n <= 0 for n in issues):
            raise c.UsageError("--issue takes a positive issue number")
        topic = args.topic if args.topic and args.topic.strip() else None   # a blank --topic means none
        if topic is not None and not re.findall(r"\w+", topic):
            raise c.UsageError("--topic has no words")
        c.repos_dir()
    except c.UsageError as exc:
        print(f"software_factory_sync: {exc}", file=sys.stderr)
        return 2
    try:
        state = collect(args.repo, issues, topic, args.owner, fetch=not args.precheck, logs=not args.precheck)
    except (c.GitHubError, OSError) as exc:
        reason = " ".join(str(exc).split())
        line = f"{c.STALE_PREFIX} {reason}"
        if not args.precheck:
            out = Path(args.out)
            out.mkdir(parents=True, exist_ok=True)
            (out / c.SYNC_FILE).write_text(line + "\n\nGitHub could not be read; nothing else was written.\n",
                                           encoding="utf-8")
        print(json.dumps({"result": "STALE", "line": line}, indent=1) if args.format == "json" else line)
        return 0
    if args.precheck:
        result = precheck(args.repo, state)
        print(json.dumps(result, indent=1) if args.format == "json" else result["line"])
        return 0
    out = Path(args.out)
    write_out(out, state)
    line = synced_line(state)
    if args.format == "json":
        print(json.dumps({"result": "SYNCED", "line": line, "out": str(out), "issues": len(state["issues"]),
                          "prs": len(state["prs"]), "ci": state["ci"]["integration"]["state"],
                          "integration_branch": state["repo"]["integration_branch"]}, indent=1))
    else:
        print(line)
        print(f"Wrote {out}/repo.json, issues.json, prs.json, ci.json, SYNC.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
