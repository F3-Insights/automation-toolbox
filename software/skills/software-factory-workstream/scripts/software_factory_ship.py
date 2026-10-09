"""Apply a software-factory session's manifest and outbox to GitHub, under the guards.

The finish phase (SOFTWARE-FACTORY.md, "software-factory-ship's guards"). It reads
RUN/sync/repo.json, and RUN/ship/manifest.json and RUN/ship/outbox.json when present, then:

1. Branches. Each manifest branch is refused, with every reason, unless the branch is the
   factory branch for its issue; the base is the integration branch and neither protected nor
   the default (with no integration branch the PR targets the default and is never merged); the
   worktree's HEAD is head_sha; verify.json says verified for that SHA, its base SHA is an
   ancestor of it and already on origin/<base>, and its commands came from that base (from the
   head only on the onboarding branch); review.json says PASS for that SHA; and the diff touches
   no protected path unless the risk is one-way-door. A branch that passes is pushed (no force;
   --force-with-lease only on `action: update` of a factory branch), its PR opened or updated with
   the body file plus the evidence and the marker, labelled software-factory:pr-open, and the
   issue told.
2. Merges. Every open factory PR (the sync's and this run's, each re-read) is squash-merged into
   the integration branch only when the rules say Auto-merge: yes, CI is success, the ledger has
   review PASS for the PR's head SHA, GitHub says mergeable, it is not a one-way door, onboarding
   or a protected-path change, and no comment is left unanswered. The merge is pinned to that SHA.
3. Release PR. With Release PR: yes and the integration branch ahead of the default, one open
   integration -> default PR is kept, listing the factory PRs merged since the last release. It
   is never merged here.
4. Outbox. Comments are posted marked as the factory's; a `kind: question` only on an issue the
   owner policy leaves to the factory, else it comes back under for_owner. Only
   software-factory:* labels are added or removed. Issue 0 (onboarding) gets no comment or label.

Nothing is ever pushed or merged to the default branch or a protected name. Every result is
recorded in the ledger; a refusal is reported, never forced. --dry-run makes the same reads,
lists every write it would make and writes nothing, not even the ledger.

Inputs: OWNER/NAME, --run RUN, --dry-run, --owner LOGIN. Needs `gh` signed in ($GH may name
another executable). Prints a summary or JSON. Exit 0 when it ran (refusals included), 1 when a
GitHub write failed or GitHub could not be read, 2 for a bad argument or unreadable input.

Example: python3 software_factory_ship.py acme/widgets --run RUN --dry-run
"""

import argparse
import json
import re
import sys
from pathlib import Path

import _common as c

RISKS = ("low", "normal", "one-way-door")
ACTIONS = ("open", "update")
BY = "software-factory-ship"
ONBOARD_TITLE = "Onboard this repository to the software factory"
PR_URL_RE = re.compile(r"https?://\S+/pull/(\d+)")
RELEASE_MARKER = "<!-- software-factory release -->"


def load(path, required):
    if not path.is_file():
        if required:
            raise c.UsageError(f"{path} not found")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise c.UsageError(f"{path} is not readable JSON: {exc}")


def resolve(run, value):
    if not value:
        return None
    p = Path(str(value)).expanduser()
    return p if p.is_absolute() else run / p


