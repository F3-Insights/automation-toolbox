---
name: software-release-workstream
description: "The software release's method, loaded by software-release-orchestrator and by the software-reviewer it dispatches, not for a user request; adds to orchestration-workstream. Covers a repository's integration-to-default release read offline from the local clone, the sections Prepare a release, Write the release and Check the release, the release notes, release pull request body and deploy checklist a person works from, the GitHub writes drafted as github-drafts.json for a later finish step, and the DONE checklist. To prepare a release, start software-release-orchestrator."
---

# Software release workstream

This skill extends `orchestration-workstream`: keep its conduct and return its block. Load it if it is not loaded. What follows is only what a release adds.

The issue loop (`software-orchestrator`) merges verified agent pull requests into a repository's integration branch; promotion to the default branch belongs to a person, through one release pull request (integration to default). This work makes that release easy and safe for the person: notes that say what ships, a pull request body a reviewer can act on (`software-pr`), the issues the release closes, and a deploy checklist that names every migration and gate. A person merges, deploys and runs migrations. Agents never do.

## Offline

The session has no route to GitHub. It reads:
- the local clone, with `git -C <clone>` read-only commands only (`log`, `show`, `diff --stat`, `branch`, `rev-parse`, `merge-base`), on the remote-tracking refs as last fetched. Say how old the fetch is (`FETCH_HEAD`'s time); older than a day is a finding;
- each merge's own record in the clone: its PR number, its branch (`issue/N-slug` for an issue-loop PR) and its message, which for an issue-loop PR carries `Closes #N` and how the change was verified;
- the repository's own docs: its agent file (`AGENTS.md`), README and the deploy and migration docs they name.

## The range

The release is `origin/<default>..origin/<integration>`. Each merge in it is an issue-loop PR (from an `issue/N-slug` branch) or a person's change. A change whose merge record does not show how it was verified and reviewed is flagged for the person's review.

## Prepare a release

For `software-release-orchestrator`.

1. Read the release rules (which repositories release this way, their local clones, integration and default branches) and the repository's agent file and deploy docs. If the repository has no integration branch, write notes for the last week's merges only and say so.
2. Find the range and the fetch age with `git -C`. Read each merge's record. Write `RUN/plan.json`: the merges, each marked issue-loop PR (with its issue) or a person's change.
3. Write the release yourself, by the section Write the release, into `RUN/release/`.
4. Dispatch `software-reviewer`, told to use this skill's section Check the release, with the drafts' folder and the clone path only, never your plan's reasoning. On a FAIL, answer each fix once and send it back; a second FAIL stays in the report.
5. Walk the DONE checklist into `RUN/done.md`, each line with its evidence.

## Write the release

1. Read each merge in the plan with `git -C <clone> show --stat`, the issue it closes (`Closes #N`) and how it was verified, from the commit message.
2. Write `RELEASE-NOTES.md` in user terms, one line per change.
3. Write `pr-body.md` in the `software-pr` shape for the whole range.
4. Write `DEPLOY-CHECKLIST.md`: every migration file the range adds or changes (from `git -C <clone> diff --stat` over the range) with its command from the repo's docs, then the review verdicts, config, deploy, rollback and smoke checks.
5. Write `github-drafts.json` as shown below.

Only read-only `git -C` commands; write only in `RUN/release/`.

## What is written (all in `RUN/release/`)

- `RELEASE-NOTES.md`: grouped as Fixed, Added, Changed, Internal; one line per change in user terms, its PR and issue; nothing claimed that is not in the range.
- `pr-body.md`: the release pull request body in the `software-pr` shape, covering the range.
- `DEPLOY-CHECKLIST.md`: every migration file added or changed in the range with the command a person runs; config and secrets to set; both review passes (code and security) per change, from the merge record or marked "a person reviews"; the deploy steps from the repo's docs; how to roll back; the smoke checks after deploy.
- `github-drafts.json`, the GitHub writes for a later finish step:

```json
{"repo": "owner/name", "range": {"base": "<sha>", "head": "<sha>"}, "fetched_at": "...",
 "release_pr": {"number": 120, "body_file": "release/pr-body.md"},
 "comments": [{"issue": 42, "body": "...", "when": "now|on-release"}],
 "close": [{"issue": 42, "why": "fix <sha> is on <default> since <date>"}]}
```

`close` holds only issues whose fix is already on the default branch and that are still open; an issue fixed in the open release goes in `comments` with `when: on-release`.

## Check the release

For `software-reviewer`, from the drafts and the clone only. Recompute the range yourself with read-only `git -C` commands and check the starred lines of the DONE checklist against it:

- each merge in the range is in `RELEASE-NOTES.md` or named internal;
- each `close` issue's fix commit is an ancestor of the default branch (`git -C <clone> merge-base --is-ancestor` or `branch --contains`);
- each migration file changed in the range is on `DEPLOY-CHECKLIST.md` with a command;
- each change's review verdict matches its merge record, or it says "a person reviews";
- for a public repository, no private name, client term or internal path in any draft.

Return the `orchestration-workstream` block with `workstream: "software-release-check"`: one `items` row per check, `state` `PASS` or `FAIL`, `evidence` the command or file, and for a FAIL the fix in `note`.

## DONE checklist

The orchestrator checks each; starred lines are confirmed by the reviewer's Check the release.

1. The range, its SHAs and the fetch age are stated.
2. * Every merge in the range appears in the notes or is named as internal.
3. * Every `close` entry's fix commit is on the default branch.
4. * Every migration file changed in the range is in the deploy checklist with its command.
5. * Every change carries a code and a security review verdict, or "a person reviews".
6. Nothing in a public repository's drafts carries a private name or a client term.
7. Nothing was pushed, merged, deployed or run against a database, and GitHub was not touched.

## Later tools

- `release-snapshot` (prepare): fetch the clone and snapshot the release PR, open issues and CI.
- `release-ship` (finish): apply `github-drafts.json` under guards (update the release PR body, post comments, close listed issues; never merge), as a deterministic finish command after the session.
- `release-check --precheck`: an integration branch ahead of default with no drafts newer than its head.
