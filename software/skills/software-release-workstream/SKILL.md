---
name: software-release-workstream
description: Reference loaded by software-release-writer, software-release-checker and software-release-orchestrator, not for a user request; adds to orchestration-workstream. Covers a repository's integration-to-default release read offline from the local clone and the factory ledger, the release notes, release pull request body and deploy checklist a person works from, the GitHub writes drafted as github-drafts.json for a later finish step, and the DONE checklist. To prepare a release, start software-release-orchestrator.
---

# Software release workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Load it if it is not loaded. What follows is only what a release adds.

The software factory merges verified, reviewed work into a repository's integration branch and keeps one release pull request (integration to default) open for a person. This work makes that release easy and safe for the person: notes that say what ships, a pull request body a reviewer can act on (`software-pr`), the issues the release closes, and a deploy checklist that names every migration and gate. A person merges, deploys and runs migrations. Agents never do.

## Offline

The session has no route to GitHub. It reads:
- the local clone, with `git -C <clone>` read-only commands only (`log`, `show`, `diff --stat`, `branch`, `rev-parse`), on the remote-tracking refs as last fetched. Say how old the fetch is (`FETCH_HEAD`'s time); older than a day is a finding;
- the factory's ledger for the repository, read only: which issue each branch fixed, its verify and review verdicts, and its PR number;
- the repository's own docs: the factory rules file, the deploy and migration docs it names.

## The range

The release is `origin/<default>..origin/<integration>`. Each merge in it is a factory PR (its ledger row) or a person's change (no row). A person's change gets no review verdict from the ledger and is flagged for the person's review.

## What is written (all in `RUN/release/`)

- `RELEASE-NOTES.md`: grouped as Fixed, Added, Changed, Internal; one line per change in user terms, its PR and issue; nothing claimed that is not in the range.
- `pr-body.md`: the release pull request body in the `software-pr` shape, covering the range.
- `DEPLOY-CHECKLIST.md`: every migration file added or changed in the range with the command a person runs; config and secrets to set; both review passes (code and security) per change, from the ledger or marked "a person reviews"; the deploy steps from the repo's docs; how to roll back; the smoke checks after deploy.
- `github-drafts.json`, the GitHub writes for a later finish step:

```json
{"repo": "owner/name", "range": {"base": "<sha>", "head": "<sha>"}, "fetched_at": "...",
 "release_pr": {"number": 120, "body_file": "release/pr-body.md"},
 "comments": [{"issue": 42, "body": "...", "when": "now|on-release"}],
 "close": [{"issue": 42, "why": "fix <sha> is on <default> since <date>"}]}
```

`close` holds only issues whose fix is already on the default branch and that are still open; an issue fixed in the open release goes in `comments` with `when: on-release`.

## DONE checklist

The orchestrator checks each; starred lines are confirmed by `software-release-checker`.

1. The range, its SHAs and the fetch age are stated.
2. * Every merge in the range appears in the notes or is named as internal.
3. * Every `close` entry's fix commit is on the default branch.
4. * Every migration file changed in the range is in the deploy checklist with its command.
5. * Every change carries a code and a security review verdict, or "a person reviews".
6. Nothing in a public repository's drafts carries a private name or a client term.
7. Nothing was pushed, merged, deployed or run against a database, and GitHub was not touched.

## Later tools

- `release-snapshot` (prepare): fetch the clone and snapshot the release PR, open issues and CI.
- `release-ship` (finish): apply `github-drafts.json` under guards (update the release PR body, post comments, close listed issues; never merge), the way `software-factory-ship` applies its outbox.
- `release-check --precheck`: an integration branch ahead of default with no drafts newer than its head.