class Shipper:
    def __init__(self, repo, run, info, dry, owner):
        self.repo, self.run, self.info, self.dry = repo, run, info, dry
        self.owner = owner or info.get("owner_login") or None
        self.rules = info.get("rules") or {}
        self.patterns = c.protected_paths(self.rules)
        self.rows = c.latest(c.read_ledger(repo))
        self.out = {"repo": repo, "dry_run": dry, "actions": [], "refused": [], "opened": [], "updated": [],
                    "merged": [], "not_merged": [], "release": None, "comments": [], "labels": [],
                    "for_owner": [], "failures": [], "recorded": [], "notes": []}
        self.one_way = set()          # PR numbers this run knows are one-way doors
        self.protected_hits = {}
        self.labels_known = None
        self.notes = {}               # every note this run recorded, per issue

    default = property(lambda self: self.info["default_branch"])

    @property
    def integration(self):
        integ = self.info.get("integration_branch") or self.default
        return self.default if integ != self.default and c.is_protected(integ, self.default) else integ

    @property
    def has_integration(self):
        return self.integration != self.default

    def write(self, what, fn, *args):
        """One GitHub or git write: listed under actions; in a dry run, not made."""
        self.out["actions"].append(("would " if self.dry else "") + what)
        if self.dry:
            return None
        result = fn(*args)
        if not result.ok:
            self.out["failures"].append(f"{what}: {result.tail()}")
        return result

    def record(self, issue, state=None, **fields):
        if issue is None:
            return
        state = state or (self.rows.get(int(issue)) or {}).get("state")
        if not state:
            self.out["notes"].append(f"{c.issue_label(issue)}: no ledger row to record on ({fields.get('note') or ''})")
            return
        if fields.get("note"):   # one note column: keep every note this run writes for the issue
            self.notes.setdefault(int(issue), []).append(str(fields["note"]))
            fields["note"] = "; ".join(self.notes[int(issue)])
        desc = f"record {c.issue_label(issue)} {state}" + (f" ({fields['note']})" if fields.get("note") else "")
        if self.dry:
            self.out["actions"].append("would " + desc)
            return
        try:
            done = c.record(self.repo, issue, state, BY, **fields)
        except (c.FactoryError, OSError) as exc:
            self.out["notes"].append(f"ledger record for {c.issue_label(issue)} failed: {exc}")
            return
        self.rows[int(issue)] = done["row"]
        self.out["recorded"].append(f"{done['id']} {state}")

    # -- branches ------------------------------------------------------------------------------

    def read_json(self, value, name, reasons):
        path = resolve(self.run, value)
        if path is None or not path.is_file():
            reasons.append(f"{name} {value!r} not found")
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            reasons.append(f"{name} is not readable JSON: {exc}")
            return None
        if not isinstance(data, dict):
            reasons.append(f"{name} is not a JSON object")
            return None
        return data

    def guard(self, e):
        """(reasons to refuse, facts) for one manifest branch."""
        reasons, facts = [], {}
        branch, issue, base = str(e.get("branch") or ""), e.get("issue"), str(e.get("base") or "")
        sha, risk = str(e.get("head_sha") or "").strip().lower(), str(e.get("risk") or "")
        if not c.BRANCH_RE.match(branch):
            reasons.append(f"branch {branch!r} is not a factory branch (software-factory/issue-<n>-<slug>, "
                           f"or {c.ONBOARD_BRANCH} for issue 0)")
        elif c.issue_of_branch(branch) != (int(issue) if str(issue).isdigit() else issue):
            reasons.append(f"branch {branch!r} is not the onboarding branch {c.ONBOARD_BRANCH} (issue 0)"
                           if str(issue) == "0" else f"branch {branch!r} is not issue #{issue}'s")
        if self.has_integration:
            if base != self.integration:
                reasons.append(f"base {base!r} is not the integration branch {self.integration!r}")
            if c.is_protected(base, self.default):
                reasons.append(f"base {base!r} is the default or a protected branch")
        elif base != self.default:
            reasons.append(f"the repo has no integration branch, so PRs target {self.default!r}, not {base!r}")
        if risk not in RISKS:
            reasons.append(f"risk {risk!r} is not one of {', '.join(RISKS)}")
        if e.get("action") not in ACTIONS:
            reasons.append(f"action {e.get('action')!r} is not open or update")
        if len(sha) < 7:
            reasons.append("no head_sha")
        body = resolve(self.run, e.get("body_file"))
        if body is None or not body.is_file():
            reasons.append(f"body file {e.get('body_file')!r} not found")
        wt = resolve(self.run, e.get("worktree"))
        if wt is None or not wt.is_dir():
            reasons.append(f"worktree {e.get('worktree')!r} not found")
            return reasons, facts
        head = c.git(wt, "rev-parse", "HEAD")
        if not head.ok or not c.same_sha(head.stdout.strip(), sha):
            reasons.append(f"the worktree's HEAD {head.stdout.strip()[:12] or head.tail()} is not head_sha {sha[:12]}")
        on = c.git(wt, "rev-parse", "--abbrev-ref", "HEAD")
        if on.ok and on.stdout.strip() != branch:
            reasons.append(f"the worktree is on {on.stdout.strip()!r}, not {branch!r}")
        verify = self.read_json(e.get("verify_file"), "verify.json", reasons)
        if verify is not None:
            facts["verify"] = verify
            if verify.get("verdict") != "verified":
                reasons.append(f"verify.json verdict is {verify.get('verdict')!r}, not verified")
            if not c.same_sha(verify.get("head_sha"), sha):
                reasons.append(f"verify.json is for {str(verify.get('head_sha') or '')[:12]}, not {sha[:12]}")
            base_sha = str(verify.get("base_sha") or "")
            if not base_sha:
                reasons.append("verify.json names no base_sha")
            elif not c.git(wt, "merge-base", "--is-ancestor", base_sha, sha).ok:
                reasons.append(f"verify.json's base {base_sha[:12]} is not an ancestor of {sha[:12]}")
            elif c.same_sha(base_sha, sha):
                reasons.append(f"verify.json's base is the branch's own head {sha[:12]}")
            elif not c.git(wt, "merge-base", "--is-ancestor", base_sha, f"origin/{base}").ok:
                # the commands and the coverage minimum must come from history the base branch already has
                reasons.append(f"verify.json's base {base_sha[:12]} is not on origin/{base}")
            reasons += self.commands_source(verify, base_sha, sha, branch, facts)
        review = self.read_json(e.get("review_file"), "review.json", reasons)
        if review is not None:
            facts["review"] = review
            if str(review.get("review") or "").upper() != "PASS":
                reasons.append(f"review.json says {review.get('review')!r}, not PASS")
            if not c.same_sha(review.get("head_sha"), sha):
                reasons.append(f"review.json is for {str(review.get('head_sha') or '')[:12]}, not {sha[:12]}")
        if self.patterns:
            diff = c.git(wt, "diff", "--name-only", f"origin/{base}...{sha}")
            if not diff.ok:
                reasons.append(f"could not list the changed files: {diff.tail()}")
            else:
                hits = facts["protected_hits"] = c.touches(diff.stdout.splitlines(), self.patterns)
                if hits and risk != "one-way-door":
                    reasons.append("touches protected paths (" + ", ".join(hits[:5]) + ") but risk is not one-way-door")
        return reasons, facts

    @staticmethod
    def commands_source(verify, base_sha, sha, branch, facts):
        """Why verify.json's commands_from is not acceptable: the base always is; the head only
        on the onboarding branch; anything else never."""
        source = str(verify.get("commands_from") or "")
        if not source:
            return []
        at = source.rsplit("@", 1)[1] if "@" in source else ""
        if base_sha and c.same_sha(at, base_sha):
            return []
        if c.same_sha(at, sha):
            if c.is_onboarding(branch):
                facts["commands_from_head"] = True
                return []
            return [f"verify.json read the commands from the branch's head ({source}); only the onboarding "
                    f"branch {c.ONBOARD_BRANCH} may, every other branch is judged by the base's"]
        return [f"verify.json read the commands from {source}, not the base {base_sha[:12]}"]

    def evidence(self, e, facts):
        v, r = facts.get("verify") or {}, facts.get("review") or {}
        at = f" at `{str(v.get('base_sha'))[:12]}`" if v.get("base_sha") else ""
        lines = ["## Evidence", "", f"- Head `{str(e['head_sha'])[:12]}` on `{e['branch']}`, base `{e['base']}`{at}."]
        lines += [f"- {s.get('name')}: `{s.get('run')}` exit {s.get('exit')}" + (f", {s['summary']}" if s.get("summary") else "")
                  for s in v.get("steps") or []]
        rep = v.get("repro") or {}
        if rep.get("command"):
            lines.append(f"- Repro `{rep['command']}`: base exit {rep.get('base_exit')}, head exit {rep.get('head_exit')}")
        lines.append(f"- Verify: {v.get('verdict')}" + (" (offline)" if v.get("offline") else "") + ".")
        lines.append(f"- Review: {str(r.get('review') or '').upper()}" + (f". {r['summary']}" if r.get("summary") else "") + ".")
        lines.append(f"- Risk: {e.get('risk')}.")
        if c.is_onboarding(str(e.get("branch") or "")):
            lines.append("- Onboarding: this pull request writes the repository's `.software-factory/` folder"
                         + (", and its checks were read from this branch's head because the base has none yet"
                            if facts.get("commands_from_head") else "")
                         + ". A person reviews and merges it; the factory never does.")
        if facts.get("protected_hits"):
            lines.append("- Protected paths touched: " + ", ".join(facts["protected_hits"])
                         + ". A one-way door: the factory never merges this; a person does.")
        if not self.has_integration:
            lines.append(f"- The repo has no integration branch: this PR targets `{self.default}` and only a person merges it.")
        return "\n".join(lines)

    def pr_body(self, e, facts):
        body = resolve(self.run, e["body_file"]).read_text(encoding="utf-8").rstrip()
        issue = int(e["issue"])
        if issue != c.ONBOARD_ISSUE and not re.search(rf"#{issue}\b", body):
            body += f"\n\n{'Closes' if e['base'] == self.default else 'Refs'} #{issue}"
        return f"{body}\n\n{self.evidence(e, facts)}\n\n{c.MARKER}\n"

    def ensure_labels(self, wanted):
        if self.labels_known is None:
            listed = c.gh("label", "list", "-R", self.repo, "--limit", "500", "--json", "name")
            try:
                self.labels_known = {str(l.get("name")) for l in c.parse_json(listed.stdout, "gh label list") or []} \
                    if listed.ok else set()
            except c.GitHubError:
                self.labels_known = set()
        for name in wanted:
            if name not in self.labels_known:
                self.write(f"create label {name}", c.gh, "label", "create", name, "-R", self.repo,
                           "--description", "Set by the software factory")
                self.labels_known.add(name)

    def ship_branch(self, e):
        issue, branch = e.get("issue"), str(e.get("branch") or "")
        reasons, facts = self.guard(e)
        if reasons:
            self.out["refused"].append({"issue": issue, "branch": branch, "reasons": reasons})
            self.record(int(issue) if str(issue).isdigit() else None, note="ship refused: " + "; ".join(reasons))
            return
        issue, sha, wt = int(issue), str(e["head_sha"]).strip().lower(), resolve(self.run, e["worktree"])
        try:
            existing = c.gh_json("gh pr list", "pr", "list", "-R", self.repo, "--head", branch, "--state", "open",
                                 "--json", "number,url,baseRefName,headRefName") or []
            existing = existing[0] if existing else None
        except c.GitHubError as exc:
            self.out["failures"].append(f"#{issue}: could not look for an open PR: {exc}")
            return
        if existing and existing.get("baseRefName") != e["base"]:
            reason = f"an open PR #{existing.get('number')} for {branch} targets {existing.get('baseRefName')!r}"
            self.out["refused"].append({"issue": issue, "branch": branch, "reasons": [reason]})
            self.record(issue, note="ship refused: " + reason)
            return
        refspec = f"refs/heads/{branch}:refs/heads/{branch}"
        if e["action"] == "update" and c.BRANCH_RE.match(branch):
            pushed = self.write(f"push {branch} with --force-with-lease", c.git, wt, "push",
                                f"--force-with-lease={branch}", "origin", refspec)
        else:
            pushed = self.write(f"push {branch}", c.git, wt, "push", "origin", refspec)
        if pushed is not None and not pushed.ok:
            return
        onboarding = issue == c.ONBOARD_ISSUE
        one_way = e["risk"] == "one-way-door" or bool(facts.get("protected_hits")) or onboarding
        body_file = self.run / "ship" / f"pr-{issue}.final.md"
        if not self.dry:
            body_file.parent.mkdir(parents=True, exist_ok=True)
            body_file.write_text(self.pr_body(e, facts), encoding="utf-8")
        self.ensure_labels([c.PR_OPEN_LABEL])
        title = str(e.get("title") or (ONBOARD_TITLE if onboarding else f"Issue #{issue}"))
        if existing is None:
            made = self.write(f"open PR {branch} -> {e['base']}", c.gh, "pr", "create", "-R", self.repo, "--base",
                              e["base"], "--head", branch, "--title", title, "--body-file", str(body_file))
            if made is None:   # dry run
                self.out["actions"].append(f"would label the new PR {c.PR_OPEN_LABEL}")
                if not onboarding:
                    self.out["actions"].append(f"would comment on issue #{issue} linking the PR")
                self.out["opened"].append({"issue": issue, "branch": branch, "pr": None})
                self.record(issue, "pr-open", branch=branch, head_sha=sha, verify="verified", review="PASS",
                            risk=e["risk"])
                return
            if not made.ok:
                return
            m = PR_URL_RE.search(made.stdout)
            if not m:
                self.out["failures"].append(f"gh pr create for {branch} printed no PR URL: {made.tail()}")
                return
            number, url = int(m.group(1)), m.group(0)
            self.write(f"label PR #{number} {c.PR_OPEN_LABEL}", c.gh, "pr", "edit", str(number), "-R", self.repo,
                       "--add-label", c.PR_OPEN_LABEL)
            if not onboarding:   # issue 0 is no GitHub issue: nothing to tell
                note = " It touches a one-way door, so a person reviews and merges it." if one_way else ""
                self.write(f"comment on issue #{issue} linking PR #{number}", c.gh, "issue", "comment", str(issue),
                           "-R", self.repo, "--body",
                           c.marked(f"Opened pull request #{number} ({url}) for this issue, into `{e['base']}`.{note}"))
            self.out["opened"].append({"issue": issue, "branch": branch, "pr": number, "url": url})
        else:
            number, url = int(existing["number"]), existing.get("url")
            self.write(f"update PR #{number} body", c.gh, "pr", "edit", str(number), "-R", self.repo,
                       "--body-file", str(body_file), "--add-label", c.PR_OPEN_LABEL)
            changes = str(e.get("changes") or "").strip()
            self.write(f"comment on PR #{number} what changed", c.gh, "pr", "comment", str(number), "-R", self.repo,
                       "--body", c.marked(f"Pushed `{sha[:12]}` to `{branch}`." + (f"\n\n{changes}" if changes else "")
                                          + "\n\nThe evidence in the description is for this commit."))
            self.out["updated"].append({"issue": issue, "branch": branch, "pr": number, "url": url})
        if one_way:
            self.one_way.add(number)
        self.protected_hits[number] = facts.get("protected_hits") or []
        self.record(issue, "pr-open", branch=branch, pr=number, head_sha=sha, verify="verified", review="PASS",
                    risk=e["risk"])

    # -- merges --------------------------------------------------------------------------------

    def merge_pass(self, numbers):
        for number in sorted({n for n in numbers if n}):
            try:
                raw = c.gh_json("gh pr view", "pr", "view", str(number), "-R", self.repo, "--json", c.PR_FIELDS) or {}
                if not c.BRANCH_RE.match(str(raw.get("headRefName") or "")):
                    self.out["not_merged"].append({"pr": number, "reasons": ["not a factory branch"]})
                    continue
                pr = c.factory_pr(self.repo, raw, logs=False)
                hits = self.protected_hits.get(number)
                if hits is None and self.patterns:
                    names = c.need(c.gh("pr", "diff", str(number), "-R", self.repo, "--name-only"), "gh pr diff")
                    hits = c.touches(names.stdout.splitlines(), self.patterns)
            except c.GitHubError as exc:
                self.out["not_merged"].append({"pr": number, "reasons": [f"could not read it: {exc}"]})
                continue
            row = self.rows.get(pr["issue"] if pr["issue"] is not None else -1)
            blockers = c.merge_blockers(pr, self.rules, self.integration, self.default, row,
                                        one_way_door=number in self.one_way, protected_hits=hits)
            if blockers:
                self.out["not_merged"].append({"pr": number, "issue": pr["issue"], "reasons": blockers})
                continue
            # The guard again at the point of writing: never into the default or a protected branch.
            if c.is_protected(pr["base"], self.default) or pr["base"] != self.integration:
                self.out["not_merged"].append({"pr": number, "reasons": ["base is not the integration branch"]})
                continue
            done = self.write(f"squash-merge PR #{number} into {pr['base']}", c.gh, "pr", "merge", str(number),
                              "-R", self.repo, "--squash", "--delete-branch", "--match-head-commit", pr["head_sha"])
            if done is not None and not done.ok:
                continue
            self.out["merged"].append({"pr": number, "issue": pr["issue"], "head_sha": pr["head_sha"]})
            self.record(pr["issue"], "merged", pr=number)

    # -- release PR ----------------------------------------------------------------------------

    def release(self):
        if not c.yes(self.rules.get("release pr")):
            self.out["release"] = {"action": "none", "reason": "the rules do not say Release PR: yes"}
            return
        if not self.has_integration:
            self.out["release"] = {"action": "none", "reason": "no integration branch"}
            return
        clone = Path(self.info.get("local_clone") or c.local_clone(self.repo))
        integ, default = self.integration, self.default
        c.git(clone, "fetch", "origin", "--prune")
        ahead = c.git(clone, "rev-list", "--count", f"refs/remotes/origin/{default}..refs/remotes/origin/{integ}")
        if not ahead.ok:
            self.out["release"] = {"action": "none", "reason": f"could not compare branches: {ahead.tail()}"}
            return
        if int(ahead.stdout.strip() or 0) == 0:
            self.out["release"] = {"action": "none", "reason": f"{integ} is not ahead of {default}"}
            return
        try:
            existing = c.gh_json("gh pr list", "pr", "list", "-R", self.repo, "--head", integ, "--base", default,
                                 "--state", "open", "--json", "number,url,body") or []
            merged = c.gh_json("gh pr list", "pr", "list", "-R", self.repo, "--base", integ, "--state", "merged",
                               "--limit", "200", "--json", "number,title,url,headRefName,mergedAt,mergeCommit") or []
        except c.GitHubError as exc:
            self.out["release"] = {"action": "none", "reason": str(exc)}
            return
        entries = []
        for pr in sorted(merged, key=lambda p: str(p.get("mergedAt") or "")):
            if not c.BRANCH_RE.match(str(pr.get("headRefName") or "")):
                continue
            oid = str((pr.get("mergeCommit") or {}).get("oid") or "")
            if oid and c.git(clone, "merge-base", "--is-ancestor", oid, f"refs/remotes/origin/{default}").ok:
                continue   # already released
            entries.append(pr)
        lines = [f"Everything merged into `{integ}` since `{default}` last moved. A person merges this pull "
                 "request; the software factory never does.", ""]
        for pr in entries:
            issue = c.issue_of_branch(str(pr.get("headRefName")))
            what = "onboarding" if issue == c.ONBOARD_ISSUE else f"issue #{issue}"
            lines.append(f"- #{pr.get('number')} {pr.get('title')} ({what}), merged {str(pr.get('mergedAt'))[:10]}")
        if not entries:
            lines.append("- No factory pull requests; the difference is other commits.")
        body = "\n".join(lines) + f"\n\n{RELEASE_MARKER}\n{c.MARKER}\n"
        body_file = self.run / "ship" / "release-pr.md"
        if not self.dry:
            body_file.parent.mkdir(parents=True, exist_ok=True)
            body_file.write_text(body, encoding="utf-8")
        numbers = [p.get("number") for p in entries]
        if not existing:
            made = self.write(f"open release PR {integ} -> {default}", c.gh, "pr", "create", "-R", self.repo,
                              "--base", default, "--head", integ, "--title", f"Release {integ} to {default}",
                              "--body-file", str(body_file))
            m = PR_URL_RE.search(made.stdout) if made is not None and made.ok else None
            self.out["release"] = {"action": "created", "pr": int(m.group(1)) if m else None, "entries": numbers}
            return
        first, action = existing[0], "unchanged"
        if str(first.get("body") or "").strip() != body.strip():
            self.write(f"update release PR #{first.get('number')} body", c.gh, "pr", "edit", str(first.get("number")),
                       "-R", self.repo, "--body-file", str(body_file))
            action = "updated"
        self.out["release"] = {"action": action, "pr": first.get("number"),
                               "others": [int(p.get("number") or 0) for p in existing[1:]], "entries": numbers}

    # -- outbox --------------------------------------------------------------------------------

    def may_ask(self, issue):
        """Why the owner policy keeps a question off this issue; empty when it may be asked."""
        if not self.owner:
            try:
                self.owner = c.owner_login()
            except c.GitHubError as exc:
                return [f"the owner's login is unknown ({exc})"]
        try:
            raw = c.gh_json("gh issue view", "issue", "view", str(issue), "-R", self.repo, "--json",
                            "number,title,labels,state,updatedAt,createdAt,assignees,author,body")
        except c.GitHubError as exc:
            return [f"could not read the issue ({exc})"]
        return c.exclusion_reasons(c.normalise_issue(raw or {"number": issue}), self.owner)

    def outbox(self, box):
        for item in box.get("comments") or []:
            issue, body, kind = item.get("issue"), str(item.get("body") or ""), str(item.get("kind") or "status")
            if not str(issue).isdigit() or not body.strip():
                self.out["notes"].append(f"outbox comment skipped: needs an issue number and a body ({item!r:.80})")
                continue
            issue = int(issue)
            if issue == c.ONBOARD_ISSUE:
                self.out["notes"].append("outbox comment skipped: issue 0 is onboarding, not a GitHub issue")
                continue
            if kind == "question":
                reasons = self.may_ask(issue)
                if reasons:
                    self.out["for_owner"].append({"issue": issue, "body": body, "reasons": reasons})
                    self.record(issue, note="question held for the owner: " + "; ".join(reasons))
                    continue
            done = self.write(f"comment on #{issue} ({kind})", c.gh, "issue", "comment", str(issue), "-R", self.repo,
                              "--body", c.marked(body))
            if done is None or done.ok:
                self.out["comments"].append({"issue": issue, "kind": kind})
                self.record(issue, note=f"posted {kind} comment")
        for item in box.get("labels") or []:
            issue = item.get("issue")
            add, remove = [str(x) for x in item.get("add") or []], [str(x) for x in item.get("remove") or []]
            bad = [x for x in add + remove if not x.startswith(c.LABEL_PREFIX)]
            if str(issue) == "0":
                self.out["notes"].append("outbox labels skipped: issue 0 is onboarding, not a GitHub issue")
                continue
            if not str(issue).isdigit() or bad or not (add or remove):
                self.out["notes"].append(f"outbox labels skipped for #{issue}: " + (
                    f"only {c.LABEL_PREFIX}* labels ({', '.join(bad)})" if bad else "nothing to do"))
                continue
            self.ensure_labels(add)
            argv = ["issue", "edit", str(issue), "-R", self.repo]
            argv += ["--add-label", ",".join(add)] if add else []
            argv += ["--remove-label", ",".join(remove)] if remove else []
            done = self.write(f"labels on #{issue}: +{','.join(add)} -{','.join(remove)}", c.gh, *argv)
            if done is None or done.ok:
                self.out["labels"].append({"issue": int(issue), "add": add, "remove": remove})


