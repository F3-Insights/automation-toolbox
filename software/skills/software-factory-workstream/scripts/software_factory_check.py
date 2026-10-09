"""Report where each issue of a repository stands in the software factory.

Each issue's state is its latest attempt in the ledger. With --sync DIR (a folder
software_factory_sync.py wrote) it is joined with DIR/issues.json and DIR/prs.json; a SYNC.md
starting STALE: means the snapshot is not used, and the report says so.

The report gives counts of issues by state, then stalled work:
  no-pr                verified or reviewed, no pull request, older than --stale-hours
  building-too-long    building with no update for --stale-hours (did the session die?)
  ask-unanswered       triaged-ask with the factory's question unanswered for over 3 days
  ci-failing           a factory PR with failing CI for longer than --stale-hours
  unanswered-comments  a factory PR with a person's comment unanswered for --stale-hours
  not-merged           a factory PR approved, green and mergeable but still open
then reopened issues (merged or released in the ledger but open in the snapshot), and repeat
offenders: issues built more than once, and (a heuristic on title words) issues that look like
one merged in the last 30 days. Issue 0 is onboarding and is shown as such.

A comment is the factory's when it carries <!-- software-factory -->.

Inputs: OWNER/NAME, --sync, --stale-hours (default 24), --format. Reads the ledger in the
factory's state folder. Prints text or JSON; writes nothing. Exit 0 when it ran, 2 on a bad
argument or an incomplete snapshot.

Example: python3 software_factory_check.py acme/widgets --sync RUN/sync --format json
"""

import argparse
import json
import re
import sys
from datetime import timedelta
from pathlib import Path

from _common import (MARKER, ONBOARD_ISSUE, STALE_PREFIX, STATES, SYNC_FILE, SYNCED_PREFIX, FactoryError,
                     UsageError, attempts, issue_label, issue_of_branch, ledger_path, now_local, parse_time,
                     read_ledger, read_titles, split_repo, to_int)

ASK_DAYS = 3
SIMILAR_DAYS = 30
STOPWORDS = frozenset("""a an the and or but of to in on at for from by with without into onto
is are was were be been being it its this that these those when where why how what which not no
can cant cannot should would will wont does doesnt do dont did didnt has have had after before
than then there their our your my we you they he she them us all any some via as if so up out
issue bug fix error problem""".split())