def ship(repo, run, dry=False, owner=None):
    """Apply the manifest and the outbox. UsageError for unreadable input; GitHubError when the
    default branch cannot be confirmed (then nothing is written)."""
    info = load(run / "sync" / "repo.json", True)
    if not isinstance(info, dict) or f"{info.get('owner')}/{info.get('name')}" != repo:
        raise c.UsageError(f"{run}/sync/repo.json is not for {repo}")
    manifest = load(run / "ship" / "manifest.json", False) or {}
    box = load(run / "ship" / "outbox.json", False) or {}
    if not isinstance(manifest, dict) or not isinstance(box, dict):
        raise c.UsageError("manifest.json and outbox.json must be JSON objects")
    if manifest.get("repo") not in (None, repo):
        raise c.UsageError(f"manifest.json is for {manifest.get('repo')}, not {repo}")
    prs = load(run / "sync" / "prs.json", False) or []
    synced_default = info.get("default_branch")
    live_default = c.default_branch(repo)    # GitHub's word now, not only the snapshot's
    s = Shipper(repo, run, dict(info, default_branch=live_default), dry, owner)
    if live_default != synced_default:
        s.out["notes"].append(f"the default branch is now {live_default}, not {synced_default} as sync read")
    for e in manifest.get("branches") or []:
        if isinstance(e, dict):
            s.ship_branch(e)
    numbers = [int(p.get("number") or 0) for p in prs if isinstance(p, dict)]
    numbers += [x["pr"] for x in s.out["opened"] + s.out["updated"] if x.get("pr")]
    s.merge_pass(numbers)
    s.release()
    s.outbox(box)
    return s.out