def load_list(path):
    if not path.is_file():
        raise UsageError(f"the snapshot has no {path.name}: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise UsageError(f"{path.name} is not JSON: {exc}")
    if not isinstance(data, list):
        raise UsageError(f"{path.name} is not a list, as software_factory_sync.py writes it")
    return [item for item in data if isinstance(item, dict)]


def load_snapshot(folder, repo):
    """{status, dir, issues: {n: issue}, prs}; status is 'synced' or 'stale: <reason>'."""
    folder = Path(folder).expanduser()
    summary = folder / SYNC_FILE
    if not summary.is_file():
        raise UsageError(f"the snapshot has no {SYNC_FILE} (sync writes it last): {folder}")
    first = (summary.read_text(encoding="utf-8").splitlines() or [""])[0].strip()
    if first.startswith(STALE_PREFIX):
        return {"status": f"stale: {first[len(STALE_PREFIX):].strip()}", "dir": str(folder), "issues": {}, "prs": []}
    if not first.startswith(SYNCED_PREFIX):
        raise UsageError(f"{SYNC_FILE} starts neither {SYNCED_PREFIX} nor {STALE_PREFIX}: {first[:80]!r}")
    try:
        info = json.loads((folder / "repo.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UsageError(f"the snapshot's repo.json is unreadable: {exc}")
    if not isinstance(info, dict) or f"{info.get('owner')}/{info.get('name')}" != repo:
        raise UsageError(f"the snapshot in {folder} is not for {repo}")
    issues = {}
    for item in load_list(folder / "issues.json"):
        if str(item.get("number")).isdigit():
            issues[int(item["number"])] = item
    return {"status": "synced", "dir": str(folder), "issues": issues, "prs": load_list(folder / "prs.json")}


def pr_issue(pr):
    if str(pr.get("issue")).isdigit():
        return int(pr["issue"])
    return issue_of_branch(str(pr.get("head") or ""))


def from_factory(comment):
    return MARKER in str(comment.get("body") or "")


def title_tokens(title):
    """A title's key: its lowercase words, less stopwords, short words and plural s."""
    out = set()
    for word in re.findall(r"[a-z0-9]+", (title or "").lower()):
        if len(word) < 3 or word in STOPWORDS:
            continue
        if len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        out.add(word)
    return out


def similar(a, b):
    """The same key, or two or more shared words that are half the words of both together."""
    if not a or not b:
        return False
    shared = a & b
    return a == b or (len(shared) >= 2 and len(shared) / len(a | b) >= 0.5)


def check(repo, sync=None, stale_hours=24, now=None):
    split_repo(repo)
    if stale_hours <= 0:
        raise UsageError("--stale-hours must be more than 0")
    now = now or now_local()
    groups = attempts(read_ledger(repo))
    current = {issue: group[-1] for issue, group in groups.items()}
    snapshot = load_snapshot(sync, repo) if sync else None
    synced = bool(snapshot and snapshot["status"] == "synced")
    open_issues = snapshot["issues"] if synced else {}
    prs = snapshot["prs"] if synced else []
    titles = read_titles(repo)
    titles.update({n: str(i["title"]) for n, i in open_issues.items() if i.get("title")})
    by_number = {str(pr.get("number")): pr for pr in prs}
    by_issue = {}
    for pr in prs:
        if pr_issue(pr) is not None:
            by_issue.setdefault(pr_issue(pr), pr)

    counts, stalled, reopened, issues = {}, [], [], []
    stale = timedelta(hours=stale_hours)

    def hours(then):
        return None if then is None else round((now - then).total_seconds() / 3600, 1)

    def stall(issue, kind, detail, since, pr=""):
        stalled.append({"issue": issue, "label": issue_label(issue), "kind": kind, "detail": detail, "pr": pr,
                        "since": since.isoformat(timespec="seconds") if since else "", "hours": hours(since)})

    for issue in sorted(current):
        row = current[issue]
        state = row["state"]
        counts[state] = counts.get(state, 0) + 1
        updated = parse_time(row["updated_at"])
        pr = (by_number.get(row["pr"]) if row["pr"] else None) or by_issue.get(issue)
        entry = {"issue": issue, "label": issue_label(issue),
                 "title": titles.get(issue, "") or ("Onboarding" if issue == ONBOARD_ISSUE else ""),
                 "attempt": to_int(row["attempt"]), "attempts": len(groups[issue]), "state": state, "status": state,
                 "branch": row["branch"], "pr": row["pr"] or (str(pr.get("number")) if pr else ""),
                 "head_sha": row["head_sha"], "verify": row["verify"], "review": row["review"],
                 "updated_at": row["updated_at"], "open_in_snapshot": (issue in open_issues) if synced else None,
                 "pr_in_snapshot": bool(pr) if synced else None, "ci": str(pr.get("ci") or "none") if pr else ""}

        if state in ("merged", "released") and issue in open_issues and issue != ONBOARD_ISSUE:
            entry["status"] = "reopened"
            reopened.append({"issue": issue, "title": entry["title"], "ledger_state": state,
                             "attempt": entry["attempt"], "pr": entry["pr"]})
        if state in ("verified", "reviewed") and not row["pr"] and not pr and (updated is None or now - updated > stale):
            stall(issue, "no-pr", f"{state} with no pull request", updated)
        if state == "building" and (updated is None or now - updated > stale):
            stall(issue, "building-too-long", "building with no update (did the session die?)", updated)
        if state == "triaged-ask":
            asked_at, answered = updated, False
            if issue in open_issues:
                comments = [c for c in open_issues[issue].get("comments") or [] if isinstance(c, dict)]
                asked = [t for t in (parse_time(c.get("created_at")) for c in comments if from_factory(c)) if t]
                if asked:
                    asked_at = max(asked)
                answered = any(not from_factory(c) and asked_at and (t := parse_time(c.get("created_at")))
                               and t > asked_at for c in comments)
            if not answered and (asked_at is None or now - asked_at > timedelta(days=ASK_DAYS)):
                where = "" if synced else " (not checked against a snapshot)"
                stall(issue, "ask-unanswered", f"the factory's question is unanswered{where}", asked_at)
        if pr:
            number, ci = str(pr.get("number") or ""), str(pr.get("ci") or "none").lower()
            if ci == "failure" and (updated is None or now - updated > stale):
                # the snapshot carries no CI time; the ledger row's time is the floor
                stall(issue, "ci-failing", f"PR #{number} has failing CI", updated, number)
            waiting = [t for t in (parse_time(c.get("created_at")) for c in pr.get("unanswered_comments") or []
                                   if isinstance(c, dict)) if t]
            if waiting and now - min(waiting) > stale:
                stall(issue, "unanswered-comments", f"PR #{number} has {len(waiting)} unanswered comment(s)",
                      min(waiting), number)
            sha = str(pr.get("head_sha") or "").lower()
            ledger_pass = row["review"] == "PASS" and (not row["head_sha"] or not sha or sha.startswith(row["head_sha"])
                                                       or row["head_sha"].startswith(sha))
            approved = str(pr.get("review_state") or "").upper() == "APPROVED" or ledger_pass
            if approved and ci == "success" and str(pr.get("mergeable") or "").lower() == "mergeable":
                detail = (f"the onboarding PR #{number} is green and mergeable; a person merges it"
                          if issue == ONBOARD_ISSUE else f"PR #{number} is approved, green and mergeable but not merged")
                stall(issue, "not-merged", detail, updated, number)
        issues.append(entry)

    repeat_attempts = [{"issue": i, "label": issue_label(i), "title": titles.get(i, ""), "attempts": len(g),
                        "states": [r["state"] for r in g]} for i, g in sorted(groups.items()) if len(g) >= 2]
    recent = [i for i, row in current.items() if i != ONBOARD_ISSUE and row["state"] in ("merged", "released")
              and (when := parse_time(row["updated_at"])) and now - when <= timedelta(days=SIMILAR_DAYS)]
    keys = {i: title_tokens(t) for i, t in titles.items() if i != ONBOARD_ISSUE}
    pairs, seen = [], set()
    for merged in sorted(recent):
        for other in sorted(keys):
            pair = (min(merged, other), max(merged, other))
            if other != merged and pair not in seen and similar(keys.get(merged, set()), keys[other]):
                seen.add(pair)
                pairs.append({"issue": other, "title": titles.get(other, ""), "like_merged": merged,
                              "merged_title": titles.get(merged, ""), "shared": sorted(keys[merged] & keys[other])})

    return {"repo": repo, "ledger": str(ledger_path(repo)), "now": now.isoformat(timespec="seconds"),
            "stale_hours": stale_hours,
            "sync": {"dir": snapshot["dir"], "status": snapshot["status"]} if snapshot else None,
            "counts": {s: counts[s] for s in STATES if counts.get(s)}, "issues": issues, "stalled": stalled,
            "reopened": reopened,
            "repeats": {"attempts": repeat_attempts,
                        "similar_titles": {"heuristic": True, "method": "title word overlap", "days": SIMILAR_DAYS,
                                           "pairs": pairs}}}


def render(result):
    out = [f"Software factory check for {result['repo']} at {result['now']}"]
    sync = result["sync"]
    out.append(f"Snapshot: {sync['dir']} ({sync['status']})" if sync
               else "Snapshot: none given; PR, CI and reopen checks need --sync")
    if not result["issues"]:
        out.append("The ledger has no rows.")
    out.append("Issues by state: " + (", ".join(f"{s} {n}" for s, n in result["counts"].items()) or "none"))
    onboarding = next((i for i in result["issues"] if i["issue"] == ONBOARD_ISSUE), None)
    if onboarding:
        out.append(f"Onboarding: {onboarding['state']}" + (f", PR #{onboarding['pr']}" if onboarding["pr"] else "")
                   + (f" on {onboarding['branch']}" if onboarding["branch"] else ""))
    out.append("")
    if result["stalled"]:
        out.append(f"Stalled ({len(result['stalled'])}):")
        out += [f"  {s['label']} {s['kind']}: {s['detail']}" + (f", {s['hours']}h" if s["hours"] is not None else "")
                for s in result["stalled"]]
    else:
        out.append("Stalled: nothing")
    if result["reopened"]:
        out.append(f"Reopened ({len(result['reopened'])}):")
        out += [f"  #{r['issue']}{' ' + r['title'] if r['title'] else ''}: the ledger says {r['ledger_state']}, "
                "the issue is open again" for r in result["reopened"]]
    else:
        out.append("Reopened: none")
    rep = result["repeats"]
    if rep["attempts"]:
        out.append("Built more than once:")
        out += [f"  {r['label']} {r['attempts']} attempts ({' -> '.join(r['states'])})" for r in rep["attempts"]]
    pairs = rep["similar_titles"]["pairs"]
    if pairs:
        out.append(f"Looks like an issue merged in the last {SIMILAR_DAYS} days (heuristic, title words):")
        out += [f"  #{p['issue']} {p['title']!r} like #{p['like_merged']} {p['merged_title']!r}" for p in pairs]
    if not rep["attempts"] and not pairs:
        out.append("Repeat offenders: none")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Each issue's factory state, stalled work, reopened issues and repeats.")
    ap.add_argument("repo", help="OWNER/NAME")
    ap.add_argument("--sync", help="a software_factory_sync.py output folder")
    ap.add_argument("--stale-hours", type=float, default=24,
                    help="how long building, an unshipped branch, failing CI or a comment may sit (default 24)")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--now", help=argparse.SUPPRESS)   # pretend it is this ISO time, for tests
    args = ap.parse_args(argv)
    try:
        now = None
        if args.now:
            now = parse_time(args.now)
            if now is None:
                raise UsageError(f"--now {args.now!r} is not an ISO time")
        result = check(args.repo, args.sync, args.stale_hours, now)
    except (FactoryError, OSError) as exc:
        print(f"software_factory_check: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=1) if args.format == "json" else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