def text_report(out):
    lines = [f"{'DRY RUN' if out['dry_run'] else 'SHIPPED'}: {len(out['opened'])} opened, {len(out['updated'])} updated, "
             f"{len(out['merged'])} merged, {len(out['refused'])} refused, {len(out['comments'])} comments, "
             f"{len(out['for_owner'])} for the owner, {len(out['failures'])} failed"]
    lines += [f"- refused {c.issue_label(r['issue'])} {r['branch']}: " + "; ".join(r["reasons"]) for r in out["refused"]]
    lines += [f"- merged PR #{m['pr']} ({c.issue_label(m['issue'])})" for m in out["merged"]]
    lines += [f"- not merged PR #{n['pr']}: " + "; ".join(n["reasons"]) for n in out["not_merged"]]
    if out["release"]:
        rel = out["release"]
        lines.append(f"- release PR: {rel.get('action')}" + (f" #{rel['pr']}" if rel.get("pr") else "")
                     + (f" ({rel['reason']})" if rel.get("reason") else ""))
    lines += [f"- for the owner, question on #{q['issue']} ({'; '.join(q['reasons'])}): {q['body'][:200]}"
              for q in out["for_owner"]]
    lines += [f"- FAILED {f}" for f in out["failures"]] + [f"- note: {n}" for n in out["notes"]]
    lines += [f"- {a}" for a in out["actions"]]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Push, open, merge and comment for OWNER/NAME from a RUN folder, under guards.")
    ap.add_argument("repo", help="OWNER/NAME")
    ap.add_argument("--run", required=True, help="the Run folder")
    ap.add_argument("--dry-run", action="store_true", help="list every write it would make; write nothing")
    ap.add_argument("--owner", help="the owner's GitHub login (default: repo.json, else gh api user)")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args(argv)
    try:
        c.split_repo(args.repo)
        out = ship(args.repo, Path(args.run).expanduser().resolve(), args.dry_run, args.owner)
    except c.FactoryError as exc:
        print(f"software_factory_ship: {exc}", file=sys.stderr)
        return 2
    except c.GitHubError as exc:
        print(f"software_factory_ship: nothing shipped, GitHub could not be read: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(out, indent=1) if args.format == "json" else text_report(out))
    return 1 if out["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
